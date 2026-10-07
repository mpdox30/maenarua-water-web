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

def signed_log_inv(z):
    return np.sign(z) * (np.expm1(np.abs(z)))

log_models = joblib.load(EXP / "candidate_regressors_signed_log.pkl")
log_meta = json.load(open(EXP / "candidate_signed_log_metadata.json", encoding="utf-8"))
deployed_models = joblib.load(REGEXP / "candidate_regressors_regularized_final.pkl")
deployed_meta = json.load(open(REGEXP / "candidate_metadata.json", encoding="utf-8"))

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
    X_base = latest[FEATS_CLEAN].to_numpy(dtype=float)
    current_qin = float(latest["Q_in_t"])
    fcst_row = arc_piv.loc[data_date] if data_date in arc_piv.index else None

    for h in range(1, 8):
        info = deployed_meta["horizons"][str(h)]
        rain_val = 0.0
        if info["uses_rain_forecast_binary"] and fcst_row is not None:
            cum = fcst_row.loc[1:h].sum()
            rain_val = 1.0 if cum > info["rain_forecast_threshold_mm"] else 0.0
        X = np.append(X_base, rain_val).reshape(1, -1) if info["uses_rain_forecast_binary"] else X_base.reshape(1, -1)

        pred_deployed = max(current_qin + float(deployed_models[h].predict(X)[0]), 0.0)
        z_pred = float(log_models[h].predict(X)[0])
        delta_log = signed_log_inv(z_pred)
        pred_logtransform = max(current_qin + delta_log, 0.0)

        records.append(dict(recorded_as_of_date=d_ts, horizon=h, data_date=data_date,
                             pred_deployed=pred_deployed, pred_logtransform=pred_logtransform))

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date","horizon"], how="left")
merged.to_csv(EXP / "logtransform_vs_deployed_full_log.csv", index=False)

def nse(a, p):
    a=np.asarray(a,float); p=np.asarray(p,float)
    d = np.sum((a-a.mean())**2)
    return 1-np.sum((a-p)**2)/d if d else np.nan

# --- final rigorous test: last 35% chronological holdout per horizon, matching deploy-decision methodology ---
FIT_FRAC = 0.65
rows = []
for h, g in merged.dropna(subset=["actual_m3_per_day","pred_deployed","pred_logtransform"]).groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n * FIT_FRAC), 5)
    hold = g.iloc[cut:]
    if len(hold) < 3:
        continue
    mae_dep = (hold["pred_deployed"] - hold["actual_m3_per_day"]).abs().mean()
    mae_log = (hold["pred_logtransform"] - hold["actual_m3_per_day"]).abs().mean()
    nse_dep = nse(hold["actual_m3_per_day"], hold["pred_deployed"])
    nse_log = nse(hold["actual_m3_per_day"], hold["pred_logtransform"])
    imp = 100 * (1 - mae_log / mae_dep) if mae_dep else np.nan
    rows.append(dict(horizon=h, n=len(hold), mae_deployed=mae_dep, mae_logtransform=mae_log,
                      improvement_pct=imp, nse_deployed=nse_dep, nse_logtransform=nse_log))

rep = pd.DataFrame(rows)
pd.set_option("display.width", 160)
print("=== FINAL (last-35%% holdout, no bias correction on either side yet) ===")
print(rep.round(3).to_string(index=False))
rep.to_csv(EXP / "final_holdout_logtransform_vs_deployed.csv", index=False)
w_dep = (rep.mae_deployed * rep.n).sum() / rep.n.sum()
w_log = (rep.mae_logtransform * rep.n).sum() / rep.n.sum()
print(f"\nWeighted MAE: deployed={w_dep:.0f}  logtransform={w_log:.0f}  overall improvement={100*(1-w_log/w_dep):.1f}%")
