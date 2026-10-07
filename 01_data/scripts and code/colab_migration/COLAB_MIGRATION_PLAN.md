# แผนการย้าย Pipeline หลักไป Google Colab

อัปเดตล่าสุด: 2026-07-19 (รอบทบทวน 2 — เพิ่มรายละเอียดตั้งแต่ mount Drive + จัดการไฟล์/โฟลเดอร์)
ไฟล์นี้คือแผนงานเต็มสำหรับย้าย "pipeline หลักที่รันวันละ/สัปดาห์ละครั้ง" (climate features, SAR,
prediction models) จาก Windows Task Scheduler ไป Google Colab — เสริมไฟล์
`prompt_for_cowork_colab_migration.txt` (บริบทเดิมจากแชทที่ตัดสินใจสถาปัตยกรรมนี้)

**กฎที่ต้องทำตามเคร่งครัด (ย้ำจากบริบทเดิม)**: ห้ามแก้/ย้าย/ลบไฟล์ใดๆ ใน
`01_data/scripts and code/pipeline/`, `Water_demand/`, `Reservoir_inflow/` เด็ดขาด (ทั้งบนเครื่อง
Windows และบน Drive ที่ mirror มา) งานทั้งหมดของ Colab migration ทำในโฟลเดอร์
`01_data/scripts and code/colab_migration/` เท่านั้น

## 0. สรุปลำดับขั้นตอนทั้งหมด (เช็คสถานะล่าสุดตรงนี้ก่อนเสมอ)

| # | ขั้นตอน | ใครทำ | สถานะ |
|---|---|---|---|
| 1 | ตัดสินใจสถาปัตยกรรม (Telemetry→Apps Script แยก, pipeline หลัก→Colab) | ตัดสินใจแล้ว (แชทก่อน) | ✅ เสร็จ |
| 2 | พอร์ต `era5t_worker.py`→`era5t_worker_colab.py` + ทดสอบ business logic (manual upload) | ผม+คุณ | ✅ เสร็จ (bit-exact + live CDS fetch ผ่าน) |
| 3 | ตัดสินใจ trigger: เปิด Colab เองทุกวัน (ไม่ใช้ GitHub Actions/Colab Enterprise) | คุณ | ✅ เสร็จ |
| 4 | Copy `maenaruea-water-web` + `WMB_Phayao` ขึ้น Drive | คุณ | ✅ เสร็จ |
| 5 | ลบ `.venv/`, `.git/` ออกจาก Drive ทั้ง 2 โปรเจกต์ | คุณ | ✅ เสร็จ |
| 6 | ยืนยันวิธี CDS credential เดิม (`.cdsapirc` อัปโหลดตรง) | คุณ | ✅ เสร็จ |
| 7 | เขียนสคริปต์ robocopy mirror Drive (`colab_migration/sync_to_drive.bat`) | ผมเขียนแล้ว | ✅ เสร็จ — **เหลือคุณเลือกวิธีใช้ + ตั้ง Task Scheduler เอง (ดูหัวข้อ 2.5)** |
| **8** | **Redo ERA5T ผ่าน Drive จริง (Cell 1-7 หัวข้อ 3) — ไม่ต้องรอข้อ 7** | **คุณรัน + ผมเช็คผล** | ⬜ **ทำต่อได้ทันที** |
| 9 | หา path ไฟล์ GEE service account `.json` + email | คุณ | ⬜ รอ |
| 10 | Phase 1 — พอร์ต `mei_feature.py` → `mei_feature_colab.py` | ผม+คุณ | ✅ เสร็จ (2026-07-19) — ผลตรงกับ Windows เป๊ะทุกค่ารวม `nino34_oni_latest` |
| 11 | Phase 2 — พอร์ต `chirps_feature.py` → `chirps_feature_colab.py` | ผม+คุณ | ✅ เสร็จ (2026-07-19) — GEE Service Account ทำงาน, ผลตรงกับ Windows log ล่าสุดเป๊ะทั้ง 2 zone |
| 12 | หา version scikit-learn/rasterio ที่ train ไว้ + path โมเดล `.pkl` บน Drive | คุณ | ✅ เสร็จ (2026-07-19) — path ที่ให้มาผิดไฟล์ แต่ path จริงมีอยู่แล้วบน Drive (ดูหัวข้อ 6) |
| 13 | Phase 3 — พอร์ต `sar_classification.py` | ผม+คุณ | ✅ เสร็จ (2026-07-19) — import ตรงจาก `pipeline/` ไม่ต้อง copy ไฟล์เลย รันจริง `trigger_crop_classification()` สำเร็จ `status="ok"`, ไม่มี error, band order verified (ดูหัวข้อ 6) |
| 14 | หา version catboost/xgboost/lightgbm ที่ train ไว้ | คุณ | ⬜ รอ |
| 15 | Phase 4 — พอร์ต prediction models | ผม+คุณ | ✅ เสร็จ (2026-07-19) — `data_pipeline_colab.py` (copy, แก้แค่ logger) รันจริง ตรงกับ Windows เป๊ะทั้ง Water Demand + Reservoir Inflow |
| 16 | Phase 5 — รวม `data_pipeline.py` เป็น flow เดียวบน Colab | ผม+คุณ | ✅ เสร็จ (2026-07-19) — orchestration เต็มรูปแบบรันจริง ตรงกับ Windows |
| 17 | หา GitHub PAT (scope `repo`) + ยืนยัน remote repo จริง | คุณ | ⬜ รอ |
| 18 | Phase 6 — เขียนขั้น git push + รันคู่ขนานกับ Windows สักพัก | ผม+คุณ | ✅ เขียน+ทดสอบ push จริงสำเร็จ (2026-07-19) — เหลือช่วงรันคู่ขนานตัดสินใจ cutover |
| 19 | Phase 7 — เขียน runbook รันประจำวัน | ผม | ✅ เสร็จ (2026-07-19/20) — ดู `colab_migration/DAILY_RUNBOOK.md` |
| 20 | **Cutover** — ปิด Windows Task Scheduler ของ `data_pipeline.py`/`sar_background_job.py` | คุณ (ตัดสินใจร่วม) | ⬜ รอ |

**ทำได้เลยตอนนี้ (ไม่ต้องรออะไร) = ข้อ 7 กับข้อ 8** — ตอบเรื่อง robocopy (ข้อ 7) แล้วไปรัน Cell
1-7 (ข้อ 8) ได้พร้อมกัน คนละเรื่องไม่ผูกกัน

---

**สำคัญ**: การทดสอบ ERA5T รอบก่อน (อัปโหลดไฟล์มือทีละไฟล์เข้า `/content`) เป็นแค่การทดลองว่า
business logic ถูกต้อง **ไม่ใช่ workflow จริงที่จะใช้งาน** — รอบนี้ต้องทำใหม่ทั้งหมดผ่าน Drive ที่
mount แล้ว (ดูหัวข้อ 3)

---

## 1. เป้าหมายเดิม vs ข้อจำกัดที่พบจริง

เป้าหมายเดิม: "เว็บจะไม่อัปเดตถ้าไม่เปิดเครื่อง Windows ทิ้งไว้ ต้องการแก้ปัญหานี้"

Colab เวอร์ชันปกติ (Pro/Pro+) **ไม่มีฟีเจอร์รันตามเวลาอัตโนมัติแบบไม่ต้องเปิดเอง** (ฟีเจอร์นั้นอยู่ใน
Colab Enterprise บน Google Cloud คนละ tier ต้องมี GCP billing แยก) — **ผู้ใช้ตัดสินใจแล้ว
(2026-07-19): เปิด Colab เองทุกวัน** ยอมรับว่าไม่ได้ automation 100% แต่แก้ปัญหาหลักที่ตั้งใจแก้ได้
แล้ว (ปัญหา ecCodes/conda บน Windows + ไม่ต้องเปิดเครื่อง Windows เครื่องนี้ทิ้งไว้ เปลี่ยนเป็นเปิด
เบราว์เซอร์สั้นๆ จากเครื่องไหนก็ได้)

---

## 2. โครงสร้างบน Google Drive (ยืนยันแล้วจากผู้ใช้)

Path จริงบน Drive (มุมมอง Windows ผ่าน Drive สำหรับเดสก์ท็อป):
- `G:\My Drive\Colab Notebooks\Mae_Na_Rua\maenaruea-water-web`
- `G:\My Drive\Colab Notebooks\Mae_Na_Rua\WMB_Phayao`

Path เดียวกันเมื่อ mount ใน Colab (ใช้ path นี้ในโค้ดทุกที่ ไม่ใช่ path แบบ Windows):
```
/content/drive/MyDrive/Colab Notebooks/Mae_Na_Rua/maenaruea-water-web
/content/drive/MyDrive/Colab Notebooks/Mae_Na_Rua/WMB_Phayao
```

ผู้ใช้ copy "โครงสร้างเดิมทั้งหมด" ขึ้นไป (ไม่ได้เลือกเฉพาะไฟล์ที่จำเป็น) — เท่ากับว่า
`01_data/scripts and code/colab_migration/` (มี `era5t_worker_colab.py` +
`COLAB_MIGRATION_PLAN.md` อยู่แล้ว) ถูก copy ขึ้นไปด้วยโดยอัตโนมัติ **ไม่ต้องอัปโหลดไฟล์พวกนี้
ซ้ำมือเข้า Colab อีก** — mount Drive แล้วเรียกใช้จาก path ตรงได้เลย (ต่างจากรอบทดลองก่อนหน้าที่ต้อง
`files.upload()` ทุกครั้ง)

### 2.1 การจัดการไฟล์/โฟลเดอร์ที่ต้องทำ (ทำครั้งเดียว)

