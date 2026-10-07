"""
Telemetry integration feasibility study.

IMPORTANT CORRECTION to what was said earlier this session (in the range_24h report): telemetry is
NOT disconnected from the forecasting pipeline. `reservoir_daily_orchestration.py` has been running
automatically via Windows Task Scheduler every morning at 07:30 since 2026-07-18 (confirmed: a
".bak_before_live_write_<date>" backup exists for every single day 2026-07-18 .. 2026-09-07, no
gaps), computing Water_Level_t/Storage/Inflow from live telemetry (wide_log Google Sheet, polled
every 10 min) and writing directly into the OFFICIAL account xlsx files
(01_data/Reservoirs/inflow/<year>/<year>_<month>_MNR.xlsx) -- the exact files data_pipeline.py reads
as its feature source. It also auto-pushes those files to GitHub (added 2026-08-12).

So "telemetry -> account file" is already live and reliable (verified: file written each morning by
~09:20 always contains complete data through *yesterday*, i.e. minimal 1-day lag -- see file mtimes
under 01_data/Reservoirs/inflow/2026/).

The REAL remaining gap: Colab reads the account files from a Google-Drive mirror
(G:\\My Drive\\Colab Notebooks\\Mae_Na_Rua\\...), refreshed by `sync_to_drive.bat`, which
(per its own comments) supports being run either manually or via Task Scheduler -- but there's no
direct evidence in the repo that the Task Scheduler option was ever set up, and this session already
hit a real incident where the user ran Colab without having just run sync_to_drive.bat, causing
stale data to be used. This matches the empirically-calibrated OFFSET_DAYS=2 in the point-in-time
reconstruction tool (used throughout this session) -- i.e., production has historically been running
on data that's ~2 days stale on average, when the underlying telemetry pipeline could support ~1 day
(the practical minimum, since a full calendar day's 07:00-07:00 telemetry window can't close until
that day is basically over).

This script quantifies: how much would prediction accuracy improve if staleness were reduced from
~2 days (current typical, OFFSET_DAYS=2) to ~1 day (the practical minimum if sync always ran
promptly, OFFSET_DAYS=1)? Uses the CURRENTLY DEPLOYED model (no candidate changes) -- this measures
a pure operational/scheduling fix, not a model change.
"""
import json, joblib, importlib.util
import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()
H5EXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_h5_bias_fix_20260907")
REGEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_regularized_final_20260907")
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

spec = importlib.util.spec_from_file_location("reconstruct", str(H5EXP / "09_reconstruct_live_features.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]
deployed_models = joblib.load(REGEXP / "candidate_regressors_regularized_final.pkl")
deployed_meta = json.load(open(REGEXP / "candidate_metadata.json", encoding="utf-8"))
arc_piv = pd.read_csv(RAINEXP / "rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"]).pivot_table(
    index="issue_date", columns="lead_day", values="precipitation_sum_mm")

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy()
log_c = log_c[log_c.recorded_as_of_date >= "2026-07-20"]  # post-telemetry-live period only

def nse(a, p):
    a = np.asarray(a, float); p = np.asarray(p, float)
    d = np.sum((a - a.mean()) ** 2)
    return 1 - np.sum((a - p) ** 2) / d if d else np.nan

def mae(a, p):
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(p, float))))

results = {}
for OFFSET in [1, 2]:
    records = []
    cache = {}
    for d in sorted(log_c.recorded_as_of_date.unique()):
        d_ts = pd.Timestamp(d); run_ts = d_ts + pd.Timedelta(days=OFFSET)
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
            rv = 0.0
            if info["uses_rain_forecast_binary"] and fcst_row is not None:
                cum = fcst_row.loc[1:h].sum()
                rv = 1.0 if cum > info["rain_forecast_threshold_mm"] else 0.0
            X = np.append(X_base, rv).reshape(1, -1) if info["uses_rain_forecast_binary"] else X_base.reshape(1, -1)
            pred = max(current_qin + float(deployed_models[h].predict(X)[0]), 0.0)
            records.append(dict(recorded_as_of_date=d_ts, horizon=h, pred=pred))
    recon = pd.DataFrame(records)
    merged = log_c.merge(recon, on=["recorded_as_of_date", "horizon"], how="left").dropna(
        subset=["pred", "actual_m3_per_day"])
    results[OFFSET] = merged
    merged.to_csv(EXP / f"reconstruction_offset{OFFSET}.csv", index=False)

rows = []
print(f"{'h':>2} {'n':>4} {'NSE_offset1_fresher':>20} {'NSE_offset2_current':>20} {'MAE_off1':>10} {'MAE_off2':>10}")
for h in range(1, 8):
    g1 = results[1][results[1].horizon == h]
    g2 = results[2][results[2].horizon == h]
    n1, n2 = nse(g1.actual_m3_per_day, g1.pred), nse(g2.actual_m3_per_day, g2.pred)
    m1, m2 = mae(g1.actual_m3_per_day, g1.pred), mae(g2.actual_m3_per_day, g2.pred)
    rows.append(dict(horizon=h, n=len(g1), nse_offset1=n1, nse_offset2=n2, mae_offset1=m1, mae_offset2=m2))
    print(f"{h:>2} {len(g1):>4} {n1:>20.3f} {n2:>20.3f} {m1:>10.0f} {m2:>10.0f}")

pd.DataFrame(rows).to_csv(EXP / "offset_sensitivity_results.csv", index=False)
