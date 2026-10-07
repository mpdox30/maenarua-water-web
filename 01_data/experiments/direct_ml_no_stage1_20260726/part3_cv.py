# -*- coding: utf-8 -*-
"""Part 3: walk-forward CV diagnostic (train block only), checkpointed per (Model,H).
Requires outputs/all_models_tuned_params.csv from part2_tune.py to be complete first.
Resumable: run repeatedly until DONE_ALL.
"""
import os, re, sys, time, warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

OUTDIR = "outputs"
CV_CSV = os.path.join(OUTDIR, "cv_stability_diagnostic.csv")
PARAMS_CSV = os.path.join(OUTDIR, "all_models_tuned_params.csv")
TIME_BUDGET_S = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0

from catboost import CatBoostRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import lightgbm as lgb


class CatBoostAdapter:
    @staticmethod
    def build(params):
        p = dict(params); p.setdefault("loss_function", "MAE"); p.setdefault("bootstrap_type", "Bernoulli")
        p.setdefault("random_seed", 42); p.setdefault("verbose", False)
        return CatBoostRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr): model.fit(X_tr, y_tr, verbose=False); return model
    @staticmethod
    def predict(model, X): return model.predict(X)


class XGBoostAdapter:
    @staticmethod
    def build(params):
        p = dict(params); p.setdefault("random_state", 42); p.setdefault("verbosity", 0)
        return XGBRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr): model.fit(X_tr, y_tr, verbose=False); return model
    @staticmethod
    def predict(model, X): return model.predict(X)


class LightGBMAdapter:
    @staticmethod
    def build(params):
        p = dict(params); p.setdefault("random_state", 42); p.setdefault("verbose", -1)
        return LGBMRegressor(**p)
    @staticmethod
    def fit(model, X_tr, y_tr): model.fit(X_tr, y_tr); return model
    @staticmethod
    def predict(model, X): return model.predict(X)


MODEL_ADAPTERS = {"CatBoost": CatBoostAdapter, "XGBoost": XGBoostAdapter, "LightGBM": LightGBMAdapter}


def nse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(1 - np.sum((y - yhat) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-9))


# ---------- load + split (identical to part2_tune.py) ----------
df = pd.read_csv("Training_Values_Nofct_7day_Extended.csv")
df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.sort_values("Date_dt").reset_index(drop=True)
QIN_COL = "Q_in_t (m3/day)"
targets = sorted([c for c in df.columns if re.match(r"^y\d+=Q_in", str(c))],
                  key=lambda x: int(re.findall(r"^y(\d+)=", x)[0]))
meta_cols = {"manual_copy_paste_error_corrected", "correction_note", "data_lineage_uncertain",
             "lineage_group", "training_value_replaced_no_duplicate_evidence", "raw_diverged_from_training_snapshot"}
exclude = {"Date", "Date_num", "Date_dt"} | set(targets) | meta_cols
feature_cols = [c for c in df.columns if c not in exclude]
df["DeltaS_t (m3/day)"] = df["DeltaS_t (m3/day)"].ffill()
X = df[feature_cols].copy(); Y = df[targets].copy()
mask = (~Y.isna().any(axis=1)) & (~df["Date_dt"].isna())
X, Y = X.loc[mask].reset_index(drop=True), Y.loc[mask].reset_index(drop=True)
dates = df.loc[mask, "Date_dt"].reset_index(drop=True)

dry_start, dry_end = pd.Timestamp("2026-02-03"), pd.Timestamp("2026-05-17")
wet_before_idx = np.where(dates < dry_start)[0]
dry_idx = np.where((dates >= dry_start) & (dates <= dry_end))[0]
wet_after_idx = np.where(dates > dry_end)[0]
TRAIN_FRAC, VAL_FRAC = 0.70, 0.15
n_dry = len(dry_idx); n_dry_train = round(n_dry * TRAIN_FRAC); n_dry_val = round(n_dry * VAL_FRAC)
dry_train_idx = dry_idx[:n_dry_train]; dry_val_idx = dry_idx[n_dry_train:n_dry_train + n_dry_val]

def chrono_split(idx_array, frac_train=TRAIN_FRAC, frac_val=VAL_FRAC):
    n = len(idx_array); c1 = int(round(n * frac_train)); c2 = int(round(n * (frac_train + frac_val)))
    return idx_array[:c1], idx_array[c1:c2], idx_array[c2:]

wb_train, wb_val, _ = chrono_split(wet_before_idx)
wa_train, wa_val, _ = chrono_split(wet_after_idx)
train_idx = np.sort(np.concatenate([wb_train, dry_train_idx, wa_train]))
X_train = X.iloc[train_idx].reset_index(drop=True)
Y_train_abs = Y.iloc[train_idx].reset_index(drop=True)

tuned_params_df = pd.read_csv(PARAMS_CSV)
int_cols = ["iterations", "n_estimators", "depth", "max_depth", "min_data_in_leaf",
            "min_child_weight", "min_child_samples", "subsample_freq"]

done_pairs = set()
if os.path.exists(CV_CSV):
    prev = pd.read_csv(CV_CSV)
    done_pairs = set(zip(prev["Model"], prev["H"]))
    print(f"Resuming: {len(done_pairs)} (Model,H) combos already done")

t0 = time.time()
n_done = 0
all_combos = [(mn, h) for mn in MODEL_ADAPTERS for h in range(1, len(targets) + 1)]
tscv = TimeSeriesSplit(n_splits=5)

for model_name, h in all_combos:
    if (model_name, h) in done_pairs:
        continue
    if time.time() - t0 > TIME_BUDGET_S:
        print(f"Time budget reached, stopping. Re-invoke to continue.")
        break

    tcol = targets[h - 1]
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

        m_cv = adapter.build(params)
        m_cv = adapter.fit(m_cv, Xtr_cv, ytr_delta_cv)
        yhat_cv = np.clip(base_te_cv + adapter.predict(m_cv, Xte_cv), 0, None)

        fold_rows.append({"Model": model_name, "fold": fold, "H": h,
                           "Baseline_NSE": nse_np(yte_abs_cv, base_te_cv),
                           "Model_NSE": nse_np(yte_abs_cv, yhat_cv)})

    pd.DataFrame(fold_rows).to_csv(CV_CSV, mode="a", header=not os.path.exists(CV_CSV), index=False)
    n_done += 1
    mean_nse = np.mean([r["Model_NSE"] for r in fold_rows])
    print(f"[{time.time()-t0:.0f}s] {model_name} H{h}: walkforward_cv_NSE mean={mean_nse:.4f} "
          f"(baseline mean={np.mean([r['Baseline_NSE'] for r in fold_rows]):.4f})")

total_done = len(done_pairs) + n_done
print(f"\nThis run: {n_done} combos done in {time.time()-t0:.0f}s | Total so far: {total_done}/{len(all_combos)}")
if total_done >= len(all_combos):
    print("DONE_ALL")