| โฟลเดอร์/ไฟล์ | ทำอะไร | เหตุผล |
|---|---|---|
| `maenaruea-water-web/.venv/` | **ลบออกจาก Drive** | Python venv เฉพาะ Windows (binary) ใช้บน Colab ไม่ได้ กิน storage เปล่าๆ (หลักร้อย MB ขึ้นไป) |
| `maenaruea-water-web/.git/` | **ลบออกจาก Drive** | ไม่ใช้ git ผ่าน Drive-mounted filesystem (ช้า/เสี่ยง conflict) — ขั้น push ใช้ shallow clone สดใหม่ทุกรอบแทน (ดูหัวข้อ 8) |
| `WMB_Phayao/.venv/`, `WMB_Phayao/.git/` (ถ้ามี) | **ลบออกจาก Drive** เช่นกัน | เหตุผลเดียวกัน |
| `__pycache__/` ต่างๆ | ลบได้ ไม่บังคับ | ไฟล์ compiled เฉพาะ interpreter เดิม ไม่มีประโยชน์ ไม่กระทบอะไรถ้าไม่ลบ |
| `01_data/scripts and code/colab_migration/` | **สร้าง subfolder ใหม่ 1 อัน: `test_output/`** | ที่เก็บผลทดสอบระหว่าง migration ทั้งหมด (แยกจากโฟลเดอร์ output ของ pipeline เดิมบน Windows ที่ยังใช้งานจริงอยู่ — ดูหัวข้อ 2.2) |

**คำเตือนเรื่องการลบ**: ลบผ่านหน้าเว็บ Drive หรือ Windows Explorer เอง (ผมไม่ควร/ไม่สามารถรันคำสั่ง
ลบไฟล์ในโฟลเดอร์ที่ sync กับ Drive ให้ได้ เพราะเป็นการเปลี่ยนแปลงถาวรที่ควรเป็นคนกดเอง) เช็คให้แน่ใจ
ว่า sync เสร็จ (ไม่มีไอคอนกำลัง sync ค้าง) ก่อนลบ — **ทำเสร็จแล้ว 2026-07-19**

### 2.3 ข้อควรระวัง: Drive เป็น snapshot นิ่ง ไม่ sync กับ Windows อัตโนมัติ

**ยืนยันแล้ว (2026-07-19)**: การ copy ขึ้น Drive เป็นการ copy ครั้งเดียวแบบมือ — **Windows Task
Scheduler ที่ยังรัน `data_pipeline.py`/`sar_background_job.py`/`reservoir_daily_orchestration.py`
จริงทุกสัปดาห์/ทุกวัน เขียนผลลัพธ์ลงโฟลเดอร์เดิมบนเครื่อง Windows เท่านั้น ไม่ได้ sync เข้า Drive
เลย** ผลคือ:

- ไฟล์บน Drive (`pipeline/era5t_output/*.json`, `pipeline/logs/pipeline_log.txt` ที่ใช้เป็นเกณฑ์
  เทียบผลใน Phase ต่างๆ) เป็นภาพนิ่ง ณ วันที่ copy (2026-07-19) — **ใช้เป็นเกณฑ์เทียบผลได้ตามปกติ**
  (ค่าที่เคย log ไว้ไม่เปลี่ยนย้อนหลัง) แต่จะไม่มี log ใหม่ๆ ที่ Windows รันหลังจากนี้ปรากฏบน Drive
  ให้เทียบเพิ่มอีก
- ถ้าในอนาคตมีการ retrain โมเดล `.pkl` หรืออัปเดตไฟล์ reference (CSV ค่าคงที่ ฯลฯ) บนเครื่อง
  Windows **ต้อง copy ไฟล์นั้นขึ้น Drive ซ้ำด้วยมืออีกครั้ง** ไม่มีระบบ sync อัตโนมัติคอยทำให้ —
  ต้องจำเป็น manual step เพิ่มเข้า runbook (Phase 7) ด้วย
- Drive กับ Windows เป็นคนละชุดข้อมูลที่ **แยกกันเด็ดขาดจริง** (ไม่ใช่แค่แยกกันเชิง logical ตามกฎ
  "ห้ามแตะ" — แยกกันทางกายภาพเพราะไม่มี sync channel เลย) จึงไม่มีความเสี่ยงที่ Colab จะเขียนอะไรไป
  กระทบของจริงบน Windows โดยไม่ตั้งใจ (ปลอดภัยกว่าที่คาดไว้เดิม) แต่ก็หมายความว่าการรันคู่ขนาน
  (Windows + Colab) ในช่วง Phase 6 จะต้องเทียบผลจาก **GitHub repo ที่ทั้งสองฝั่ง push เข้าไป** เป็น
  จุดเทียบร่วมจริง ไม่ใช่เทียบจากไฟล์บน Drive

### 2.2 ทำไมต้องมี `test_output/` แยก (สำคัญ — กันของจริงพัง)

**ตอนนี้ Windows Task Scheduler ยังรัน `data_pipeline.py` จริงอยู่ทุกสัปดาห์** เขียนผลไปที่
`pipeline/era5t_output/`, `pipeline/logs/`, และท้ายสุด commit ขึ้น GitHub จริง — เว็บสาธารณะยัง
พึ่งพา flow นี้อยู่ 100% จนกว่าจะย้ายเสร็จ (Phase 5-6) และตัดสินใจ "cutover" อย่างเป็นทางการ

ดังนั้นระหว่างที่ยังทดสอบ (Phase 1-4) **ห้ามให้ Colab เขียนไฟล์ทับ/ปนกับโฟลเดอร์ output ของ Windows
เด็ดขาด** แม้จะเป็นแค่การ "อ่าน" ไฟล์ .grib/reference CSV ที่มีอยู่แล้วก็ทำได้ปกติ (read-only ไม่มี
ความเสี่ยง) แต่ผลลัพธ์ใหม่ทุกอย่างจาก Colab (JSON output, .grib ที่โหลดใหม่, log) ให้เขียนไปที่
`colab_migration/test_output/` เท่านั้นจนกว่าจะถึง Phase 6 (ตัดสินใจ cutover จริง)

### 2.4 ทำไมไม่แนะนำให้ "sync ทั้งโฟลเดอร์โปรเจกต์" เข้า Drive ตรงๆ (ย้ายที่ทำงานจริงไปอยู่ใต้ G:\)

มีทางเลือกคือย้าย working directory จริงของ Windows (`D:\maenaruea-water-web`) ไปอยู่ใต้
`G:\My Drive\...` เลย (ใช้ Google Drive for Desktop sync ต่อเนื่องอัตโนมัติ ไม่ต้อง copy มือ
อีก) — **ไม่แนะนำ** เพราะ:

1. **`.git` ที่ sync ต่อเนื่องเสี่ยง corrupt จริง** — เป็นปัญหาที่รู้กันดีของ sync client ทั่วไป
   (Google Drive/OneDrive/Dropbox) เพราะ git เขียนไฟล์ย่อยจำนวนมากแบบ atomic operation ที่ sync
   client ไม่ได้ออกแบบมารองรับ ถ้า sync ไปแทรกระหว่างที่ git กำลังเขียน อาจทำ repo พังได้ (ตรงกับ
   เหตุผลเดิมที่แนะนำให้ลบ `.git` ออกจาก Drive ไปแล้ว)
2. **Task Scheduler เขียนไฟล์รัวๆ ขณะ sync client ก็พยายามอ่าน/sync ไฟล์เดียวกัน** — เสี่ยง
   ไฟล์ล็อก/sync ไม่ทันจนได้ข้อมูลไม่ครบ โดยเฉพาะช่วงที่ pipeline กำลังเขียน `ml_features_live.csv`/
   ไฟล์ xlsx ทางการ
3. **ฝั่ง Colab เขียน/อ่านผ่าน Drive-mounted filesystem (FUSE) ช้าและไม่เสถียรกับไฟล์จำนวนมาก/
   เขียนถี่** — เป็นข้อจำกัดที่รู้กันของ Colab (ตรงกับเหตุผลเดิมที่แผนนี้ให้ทำ git push ผ่าน
   shallow clone สดใหม่ ไม่ใช่ผ่าน Drive)

**แนะนำแทน**: ให้ `D:\maenaruea-water-web` (มี `.git`/`.venv` จริง) เป็น working directory เดิมของ
Windows ต่อไปเหมือนเดิมไม่เปลี่ยน แล้วเพิ่ม**สคริปต์ mirror ทางเดียว** (เช่น `robocopy` แบบ
`/MIR /XD .git .venv __pycache__`) จาก `D:\maenaruea-water-web` ไปที่ Drive copy — ตั้งเป็น
Windows Task Scheduler งานใหม่ **แยกต่างหาก** (ไม่แก้ `run_*.bat` เดิมที่อยู่ใน `pipeline/` — ผิดกฎ
ห้ามแตะ) ให้รันเองอัตโนมัติหลังงาน pipeline หลักรันจบทุกวัน/สัปดาห์ ได้ผลเทียบเท่า "sync อัตโนมัติ"
ที่ต้องการ แต่ไม่มีความเสี่ยงข้อ 1-2 ด้านบน (ไฟล์ปลายทางเป็นแค่ copy พร้อมใช้ ไม่ใช่ live git tree
ที่ sync client มาแทรก) — ถ้าต้องการให้ผมเขียนสคริปต์นี้ให้ บอกได้เลย (จะเก็บไว้ใน
`colab_migration/` เพราะเป็นเรื่อง Colab migration โดยตรง ไม่ใช่แก้ pipeline เดิม)

### 2.5 `sync_to_drive.bat` — เขียนแล้ว (2026-07-19)

