"""
Screen Tweedie-loss direct regression (predict y_h directly, always >=0) against the current
production architecture (delta regression: predict y_h - Q_in_t, loss=MAE) using the same honest
80/20 chronological holdout methodology established this session.

Tweedie loss requires non-negative targets -- that's why this uses DIRECT regression on y_h
(the future inflow value itself, floored at 0 by construction) rather than the delta, which can be
negative under the current production architecture.
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
VARIANCE_POWERS = [1.1, 1.3, 1.5, 1.7, 1.9]

df = pd.read_csv(RAINEXP / "training_with_rain_forecast_features.csv", parse_dates=["Date"])

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean()) ** 2)
    return 1 - np.sum((actual - pred) ** 2) / denom if denom else np.nan

def mae(actual, pred):
    return float(np.mean(np.abs(np.asarray(actual, float) - np.asarray(pred, float))))

def fit_early_stopped(X, y, params, loss_function, seed=42):
    # baseline (delta + MAE) keeps the original deploy-tuned learning_rate/iterations/od_wait --
    # already validated this session. Direct-target variants (MAE or Tweedie) need a much larger
    # learning_rate and od_wait: direct regression on raw y (up to 1.4M, log-link for Tweedie) needs
    # far more cumulative boosting per tree than delta-regression on small residuals, and Tweedie's
    # eval-metric trajectory is non-monotonic early on (confirmed via debugging: od_wait=30 stops
    # after 1-20 trees with degenerate near-constant predictions; od_wait=150 + higher LR converges
    # properly, matching the unrestricted-iteration training curve).
    n = len(X); cut = int(n * 0.85)
    p = dict(params)
    if loss_function == "MAE":
        p.update(iterations=300, loss_function=loss_function, random_seed=seed, verbose=False,
                  od_type="Iter", od_wait=30)
    else:
        p.pop("learning_rate", None)
        p.update(iterations=500, learning_rate=0.1, loss_function=loss_function, random_seed=seed,
                  verbose=False, od_type="Iter", od_wait=150)
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

    # baseline: delta regression + MAE (current production architecture)
    y_train_delta = (train_df[target_col] - train_df["Q_in_t (m3/day)"]).values
    m_base = fit_early_stopped(X_train, y_train_delta, DEPLOY_PARAMS[h], "MAE")
    pred_base = np.maximum(current_qin_test + m_base.predict(X_test), 0.0)
    results.append(dict(horizon=h, variant="baseline_delta_MAE", n_train=len(train_df), n_test=len(test_df),
                         mae=mae(actual_test, pred_base), nse=nse(actual_test, pred_base)))

    # direct regression + MAE (isolate: is it the loss, or the direct-vs-delta target, that matters?)
    y_train_direct = train_df[target_col].values
    m_direct_mae = fit_early_stopped(X_train, y_train_direct, DEPLOY_PARAMS[h], "MAE")
    pred_direct_mae = np.maximum(m_direct_mae.predict(X_test), 0.0)
    results.append(dict(horizon=h, variant="direct_MAE", n_train=len(train_df), n_test=len(test_df),
                         mae=mae(actual_test, pred_direct_mae), nse=nse(actual_test, pred_direct_mae)))

    # direct regression + Tweedie, several variance_power
    for p in VARIANCE_POWERS:
        m_tw = fit_early_stopped(X_train, y_train_direct, DEPLOY_PARAMS[h], f"Tweedie:variance_power={p}")
        pred_tw = np.maximum(m_tw.predict(X_test), 0.0)
        results.append(dict(horizon=h, variant=f"tweedie_p{p}", n_train=len(train_df), n_test=len(test_df),
                             mae=mae(actual_test, pred_tw), nse=nse(actual_test, pred_tw)))

    print(f"h{h} done")

rep = pd.DataFrame(results)
rep.to_csv(EXP / "tweedie_cv_screen_results.csv", index=False)

print("\n=== NSE by horizon x variant ===")
piv = rep.pivot(index="horizon", columns="variant", values="nse")
cols = ["baseline_delta_MAE", "direct_MAE"] + [f"tweedie_p{p}" for p in VARIANCE_POWERS]
print(piv[cols].round(3).to_string())
print("\n=== MAE by horizon x variant ===")
piv2 = rep.pivot(index="horizon", columns="variant", values="mae")
print(piv2[cols].round(0).to_string())
