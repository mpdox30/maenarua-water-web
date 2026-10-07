import json, pandas as pd, numpy as np
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
y_all = sub[TARGET].values
delta_all = y_all - qin_all

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

tscv = TimeSeriesSplit(n_splits=5)

def cv_eval(params, od_wait=30):
    p = dict(params); p.update(od_type="Iter", od_wait=od_wait, verbose=False, random_seed=42)
    fold_nse = []
    for tr_idx, va_idx in tscv.split(X_all):
        Xtr, Xva = X_all[tr_idx], X_all[va_idx]
        dtr, dva = delta_all[tr_idx], delta_all[va_idx]
        qva, yva = qin_all[va_idx], y_all[va_idx]
        m = CatBoostRegressor(**p)
        m.fit(Xtr, dtr, eval_set=(Xva, dva), use_best_model=True)
        pred = np.maximum(qva + m.predict(Xva), 0.0)
        fold_nse.append(nse(yva, pred))
    return fold_nse, float(np.mean(fold_nse))

base = dict(iterations=300, learning_rate=0.0121759578591452, loss_function="MAE", min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372)

grid = [
    dict(base, depth=2, l2_leaf_reg=31.27, random_strength=2.0),
    dict(base, depth=2, l2_leaf_reg=31.27, random_strength=3.0),
    dict(base, depth=1, l2_leaf_reg=31.27, random_strength=2.0),
    dict(base, depth=3, l2_leaf_reg=31.27, random_strength=2.0),
    dict(base, depth=2, l2_leaf_reg=50.0, random_strength=2.0),
    dict(base, depth=2, l2_leaf_reg=31.27, random_strength=2.0, min_data_in_leaf=40),
    dict(base, depth=2, l2_leaf_reg=31.27, random_strength=1.0),
]
results = []
for i, p in enumerate(grid):
    folds, mean = cv_eval(p)
    print(f"grid[{i}] depth={p['depth']} l2={p['l2_leaf_reg']} rs={p['random_strength']} mdl={p['min_data_in_leaf']} -> mean NSE {mean:.4f} folds={[round(x,3) for x in folds]}")
    results.append({"params": {k:v for k,v in p.items() if k not in ('verbose',)}, "folds": folds, "mean": mean})

best = max(results, key=lambda r: r["mean"])
print("\nBEST:", best["params"], "mean NSE", best["mean"])
with open("h5_grid_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
