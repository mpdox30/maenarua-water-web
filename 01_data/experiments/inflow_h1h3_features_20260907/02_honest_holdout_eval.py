"""
Honest chronological train/holdout evaluation of 2 candidate features on top of the CURRENT
PRODUCTION feature set (regularized hyperparams, early-stopped, + rain-forecast binary for h3/6/7):
  - daily_max_level_24h / daily_range_24h  (from hourly telemetry, 379/393 coverage)
  - is_release_active / release_rate_m3day (from release_events.csv, only 29/393 rows =1, all at
    the very end of the dataset -- known structural limitation, tested anyway per user request)

Methodology: single chronological 80/20 split (last 20% = holdout, NEVER used for fitting or for
early-stopping), matching the honest-holdout approach used for bias-recalibration/threshold-tuning
earlier this session. Within the 80% fit portion, an 85/15 sub-split is used for early stopping
(same as 01_build_final_candidate.py in inflow_regularized_final_20260907).
"""
import json
import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor

EXP = Path.cwd()

FEATS_BASE = ["Q_in_t (m3/day)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/day)",
              "%Full_t", "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/day)", "Qin_lag2 (m3/day)",
              "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)"]

DEPLOY_PARAMS = {
    1: dict(depth=6, learning_rate=0.0109312751880508, l2_leaf_reg=23.808543547006124, min_data_in_leaf=8, subsample=0.8332116765879214, rsm=0.7890628480631008, random_strength=1.07161216899677),
    2: dict(depth=5, learning_rate=0.0146991485489077, l2_leaf_reg=1.7430504177815451, min_data_in_leaf=24, subsample=0.914033992242307, rsm=0.6212741213218833, random_strength=1.9674909492695445),
    3: dict(depth=5, learning_rate=0.0159859205807381, l2_leaf_reg=4.339666832543908, min_data_in_leaf=37, subsample=0.986523802644266, rsm=0.8127877215251221, random_strength=2.57649494325228),
    4: dict(depth=3, learning_rate=0.0109387154307568, l2_leaf_reg=3.810029124004568, min_data_in_leaf=36, subsample=0.4063769521841512, rsm=0.9913749176499462, random_strength=2.699726957831789),
    5: dict(depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472, min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372, random_strength=1.0),
    6: dict(depth=2, learning_rate=0.0136765950369614, l2_leaf_reg=4.382716203014211, min_data_in_leaf=29, subsample=0.7105210344032551, rsm=0.8290243458181864, random_strength=1.9867898992450308),
    7: dict(depth=2, learning_rate=0.0119080907879342, l2_leaf_reg=1.426422588105843, min_data_in_leaf=18, subsample=0.4317495679086314, rsm=0.7638703770649338, random_strength=1.0054966332229271),
}
BINARY_FEATURE_HORIZONS = {3: 27.3, 6: 3.1, 7: 61.0}  # already-deployed rain binary (h3,h6,h7)

df = pd.read_csv(EXP / "training_with_new_features.csv", parse_dates=["Date"])

def fit_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean()) ** 2)
    return 1 - np.sum((actual - pred) ** 2) / denom if denom else np.nan

def mae(actual, pred):
    return float(np.mean(np.abs(np.asarray(actual, float) - np.asarray(pred, float))))

VARIANTS = {
    "baseline": [],
    "+range": ["max_level_24h", "range_24h"],
    "+release": ["is_release_active", "release_rate_m3day"],
    "+both": ["max_level_24h", "range_24h", "is_release_active", "release_rate_m3day"],
}

results = []
OUTER_FRAC = 0.80  # last 20% = untouched holdout

for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    base_feats = FEATS_BASE + ([f"Rain_fcst_binary_h{h}"] if h in BINARY_FEATURE_HORIZONS else [])
    if h in BINARY_FEATURE_HORIZONS:
        raw_col = f"Rain_fcst_cum_h{h} (mm)"
        thresh = BINARY_FEATURE_HORIZONS[h]
        df[f"Rain_fcst_binary_h{h}"] = (df[raw_col] > thresh).astype(float)

    for vname, extra_feats in VARIANTS.items():
        feats = base_feats + extra_feats
        sub = df.dropna(subset=feats + [target_col, "Q_in_t (m3/day)"]).reset_index(drop=True)
        n = len(sub)
        cut = int(n * OUTER_FRAC)
        train_df, test_df = sub.iloc[:cut], sub.iloc[cut:]

        X_train = train_df[feats].values
        y_train = (train_df[target_col] - train_df["Q_in_t (m3/day)"]).values
        X_test = test_df[feats].values
        current_qin_test = test_df["Q_in_t (m3/day)"].values
        actual_test = test_df[target_col].values

        m = fit_early_stopped(X_train, y_train, DEPLOY_PARAMS[h])
        pred_test = np.maximum(current_qin_test + m.predict(X_test), 0.0)

        results.append(dict(
            horizon=h, variant=vname, n_total=n, n_train=len(train_df), n_test=len(test_df),
            test_extra_feat_variance=(test_df[extra_feats].nunique().min() if extra_feats else np.nan),
            mae=mae(actual_test, pred_test), nse=nse(actual_test, pred_test),
            tree_count=int(m.tree_count_),
        ))
        print(f"h{h} {vname:10s} n_train={len(train_df):3d} n_test={len(test_df):3d} "
              f"MAE={mae(actual_test, pred_test):9.0f} NSE={nse(actual_test, pred_test):7.3f}")

rep = pd.DataFrame(results)
rep.to_csv(EXP / "honest_holdout_results.csv", index=False)

print("\n=== SUMMARY: MAE/NSE vs baseline, per horizon ===")
piv_mae = rep.pivot(index="horizon", columns="variant", values="mae")[["baseline", "+range", "+release", "+both"]]
piv_nse = rep.pivot(index="horizon", columns="variant", values="nse")[["baseline", "+range", "+release", "+both"]]
print("\nMAE:\n", piv_mae.round(0))
print("\nNSE:\n", piv_nse.round(3))
