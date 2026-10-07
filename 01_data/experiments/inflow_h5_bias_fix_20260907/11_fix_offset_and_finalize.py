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

FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

regressors = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")
h5_v2 = joblib.load(EXP / "h5_v2_final_fulldata.pkl")

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy()
as_of_dates = sorted(log_c["recorded_as_of_date"].unique())

records = []
cache = {}
OFFSET_DAYS = 2  # run happens ~2 days after the data's own date, per empirical match found in step 10
for d in as_of_dates:
    d_ts = pd.Timestamp(d)
    run_ts = d_ts + pd.Timedelta(days=OFFSET_DAYS)
    if run_ts not in cache:
        df = rc.build_raw_df_as_of(run_ts)
        valid = df[df["valid"]] if not df.empty else df
        cache[run_ts] = valid
    valid = cache[run_ts]
    if valid.empty:
        continue
    latest = valid.iloc[-1]
    X = latest[FEATS_CLEAN].to_numpy(dtype=float).reshape(1, -1)
    current_qin = float(latest["Q_in_t"])
    for h in range(1, 8):
        delta_old = float(regressors[h].predict(X)[0])
        pred_old = max(current_qin + delta_old, 0.0)
        rec = {"recorded_as_of_date": d_ts, "horizon": h,
               "reconstructed_data_date": latest["date"], "current_qin_reconstructed": current_qin,
               "pred_old_reconstructed": pred_old}
        if h == 5:
            delta_new = float(h5_v2.predict(X)[0])
            rec["pred_v2_reconstructed"] = max(current_qin + delta_new, 0.0)
        records.append(rec)

recon_df = pd.DataFrame(records)
merged = log_c.merge(recon_df, on=["recorded_as_of_date","horizon"], how="left")
merged["match_diff"] = (merged["predicted_m3_per_day"] - merged["pred_old_reconstructed"]).abs()
sanity = merged.dropna(subset=["pred_old_reconstructed"])
print(f"Sanity: n={len(sanity)}, median abs diff={sanity['match_diff'].median():.1f}")
denom = sanity['predicted_m3_per_day'].abs().replace(0, np.nan)
print(f"pct within 5%: {100*((sanity['match_diff']/denom) < 0.05).mean():.1f}%")
print(f"pct within 1%: {100*((sanity['match_diff']/denom) < 0.01).mean():.1f}%")
print(sanity.groupby("horizon")["match_diff"].median())

merged.to_csv(EXP / "reconstructed_vs_log_v2.csv", index=False)
print("saved reconstructed_vs_log_v2.csv")
