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

# candidate WITH range feature (this experiment)
range_models = joblib.load(EXP / "candidate_regressors_plus_range.pkl")
range_meta = json.load(open(EXP / "candidate_plus_range_metadata.json", encoding="utf-8"))

# range_24h/max_level_24h history (extended, covers through 2026-09-07)
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
    X_base = latest[FEATS_CLEAN].to_numpy(dtype=float)
    current_qin = float(latest["Q_in_t"])
    fcst_row = arc_piv.loc[data_date] if data_date in arc_piv.index else None

    has_range = data_date in range_hist.index
    range_vals = range_hist.loc[data_date, ["max_level_24h", "range_24h"]].to_numpy(dtype=float) if has_range else None

    for h in range(1, 8):
        info = range_meta["horizons"][str(h)]
        feat_names = info["features"]
        X = X_base.copy()
        if info["uses_rain_forecast_binary"] and fcst_row is not None:
            cum = fcst_row.loc[1:h].sum()
            val = 1.0 if cum > info["rain_forecast_threshold_mm"] else 0.0
            X = np.append(X, val)
        elif info["uses_rain_forecast_binary"]:
            X = np.append(X, 0.0)  # fallback, matches production behavior on missing forecast
        pred_range = None
        if has_range:
            X_full = np.append(X, range_vals).reshape(1, -1)
            pred_range = max(current_qin + float(range_models[h].predict(X_full)[0]), 0.0)
        records.append({
            "recorded_as_of_date": d_ts, "horizon": h, "data_date": data_date,
            "has_range_feature": has_range, "pred_plus_range": pred_range,
        })

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date", "horizon"], how="left")
merged.to_csv(EXP / "range_candidate_vs_log.csv", index=False)

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean()) ** 2)
    return 1 - np.sum((actual - pred) ** 2) / denom if denom else np.nan

def mae(actual, pred):
    return float(np.mean(np.abs(np.asarray(actual, float) - np.asarray(pred, float))))

print(f"{'h':>2} {'n_total':>8} {'n_has_range':>12} {'MAE_production':>16} {'MAE_plus_range':>16} {'improvement':>12} {'NSE_prod':>10} {'NSE_plus_range':>14}")
summary = []
for h, g in merged.groupby("horizon"):
    g_all = g.dropna(subset=["actual_m3_per_day", "predicted_m3_per_day"])
    g_range = g_all.dropna(subset=["pred_plus_range"])
    n_total = len(g_all); n_range = len(g_range)
    mae_prod_all = mae(g_all["actual_m3_per_day"], g_all["predicted_m3_per_day"])
    if n_range > 0:
        mae_prod_range_subset = mae(g_range["actual_m3_per_day"], g_range["predicted_m3_per_day"])
        mae_cand = mae(g_range["actual_m3_per_day"], g_range["pred_plus_range"])
        nse_prod = nse(g_range["actual_m3_per_day"], g_range["predicted_m3_per_day"])
        nse_cand = nse(g_range["actual_m3_per_day"], g_range["pred_plus_range"])
        imp = 100 * (1 - mae_cand / mae_prod_range_subset) if mae_prod_range_subset else np.nan
    else:
        mae_prod_range_subset = mae_cand = nse_prod = nse_cand = imp = np.nan
    summary.append(dict(horizon=h, n_total=n_total, n_has_range=n_range,
                         mae_production_same_subset=mae_prod_range_subset, mae_plus_range=mae_cand,
                         improvement_pct=imp, nse_production=nse_prod, nse_plus_range=nse_cand))
    print(f"{h:>2} {n_total:>8} {n_range:>12} {mae_prod_range_subset if n_range else float('nan'):>16.0f} "
          f"{mae_cand if n_range else float('nan'):>16.0f} {imp if n_range else float('nan'):>11.1f}% "
          f"{nse_prod if n_range else float('nan'):>10.3f} {nse_cand if n_range else float('nan'):>14.3f}")

rep = pd.DataFrame(summary)
rep.to_csv(EXP / "range_candidate_real_log_summary.csv", index=False)
