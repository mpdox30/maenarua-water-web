# -*- coding: utf-8 -*-
"""
Walk-forward CV เปรียบเทียบ baseline (12 feature เดิม) กับ +max_level_24h/range_24h (จากข้อมูล
รายชั่วโมงเต็มปีที่ผู้ใช้ชี้ให้ดู "Raw Data_RES002 station.xlsx" + wide_log รวมกัน ครอบคลุม 386/393
แถว = 96.4% ของ training data) และ all_features (baseline + release flag + range) บน
Training_Values_full_features.csv

Methodology เดียวกับ walkforward_release_flag.py/part3_cv.py ทุกจุด (reuse tuned hyperparameter จาก
model_metadata.json ที่ deploy จริง ไม่ re-tune ใหม่) CatBoost รองรับ NaN ในฟีเจอร์โดยตรง (14 แถวที่
ไม่มีข้อมูล intraday จะเป็น NaN ปล่อยให้ CatBoost จัดการเอง ไม่ impute)

ไม่แตะไฟล์ deploy เลย
"""
import json
import os
import re
import sys
import time
import warnings

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_DIR = os.path.join(HERE, "..", "..", "scripts and code", "Reservoir_inflow", "active")
OUTDIR = os.path.join(HERE, "outputs")
os.makedirs(OUTDIR, exist_ok=True)

QIN_COL = "Q_in_t (m3/day)"

BASE_FEATURES = [
    "Q_in_t (m3/day)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/day)",
    "%Full_t", "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/day)", "Qin_lag2 (m3/day)",
    "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
]
RANGE_FEATURES = BASE_FEATURES + ["max_level_24h", "range_24h"]
ALL_FEATURES = BASE_FEATURES + ["is_release_active", "release_rate_m3day", "max_level_24h", "range_24h"]

FEATURE_SETS = {
    "baseline_12feat": BASE_FEATURES,
    "plus_range_24h": RANGE_FEATURES,
    "plus_release_and_range": ALL_FEATURES,
}


def nse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(1 - np.sum((y - yhat) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-9))


with open(os.path.join(ACTIVE_DIR, "model_metadata.json"), encoding="utf-8") as f:
    metadata = json.load(f)
tuned_params_by_h = {int(h): info["tuned_params"] for h, info in metadata["deployment_model_per_horizon"].items()}

df = pd.read_csv(os.path.join(HERE, "Training_Values_full_features.csv"))
df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.sort_values("Date_dt").reset_index(drop=True)
df["DeltaS_t (m3/day)"] = df["DeltaS_t (m3/day)"].ffill()

targets = sorted(
    [c for c in df.columns if re.match(r"^y\d+=Q_in", str(c))],
    key=lambda x: int(re.findall(r"^y(\d+)=", x)[0]),
)
Y = df[targets].copy()
mask = (~Y.isna().any(axis=1)) & (~df["Date_dt"].isna())
df = df.loc[mask].reset_index(drop=True)
Y = Y.loc[mask].reset_index(drop=True)
dates = df["Date_dt"]

dry_start, dry_end = pd.Timestamp("2026-02-03"), pd.Timestamp("2026-05-17")
wet_before_idx = np.where(dates < dry_start)[0]
dry_idx = np.where((dates >= dry_start) & (dates <= dry_end))[0]
wet_after_idx = np.where(dates > dry_end)[0]
TRAIN_FRAC, VAL_FRAC = 0.70, 0.15


def chrono_split(idx_array, frac_train=TRAIN_FRAC, frac_val=VAL_FRAC):
    n = len(idx_array)
    c1 = int(round(n * frac_train))
    c2 = int(round(n * (frac_train + frac_val)))
    return idx_array[:c1], idx_array[c1:c2], idx_array[c2:]


wb_train, _, _ = chrono_split(wet_before_idx)
n_dry_train = round(len(dry_idx) * TRAIN_FRAC)
dry_train_idx = dry_idx[:n_dry_train]
wa_train, _, _ = chrono_split(wet_after_idx)
train_idx = np.sort(np.concatenate([wb_train, dry_train_idx, wa_train]))

