import json
import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor
from sklearn.model_selection import TimeSeriesSplit

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
FEATS_BASE = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
              '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
              'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']

train = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"]).sort_values("Date")
arc = pd.read_csv("rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"])

# pivot archive: issue_date -> lead1..lead7 forecast precip
piv = arc.pivot_table(index="issue_date", columns="lead_day", values="precipitation_sum_mm")
piv.columns = [f"fcst_lead{c}_mm" for c in piv.columns]

df = train.merge(piv, left_on="Date", right_index=True, how="left")

# cumulative forward rain forecast feature PER HORIZON: sum of lead1..leadH (strictly future, excludes lead0=today)
for h in range(1, 8):
    lead_cols = [f"fcst_lead{i}_mm" for i in range(1, h+1)]
    df[f"Rain_fcst_cum_h{h} (mm)"] = df[lead_cols].sum(axis=1)

DEPLOY_PARAMS = {
    1: dict(iterations=650, depth=6, learning_rate=0.0109312751880508, l2_leaf_reg=23.808543547006124,
            min_data_in_leaf=8, subsample=0.8332116765879214, rsm=0.7890628480631008, random_strength=1.07161216899677),
    2: dict(iterations=300, depth=5, learning_rate=0.0146991485489077, l2_leaf_reg=1.7430504177815451,
            min_data_in_leaf=24, subsample=0.914033992242307, rsm=0.6212741213218833, random_strength=1.9674909492695445),
    3: dict(iterations=300, depth=5, learning_rate=0.0159859205807381, l2_leaf_reg=4.339666832543908,
            min_data_in_leaf=37, subsample=0.986523802644266, rsm=0.8127877215251221, random_strength=2.57649494325228),
    4: dict(iterations=300, depth=3, learning_rate=0.0109387154307568, l2_leaf_reg=3.810029124004568,
            min_data_in_leaf=36, subsample=0.4063769521841512, rsm=0.9913749176499462, random_strength=2.699726957831789),
    5: dict(iterations=300, depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472,
            min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372, random_strength=0.217429400040442),
    6: dict(iterations=300, depth=2, learning_rate=0.0136765950369614, l2_leaf_reg=4.382716203014211,
            min_data_in_leaf=29, subsample=0.7105210344032551, rsm=0.8290243458181864, random_strength=1.9867898992450308),
    7: dict(iterations=300, depth=2, learning_rate=0.0119080907879342, l2_leaf_reg=1.426422588105843,
            min_data_in_leaf=18, subsample=0.4317495679086314, rsm=0.7638703770649338, random_strength=1.0054966332229271),
}
# hyperparams for h5 improved (from earlier experiment) -- to test "new feature + fixed h5" combo too
H5_IMPROVED = dict(iterations=300, depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472,
                    min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372,
                    random_strength=1.0)

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

tscv = TimeSeriesSplit(n_splits=5)

def cv_eval(sub, feats, target_col, params, early_stop=False, od_wait=30, seed=42):
    X_all = sub[feats].values
    qin_all = sub["Q_in_t (m3/day)"].values
    y_all = sub[target_col].values
    delta_all = y_all - qin_all
    fold_nse = []
    for tr_idx, va_idx in tscv.split(X_all):
        Xtr, Xva = X_all[tr_idx], X_all[va_idx]
        dtr, dva = delta_all[tr_idx], delta_all[va_idx]
        qva, yva = qin_all[va_idx], y_all[va_idx]
        p = dict(params); p.update(loss_function="MAE", random_seed=seed, verbose=False)
        if early_stop:
            p.update(od_type="Iter", od_wait=od_wait)
        m = CatBoostRegressor(**p)
        if early_stop:
            m.fit(Xtr, dtr, eval_set=(Xva, dva), use_best_model=True)
        else:
            m.fit(Xtr, dtr)
        pred = np.maximum(qva + m.predict(Xva), 0.0)
        fold_nse.append(nse(yva, pred))
    return fold_nse, float(np.mean(fold_nse))

results = []
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    fcst_col = f"Rain_fcst_cum_h{h} (mm)"
    feats_with = FEATS_BASE + [fcst_col]
    sub = df.dropna(subset=FEATS_BASE + [fcst_col, target_col]).reset_index(drop=True)

    params = DEPLOY_PARAMS[h]
    folds_base, mean_base = cv_eval(sub, FEATS_BASE, target_col, params, early_stop=False)
    folds_with, mean_with = cv_eval(sub, feats_with, target_col, params, early_stop=False)

    row = dict(horizon=h, n=len(sub), nse_base=mean_base, nse_with_fcst=mean_with,
               delta=mean_with - mean_base)

    if h == 5:
        folds_b2, mean_b2 = cv_eval(sub, FEATS_BASE, target_col, H5_IMPROVED, early_stop=True)
        folds_w2, mean_w2 = cv_eval(sub, feats_with, target_col, H5_IMPROVED, early_stop=True)
        row["nse_h5improved_base"] = mean_b2
        row["nse_h5improved_with_fcst"] = mean_w2

    results.append(row)
    print(f"h{h}: n={len(sub):3d}  base={mean_base:+.4f}  with_fcst={mean_with:+.4f}  "
          f"delta={row['delta']:+.4f}" + (f"  | h5improved base={row.get('nse_h5improved_base'):+.4f} "
          f"with_fcst={row.get('nse_h5improved_with_fcst'):+.4f}" if h==5 else ""))

rep = pd.DataFrame(results)
rep.to_csv("cv_comparison_rain_forecast_feature.csv", index=False)
df.to_csv("training_with_rain_forecast_features.csv", index=False)
print("\nsaved cv_comparison_rain_forecast_feature.csv, training_with_rain_forecast_features.csv")
