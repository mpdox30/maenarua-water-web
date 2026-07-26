"""
ทดสอบโมเดลที่เพิ่ง deploy ใหม่ (2026-07-26: direct delta-regression per horizon, ไม่มี stage1
hurdle แล้ว -- CatBoost ทุก horizon, เทรนบน Training_Values_Nofct_7day_Extended_lagfeat.csv ซึ่ง
เพิ่ม Qin_lag1/Qin_lag2/Rain_roll3/Rain_roll5/Rain_roll7 ต่อจาก 7 feature เดิม) บนเครื่อง
production จริง ก่อนเชื่อผล 100% -- ใช้ข้อมูลจริง 5 แถวล่าสุด จำลอง logic เดียวกับที่
_ri_run_prediction() ใน data_pipeline.py ใช้จริง

หมายเหตุ: stage1_classifiers.pkl / stage1_thresholds.pkl / deployment_stage2_regressors.pkl
ที่ยังอยู่ในโฟลเดอร์นี้เป็นไฟล์จากสถาปัตยกรรมเดิม (hurdle) เก็บไว้เผื่อ rollback เท่านั้น --
ไม่ได้ถูกโหลดใช้งานอีกต่อไป (ดู model_metadata.json.bak_before_no_stage1_lagfeat_20260726
สำหรับ metadata ของรุ่นก่อนหน้า)

วิธีรัน (จากเครื่อง Windows, ในโฟลเดอร์นี้หรือ repo root ก็ได้):
    python "01_data/scripts and code/Reservoir_inflow/active/test_predict_production.py"

ไม่แก้ไฟล์ใดๆ ทั้งสิ้น แค่โหลด + predict แล้ว print ผลออกมาดู
"""
import os
import json
import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))  # .../Reservoir_inflow/active

QIN_COL = "Q_in_t (m3/day)"

print(f"กำลังโหลดโมเดลจาก: {HERE}\n")
regressors = joblib.load(os.path.join(HERE, "deployment_regressors_no_stage1.pkl"))
metadata = json.load(open(os.path.join(HERE, "model_metadata.json"), encoding="utf-8"))
targets = metadata["targets"]
feature_cols = metadata["feature_cols"]

print("โหลดสำเร็จ:")
print(f"  regressors: {len(regressors)} horizon (ไม่มี stage1 แล้ว)")
print(f"  feature_cols: {feature_cols}\n")

# ใช้ 5 แถวล่าสุดจาก Extended_lagfeat.csv (ข้อมูลจริงล่าสุดที่มี) เป็น input ทดสอบ
df = pd.read_csv(os.path.join(HERE, "Training_Values_Nofct_7day_Extended_lagfeat.csv"))
sample = df.dropna(subset=feature_cols).tail(5).reset_index(drop=True)

print(f"ทดสอบ predict บนข้อมูลจริง {len(sample)} แถวล่าสุด:")
print(sample[["Date"] + feature_cols].to_string(index=False))
print()

any_error = False
for _, row in sample.iterrows():
    X = pd.DataFrame([row[feature_cols].to_dict()])
    current_qin = float(row[QIN_COL])
    print(f"--- วันที่ {row['Date']} (Q_in_t ปัจจุบัน = {current_qin:,.1f}) ---")
    for h in range(1, 8):
        tcol = targets[h - 1]
        try:
            delta = float(regressors[h].predict(X)[0])
            prediction = max(current_qin + delta, 0.0)
            status = "OK" if np.isfinite(prediction) and prediction >= 0 else "!! ผิดปกติ !!"
            print(f"  H{h}: delta={delta:>12,.1f} -> pred={prediction:>12,.1f}  [{status}]")
        except Exception as e:
            any_error = True
            print(f"  H{h}: !! ERROR: {e}")
    print()

if any_error:
    print("พบ ERROR ในบางจุด — อย่าเพิ่งไว้ใจผลลัพธ์ ลองแจ้งข้อความ error กลับมาดูเพิ่มเติม")
else:
    print("ทุก horizon ทำนายได้ไม่มี error ค่าทั้งหมดเป็นตัวเลขปกติ (ไม่ติดลบ ไม่ NaN/Inf)")
    print("ถือว่าโมเดลใหม่ใช้งานได้บนเครื่องนี้แล้ว")
