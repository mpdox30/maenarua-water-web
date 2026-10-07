import json, joblib
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

range_models = {}
range_meta = {"horizons": {}}
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    feats = FEATS_BASE.copy()
    if h in BINARY_FEATURE_HORIZONS:
        raw_col = f"Rain_fcst_cum_h{h} (mm)"
        thresh = BINARY_FEATURE_HORIZONS[h]
        df[f"Rain_fcst_binary_h{h}"] = (df[raw_col] > thresh).astype(float)
        feats = feats + [f"Rain_fcst_binary_h{h}"]
    feats = feats + ["max_level_24h", "range_24h"]

    sub = df.dropna(subset=feats + [target_col]).reset_index(drop=True)
    m = fit_early_stopped(sub[feats].values, (sub[target_col] - sub["Q_in_t (m3/day)"]).values, DEPLOY_PARAMS[h])
    range_models[h] = m
    range_meta["horizons"][str(h)] = {
        "features": feats, "tree_count": int(m.tree_count_),
        "uses_rain_forecast_binary": h in BINARY_FEATURE_HORIZONS,
        "rain_forecast_threshold_mm": BINARY_FEATURE_HORIZONS.get(h),
        "n_train_rows": len(sub),
    }
    print(f"h{h}: features={feats} tree_count={m.tree_count_} n={len(sub)}")

joblib.dump(range_models, EXP / "candidate_regressors_plus_range.pkl")
range_meta["note"] = "CANDIDATE ONLY -- production feature set + max_level_24h/range_24h. Not deployed."
with open(EXP / "candidate_plus_range_metadata.json", "w", encoding="utf-8") as f:
    json.dump(range_meta, f, indent=2, ensure_ascii=False)
print("\nSaved candidate_regressors_plus_range.pkl + candidate_plus_range_metadata.json")
