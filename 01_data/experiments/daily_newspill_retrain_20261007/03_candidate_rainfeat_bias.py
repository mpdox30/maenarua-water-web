# -*- coding: utf-8 -*-
"""Candidate (experiment only): ฟีเจอร์ rain-forecast binary (H3/H6/H7) + bias correction (H3-H7) refit บนข้อมูลสูตรใหม่
threshold = percentile ของ cum forecast ในช่วง train ของแต่ละ fold (p80/p30/p80 เหมือนเดิม) ; bias = mean residual ของ out-of-fold fold ก่อนหน้า"""
import os, json, joblib, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"02_compare.py"),encoding="utf-8").read().split("folds=")[0])
ARC=f"{M}/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907/rain_forecast_archive_raw.csv"
a=pd.read_csv(ARC,parse_dates=["issue_date","forecast_date"]).pivot_table(index="issue_date",columns="lead_day",values="precipitation_sum_mm")
BIN={3:80,6:30,7:80}
for h in BIN: new[f"cum{h}"]=new.Date.map(a[[c for c in a.columns if c<=h]].sum(axis=1,min_count=h))
print("rain-fcst coverage",{h:int(new[f'cum{h}'].notna().sum()) for h in BIN})
folds=[(150,180),(180,210),(210,240),(240,270),(270,300),(300,330),(330,360),(360,393)]
Q="Q_in_t (m3/day)";rows=[];bias_hist={h:[] for h in range(1,8)}
for h in range(1,8):
    yc=f"y{h}=Q_in_t+{h} (m3/day)";res_prev=[]
    for te,tend in folds:
        d=new.iloc[:te-h];d=d[d[yc].notna()&d["Qin_lag2 (m3/day)"].notna()]
        t=new.iloc[te:tend];t=t[t[yc].notna()]
        if len(t)==0:continue
        variants={"base":(FEATS,d,t)}
        if h in BIN:
            c=f"cum{h}";dd=d.dropna(subset=[c]);th=np.percentile(dd[c],BIN[h])
            dd=dd.assign(b=(dd[c]>th).astype(float));tt=t.assign(b=(t[c]>th).astype(float)).fillna({"b":0.0})
            variants["rainfeat"]=(FEATS+["b"],dd,tt)
        for tag,(F,dtr,tte) in variants.items():
            m=fit(dtr[F].values,(dtr[yc]-dtr[Q]).values,P[h])
            p=np.clip(tte[Q].values+m.predict(tte[F].values),0,None)
            bc=np.mean(res_prev) if (h>=3 and len(res_prev)) else 0.0
            pb=np.clip(p-bc,0,None)
            for nm,pp in ((tag,p),(tag+"+bias",pb)):
                rows.append(pd.DataFrame(dict(h=h,tag=nm,Date=tte.Date.values,obs=tte[yc].values,pred=pp)))
            if tag==("rainfeat" if h in BIN else "base"): res_prev+=list(p-tte[yc].values)
    # per-fold residual for bias uses all prior folds (accumulated above)
R=pd.concat(rows);R.to_csv(f"{HERE}/cv_candidate_predictions.csv",index=False)
S=R.groupby(["h","tag"]).apply(lambda g:pd.Series(dict(n=len(g),MAE=(g.obs-g.pred).abs().mean(),NSE=nse(g.obs.values,g.pred.values)))).reset_index()
S.to_csv(f"{HERE}/cv_candidate_summary.csv",index=False)
print(S.pivot(index="h",columns="tag",values=["MAE","NSE"]).round(3).to_string())
