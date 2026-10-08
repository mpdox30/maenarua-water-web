# -*- coding: utf-8 -*-
"""Shadow test ของรุ่นผู้สมัคร (recession + ฝนเชิงเส้น ผสม 50/50 กับ persistence+รูปแบบรายวัน) -- ไม่แตะ production/shadow เดิม
ใช้ฟังก์ชันสร้างแถว 6 ชม. จาก ../sixhourly_refresh_20260918/shadow_predict.py (Q_in/ฝนชุดเดียวกับ shadow เดิม) แล้วทำนายด้วย candidate_coefs.json
ฝน IMERG (Early/Late) มาจาก imerg_early_halfhourly_main1.csv (fetch_imerg_early_earthaccess.py) ; ถ้า IMERG ไม่ครบ 6 บล็อกที่ต้องใช้ -> cand_imerg เป็นค่าว่าง (cand_norain ยังบันทึกปกติ)
Log: candidate_predictions_log.csv (idempotent, backfill ทุก mark ที่ยังไม่บันทึก ตั้งแต่ DEPLOY_START_MARK)
usage: python shadow_candidate.py   (env: IMERG_CSV=<path>, CAND_DEPLOY_START=2026-10-08T07:00 เพื่อทดสอบย้อนหลัง)"""
import os, sys, json, csv
from datetime import datetime, timedelta
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
SP_DIR=os.path.join(HERE,"..","sixhourly_refresh_20260918");sys.path.insert(0,SP_DIR)
import shadow_predict as sp
COEFS=json.load(open(os.path.join(HERE,"candidate_coefs.json"),encoding="utf-8"))
LOG=os.path.join(HERE,os.environ.get("CAND_LOG","candidate_predictions_log.csv"))
IMERG_CSV=os.environ.get("IMERG_CSV",os.path.join(HERE,"imerg_early_halfhourly_main1.csv"))
DEPLOY=datetime.fromisoformat(os.environ.get("CAND_DEPLOY_START","2026-10-08T13:00:00"))   # mark แรกที่จะนับ (หลังล็อกรุ่น)
WAIT_H=float(os.environ.get("CAND_WAIT_H","14"))   # รอ IMERG ได้นานสุด (Late หน่วง ~14 ชม.)
K=COEFS["K"];API_MED=COEFS["api_med"];HR=COEFS["hours"]
def imerg_series():
    if not os.path.exists(IMERG_CSV): return None
    d=pd.read_csv(IMERG_CSV,parse_dates=["end_utc"]);d["end_l"]=d.end_utc+pd.Timedelta(hours=7);return d.set_index("end_l").rain_mm_30min.sort_index()
def imerg_block(s,t):
    if s is None: return np.nan
    w=s[(s.index>t-timedelta(hours=6))&(s.index<=t)];return float(w.sum()) if len(w)>=11 else np.nan
def hr_dummies(t): return [1.0 if t.hour==h else 0.0 for h in HR]
def predict_row(h,q,qm1,iblocks,api,t,use_imerg):
    c=COEFS["horizons"][str(h)];hd=hr_dummies(t)
    lin_ar=float(np.dot([q,qm1]+hd,c["lin_ar"][:2]+c["lin_ar"][2:]))
    clim=float(c["clim"][str(t.hour)]);cp=q+clim
    cand_norain=max(0.5*lin_ar+0.5*cp,0.0)
    cand_imerg=np.nan
    if use_imerg:
        ia=[v*(api/API_MED) for v in iblocks]
        lin_im=float(np.dot([q,qm1]+iblocks+ia+hd,c["lin_imerg_api"]));cand_imerg=max(0.5*lin_im+0.5*cp,0.0)
    return max(cp,0.0),cand_norain,cand_imerg
def main():
    print(f"[shadow_candidate] {datetime.now().isoformat()}")
    rows=sp.add_segment_lag_feats(sp.build_6hourly_rows())
    rows=sorted(rows,key=lambda r:r["Datetime"])
    # segment ต่อเนื่อง 6 ชม. -> ดึงฝน/IMERG ย้อน K บล็อกเฉพาะภายใน segment
    seg=0;prev=None
    for r in rows:
        if prev is not None and (r["Datetime"]-prev)!=timedelta(hours=6): seg+=1
        r["_seg"]=seg;prev=r["Datetime"]
    s=imerg_series();done=set()
    if os.path.exists(LOG):
        ex=pd.read_csv(LOG)
        if not ex.empty: done=set(ex.issued_at.astype(str))
    out=[]
    for i,r in enumerate(rows):
        t=r["Datetime"]
        if t<DEPLOY or t.isoformat() in done or r.get("Qin_lag1 (m3/6h)") is None: continue
        q=r["Q_in_t (m3/6h)"];qm1=r["Qin_lag1 (m3/6h)"];api=r["API_t (mm)"]
        ib=[imerg_block(s,t-timedelta(hours=6*k)) for k in range(K)]
        use_im=not any(np.isnan(v) for v in ib)
        # IMERG Early หน่วง ~4+ ชม.: ถ้ายังไม่มีบล็อกล่าสุดและ mark ยังใหม่ (<WAIT_H ชม.) รอรอบถัดไป ไม่บันทึก (กันบันทึกแบบไม่มี IMERG ทั้งที่แค่ยังมาไม่ถึง)
        if (not use_im) and s is not None and (datetime.now()-t)<timedelta(hours=WAIT_H): continue
        row={"issued_at":t.isoformat(),"run_at":datetime.now().isoformat(),"persistence_qin_now":round(q,2),"imerg_ok":int(use_im),"imerg_blocks":";".join("" if np.isnan(v) else f"{v:.3f}" for v in ib)}
        for h in range(1,13):
            cp,cn,ci=predict_row(h,q,qm1,ib if use_im else [0.0]*K,api,t,use_im)
            row[f"h{h}_target_datetime"]=(t+timedelta(hours=6*h)).isoformat();row[f"h{h}_clim_pers"]=round(cp,2);row[f"h{h}_cand_norain"]=round(cn,2);row[f"h{h}_cand_imerg"]="" if np.isnan(ci) else round(ci,2)
        out.append(row)
    if not out: print("[shadow_candidate] ไม่มี mark ใหม่ให้บันทึก");return
    new=not os.path.exists(LOG)
    with open(LOG,"a",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()))
        if new: w.writeheader()
        w.writerows(out)
    print(f"[shadow_candidate] บันทึก {len(out)} แถว ถึง {out[-1]['issued_at']} (imerg_ok={sum(r['imerg_ok'] for r in out)}/{len(out)}) -> {LOG}")
if __name__=="__main__": main()
