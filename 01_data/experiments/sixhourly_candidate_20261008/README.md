# รุ่นผู้สมัคร 6h (shadow เท่านั้น ไม่แตะ production) — 2026-10-08
ที่มา: ../sixhourly_beat_persistence_20261008/FINDINGS.md (ขั้น 6). รุ่น = 0.5*(โมเดลเชิงเส้น recession+ฝน) + 0.5*(persistence + ส่วนต่างรายวัน) ; น้ำหนัก 0.5 ล็อกแล้ว ไม่ปรับจูน
- candidate_coefs.json : สัมประสิทธิ์ล็อกจาก fit_candidate.py (ข้อมูลถึง 7 ต.ค. 2026 ; รวมแถว unverified) — อย่าแก้ระหว่าง shadow test
- cand_norain : ไม่ใช้ฝน (ใช้ได้ทันที) ; cand_imerg : ใช้ IMERG Late/Early 6 บล็อก (ต้องมี imerg_early_halfhourly_main1.csv)
- เริ่มนับ mark: 2026-10-08 13:00 (CAND_DEPLOY_START) ; log = candidate_predictions_log.csv ; คะแนน = score_candidate.py -> candidate_scoring_report.csv
ข้อควรรู้: (1) สัมประสิทธิ์ IMERG เทรนด้วยรุ่น Final (GEE) แต่ใช้สดด้วย Early/Late ซึ่งมีความเอนเอียง/สัญญาณรบกวนต่างกัน ต้องดูใน shadow log ว่าไม่ทำให้แย่ลง (2) IMERG Early หน่วง ~4+ ชม. (Late ~14 ชม.) ผลคือพยากรณ์ที่ใช้ IMERG ออกช้ากว่า mark ราว 5–15 ชม. (3) น้อยกว่า ~60 mark ต่อ horizon อย่าสรุป
## ติดตั้ง/รัน (Windows)
1. `.venv\Scripts\python.exe -m pip install earthaccess h5py` (geopandas/shapely มีอยู่แล้ว)
2. ตั้งบัญชี Earthdata: `setx EARTHDATA_USERNAME ...` และ `setx EARTHDATA_PASSWORD ...` (เปิด PowerShell ใหม่)
3. ทดสอบมือ: `python fetch_imerg_early_earthaccess.py` แล้ว `python shadow_candidate.py`
4. ตั้ง Task Scheduler ตามคอมเมนต์ใน run_candidate_shadow.bat (ไม่ซ้อนกับ MaeNaRua_Inflow_ShadowTest_6h เพราะใช้ log คนละไฟล์)
5. หลังสะสมข้อมูล: `python score_candidate.py`
สถานะการทดสอบ: shadow_candidate.py ทดสอบกับข้อมูล local ในช่วง 28 ก.ย.–8 ต.ค. (IMERG = ชุด Final) ผ่านครบ ; fetch_imerg_early_earthaccess.py ยังไม่เคยรันกับ Earthdata จริง (ไม่มีบัญชีใน sandbox)
