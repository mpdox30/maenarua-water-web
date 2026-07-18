# Project Memory — เว็บไซต์บริหารจัดการน้ำ ตำบลแม่นาเรือ

อัปเดตล่าสุด: 2026-07-18
ไฟล์นี้เป็นสรุปความจำโปรเจกต์แบบละเอียด สำหรับให้ Claude (หรือคนอื่น) อ่านแล้วเข้าใจสถานะปัจจุบัน
ของทั้งระบบได้เร็ว โดยไม่ต้องไล่อ่าน chat history ย้อนหลัง — เสริมไฟล์ `Cowork_Global_Instructions.md`
(กฎการทำงาน/สไตล์) และ `สรุปไอเดีย_เว็บไซต์บริหารจัดการน้ำ_แม่นาเรือ.md` (ไอเดียตั้งต้นของโปรเจกต์)

---

## 1. ภาพรวมโปรเจกต์

เว็บไซต์ศูนย์ข้อมูลสนับสนุนการบริหารจัดการน้ำ ตำบลแม่นาเรือ อำเภอเมือง จังหวัดพะเยา
โดย School of ICT มหาวิทยาลัยพะเยา ร่วมกับ Hydro-Informatics Institute (HII)
รวมงานวิจัย/ระบบ 3 ด้านหลัก:

1. **พยากรณ์ความต้องการใช้น้ำเกษตร** (Water Demand) — Zone A (rainfed) / Zone B (irrigated)
2. **พยากรณ์น้ำไหลลงอ่างเก็บน้ำ** (Reservoir Inflow Forecasting)
3. **Water Monitoring** — ข้อมูลสดจากสถานีโทรมาตร 4 จุด + GIS

โครงสร้างโฟลเดอร์หลัก:

```
D:\maenaruea-water-web\
├── 01_data\                          -- ข้อมูลดิบ, pipeline scripts, reference tables
│   ├── scripts and code\pipeline\    -- โค้ด production ทั้งหมด (ดูหัวข้อ 3)
│   ├── scripts and code\Reservoir_inflow\  -- notebook ต้นฉบับโมเดล inflow (active/archive)
│   ├── scripts and code\Water_demand\      -- notebook/py ต้นฉบับโมเดล water demand
│   ├── Reservoirs\                   -- rating curve, release log, reference constants
│   └── gis\                          -- shapefile (zone A/B, tambon, village, อ่างเก็บน้ำ)
├── 02_dashboards_existing\           -- dashboard เก่า (ไม่ใช่ระบบหลักปัจจุบัน)
├── 03_website\                       -- เว็บไซต์จริง (ดูหัวข้อ 2)
├── 04_docs_research\                 -- รูป/ตาราง/เอกสารประกอบ manuscript
├── Cowork_Global_Instructions.md     -- กฎการทำงาน/สไตล์ (อ่านก่อนเริ่มงานเสมอ)
├── สรุปไอเดีย_เว็บไซต์บริหารจัดการน้ำ_แม่นาเรือ.md  -- ไอเดียตั้งต้นฉบับเต็ม
├── คำสั่งรัน_scripts.txt              -- คำสั่งรัน .py ทั้งหมดแบบ manual (path เต็ม)
└── PROJECT_MEMORY.md                 -- ไฟล์นี้
```

---

## 2. หน้าเว็บทั้งหมด (03_website/)

ทุกหน้าใช้ดีไซน์ระบบเดียวกัน (dark theme, IBM Plex Sans Thai + Noto Serif Thai + Space Grotesk,
CSS variables ชุดเดียวกันทุกหน้า — ดูตัวอย่างเต็มใน `<style>` ของ monitoring.html/research.html)
Nav bar (main-nav + mobile-nav) เหมือนกันทุกหน้า เรียงลำดับ:

หน้าแรก → ความต้องการใช้น้ำ → น้ำไหลลงอ่าง → สถานการณ์น้ำ → คาดการณ์น้ำท่วม → แผนที่ GIS → งานวิจัย

| ไฟล์ | ชื่อแท็บ | สถานะ | หมายเหตุ |
|---|---|---|---|
| `index.html` | หน้าแรก | ใช้งานจริง | KPI การ์ด %ความจุอ่าง (live, 4 อ่าง) + พรีวิวแผนที่ Zone A/B (Leaflet, satellite imagery, non-interactive) |
| `water-demand.html` | ความต้องการใช้น้ำ | validation mode | โมเดล Two-Stage (CatBoost/XGBoost/LightGBM), train 2020-22, calibrate 23, test 24 — **ยังไม่ใช่ live forecast เต็มรูปแบบ ต้องระบุข้อจำกัดเสมอ** |
| `inflow-forecast.html` | น้ำไหลลงอ่าง | ใช้งานจริง | อ่านจาก `latest.json` → `forecasts.inflow` (7 horizon) |
| `monitoring.html` | สถานการณ์น้ำ | ใช้งานจริง (live) | การ์ดรายสถานี 4 จุด + กราฟ trend ระดับน้ำรายชั่วโมง (filter ต่ออ่าง) + ตารางอ่างเก็บน้ำ 5 แห่ง |
| `flood-forecast.html` | คาดการณ์น้ำท่วม | **ใช้งานจริง (เชื่อมแล้ว 2026-07-18)** | ธงเตือน + KPI ระดับกว๊านพะเยา/ระยะห่างตลิ่ง/ฝน 7 วัน/น้ำล้นรวม + กราฟ 30 วันย้อนหลัง+พยากรณ์ 7 วัน (P10-P90) + heatmap น้ำล้นรายลำน้ำ + แผนที่จุดเสี่ยง (Leaflet) + รายการคำเตือนคุณภาพข้อมูล — ข้อมูลมาจากโปรเจกต์แยก `D:\WMB_Phayao` (ดูหัวข้อ 9) ไม่ใช่ placeholder เดิมแล้ว |
| `gis-map.html` | แผนที่ GIS | ใช้งานจริง | Leaflet เต็มรูปแบบ, 5 basemap, layer toggle (tambon/village/Zone A/Zone B/reservoir) |
| `research.html` | งานวิจัย | ใช้งานจริง | รูป/ตาราง/เอกสารเสริมจาก `04_docs_research/` |