ไฟล์: `01_data/scripts and code/colab_migration/sync_to_drive.bat` — robocopy `/MIR` จาก
`D:\maenaruea-water-web` และ `D:\WMB_Phayao` ไปยัง Drive copy ทั้งคู่ (ไม่แตะไฟล์ต้นทางเลย
เป็น read-only จากมุมมอง `D:\`) ไม่ sync `.git`/`.venv`/`__pycache__` (`/XD`)

**เลือกใช้ได้ 2 แบบ — ไม่ต้องทำทั้งคู่**:
- **(ก) รันมือ**: ดับเบิลคลิกไฟล์นี้ก่อนเปิด Colab ทุกครั้งที่อยากได้ข้อมูลล่าสุดแน่ๆ (ปลอดภัยสุด
  ไม่มีความเสี่ยงชนกับ Task Scheduler งานอื่น เพราะคุณเป็นคนสั่งรันเองตอนที่รู้ว่าไม่มีงานอื่นค้าง)
- **(ข) ตั้ง Task Scheduler อัตโนมัติ**: รันคำสั่ง `schtasks` ที่อยู่ในคอมเมนต์ท้ายไฟล์
  `sync_to_drive.bat` เอง (ตั้งไว้ 08:15 ทุกวัน — หลัง `MaeNaRua_Reservoir_Daily_Orchestration`
  07:30 เสร็จแน่ๆ) ข้อควรระวัง: วันจันทร์มีโอกาสต่ำที่จะชนกับ `MaeNaRua_Pipeline_Weekly`/
  `MaeNaRua_SAR_Background_Job` (02:00/03:00) ถ้ารันช้ากว่าปกติมาก — ถ้าเกิดขึ้นได้แค่ snapshot
  ไม่ครบรอบเดียว ไม่ทำให้ไฟล์จริงบน `D:\` เสียหาย (robocopy อ่านจาก `D:\` เป็น source เท่านั้น)

Log การ sync แต่ละรอบอยู่ที่ `colab_migration/sync_to_drive.log` (เขียนทับทุกรอบ)

---

## 3. Notebook cells มาตรฐาน — ตั้งแต่ mount Drive จนรัน ERA5T ใหม่ "แบบจริง"

ใช้ notebook เดียวกันนี้ต่อไปเรื่อยๆ ทุก Phase (เพิ่ม cell ใหม่ต่อท้ายทีละ Phase ไม่ต้องเปิด
notebook ใหม่) ลำดับ cell ที่ต้องมีเสมอ (รันจากบนลงล่างทุกครั้งที่เปิด session ใหม่ เพราะ pip
install + mount ไม่ persist ข้าม session):

**Cell 1 — Mount Drive + ตั้ง path constants**
```python
from google.colab import drive
drive.mount('/content/drive')

import os

DRIVE_BASE = "/content/drive/MyDrive/Colab Notebooks/Mae_Na_Rua"
PROJECT_WEB = f"{DRIVE_BASE}/maenaruea-water-web"
PROJECT_WMB = f"{DRIVE_BASE}/WMB_Phayao"
PIPELINE_DIR = f"{PROJECT_WEB}/01_data/scripts and code/pipeline"          # อ่านอย่างเดียว ห้ามเขียน
COLAB_MIGRATION_DIR = f"{PROJECT_WEB}/01_data/scripts and code/colab_migration"
TEST_OUTPUT_DIR = f"{COLAB_MIGRATION_DIR}/test_output"

os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

for p in [PROJECT_WEB, PIPELINE_DIR, COLAB_MIGRATION_DIR]:
    print(p, "->", "OK" if os.path.exists(p) else "!! ไม่พบ ตรวจสอบ path/การ mount")
```

**Cell 2 — เช็ค `.venv`/`.git` ที่ยังไม่ได้ลบ (แค่เตือน ไม่ลบอัตโนมัติ)**
```python
for p in [f"{PROJECT_WEB}/.venv", f"{PROJECT_WEB}/.git",
          f"{PROJECT_WMB}/.venv", f"{PROJECT_WMB}/.git"]:
    if os.path.exists(p):
        print("ยังไม่ลบ:", p, "— ลบเองผ่าน Drive/Explorer ได้เลย ไม่กระทบสคริปต์")
```

**Cell 3 — ติดตั้ง dependency ของ ERA5T (ต้องรันใหม่ทุก session — pip install ไม่ persist)**
```python
!pip install -q cdsapi cfgrib eccodes ecmwflibs xarray
import eccodes
print("eccodes version:", eccodes.codes_get_api_version())
```

**Cell 4 — โหลด CDS credential เป็น `.cdsapirc`**

**ยืนยันแล้ว (2026-07-19): รอบก่อนใช้วิธีอัปโหลดไฟล์ `.cdsapirc` ตรงๆ** (ไม่ใช่ Colab Secrets) —
ข้อเสียของวิธีนี้คือดิสก์ของ Colab session (`/content`, `/root`) เป็น ephemeral ทุก session ใหม่
ต้องอัปโหลดไฟล์นี้ซ้ำทุกครั้งที่เปิด notebook ใหม่ (เพิ่มขั้นตอนมือทุกวันในระยะยาว ตาม runbook
Phase 7)

วิธีเดิม (อัปโหลดตรง — ใช้ต่อได้ ไม่ต้องเปลี่ยนถ้าไม่อยากยุ่ง):
```python
from google.colab import files
files.upload()  # เลือกไฟล์ .cdsapirc จากเครื่อง

import shutil
shutil.move("/content/.cdsapirc", "/root/.cdsapirc")
print("ย้าย .cdsapirc ไปที่ /root/ แล้ว")
```

**วิธีแนะนำ (ลดขั้นตอนมือทุกวันเหลือ 0 — ตั้งครั้งเดียว)**: เปิดไฟล์ `.cdsapirc` เดิมด้วย Notepad
copy 2 บรรทัด (`url:` กับ `key:`) ไปวางเป็น Colab Secret 2 ตัว (`CDSAPI_URL`, `CDSAPI_KEY` ผ่าน
ไอคอนกุญแจแถบซ้ายของ Colab) ครั้งเดียว จากนั้นใช้ cell นี้แทนได้ทุก session โดยไม่ต้องอัปโหลดไฟล์ซ้ำ
อีกเลย:
```python
from google.colab import userdata

cdsapi_url = userdata.get('CDSAPI_URL')
cdsapi_key = userdata.get('CDSAPI_KEY')

with open('/root/.cdsapirc', 'w') as f:
    f.write(f"url: {cdsapi_url}\nkey: {cdsapi_key}\n")
print("เขียน .cdsapirc แล้ว (ไม่ต้องอัปโหลดไฟล์อีก)")
```
(เลือกวิธีไหนก็ได้ — ทั้งสองวิธีให้ผลเหมือนกัน ต่างกันแค่ต้องอัปโหลดไฟล์มือทุกวันหรือไม่)

**Cell 5 — เพิ่ม path สำหรับ import โมดูลในขั้นต่อไป (เตรียมไว้ล่วงหน้าสำหรับ Phase 1+)**
```python
import sys
sys.path.insert(0, PIPELINE_DIR)          # import ตรงจากไฟล์ที่ไม่ต้องแก้เลย (เช่น gee_auth.py, mei_feature.py — ยืนยันทีละไฟล์ก่อนใช้จริง)
sys.path.insert(0, COLAB_MIGRATION_DIR)   # import ไฟล์ที่พอร์ตแล้ว (era5t_worker_colab.py ฯลฯ)
```

**Cell 6 — รัน ERA5T แบบ "จริง" (ผ่าน Drive ทั้งหมด ไม่ต้องอัปโหลดไฟล์มือ) — เทียบ decode-logic**

อ้างอิงไฟล์ .grib ของจริงที่มีอยู่แล้วบน Drive (จากการรันบน Windows ก่อนหน้า — อ่านอย่างเดียว):
```python
grib_ref = f"{PIPELINE_DIR}/era5t_output/era5t_week_202607_06-10.grib"
out_json = f"{TEST_OUTPUT_DIR}/era5t_week_2026-07-11_colab.json"

!python "{COLAB_MIGRATION_DIR}/era5t_worker_colab.py" \
    --as-of-date 2026-07-11 \
    --grib-in-week "{grib_ref}" \
    --out-json "{out_json}"

!cat "{out_json}"
```
ผลที่ต้องตรงกันเป๊ะ (เคยทดสอบผ่านแล้วรอบทดลอง — รอบนี้แค่เปลี่ยนวิธีเข้าถึงไฟล์เป็นผ่าน Drive):
`ET0_mm_week=0.3911, T_mean=27.6014, RH_pct=84.1158, VPD_kPa=0.5866, u2_ms=1.075, Rn_MJ=-0.0422`

**Cell 7 — ยิง CDS จริง เขียนผลลง Drive (ไม่ใช่ `/content` เฉยๆ แบบรอบทดลอง)**
```python
out_json_live = f"{TEST_OUTPUT_DIR}/era5t_live_{__import__('datetime').date.today().isoformat()}.json"

!python "{COLAB_MIGRATION_DIR}/era5t_worker_colab.py" \
    --as-of-date {__import__('datetime').date.today().isoformat()} \
    --out-json "{out_json_live}"

!cat "{out_json_live}"
```
(`.grib` ที่โหลดจาก CDS จะถูกเก็บไว้ข้าง `out_json_live` บน Drive ด้วยโดย default — ไฟล์เล็ก
~1-2KB ต่อรอบ ไม่ต้องกังวลเรื่อง storage)

---

### 3.1 Cell 8-9 — ตั้ง GEE Service Account (ทำครั้งเดียว เตรียมไว้ก่อน Phase 2)

**ห้ามวางเนื้อไฟล์ `.json` หรือ email ลงในแชทกับผม — เป็น credential ที่ควรอยู่แค่ใน Colab
Secrets ของคุณเท่านั้น** ทำตามนี้ในเบราว์เซอร์ตัวเอง:

1. เปิดไฟล์ `.json` ที่หาเจอด้วย Notepad → Ctrl+A, Ctrl+C (copy เนื้อทั้งไฟล์ทั้งหมด)
2. ใน Colab กดไอคอนรูปกุญแจ (🔑) แถบซ้าย → "Add new secret"
   - ชื่อ: `GEE_SA_KEY_JSON` → วางเนื้อ JSON ที่ copy มาเป็นค่า → เปิด toggle "Notebook access"
   - เพิ่มอีกตัว ชื่อ: `GEE_SA_EMAIL` → ค่าเป็น email ของ service account (รูปแบบ
     `xxx@xxx.iam.gserviceaccount.com` — หาได้จาก field `client_email` ในไฟล์ `.json` เดียวกัน
     ถ้าจำที่จดไว้ตอนสร้างไม่ได้) → เปิด toggle "Notebook access" เช่นกัน

**Cell 8 — ติดตั้ง `earthengine-api` + โหลด secret ตั้ง env var**
```python
!pip install -q earthengine-api

from google.colab import userdata
import os

gee_sa_key_json = userdata.get('GEE_SA_KEY_JSON')
gee_sa_email = userdata.get('GEE_SA_EMAIL')

gee_key_path = "/content/gee_sa_key.json"
with open(gee_key_path, "w") as f:
    f.write(gee_sa_key_json)

os.environ["GEE_SERVICE_ACCOUNT_EMAIL"] = gee_sa_email
os.environ["GEE_SERVICE_ACCOUNT_KEY"] = gee_key_path

print("ตั้ง env var แล้วสำหรับ:", gee_sa_email)
```

**Cell 9 — ทดสอบ `gee_auth.init_ee()` ตรงจาก `PIPELINE_DIR` (ไม่ต้อง copy ไฟล์นี้เลย — อ่านข้อ
4 ด้านล่างว่าทำไม)**
```python
import sys
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)

