# -*- coding: utf-8 -*-
"""ให้คะแนน candidate_predictions_log.csv เทียบ persistence (NSE หลัก + MAE) ต่อ horizon ; ถ้ามี shadow log เดิม (โมเดล GBM) ก็เทียบด้วย
ค่าจริง = Q_in ที่สร้างใหม่จาก raw (สูตรเดียวกับตอนทำนาย) ; ให้คะแนนเฉพาะ mark ที่เป้าหมายผ่านไปแล้ว ; ปลอดภัยที่จะรันซ้ำ
ผลลัพธ์: candidate_scoring_report.csv  (n น้อยมากช่วงแรก -- อย่าสรุปก่อนมี >=60 mark ต่อ horizon และมีพายุอย่างน้อย 1-2 ลูก)"""
import os, sys, numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,os.path.join(HERE,"..","sixhourly_refresh_20260918"))
import shadow_predict as sp
LOG=os.path.join(HERE,"candidate_predictions_log.csv");OLD=os.path.join(HERE,"..","sixhourly_refresh_20260918","shadow_predictions_log.csv")
def nse(o,p): o=np.asarray(o,float);p=np.asarray(p,float);d=((o-o.mean())**2).sum();return float("nan") if d<1e-9 else float(1-((o-p)**2).sum()/d)
def main():
    if not os.path.exists(LOG): print("ยังไม่มี log");return
    log=pd.read_csv(LOG,parse_dates=["issued_at"]);act={r["Datetime"]:r["Q_in_t (m3/6h)"] for r in sp.build_6hourly_rows()}
    old=pd.read_csv(OLD,parse_dates=["issued_at"]) if os.path.exists(OLD) else None;res=[]
    for h in range(1,13):
        rec=[]
        for _,r in log.iterrows():
            a=act.get(pd.Timestamp(r[f"h{h}_target_datetime"]).to_pydatetime())
            if a is None: continue
            o={"issued_at":r.issued_at,"obs":a,"persist":r.persistence_qin_now,"clim_pers":r[f"h{h}_clim_pers"],"cand_norain":r[f"h{h}_cand_norain"],"cand_imerg":r[f"h{h}_cand_imerg"]}
            if old is not None:
                m=old[old.issued_at==r.issued_at]
                if len(m): o["gbm_shadow"]=m.iloc[0][f"h{h}_pred_qin"]
            rec.append(o)
        if not rec: continue
        d=pd.DataFrame(rec);row={"h":h,"n":len(d)}
        for k in ("persist","clim_pers","cand_norain","cand_imerg","gbm_shadow"):
            if k in d and d[k].notna().sum()>=5:
                dd=d.dropna(subset=[k]);row[f"{k}_nse"]=nse(dd.obs,dd[k]);row[f"{k}_mae"]=float(np.abs(dd.obs-dd[k]).mean());row[f"{k}_n"]=len(dd)
        res.append(row)
    R=pd.DataFrame(res);R.to_csv(os.path.join(HERE,"candidate_scoring_report.csv"),index=False);pd.set_option("display.width",250);print(R.round(3).to_string(index=False))
if __name__=="__main__": main()
