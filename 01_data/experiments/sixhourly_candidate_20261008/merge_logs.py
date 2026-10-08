"""รวม candidate_predictions_log.csv จากหลายเครื่อง -> candidate_predictions_log.csv (สำรองของเดิมเป็น .bak)
ใช้: python merge_logs.py <โฟลเดอร์ Drive หรือ log เครื่องอื่น.csv> [...]
กฎ: คีย์ = issued_at (เวลา mark) ถ้าซ้ำ เก็บแถวที่ imerg_ok=1 ก่อน แล้วเก็บแถว run_at เก่าสุด"""
import sys, os, shutil, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__));LOG=os.path.join(HERE,"candidate_predictions_log.csv")
import glob
fs=([LOG] if os.path.exists(LOG) else [])
for a in sys.argv[1:]:  # รับไฟล์ หรือโฟลเดอร์ (จะอ่าน candidate_log_*.csv ทั้งหมด)
    fs+=sorted(glob.glob(os.path.join(a,"candidate_log_*.csv"))) if os.path.isdir(a) else [a]
if len(fs)<2: sys.exit("ต้องมีอย่างน้อย 2 ไฟล์ (ของเครื่องนี้ + ไฟล์จากเครื่องอื่น)")
d=pd.concat([pd.read_csv(f).assign(_src=os.path.basename(f)) for f in fs],ignore_index=True)
key=["issued_at"]  # 1 แถวต่อ mark
d["_i"]=d.get("imerg_ok",0).fillna(0).astype(int);d["_t"]=pd.to_datetime(d["run_at"])
d=d.sort_values(["_i","_t"],ascending=[False,True]).drop_duplicates(key,keep="first")
if os.path.exists(LOG): shutil.copy(LOG,LOG+".bak")
d.drop(columns=["_src","_i","_t"]).sort_values(key).to_csv(LOG,index=False)
print(f"รวม {len(fs)} ไฟล์ -> {len(d)} แถว (คีย์={key})")