import gee_auth
mode = gee_auth.init_ee(gee_project="maenaruea-water-pipeline")
print("GEE auth mode:", mode)  # ต้องได้ "service_account" ถ้าตั้งค่าถูก
```
ถ้าได้ `mode == "personal_credential"` แปลว่า env var ยังไม่ถูกอ่านเจอ (เช็ค secret name/toggle
"Notebook access" อีกรอบ) ถ้า error ตรงๆ (เช่น "not registered") แปลว่า service account นี้ยังไม่ได้
ลงทะเบียนกับ Earth Engine (ดูขั้นตอนที่ 4 ใน docstring ของ `gee_auth.py` เอง —
`https://code.earthengine.google.com/register`)

---

## 4. หลักการพอร์ตแต่ละไฟล์ (ยึด pattern เดิมที่ได้ผลดีกับ ERA5T)

สำหรับทุกไฟล์ที่ยังไม่พอร์ต (Phase 1 เป็นต้นไป):

1. อ่านไฟล์ต้นฉบับให้ครบทั้งไฟล์ (ห้ามพอร์ตจากความจำ/เดา)
2. เช็คว่าไฟล์นี้มีจุดที่ "ผูกกับ Windows/environment เดิมจริงๆ" กี่จุด
3. **ถ้าไม่มีจุดผูกกับ environment เลย** (เช่น `gee_auth.py` — อ่านแล้วยืนยันว่าอ่านแค่ env var
   ทั่วไป): **import ตรงจาก `PIPELINE_DIR` ผ่าน Cell 5 ด้านบน ไม่ต้อง copy ไฟล์ซ้ำ**
4. **ถ้ามีจุดผูกกับ environment**: copy เข้า `colab_migration/<ชื่อไฟล์>_colab.py` แก้เฉพาะจุดนั้น
   ห้ามแก้สูตร/ค่าคงที่/logic ทางธุรกิจ เขียนสรุป diff ไว้ใน docstring แบบเดียวกับ
   `era5t_worker_colab.py`
5. หาผลทดสอบจริงบน Windows ที่มีอยู่แล้ว (จาก `pipeline/logs/pipeline_log.txt` หรือไฟล์ output ที่
   cache ไว้ใน `pipeline/`) มาเป็นเกณฑ์เทียบ — **อ่านอย่างเดียวจาก `PIPELINE_DIR`** ไม่เขียนทับ
6. รันบน Colab เขียนผลลง `TEST_OUTPUT_DIR` เทียบผล รายงานกลับก่อนไปโมดูลถัดไปเสมอ

---

## 5. Credential / Secrets

| Credential | ใช้กับ | สถานะ | แผน |
|---|---|---|---|
| CDS API key | ERA5T | **ใช้งานได้แล้ว** (ยืนยันจาก live fetch test 2026-07-19) | ยืนยันชื่อ Colab Secret ที่ใช้จริงกับผู้ใช้ (ดู Cell 4) |
| GEE Service Account (email + key .json) | CHIRPS, SAR (ผ่าน `gee_auth.py`) | ยังไม่ตั้งบน Colab | เก็บเนื้อ JSON เป็น Colab Secret (`GEE_SA_KEY_JSON`) + email (`GEE_SA_EMAIL`) เขียนลงไฟล์ temp ตอนเริ่ม session แล้วตั้ง env var `GEE_SERVICE_ACCOUNT_EMAIL`/`GEE_SERVICE_ACCOUNT_KEY` ชี้ไปที่ไฟล์นั้น — ไม่ต้องแก้ `gee_auth.py` เลย |
| GitHub PAT (scope `repo`) | ขั้น push ท้าย pipeline (Phase 6) | ยังไม่ตั้ง | เก็บเป็น Colab Secret (`GITHUB_PAT`) ใช้ตอน clone/push เท่านั้น |

**ต้องถามผู้ใช้ก่อนเริ่ม Phase 2 (CHIRPS)**: path ไฟล์ GEE service account `.json` (นอก repo ตาม
`gee_auth.py` docstring) เพื่อเอาเนื้อไฟล์ไปวางเป็น Colab Secret

---

## 6. ลำดับ Phase ที่เหลือ

**Phase 0 — ERA5T: เสร็จ business-logic แล้ว (ยืนยัน bit-exact กับ Windows) — รอทำ Cell 1-7 ด้าน
บนจริงเพื่อยืนยันว่า workflow ผ่าน Drive ใช้งานได้จริง ไม่ใช่แค่ manual upload**

**Phase 1 — MEI (`mei_feature.py`): อ่านไฟล์เต็มแล้ว (2026-07-19) — พอร์ตเป็น
`mei_feature_colab.py`** ผลตรงข้ามกับที่คาดไว้เล็กน้อย: **ไม่ใช่ zero-change** เพราะเจอจุดที่
`_get_logger()` เขียน log ไปที่ `SCRIPT_DIR / "logs" / "pipeline_log.txt"` เสมอ — ถ้า import
`mei_feature.py` ตรงจาก Drive-mirrored `pipeline/` ตามหลักการเดิม จะกลายเป็นเขียนทับ/ต่อท้ายไฟล์
log ของจริงที่ mirror มาจาก Windows (ผิดกฎข้อ 2.2) จึง copy มาเป็น
`colab_migration/mei_feature_colab.py` แก้แค่จุดเดียว: `LOG_DIR` จาก `SCRIPT_DIR / "logs"` เป็น
`SCRIPT_DIR / "test_output"` (เพราะไฟล์นี้อยู่ใน `colab_migration/` เอง log จึงไปลง
`colab_migration/test_output/mei_feature_colab_log.txt` แทน) ตรวจสอบ diff แล้วว่าไม่มีจุดอื่นต่างจาก
ต้นฉบับเลย (ยกเว้นตัดคอมเมนต์/docstring บางส่วนให้กระชับขึ้น ไม่กระทบพฤติกรรมโค้ด) dependency
(`pandas`, `requests`) ไม่มีปัญหาบน Colab (มักติดตั้งมาให้แล้ว)

**ค่าอ้างอิงจริงจาก Windows (จาก `pipeline/logs/pipeline_log.txt` รอบล่าสุด 2026-07-18)** สำหรับ
เทียบผล: `MEI=1.52, MEI_lag4=1.52, MEI_lag8=0.27, latest_actual_period=2026-06, is_stale=False,
stale_fallback_used=True, mei_reporting_lag_risk=False` — รันบน Colab วันนี้ (2026-07-19) ควรได้
ค่าเดียวกันทุกตัว (แค่ `data_age_days` เพิ่มขึ้น 1) เพราะ MEI เป็นข้อมูลรายเดือน ไม่น่ามีค่าใหม่มา
ระหว่างนี้ (`nino34_oni_latest` เป็นแค่ค่าเทียบเคียงเสริม อาจต่างกันได้บ้าง ไม่ใช่ตัวตัดสิน parity)

**Cell 10 — รัน MEI feature บน Colab**
```python
import sys
if COLAB_MIGRATION_DIR not in sys.path:
    sys.path.insert(0, COLAB_MIGRATION_DIR)

import mei_feature_colab
import json

result = mei_feature_colab.get_mei_feature()
print(json.dumps(result, indent=2, ensure_ascii=False))
```

**Phase 2 — CHIRPS (`chirps_feature.py`): อ่านไฟล์เต็มแล้ว (2026-07-19) — พอร์ตเป็น
`chirps_feature_colab.py`** เจอปัญหาเดียวกับ MEI (logger เขียนเข้า `pipeline/logs/`) แก้แบบ
เดียวกัน (เปลี่ยน `LOG_DIR` เป็น `SCRIPT_DIR / "test_output"`) — ตรวจแล้วว่า
`DEFAULT_HISTORICAL_CSV_PATH` (อ่านไฟล์ `Water_demand/active/ml_features_phase4.csv`) และการ
`import gee_auth` ข้างในฟังก์ชัน **ไม่ต้องแก้เลย** (path/sys.path resolve ถูกต้องอยู่แล้ว — ดู
docstring หัวไฟล์ `chirps_feature_colab.py` สำหรับรายละเอียด) GEE auth ตั้งไว้แล้วจาก Cell 8-9
(Phase ก่อนหน้า) ใช้ต่อได้เลยไม่ต้องตั้งใหม่

