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

PCTS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

def fit_early_stopped(X, y, params, seed=42):
    n = len(X); cut = int(n * 0.85)
    p = dict(params); p.update(iterations=300, loss_function="MAE", random_seed=seed, verbose=False,
                                od_type="Iter", od_wait=30)
    m = CatBoostRegressor(**p)
    m.fit(X[:cut], y[:cut], eval_set=(X[cut:], y[cut:]), use_best_model=True)
    return m

records_raw = []
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
        raw_cum = fcst_row.loc[1:h].sum() if fcst_row is not None else np.nan
        records_raw.append({"recorded_as_of_date": d_ts, "horizon": h, "X_base": X_base,
                             "current_qin": current_qin, "raw_cum": raw_cum})
recon_raw = pd.DataFrame(records_raw)

baseline = pd.read_csv(EXP / "real_holdout_regularized_summary.csv").set_index("horizon")

final_rows = []
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    raw_col = f"Rain_fcst_cum_h{h} (mm)"
    train_vals = df[raw_col].dropna()

    g_log = log_c[log_c.horizon == h].merge(
        recon_raw[recon_raw.horizon==h], on=["recorded_as_of_date","horizon"], how="left"
    ).dropna(subset=["raw_cum"]).sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g_log)
    cut = max(int(n * 0.65), 5)
    fit_set, hold_set = g_log.iloc[:cut], g_log.iloc[cut:]
    if len(hold_set) < 3:
        continue

    # pick best threshold using ONLY fit_set (honest: holdout untouched during selection)
    best_pct, best_fit_mae = None, np.inf
    fitted_models = {}
    for pct in PCTS:
        thresh = train_vals.quantile(pct)
        col = f"bin_p{int(pct*100)}_h{h}"
        df[col] = (df[raw_col] > thresh).astype(float)
        sub = df.dropna(subset=FEATS_BASE + [col, target_col]).reset_index(drop=True)
        m = fit_early_stopped(sub[FEATS_BASE+[col]].values, (sub[target_col]-sub["Q_in_t (m3/day)"]).values, DEPLOY_PARAMS[h])
        fitted_models[pct] = (thresh, m)

        preds = []
        for _, row in fit_set.iterrows():
            val = 1.0 if row["raw_cum"] > thresh else 0.0
            X_v = np.append(row["X_base"], val).reshape(1, -1)
            preds.append(max(row["current_qin"] + float(m.predict(X_v)[0]), 0.0))
        mae_fit = np.mean(np.abs(np.array(preds) - fit_set["actual_m3_per_day"].values))
        if mae_fit < best_fit_mae:
            best_fit_mae = mae_fit
            best_pct = pct

    thresh, m = fitted_models[best_pct]
    preds_hold = []
    for _, row in hold_set.iterrows():
        val = 1.0 if row["raw_cum"] > thresh else 0.0
        X_v = np.append(row["X_base"], val).reshape(1, -1)
        preds_hold.append(max(row["current_qin"] + float(m.predict(X_v)[0]), 0.0))
    mae_hold_with_feat = np.mean(np.abs(np.array(preds_hold) - hold_set["actual_m3_per_day"].values))

    # compare against no-feature baseline model evaluated on the SAME holdout subset (fair apples-to-apples)
    sub_b = df.dropna(subset=FEATS_BASE + [target_col]).reset_index(drop=True)
    mb = fit_early_stopped(sub_b[FEATS_BASE].values, (sub_b[target_col]-sub_b["Q_in_t (m3/day)"]).values, DEPLOY_PARAMS[h])
    preds_hold_base = []
    for _, row in hold_set.iterrows():
        preds_hold_base.append(max(row["current_qin"] + float(mb.predict(row["X_base"])[0]), 0.0))
    mae_hold_base = np.mean(np.abs(np.array(preds_hold_base) - hold_set["actual_m3_per_day"].values))

    final_rows.append(dict(horizon=h, n_fit=len(fit_set), n_holdout=len(hold_set),
                            chosen_pct=best_pct, chosen_threshold_mm=thresh,
                            mae_holdout_base_no_feat=mae_hold_base,
                            mae_holdout_with_binary_feat=mae_hold_with_feat,
                            improvement=mae_hold_base - mae_hold_with_feat))
    print(f"h{h}: chosen_pct={best_pct} thresh={thresh:.1f}mm | HONEST holdout(n={len(hold_set)}): "
          f"base={mae_hold_base:.0f}  with_binary_feat={mae_hold_with_feat:.0f}  "
          f"{'IMPROVED' if mae_hold_with_feat < mae_hold_base else 'worse'}")

pd.DataFrame(final_rows).to_csv(EXP / "binary_feature_honest_holdout_results.csv", index=False)
print("\nsaved binary_feature_honest_holdout_results.csv")
