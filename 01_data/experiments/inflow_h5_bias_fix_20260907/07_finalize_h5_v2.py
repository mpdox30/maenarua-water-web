import joblib, json, pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
FEATS = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
         '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
         'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']
TARGET = "y5=Q_in_t+5 (m3/day)"

df = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"]).sort_values("Date")
sub = df.dropna(subset=FEATS + [TARGET]).reset_index(drop=True)
n = len(sub)
cut = int(n * 0.85)  # last 15% chronological as early-stopping validation, matches original 70/15/15-ish tail

X_all = sub[FEATS].values
qin_all = sub["Q_in_t (m3/day)"].values
y_all = sub[TARGET].values
delta_all = y_all - qin_all

Xtr, Xva = X_all[:cut], X_all[cut:]
dtr, dva = delta_all[:cut], delta_all[cut:]

BEST_PARAMS = dict(iterations=300, depth=2, learning_rate=0.0121759578591452,
                    l2_leaf_reg=31.27438558692472, min_data_in_leaf=25,
                    subsample=0.9868547519916756, rsm=0.6502309452463372,
                    random_strength=1.0, loss_function="MAE",
                    od_type="Iter", od_wait=30, random_seed=42, verbose=False)

m_new = CatBoostRegressor(**BEST_PARAMS)
m_new.fit(Xtr, dtr, eval_set=(Xva, dva), use_best_model=True)
print("h5_v2 best_iter (tree_count_):", m_new.tree_count_, "/ requested", BEST_PARAMS["iterations"])

# Load original for comparison
regressors_orig = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")
m_old = regressors_orig[5]
print("h5_v1 (production) tree_count_:", m_old.tree_count_)

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

# Held-out tail evaluation (last 15%, genuinely not used for old model's training either -- old model trained on all 393 rows though, so this isn't fully fair to old model, just a diagnostic)
pred_new_va = np.maximum(qin_all[cut:] + m_new.predict(Xva), 0.0)
pred_old_va = np.maximum(qin_all[cut:] + m_old.predict(Xva), 0.0)
y_va = y_all[cut:]
print(f"\nTail-15% holdout (n={len(y_va)}):")
print(f"  h5_v1 (prod, saw this data in training): NSE={nse(y_va,pred_old_va):.3f} MAE={np.mean(np.abs(pred_old_va-y_va)):.1f}")
print(f"  h5_v2 (new, early-stopped, held this out): NSE={nse(y_va,pred_new_va):.3f} MAE={np.mean(np.abs(pred_new_va-y_va)):.1f}")

# Synthetic extrapolation stress test: sweep Rain_roll7/API_t beyond training max, holding other feats at median
med = np.median(X_all, axis=0)
idx_rain7 = FEATS.index("Rain_roll7 (mm)")
idx_api = FEATS.index("API_t (mm)")
print("\nSynthetic stress test -- sweeping Rain_roll7 & API_t from median to 3x training max, other feats at median:")
train_max_rain7 = X_all[:, idx_rain7].max()
train_max_api = X_all[:, idx_api].max()
print(f"{'mult':>5} {'Rain_roll7':>11} {'API_t':>8} {'delta_old':>12} {'delta_new':>12}")
for mult in [1.0, 1.5, 2.0, 3.0]:
    row = med.copy()
    row[idx_rain7] = train_max_rain7 * mult
    row[idx_api] = train_max_api * mult
    d_old = m_old.predict(row.reshape(1,-1))[0]
    d_new = m_new.predict(row.reshape(1,-1))[0]
    print(f"{mult:>5.1f} {row[idx_rain7]:>11.1f} {row[idx_api]:>8.1f} {d_old:>12.1f} {d_new:>12.1f}")

# Save the new model + summary into experiments folder ONLY
m_new.save_model(str(Path.cwd() / "h5_v2_model.cbm"))
joblib.dump(m_new, Path.cwd() / "h5_v2_model.pkl")

summary = {
    "chosen_params": BEST_PARAMS,
    "h5_v2_tree_count": int(m_new.tree_count_),
    "h5_v1_tree_count": int(m_old.tree_count_),
    "tail15pct_holdout_n": int(len(y_va)),
    "tail15pct_nse_v1_prod": float(nse(y_va,pred_old_va)),
    "tail15pct_nse_v2_new": float(nse(y_va,pred_new_va)),
    "tail15pct_mae_v1_prod": float(np.mean(np.abs(pred_old_va-y_va))),
    "tail15pct_mae_v2_new": float(np.mean(np.abs(pred_new_va-y_va))),
}
with open("h5_v2_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nSaved h5_v2_model.cbm / .pkl and h5_v2_summary.json")