**หมายเหตุเรื่องการเทียบผล**: CHIRPS ของสัปดาห์ล่าสุด (`as_of` = วันนี้) เป็นข้อมูล **prelim**
ที่ทยอยอัปเดตทุกวัน (ยังไม่ใช่ final จนกว่าจะผ่าน ~50 วัน) ค่าที่ได้จาก Colab วันนี้จึง**ไม่ควรตรง
กับ log เก่าบน Windows เป๊ะ** (ข้อมูล prelim ของสัปดาห์เดียวกันจะสมบูรณ์ขึ้นเรื่อยๆ ตามวันที่ผ่านไป
ไม่ใช่บั๊ก) เกณฑ์เทียบผลที่ใช้ได้จริงคือ: (ก) ไม่มี `fetch_error`, (ข) `p_eff_mm` ต้องตรงตามสูตร
ที่คำนวณจาก `p_mm_week` เอง (`zone_A` = `max(0, P-5)*0.85`, `zone_B` = `P*0.8`), (ค) ค่าที่ได้
สมเหตุสมผลกับช่วงฤดูฝนของไทยตอนนี้

**Cell 11 — รัน CHIRPS feature บน Colab (ทั้ง 2 zone)**
```python
import sys
if COLAB_MIGRATION_DIR not in sys.path:
    sys.path.insert(0, COLAB_MIGRATION_DIR)

import chirps_feature_colab
import json

for zone in ("zone_A", "zone_B"):
    print(f"--- {zone} ---")
    print(json.dumps(chirps_feature_colab.get_chirps_feature(zone=zone), indent=2, ensure_ascii=False))
```

### 3.3 Cell 12-13 — Phase 3: SAR classification (ทดสอบ)

**Cell 12 — pip install (pin version ให้ตรง Windows เพื่อไม่ให้ pickle โมเดล/scaler พัง)**

```python
!pip install -q scikit-learn==1.9.0 rasterio==1.5.0 geopandas shapely joblib
```

รันแล้วเช็คว่าไม่มี error สีแดง (warning เรื่อง dependency conflict ของ Colab เอง เฉยได้ ไม่ต้อง
สนใจ) — ถ้าติด ให้ paste error กลับมาก่อนไปต่อ Cell 13

**Cell 13 — import ตรงจาก `pipeline/` (ไม่ต้อง copy ไฟล์) + เช็คว่าโหลดโมเดล/shapefile ได้**

```python
import sys
PIPELINE_DIR = "/content/drive/MyDrive/Colab Notebooks/Mae_Na_Rua/maenaruea-water-web/01_data/scripts and code/pipeline"
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)

import sar_classification as sar

print("RF_MODEL_PATH exists:", sar.RF_MODEL_PATH.exists())
print("RF_SCALER_PATH exists:", sar.RF_SCALER_PATH.exists())
print("ZONE_A_SHP_PATH exists:", sar.ZONE_A_SHP_PATH.exists())
print("ZONE_B_SHP_PATH exists:", sar.ZONE_B_SHP_PATH.exists())

rf = sar.load_rf_classifier()
print("model loaded OK:", type(rf["model"]).__name__, type(rf["scaler"]).__name__,
      "| n_features:", len(rf["feature_order"]))

zones = sar.load_zone_boundaries()
print("zone_A area_ha:", zones["zone_A"]["area_m2"] / 10000)
print("zone_B area_ha:", zones["zone_B"]["area_m2"] / 10000)
```

(2026-07-19 แก้บั๊ก — เดิม unpack เป็น tuple ผิด ทั้ง `load_rf_classifier()` และ
`load_zone_boundaries()` คืนค่าเป็น `dict` ไม่ใช่ tuple)

✅ Cell 13 ผ่านแล้ว (2026-07-19): model=RandomForestClassifier (n_estimators=600, n_features=86),
scaler=MinMaxScaler, zone_A=3472.8 ha, zone_B=1157.7 ha — เจอ `InconsistentVersionWarning`
(train ด้วย sklearn 1.8.0, Colab ใช้ 1.9.0) แต่ไม่ block, feature-count check ผ่าน

**Cell 14 — รันของจริง (`check_new_sar_image()` + `trigger_crop_classification()`)**

ก่อนรัน: override `SAR_RASTER_OUTPUT_DIR` เป็น runtime patch (ไม่แก้ source) ให้ raster ที่เขียนจริง
ไปลง `colab_migration/test_output/` แทน `01_data/gis/sar_rasters/` ตัวจริง และส่ง `marker_path`
custom เข้าไปทั้ง 2 ฟังก์ชัน (ฟังก์ชันมี parameter นี้ให้อยู่แล้ว) กัน gate ตัวจริงถูกแก้ — **การรันนี้
หนัก**: ดาวน์โหลด GeoTIFF composite 86 band ต่อ zone (ตามคอมเมนต์ในไฟล์ "นาทีถึงหลายนาที")

```python
from pathlib import Path
import json

TEST_OUTPUT_DIR = Path(COLAB_MIGRATION_DIR) / "test_output"
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sar.SAR_RASTER_OUTPUT_DIR = TEST_OUTPUT_DIR / "sar_rasters"
TEST_MARKER_PATH = TEST_OUTPUT_DIR / ".sar_last_classified_test"

sar_trigger = sar.check_new_sar_image(marker_path=TEST_MARKER_PATH)
print("sar_trigger:", sar_trigger)

if sar_trigger:
    result = sar.trigger_crop_classification(sar_trigger, marker_path=TEST_MARKER_PATH)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
else:
    print("ยังไม่มีภาพ S1 ใหม่ในช่วง 30 วัน หรือดึง GEE ไม่สำเร็จ — ดู log ด้านบน")
```

หมายเหตุ: `COLAB_MIGRATION_DIR` ต้องมีอยู่แล้วจาก Cell 5 (sys.path setup) — ถ้า error ว่าไม่มีตัวแปรนี้
ให้เช็คว่ารัน Cell 5 ไปแล้วในเซสชันนี้

**Phase 3 — SAR classification (`sar_classification.py`)**: อ่านไฟล์ครบ 1195 บรรทัดแล้ว
(2026-07-19) สรุปผล:

- **path โมเดลที่คุณให้มา (`Reservoir_inflow/active/Retrain/exported_models/`) ไม่ใช่โมเดลที่
  ไฟล์นี้ใช้** — ไฟล์นั้นมี `stage1_classifiers.pkl`, `stage2_regressors_all_models.pkl` ฯลฯ
  (โมเดล Two-Stage ของ Reservoir Inflow — ใช้กับ Phase 4 ทีหลัง ไม่ใช่ Phase 3)
  โมเดลจริงที่ `sar_classification.py` โหลด คือ `rf_model_v3b_final.pkl` +
  `rf_scaler_v3b_final.pkl` + `col_medians_v3b_final.pkl`/`.json` ซึ่งอยู่ที่
  `Water_demand/active/` — **เช็คแล้วมีไฟล์ครบอยู่บน Drive แล้ว** (โมเดลใหญ่ 117MB) ไม่ต้องหา/
  อัปโหลดเพิ่ม
- **ไม่มี environment coupling เลย** — ต่างจาก MEI/CHIRPS ไฟล์นี้ไม่มี `_get_logger()`/`LOG_DIR`
  ของตัวเอง (ใช้ `logging.getLogger("data_pipeline")` เฉยๆ ไม่ตั้ง handler เอง) และ
  `PROJECT_ROOT = Path(__file__).resolve().parents[3]` ได้ค่าเดียวกันไม่ว่าไฟล์จะอยู่ใน
  `pipeline/` หรือ `colab_migration/` (เพราะทั้งสองโฟลเดอร์อยู่ลึกเท่ากันใต้
  `01_data/scripts and code/`) → **สรุป: import ตรงจาก `PIPELINE_DIR` ได้เลย ไม่ต้อง copy ไฟล์
  เป็น `sar_classification_colab.py`** (เหมือน `gee_auth.py`)
- ฟังก์ชัน `trigger_crop_classification()` เขียนไฟล์ 2 จุด: marker `.sar_last_classified` และ
  raster ผลลัพธ์ `.tif` — ทั้งคู่อยู่ใต้ `01_data/gis/` (ไม่ใช่ `pipeline/`/`Water_demand/`/
  `Reservoir_inflow/` ที่ห้ามแตะ) และเพราะ Drive เป็น snapshot แยกจาก Windows จริง (ดูหัวข้อ 2.3)
  การเขียนนี้จะลงแค่บนสำเนา Drive ไม่กระทบไฟล์จริงบน Windows — ปลอดภัย แต่ต้องรู้ไว้ว่าเขียนจริง
  (ไม่ใช่แค่ log เฉยๆ แบบ MEI/CHIRPS)
- ต้องเช็คก่อนรันจริง: (ก) pip install `rasterio==1.5.0`, `scikit-learn==1.9.0`, `geopandas`,
  `shapely`, `joblib` บน Colab ได้ครบหรือไม่ (ข) โหลดโมเดล 117MB ผ่าน Drive-mount อาจช้า — พิจารณา
  copy ไปไว้ `/content` ก่อนถ้าช้าเกินไป (ค) GEE-heavy step (composite S2/S1 86 bands +
  getDownloadURL) ใช้เวลานานกว่า MEI/CHIRPS มาก — คาดว่าหลายนาที