ไฟล์ข้อมูล JSON ที่หน้าเว็บ fetch():
- `assets/data/latest.json` — ผลพยากรณ์หลัก (water demand, inflow, SAR crop classification) เขียนโดย `data_pipeline.py`
- `assets/data/monitoring.json` — ข้อมูลโทรมาตรสด + ประวัติรายชั่วโมง เขียนโดย `monitoring_data_builder.py`
- `assets/data/zone_a.geojson.json`, `zone_b.geojson.json`, `reservoirs.geojson.json`,
  `tambon_boundary.geojson.json`, `villages.geojson.json` — GeoJSON ทั้ง 5 ชั้นข้อมูลของแผนที่ ใช้ร่วมกัน
  ทั้ง `index.html` (พรีวิวแผนที่) และ `gis-map.html` (แผนที่เต็ม) ผ่าน `fetch()` ทั้งคู่แล้ว
  (**แก้แล้ว 2026-07-18**: เดิม `gis-map.html` ฝังเป็น inline `const` ซ้ำข้อมูลกับไฟล์เหล่านี้ ~220KB
  ตอนนี้ดึงจากไฟล์ชุดเดียวกันหมด ไม่มีข้อมูลซ้ำอีกต่อไป — ทำให้ขนาดไฟล์ `gis-map.html` ลดจาก ~267KB
  เหลือ ~40KB)

**ข้อจำกัดสำคัญของทุกหน้าที่ fetch JSON**: ต้องเปิดผ่าน local server (`python -m http.server`)
ไม่ใช่ดับเบิลคลิกเปิดไฟล์ตรงๆ เพราะเบราว์เซอร์บล็อกการอ่านไฟล์ local ผ่าน `file://`

**Chart.js**: vendor ไว้ local แล้วที่ `assets/js/chart.umd.min.js` (v4.4.4) ใช้ใน
`inflow-forecast.html`, `water-demand.html`, `monitoring.html` — ไม่พึ่ง CDN เพื่อให้ทำงาน offline ได้
ส่วน Leaflet (`gis-map.html`, `index.html`) และ Google Fonts (ทุกหน้า) ยังพึ่ง CDN/อินเทอร์เน็ตอยู่

---

## 3. Pipeline scripts (01_data/scripts and code/pipeline/)

ดู `คำสั่งรัน_scripts.txt` (root โปรเจกต์) สำหรับคำสั่งรันแบบเต็มพร้อม path — สรุปย่อที่นี่:

### สคริปต์ที่รันเอง/ผ่าน Task Scheduler ได้

| ไฟล์ | หน้าที่ | ความถี่ | เขียนผลไปที่ |
|---|---|---|---|
| `data_pipeline.py` | pipeline หลัก: water demand + inflow forecast + อ่านผล SAR ล่าสุด | ทุกสัปดาห์ | `03_website/assets/data/latest.json` |
| `sar_background_job.py` | เช็ค/classify ภาพ SAR ใหม่ (Sentinel-1) แยกจาก pipeline หลัก (ใช้เวลานาน) | ทุก 7-10 วัน (มี gate `min_days_between_runs=30` ภายใน) | `01_data/gis/sar_output/sar_result_latest.json` |
| `reservoir_daily_orchestration.py` | คำนวณ Inflow รายวันจากโทรมาตร — **LIVE ตั้งแต่ 2026-07-18** | ทุกวัน | เขียนคู่กัน: `01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv` (shadow) **และ** ไฟล์ทางการจริง `2026_MM_MNR.xlsx` (ผ่าน `reservoir_official_file_writer.py`, backup อัตโนมัติทุกครั้ง) |
| `monitoring_data_builder.py` | ดึงข้อมูลโทรมาตรสด 4 สถานี + ประวัติรายชั่วโมง | ทุก 10-15 นาที | `03_website/assets/data/monitoring.json` |
| `reservoir_official_file_writer.py` | เขียนผลคำนวณลงไฟล์ทางการ .xlsx โดยตรง (แปลงสูตรเป็นค่าคงที่ก่อนเขียนกันข้อมูลเสีย) | ปกติถูกเรียกอัตโนมัติจาก `reservoir_daily_orchestration.py` — รันแยกเองได้เพื่อ backfill หลายวัน | ไฟล์ทางการ `01_data/Reservoirs/inflow/<year>/<year>_<month>_MNR.xlsx` |

มี launcher `.bat` พร้อม venv-detection ให้แล้ว: `run_pipeline.bat`, `run_sar_background_job.bat`,
`run_reservoir_daily_orchestration.bat`, `run_monitoring_data_builder.bat` — ตั้ง Windows Task
Scheduler ให้ทั้ง 4 ตัวแล้ว (คำสั่ง `schtasks` เต็มอยู่ใน `คำสั่งรัน_scripts.txt` และ comment ในไฟล์ .bat เอง)

