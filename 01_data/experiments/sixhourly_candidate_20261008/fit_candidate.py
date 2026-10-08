# -*- coding: utf-8 -*-
"""ฟิตรุ่นผู้สมัคร (ล็อกล่วงหน้าก่อน shadow test): ต่อ horizon h=1..12 —
  lin_ar        : y = a*Q_t + b*Q_{t-1} + c(hr)                         (ไม่ใช้ฝน)
  lin_imerg_api : y = a*Q_t + b*Q_{t-1} + sum_k w_k*I_{t-k} + sum_k v_k*I_{t-k}*API_t/API_med + c(hr)   (IMERG 6 บล็อก, w,v>=0)
  clim          : ส่วนต่างเฉลี่ย (y-Q) ตามชั่วโมง mark จากแถวไม่มีฝน 3 บล็อก
  ผู้สมัคร = 0.5*lin + 0.5*(Q_t + clim)  (cand_norain ใช้ lin_ar ; cand_imerg ใช้ lin_imerg_api) -- น้ำหนัก 0.5 ล็อกตาม 08_linear_rr.py ไม่ปรับจูน
ข้อมูลฝึก: Training_6hourly_full_delta017.csv ทั้งหมด (ถึง 7 ต.ค. 2026) + imerg_halfhourly_main1.csv (GEE Final)
ผลลัพธ์: candidate_coefs.json  (ห้ามแก้ภายหลังระหว่าง shadow test ; ถ้าจะ refit ให้ตั้งชื่อเวอร์ชันใหม่)"""
import os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from scipy.optimize import lsq_linear
HERE=os.path.dirname(os.path.abspath(__file__));M=os.environ.get("MNT","/sessions/busy-awesome-cerf/mnt")
EXP=f"{M}/maenaruea-water-web/01_data/experiments"
D=pd.read_csv(f"{EXP}/sixhourly_newspill_20261007/Training_6hourly_full_delta017.csv",parse_dates=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
h30=pd.read_csv(f"{EXP}/sixhourly_beat_persistence_20261008/imerg_halfhourly_main1.csv",parse_dates=["end_utc"]);h30["end_l"]=h30.end_utc+pd.Timedelta(hours=7);s=h30.set_index("end_l").rain_mm_30min.sort_index()
def blk(t):
    w=s[(s.index>t-pd.Timedelta(hours=6))&(s.index<=t)];return w.sum() if len(w)>=11 else np.nan
D["im"]=[blk(t) for t in D.Datetime];D["hr"]=D.Datetime.dt.hour
Q="Q_in_t (m3/6h)";Qm1="Qin_lag1 (m3/6h)";G="Rain_obs_t (mm)";K=6;HR=[1,7,13,19]
for k in range(K): D[f"i{k}"]=D.im.shift(k)
API_MED=float(D["API_t (mm)"].median())
for k in range(K): D[f"ia{k}"]=D[f"i{k}"]*(D["API_t (mm)"]/API_MED)
for k in HR: D[f"hh{k}"]=(D.hr==k).astype(float)
IC=[f"i{k}" for k in range(K)];IA=[f"ia{k}" for k in range(K)];HC=[f"hh{k}" for k in HR]
r=D[G];D["dry"]=(r<=0.5)&(r.shift(1)<=0.5)&(r.shift(2)<=0.5)
def fit(df,y,rc):
    X=df[[Q,Qm1]+rc+HC].values.astype(float);lo=[-0.5,-0.5]+[0.0]*len(rc)+[-np.inf]*4;hi=[1.5,1.5]+[np.inf]*len(rc)+[np.inf]*4
    return lsq_linear(X,df[y].values,bounds=(lo,hi),method="trf",max_iter=300).x.tolist()
out={"api_med":API_MED,"K":K,"hours":HR,"rain_blocks_imerg":K,"trained_through":str(D.Datetime.max()),"n_rows_total":int(len(D)),"horizons":{}}
for h in range(1,13):
    y=f"y{h}=Q_in_t+{h} (m3/6h)";base=D[D[[Q,Qm1,y]].notna().all(axis=1)]
    ar=fit(base,y,[]);im_df=base.dropna(subset=IC+IA);ia=fit(im_df,y,IC+IA)
    dd=base[base.dry];prof=(dd[y]-dd[Q]).groupby(dd.hr).mean();clim={str(k):float(prof.get(k,0.0)) for k in HR}
    out["horizons"][str(h)]={"n_ar":int(len(base)),"n_imerg":int(len(im_df)),"lin_ar":ar,"lin_imerg_api":ia,"clim":clim}
    print(h,"n",len(base),len(im_df),"a,b(ar)",np.round(ar[:2],3),"a,b(imerg)",np.round(ia[:2],3),"sum w",round(sum(ia[2:2+K]),3),"sum v",round(sum(ia[2+K:2+2*K]),3))
json.dump(out,open(f"{HERE}/candidate_coefs.json","w"),indent=1);print("saved candidate_coefs.json")
