# -*- coding: utf-8 -*-
"""
Train and FREEZE the shadow-test models for the 6-hourly reservoir-inflow investigation
(2026-09-18). Trains once on ALL usable data through today, using the best-per-horizon
model family found in sixhourly_train_all.py's honest holdout comparison. These frozen
models are what shadow_predict.py loads every 6h during the shadow-test period -- they
are NOT retrained automatically; that is the point of a shadow test (fixed candidate,
scored against reality going forward).

Run with an optional horizon range: `python3 train_final_shadow_models.py 1 6` (else all 12).
"""
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import optuna
from catboost import CatBoostRegressor, CatBoostClassifier
from sklearn.model_selection import TimeSeriesSplit
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

DATA_PATH = Path(
    "/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/"
    "sixhourly_refresh_20260918/Training_6hourly_full_extended_20260918.csv"
)
OUT_DIR = DATA_PATH.parent / "shadow_models"
OUT_DIR.mkdir(exist_ok=True)

QIN_COL = "Q_in_t (m3/6h)"
FEATS = [
    "Q_in_t (m3/6h)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/6h)", "%Full_t",
    "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/6h)", "Qin_lag2 (m3/6h)",
    "Rain_lag1 (mm)", "Rain_lag2 (mm)", "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
]
N_TRIALS = 12
ZERO_THRESHOLD = 1e-6

# [2026-09-25 แก้] อัปเดตตาม honest holdout comparison บนข้อมูลที่แก้ label ด้วยสูตร spillway
# ใหม่แล้ว (critical-flow+friction, ดู Spillway_check/03_experiment/weir_friction_model.py) --
# DATA_PATH ด้านบนตอนนี้ชี้ไปที่ Training_6hourly_full_extended_20260918.csv ที่แก้แล้วเช่นกัน
# (ของเดิมก่อนแก้ สำรองไว้ที่ Training_6hourly_full_extended_20260918_PRE_SPILLWAY_FIX_20260925.csv)
# BEST_FAMILY ชุดนี้ต้องตรงกับใน shadow_predict.py เป๊ะ (โมเดล frozen ปัจจุบันใน shadow_models/
# เทรนด้วยชุดนี้แล้ว -- ถ้าจะ re-freeze ใหม่ในอนาคตด้วยสคริปต์นี้ ค่า BEST_FAMILY นี้ยังใช้ได้ต่อ
# จนกว่าจะรัน honest holdout comparison ใหม่อีกรอบ)
BEST_FAMILY = {
    1: "CatBoost_hurdle", 2: "CatBoost_hurdle", 3: "LightGBM", 4: "LightGBM", 5: "LightGBM",
    6: "CatBoost_hurdle", 7: "XGBoost", 8: "XGBoost", 9: "XGBoost", 10: "CatBoost_hurdle",
    11: "CatBoost_hurdle", 12: "XGBoost",
}


def nse_np(y, yhat):
    y, yhat = np.asarray(y, dtype=float), np.asarray(yhat, dtype=float)
    denom = np.sum((y - y.mean()) ** 2)
    if denom < 1e-9:
        return float("nan")
    return float(1 - np.sum((y - yhat) ** 2) / denom)


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


SPACE_FIT = {
    "CatBoost_hurdle": (cat_space, fit_cat),
    "LightGBM": (lgbm_space, fit_lgbm),
    "XGBoost": (xgb_space, fit_xgb),
}


def predict_generic(model, X):
    return model.predict(X)


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
    clf = CatBoostClassifier(iterations=200, learning_rate=0.05, depth=4, random_seed=42,
                              verbose=False, auto_class_weights="Balanced")
    clf.fit(Xtr, is_zero, verbose=False)
    nz = ~is_zero.astype(bool)
    reg = fit_cat(cat_params, Xtr.loc[nz].reset_index(drop=True), (ytr_abs[nz] - Xtr.loc[nz, QIN_COL].to_numpy()))
    return clf, reg


def main():
    h_start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    h_end = int(sys.argv[2]) if len(sys.argv) > 2 else 12

    df = pd.read_csv(DATA_PATH, parse_dates=["Datetime"])
    df = df.sort_values("Datetime").reset_index(drop=True)

    meta_path = OUT_DIR / "shadow_model_metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_source": str(DATA_PATH.name),
        "feats": FEATS,
        "qin_col": QIN_COL,
        "horizons": {},
    }

    for h in range(h_start, h_end + 1):
        family = BEST_FAMILY[h]
        ycol = f"y{h}=Q_in_t+{h} (m3/6h)"
        mask = df[FEATS + [ycol]].notna().all(axis=1)
        usable = df[mask].reset_index(drop=True)

        X = usable[FEATS]
        y_abs = usable[ycol].to_numpy()
        qin = usable[QIN_COL].to_numpy()

        base_family = "CatBoost_hurdle" if family == "CatBoost_hurdle" else family
        space_fn, fit_fn = SPACE_FIT[base_family] if base_family != "CatBoost_hurdle" else SPACE_FIT["CatBoost_hurdle"]

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(lambda t: inner_cv_objective(t, space_fn, fit_fn, X, y_abs, qin), n_trials=N_TRIALS)
        best_params = study.best_params

        y_delta = y_abs - qin
        cut = int(len(X) * 0.9)

        if family == "CatBoost_hurdle":
            clf, reg = fit_hurdle(X, y_abs, best_params)
            joblib.dump(clf, OUT_DIR / f"h{h}_clf.joblib")
            joblib.dump(reg, OUT_DIR / f"h{h}_reg.joblib")
            model_files = [f"h{h}_clf.joblib", f"h{h}_reg.joblib"]
        else:
            final_model = fit_fn(best_params, X.iloc[:cut], y_delta[:cut], X.iloc[cut:], y_delta[cut:])
            joblib.dump(final_model, OUT_DIR / f"h{h}_model.joblib")
            model_files = [f"h{h}_model.joblib"]

        meta["horizons"][str(h)] = {
            "family": family,
            "best_params": best_params,
            "inner_cv_nse": study.best_value,
            "n_train_rows": int(len(usable)),
            "train_data_through": str(usable["Datetime"].max()),
            "model_files": model_files,
        }
        meta_path.write_text(json.dumps(meta, indent=2, default=str))
        print(f"H{h} ({family}): inner_cv_nse={study.best_value:+.3f}, n_train={len(usable)}, "
              f"data_through={usable['Datetime'].max()} -- saved {model_files}")

    print(f"\nDone. Metadata: {meta_path}")


if __name__ == "__main__":
    main()