**✅ ผลทดสอบจริง (2026-07-19, Cell 12-14)**: `status="ok"`, `errors=[]`,
`band_order_check.verified=true` (86/86 band ตรงเป๊ะ) โมเดลโหลดได้ (แค่ warning
`InconsistentVersionWarning` 1.8.0→1.9.0 ไม่ block) ทั้ง 2 zone classify สำเร็จ
(zone_A 86,813 pixel ในโซน, zone_B 28,945 pixel) `getDownloadURL()` single-shot เกิน 50MB
limit ทั้ง 2 zone แล้ว fallback ไป tile 2x2 อัตโนมัติตามที่โค้ดออกแบบไว้ — ทำงานถูกต้อง ไฟล์ raster
เขียนไปที่ `colab_migration/test_output/sar_rasters/` (ไม่ใช่ `01_data/gis/` ตัวจริง) และ marker
เขียนไปที่ `.sar_last_classified_test` (ไม่ใช่ gate ตัวจริง) ตามที่ override ไว้ — **ไม่กระทบไฟล์จริง
เลย** **Phase 3 ปิดจบ**

หมายเหตุนอกเหนือจากการย้าย Colab (ไม่ใช่บั๊กของการพอร์ต — เป็น data signal จริง): ผลรันนี้ flag
`sar_data_quality.risk_note` ว่า 12/19 สัปดาห์ว่างของรอบนี้ไม่ตรงกับ pattern ตอน train (สัปดาห์ที่
train มีข้อมูลจริงแต่รอบนี้ไม่มีภาพ S1) — ตัวเลข `zone_crop_area_ha` ที่ได้ (เช่น zone_A corn
+127.7% จาก baseline 2020) อาจได้รับผลกระทบจากจุดนี้ ควรพิจารณาแยกว่าเป็นเรื่อง data quality ของ
SAR รอบนี้ ไม่เกี่ยวกับการย้าย environment

**Phase 4 — Prediction models** (อ่าน `data_pipeline.py` เต็มไฟล์ 2452 บรรทัดแล้ว 2026-07-19)

- ฟังก์ชันที่เกี่ยวข้อง: `_wd_load_models()`/`_wd_build_feature_vector()`/`_wd_run_prediction()`
  (Water Demand two-stage: LGBMClassifier stage1 x [CatBoostRegressor+LGBMRegressor] stack
  stage2) และ `_ri_load_models()`/`_ri_build_feature_vector()`/`_ri_run_prediction()`
  (Reservoir Inflow hurdle: CatBoostClassifier stage1 x CatBoostRegressor stage2) — เรียกผ่าน
  `load_latest_model()` + `build_feature_vector()` + `run_prediction()` รวมทั้งสองระบบ
- **path โมเดลที่ `Reservoir_inflow/active/Retrain/exported_models/` (ที่ให้มาตอนแรกสำหรับ Phase
  3) จริงๆ ใช้ที่ Phase นี้แหละ** — แต่ path จริงที่โค้ดอ่านคือ `Reservoir_inflow/active/` ตรงๆ
  (ไม่ใช่ subfolder `Retrain/exported_models/`) ไฟล์ที่ต้องการ (`stage1_classifiers.pkl`,
  `stage1_thresholds.pkl`, `deployment_stage2_regressors.pkl`, `model_metadata.json`) มีอยู่ที่
  `Reservoir_inflow/active/` แล้ว (เช็คแล้วบน Drive) เช่นเดียวกับ Water Demand
  (`catboost_models.pkl`, `lightgbm_models.pkl`, `stage1_classifiers.pkl`,
  `stage1_thresholds.pkl`, `stack_weights.pkl` ที่ `Water_demand/active/`) — ไม่ต้องหา/อัปโหลดอะไรเพิ่ม
- **ไม่ต้องเดา version library** — `pipeline/requirements.txt` (comment ในไฟล์บอกตรงๆ ว่าเช็คจาก
  `.dist-info/METADATA` จริงบน Windows venv วันที่ 2026-07-04) ระบุ pin ไว้ครบ:
  `lightgbm==4.6.0`, `catboost==1.2.10`, `openpyxl==3.1.5` (`scikit-learn==1.9.0` ตรงกับที่ใช้ไปแล้ว
  Phase 3) — **ไม่ต้องติดตั้ง xgboost** (มีอยู่แค่ใน `stage2_regressors_all_models.pkl` ที่ไม่ใช่ไฟล์
  deployment จริง — `deployment_model_choice.json` เลือก CatBoost ทุก horizon แล้ว โค้ดไม่โหลดไฟล์นั้น)
- `data_pipeline.py` มี logger-coupling เหมือน MEI/CHIRPS (`LOG_DIR = SCRIPT_DIR / "logs"` เขียนลง
  `pipeline/logs/pipeline_log.txt` ตั้งแต่ import — ไม่ใช่ lazy) → **copy เป็น
  `colab_migration/data_pipeline_colab.py` แล้ว** (2026-07-19) แก้แค่ 2 บรรทัด (`LOG_DIR`/`LOG_FILE`
  → `test_output/`) ยืนยันด้วย `diff` ว่าไม่มีจุดอื่นเปลี่ยนเลย — ไฟล์นี้ใช้ต่อได้ทั้ง Phase 4
  (prediction functions) และ Phase 5 (orchestration functions `run_pipeline()`/`main()`) เพราะอยู่
  ไฟล์เดียวกัน
- `_fetch_era5t_via_subprocess()` (Windows-only, เรียก conda env แยก) **ไม่กระทบการทดสอบ Phase 4**
  เพราะ `_wd_build_feature_vector()`/`_ri_build_feature_vector()` มี fallback ไปใช้ static
  snapshot CSV ในตัวอยู่แล้วถ้า live path ยังไม่พร้อม (ปกติของ session ใหม่ที่ยังไม่มี
  `ml_features_live.csv`) — เก็บการแก้จุดนี้ไว้ทำตอน Phase 5 จริงๆ
- **Reference จริงจาก Windows** (`01_data/forecasting_results/latest.json`, รันจริง
  2026-07-18T08:51): `demand_zone_a` (static_snapshot, as_of 2024-W51): prob_active=0.757,
  magnitude=74491.68, final=56389.54 | `demand_zone_b`: prob_active=0.8434, magnitude=34055.14,
  final=28720.57 | `inflow` (live_monthly_account_files, as_of=2026-07-17): h1
  pred=3125.6, prob_zero=0.1145, stage_used=stage2_regressor, model=CatBoost — ใช้เทียบผลตอนรัน
  บน Colab (ไม่คาดหวัง bit-exact 100% เพราะ Drive เป็น snapshot ณ ตอน copy อาจมีไฟล์ "บัญชีน้ำ"
  รายเดือนเก่ากว่า D:\ ปัจจุบันเล็กน้อย แต่ Water Demand ส่วน static_snapshot ควรตรงเป๊ะเพราะเป็น
  ไฟล์ static เดียวกัน)

**Cell 15 — pip install:**

```python
!pip install -q catboost==1.2.10 lightgbm==4.6.0 openpyxl==3.1.5
```

**Cell 16 — import `data_pipeline_colab.py` (ต้อง sync ไฟล์นี้ขึ้น Drive ก่อน — ดูหมายเหตุ) + รันทำนายจริง:**

```python
import sys
if COLAB_MIGRATION_DIR not in sys.path:
    sys.path.insert(0, COLAB_MIGRATION_DIR)

import data_pipeline_colab as dp
import json

model = dp.load_latest_model()
features = dp.build_feature_vector(telemetry=[], crop_classification=None)
predictions = dp.run_prediction(model, features)
print(json.dumps(predictions, indent=2, ensure_ascii=False, default=str))
```

