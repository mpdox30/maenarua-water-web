# Retrain รายวัน ด้วย Q_in สูตร spill ใหม่ (offset 0) — experiment, ไม่แตะ production
- 01_build_dataset.py: ใช้ Q_in จาก ledger (offset 0) แทน Q_in เดิมใน Training_Values_Nofct_7day_Extended_lagfeat.csv, สร้าง lag1/2 และ y1..y7 ใหม่ (393 แถว, 266 แถวเปลี่ยน >1 m3, 4 แถวต้นเดือน มิ.ย. 2025 fallback สูตรเก่า). Q รวม 44.4M → 33.5M m3.
- 02_compare.py: expanding-window walk-forward 8 folds, hyperparam production, ไม่รวม rain-forecast feature/bias correction. ประเมินบน target ใหม่ทั้งหมด.
- ผล (cv_summary.csv): B (เทรนข้อมูลใหม่) ≈ A (เทรนข้อมูลเก่า) ทุก horizon ยกเว้น H3 ที่ MAE ดีขึ้น (23.2k→18.5k); ทั้งคู่ใกล้เคียง persistence (H1–H2 persistence ดีกว่าเล็กน้อย; H4–H7 โมเดลดีกว่า persistence เล็กน้อย).
- สรุป: retrain ไม่ได้ทำให้แม่นขึ้นมาก ประโยชน์หลักคือสูตรสอดคล้องกัน. ยังต้อง refit bias correction H3–H7 + threshold rain-forecast ก่อนใช้จริง.

## รอบ 2: rain-forecast feature + bias correction (03_candidate_rainfeat_bias.py, cv_candidate_summary.csv)
threshold = p80/p30/p80 ของ train แต่ละ fold, bias = mean residual ของ fold ก่อนหน้า (out-of-fold)
- Rain-forecast binary: ดีขึ้นเฉพาะ H6 (MAE 31.7k→29.2k, NSE .259→.293); H3 และ H7 แย่ลง (H7 33.6k→36.1k)
- Bias correction (mean): ไม่ช่วยชัดเจน (H3/H4 แย่ลง, H5/H7 ดีขึ้นเล็กน้อยใน MAE แต่ NSE ลด) — ข้อมูลใหม่ bias ลดลงเพราะ spill ไม่ถูกประเมินเกิน
- ข้อเสนอสำหรับ retrain จริง: ใช้ 12 ฟีเจอร์พื้นฐานทุก horizon, rain-forecast เฉพาะ H6 (ต้องยืนยันด้วย holdout จริง), ยกเลิก bias correction ของ H3–H7 หรือ refit ด้วย live log หลัง deploy
- ข้อจำกัด: 393 แถว / 8 fold, ผลต่างระหว่างตัวเลือกอยู่ในระดับ noise ของตัวอย่างพายุไม่กี่ลูก