### โมดูลภายใน (ไม่ต้องรันตรง — ถูกเรียกโดยสคริปต์ข้างบน)

`era5t_worker.py` (เรียกผ่าน subprocess โดย data_pipeline.py, ใช้ conda env "era5-grib" แยก),
`chirps_feature.py`, `mei_feature.py`, `sar_classification.py`, `reservoir_water_balance.py`,
`reservoir_reference_data.py`, `gee_auth.py`, `reservoir_telemetry_from_sheet.py` (ใช้โดย
`monitoring_data_builder.py` และ `reservoir_daily_orchestration.py`)

### โมดูล/แนวทางที่เลิกใช้แล้ว (superseded, เก็บไว้เผื่ออ้างอิง)

- `reservoir_telemetry_client.py` — เดิมตั้งใจ poll API สสน. ตรง (ไม่รองรับ query ย้อนหลัง) —
  แทนที่ด้วย `reservoir_telemetry_from_sheet.py` ที่อ่านจาก Google Sheet ที่ผู้ใช้ตั้ง Apps Script
  poll เองทุก 10 นาทีแล้ว (ดูหัวข้อ 5)
- `telemetry_history_store.py`, `telemetry_feature.py`, `telemetry_hourly_aggregate.py` —
  ออกแบบไว้ตั้งแต่ 2026-07-06 (ก่อนรู้ว่ามี Google Sheet log อยู่แล้ว) **ไม่ได้เชื่อมเข้า
  data_pipeline.py จริง** ถือเป็นของเก่าที่ยังไม่ได้ลบ ไม่ใช่ส่วนของระบบ production ปัจจุบัน

### สคริปต์ debug/ทดสอบ (ใช้ระหว่างพัฒนา ไม่ใช่ production)

ไฟล์ที่ขึ้นต้นด้วย `test_*.py` ทั้งหมดในโฟลเดอร์ pipeline

---

## 4. สูตร/ค่าคงที่สำคัญ — น้ำไหลลงอ่าง (Reservoir Water Balance)

สูตรหลัก (validate bit-exact กับไฟล์ทางการ `2026_July_MNR.xlsx` แล้ว):

```
Inflow(day) = ΔS − R + O + Spill + Evap + Infiltration
```
- `ΔS` = ผลต่าง Storage วันนี้ vs เมื่อวาน (จาก rating curve, lookup ด้วย XLOOKUP floor-match)
- `R` = ฝน (rainfall_1h สะสม 24 ชม., window 07:00→07:00)
- `O` = ปริมาณน้ำที่ปล่อยออก (จาก release_events.csv / ในอนาคตคือ Google Form)
- `Spill` = น้ำล้น spillway (สูตร weir, คำนวณจากระดับน้ำรายชั่วโมง 24 ค่า)
- `Evap` = ระเหย (ตาราง evap รายเดือน × พื้นที่ผิวน้ำ × pan coefficient 0.7)
- `Infiltration` = ซึมลงดิน (1.0 mm/day คงที่ × พื้นที่จาก area_terrain.csv)

**Excel XLOOKUP(..., match_mode=-1)** = exact-or-next-smaller (floor) ไม่ใช่ round-to-nearest —
เคยผิดเพราะ implement เป็น round มาก่อน (คลาดเคลื่อน ~3000 m3/วัน 3 ใน 14 วันทดสอบ) แก้แล้วใน
`reservoir_water_balance.py::_xlookup_floor()`

**สูตร weir spillway**: `water_level_adj = level - 0.155`; `H = max(0, water_level_adj - 489.545)`;
`Q(m3/s) = 1.82 × 30 × H^1.5`; รวม 24 ชม. เป็น Spill รายวัน — ค่าคงที่ตรงกับ
`01_data/Reservoirs/reference/weir_constants.json` (พบว่ามีอยู่แล้วตั้งแต่ 5 ก.ค. ยืนยันตรงกัน)

**สูตร Evap**: `surface_area_m2 × (monthly_evap_norm_mm / days_in_month × 0.7) / 1000` — ค่าคงที่ 12
เดือนตรงกับ `01_data/Reservoirs/reference/monthly_evap_norm.json`

**✅ Resolved 2026-07-18**: เดิมสงสัยว่า Infiltration ควรใช้ `rating_curve_1cm.csv` (ตาม README เก่า
ที่อ้างอิงไฟล์ 2026_May_MNR.xlsx) หรือ `area_terrain.csv` (ตามที่ `reservoir_water_balance.py` ใช้อยู่)
— ตรวจสอบสูตรจริงในไฟล์ทางการปัจจุบัน `01_data/Reservoirs/inflow/2026/2026_July_MNR.xlsx` โดยตรง
(sheet "บัญชีน้ำ" คอลัมน์ J) พบว่า **ยัง XLOOKUP จาก sheet "Area_Terrain" อยู่จริง** ไม่ใช่ Rating
Curve — ยืนยันว่า `reservoir_water_balance.py` ถูกต้องอยู่แล้ว ไม่ต้องแก้โค้ด แก้แค่ README.md ให้ตรง
กับความจริง (README เดิมอ้างอิงไฟล์เดือนพฤษภาที่อาจมีสูตรคนละเวอร์ชัน)