**หมายเหตุสำคัญก่อนรัน**: ไฟล์ `data_pipeline_colab.py` เพิ่งถูกสร้างบน `D:\...\colab_migration\`
(เครื่อง Windows จริง) — **ยังไม่อยู่บน Google Drive** ต้อง sync/อัปโหลดไฟล์นี้ 1 ไฟล์ขึ้น Drive
ก่อน (copy มือ หรือรัน `sync_to_drive.bat` ที่เขียนไว้แล้วในข้อ 7) ไม่งั้น Cell 16 จะ error
`ModuleNotFoundError` (ถ้า sync แล้วยัง error อยู่ — เจอจริง 2026-07-19 — สาเหตุคือ Python cache
`sys.path_importer_cache` ของ directory ตั้งแต่ตอนที่ไฟล์ยังไม่มี ต้องเรียก
`importlib.invalidate_caches()` ก่อน `import` ใหม่ ไม่ต้อง restart runtime)

**✅ ผลทดสอบจริง (2026-07-19, Cell 15-16) — ตรงกับ Windows เป๊ะ**: `demand_zone_a`
(prob=0.757, magnitude=74491.68, final=56389.54), `demand_zone_b` (prob=0.8434,
magnitude=34055.14, final=28720.57) ตรงกับ `latest.json` ของ Windows เป๊ะทุกตัวเลข (static
snapshot ไฟล์เดียวกัน คาดหวัง bit-exact แล้วได้ตรงจริง) — `inflow` h1 (pred=3125.6,
prob_zero=0.1145, threshold=0.5663, model=CatBoost) ตรงกับ Windows เป๊ะด้วย (gap_days ต่างกัน 1
วันเพราะรันคนละวัน ตามคาด ไม่ใช่บั๊ก) **Phase 4 ปิดจบ** — เจอ warning
`X does not have valid feature names` จาก LGBM (เกิดจากโค้ดเดิมแปลง DataFrame เป็น numpy array
ก่อนป้อนโมเดลอยู่แล้ว ไม่ใช่ปัญหาจาก Colab — เกิดเหมือนกันบน Windows)

**Phase 5 — Orchestration เต็มรูปแบบ (`data_pipeline.py`)** (เริ่ม 2026-07-19)

- แก้ `_fetch_era5t_via_subprocess()` ใน `data_pipeline_colab.py` แล้ว — เปลี่ยนจาก
  `subprocess.run([python_exe, script, ...])` เป็นเรียก `era5t_worker_colab.main(argv)` ตรงใน
  โปรเซสเดียวกัน (argv เดียวกันเป๊ะ แค่ไม่ผ่าน python.exe/subprocess) ยืนยันด้วย `diff` ว่าจุดอื่น
  ของไฟล์ 2452 บรรทัดไม่เปลี่ยนเลยนอกจาก LOG_DIR (บรรทัด 132-133) กับฟังก์ชันนี้ — **ยังไม่ทดสอบรัน
  จริงบน Colab**
- `ML_FEATURES_LIVE_CSV = SCRIPT_DIR / "ml_features_live.csv"` — ไม่ต้องแก้อะไรเพิ่ม เพราะ
  `SCRIPT_DIR` ของไฟล์ colab คือ `colab_migration/` อยู่แล้ว (แยกจาก `pipeline/ml_features_live.csv`
  โดยธรรมชาติ ไม่ต้อง redirect)
- **จุดที่ต้องระวังก่อนรัน `run_pipeline()`/`main()` เต็มรูปแบบ**: `save_results()` มี
  `output_path: Path = OUTPUT_PATH` เป็น default parameter (ผูกค่าตอน define ฟังก์ชัน ไม่ใช่ตอนเรียก)
  — **monkey-patch `dp.OUTPUT_PATH` ตอน runtime ใช้ไม่ได้กับจุดนี้** (ต่างจาก
  `SAR_RASTER_OUTPUT_DIR` ของ SAR ที่ lookup จาก module global ตรงในตัวฟังก์ชัน) ถ้าจะทดสอบ
  `run_pipeline()` เต็มรูปแบบโดยไม่เขียนทับ `01_data/forecasting_results/latest.json`/
  `03_website/assets/data/latest.json` ตัวจริงบน Drive ต้องเรียก `save_results(result,
  output_path=test_path, website_copy_path=test_path2)` ตรงๆ แทนการเรียกผ่าน `run_pipeline()`
  (ซึ่ง hardcode เรียก `save_results(result)` ไม่มี parameter ให้ override จากนอก) — แผน: ทดสอบ
  ทีละส่วนก่อน (`_fetch_era5t_via_subprocess()` เดี่ยวๆ, `_fetch_climate_features_step()`) แล้วค่อย
  เขียน wrapper เล็กๆ เทียบเท่า `run_pipeline()` แต่เรียก `save_results()` แบบ redirect เอง เป็น
  ขั้นสุดท้ายก่อนเชื่อ orchestration เต็มรูปแบบ

**✅ ทดสอบ `_fetch_era5t_via_subprocess()` เดี่ยวๆ ผ่านแล้ว (2026-07-19)** — เรียกจริงผ่าน CDS
(as_of=2026-07-19) ได้ค่าตรงกับ Phase 0 CLI test เป๊ะทุกตัวเลข (`ETo_mm_day=0.6108320735067327,
T_c=27.178674316406273, RH_pct=80.5745538173426, VPD_kPa=0.6998763513067603,
u2_ms=1.3971249333863356, Rn_MJ=-0.0365016`) ยืนยันว่าเปลี่ยนจาก subprocess เป็นเรียกตรงไม่กระทบ
ผลลัพธ์เลย

**✅ ทดสอบ `_fetch_climate_features_step()` ผ่านแล้ว (2026-07-19)** — MEI+CHIRPS (ทั้ง 2 zone)+
ERA5T รันจริงครบ, `errors=[]`, `rows_appended=2` เข้า `colab_migration/ml_features_live.csv`
(แยกจากไฟล์จริงของ `pipeline/` โดยธรรมชาติ) `data_status="partial"` (CHIRPS ยัง prelim + ERA5T
สัปดาห์นี้มีแค่ 1/7 วัน — ปกติของสัปดาห์ปัจจุบันที่ยังไม่ปิด ไม่ใช่บั๊ก) `prediction_readiness`
blocked ทั้ง 2 zone เพราะเป็นแถวแรกที่เพิ่งเขียน (ต้องสะสม 12 สัปดาห์ต่อเนื่องก่อน live path จะพร้อม
— ตรงกับ pattern เดียวกับที่เห็นใน Windows log จริง ไม่ใช่ความผิดพลาดจากการย้าย)

**✅ ทดสอบ orchestration เต็มรูปแบบผ่านแล้ว (2026-07-19)** — รัน wrapper เทียบเท่า `run_pipeline()`
(telemetry mock → climate features → SAR cache read → load models → build features → predict →
save) ครบทุก step `status="ok"`, `errors=[]` เขียนผลไปที่ `colab_migration/test_output/
latest_test.json` (ไม่แตะไฟล์จริงบน Drive) ผลทำนายตรงกับ Windows เป๊ะทั้งหมด (เหมือน Phase 4 —
Water Demand bit-exact, Reservoir Inflow h1 ตรงเป๊ะ, gap_days ต่างกันแค่เพราะวันที่รันต่างกัน)
**Phase 5 ปิดจบ** — เจอบั๊กเล็กน้อยระหว่างทดสอบ 2 จุด (ไม่ใช่บั๊กของโค้ด pipeline): (1) `TypeError`
จาก `TEST_OUTPUT_DIR` เป็น string ไม่ใช่ Path ใน session ตอนนั้น แก้ด้วย `Path(TEST_OUTPUT_DIR)`
(2) พิมพ์ชื่อตัวแปรผิดตอนก่อนหน้า (`crf` vs `rf` ใน Phase 3) — ทั้งสองเป็นบั๊กของโค้ดทดสอบที่ผมเขียน
ให้ ไม่ใช่โค้ด `data_pipeline.py`/`data_pipeline_colab.py`

**สรุป Phase 5**: `data_pipeline_colab.py` (copy จาก `data_pipeline.py` แก้ 2 จุด: LOG_DIR +
`_fetch_era5t_via_subprocess()`) ทำงานได้ครบทุก step ของ orchestration จริงบน Colab ตรงกับ Windows
ทุกตัวเลขที่เทียบได้ เหลือแค่ Phase 6 (git push ไปที่ repo จริง + ตัดสินใจ cutover) และ Phase 7
(เขียน runbook รันประจำวัน) ก่อนพร้อมใช้งานจริง

**Notebook**: บันทึกไว้ที่ `G:\My Drive\Colab Notebooks\Mae_Na_Rua\maenaruea_pipeline_colab.ipynb`
(ยืนยันแล้ว 2026-07-19) — ใช้ path นี้อ้างอิงใน runbook (Phase 7)

**Phase 6 — Git push + ตัดสินใจ cutover**: shallow clone repo ด้วย `GITHUB_PAT` → เขียน
`latest.json` ลง working tree → commit + push — **จุดนี้คือจุดที่ต้องตัดสินใจร่วมกันว่าจะปิด Windows
Task Scheduler ของ `data_pipeline.py`/`sar_background_job.py` เมื่อไหร่** (แนะนำ: รันคู่กันสัก
1-2 สัปดาห์ก่อน เทียบผลจริงให้แน่ใจ ค่อยปิดของ Windows)

**Repo ยืนยันแล้ว (2026-07-19)**: `https://github.com/mpdox30/maenarua-water-web.git` — สร้างเป็น
repo ว่างเปล่าบน GitHub (ไม่ initialize README/.gitignore) เครื่อง Windows (`D:\maenaruea-water-web`
ที่มี `.git` จริง) ตั้ง `git remote add origin` ไปที่ repo เดียวกันนี้แล้วด้วย (ทำแทนแล้วผ่านคำสั่งตรง
ไม่ต้องใช้ credential ใดๆ) — **แบ่งหน้าที่ชัดเจน**: ผู้ใช้ push โค้ด/HTML ที่แก้เอง (เช่น
`git push -u origin master` รอบแรก) จากเครื่อง Windows ตามปกติ ส่วน Colab (ด้านล่าง) auto-push
**เฉพาะ 3 ไฟล์ข้อมูลที่ pipeline ผลิตทุกวัน** เท่านั้น ไม่แตะไฟล์อื่นเลย กันชนกับงานแก้เว็บที่ทำเอง

