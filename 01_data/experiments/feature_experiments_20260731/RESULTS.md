# ผลทดลอง 3 feature ใหม่ (2026-07-31)

สถานะ: **เสร็จแล้ว ทำในโฟลเดอร์นี้ทั้งหมด ไม่แตะไฟล์ deploy ใน `01_data/scripts and code/Reservoir_inflow/active/`
เลย** (อ่าน `model_metadata.json` แบบ read-only เพื่อเอา tuned hyperparameter มาใช้ซ้ำเท่านั้น)

feature ที่ขอให้ลอง 3 ตัว: (1) อยู่ระหว่างปล่อยน้ำ (2) ระดับน้ำสูงสุดในรอบ 24 ชม. (3) ช่วงต่าง
สูงสุด-ต่ำสุดในวัน

## 1. is_release_active / release_rate_m3day

**ผล: ไม่มีผลต่าง (diff=0.0 ทุก horizon) — แต่เป็นเพราะข้อจำกัดของข้อมูล ไม่ใช่เพราะ feature ไม่มีประโยชน์**

รัน walk-forward CV เดียวกับที่ deploy จริง (TimeSeriesSplit 5-fold บน train block เดิม, ใช้
hyperparameter ที่ tune ไว้แล้วซ้ำ ไม่ re-tune) เทียบ baseline (12 feature เดิม) กับ +release feature:

| H | baseline NSE | +release NSE | diff |
|---|---|---|---|
| 1 | 0.4216 | 0.4216 | 0.0 |
| 2 | 0.2559 | 0.2559 | 0.0 |
| 3 | -0.0649 | -0.0649 | 0.0 |
| 4 | -0.2526 | -0.2526 | 0.0 |
| 5 | -0.2920 | -0.2920 | 0.0 |
| 6 | -0.3724 | -0.3724 | 0.0 |
| 7 | -0.5808 | -0.5808 | 0.0 |

**สาเหตุที่ diff=0 เป๊ะ**: release เพิ่งเริ่ม 2026-06-26 ส่วน training data มี 393 แถวย้อนไปถึง
2025-06-27 — ในบรรดา "train block" ของ walk-forward (271 แถวแรกตาม season-split เดิม) มีแค่ **4 แถว**
ที่ is_release_active=1 (ทั้งหมดอยู่ท้ายสุดของ block พอดี) โมเดลแทบไม่เห็น variation ของ feature นี้เลย
ในทุก fold เทรน จึงไม่ได้เรียนรู้อะไรจากมัน — **ไม่ใช่ว่า feature ไม่มีประโยชน์ แต่ข้อมูลปัจจุบันยังไม่พอ
ให้ทดสอบได้จริง** เพราะช่วง release ทั้งหมด (29 วัน) กระจุกอยู่ปลายสุดของ dataset พอดี ไม่ว่าจะ split
แบบไหน (walk-forward หรือ TimeSeriesSplit เต็มชุด) ก็จะไม่มี fold ไหนที่มีทั้ง train และ test ครอบคลุม
ช่วง release พร้อมกันได้เลยตามธรรมชาติของข้อมูลตอนนี้

**ข้อเสนอ**: เพิ่ม feature นี้เข้าไปใน live feature pipeline ตั้งแต่ตอนนี้ (คำนวณง่าย ไม่มีความเสี่ยง)
เพื่อให้สะสมวันที่มี label ครบไปเรื่อยๆ แล้วค่อยทดสอบใหม่อีกครั้งเมื่อผ่านไปอีกสัก 1-2 เดือน (หรือเมื่อ
release ปิดแล้วเปิดใหม่อีกรอบ จะเกิด contrast ให้โมเดลเรียนได้จริง)

## 2-3. daily_max_level_24h / daily_range_24h — อัปเดตหลังผู้ใช้ชี้ให้ดู "Raw Data_RES002 station.xlsx"

**รอบแรก** (diagnostic เท่านั้น จาก wide_log 22 วัน) ยังไม่พอ retrain — แต่ผู้ใช้ชี้ให้ดูไฟล์
`01_data/Reservoirs/inflow/Raw Data_RES002 station.xlsx` ซึ่งมีข้อมูล**รายชั่วโมงจริง 2025-06-26 ถึง
2026-06-27** (8,775 แถว ขาดแค่ 1 ช่วง 2 ชม. ตลอดทั้งปี) รวมกับ wide_log (10-31 ก.ค. 2569) ได้ช่วงข้อมูล
รายชั่วโมงต่อเนื่องครอบคลุม **386/393 วัน (96.4%) ของ training data ทั้งหมด** — ขาดแค่ 2026-06-28 ถึง
2026-07-09 (~12 วัน ที่ไม่มีทั้งสองแหล่ง) **พอทำ walk-forward CV จริงได้แล้ว**

**ผล walk-forward CV จริง (baseline 12 feature เดิม vs +max_level_24h/range_24h, hyperparameter
เดิมที่ tune ไว้แล้ว ไม่ re-tune ใหม่):**