**⚠️ ยังไม่ได้ใช้**: `flow_rate_inlet.csv` / `flow_rate_spillway.csv` (มีอยู่แล้วตั้งแต่ 5 ก.ค.) มีตาราง
"จำนวนรอบวาล์ว → อัตราการไหล" ที่ตอบโจทย์ TODO เดิม (แปลง input ของ Google Form เป็น O m3/day) —
ยังไม่ได้เอามาต่อกับ `release_events.csv` / `reservoir_daily_orchestration.py`
(valve_turns ที่มีข้อมูลจริง: inlet 1-11 รอบ, spillway 1-12 รอบ — ดู
`01_data/Reservoirs/reference/flow_rate_inlet.csv` / `flow_rate_spillway.csv`)

**Google Form สำหรับบันทึกการปล่อยน้ำ**: โค้ดฝั่ง pipeline พร้อมแล้ว (2026-07-18) — ยังเหลือแค่
สร้าง Form/Sheet จริงฝั่งผู้ใช้ สเปคเต็ม + Apps Script (`Code.gs`) ทดสอบ logic ผ่านหมดแล้ว (mock
ทุก branch: เปิดวาล์วถูก/ผิดรอบ, ปิดวาล์วถูก event, ปิด event ที่ไม่มีจริง) อยู่ใน
`01_data/scripts and code/pipeline/RESERVOIR_AUTOMATION_DESIGN.md` หัวข้อ "อัปเดต 2026-07-18"
รวม 5 ขั้นตอน: สร้าง Form (branch เปิด/ปิดตามคำถาม "การกระทำ") → เพิ่มแท็บ `release_log` ใน Sheet
คำตอบ → วาง Apps Script → ตั้ง 2 triggers (onFormSubmit + time-driven ทุก 15 นาทีรีเฟรช dropdown
ปิดวาล์ว) → publish-to-web แท็บ `release_log` แล้วตั้ง env var `RESERVOIR_RELEASE_SHEET_CSV_URL`
บนเครื่องที่รัน `reservoir_daily_orchestration.py` — ระหว่างที่ยังไม่ตั้ง env var นี้ ระบบ fallback
ไปอ่าน `01_data/Reservoirs/release_log/release_events.csv` local เหมือนเดิมอัตโนมัติ (มี 1 event จริง
บันทึกไว้: 9446.4 m3/day, 2026-06-26 ถึง 2026-10-14) ไม่มีความเสี่ยงถ้ายังไม่พร้อมตั้ง Form ตอนนี้

**✅ แก้แล้ว 2026-07-18 (ก่อนสร้าง Form จริง)**: `load_release_events()`/`get_release_o_for_date()`
ใน `reservoir_daily_orchestration.py` เดิมจะ **crash ทั้งไฟล์** (ValueError) ถ้ามีแถวไหน end_date/
end_time ว่าง (กรณีชุมชนกรอกแค่ตอนเปิดวาล์ว ยังไม่กรอกตอนปิด) — แก้แล้วให้ end_dt=None ตีความว่า
"เปิดต่อเนื่องไปเรื่อยๆ จนกว่าจะมีแถวปิดจริงมาแทน" คำนวณ inflow รายวันของช่วงที่ยังเปิดค้างได้ปกติ
ทดสอบแล้วด้วย mock event ที่ end_date/end_time ว่าง (ครอบคลุมกรณีเปิดแล้วไม่ปิด และกรณีปิดแล้วจริง)
ทั้งคู่ทำงานถูกต้อง ไม่กระทบ event เดิมที่ปิดแล้ว (release_events.csv ปัจจุบัน)

**Rain window convention**: สมมติฐาน 07:00→07:00 ยังไม่ยืนยัน 100% — ทดสอบ 3 วัน (12,13,14 ก.ค.)
วันที่ 12-13 ตรงเป๊ะ, วันที่ 14 ต่างกัน ~2169 m3 (สาเหตุ: ฝน 24 ชม. คำนวณได้ 17.0mm vs ไฟล์ทางการ
24.4mm) — ต้องเก็บข้อมูลขนานเพิ่มอีกหลายวัน (โดยเฉพาะวันฝนตกหนัก) ถึงจะสรุปได้ชัด

**อัปเดต 2026-07-18**: ทดสอบ window 7 รูปแบบ (07:00, ปฏิทิน 00:00-24:00, 06:00, 08:00, 09:00, 12:00,
18:00) กับข้อมูลจริงวันที่ 14 ก.ค. พบว่าทุก window ที่ปลายอยู่ช่วง 00:00-09:00 ได้ **17.00mm เท่ากันหมด**
— สรุปว่าช่องว่าง ~7.4mm **ไม่ได้เกิดจากเลือก window ผิด** แต่น่าจะเป็นความต่างระหว่างเซนเซอร์ฝนโทรมาตร
กับตัวเลขที่ชุมชนกรอกมือ (เครื่องวัดฝนคนละตัว หรือคลาดเคลื่อนตอนกรอก) — ยึด "07:00→07:00" ต่อไปได้
ไม่ต้องเปลี่ยนสูตร ความเสี่ยงที่เหลือคือความต่างของแหล่งข้อมูลฝน ไม่ใช่บั๊ก timing

---

## 5. ระบบ Monitoring (สถานีโทรมาตร 4 จุด)

**สถานีที่อยู่ในตำบลแม่นาเรือ** (ยืนยันจาก attribute `Tele_Code` ใน `01_data/gis/อ่างเก็บน้ำ.shp`):

