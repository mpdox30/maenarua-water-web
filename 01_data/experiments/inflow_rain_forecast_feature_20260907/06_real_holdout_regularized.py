import importlib.util
import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor

EXP = Path.cwd()
H5EXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_h5_bias_fix_20260907")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

spec = importlib.util.spec_from_file_location("reconstruct", str(H5EXP / "09_reconstruct_live_features.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FEATS_BASE = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
              '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
              'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']
FEATS_CLEAN = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
               "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]

# same base hyperparams as production but ALWAYS early-stopped (od_wait=30, 15% chronological tail
# as validation) -- this is the general regularization fix, applied uniformly to control the
# tree-extrapolation/plateau failure mode for every horizon, not just h5
DEPLOY_PARAMS = {
    1: dict(depth=6, learning_rate=0.0109312751880508, l2_leaf_reg=23.808543547006124, min_data_in_leaf=8, subsample=0.8332116765879214, rsm=0.7890628480631008, random_strength=1.07161216899677),
    2: dict(depth=5, learning_rate=0.0146991485489077, l2_leaf_reg=1.7430504177815451, min_data_in_leaf=24, subsample=0.914033992242307, rsm=0.6212741213218833, random_strength=1.9674909492695445),
    3: dict(depth=5, learning_rate=0.0159859205807381, l2_leaf_reg=4.339666832543908, min_data_in_leaf=37, subsample=0.986523802644266, rsm=0.8127877215251221, random_strength=2.57649494325228),
    4: dict(depth=3, learning_rate=0.0109387154307568, l2_leaf_reg=3.810029124004568, min_data_in_leaf=36, subsample=0.4063769521841512, rsm=0.9913749176499462, random_strength=2.699726957831789),
    5: dict(depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472, min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372, random_strength=1.0),
    6: dict(depth=2, learning_rate=0.0136765950369614, l2_leaf_reg=4.382716203014211, min_data_in_leaf=29, subsample=0.7105210344032551, rsm=0.8290243458181864, random_strength=1.9867898992450308),
    7: dict(depth=2, learning_rate=0.0119080907879342, l2_leaf_reg=1.426422588105843, min_data_in_leaf=18, subsample=0.4317495679086314, rsm=0.7638703770649338, random_strength=1.0054966332229271),
}

df = pd.read_csv(EXP / "training_with_rain_forecast_features.csv", parse_dates=["Date"])
arc_piv = pd.read_csv(EXP / "rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"]).pivot_table(
    index="issue_date", columns="lead_day", values="precipitation_sum_mm")

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy()

def fit_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

models_base, models_with = {}, {}
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    fcst_col = f"Rain_fcst_cum_h{h} (mm)"
    sub_b = df.dropna(subset=FEATS_BASE + [target_col]).reset_index(drop=True)
    sub_w = df.dropna(subset=FEATS_BASE + [fcst_col, target_col]).reset_index(drop=True)
    p = DEPLOY_PARAMS[h]
    models_base[h] = fit_early_stopped(sub_b[FEATS_BASE].values, (sub_b[target_col]-sub_b["Q_in_t (m3/day)"]).values, p)
    models_with[h] = fit_early_stopped(sub_w[FEATS_BASE+[fcst_col]].values, (sub_w[target_col]-sub_w["Q_in_t (m3/day)"]).values, p)
    print(f"h{h}: base tree_count={models_base[h].tree_count_}  with_fcst tree_count={models_with[h].tree_count_}")

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
        pred_base = max(current_qin + float(models_base[h].predict(X_base)[0]), 0.0)
        rec = {"recorded_as_of_date": d_ts, "horizon": h, "pred_base_reg": pred_base}
        if fcst_row is not None:
            cum_fcst = fcst_row.loc[1:h].sum()
            X_with = np.append(X_base, cum_fcst).reshape(1, -1)
            rec["pred_with_fcst_reg"] = max(current_qin + float(models_with[h].predict(X_with)[0]), 0.0)
        records.append(rec)

recon = pd.DataFrame(records)
merged = log_c.merge(recon, on=["recorded_as_of_date","horizon"], how="left")
merged.to_csv(EXP / "real_holdout_regularized_comparison.csv", index=False)

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

print(f"\n{'h':>2} {'n':>4} {'MAE_orig_log':>13} {'MAE_base_reg':>13} {'MAE_with_fcst_reg':>18} {'NSE_base_reg':>13} {'NSE_with_fcst_reg':>18}")
summary = []
for h, g in merged.groupby("horizon"):
    g2 = g.dropna(subset=["pred_with_fcst_reg","actual_m3_per_day"])
    if len(g2) < 5:
        continue
    mae_orig = (g2["predicted_m3_per_day"]-g2["actual_m3_per_day"]).abs().mean()
    mae_b = (g2["pred_base_reg"]-g2["actual_m3_per_day"]).abs().mean()
    mae_w = (g2["pred_with_fcst_reg"]-g2["actual_m3_per_day"]).abs().mean()
    nse_b = nse(g2["actual_m3_per_day"], g2["pred_base_reg"])
    nse_w = nse(g2["actual_m3_per_day"], g2["pred_with_fcst_reg"])
    summary.append(dict(horizon=h, n=len(g2), mae_orig_log=mae_orig, mae_base_reg=mae_b, mae_with_fcst_reg=mae_w, nse_base_reg=nse_b, nse_with_fcst_reg=nse_w))
    print(f"{h:>2} {len(g2):>4} {mae_orig:>13.0f} {mae_b:>13.0f} {mae_w:>18.0f} {nse_b:>13.3f} {nse_w:>18.3f}")

pd.DataFrame(summary).to_csv(EXP / "real_holdout_regularized_summary.csv", index=False)
print("\nsaved real_holdout_regularized_comparison.csv, real_holdout_regularized_summary.csv")
