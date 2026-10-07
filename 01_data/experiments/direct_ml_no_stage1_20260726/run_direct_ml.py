# -*- coding: utf-8 -*-
"""Experiment: direct ML regression, NO stage1 hurdle gate.

เอา Part 1-5 ของ inflow_forecasting_MULTIMODEL_stratified_split_retrain.ipynb (การเทรน
delta-regression ตรงๆ ทุกแถว ไม่มี stage1 classifier กรอง zero/nonzero) มาปรับให้รันเป็น
สคริปต์เดี่ยว ชี้ input ไปที่ Training_Values_Nofct_7day_Extended.csv (ไฟล์เดียวกับที่ production
ใช้อยู่บางส่วน) วิธี split/metric/Optuna search space เหมือนต้นฉบับทุกประการ ไม่ได้ปรับอะไรเพิ่ม
เพื่อให้เทียบผลได้ตรงไปตรงมา

Output: outputs/all_models_test_performance.csv, outputs/cv_stability_diagnostic.csv,
        outputs/all_models_tuned_params.csv
"""
import os
import re
import time
import warnings
import numpy as np
import pandas as pd
import optuna
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

OUTDIR = "outputs"
os.makedirs(OUTDIR, exist_ok=True)

# =============================================================================
# Model adapters (เหมือนต้นฉบับทุกประการ)
# =============================================================================
from catboost import CatBoostRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import lightgbm as lgb


class CatBoostAdapter:
    name = "CatBoost"

    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params)
        p.setdefault("loss_function", "MAE")
        p.setdefault("bootstrap_type", "Bernoulli")
        p.setdefault("random_seed", 42)
        p.setdefault("verbose", False)
        if with_early_stopping:
            p.setdefault("od_type", "Iter")
            p.setdefault("od_wait", 200)
        return CatBoostRegressor(**p)

    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=(X_val, y_val), use_best_model=True, verbose=False)
            best_iter = model.get_best_iteration()
        else:
            model.fit(X_tr, y_tr, verbose=False)
            best_iter = model.tree_count_
        return model, best_iter

    @staticmethod
    def predict(model, X):
        return model.predict(X)


class XGBoostAdapter:
    name = "XGBoost"

    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params)
        p.setdefault("random_state", 42)
        p.setdefault("verbosity", 0)
        if with_early_stopping:
            p.setdefault("early_stopping_rounds", 50)
            p.setdefault("eval_metric", "rmse")
        return XGBRegressor(**p)

    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
            best_iter = model.best_iteration if hasattr(model, "best_iteration") and model.best_iteration is not None else model.n_estimators
        else:
            model.fit(X_tr, y_tr, verbose=False)
            best_iter = model.n_estimators
        return model, best_iter

    @staticmethod
    def predict(model, X):
        return model.predict(X)


class LightGBMAdapter:
    name = "LightGBM"

    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params)
        p.setdefault("random_state", 42)
        p.setdefault("verbose", -1)
        return LGBMRegressor(**p)

    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], eval_metric="rmse",
                       callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)])
            best_iter = model.best_iteration_
        else:
            model.fit(X_tr, y_tr)
            best_iter = model.n_estimators_
        return model, best_iter

    @staticmethod
    def predict(model, X):
        return model.predict(X)


MODEL_ADAPTERS = {
    "CatBoost": CatBoostAdapter,
    "XGBoost": XGBoostAdapter,
    "LightGBM": LightGBMAdapter,
}


