# -*- coding: utf-8 -*-
"""Direct-ML (no stage1 hurdle) experiment — Colab version, full-fidelity tuning.

ต่างจาก part2_tune.py/part3_cv.py (เวอร์ชันแซนด์บ็อกซ์) ตรงที่:
  - N_TRIALS กลับไป 40 (เหมือน notebook ต้นฉบับ) ไม่ใช่ 12
  - INNER_SPLITS กลับไป 4 (เหมือนต้นฉบับ) ไม่ใช่ 3
  - iterations/n_estimators upper bound กลับไป 1500 (เหมือนต้นฉบับ) ไม่ใช่ 700
  - ไม่มี time-budget cutoff บังคับ (Colab รันยาวได้) แต่ยังคง checkpoint ต่อ (Model,H) ไว้
    เผื่อ session หลุด/timeout กลางทาง -- รันสคริปต์นี้ซ้ำได้เลย มันจะข้ามส่วนที่ทำเสร็จแล้ว

รวม Part 2 (tuning+test) และ Part 3 (walk-forward CV) ไว้ในไฟล์เดียว รันจบแล้วพิมพ์ตาราง
เทียบกับตัวเลข production ปัจจุบันให้เลย

วิธีใช้ใน Colab: ดูคอมเมนต์ท้ายไฟล์ / คำอธิบายที่ให้แยกต่างหาก
"""
import os, re, sys, time, warnings
import numpy as np
import pandas as pd
import optuna
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

OUTDIR = "outputs"
os.makedirs(OUTDIR, exist_ok=True)
PERF_CSV = os.path.join(OUTDIR, "all_models_test_performance.csv")
PARAMS_CSV = os.path.join(OUTDIR, "all_models_tuned_params.csv")
CV_CSV = os.path.join(OUTDIR, "cv_stability_diagnostic.csv")
CSV_PATH = "Training_Values_Nofct_7day_Extended.csv"  # แก้ path ตรงนี้ถ้าอัปโหลดไว้ที่อื่น

from catboost import CatBoostRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import lightgbm as lgb


class CatBoostAdapter:
    name = "CatBoost"
    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params); p.setdefault("loss_function", "MAE"); p.setdefault("bootstrap_type", "Bernoulli")
        p.setdefault("random_seed", 42); p.setdefault("verbose", False)
        if with_early_stopping: p.setdefault("od_type", "Iter"); p.setdefault("od_wait", 200)
        return CatBoostRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=(X_val, y_val), use_best_model=True, verbose=False)
            return model, model.get_best_iteration()
        model.fit(X_tr, y_tr, verbose=False); return model, model.tree_count_
    @staticmethod
    def predict(model, X): return model.predict(X)


class XGBoostAdapter:
    name = "XGBoost"
    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params); p.setdefault("random_state", 42); p.setdefault("verbosity", 0)
        if with_early_stopping: p.setdefault("early_stopping_rounds", 50); p.setdefault("eval_metric", "rmse")
        return XGBRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
            bi = model.best_iteration if hasattr(model, "best_iteration") and model.best_iteration is not None else model.n_estimators
            return model, bi
        model.fit(X_tr, y_tr, verbose=False); return model, model.n_estimators
    @staticmethod
    def predict(model, X): return model.predict(X)


class LightGBMAdapter:
    name = "LightGBM"
    @staticmethod
    def build(params, with_early_stopping=True):
        p = dict(params); p.setdefault("random_state", 42); p.setdefault("verbose", -1)
        return LGBMRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr, X_val=None, y_val=None):
        if X_val is not None:
            model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], eval_metric="rmse",
                       callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)])
            return model, model.best_iteration_
        model.fit(X_tr, y_tr); return model, model.n_estimators_
    @staticmethod
    def predict(model, X): return model.predict(X)


MODEL_ADAPTERS = {"CatBoost": CatBoostAdapter, "XGBoost": XGBoostAdapter, "LightGBM": LightGBMAdapter}