**✅ ตั้ง `GITHUB_PAT` เป็น Colab Secret เสร็จแล้ว (2026-07-19)** — ทำเองในเบราว์เซอร์ตามที่แนะนำ
(สร้างที่ https://github.com/settings/tokens scope `repo`)

**Cell 17 — Phase 6: push ไฟล์ข้อมูลรายวันขึ้น GitHub (รันหลัง Cell 16 + หลัง
`daily_update_colab.py` ของ WMB_Phayao เสร็จทั้งคู่ในแต่ละวัน)**

```python
from google.colab import userdata
import subprocess, os, shutil
from pathlib import Path
from datetime import datetime

GITHUB_PAT = userdata.get('GITHUB_PAT')
GITHUB_REPO_URL = f"https://{GITHUB_PAT}@github.com/mpdox30/maenarua-water-web.git"

PUSH_CLONE_DIR = "/content/repo_push"     # ephemeral — clone สดใหม่ทุกรอบ ไม่ผูกกับ Drive .git ใดๆ
GIT_USER_NAME = "Mae Na Rua Pipeline (Colab)"
GIT_USER_EMAIL = "mp.dox69@gmail.com"

# เฉพาะไฟล์ที่ Colab ดูแล auto-push — ไฟล์อื่น (HTML/โค้ด) ผู้ใช้ push เองจาก Windows
FILES_TO_PUSH = [
    "03_website/assets/data/latest.json",            # data_pipeline_colab.py (Water Demand/Inflow)
    "03_website/assets/data/flood_latest.json",       # WMB_Phayao daily_update_colab.py
    "03_website/assets/data/reservoir_inflow.json",   # WMB_Phayao daily_update_colab.py (เพิ่ม 2026-07-19)
]

def push_daily_data():
    if os.path.exists(PUSH_CLONE_DIR):
        shutil.rmtree(PUSH_CLONE_DIR)
    subprocess.run(["git", "clone", "--depth", "1", GITHUB_REPO_URL, PUSH_CLONE_DIR],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", PUSH_CLONE_DIR, "config", "user.name", GIT_USER_NAME], check=True)
    subprocess.run(["git", "-C", PUSH_CLONE_DIR, "config", "user.email", GIT_USER_EMAIL], check=True)

    changed = []
    for rel in FILES_TO_PUSH:
        src = Path(PROJECT_WEB) / rel
        dst = Path(PUSH_CLONE_DIR) / rel
        if not src.exists():
            print(f"ข้าม (ไม่พบไฟล์ต้นทางบน Drive): {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        changed.append(rel)

    if not changed:
        print("ไม่มีไฟล์ให้ push เลย — เช็ค PROJECT_WEB/path ก่อน")
        return

    subprocess.run(["git", "-C", PUSH_CLONE_DIR, "add"] + changed, check=True)
    diff = subprocess.run(["git", "-C", PUSH_CLONE_DIR, "diff", "--cached", "--stat"],
                         capture_output=True, text=True)
    if not diff.stdout.strip():
        print("ข้อมูลไม่เปลี่ยนจากรอบก่อน (เทียบกับ HEAD ของ repo) — ไม่ commit/push")
        return

    msg = f"Auto-update: pipeline data {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    subprocess.run(["git", "-C", PUSH_CLONE_DIR, "commit", "-m", msg], check=True)
    result = subprocess.run(["git", "-C", PUSH_CLONE_DIR, "push", "origin", "HEAD:master"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print("push สำเร็จ:", msg)
    else:
        print("push ไม่สำเร็จ:")
        print(result.stderr[-800:])

push_daily_data()
```

หมายเหตุ: `HEAD:master` ตรงกับชื่อ branch จริงบนเครื่อง Windows (`master` — เช็คแล้ว 2026-07-19 ไม่ใช่
`main`) ถ้าภายหลังมีการ rename branch บน GitHub ต้องแก้บรรทัดนี้ให้ตรงด้วย

**✅ ทดสอบรันจริงผ่านแล้ว (2026-07-19)** — ลำดับที่ทดสอบจริง: รัน `daily_update_colab.py` (WMB_Phayao,
ไม่ offline) → export `flood_latest.json` + `reservoir_inflow.json` (740 วัน ถึง 2026-07-20) สำเร็จ →
รัน Cell 17 → clone repo สด, copy 3 ไฟล์, commit, push → **"push สำเร็จ: Auto-update: pipeline data
2026-07-19 17:38"** ยืนยันบน GitHub แล้วว่ามี commit ใหม่จริง **Phase 6 ปิดจบ** (เหลือแค่ตัดสินใจ
cutover — ดูหัวข้อ 6 ด้านบน — รันคู่ขนาน Windows + Colab สักพักก่อนปิด Windows Task Scheduler)

**Phase 7 — Daily routine (runbook)**: สรุปเป็นเอกสารสั้นๆ ว่าทุกวันต้องเปิด notebook ไหน กด
"Runtime > Run all" ใช้เวลาประมาณเท่าไหร่ (รวม queue delay ของ CDS/GEE) ต้องเช็คอะไรถ้ารันไม่ผ่าน

---

## 6.1 ส่วนเสริม — รวม `WMB_Phayao/09_live/daily_update.py` เข้า notebook เดียวกัน (2026-07-19)

คนละโปรเจกต์จาก Mae Na Rua แต่เขียนผลลง `03_website/assets/data/flood_latest.json` ของเว็บเดียวกัน
(ตาม `config.json` → `website_data_path`) จึงรวมมารันใน `maenaruea_pipeline_colab.ipynb` เดียวกัน
ตามที่ผู้ใช้ขอ — WMB_Phayao มีกฎเดียวกัน "ห้ามแก้ไฟล์เดิม" จึง copy ไปที่
`WMB_Phayao/colab_migration/` (โฟลเดอร์ใหม่ระดับเดียวกับ `06_scripts/`/`09_live/`):

- `config_colab.json` (copy จาก `09_live/config.json`) — แก้แค่ `website_data_path` จาก
  `D:/maenaruea-water-web/...` (Windows path ตรงๆ) เป็น path Drive-mounted
- `daily_update_colab.py` (copy จาก `09_live/daily_update.py`, 500 บรรทัด) — แก้แค่ 1 บรรทัดที่โหลด
  CFG ให้อ่าน `config_colab.json` แทน — ยืนยันด้วย `diff` ว่าไม่มีจุดอื่นเปลี่ยน `wmb_engine.py`
  (โมเดลหลักที่ import) ใช้แค่ numpy/pandas/json ไม่มี geospatial library หนักๆ
- รันแบบเดิมทุกประการ (เป็น script ไม่ใช่ module ที่ import) ผ่าน
  `!WMB_ROOT="{PROJECT_WMB}" python3 "{WMB_COLAB_MIGRATION_DIR}/daily_update_colab.py" --offline`
  — เพิ่ม `PROJECT_WMB`/`WMB_COLAB_MIGRATION_DIR` ใน Cell 1 (mount Drive) ให้ครบ

**✅ ทดสอบผ่านแล้ว (2026-07-19, `--offline`)**: รันครบ 7 วันพยากรณ์กว๊าน + WMB flood flags +
export `flood_latest.json` + rebuild `Reservoirs_inflow.html` — เทียบกับผลจริงที่ Windows รันเช้า
วันเดียวกัน (`09_live/output/flood_latest.json`/`forecast_2026-07-19.csv` ตัวจริง) **ตรงกันเป๊ะทุก
ทศนิยม** (เช่น 2026-07-20: level=390.717, p10=390.668, p90=390.775 ตรงกันทั้งคู่) ธงรวม "watch"
ตรงกัน — ปิดจบส่วนนี้

**✅ ทดสอบโหมดดึงข้อมูลจริงผ่านแล้วด้วย (2026-07-19, ไม่มี `--offline`)**: ดาวน์โหลด log 10 นาที
จาก Google Drive จริงสำเร็จ (1337 KB, รวม 42,625 แถวสะสม) พยากรณ์ 7 วัน + เขียนผลครบทุกไฟล์ + export
เว็บสำเร็จ ไม่มี error ค่าต่างจากรอบ `--offline` เล็กน้อย (เช่น 390.71 vs 390.72) เพราะข้อมูลสดใหม่กว่า
snapshot เดิมที่ cache ไว้ — เป็นพฤติกรรมที่ถูกต้อง ไม่ใช่บั๊ก **WMB_Phayao integration ปิดจบสมบูรณ์**
ทั้งสองโปรเจกต์ (Mae Na Rua pipeline + WMB_Phayao daily_update) รันจาก
`maenaruea_pipeline_colab.ipynb` เดียวกันได้แล้วครบทุกโหมด

---

## 7. นอกขอบเขตของแผนนี้ (ยังไม่ย้าย)

- `reservoir_daily_orchestration.py`, `monitoring_data_builder.py` — ยังอยู่ Windows Task
  Scheduler เหมือนเดิม
- Tier 1 (Telemetry ทุก 10-15 นาที ผ่าน Apps Script push JSON เข้า GitHub ตรง) — ยังไม่เริ่มทำ

---

## 8. เช็กลิสต์ก่อนเริ่มแต่ละ Phase

- [x] **Cell 4**: ยืนยันแล้ว — รอบก่อนใช้อัปโหลดไฟล์ `.cdsapirc` ตรงๆ (ดูหัวข้อ 3 Cell 4 สำหรับทั้ง
  2 วิธี — ใช้วิธีเดิมต่อได้ หรือเปลี่ยนเป็น Colab Secret เพื่อลดขั้นตอนมือทุกวัน)
- [ ] **ก่อน Phase 2 (CHIRPS)**: ได้เนื้อไฟล์ GEE service account `.json` + email มาวางเป็น Colab
  Secret แล้ว
- [x] **ก่อน Phase 3 (SAR)**: ยืนยัน path โมเดล `.pkl` บน Drive (`Water_demand/active/` — ไม่ใช่
  path ที่ให้มาตอนแรก) + version scikit-learn 1.9.0 / rasterio 1.5.0 ที่ train ไว้บน Windows —
  เสร็จ (2026-07-19)
- [ ] **ก่อน Phase 4 (Prediction)**: เหมือน Phase 3 แต่เป็น version ของ
  CatBoost/XGBoost/LightGBM
- [x] ยืนยัน remote ของ repo จริงที่จะ push แล้ว (2026-07-19): `https://github.com/mpdox30/maenarua-water-web.git`
  — ตั้ง `origin` ให้เครื่อง Windows แล้วด้วย
- [x] push ครั้งแรกจากเครื่อง Windows สำเร็จแล้ว (2026-07-19/20) — เจอปัญหาไฟล์โมเดล 2 ไฟล์ใน
  `Water_demand/active/` เกินลิมิต 100MB ของ GitHub ระหว่างทาง แก้ด้วย `git filter-repo` ลบออกจาก
  ประวัติทั้งหมด (ไฟล์บนดิสก์ไม่กระทบ แค่เลิก track ใน git + เพิ่มใน `.gitignore`) แล้ว push สำเร็จ —
  `master` sync กับ `origin/master` เรียบร้อย
- [x] **ก่อน Phase 6 (Git push)**: มี GitHub PAT (scope `repo`) เป็น Colab Secret ชื่อ `GITHUB_PAT`
  แล้ว + ทดสอบ push จริงสำเร็จ (2026-07-19)
- [ ] **ก่อน Phase 6 (cutover)**: ตกลงกันว่าจะรันคู่ขนาน (Windows + Colab) นานแค่ไหนก่อนปิด
  Windows Task Scheduler ของ `data_pipeline.py`
