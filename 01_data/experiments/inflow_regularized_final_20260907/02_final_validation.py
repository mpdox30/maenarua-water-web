import json, joblib, importlib.util
import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")
H5EXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_h5_bias_fix_20260907")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

spec = importlib.util.spec_from_file_location("reconstruct", str(H5EXP / "09_reconstruct_live_features.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

models = joblib.load(EXP / "candidate_regressors_regularized_final.pkl")
meta = json.load(open(EXP / "candidate_metadata.json", encoding="utf-8"))
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
    X_base = latest[FEATS_CLEAN].to_numpy(dtype=float).reshape(1, -1)
    current_qin = float(latest["Q_in_t"])
    fcst_row = arc_piv.loc[data_date] if data_date in arc_piv.index else None
    for h in range(1, 8):
        info = meta["horizons"][str(h)]
        if info["uses_rain_forecast_binary"] and fcst_row is not None:
            cum = fcst_row.loc[1:h].sum()
            val = 1.0 if cum > info["rain_forecast_threshold_mm"] else 0.0
            X = np.append(X_base, val).reshape(1, -1)
        else:
            X = X_base
        pred = max(current_qin + float(models[h].predict(X)[0]), 0.0)
        records.append({"recorded_as_of_date": d_ts, "horizon": h, "pred_final_candidate": pred})

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date","horizon"], how="left")
merged.to_csv(EXP / "final_candidate_vs_log.csv", index=False)

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

print(f"{'h':>2} {'n':>4} {'MAE_production(now)':>20} {'MAE_final_candidate':>20} {'improvement':>12} {'NSE_candidate':>13}")
summary = []
for h, g in merged.groupby("horizon"):
    g2 = g.dropna(subset=["pred_final_candidate"])
    mae_prod = (g2["predicted_m3_per_day"]-g2["actual_m3_per_day"]).abs().mean()
    mae_cand = (g2["pred_final_candidate"]-g2["actual_m3_per_day"]).abs().mean()
    nse_cand = nse(g2["actual_m3_per_day"], g2["pred_final_candidate"])
    imp = 100*(1 - mae_cand/mae_prod)
    summary.append(dict(horizon=h, n=len(g2), mae_production=mae_prod, mae_final_candidate=mae_cand,
                         improvement_pct=imp, nse_final_candidate=nse_cand))
    print(f"{h:>2} {len(g2):>4} {mae_prod:>20.0f} {mae_cand:>20.0f} {imp:>11.1f}% {nse_cand:>13.3f}")

rep = pd.DataFrame(summary)
rep.to_csv(EXP / "final_candidate_summary.csv", index=False)
w_before = (rep["mae_production"]*rep["n"]).sum()/rep["n"].sum()
w_after = (rep["mae_final_candidate"]*rep["n"]).sum()/rep["n"].sum()
print(f"\nWeighted-avg MAE across all horizons: production={w_before:.0f}  final_candidate={w_after:.0f}  "
      f"overall improvement={100*(1-w_after/w_before):.1f}%")
