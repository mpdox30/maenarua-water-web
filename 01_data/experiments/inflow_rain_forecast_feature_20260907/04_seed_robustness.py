import pandas as pd, numpy as np
from pathlib import Path
from catboost import CatBoostRegressor
from sklearn.model_selection import TimeSeriesSplit

FEATS_BASE = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
              '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
              'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']

df = pd.read_csv("training_with_rain_forecast_features.csv", parse_dates=["Date"])

DEPLOY_PARAMS = {
    1: dict(iterations=650, depth=6, learning_rate=0.0109312751880508, l2_leaf_reg=23.808543547006124, min_data_in_leaf=8, subsample=0.8332116765879214, rsm=0.7890628480631008, random_strength=1.07161216899677),
    2: dict(iterations=300, depth=5, learning_rate=0.0146991485489077, l2_leaf_reg=1.7430504177815451, min_data_in_leaf=24, subsample=0.914033992242307, rsm=0.6212741213218833, random_strength=1.9674909492695445),
    3: dict(iterations=300, depth=5, learning_rate=0.0159859205807381, l2_leaf_reg=4.339666832543908, min_data_in_leaf=37, subsample=0.986523802644266, rsm=0.8127877215251221, random_strength=2.57649494325228),
    4: dict(iterations=300, depth=3, learning_rate=0.0109387154307568, l2_leaf_reg=3.810029124004568, min_data_in_leaf=36, subsample=0.4063769521841512, rsm=0.9913749176499462, random_strength=2.699726957831789),
    5: dict(iterations=300, depth=2, learning_rate=0.0121759578591452, l2_leaf_reg=31.27438558692472, min_data_in_leaf=25, subsample=0.9868547519916756, rsm=0.6502309452463372, random_strength=0.217429400040442),
    6: dict(iterations=300, depth=2, learning_rate=0.0136765950369614, l2_leaf_reg=4.382716203014211, min_data_in_leaf=29, subsample=0.7105210344032551, rsm=0.8290243458181864, random_strength=1.9867898992450308),
    7: dict(iterations=300, depth=2, learning_rate=0.0119080907879342, l2_leaf_reg=1.426422588105843, min_data_in_leaf=18, subsample=0.4317495679086314, rsm=0.7638703770649338, random_strength=1.0054966332229271),
}

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

tscv = TimeSeriesSplit(n_splits=5)

def cv_eval(sub, feats, target_col, params, seed):
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
        m = CatBoostRegressor(**p)
        m.fit(Xtr, dtr)
        pred = np.maximum(qva + m.predict(Xva), 0.0)
        fold_nse.append(nse(yva, pred))
    return float(np.mean(fold_nse))

SEEDS = [42, 7]
rows = []
for h in range(1, 8):
    target_col = f"y{h}=Q_in_t+{h} (m3/day)"
    fcst_col = f"Rain_fcst_cum_h{h} (mm)"
    feats_with = FEATS_BASE + [fcst_col]
    sub = df.dropna(subset=FEATS_BASE + [fcst_col, target_col]).reset_index(drop=True)
    params = DEPLOY_PARAMS[h]
    base_scores = [cv_eval(sub, FEATS_BASE, target_col, params, s) for s in SEEDS]
    with_scores = [cv_eval(sub, feats_with, target_col, params, s) for s in SEEDS]
    rows.append(dict(horizon=h, base_mean=np.mean(base_scores), base_std=np.std(base_scores),
                      with_mean=np.mean(with_scores), with_std=np.std(with_scores),
                      delta=np.mean(with_scores)-np.mean(base_scores)))
    print(f"h{h}: base={np.mean(base_scores):+.4f}(±{np.std(base_scores):.3f})  "
          f"with_fcst={np.mean(with_scores):+.4f}(±{np.std(with_scores):.3f})  "
          f"delta={np.mean(with_scores)-np.mean(base_scores):+.4f}")

pd.DataFrame(rows).to_csv("cv_comparison_seed_robust.csv", index=False)
print("\nsaved cv_comparison_seed_robust.csv")