| Tele_Code | ชื่ออ่าง | spillway (ม.รทก.) | ความจุที่ spillway |
|---|---|---|---|
| RES002 | อ่างเก็บน้ำแม่นาเรือ (Mae Na Rua) | 489.54 | 1.625 ล้าน ลบ.ม. |
| RES004 | อ่างเก็บน้ำวิทยาลัยเกษตร (Phayao C.A.T.) | 457.07 | 0.348 ล้าน ลบ.ม. |
| RES005 | อ่างเก็บน้ำห้วยถ้ำ (Huai Tham) | 478.10 | 0.495 ล้าน ลบ.ม. |
| RES006 | อ่างเก็บน้ำห้วยโซ้ (Huai So) | 508.00 | 0.119 ล้าน ลบ.ม. |
| (ไม่มี) | อ่างเก็บน้ำห้วยจำตุ้ม (Huai Cham Tum) | 497.50 | 0.314 ล้าน ลบ.ม. — **ไม่มีสถานีโทรมาตร** |

สถานีอื่นนอกตำบลที่ API ส่งมาปนด้วย (กรองทิ้งอัตโนมัติใน `monitoring_data_builder.py`):
PYO001, RES001, RES003, WBYN

**Data source**: API สสน. (`https://wea.hii.or.th:3005/api/v1/...`) → ผู้ใช้ตั้ง Google Apps Script
poll เองทุก 10 นาที → บันทึกลง Google Sheet แท็บ "wide_log" (1 แถว/รอบ poll, คอลัมน์
`<station_code>_<data_type>` เช่น `RES002_water_level`) → publish-to-web เป็น CSV (public read-only
link, ไม่ต้อง OAuth) → `reservoir_telemetry_from_sheet.py::load_wide_log()` อ่านมาใช้

**บั๊กสำคัญที่เจอและแก้แล้ว** (ทั้งคู่อยู่ใน `reservoir_telemetry_from_sheet.py`):
1. **rolling 1h rainfall นับซ้ำ** — ถ้าเอาทุกแถว (poll ทุก 10 นาที) มาบวกกันตรงๆ จะนับฝนซ้ำ ~6 เท่า
   แก้ด้วยการหาแถว "ใกล้เวลาหลักชั่วโมงที่สุด" (±30 นาที) แล้วเอาแค่ 24 ค่ามาบวก
2. **"แถวล่าสุดในชั่วโมง" ≠ "ค่า ณ เวลาเป้าหมาย"** — เดิมหยิบแถวล่าสุดในชั่วโมงนั้นมาใช้แทนค่า ณ
   เวลาหลักชั่วโมงจริง ทำให้ระดับน้ำ/Storage เพี้ยนหลักพัน m3/วัน (ยืนยันจากข้อมูลจริง 2026-07-11)
   แก้เป็น "หาแถวใกล้เวลาเป้าหมายที่สุด" แทน — ใช้เทคนิคเดียวกันนี้ทั้งใน `compute_daily_inputs()`
   (สำหรับ inflow) และ `build_station_history()` ใน `monitoring_data_builder.py` (สำหรับกราฟ trend)
3. **datetime ไม่ zero-pad** — Google Sheets CSV export ให้ `"2026-07-11 0:00:00"` (ไม่ใช่ `"00:00:00"`)
   ทำให้ `dt.datetime.fromisoformat()` error — แก้ด้วย `_parse_dt_lenient()` (regex-based parser)

**%ความจุ**: คำนวณจาก rating curve เฉพาะแต่ละอ่าง (interpolation ไม่ใช่ floor-match เพราะเป็นค่าที่
แสดงผลอย่างเดียว ไม่ต้อง bit-exact) — validate แล้วว่า storage-at-spillway ตรงกับตัวเลข capacity ที่มี
อยู่เดิมในเว็บแทบทุกอ่าง (ยกเว้นคลาดเคลื่อนเล็กน้อยจาก floating point)

**ประวัติกราฟ trend**: `build_station_history()` ให้ค่ารายชั่วโมงย้อนหลัง (default 14 วัน, จำกัดตาม
ข้อมูลจริงที่มี — ปัจจุบันมีจริง ~7 วัน) ไม่เติมค่าประมาณช่วงที่ขาดหาย (ปล่อยกราฟเว้นช่วง)

**⚠️ ข้อจำกัดของ `mcp__workspace__web_fetch`**: fetch ลิงก์ Google Sheets publish-to-web
(`docs.google.com`) ไม่ได้เลย (return ว่างเปล่าไม่มี error) — เป็นข้อจำกัดของ tool ไม่ใช่ปัญหาที่ตัวลิงก์
ผู้ใช้เปิดผ่านเบราว์เซอร์ตัวเองได้ปกติ และสคริปต์ production (`urllib` ธรรมดา) ก็ทำงานได้ปกติบนเครื่อง
ผู้ใช้เอง (bash sandbox ของผมก็ block `wea.hii.or.th`/`docs.google.com` เช่นกัน — ต้องทดสอบด้วยไฟล์
ที่ผู้ใช้ upload มาให้แทนเสมอ)

---

## 5b. climate_prediction_readiness (Water Demand — ml_features_live.csv)

**บั๊กเชิงโครงสร้างที่พบ + แก้แล้ว 2026-07-18**: ตรวจสอบพบว่า `ml_features_live.csv` สะสมแถวทุกสัปดาห์
จริง (จาก `_fetch_climate_features_step()` ที่ `data_pipeline.py` เรียกทุกรอบ) แต่ **ไม่มีสัปดาห์ไหน
ครบ 7/7 วัน (ERA5T และ CHIRPS) เลยแม้แต่สัปดาห์เดียว** ใน 34 แถวแรก (~17 สัปดาห์) เพราะโค้ดดึงข้อมูล
"สัปดาห์นี้" (as_of=วันนี้) ทุกครั้งที่รัน ซึ่ง ERA5T/CHIRPS มี publish latency เสมอ (สัปดาห์ปัจจุบันจึง
ไม่ครบ 7 วันโดยธรรมชาติ) และไม่มีขั้นตอนย้อนไปอัปเดตสัปดาห์เก่าตอนข้อมูล final ออกแล้วจริง — **แค่รอ
เวลาผ่านไปจะไม่หายเอง** ต้องแก้โค้ด

