# -*- coding: utf-8 -*-
"""เทรน candidate ชุดสุดท้าย (CANDIDATE ONLY, ไม่ deploy): ฟีเจอร์พื้นฐาน 12 ตัวทุก horizon, H6 + rain-forecast binary (p30), ไม่มี bias correction"""
import os, json, joblib, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"02_compare.py"),encoding="utf-8").read().split("folds=")[0])
ARC=f"{M}/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907/rain_forecast_archive_raw.csv"
a=pd.read_csv(ARC,parse_dates=["issue_date","forecast_date"]).pivot_table(index="issue_date",columns="lead_day",values="precipitation_sum_mm")
new["cum6"]=new.Date.map(a[[c for c in a.columns if c<=6]].sum(axis=1,min_count=6))
Q="Q_in_t (m3/day)";models={};meta={"horizons":{},"dataset":"Training_Values_newspill_offset0_20261007.csv","bias_correction":None}
for h in range(1,8):
    yc=f"y{h}=Q_in_t+{h} (m3/day)";F=list(FEATS);d=new[new[yc].notna()&new["Qin_lag2 (m3/day)"].notna()].copy();th=None
    if h==6:
        th=float(np.percentile(d["cum6"].dropna(),30));d["b"]=(d["cum6"]>th).astype(float);F=F+["b"]
    m=fit(d[F].values,(d[yc]-d[Q]).values,P[h]);models[h]=m
    meta["horizons"][str(h)]=dict(features=F,tree_count=int(m.tree_count_),n_train_rows=len(d),rain_forecast_threshold_mm=th)
    print(h,len(F),m.tree_count_,len(d),th)
joblib.dump(models,f"{HERE}/candidate_regressors_newspill.pkl")
meta["note"]="CANDIDATE ONLY -- เทรนด้วย Q_in สูตร spill ใหม่ (offset 0). H6 ใช้ binary rain-forecast (Rain_fcst_cum_h6 > threshold). ไม่มี bias correction. ยังไม่ deploy"
json.dump(meta,open(f"{HERE}/candidate_metadata_newspill.json","w",encoding="utf-8"),indent=2,ensure_ascii=False)
# sanity: in-sample predict ล่าสุด
last=new.dropna(subset=["Qin_lag2 (m3/day)"]).iloc[-1]
print("last",last.Date.date(),{h:round(float(max(0,last[Q]+models[h].predict(pd.DataFrame([last])[meta['horizons'][str(h)]['features']].assign(**({'b':float(last['cum6']>meta['horizons']['6']['rain_forecast_threshold_mm'])} if h==6 else {})).values)[0]))) for h in range(1,8)})