def make_optuna_params(trial, model_name):
    if model_name == "CatBoost":
        return dict(iterations=trial.suggest_int("iterations", 300, 1500, step=100),
                     learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                     depth=trial.suggest_int("depth", 2, 6),
                     l2_leaf_reg=trial.suggest_float("l2_leaf_reg", 1.0, 500.0, log=True),
                     min_data_in_leaf=trial.suggest_int("min_data_in_leaf", 5, 40),
                     subsample=trial.suggest_float("subsample", 0.4, 1.0),
                     rsm=trial.suggest_float("rsm", 0.5, 1.0),
                     random_strength=trial.suggest_float("random_strength", 0.0, 3.0))
    elif model_name == "XGBoost":
        return dict(n_estimators=trial.suggest_int("n_estimators", 300, 1500, step=100),
                     learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                     max_depth=trial.suggest_int("max_depth", 2, 6),
                     reg_lambda=trial.suggest_float("reg_lambda", 1.0, 500.0, log=True),
                     min_child_weight=trial.suggest_int("min_child_weight", 1, 40),
                     subsample=trial.suggest_float("subsample", 0.4, 1.0),
                     colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0))
    elif model_name == "LightGBM":
        return dict(n_estimators=trial.suggest_int("n_estimators", 300, 1500, step=100),
                     learning_rate=trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                     max_depth=trial.suggest_int("max_depth", 2, 6),
                     reg_lambda=trial.suggest_float("reg_lambda", 1.0, 500.0, log=True),
                     min_child_samples=trial.suggest_int("min_child_samples", 5, 40),
                     subsample=trial.suggest_float("subsample", 0.4, 1.0),
                     colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
                     subsample_freq=1)
    raise ValueError(model_name)


