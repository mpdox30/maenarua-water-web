"""
Train + tune every model family tried so far on the 6-hourly dataset (12 horizons, 6h to
72h ahead), using the same discipline as the daily investigation: tune only on an early
chronological block via inner TimeSeriesSplit CV, then evaluate ONCE on a never-touched
final chronological holdout (last ~15% of usable rows, which lands in Jul-Sep 2026 and
includes the real flood event).

No live forecast_accuracy_log exists at 6-hourly resolution (it was never deployed), so
this self-contained holdout is the best available honest test -- same self-contained
approach the original 2026-07-31 6-hourly experiment used when it first lost to daily.

Run with an argv flag to control which model families this invocation covers (keeps each
run under the tool timeout): `python3 sixhourly_train_all.py catboost` or `... other`
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import optuna
from catboost import CatBoostRegressor, CatBoostClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

DATA_PATH = Path(
    "/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/"
    "sixhourly_refresh_20260918/Training_6hourly_full_extended_20260918.csv"
)
OUT_DIR = DATA_PATH.parent

QIN_COL = "Q_in_t (m3/6h)"
FEATS = [
    "Q_in_t (m3/6h)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/6h)", "%Full_t",
    "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/6h)", "Qin_lag2 (m3/6h)",
    "Rain_lag1 (mm)", "Rain_lag2 (mm)", "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
]
N_HORIZONS = 12
N_TRIALS = 12
ZERO_THRESHOLD = 1e-6


def nse_np(y, yhat):
    y, yhat = np.asarray(y, dtype=float), np.asarray(yhat, dtype=float)
    denom = np.sum((y - y.mean()) ** 2)
    if denom < 1e-9:
        return float("nan")
    return float(1 - np.sum((y - yhat) ** 2) / denom)


def mae_np(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, dtype=float) - np.asarray(yhat, dtype=float))))


# ---------------- model adapters (same shapes as the daily "try_other_ml.py") ----------------

def cat_space(trial):
    return dict(
        learning_rate=trial.suggest_float("learning_rate", 0.005, 0.08, log=True),
        depth=trial.suggest_int("depth", 2, 7),
        l2_leaf_reg=trial.suggest_float("l2_leaf_reg", 1.0, 40.0, log=True),
        min_data_in_leaf=trial.suggest_int("min_data_in_leaf", 5, 40),
        subsample=trial.suggest_float("subsample", 0.4, 1.0),
        rsm=trial.suggest_float("rsm", 0.5, 1.0),
        random_strength=trial.suggest_float("random_strength", 1.0, 6.0),
    )


def fit_cat(params, Xtr, ytr, Xev=None, yev=None):
    p = dict(params)
    p.update(iterations=400, loss_function="MAE", bootstrap_type="Bernoulli", random_seed=42,
              verbose=False, od_type="Iter", od_wait=20)
    m = CatBoostRegressor(**p)
    if Xev is not None and len(Xev) > 5:
        m.fit(Xtr, ytr, eval_set=(Xev, yev), use_best_model=True, verbose=False)
    else:
        m.fit(Xtr, ytr, verbose=False)
    return m


def lgbm_space(trial):
    return dict(
        n_estimators=400,
        learning_rate=trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
        num_leaves=trial.suggest_int("num_leaves", 4, 48),
        min_child_samples=trial.suggest_int("min_child_samples", 3, 30),
        reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10, log=True),
        reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
    )


def fit_lgbm(params, Xtr, ytr, Xev=None, yev=None):
    import lightgbm
    m = LGBMRegressor(**params, random_state=42, verbose=-1)
    if Xev is not None and len(Xev) > 5:
        m.fit(Xtr, ytr, eval_set=[(Xev, yev)], callbacks=[lightgbm.early_stopping(20, verbose=False)])
    else:
        m.fit(Xtr, ytr)
    return m


def xgb_space(trial):
    return dict(
        n_estimators=400,
        learning_rate=trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
        max_depth=trial.suggest_int("max_depth", 2, 7),
        min_child_weight=trial.suggest_float("min_child_weight", 1, 20, log=True),
        reg_alpha=trial.suggest_float("reg_alpha", 1e-3, 10, log=True),
        reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
    )


def fit_xgb(params, Xtr, ytr, Xev=None, yev=None):
    p = dict(params)
    m = XGBRegressor(**p, random_state=42, verbosity=0,
                      early_stopping_rounds=20 if Xev is not None and len(Xev) > 5 else None)
    if Xev is not None and len(Xev) > 5:
        m.fit(Xtr, ytr, eval_set=[(Xev, yev)], verbose=False)
    else:
        m.fit(Xtr, ytr)
    return m


def rf_space(trial):
    return dict(
        n_estimators=trial.suggest_int("n_estimators", 80, 250),
        max_depth=trial.suggest_int("max_depth", 2, 12),
        min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 15),
        max_features=trial.suggest_float("max_features", 0.3, 1.0),
    )


def fit_rf(params, Xtr, ytr, Xev=None, yev=None):
    m = RandomForestRegressor(**params, random_state=42, n_jobs=-1)
    m.fit(Xtr, ytr)
    return m


def ridge_space(trial):
    return dict(alpha=trial.suggest_float("alpha", 1e-2, 500, log=True))


def fit_ridge(params, Xtr, ytr, Xev=None, yev=None):
    scaler = StandardScaler().fit(Xtr)
    m = Ridge(**params)
    m.fit(scaler.transform(Xtr), ytr)
    return ("ridge_with_scaler", m, scaler)


def predict_generic(model, X):
    if isinstance(model, tuple) and model[0] == "ridge_with_scaler":
        _, m, scaler = model
        return m.predict(scaler.transform(X))
    return model.predict(X)


CATBOOST_FAMILY = {"CatBoost": (cat_space, fit_cat)}
OTHER_FAMILIES = {
    "LightGBM": (lgbm_space, fit_lgbm),
    "XGBoost": (xgb_space, fit_xgb),
    "RandomForest": (rf_space, fit_rf),
    "Ridge": (ridge_space, fit_ridge),
}


def inner_cv_objective(trial, space_fn, fit_fn, X_fit, y_fit_abs, qin_fit):
    params = space_fn(trial)
    tscv = TimeSeriesSplit(n_splits=5)
    fold_nse = []
    for tr, te in tscv.split(X_fit):
        Xtr, Xte = X_fit.iloc[tr].reset_index(drop=True), X_fit.iloc[te].reset_index(drop=True)
        ytr_abs, yte_abs = y_fit_abs[tr], y_fit_abs[te]
        qin_tr, qin_te = qin_fit[tr], qin_fit[te]
        ytr_delta = ytr_abs - qin_tr
        n = len(Xtr)
        if n < 20:
            m = fit_fn(params, Xtr, ytr_delta)
        else:
            cut = int(n * 0.85)
            m = fit_fn(params, Xtr.iloc[:cut], ytr_delta[:cut], Xtr.iloc[cut:], ytr_delta[cut:])
        yhat = np.clip(qin_te + predict_generic(m, Xte), 0, None)
        fold_nse.append(nse_np(yte_abs, yhat))
    return float(np.mean(fold_nse))


def fit_hurdle(Xtr, ytr_abs, cat_params):
    is_zero = (ytr_abs <= ZERO_THRESHOLD).astype(int)
    if not (3 <= is_zero.sum() <= len(is_zero) - 3):
        return None
    clf = CatBoostClassifier(iterations=200, learning_rate=0.05, depth=4, random_seed=42,
                              verbose=False, auto_class_weights="Balanced")
    clf.fit(Xtr, is_zero, verbose=False)
    nz = ~is_zero.astype(bool)
    reg = fit_cat(cat_params, Xtr.loc[nz].reset_index(drop=True), (ytr_abs[nz] - Xtr.loc[nz, QIN_COL].to_numpy()))
    return (clf, reg)


def predict_hurdle(hurdle, Xte, base_te):
    if hurdle is None:
        return None
    clf, reg = hurdle
    pred_zero = clf.predict(Xte).astype(bool).reshape(-1)
    reg_pred = np.clip(base_te + reg.predict(Xte), 0, None)
    return np.where(pred_zero, 0.0, reg_pred)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "catboost"
    if which == "catboost":
        families = CATBOOST_FAMILY
    elif which in OTHER_FAMILIES:
        families = {which: OTHER_FAMILIES[which]}
    else:
        families = OTHER_FAMILIES

    df = pd.read_csv(DATA_PATH, parse_dates=["Datetime"])
    df = df.sort_values("Datetime").reset_index(drop=True)

    y_cols = [f"y{h}=Q_in_t+{h} (m3/6h)" for h in range(1, N_HORIZONS + 1)]
    mask = df[FEATS + y_cols].notna().all(axis=1)
    usable = df[mask].reset_index(drop=True)
    print(f"Usable rows (all feats + all 12 targets present): {len(usable)}  "
          f"{usable['Datetime'].min()} .. {usable['Datetime'].max()}")

    n = len(usable)
    holdout_start_idx = int(n * 0.85)
    holdout_start_date = usable["Datetime"].iloc[holdout_start_idx]
    print(f"Holdout starts at row {holdout_start_idx} ({holdout_start_date}), "
          f"{n - holdout_start_idx} holdout rows")

    fit_df = usable.iloc[:holdout_start_idx].reset_index(drop=True)
    holdout_df = usable.iloc[holdout_start_idx:].reset_index(drop=True)

    h_start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    h_end = int(sys.argv[3]) if len(sys.argv) > 3 else N_HORIZONS

    results = []
    for h in range(h_start, h_end + 1):
        ycol = f"y{h}=Q_in_t+{h} (m3/6h)"
        X_fit = fit_df[FEATS]
        y_fit_abs = fit_df[ycol].to_numpy()
        qin_fit = fit_df[QIN_COL].to_numpy()

        Xh = holdout_df[FEATS]
        base_h = holdout_df[QIN_COL].to_numpy()
        actual_h = holdout_df[ycol].to_numpy()
        persistence_h = base_h.copy()

        row_result = {"H": h, "n_fit": len(fit_df), "n_holdout": len(holdout_df),
                      "persistence_holdout_nse": nse_np(actual_h, persistence_h)}

        if which == "catboost":
            # -- direct delta-regression, tuned --
            study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
            study.optimize(lambda t: inner_cv_objective(t, cat_space, fit_cat, X_fit, y_fit_abs, qin_fit),
                            n_trials=N_TRIALS)
            best_params = study.best_params
            y_delta_final = y_fit_abs - qin_fit
            cut_i = int(len(X_fit) * 0.85)
            final_direct = fit_cat(best_params, X_fit.iloc[:cut_i], y_delta_final[:cut_i],
                                    X_fit.iloc[cut_i:], y_delta_final[cut_i:])
            pred_direct = np.clip(base_h + final_direct.predict(Xh), 0, None)
            row_result["CatBoost_direct_inner_cv_nse"] = study.best_value
            row_result["CatBoost_direct_holdout_nse"] = nse_np(actual_h, pred_direct)

            # -- 2-stage hurdle, same tuned params reused for stage2 regressor --
            hurdle = fit_hurdle(X_fit, y_fit_abs, best_params)
            pred_hurdle = predict_hurdle(hurdle, Xh, base_h)
            row_result["CatBoost_hurdle_holdout_nse"] = nse_np(actual_h, pred_hurdle) if pred_hurdle is not None else None

            print(f"H{h} (6h-step, ~{h*6}h ahead): persistence={row_result['persistence_holdout_nse']:+.3f} | "
                  f"CatBoost_direct inner_cv={row_result['CatBoost_direct_inner_cv_nse']:+.3f} "
                  f"holdout={row_result['CatBoost_direct_holdout_nse']:+.3f} | "
                  f"CatBoost_hurdle holdout={row_result['CatBoost_hurdle_holdout_nse']}")
        else:
            for name, (space_fn, fit_fn) in families.items():
                study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
                study.optimize(lambda t: inner_cv_objective(t, space_fn, fit_fn, X_fit, y_fit_abs, qin_fit),
                                n_trials=N_TRIALS)
                best_params = study.best_params
                y_delta_final = y_fit_abs - qin_fit
                cut_i = int(len(X_fit) * 0.85)
                final_model = fit_fn(best_params, X_fit.iloc[:cut_i], y_delta_final[:cut_i],
                                      X_fit.iloc[cut_i:], y_delta_final[cut_i:])
                pred = np.clip(base_h + predict_generic(final_model, Xh), 0, None)
                row_result[f"{name}_inner_cv_nse"] = study.best_value
                row_result[f"{name}_holdout_nse"] = nse_np(actual_h, pred)
            print(f"H{h} (6h-step, ~{h*6}h ahead): persistence={row_result['persistence_holdout_nse']:+.3f} | " +
                  " | ".join(f"{name}={row_result[name+'_holdout_nse']:+.3f}" for name in families))

        results.append(row_result)

    out = pd.DataFrame(results)
    suffix = f"{which}_h{h_start}-{h_end}"
    out.to_csv(OUT_DIR / f"sixhourly_results_{suffix}.csv", index=False)
    print(f"\nSaved: {OUT_DIR / f'sixhourly_results_{suffix}.csv'}")


if __name__ == "__main__":
    main()