แก้โดยเพิ่ม `_backfill_incomplete_climate_weeks()` ใน `data_pipeline.py` — สแกน `ml_features_live.csv`
หาสัปดาห์ที่เคย fetch ได้ไม่ครบ 7/7 แต่ผ่านมานานพอแล้ว (default `min_age_days=14`) ที่ provider ควรมี
final data ให้ดึงซ้ำ แล้ว re-fetch สัปดาห์นั้นใหม่ (as_of = วันอาทิตย์ของสัปดาห์) — ถ้าได้ 7/7 จะ append
แถวใหม่ (ไม่แก้แถวเดิม เก็บ audit trail) จำกัด `max_weeks_to_backfill=2` ต่อรอบ (ERA5T เรียก subprocess
แยก environment ช้า) ถ้าค้างมากกว่านี้จะไล่ backfill ต่อในรอบถัดๆไปเอง เรียกจาก
`_fetch_climate_features_step()` อัตโนมัติทุกรอบ ก่อนเช็ค `prediction_readiness` (backfill สำเร็จรอบ
ไหน readiness จะเห็นผลรอบเดียวกันเลย)

ทดสอบด้วย mock (chirps_feature.get_chirps_feature / _fetch_era5t_via_subprocess ปลอม เพราะ sandbox
ผมเรียก GEE/conda env จริงไม่ได้) ยืนยันแล้ว: เลือกสัปดาห์เก่า+ไม่ครบถูกต้อง, ข้ามสัปดาห์ที่มีแถวครบอยู่
แล้ว, ข้ามสัปดาห์ที่ใหม่เกินไป (< min_age_days), เคารพ quota, append แถวใหม่ถูก schema เมื่อ mock คืน
7/7, ไม่ append เมื่อยังไม่ครบ, error รายสัปดาห์ไม่ทำให้สัปดาห์อื่น/ทั้งฟังก์ชันพัง — **ยังไม่ได้ทดสอบ
เรียก GEE/ERA5T จริงบนเครื่องผู้ใช้ (ทำไม่ได้จาก sandbox นี้) ต้องรัน `data_pipeline.py` จริงอีกสัก
รอบเพื่อยืนยัน end-to-end**

**ข้อจำกัดของแถวที่ backfill**: ไม่มี MEI และไม่มี NIR_A_m3/GIR_B_m3 (ต้องใช้พื้นที่ SAR ณ ตอนนั้น) —
ยังไม่กระทบเพราะ live climate path นี้ยังไม่ถูกเรียกใช้จริงในการทำนาย (`_wd_build_feature_vector()`
ยังอ่านจาก `ml_features_phase4.csv` static เหมือนเดิม)

---

## 6. ข้อเท็จจริง/กฎสำคัญที่ต้องจำ

- ชื่อคลองในระบบน้ำ ต.นครป่าหมาก คือ **"แคววังทอง"** (ไม่ใช่ "แควังทอง")
- โมเดล Water Demand ยังเป็น **validation เท่านั้น** (train 2020-22, calibrate 23, test 24) —
  ห้ามนำเสนอเป็น live forecast เต็มรูปแบบโดยไม่ระบุข้อจำกัด
- **ห้ามสร้างตัวเลขผลการทดลอง ([TBD] values) ขึ้นมาเองโดยไม่มีข้อมูลรองรับ**
- หน้า `flood-forecast.html` **เชื่อมกับโปรเจกต์ WMB_Phayao แล้ว 2026-07-18** (ไม่ใช่ placeholder
  เปล่าอีกต่อไป — เดิมตั้งใจเว้นว่างไว้ก่อน 2026-07-17 ดูหัวข้อ 9 สำหรับรายละเอียดการเชื่อมต่อ)
- การจัดหมวดข้อมูลเว็บ: สาธารณะ / จำกัดสิทธิ์นักวิจัย / เฉพาะทีมโครงการ — ห้ามเอา raw sensor data,
  โค้ดโมเดล, draft manuscript ไปแสดงในส่วนสาธารณะ
- Bash sandbox ของผมมี **ปัญหา mount ไม่เสถียรเป็นระยะ** (ไฟล์ที่เขียน/copy ผ่าน bash บางครั้งถูก
  truncate โดยไม่มี error) — ถ้าเจอ syntax error/ความยาวไฟล์ผิดปกติหลัง cp หรือเขียนผ่าน mount ให้ลอง
  เขียนใหม่ด้วย bash heredoc ตรงๆ ในแซนด์บ็อกซ์แทน หรือใช้ Read tool ยืนยัน ground truth เทียบกับที่
  bash อ่านได้

---

## 7. สรุปงานที่ทำเสร็จแล้ว (ไล่ตามลำดับเวลาคร่าวๆ)

- โครงสร้างเว็บไซต์ 6 หน้าแรก + pipeline หลัก (water demand, inflow, SAR classification)
- SAR crop classification (Sentinel-1, export+download+local classify, service account auth,
  Windows Task Scheduler) — เชื่อมเข้า NIR/GIR ของ Water Demand แล้ว