| H | baseline NSE | +range_24h NSE | diff |
|---|---|---|---|
| 1 | 0.4216 | 0.3950 | -0.027 |
| 2 | 0.2559 | 0.1952 | -0.061 |
| 3 | -0.0649 | -0.1000 | -0.035 |
| 4 | -0.2526 | -0.2643 | -0.012 |
| 5 | -0.2920 | -0.2747 | +0.017 |
| 6 | -0.3724 | -0.4285 | -0.056 |
| 7 | -0.5808 | -0.4724 | **+0.108** |

**สรุปตรงไปตรงมา: ผลผสม ค่อนไปทางแย่ลง** — H1, H2, H3, H4, H6 แย่ลง (โดยเฉพาะ H2 -0.061) มีแค่ H5
(+0.017 เล็กน้อย) และ H7 (+0.108 ชัดเจน) ที่ดีขึ้น **ไม่ใช่ผลบวกชัดเจนแบบที่หวังไว้ตอนเห็น diagnostic
รอบแรก** แม้จะพิสูจน์แล้วว่า feature นี้ "เห็น" สัญญาณจริงที่ feature เดิมมองไม่เห็น (กรณี 30 ก.ค.) แต่พอ
ให้โมเดลลองใช้จริงกลับไม่ได้ช่วยเรียนรู้ดีขึ้นในภาพรวม

**ข้อควรระวังก่อนตัดสินใจปิดประตู feature นี้**: การทดสอบนี้ **ใช้ hyperparameter เดิมที่ tune ไว้สำหรับ
12 feature เดิม ไม่ได้ tune ใหม่ให้เข้ากับ feature ที่เพิ่มมา** (เจตนา — เพื่อแยกผลของ feature ออกจากผล
ของการค้นหา hyperparameter ใหม่ ตามที่ทีมงานรอบก่อนเคยตั้งข้อสังเกตไว้ใน README_findings.md) เป็นไปได้
ว่าถ้า re-tune เต็มรูปแบบ (Optuna ต่อ horizon) ผลอาจเปลี่ยน โดยเฉพาะ H1-H4 ที่ยังแย่ลงอยู่ — แต่ด้วย
ข้อมูล train block แค่ 271 แถว การค้นหา hyperparameter เพิ่มก็มีความเสี่ยง overfit เพิ่มเช่นกัน (บทเรียน
เดิมจากงานรอบก่อน)

## สรุปรวม

| feature | สถานะ validate | ผล |
|---|---|---|
| อยู่ระหว่างปล่อยน้ำ | validate ไม่ได้ (ข้อมูลไม่พอ — release กระจุกท้าย dataset) | ไม่มีผล (ไม่ใช่พิสูจน์ว่าไม่ดี) |
| ระดับน้ำสูงสุด 24 ชม. / ช่วงต่าง max-min | **validate ได้แล้ว (96.4% coverage)** | **ผสม ค่อนไปทางแย่ลง (H1-4,6 แย่ H5,7 ดีขึ้น)** |

**ข้อสรุป: ไม่แนะนำ deploy feature max/range ทับ 12 feature เดิมตอนนี้** ด้วย hyperparameter ปัจจุบัน
ผลไม่คุ้ม (แย่ลงมากกว่าดีขึ้น) ถ้าอยากใช้ประโยชน์จาก H5/H7 ที่ดีขึ้นจริง ต้องมีข้อมูลเพิ่ม + re-tune
hyperparameter ใหม่ให้เข้ากัน ซึ่งเป็นงานอีกรอบ (ยังไม่ได้ทำ)

feature "อยู่ระหว่างปล่อยน้ำ" ยังคง validate ไม่ได้ด้วยเหตุผลเดิม (release กระจุกท้าย dataset) —
คำแนะนำเดิมยังใช้ได้: เก็บข้อมูลต่อไปเรื่อยๆ รอ contrast มากพอ

## ไฟล์ในโฟลเดอร์นี้

- `build_release_flag.py`, `Training_Values_with_release_flag.csv` — feature 1
- `walkforward_release_flag.py`, `outputs/walkforward_release_flag_comparison.csv`,
  `outputs/walkforward_release_flag_summary.csv` — ผล walk-forward CV feature 1 (ข้อมูลไม่พอ)
- `build_intraday_range_diagnostic.py`, `intraday_range_diagnostic.csv` — diagnostic รอบแรก (22 วัน)
- `Raw Data_RES002 station.xlsx` — สำเนาไฟล์ที่ผู้ใช้ชี้ให้ดู (ข้อมูลรายชั่วโมงเต็มปี)
- `build_intraday_range_full_history.py`, `intraday_range_full_history.csv` — max/min/range รวม 2
  แหล่ง ครอบคลุม 386 วัน
- `merge_range_into_training.py`, `Training_Values_full_features.csv` — training data เต็มพร้อมทั้ง
  3 feature
- `walkforward_range_feature.py`, `outputs/walkforward_range_feature_comparison.csv`,
  `outputs/walkforward_range_feature_summary.csv` — **ผล walk-forward CV จริงของ feature max/range**
- `wide_log_20260731.csv` — สำเนาไฟล์ wide_log ที่ผู้ใช้อัปโหลดก่อนหน้า
