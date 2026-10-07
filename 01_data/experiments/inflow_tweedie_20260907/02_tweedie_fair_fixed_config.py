"""
Final, non-cherry-picked comparison: baseline (current production architecture: delta-regression +
MAE, regularized) vs Tweedie direct-regression with ONE fixed config (iterations=150,
variance_power=1.5, learning_rate=0.1) applied uniformly across all 7 horizons -- avoids the
per-horizon grid-search-on-test-set bias seen in the earlier screen (01_tweedie_cv_screen.py /
ad-hoc grid), which showed illusory gains at h5-h7 that don't replicate with a single fair config.
"""
import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor

EXP = Path.cwd()
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")

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
BINARY_FEATURE_HORIZONS = {3: 27.3, 6: 3.1, 7: 61.0}
df = pd.read_csv(RAINEXP / "training_with_rain_forecast_features.csv", parse_dates=["Date"])

def nse(a, p):
    a = np.asarray(a, float); p = np.asarray(p, float)
    d = np.sum((a - a.mean()) ** 2)
    return 1 - np.sum((a - p) ** 2) / d if d else np.nan

def mae(a, p):
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(p, float))))

def fit_baseline_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

results = []
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    feats = FEATS_BASE.copy()
    if h in BINARY_FEATURE_HORIZONS:
        raw_col = f"Rain_fcst_cum_h{h} (mm)"
        df[f"Rain_fcst_binary_h{h}"] = (df[raw_col] > BINARY_FEATURE_HORIZONS[h]).astype(float)
        feats = feats + [f"Rain_fcst_binary_h{h}"]

    sub = df.dropna(subset=feats + [target_col]).reset_index(drop=True)
    n = len(sub); cut = int(n * 0.80)
    train_df, test_df = sub.iloc[:cut], sub.iloc[cut:]
    X_train, X_test = train_df[feats].values, test_df[feats].values
    y_train_direct = train_df[target_col].values
    current_qin_test = test_df["Q_in_t (m3/day)"].values
    actual_test = test_df[target_col].values

    # baseline: production architecture (delta + MAE, regularized/early-stopped)
    y_train_delta = (train_df[target_col] - train_df["Q_in_t (m3/day)"]).values
    m_base = fit_baseline_early_stopped(X_train, y_train_delta, DEPLOY_PARAMS[h])
    pred_base = np.maximum(current_qin_test + m_base.predict(X_test), 0.0)

    # tweedie: ONE fixed config, no per-horizon tuning
    params_tw = dict(depth=6, l2_leaf_reg=23.8, min_data_in_leaf=8, subsample=0.83, rsm=0.79,
                      random_strength=1.07, learning_rate=0.1, iterations=150,
                      loss_function="Tweedie:variance_power=1.5", random_seed=42, verbose=False)
    m_tw = CatBoostRegressor(**params_tw)
    m_tw.fit(X_train, y_train_direct)
    pred_tw = np.maximum(m_tw.predict(X_test), 0.0)

    results.append(dict(horizon=h, nse_baseline=nse(actual_test, pred_base), nse_tweedie=nse(actual_test, pred_tw),
                         mae_baseline=mae(actual_test, pred_base), mae_tweedie=mae(actual_test, pred_tw)))

rep = pd.DataFrame(results)
rep["nse_diff"] = rep["nse_tweedie"] - rep["nse_baseline"]
rep.to_csv(EXP / "tweedie_fair_fixed_config_results.csv", index=False)
print(rep.round(3).to_string(index=False))
