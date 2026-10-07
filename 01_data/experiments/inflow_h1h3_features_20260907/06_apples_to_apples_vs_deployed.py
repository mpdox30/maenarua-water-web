"""
Apples-to-apples: compare CURRENTLY DEPLOYED candidate (regularized + rain-binary h3/6/7, no range)
against the +range candidate, both reconstructed point-in-time over the SAME as_of dates (the ones
where the extended range_24h history has coverage). Neither includes the post-hoc bias correction
here -- isolate the raw marginal effect of the range feature first; bias correction can be redone
after if range is adopted.
"""
import json, joblib, importlib.util
import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")
H5EXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_h5_bias_fix_20260907")
REGEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_regularized_final_20260907")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

spec = importlib.util.spec_from_file_location("reconstruct", str(H5EXP / "09_reconstruct_live_features.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

deployed_models = joblib.load(REGEXP / "candidate_regressors_regularized_final.pkl")
deployed_meta = json.load(open(REGEXP / "candidate_metadata.json", encoding="utf-8"))
range_models = joblib.load(EXP / "candidate_regressors_plus_range.pkl")
range_meta = json.load(open(EXP / "candidate_plus_range_metadata.json", encoding="utf-8"))

range_hist = pd.read_csv(EXP / "intraday_range_full_history_extended.csv", parse_dates=["Date"]).set_index("Date")
arc_piv = pd.read_csv(RAINEXP / "rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"]).pivot_table(
    index="issue_date", columns="lead_day", values="precipitation_sum_mm")

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy()

records = []
cache = {}
OFFSET_DAYS = 2
as_of_dates = sorted(log_c["recorded_as_of_date"].unique())
for d in as_of_dates:
    d_ts = pd.Timestamp(d)
    run_ts = d_ts + pd.Timedelta(days=OFFSET_DAYS)
    if run_ts not in cache:
        rdf = rc.build_raw_df_as_of(run_ts)
        valid = rdf[rdf["valid"]] if not rdf.empty else rdf
        cache[run_ts] = valid
    valid = cache[run_ts]
    if valid.empty:
        continue
    latest = valid.iloc[-1]
    data_date = latest["date"]
    if data_date not in range_hist.index:
        continue  # only compare on dates where range feature is actually available
    X_base = latest[FEATS_CLEAN].to_numpy(dtype=float)
    current_qin = float(latest["Q_in_t"])
    fcst_row = arc_piv.loc[data_date] if data_date in arc_piv.index else None
    range_vals = range_hist.loc[data_date, ["max_level_24h", "range_24h"]].to_numpy(dtype=float)

    for h in range(1, 8):
        dep_info = deployed_meta["horizons"][str(h)]
        X_dep = X_base.copy()
        rain_val = 0.0
        if dep_info["uses_rain_forecast_binary"]:
            if fcst_row is not None:
                cum = fcst_row.loc[1:h].sum()
                rain_val = 1.0 if cum > dep_info["rain_forecast_threshold_mm"] else 0.0
            X_dep = np.append(X_dep, rain_val)
        pred_deployed = max(current_qin + float(deployed_models[h].predict(X_dep.reshape(1, -1))[0]), 0.0)

        X_range = X_base.copy()
        if dep_info["uses_rain_forecast_binary"]:
            X_range = np.append(X_range, rain_val)
        X_range = np.append(X_range, range_vals)
        pred_range = max(current_qin + float(range_models[h].predict(X_range.reshape(1, -1))[0]), 0.0)

        records.append(dict(recorded_as_of_date=d_ts, horizon=h, data_date=data_date,
                             pred_deployed=pred_deployed, pred_plus_range=pred_range))

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date","horizon"], how="inner")
merged.to_csv(EXP / "apples_to_apples_vs_deployed.csv", index=False)

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan
def mae(actual, pred):
    return float(np.mean(np.abs(np.asarray(actual,float)-np.asarray(pred,float))))

print(f"{'h':>2} {'n':>4} {'MAE_deployed(now)':>18} {'MAE_plus_range':>16} {'improvement':>12} {'NSE_deployed':>13} {'NSE_plus_range':>15}")
summary=[]
for h, g in merged.groupby("horizon"):
    g2 = g.dropna(subset=["actual_m3_per_day","pred_deployed","pred_plus_range"])
    mae_dep = mae(g2["actual_m3_per_day"], g2["pred_deployed"])
    mae_rng = mae(g2["actual_m3_per_day"], g2["pred_plus_range"])
    nse_dep = nse(g2["actual_m3_per_day"], g2["pred_deployed"])
    nse_rng = nse(g2["actual_m3_per_day"], g2["pred_plus_range"])
    imp = 100*(1-mae_rng/mae_dep) if mae_dep else np.nan
    summary.append(dict(horizon=h, n=len(g2), mae_deployed=mae_dep, mae_plus_range=mae_rng,
                         improvement_pct=imp, nse_deployed=nse_dep, nse_plus_range=nse_rng))
    print(f"{h:>2} {len(g2):>4} {mae_dep:>18.0f} {mae_rng:>16.0f} {imp:>11.1f}% {nse_dep:>13.3f} {nse_rng:>15.3f}")

rep = pd.DataFrame(summary)
rep.to_csv(EXP / "apples_to_apples_summary.csv", index=False)
w_dep=(rep.mae_deployed*rep.n).sum()/rep.n.sum()
w_rng=(rep.mae_plus_range*rep.n).sum()/rep.n.sum()
print(f"\nWeighted MAE: deployed(now)={w_dep:.0f}  plus_range={w_rng:.0f}  overall improvement={100*(1-w_rng/w_dep):.1f}%")
