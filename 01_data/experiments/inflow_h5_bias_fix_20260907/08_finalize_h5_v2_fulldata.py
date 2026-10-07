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
X_all = sub[FEATS].values
qin_all = sub["Q_in_t (m3/day)"].values
y_all = sub[TARGET].values
delta_all = y_all - qin_all

FINAL_ITERATIONS = 64  # chosen via early-stopping on CV/tail-holdout in step 07, avoids the 272-tree overfit
FINAL_PARAMS = dict(iterations=FINAL_ITERATIONS, depth=2, learning_rate=0.0121759578591452,
                     l2_leaf_reg=31.27438558692472, min_data_in_leaf=25,
                     subsample=0.9868547519916756, rsm=0.6502309452463372,
                     random_strength=1.0, loss_function="MAE", random_seed=42, verbose=False)

m_final = CatBoostRegressor(**FINAL_PARAMS)
m_final.fit(X_all, delta_all)
print("h5_v2_final tree_count_:", m_final.tree_count_)

regressors_orig = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")
m_old = regressors_orig[5]

# Compare delta distributions on full training set
d_old = m_old.predict(X_all)
d_new = m_final.predict(X_all)
print(f"\nIn-sample delta stats -- old: mean={d_old.mean():.0f} std={d_old.std():.0f} max={d_old.max():.0f} min={d_old.min():.0f}")
print(f"In-sample delta stats -- new: mean={d_new.mean():.0f} std={d_new.std():.0f} max={d_new.max():.0f} min={d_new.min():.0f}")

# Save final candidate model (experiments folder only)
m_final.save_model(str(Path.cwd() / "h5_v2_final_fulldata.cbm"))
joblib.dump(m_final, Path.cwd() / "h5_v2_final_fulldata.pkl")
print("\nSaved h5_v2_final_fulldata.cbm/.pkl (candidate replacement for horizon-5, NOT deployed to production)")
