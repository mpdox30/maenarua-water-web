import json, joblib, importlib.util
import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor

EXP = Path.cwd()
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")
H5EXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_h5_bias_fix_20260907")
ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

spec = importlib.util.spec_from_file_location("reconstruct", str(H5EXP / "09_reconstruct_live_features.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FEATS_BASE = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
              '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
              'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']
FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

DEPLOY_PARAMS = {
    1: dict(depth=6, learning_rate=0.0109312751880508, l2_leaf_reg=23.808543547006124, min_data_in_leaf=8, subsample=0.8332116765879214, rsm=0.7890628480631008, random_strength=1.07161216899677),
    2: dict(depth=5, learning_rate=0.0146991485489077, l2_leaf_reg=1.7430504177815451, min_data_in_leaf=24, subsample=0.914033992242307, rsm=0.6212741213218833, random_strength=1.9674909492695445),
    3: dict(depth=5, learning_rate=0.0159859205807381, l2_leaf_reg=4.339666832543908, min_data_in_leaf=37, subsample=0.986523802644266, rsm=0.8127877215251221, random_strength=2.57649494325228),
    4: dict(depth=3, learning_rate=0.0109387154307568, l2_leaf_reg=3.810029124004568, min_data_in_leaf=36, subsample=0.4063769521841512, rsm=0.9913749176499462, random_strength=2.699726957831789),
    5: dict(depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472, min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372, random_strength=1.0),
    6: dict(depth=2, learning_rate=0.0136765950369614, l2_leaf_reg=4.382716203014211, min_data_in_leaf=29, subsample=0.7105210344032551, rsm=0.8290243458181864, random_strength=1.9867898992450308),
    7: dict(depth=2, learning_rate=0.0119080907879342, l2_leaf_reg=1.426422588105843, min_data_in_leaf=18, subsample=0.4317495679086314, rsm=0.7638703770649338, random_strength=1.0054966332229271),
}

# horizons that get the extra binary rain-forecast feature, with the honest-holdout-tuned threshold
# (thresholds are on Rain_fcst_cum_h{N} = sum of Open-Meteo forecast precip for lead_day 1..N, mm)
BINARY_FEATURE_HORIZONS = {
    3: 27.3,   # p80 of train distribution for cum lead1-3
    6: 3.1,    # p30 of train distribution for cum lead1-6
    7: 61.0,   # p80 of train distribution for cum lead1-7
}

df = pd.read_csv(RAINEXP / "training_with_rain_forecast_features.csv", parse_dates=["Date"])
arc_piv = pd.read_csv(RAINEXP / "rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"]).pivot_table(
    index="issue_date", columns="lead_day", values="precipitation_sum_mm")

def fit_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

final_models = {}
final_meta = {"horizons": {}}
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    if h in BINARY_FEATURE_HORIZONS:
        raw_col = f"Rain_fcst_cum_h{h} (mm)"
        thresh = BINARY_FEATURE_HORIZONS[h]
        bin_col = f"Rain_fcst_binary_h{h}"
        df[bin_col] = (df[raw_col] > thresh).astype(float)
        feats = FEATS_BASE + [bin_col]
        sub = df.dropna(subset=feats + [target_col]).reset_index(drop=True)
    else:
        feats = FEATS_BASE
        sub = df.dropna(subset=feats + [target_col]).reset_index(drop=True)

    m = fit_early_stopped(sub[feats].values, (sub[target_col]-sub["Q_in_t (m3/day)"]).values, DEPLOY_PARAMS[h])
    final_models[h] = m
    final_meta["horizons"][str(h)] = {
        "features": feats,
        "tree_count": int(m.tree_count_),
        "uses_rain_forecast_binary": h in BINARY_FEATURE_HORIZONS,
        "rain_forecast_threshold_mm": BINARY_FEATURE_HORIZONS.get(h),
        "n_train_rows": len(sub),
    }
    print(f"h{h}: features={len(feats)} tree_count={m.tree_count_} n={len(sub)}")

joblib.dump(final_models, EXP / "candidate_regressors_regularized_final.pkl")
final_meta["note"] = ("CANDIDATE ONLY -- not deployed to production. h1,h2,h4,h5 use the original 12 "
                       "base features with early-stopped (regularized) training. h3,h6,h7 additionally "
                       "get a binary rain-forecast feature (Open-Meteo Historical Forecast API archive, "
                       "cumulative forecast precip lead1..h > threshold_mm). See "
                       "01_data/experiments/inflow_h5_bias_fix_20260907 and "
                       "inflow_rain_forecast_feature_20260907 for full methodology/validation.")
with open(EXP / "candidate_metadata.json", "w", encoding="utf-8") as f:
    json.dump(final_meta, f, indent=2, ensure_ascii=False)
print("\nSaved candidate_regressors_regularized_final.pkl + candidate_metadata.json")