- แก้บั๊ก dropNulls, band-order, n_pixels_outside_zone ในระบบ SAR หลายรอบ
- Reservoir Inflow: สกัดสูตร water balance จาก Excel, สร้าง `reservoir_water_balance.py`
  (validate bit-exact 14/14 วัน), เชื่อม telemetry จริง (`reservoir_telemetry_from_sheet.py`,
  แก้บั๊ก rolling-rain + hour-bucketing), orchestration shadow-mode (`reservoir_daily_orchestration.py`)
- อัปเดตขอบเขต Zone A/B ใน `gis-map.html` จาก shapefile จริง (cross-validate กับ SAR area totals)
- Monitoring multi-station: สกัด rating curve อีก 3 อ่าง, สร้าง `monitoring_data_builder.py`,
  ปรับ `monitoring.html` เป็นการ์ดต่อสถานี, เพิ่มกราฟ trend รายชั่วโมง (filter ต่ออ่าง, Chart.js local)
- `index.html`: การ์ด %ความจุอ่าง live (4 อ่าง), พรีวิวแผนที่ Leaflet (satellite imagery, non-interactive)
- เปลี่ยนชื่อแท็บ "Monitoring" → "สถานการณ์น้ำ" ทั้งเว็บ
- เพิ่มแท็บ "คาดการณ์น้ำท่วม" (placeholder เปล่า) ทั้งเว็บ
- สร้าง `คำสั่งรัน_scripts.txt` (reference คำสั่งรัน .py ทั้งหมดแบบ manual)

## 8. งานที่ยังค้าง / ต้องตัดสินใจร่วมกับผู้ใช้

1. ~~Reconcile `area_terrain.csv` vs `rating_curve_1cm.csv`~~ — **แก้แล้ว 2026-07-18** (หัวข้อ 4)
2. เชื่อม `flow_rate_inlet.csv`/`flow_rate_spillway.csv` เข้ากับ `release_events.csv` — **แก้แล้ว
   2026-07-18**: สร้าง utility function `valve_turns_to_flow_m3_per_day()` ใน
   `reservoir_water_balance.py` พร้อมใช้งาน แต่ยังไม่มี Form ป้อนข้อมูล valve_turns จริง (ดูข้อ 3)
3. สร้าง Google Form จริงสำหรับบันทึกการปล่อยน้ำ — **โค้ด/สเปคพร้อมแล้ว 2026-07-18** (ดูหัวข้อ 4)
   รอผู้ใช้สร้าง Form/Sheet จริงตามสเปคใน `RESERVOIR_AUTOMATION_DESIGN.md` เท่านั้น (ตอนนี้ยังใช้
   CSV มือแทนอยู่ ไม่มีผลกระทบจนกว่าจะตั้ง env var)
4. ยืนยัน rain-window convention (07:00→07:00) ด้วยข้อมูลขนานเพิ่มเติม — **ยังไม่ยืนยัน** (เป็นความเสี่ยง
   ที่ยอมรับแล้วตอนตัดสินใจไป live ข้อ 5)
5. `reservoir_daily_orchestration.py` — **แก้แล้ว 2026-07-18**: ไป live แล้วตามที่ผู้ใช้ยืนยัน
   (ยอมรับความเสี่ยงคลาดเคลื่อนบางวันจาก rain-window ที่ยังไม่ 100%) เขียนทับไฟล์ทางการจริงแล้ว
   ผ่าน `write_computed_day_to_official_xlsx()` — ดูรายละเอียดหัวข้อ 9
6. เนื้อหาจริงของหน้า "คาดการณ์น้ำท่วม" — รอผู้ใช้ตัดสินใจขอบเขต/โมเดล (ยังไม่ทำ ตามที่ตั้งใจ)
7. `gis-map.html` ยังฝัง GeoJSON เป็น inline const — **แก้แล้ว 2026-07-18** เปลี่ยนเป็น fetch()
   จากไฟล์ `assets/data/*.geojson.json` ชุดเดียวกับที่ index.html ใช้แล้ว ไม่มีข้อมูลซ้ำอีกต่อไป
8. เนื้อหาจริงของหน้า "คาดการณ์น้ำท่วม" — **แก้แล้ว 2026-07-18** เชื่อมกับโปรเจกต์ WMB_Phayao แล้ว
   ไม่ใช่ placeholder เปล่าอีกต่อไป (ดูหัวข้อ 10)

---

## 9. reservoir_daily_orchestration.py — สรุปการไป live (อ้างอิงจากข้อ 5 ด้านบน)

รายละเอียดเต็มอยู่ในหัวข้อ 4 ("✅ แก้แล้ว" ทุกจุด) — สรุปสั้น: `run_and_append()` เขียนคู่กันทั้ง
shadow CSV (`inflow_auto/RES002_daily_computed.csv`) และไฟล์ทางการจริง (`reservoir_official_file_writer.py`,
backup อัตโนมัติทุกครั้ง, แก้ปัญหา openpyxl ทำลาย cached formula values แล้ว) ตั้ง Task Scheduler
อัตโนมัติแล้วทั้ง `MaeNaRua_Reservoir_Daily_Orchestration` (07:30 ทุกวัน) และ
`MaeNaRua_Monitoring_Data_Builder` (ทุก 15 นาที) — คำสั่ง `schtasks` เต็มอยู่ใน `คำสั่งรัน_scripts.txt`

---

