"""
Log-transform target experiment.

Current production architecture predicts delta = y_h - Q_in_t (can be negative -- inflow can drop
day to day), fit with CatBoost MAE loss. That's already the winning architecture this session
(delta-regression clearly beats direct-regression on y_h -- see inflow_tweedie_20260907, where
"direct_MAE" underperformed "baseline_delta_MAE" at every horizon: e.g. h1 0.743 vs 0.905).

So a log-transform here should be applied on top of the WINNING delta architecture, not by
switching to direct-on-y_h (which we already know loses). Delta can be negative, so plain log/log1p
doesn't apply -- use a SIGNED log transform instead:
    signed_log(delta) = sign(delta) * log1p(|delta|)
    inverse: delta = sign(z) * (exp(|z|) - 1)
This compresses the heavy right/left tails of delta (which can be tens of thousands of m3/day) while
preserving sign and a near-linear region close to 0 -- the idea being it may reduce the influence of
a few extreme-delta outlier days on the MAE-fit trees, similar in spirit to why log-transforms often
help skewed regression targets.

Compared via the same honest 80/20 chronological holdout used throughout this session, same
regularized/early-stopped hyperparameters (deploy-tuned), same production feature set (incl.
rain-forecast binary for h3/h6/h7).
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

def signed_log(x):
    return np.sign(x) * np.log1p(np.abs(x))

def signed_log_inv(z):
    return np.sign(z) * (np.expm1(np.abs(z)))

def nse(a, p):
    a = np.asarray(a, float); p = np.asarray(p, float)
    d = np.sum((a - a.mean()) ** 2)
    return 1 - np.sum((a - p) ** 2) / d if d else np.nan

def mae(a, p):
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(p, float))))

def fit_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

OUTER_FRAC = 0.80
results = []
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    feats = FEATS_BASE.copy()
    if h in BINARY_FEATURE_HORIZONS:
        raw_col = f"Rain_fcst_cum_h{h} (mm)"
        df[f"Rain_fcst_binary_h{h}"] = (df[raw_col] > BINARY_FEATURE_HORIZONS[h]).astype(float)
        feats = feats + [f"Rain_fcst_binary_h{h}"]

    sub = df.dropna(subset=feats + [target_col]).reset_index(drop=True)
    n = len(sub); cut = int(n * OUTER_FRAC)
    train_df, test_df = sub.iloc[:cut], sub.iloc[cut:]
    X_train, X_test = train_df[feats].values, test_df[feats].values
    current_qin_test = test_df["Q_in_t (m3/day)"].values
    actual_test = test_df[target_col].values
    delta_train = (train_df[target_col] - train_df["Q_in_t (m3/day)"]).values

    # baseline: delta + MAE (current production, no transform)
    m_base = fit_early_stopped(X_train, delta_train, DEPLOY_PARAMS[h])
    pred_base = np.maximum(current_qin_test + m_base.predict(X_test), 0.0)

    # signed-log(delta) + MAE
    z_train = signed_log(delta_train)
    m_log = fit_early_stopped(X_train, z_train, DEPLOY_PARAMS[h])
    pred_delta_log = signed_log_inv(m_log.predict(X_test))
    pred_log = np.maximum(current_qin_test + pred_delta_log, 0.0)

    results.append(dict(horizon=h, variant="baseline_delta", n_train=len(train_df), n_test=len(test_df),
                         mae=mae(actual_test, pred_base), nse=nse(actual_test, pred_base)))
    results.append(dict(horizon=h, variant="signed_log_delta", n_train=len(train_df), n_test=len(test_df),
                         mae=mae(actual_test, pred_log), nse=nse(actual_test, pred_log)))
    print(f"h{h}  baseline NSE={nse(actual_test, pred_base):.3f} MAE={mae(actual_test, pred_base):.0f}   "
          f"signed_log NSE={nse(actual_test, pred_log):.3f} MAE={mae(actual_test, pred_log):.0f}")

rep = pd.DataFrame(results)
rep.to_csv(EXP / "logtransform_cv_results.csv", index=False)
piv = rep.pivot(index="horizon", columns="variant", values="nse")[["baseline_delta", "signed_log_delta"]]
piv["diff"] = piv["signed_log_delta"] - piv["baseline_delta"]
print("\n=== NSE summary ===")
print(piv.round(3).to_string())