def mae_np(y, yhat): y, yhat = np.asarray(y), np.asarray(yhat); return float(np.mean(np.abs(y - yhat)))
def rmse_np(y, yhat): y, yhat = np.asarray(y), np.asarray(yhat); return float(np.sqrt(np.mean((y - yhat) ** 2)))
def nse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(1 - np.sum((y - yhat) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-9))
def kge_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    r = np.corrcoef(y, yhat)[0, 1]
    alpha = (yhat.std() + 1e-9) / (y.std() + 1e-9); beta = (yhat.mean() + 1e-9) / (y.mean() + 1e-9)
    return float(1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


# ---------- load + split ----------
df = pd.read_csv(CSV_PATH)
df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.sort_values("Date_dt").reset_index(drop=True)
print("Date range:", df["Date_dt"].min(), "to", df["Date_dt"].max(), "| Rows:", len(df))

QIN_COL = "Q_in_t (m3/day)"
targets = sorted([c for c in df.columns if re.match(r"^y\d+=Q_in", str(c))],
                  key=lambda x: int(re.findall(r"^y(\d+)=", x)[0]))
print("Targets:", targets)
meta_cols = {"manual_copy_paste_error_corrected", "correction_note", "data_lineage_uncertain",
             "lineage_group", "training_value_replaced_no_duplicate_evidence", "raw_diverged_from_training_snapshot"}
exclude = {"Date", "Date_num", "Date_dt"} | set(targets) | meta_cols
feature_cols = [c for c in df.columns if c not in exclude]
print("Features:", feature_cols)
n_nan = df["DeltaS_t (m3/day)"].isna().sum()
if n_nan: print(f"Forward-filling {n_nan} NaN in DeltaS_t")
df["DeltaS_t (m3/day)"] = df["DeltaS_t (m3/day)"].ffill()

X = df[feature_cols].copy(); Y = df[targets].copy()
mask = (~Y.isna().any(axis=1)) & (~df["Date_dt"].isna())
X, Y = X.loc[mask].reset_index(drop=True), Y.loc[mask].reset_index(drop=True)
dates = df.loc[mask, "Date_dt"].reset_index(drop=True)
N = len(dates)
print("Rows used:", N)

ZERO_THRESHOLD = 1e-6
dry_start, dry_end = pd.Timestamp("2026-02-03"), pd.Timestamp("2026-05-17")
wet_before_idx = np.where(dates < dry_start)[0]
dry_idx = np.where((dates >= dry_start) & (dates <= dry_end))[0]
wet_after_idx = np.where(dates > dry_end)[0]
TRAIN_FRAC, VAL_FRAC = 0.70, 0.15
n_dry = len(dry_idx); n_dry_train = round(n_dry * TRAIN_FRAC); n_dry_val = round(n_dry * VAL_FRAC)
dry_train_idx = dry_idx[:n_dry_train]; dry_val_idx = dry_idx[n_dry_train:n_dry_train + n_dry_val]
dry_test_idx = dry_idx[n_dry_train + n_dry_val:]

def chrono_split(idx_array, frac_train=TRAIN_FRAC, frac_val=VAL_FRAC):
    n = len(idx_array); c1 = int(round(n * frac_train)); c2 = int(round(n * (frac_train + frac_val)))
    return idx_array[:c1], idx_array[c1:c2], idx_array[c2:]

wb_train, wb_val, wb_test = chrono_split(wet_before_idx)
wa_train, wa_val, wa_test = chrono_split(wet_after_idx)
train_idx = np.sort(np.concatenate([wb_train, dry_train_idx, wa_train]))
val_idx = np.sort(np.concatenate([wb_val, dry_val_idx, wa_val]))
test_idx = np.sort(np.concatenate([wb_test, dry_test_idx, wa_test]))

X_train, Y_train_abs = X.iloc[train_idx].reset_index(drop=True), Y.iloc[train_idx].reset_index(drop=True)
X_val, Y_val_abs = X.iloc[val_idx].reset_index(drop=True), Y.iloc[val_idx].reset_index(drop=True)
X_test, Y_test_abs = X.iloc[test_idx].reset_index(drop=True), Y.iloc[test_idx].reset_index(drop=True)
base_test = X_test[QIN_COL].to_numpy()
print(f"Split sizes: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

N_TRIALS = 40       # เท่า notebook ต้นฉบับ (เพิ่มได้อีกถ้าอยากลอง เช่น 80-100)
INNER_SPLITS = 4    # เท่าต้นฉบับ

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


# =============================================================================
# PART 2 -- Optuna tuning + test eval (checkpointed, resumable if Colab disconnects)
# =============================================================================
done_pairs = set()
if os.path.exists(PERF_CSV):
    prev = pd.read_csv(PERF_CSV)
    done_pairs = set(zip(prev["Model"], prev["H"]))
    print(f"[Part 2] Resuming: {len(done_pairs)} combos already done")

t0 = time.time()
all_combos = [(mn, h, tcol) for mn in MODEL_ADAPTERS for h, tcol in enumerate(targets, start=1)]

for model_name, h, tcol in all_combos:
    if (model_name, h) in done_pairs:
        continue
    adapter = MODEL_ADAPTERS[model_name]
    qin_train_arr = X_train[QIN_COL].to_numpy()
    y_train_delta = Y_train_abs[tcol].to_numpy() - qin_train_arr

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(make_objective(model_name, X_train, y_train_delta, qin_train_arr), n_trials=N_TRIALS)
    best_params = study.best_params

    yval_delta = Y_val_abs[tcol].to_numpy() - X_val[QIN_COL].to_numpy()
    m = adapter.build(best_params, with_early_stopping=True)
    m, best_iter = adapter.fit(m, X_train, y_train_delta, X_val, yval_delta)

    delta_pred_test = adapter.predict(m, X_test)
    q_pred_test = np.clip(base_test + delta_pred_test, 0, None)
    y_true_test = Y_test_abs[tcol].to_numpy()
    delta_pred_val = adapter.predict(m, X_val)
    q_pred_val = np.clip(X_val[QIN_COL].to_numpy() + delta_pred_val, 0, None)

    perf_row = {
        "Model": model_name, "H": h, "Target": tcol, "best_iter": best_iter,
        "inner_cv_rmse": study.best_value,
        "Baseline_MAE": mae_np(y_true_test, base_test), "Test_MAE": mae_np(y_true_test, q_pred_test),
        "Baseline_RMSE": rmse_np(y_true_test, base_test), "Test_RMSE": rmse_np(y_true_test, q_pred_test),
        "Baseline_NSE": nse_np(y_true_test, base_test), "Test_NSE": nse_np(y_true_test, q_pred_test),
        "Test_KGE": kge_np(y_true_test, q_pred_test),
        "Val_NSE": nse_np(Y_val_abs[tcol].to_numpy(), q_pred_val),
    }
    params_row = {"Model": model_name, "H": h, "Target": tcol, "inner_cv_rmse": study.best_value, **best_params}
    pd.DataFrame([perf_row]).to_csv(PERF_CSV, mode="a", header=not os.path.exists(PERF_CSV), index=False)
    pd.DataFrame([params_row]).to_csv(PARAMS_CSV, mode="a", header=not os.path.exists(PARAMS_CSV), index=False)
    print(f"[Part2 {time.time()-t0:.0f}s] {model_name} H{h}: Test_NSE={perf_row['Test_NSE']:.4f} "
          f"(baseline={perf_row['Baseline_NSE']:.4f}), Val_NSE={perf_row['Val_NSE']:.4f}")

print(f"\n[Part 2] done, {time.time()-t0:.0f}s total")

# =============================================================================
# PART 3 -- walk-forward CV diagnostic (checkpointed, resumable)
# =============================================================================
tuned_params_df = pd.read_csv(PARAMS_CSV)
int_cols = ["iterations", "n_estimators", "depth", "max_depth", "min_data_in_leaf",
            "min_child_weight", "min_child_samples", "subsample_freq"]

done_pairs_cv = set()
if os.path.exists(CV_CSV):
    prev = pd.read_csv(CV_CSV)
    done_pairs_cv = set(zip(prev["Model"], prev["H"]))
    print(f"[Part 3] Resuming: {len(done_pairs_cv)} combos already done")

t1 = time.time()
tscv = TimeSeriesSplit(n_splits=5)
for model_name, h, tcol in all_combos:
    if (model_name, h) in done_pairs_cv:
        continue
    adapter = MODEL_ADAPTERS[model_name]
    tuned_row = tuned_params_df[(tuned_params_df["Model"] == model_name) & (tuned_params_df["H"] == h)].iloc[0]
    param_cols = [c for c in tuned_params_df.columns if c not in ("Model", "H", "Target", "inner_cv_rmse")]
    params = {c: tuned_row[c] for c in param_cols if pd.notna(tuned_row[c])}
    for k in int_cols:
        if k in params:
            params[k] = int(params[k])

    fold_rows = []
    for fold, (tr, te) in enumerate(tscv.split(X_train), start=1):
        Xtr_cv, Xte_cv = X_train.iloc[tr].reset_index(drop=True), X_train.iloc[te].reset_index(drop=True)
        base_te_cv = Xte_cv[QIN_COL].to_numpy()
        ytr_abs_cv = Y_train_abs[tcol].iloc[tr].reset_index(drop=True).to_numpy()
        yte_abs_cv = Y_train_abs[tcol].iloc[te].reset_index(drop=True).to_numpy()
        ytr_delta_cv = ytr_abs_cv - Xtr_cv[QIN_COL].to_numpy()
        m_cv = adapter.build(params, with_early_stopping=False)
        m_cv, _ = adapter.fit(m_cv, Xtr_cv, ytr_delta_cv)
        yhat_cv = np.clip(base_te_cv + adapter.predict(m_cv, Xte_cv), 0, None)
        fold_rows.append({"Model": model_name, "fold": fold, "H": h,
                           "Baseline_NSE": nse_np(yte_abs_cv, base_te_cv),
                           "Model_NSE": nse_np(yte_abs_cv, yhat_cv)})

    pd.DataFrame(fold_rows).to_csv(CV_CSV, mode="a", header=not os.path.exists(CV_CSV), index=False)
    mean_nse = np.mean([r["Model_NSE"] for r in fold_rows])
    print(f"[Part3 {time.time()-t1:.0f}s] {model_name} H{h}: walkforward_cv_NSE mean={mean_nse:.4f}")

print(f"\n[Part 3] done, {time.time()-t1:.0f}s total")

# =============================================================================
# FINAL COMPARISON vs current production (deployed model_metadata.json, per-horizon
# hurdle model, mixed CORRECTED/Extended sourcing) -- ตัวเลข baseline นี้ก็อปมาจาก
# active/model_metadata.json ตอนทำ experiment (2026-07-26) ถ้า production เปลี่ยนไปแล้ว
# ให้ไปเอาตัวเลขล่าสุดมาเทียบใหม่แทน
# =============================================================================
CURRENT_PROD_WF_CV_NSE = {1: 0.4785, 2: -0.0312, 3: -1.6972, 4: -1.8345, 5: -3.528, 6: -15.3064, 7: -13.2143}

cv_df = pd.read_csv(CV_CSV)
summary = cv_df.groupby(["Model", "H"])["Model_NSE"].mean().reset_index()
pivot = summary.pivot(index="H", columns="Model", values="Model_NSE")
print("\n=== walk-forward CV NSE (mean of 5 folds) by model x horizon ===")
print(pivot.round(4).to_string())

print("\n=== FINAL: current production (hurdle) vs best new direct-ML model per horizon ===")
print(f"{'H':>3} {'current_hurdle':>15} {'best_new_model':>16} {'best_new_nse':>14} {'winner':>10}")
for h in range(1, len(targets) + 1):
    cur = CURRENT_PROD_WF_CV_NSE[h]
    row = pivot.loc[h]
    best_model = row.idxmax()
    best_nse = row.max()
    winner = "NEW" if best_nse > cur else "current"
    print(f"{h:>3} {cur:>15.4f} {best_model:>16} {best_nse:>14.4f} {winner:>10}")

print("\nDONE_ALL")