print(f"Train block: {len(train_idx)} rows, {dates.iloc[train_idx].min().date()} to "
      f"{dates.iloc[train_idx].max().date()}")
n_missing_range = df.iloc[train_idx]["range_24h"].isna().sum()
n_release_active = df.iloc[train_idx]["is_release_active"].sum()
print(f"  missing range_24h in train block: {n_missing_range}/{len(train_idx)}")
print(f"  is_release_active=1 in train block: {n_release_active}/{len(train_idx)}")

tscv = TimeSeriesSplit(n_splits=5)
TIME_BUDGET_S = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
CKPT_CSV = os.path.join(OUTDIR, "walkforward_range_feature_comparison.csv")

done_combos = set()
if os.path.exists(CKPT_CSV):
    prev = pd.read_csv(CKPT_CSV)
    done_combos = set(zip(prev["feature_set"], prev["H"]))
    print(f"Resuming: {len(done_combos)} (feature_set,H) combos already done")

all_combos = [(fl, h) for fl in FEATURE_SETS for h in range(1, len(targets) + 1)]

t0 = time.time()
n_done_this_run = 0
for feat_label, h in all_combos:
    if (feat_label, h) in done_combos:
        continue
    if time.time() - t0 > TIME_BUDGET_S:
        print("Time budget reached, stopping. Re-invoke to continue.")
        break

    feat_cols = FEATURE_SETS[feat_label]
    X_train_block = df.iloc[train_idx][feat_cols].reset_index(drop=True)
    Y_train_block = Y.iloc[train_idx].reset_index(drop=True)
    tcol = targets[h - 1]

    params = dict(tuned_params_by_h[h])
    params.setdefault("loss_function", "MAE")
    params.setdefault("bootstrap_type", "Bernoulli")
    params.setdefault("random_seed", 42)
    params.setdefault("verbose", False)
    for k in ("iterations", "depth", "min_data_in_leaf"):
        if k in params:
            params[k] = int(params[k])

    fold_rows = []
    for fold, (tr, te) in enumerate(tscv.split(X_train_block), start=1):
        Xtr, Xte = X_train_block.iloc[tr], X_train_block.iloc[te]
        ytr_abs = Y_train_block[tcol].iloc[tr].to_numpy()
        yte_abs = Y_train_block[tcol].iloc[te].to_numpy()
        base_te = Xte[QIN_COL].to_numpy()
        ytr_delta = ytr_abs - Xtr[QIN_COL].to_numpy()

        model = CatBoostRegressor(**params)
        model.fit(Xtr, ytr_delta, verbose=False)
        yhat = np.clip(base_te + model.predict(Xte), 0, None)

        nse = nse_np(yte_abs, yhat)
        fold_rows.append({
            "feature_set": feat_label, "H": h, "fold": fold,
            "n_train": len(tr), "n_test": len(te), "NSE": nse,
        })

    pd.DataFrame(fold_rows).to_csv(CKPT_CSV, mode="a", header=not os.path.exists(CKPT_CSV), index=False)
    n_done_this_run += 1
    mean_nse = np.mean([r["NSE"] for r in fold_rows])
    print(f"[{time.time()-t0:.0f}s] {feat_label} H{h}: walkforward NSE mean={mean_nse:.4f} "
          f"(folds: {[round(r['NSE'],3) for r in fold_rows]})")

total_done = len(done_combos) + n_done_this_run
print(f"\nThis run: {n_done_this_run} combos done in {time.time()-t0:.0f}s | Total: {total_done}/{len(all_combos)}")

if total_done >= len(all_combos):
    print("DONE_ALL")
    res = pd.read_csv(CKPT_CSV)
    print("\n=== SUMMARY: mean walkforward NSE per horizon ===")
    summary = res.groupby(["H", "feature_set"])["NSE"].mean().unstack()
    summary["diff_range"] = summary["plus_range_24h"] - summary["baseline_12feat"]
    summary["diff_all"] = summary["plus_release_and_range"] - summary["baseline_12feat"]
    print(summary.round(4).to_string())
    summary.round(4).to_csv(os.path.join(OUTDIR, "walkforward_range_feature_summary.csv"))
