import json, joblib
import pandas as pd, numpy as np
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location("reconstruct", "09_reconstruct_live_features.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")
EXP = Path.cwd()

FEATS_META = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
              '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
              'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']
FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

regressors = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")
h5_v2 = joblib.load(EXP / "h5_v2_final_fulldata.pkl")

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy()

as_of_dates = sorted(log_c["recorded_as_of_date"].unique())
print(f"{len(as_of_dates)} unique recorded_as_of_date values with complete actuals")

records = []
cache = {}
for d in as_of_dates:
    d_ts = pd.Timestamp(d)
    if d_ts not in cache:
        df = rc.build_raw_df_as_of(d_ts)
        valid = df[df["valid"]] if not df.empty else df
        cache[d_ts] = valid
    valid = cache[d_ts]
    if valid.empty:
        continue
    latest = valid.iloc[-1]
    X = latest[FEATS_CLEAN].to_numpy(dtype=float).reshape(1, -1)
    current_qin = float(latest["Q_in_t"])
    reconstructed_asof = latest["date"]
    for h in range(1, 8):
        delta_old = float(regressors[h].predict(X)[0])
        pred_old = max(current_qin + delta_old, 0.0)
        rec = {
            "recorded_as_of_date": d_ts, "horizon": h,
            "reconstructed_data_asof": reconstructed_asof,
            "current_qin_reconstructed": current_qin,
            "pred_old_reconstructed": pred_old,
        }
        if h == 5:
            delta_new = float(h5_v2.predict(X)[0])
            rec["pred_v2_reconstructed"] = max(current_qin + delta_new, 0.0)
        records.append(rec)

recon_df = pd.DataFrame(records)
merged = log_c.merge(recon_df, on=["recorded_as_of_date","horizon"], how="left")
merged["match_diff"] = (merged["predicted_m3_per_day"] - merged["pred_old_reconstructed"]).abs()

# Sanity check: how well does reconstruction match the ORIGINAL logged predictions (h!=5, or h5 old)?
sanity = merged.dropna(subset=["pred_old_reconstructed"])
print("\nSanity check -- reconstructed vs originally-logged predicted_m3_per_day (all horizons):")
print(f"  n={len(sanity)}, median abs diff={sanity['match_diff'].median():.1f}, "
      f"pct within 5%={100*(sanity['match_diff'] / sanity['predicted_m3_per_day'].replace(0,np.nan).abs() < 0.05).mean():.1f}%")
print(sanity.groupby("horizon")["match_diff"].median())

merged.to_csv(EXP / "reconstructed_vs_log_full.csv", index=False)
print("\nSaved reconstructed_vs_log_full.csv")