def make_optuna_params(trial, model_name):
    if model_name == "CatBoost":
        return dict(
            iterations=trial.suggest_int("iterations", 300, 1500, step=100),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            depth=trial.suggest_int("depth", 2, 6),
            l2_leaf_reg=trial.suggest_float("l2_leaf_reg", 1.0, 500.0, log=True),
            min_data_in_leaf=trial.suggest_int("min_data_in_leaf", 5, 40),
            subsample=trial.suggest_float("subsample", 0.4, 1.0),
            rsm=trial.suggest_float("rsm", 0.5, 1.0),
            random_strength=trial.suggest_float("random_strength", 0.0, 3.0),
        )
    elif model_name == "XGBoost":
        return dict(
            n_estimators=trial.suggest_int("n_estimators", 300, 1500, step=100),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            max_depth=trial.suggest_int("max_depth", 2, 6),
            reg_lambda=trial.suggest_float("reg_lambda", 1.0, 500.0, log=True),
            min_child_weight=trial.suggest_int("min_child_weight", 1, 40),
            subsample=trial.suggest_float("subsample", 0.4, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
        )
    elif model_name == "LightGBM":
        return dict(
            n_estimators=trial.suggest_int("n_estimators", 300, 1500, step=100),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            max_depth=trial.suggest_int("max_depth", 2, 6),
            reg_lambda=trial.suggest_float("reg_lambda", 1.0, 500.0, log=True),
            min_child_samples=trial.suggest_int("min_child_samples", 5, 40),
            subsample=trial.suggest_float("subsample", 0.4, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
            subsample_freq=1,
        )
    else:
        raise ValueError(model_name)


# =============================================================================
# Part 1 -- Load + stratified (season-balanced) chronological split
# =============================================================================
df = pd.read_csv("Training_Values_Nofct_7day_Extended.csv")
df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.sort_values("Date_dt").reset_index(drop=True)

print("Date range:", df["Date_dt"].min(), "to", df["Date_dt"].max())
print("Rows:", len(df), "| Cols:", df.shape[1])

DATE_COL = "Date_dt"
QIN_COL = "Q_in_t (m3/day)"
RAIN_COL = "Rain_obs_t (mm)"
API_COL = "API_t (mm)"
for c in [QIN_COL, RAIN_COL, API_COL]:
    assert c in df.columns, f"Expected column not found: {c}"

targets = [c for c in df.columns if re.match(r"^y\d+=Q_in", str(c))]
targets = sorted(targets, key=lambda x: int(re.findall(r"^y(\d+)=", x)[0]))
print("Targets:", targets)

# คอลัมน์เมทาดาต้าที่ Extended.csv มีเพิ่มจาก CORRECTED.csv เดิม (audit trail ของการแก้ข้อมูล)
# ไม่ใช่ feature ทำนาย -- ตัดออกเหมือนกับ Date/targets
meta_cols = {
    "manual_copy_paste_error_corrected", "correction_note", "data_lineage_uncertain",
    "lineage_group", "training_value_replaced_no_duplicate_evidence",
    "raw_diverged_from_training_snapshot",
}
exclude = {"Date", "Date_num", "Date_dt"} | set(targets) | meta_cols
feature_cols = [c for c in df.columns if c not in exclude]
print("Features:", feature_cols)

n_nan_deltaS = df["DeltaS_t (m3/day)"].isna().sum()
if n_nan_deltaS > 0:
    print(f"Forward-filling {n_nan_deltaS} NaN value(s) in DeltaS_t (documented limitation).")
    df["DeltaS_t (m3/day)"] = df["DeltaS_t (m3/day)"].ffill()

X = df[feature_cols].copy()
Y = df[targets].copy()
mask = (~Y.isna().any(axis=1)) & (~df[DATE_COL].isna())
X, Y = X.loc[mask].reset_index(drop=True), Y.loc[mask].reset_index(drop=True)
dates = df.loc[mask, DATE_COL].reset_index(drop=True)
N = len(dates)
print("Rows used:", len(X), "| Date range:", dates.min(), "to", dates.max())

ZERO_THRESHOLD = 1e-6
dry_start, dry_end = pd.Timestamp("2026-02-03"), pd.Timestamp("2026-05-17")
in_dry = (dates >= dry_start) & (dates <= dry_end)
wet_before_idx = np.where(dates < dry_start)[0]
dry_idx = np.where(in_dry)[0]
wet_after_idx = np.where(dates > dry_end)[0]

print(f"Segments: wet_before={len(wet_before_idx)} days | dry_window={len(dry_idx)} days "
      f"({(Y[targets[0]].to_numpy()[dry_idx] <= ZERO_THRESHOLD).sum()} zero) | wet_after={len(wet_after_idx)} days")

TRAIN_FRAC, VAL_FRAC, TEST_FRAC = 0.70, 0.15, 0.15
n_dry = len(dry_idx)
n_dry_train = round(n_dry * TRAIN_FRAC)
n_dry_val = round(n_dry * VAL_FRAC)
dry_train_idx = dry_idx[:n_dry_train]
dry_val_idx = dry_idx[n_dry_train:n_dry_train + n_dry_val]
dry_test_idx = dry_idx[n_dry_train + n_dry_val:]


def chrono_split(idx_array, frac_train=TRAIN_FRAC, frac_val=VAL_FRAC):
    n = len(idx_array)
    c1 = int(round(n * frac_train))
    c2 = int(round(n * (frac_train + frac_val)))
    return idx_array[:c1], idx_array[c1:c2], idx_array[c2:]


wb_train, wb_val, wb_test = chrono_split(wet_before_idx)
wa_train, wa_val, wa_test = chrono_split(wet_after_idx)

train_idx = np.sort(np.concatenate([wb_train, dry_train_idx, wa_train]))
val_idx = np.sort(np.concatenate([wb_val, dry_val_idx, wa_val]))
test_idx = np.sort(np.concatenate([wb_test, dry_test_idx, wa_test]))

assert len(set(train_idx) & set(val_idx)) == 0
assert len(set(train_idx) & set(test_idx)) == 0
assert len(set(val_idx) & set(test_idx)) == 0
assert len(train_idx) + len(val_idx) + len(test_idx) == N

X_train, Y_train_abs = X.iloc[train_idx].reset_index(drop=True), Y.iloc[train_idx].reset_index(drop=True)
X_val, Y_val_abs = X.iloc[val_idx].reset_index(drop=True), Y.iloc[val_idx].reset_index(drop=True)
X_test, Y_test_abs = X.iloc[test_idx].reset_index(drop=True), Y.iloc[test_idx].reset_index(drop=True)
print(f"Split sizes: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
base_test = X_test[QIN_COL].to_numpy()


# =============================================================================
# Metric functions + persistence baseline
# =============================================================================
def mae_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat); return float(np.mean(np.abs(y - yhat)))

def rmse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat); return float(np.sqrt(np.mean((y - yhat) ** 2)))

def nse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(1 - np.sum((y - yhat) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-9))

def kge_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    r = np.corrcoef(y, yhat)[0, 1]
    alpha = (yhat.std() + 1e-9) / (y.std() + 1e-9)
    beta = (yhat.mean() + 1e-9) / (y.mean() + 1e-9)
    return float(1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


baseline_rows = []
for h, tcol in enumerate(targets, start=1):
    y_true = Y_test_abs[tcol].to_numpy()
    baseline_rows.append({"H": h, "Baseline_NSE": nse_np(y_true, base_test)})
print("Persistence baseline (held-out test):")
print(pd.DataFrame(baseline_rows).to_string(index=False))


# =============================================================================
# Part 2 -- Optuna search per model per horizon (train-block-only inner CV)
# =============================================================================
N_TRIALS = 40
INNER_SPLITS = 4


def make_objective(model_name, X_tr, y_tr_delta, qin_tr):
    tscv_inner = TimeSeriesSplit(n_splits=INNER_SPLITS)
    adapter = MODEL_ADAPTERS[model_name]
    def objective(trial):
        params = make_optuna_params(trial, model_name)
        fold_rmses = []
        for tr_idx, te_idx in tscv_inner.split(X_tr):
            Xtr_f, Xte_f = X_tr.iloc[tr_idx], X_tr.iloc[te_idx]
            ytr_f, yte_f = y_tr_delta[tr_idx], y_tr_delta[te_idx]
            qin_te_f = qin_tr[te_idx]
            m = adapter.build(params, with_early_stopping=False)
            m, _ = adapter.fit(m, Xtr_f, ytr_f)
            y_pred_abs_f = np.clip(qin_te_f + adapter.predict(m, Xte_f), 0, None)
            y_true_abs_f = yte_f + qin_te_f
            fold_rmses.append(rmse_np(y_true_abs_f, y_pred_abs_f))
        return float(np.mean(fold_rmses))
    return objective


t0 = time.time()
all_test_results = []
all_tuned_params = []

for model_name, adapter in MODEL_ADAPTERS.items():
    print(f"=== {model_name} === ({time.time()-t0:.0f}s elapsed)")
    for h, tcol in enumerate(targets, start=1):
        qin_train_arr = X_train[QIN_COL].to_numpy()
        y_train_delta = Y_train_abs[tcol].to_numpy() - qin_train_arr

        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(make_objective(model_name, X_train, y_train_delta, qin_train_arr), n_trials=N_TRIALS)
        best_params = study.best_params
        all_tuned_params.append({"Model": model_name, "H": h, "Target": tcol,
                                  "inner_cv_rmse": study.best_value, **best_params})

        yval_delta = Y_val_abs[tcol].to_numpy() - X_val[QIN_COL].to_numpy()
        m = adapter.build(best_params, with_early_stopping=True)
        m, best_iter = adapter.fit(m, X_train, y_train_delta, X_val, yval_delta)

        delta_pred_test = adapter.predict(m, X_test)
        q_pred_test = np.clip(base_test + delta_pred_test, 0, None)
        y_true_test = Y_test_abs[tcol].to_numpy()

        delta_pred_val = adapter.predict(m, X_val)
        q_pred_val = np.clip(X_val[QIN_COL].to_numpy() + delta_pred_val, 0, None)

        all_test_results.append({
            "Model": model_name, "H": h, "Target": tcol, "best_iter": best_iter,
            "inner_cv_rmse": study.best_value,
            "Baseline_MAE": mae_np(y_true_test, base_test), "Test_MAE": mae_np(y_true_test, q_pred_test),
            "Baseline_RMSE": rmse_np(y_true_test, base_test), "Test_RMSE": rmse_np(y_true_test, q_pred_test),
            "Baseline_NSE": nse_np(y_true_test, base_test), "Test_NSE": nse_np(y_true_test, q_pred_test),
            "Test_KGE": kge_np(y_true_test, q_pred_test),
            "Val_NSE": nse_np(Y_val_abs[tcol].to_numpy(), q_pred_val),
        })
        print(f"  H{h}: Test_NSE={nse_np(y_true_test, q_pred_test):.4f} (baseline={nse_np(y_true_test, base_test):.4f}), "
              f"Val_NSE={nse_np(Y_val_abs[tcol].to_numpy(), q_pred_val):.4f}")

results_df = pd.DataFrame(all_test_results)
tuned_params_df = pd.DataFrame(all_tuned_params)
results_df.to_csv(os.path.join(OUTDIR, "all_models_test_performance.csv"), index=False)
tuned_params_df.to_csv(os.path.join(OUTDIR, "all_models_tuned_params.csv"), index=False)
print(f"\nPart 2 done at {time.time()-t0:.0f}s")

# =============================================================================
# Part 3 -- Walk-forward CV diagnostic (train block only), per model per horizon
# =============================================================================
tscv = TimeSeriesSplit(n_splits=5)
cv_rows = []

for model_name, adapter in MODEL_ADAPTERS.items():
    for fold, (tr, te) in enumerate(tscv.split(X_train), start=1):
        Xtr_cv, Xte_cv = X_train.iloc[tr].reset_index(drop=True), X_train.iloc[te].reset_index(drop=True)
        base_te_cv = Xte_cv[QIN_COL].to_numpy()
        for h, tcol in enumerate(targets, start=1):
            ytr_abs_cv = Y_train_abs[tcol].iloc[tr].reset_index(drop=True).to_numpy()
            yte_abs_cv = Y_train_abs[tcol].iloc[te].reset_index(drop=True).to_numpy()
            ytr_delta_cv = ytr_abs_cv - Xtr_cv[QIN_COL].to_numpy()

            tuned_row = tuned_params_df[(tuned_params_df["Model"] == model_name) & (tuned_params_df["H"] == h)].iloc[0]
            param_cols = [c for c in tuned_params_df.columns if c not in ("Model", "H", "Target", "inner_cv_rmse")]
            params = {c: tuned_row[c] for c in param_cols if pd.notna(tuned_row[c])}
            for k in ["iterations", "n_estimators", "depth", "max_depth", "min_data_in_leaf",
                      "min_child_weight", "min_child_samples", "subsample_freq"]:
                if k in params:
                    params[k] = int(params[k])

            m_cv = adapter.build(params, with_early_stopping=False)
            m_cv, _ = adapter.fit(m_cv, Xtr_cv, ytr_delta_cv)
            yhat_cv = np.clip(base_te_cv + adapter.predict(m_cv, Xte_cv), 0, None)

            cv_rows.append({
                "Model": model_name, "fold": fold, "H": h,
                "Baseline_NSE": nse_np(yte_abs_cv, base_te_cv),
                "Model_NSE": nse_np(yte_abs_cv, yhat_cv),
            })

cv_df = pd.DataFrame(cv_rows)
cv_df.to_csv(os.path.join(OUTDIR, "cv_stability_diagnostic.csv"), index=False)
print(f"\nPart 3 (walk-forward CV) done at {time.time()-t0:.0f}s")
print("Walk-forward CV NSE, mean +/- std across 5 folds, per model per horizon:")
summary = cv_df.groupby(["Model", "H"])["Model_NSE"].agg(["mean", "std"])
print(summary.to_string())

print(f"\nTOTAL TIME: {time.time()-t0:.0f}s")
print("DONE")
