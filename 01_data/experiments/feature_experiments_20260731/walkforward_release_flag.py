# -*- coding: utf-8 -*-
"""
Walk-forward CV เปรียบเทียบ baseline (12 feature เดิมที่ deploy จริง) กับ baseline + is_release_active
+ release_rate_m3day บน Training_Values_with_release_flag.csv

Methodology เดียวกับ 01_data/experiments/direct_ml_no_stage1_20260726/part3_cv.py ทุกจุด (สถาปัตยกรรม
เดียวกับที่ deploy จริงตอนนี้ -- direct delta-regression, ไม่มี stage1 hurdle):
  1. sort ตามวันที่, แบ่ง train/val/test แบบ chronological 70/15/15 ภายใน 3 ช่วงฤดูกาล
     (wet_before / dry 2026-02-03..2026-05-17 / wet_after) เอาเฉพาะ "train block" (70%×3 ช่วง)
     มาทำ walk-forward
  2. TimeSeriesSplit(n_splits=5) บน train block
  3. โมเดล = CatBoostRegressor ทำนาย DELTA (Q_in_t+h - Q_in_t) ด้วย hyperparameter ที่ tune ไว้แล้ว
     จาก model_metadata.json ที่ deploy จริง (ไม่ re-tune ใหม่ -- แยกผลกระทบของ feature ใหม่ออกจาก
     ผลกระทบของการค้นหา hyperparameter ใหม่)
  4. prediction = clip(Q_in_t + delta_pred, 0, None)

ไม่แตะไฟล์ใน 01_data/scripts and code/Reservoir_inflow/active/ เลย -- อ่านแค่ tuned_params จาก
model_metadata.json (read-only) มาใช้ในสคริปต์นี้
"""
import json
import os
import re
import warnings

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_DIR = os.path.join(
    HERE, "..", "..", "scripts and code", "Reservoir_inflow", "active"
)
OUTDIR = os.path.join(HERE, "outputs")
os.makedirs(OUTDIR, exist_ok=True)

QIN_COL = "Q_in_t (m3/day)"

BASE_FEATURES = [
    "Q_in_t (m3/day)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/day)",
    "%Full_t", "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/day)", "Qin_lag2 (m3/day)",
    "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
]
RELEASE_FEATURES = BASE_FEATURES + ["is_release_active", "release_rate_m3day"]


def nse_np(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    return float(1 - np.sum((y - yhat) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-9))


# ---------- load tuned params from deployed model_metadata.json (read-only) ----------
with open(os.path.join(ACTIVE_DIR, "model_metadata.json"), encoding="utf-8") as f:
    metadata = json.load(f)

tuned_params_by_h = {
    int(h): info["tuned_params"] for h, info in metadata["deployment_model_per_horizon"].items()
}

# ---------- load data + season-stratified split (identical to part3_cv.py) ----------
df = pd.read_csv(os.path.join(HERE, "Training_Values_with_release_flag.csv"))
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
n_dry = len(dry_idx)
n_dry_train = round(n_dry * TRAIN_FRAC)
dry_train_idx = dry_idx[:n_dry_train]
wa_train, _, _ = chrono_split(wet_after_idx)
train_idx = np.sort(np.concatenate([wb_train, dry_train_idx, wa_train]))

print(f"Train block: {len(train_idx)} rows, {dates.iloc[train_idx].min().date()} to "
      f"{dates.iloc[train_idx].max().date()}")
n_release_active_in_train = df.iloc[train_idx]["is_release_active"].sum()
print(f"  of which is_release_active=1: {n_release_active_in_train} rows")

tscv = TimeSeriesSplit(n_splits=5)

# ---------- checkpointed/resumable (45s per-call sandbox limit) ----------
import sys
import time

TIME_BUDGET_S = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0
CKPT_CSV = os.path.join(OUTDIR, "walkforward_release_flag_comparison.csv")

done_combos = set()
if os.path.exists(CKPT_CSV):
    prev = pd.read_csv(CKPT_CSV)
    done_combos = set(zip(prev["feature_set"], prev["H"]))
    print(f"Resuming: {len(done_combos)} (feature_set,H) combos already done")

all_combos = [(fl, h) for fl in ("baseline_12feat", "plus_release_flag") for h in range(1, len(targets) + 1)]

t0 = time.time()
n_done_this_run = 0
for feat_label, h in all_combos:
    if (feat_label, h) in done_combos:
        continue
    if time.time() - t0 > TIME_BUDGET_S:
        print("Time budget reached, stopping. Re-invoke to continue.")
        break

    feat_cols = BASE_FEATURES if feat_label == "baseline_12feat" else RELEASE_FEATURES
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
    summary["diff"] = summary["plus_release_flag"] - summary["baseline_12feat"]
    print(summary.round(4).to_string())
    summary.round(4).to_csv(os.path.join(OUTDIR, "walkforward_release_flag_summary.csv"))
