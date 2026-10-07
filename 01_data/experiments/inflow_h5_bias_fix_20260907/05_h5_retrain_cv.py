import joblib, json, pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor
from sklearn.model_selection import TimeSeriesSplit

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
FEATS = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
         '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
         'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']
TARGET = "y5=Q_in_t+5 (m3/day)"

df = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"]).sort_values("Date")
sub = df.dropna(subset=FEATS + [TARGET]).reset_index(drop=True)
X_all = sub[FEATS].values
qin_all = sub["Q_in_t (m3/day)"].values
y_all = sub[TARGET].values  # actual Q_in_t+5
delta_all = y_all - qin_all  # what the model is trained to predict

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

ORIG_PARAMS = dict(iterations=300, depth=2, learning_rate=0.0121759578591452,
                    l2_leaf_reg=31.27438558692472, min_data_in_leaf=25,
                    subsample=0.9868547519916756, rsm=0.6502309452463372,
                    random_strength=0.217429400040442, loss_function="MAE",
                    random_seed=42, verbose=False)

# Candidate: more conservative -- higher random_strength (reduce deterministic overfit),
# use early stopping instead of trusting fixed iterations=300/best_iter=271.
CANDIDATE_PARAMS = dict(iterations=300, depth=2, learning_rate=0.0121759578591452,
                         l2_leaf_reg=31.27438558692472, min_data_in_leaf=25,
                         subsample=0.9868547519916756, rsm=0.6502309452463372,
                         random_strength=2.0, loss_function="MAE",
                         random_seed=42, verbose=False, od_type="Iter", od_wait=30)

tscv = TimeSeriesSplit(n_splits=5)

def cv_eval(params, use_early_stop=False):
    fold_nse = []
    for fold_i, (tr_idx, va_idx) in enumerate(tscv.split(X_all)):
        Xtr, Xva = X_all[tr_idx], X_all[va_idx]
        dtr, dva = delta_all[tr_idx], delta_all[va_idx]
        qtr, qva = qin_all[tr_idx], qin_all[va_idx]
        ytr, yva = y_all[tr_idx], y_all[va_idx]
        m = CatBoostRegressor(**params)
        if use_early_stop:
            m.fit(Xtr, dtr, eval_set=(Xva, dva), use_best_model=True)
        else:
            m.fit(Xtr, dtr)
        pred_delta = m.predict(Xva)
        pred = np.maximum(qva + pred_delta, 0.0)
        fold_nse.append(nse(yva, pred))
    return fold_nse

print("=== ORIGINAL params, no early stop (matches production) ===")
orig_folds = cv_eval(ORIG_PARAMS, use_early_stop=False)
print("fold NSE:", [round(x,3) for x in orig_folds], "mean:", round(np.mean(orig_folds),4))

print("\n=== CANDIDATE params (random_strength=2.0, early stopping od_wait=30) ===")
cand_folds = cv_eval(CANDIDATE_PARAMS, use_early_stop=True)
print("fold NSE:", [round(x,3) for x in cand_folds], "mean:", round(np.mean(cand_folds),4))

# Also try a version with fewer iterations + more depth-limited safety: cap random_strength higher still
CANDIDATE2 = dict(CANDIDATE_PARAMS); CANDIDATE2["random_strength"] = 5.0
print("\n=== CANDIDATE2 (random_strength=5.0, early stopping) ===")
cand2_folds = cv_eval(CANDIDATE2, use_early_stop=True)
print("fold NSE:", [round(x,3) for x in cand2_folds], "mean:", round(np.mean(cand2_folds),4))

# Try higher l2 + early stop
CANDIDATE3 = dict(CANDIDATE_PARAMS); CANDIDATE3["l2_leaf_reg"] = 60.0
print("\n=== CANDIDATE3 (l2_leaf_reg=60, random_strength=2.0, early stopping) ===")
cand3_folds = cv_eval(CANDIDATE3, use_early_stop=True)
print("fold NSE:", [round(x,3) for x in cand3_folds], "mean:", round(np.mean(cand3_folds),4))

results = {
    "original": {"folds": orig_folds, "mean": float(np.mean(orig_folds))},
    "candidate_rs2_earlystop": {"folds": cand_folds, "mean": float(np.mean(cand_folds))},
    "candidate_rs5_earlystop": {"folds": cand2_folds, "mean": float(np.mean(cand2_folds))},
    "candidate_l2_60_rs2_earlystop": {"folds": cand3_folds, "mean": float(np.mean(cand3_folds))},
}
with open("h5_cv_comparison.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
