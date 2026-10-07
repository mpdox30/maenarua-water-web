"""
Build the SELECTIVE candidate: add range_24h/max_level_24h only to horizons where it demonstrably
helped in the apples-to-apples out-of-sample test (h2,h4,h5,h6,h7). h1,h3 stay on the currently
deployed feature set (no range -- h1 was noise-level, h3 was consistently worse).

Then: full point-in-time reconstruction over the whole log, re-fit bias correction per horizon
(65/35 honest split, same as the original bias_recalibration_on_candidate.py), and produce the
final end-to-end comparison against the model that's currently live in production.
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

RANGE_HORIZONS = {2, 4, 5, 6, 7}  # h1, h3 excluded (no help / worse)

deployed_models = joblib.load(REGEXP / "candidate_regressors_regularized_final.pkl")
deployed_meta = json.load(open(REGEXP / "candidate_metadata.json", encoding="utf-8"))
range_models = joblib.load(EXP / "candidate_regressors_plus_range.pkl")
range_meta = json.load(open(EXP / "candidate_plus_range_metadata.json", encoding="utf-8"))

# build the combined SELECTIVE model dict + metadata
selective_models = {}
selective_meta = {"horizons": {}}
for h in range(1, 8):
    if h in RANGE_HORIZONS:
        selective_models[h] = range_models[h]
        selective_meta["horizons"][str(h)] = range_meta["horizons"][str(h)]
    else:
        selective_models[h] = deployed_models[h]
        selective_meta["horizons"][str(h)] = deployed_meta["horizons"][str(h)]
joblib.dump(selective_models, EXP / "candidate_regressors_selective_range.pkl")
with open(EXP / "candidate_selective_range_metadata.json", "w", encoding="utf-8") as f:
    json.dump(selective_meta, f, indent=2, ensure_ascii=False)

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
        info = selective_meta["horizons"][str(h)]
        if h in RANGE_HORIZONS and not has_range:
            continue  # can't compute this horizon's prediction without range data
        X = X_base.copy()
        if info["uses_rain_forecast_binary"]:
            rain_val = 0.0
            if fcst_row is not None:
                cum = fcst_row.loc[1:h].sum()
                rain_val = 1.0 if cum > info["rain_forecast_threshold_mm"] else 0.0
            X = np.append(X, rain_val)
        if h in RANGE_HORIZONS:
            X = np.append(X, range_vals)
        pred = max(current_qin + float(selective_models[h].predict(X.reshape(1, -1))[0]), 0.0)
        records.append(dict(recorded_as_of_date=d_ts, horizon=h, data_date=data_date, pred_selective=pred))

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date", "horizon"], how="left")
merged.to_csv(EXP / "selective_candidate_vs_log.csv", index=False)

def nse(actual, pred):
    actual = np.asarray(actual, float); pred = np.asarray(pred, float)
    denom = np.sum((actual - actual.mean()) ** 2)
    return 1 - np.sum((actual - pred) ** 2) / denom if denom else np.nan

# --- re-fit bias correction on the selective candidate (65/35 honest split, same as before) ---
df = merged.dropna(subset=["pred_selective", "actual_m3_per_day"]).sort_values(["horizon", "recorded_as_of_date"])
FIT_FRAC = 0.65
bias_rows = []
for h, g in df.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n * FIT_FRAC), 5)
    fit, hold = g.iloc[:cut], g.iloc[cut:]
    if len(hold) < 3:
        continue
    bias_fit = (fit["pred_selective"] - fit["actual_m3_per_day"]).mean()
    mae_before = (hold["pred_selective"] - hold["actual_m3_per_day"]).abs().mean()
    nse_before = nse(hold["actual_m3_per_day"], hold["pred_selective"])
    corrected = (hold["pred_selective"] - bias_fit).clip(lower=0.0)
    mae_after = (corrected - hold["actual_m3_per_day"]).abs().mean()
    nse_after = nse(hold["actual_m3_per_day"], corrected)
    bias_rows.append(dict(horizon=h, n_fit=len(fit), n_holdout=len(hold), bias_correction=bias_fit,
                           mae_before=mae_before, mae_after=mae_after,
                           nse_before=nse_before, nse_after=nse_after, improve=mae_before - mae_after))

bias_rep = pd.DataFrame(bias_rows)
bias_rep.to_csv(EXP / "selective_bias_recalibration_results.csv", index=False)
print("=== bias recalibration on selective candidate ===")
print(bias_rep.round(1).to_string(index=False))