## 10. หน้า "คาดการณ์น้ำท่วม" — เชื่อมกับโปรเจกต์ WMB_Phayao (2026-07-18)

**โปรเจกต์ต้นทาง**: `D:\WMB_Phayao` — แบบจำลอง Water Mass Balance (WMB) ครอบคลุมพื้นที่ตำบล
แม่นาเรือ/บ้านตุ่น/แม่ใส (กว้างกว่าโปรเจกต์เว็บนี้ที่โฟกัสแค่แม่นาเรือ) มี 9 โฟลเดอร์หลัก (raw data →
processed terrain/CN → model network/parameters → simulation → validation → outputs → scripts →
โมเดลพยากรณ์กว๊าน `08_Kwan_prediction` → ระบบ live รายวัน `09_live`) เป็นคนละ git repo แยกจาก
`D:\maenaruea-water-web` — **ต้อง request_cowork_directory แยกทุกครั้งที่ต้องแก้ไฟล์ในโฟลเดอร์นี้**

**จุดเชื่อมต่อ**: `09_live/daily_update.py` (รันผ่าน Task Scheduler ของตัวเอง ชื่อ `WMB_daily`
07:30 ทุกวัน แยกจาก 4 tasks ของโปรเจกต์เว็บนี้ — ดู `09_live/README.md`) คำนวณพยากรณ์กว๊านพะเยา 7 วัน
+ ธงเตือน แล้ว **คัดลอก `flood_latest.json` ไปทับที่
`D:\maenaruea-water-web\03_website\assets\data\flood_latest.json` ให้อัตโนมัติทุกครั้งที่รัน**
(ตั้งค่าไว้ใน `09_live/config.json` → `website_data_path`) — ไม่ต้องมีโค้ดฝั่งเว็บไปดึงข้อมูลข้าม
โปรเจกต์เอง เป็นฝั่ง WMB_Phayao ที่ push เข้ามาเอง

**ไฟล์ที่ `flood-forecast.html` ใช้** (ทั้งหมดอยู่ใน `03_website/assets/data/`, WMB_Phayao เป็นคน
วาง/อัปเดต ไม่ใช่ pipeline ของเว็บนี้):
- `flood_latest.json` — flags (overall/kwan/overflow + message), banks (ระดับตลิ่ง Mae_Main1=391.8,
  RongHai=391.0), kwan_now (ระดับ+เปลี่ยนแปลง 3 วัน), rain_7d, kwan_forecast (7 วัน พร้อม P10/P90),
  kwan_observed_30d, overflow_forecast (รายลำน้ำ×วัน, ว่างได้ถ้าไม่มีน้ำล้นคาดการณ์), nodes
  (lat/lon/name ต่อลำน้ำ 10 จุด), warnings, model_info
- `wmb_canals.geojson.json` (17 features), `wmb_reservoirs7.geojson.json` (7 features — อ่างเก็บน้ำ
  ครอบคลุมกว้างกว่า 5 อ่างของโปรเจกต์เว็บนี้ รวมห้วยม่วง/บ้านตุ่นด้วย)

**หน้าเว็บ**: ธงเตือนใหญ่ (ปกติ/เฝ้าระวัง/เตือนภัย/วิกฤต) + KPI 4 ตัว (ระดับกว๊าน, ระยะห่างตลิ่ง, ฝน
7 วัน, น้ำล้นรวม 7 วัน) + กราฟ canvas วาดมือ (30 วันย้อนหลัง + พยากรณ์ 7 วันพร้อมแถบ P10-P90 + เส้น
ตลิ่ง 2 เส้น) + heatmap น้ำล้นรายลำน้ำ×วัน (แสดง empty-state ถ้าไม่มีน้ำล้น) + แผนที่ Leaflet
จุดเสี่ยง (สีตามระดับเตือน) + panel ความน่าเชื่อถือ/คำเตือนคุณภาพข้อมูล — มี staleness check ในตัว
(ถ้า `generated_at` เก่ากว่า 48 ชม. จะโชว์ notice เตือนแยก)

**ตรวจสอบแล้ว 2026-07-18**: สร้าง JSDOM harness (mock fetch จากไฟล์จริง 3 ไฟล์ + mock Leaflet +
mock canvas 2D context) รัน script จริงในหน้าจากไฟล์จริง ยืนยันไม่มี exception, ค่า KPI/ธง/heatmap
empty-state/warnings/model_info/แผนที่ (13 layers: tile+canals+reservoirs+10 node markers) ตรงกับ
ข้อมูลจริงในไฟล์ครบทุกจุด — **ยังไม่ได้เปิดดูจริงในเบราว์เซอร์ (แนะนำเปิดผ่าน
`python -m http.server` แล้วเช็คด้วยตาอีกครั้งก่อนใช้งานจริง)**

**ข้อควรระวังเชิงปฏิบัติการ**: หน้านี้จะสดตามรอบที่ `WMB_daily` scheduled task รันบนเครื่อง (ถ้า
เครื่องปิดตอน 07:30 ข้อมูลจะค้างเหมือนหลักการเดียวกับ `MaeNaRua_Reservoir_Daily_Orchestration` —
ดูคำอธิบาย staleness เดิมที่เคยตอบผู้ใช้ไปแล้ว) ต้องเช็คว่า Task Scheduler ของ WMB_Phayao ตั้งไว้แล้ว
จริงบนเครื่อง (คนละ task จาก 4 tasks ของโปรเจกต์เว็บนี้ ไม่ได้อยู่ใน `คำสั่งรัน_scripts.txt`)
