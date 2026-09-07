# Daily Runbook — รัน pipeline บน Colab ทุกวัน

เขียนขึ้น 2026-07-19/20 (Phase 7 ตาม `COLAB_MIGRATION_PLAN.md`) — สรุปสั้นๆ ว่าทุกวันต้องทำอะไรบ้าง
ให้ข้อมูลเว็บ (`03_website/assets/data/*.json`) อัปเดตถึงวันปัจจุบัน ไม่ต้องเปิด `COLAB_MIGRATION_PLAN.md`
ทั้งไฟล์ (ไฟล์นั้นคือ log ประวัติการย้าย ยาวและเป็นอดีต ไฟล์นี้คือของที่ใช้จริงทุกวัน)

**สถานะปัจจุบัน (อัปเดต 2026-08-12 — ตัดสินใจแล้ว)**: **Colab คือช่องทางหลัก** สำหรับรันพยากรณ์ +
push ข้อมูลขึ้นเว็บจริง (ทำตาม runbook นี้ทุกวัน) **Windows Task Scheduler เปลี่ยนบทบาทเป็น backup +
ทวนสอบ** (ยังรันตามปกติ ไม่ต้องปิด แต่ไม่ใช่ตัวหลักที่ทำให้เว็บอัปเดตอีกต่อไป)

**2026-09-08 เปลี่ยนสถาปัตยกรรมสำคัญ**: Cell 1 เปลี่ยนจาก "mount Drive แล้วชี้ path ตรงเข้า
Drive-mounted mirror" เป็น **`git clone` ทั้ง 2 repo (`maenaruea-water-web` + `WMB_Phayao`) ตรงจาก
GitHub ทุก session** — ตัด dependency จาก `sync_to_drive.bat` ที่ต้องรอ Windows sync ก่อนถึงจะรันได้จริง
ออกไปทั้งหมด (ยกเว้นไฟล์ใหญ่ 2 กลุ่มที่ .gitignore กันไว้ — model .pkl ของ Water Demand กับ raster
ภูมิประเทศของ WMB_Phayao — ยังต้อง mount Drive สำหรับ 2 กลุ่มนี้ แต่ไม่เปลี่ยนรายวัน ไม่ใช่ตัวบล็อก)
เซลล์ #7.5 (sync `ml_features_live.csv` จาก GitHub) **ถูกลบออกแล้ว** เพราะ git clone ทั้ง repo ตอน
Cell 1 ได้ไฟล์นี้สดอยู่แล้วในตัว ไม่ต้อง sync แยก และเซลล์ #8.5 (push `ml_features_live.csv`) กับ
เซลล์ push หลัก (เดิมชื่อ Cell 17) **ถูกรวมเป็นเซลล์ push เดียว** (ดูตารางด้านล่าง — เลขเซลล์อ้างอิงจาก
`maenaruea_pipeline_colab_CLEANED.ipynb` ปัจจุบัน 14 เซลล์)

---

## ก่อนเริ่ม (ทำครั้งเดียว ไม่ต้องทำซ้ำทุกวัน — เช็คว่าเสร็จหมดแล้ว)

- [x] Colab Secrets ตั้งแล้ว: `CDSAPI_URL`/`CDSAPI_KEY` (หรืออัปโหลด `.cdsapirc` มือ), `GEE_SA_KEY_JSON`,
  `GEE_SA_EMAIL`, `GITHUB_PAT`
- [x] Repo GitHub: `https://github.com/mpdox30/maenarua-water-web.git` (remote ตั้งทั้งเครื่อง Windows
  และใช้ push จาก Colab แล้ว)
- [x] Notebook: `G:\My Drive\Colab Notebooks\Mae_Na_Rua\maenaruea_pipeline_colab.ipynb`

---

## ทุกวัน: ลำดับที่ต้องรัน

Colab session ใหม่ทุกครั้งไม่มี state ค้าง (pip install/mount ไม่ persist ข้าม session) ต้องรันตาม
ลำดับนี้จากบนลงล่างเสมอ — **ห้ามกด "Runtime > Run all"** เพราะจะรันเซลล์ทดสอบเก่าๆ (ERA5T manual
test, GEE setup, SAR test, MEI/CHIRPS test เดี่ยวๆ) ที่ไม่จำเป็นต้องรันซ้ำทุกวันไปด้วย ช้าโดยใช่เหตุ
— แนะนำรันเฉพาะเซลล์ที่ระบุด้านล่างทีละเซลล์แทน (ใช้ Ctrl+Enter ไล่ทีละอัน)

### ขั้นตอน

| # | เซลล์ (index ใน `maenaruea_pipeline_colab_CLEANED.ipynb`) | ทำอะไร | จำเป็นทุกวัน? |
|---|---|---|---|
| 1 | **Cell 1** — git clone + bridge ไฟล์ใหญ่ | `git clone` ทั้ง `maenaruea-water-web` + `WMB_Phayao` เข้า `/content/repos/` สดจาก GitHub, mount Drive แค่เพื่อ bridge ไฟล์ใหญ่ที่ .gitignore กันไว้ (model .pkl / raster ภูมิประเทศ), ตั้ง `PROJECT_WEB`/`PIPELINE_DIR`/`COLAB_MIGRATION_DIR`/`PROJECT_WMB`/`WMB_COLAB_MIGRATION_DIR` | ✅ ทุกวัน (แรกสุดเสมอ) |
| 2 | **Cell 2** (`pip install cdsapi cfgrib eccodes ecmwflibs xarray`) | ติดตั้ง dependency ERA5T | ✅ ทุกวัน (ไม่ persist ข้าม session) |
| 3 | **Cell 3** (โหลด `.cdsapirc`) | ตั้ง credential CDS จาก Colab Secret (`CDSAPI_URL`/`CDSAPI_KEY`) | ✅ ทุกวัน |
| 4 | **Cell 4** (sys.path setup) | เพิ่ม `PIPELINE_DIR`/`COLAB_MIGRATION_DIR` เข้า `sys.path` | ✅ ทุกวัน |
| 5 | **Cell 5** (โหลด GEE secret → env var) | ตั้ง `GEE_SERVICE_ACCOUNT_EMAIL`/`GEE_SERVICE_ACCOUNT_KEY` จาก Colab Secret | ✅ ทุกวัน |
| 6 | **Cell 6** (`pip install catboost==1.2.10 lightgbm==4.6.0 openpyxl==3.1.5 rasterio`) | ติดตั้ง dependency โมเดลทำนาย | ✅ ทุกวัน |
| 7 | **Cell 7** (`pip install requests openpyxl plotly`) | ติดตั้ง dependency ของ `daily_update_colab.py` (WMB_Phayao) | ✅ ทุกวัน |
| 8 | **Cell 9** — รัน WMB_Phayao `daily_update_colab.py` | พยากรณ์น้ำท่วม 7 วัน + inflow อ่าง 5 อ่าง → export `flood_latest.json`/`reservoir_inflow.json` | ✅ ทุกวัน |
| 9 | **Cell 10** — รัน `sar_background_job.py` (Colab-side) | เช็ค/classify ภาพ SAR ใหม่ถ้าถึงรอบ (แยกจาก GitHub Actions SAR job ที่พอร์ตไปคู่ขนานแล้ว) | ✅ ทุกวัน (เช็คเฉยๆ ถ้ายังไม่ถึงรอบ) |
| 10 | **Cell 11** — รัน Mae Na Rua หลัก (`run_pipeline()`) | climate features (MEI/CHIRPS/ERA5T) → อ่าน SAR ที่แคชไว้ → ทำนาย Water Demand + Reservoir Inflow → เขียน `latest.json` | ✅ ทุกวัน |
| 11 | **Cell 12** — push ผลลัพธ์ขึ้น GitHub (รวม 1 เซลล์แล้ว) | commit+push `ml_features_live.csv` + `latest.json` + `flood_latest.json` + `reservoir_inflow.json` + `flood_depth_forecast.png` ในรอบ pull/commit/push เดียว | ✅ ทุกวัน (ท้ายสุดเสมอ) |

**2026-09-08 ลบออกแล้ว** (ไม่มีในเซลล์ปัจจุบันอีกต่อไป): เซลล์ #7.5 เดิม (sync `ml_features_live.csv`
จาก GitHub แยกก่อนรัน) — ไม่จำเป็นแล้วเพราะ Cell 1 clone ทั้ง repo สดอยู่แล้ว, เซลล์ #8.5 เดิม (push
`ml_features_live.csv` แยก) — รวมเข้ากับเซลล์ push หลักแล้ว (ดูแถวที่ 11 ด้านบน)

### เซลล์ #7 — รัน WMB_Phayao daily_update_colab.py

```python
import subprocess, os

r = subprocess.run(
    ["python3", f"{WMB_COLAB_MIGRATION_DIR}/daily_update_colab.py"],
    env={**os.environ, "WMB_ROOT": PROJECT_WMB},
    capture_output=True, text=True,
)
print(r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
```

**ห้ามใส่ `--offline`** (นั่นคือโหมดทดสอบ ไม่ดึงข้อมูลจริง) ปล่อยว่างไว้แบบนี้เพื่อดึง gdrive_log
สดจริงทุกวัน — เช็ค output ว่ามี `export เว็บ: ...flood_latest.json` และ `reservoir_inflow.json
อัปเดตแล้ว: ... (N วัน ถึง <วันนี้>)` ทั้งคู่ก่อนไปขั้นต่อไป (ถ้าวันที่ในไฟล์ไม่ใช่วันนี้ ดูหัวข้อ
"เช็ค troubleshoot" ด้านล่าง)

### เซลล์ #7.5 เดิม — ลบออกแล้ว (2026-09-08)

ก่อนหน้านี้เซลล์นี้ clone repo แยกต่างหากเพื่อดึง `ml_features_live.csv` สดจาก GitHub มาวางก่อนรัน
Cell 8 (กัน Colab สะสมประวัติแยกจากเครื่อง Windows) — **ไม่จำเป็นอีกต่อไป** เพราะตอนนี้ Cell 1 เอง
`git clone` ทั้ง repo `maenaruea-water-web` สดจาก GitHub อยู่แล้วทุก session ไฟล์นี้จึงสดอยู่แล้วในตัว
ไม่ต้องมีเซลล์ sync แยกอีก

### เซลล์ #8 — รัน Mae Na Rua หลัก

```python
import importlib
import data_pipeline_colab as dp
importlib.reload(dp)   # กันแคชกรณีเคย import ไฟล์เก่าไว้ใน session นี้แล้ว

result = dp.run_pipeline()
print("status:", result.status)
print("step_status:", result.step_status)
print("errors:", result.errors)
```

`run_pipeline()` เขียนผลไปที่ path จริงอยู่แล้วโดย default (`OUTPUT_PATH`/`WEBSITE_DATA_COPY_PATH` —
ไม่ต้อง override เป็น `test_output` อีกต่อไป เพราะผ่าน Phase 6 มาแล้ว) ถ้า `status` ออกมาเป็น
`"ok"` แปลว่าทุก step ผ่านหมด ถ้าเป็น `"partial_failure"` ให้ดู `step_status`/`errors` ว่า step ไหนพัง
(ปกติ pipeline นี้ออกแบบให้แต่ละ step ล้มเหลวแยกจากกันได้ ไม่ทำให้ step อื่นพังตาม เช่น ถ้า SAR ยังไม่มี
ผลลัพธ์เลยจะได้ `sar_classification: "no_data_yet"` ซึ่งไม่ใช่ error บล็อกการทำนาย)

### เซลล์ #8.5 เดิม — รวมเข้ากับเซลล์ push หลักแล้ว (2026-09-08)

ก่อนหน้านี้แยก push `ml_features_live.csv` (เซลล์นี้) กับ push 4 ไฟล์หลัก (`push_daily_data()`,
เดิมชื่อ Cell 17) เป็นคนละ clone คนละรอบ commit กัน — **รวมเป็นเซลล์เดียวแล้ว** เพราะตอนนี้ `PROJECT_WEB`
(จาก Cell 1) เป็น git clone อยู่แล้วในตัว ไม่ต้อง clone ซ้ำสองรอบ

### เซลล์ push หลัก (Cell 12 ใน notebook ปัจจุบัน) — push ทุกไฟล์ในรอบเดียว

```python
from google.colab import userdata
import subprocess
from pathlib import Path
from datetime import datetime

GITHUB_PAT = userdata.get('GITHUB_PAT')
_repo_url_with_token = f"https://{GITHUB_PAT}@github.com/mpdox30/maenarua-water-web.git"
subprocess.run(["git", "-C", PROJECT_WEB, "remote", "set-url", "origin", _repo_url_with_token], check=True)
subprocess.run(["git", "-C", PROJECT_WEB, "config", "user.name", "Mae Na Rua Pipeline (Colab)"], check=True)
subprocess.run(["git", "-C", PROJECT_WEB, "config", "user.email", "mp.dox69@gmail.com"], check=True)

FILES_TO_PUSH = [
    "01_data/scripts and code/pipeline/ml_features_live.csv",
    "03_website/assets/data/latest.json",
    "03_website/assets/data/flood_latest.json",
    "03_website/assets/data/reservoir_inflow.json",
    "03_website/assets/data/flood_depth_forecast.png",
]
# ... (add เฉพาะไฟล์ที่มีอยู่จริง, commit+push พร้อม retry เมื่อ non-fast-forward สูงสุด 3 ครั้ง —
# เนื้อหาเต็มดู Cell 12 ใน maenaruea_pipeline_colab_CLEANED.ipynb โดยตรง)
```

---

## รันเสร็จแล้ว รู้ได้ยังไงว่าสำเร็จจริง

เช็ค 3 อย่างนี้หลังรันครบทุกเซลล์:

1. เซลล์ #8 (`run_pipeline()`) print `status: ok` (หรืออย่างน้อย errors ว่างเปล่า/ไม่มี error ที่ critical)
2. เซลล์ push หลัก (Cell 12) print `push สำเร็จ: Auto-update: pipeline data <วันที่ วันนี้>`
3. เปิด https://github.com/mpdox30/maenarua-water-web/commits/master ดูว่ามี commit ใหม่วันนี้จริง
   (ชื่อ commit ขึ้นต้นด้วย "Auto-update: pipeline data")

ถ้าเว็บจริง (GitHub Pages หรือที่ hosting ใช้อยู่) อ่านข้อมูลจาก repo นี้โดยตรง หน้าเว็บจะอัปเดตตาม
commit ใหม่อัตโนมัติ (ไม่ต้อง build/deploy เพิ่ม เพราะเป็นแค่ static JSON ที่ fetch ตรง)

---

## Troubleshooting

| อาการ | สาเหตุที่เป็นไปได้ | แก้ยังไง |
|---|---|---|
| `ModuleNotFoundError` ตอน import | ลืมรัน pip install เซลล์ก่อนหน้า (Cell 2/6/7) ใน session นี้ | รัน cell pip install ที่ตกไปใหม่ |
| `NameError: PROJECT_WEB not defined` | ยังไม่ได้รัน Cell 1 ใน session นี้ | รัน Cell 1 ก่อนเสมอ |
| Cell 1 print `!! ไม่พบ ตรวจสอบ git clone` | เน็ตหลุดตอน clone หรือ repo URL/สิทธิ์เข้าถึงมีปัญหา (repo public ไม่ต้อง auth ก็จริง แต่ยังต้องมีเน็ต) | รัน Cell 1 ใหม่อีกรอบ ถ้ายังไม่ผ่านเช็ค error message เต็มจาก `subprocess.run` |
| Cell 1 print `!! ไม่พบไฟล์ใหญ่บน Drive` | ไฟล์ model .pkl (Water Demand) หรือ raster ภูมิประเทศ (WMB) ที่ยังต้องพึ่ง Drive ถูกย้าย/ลบ/ยังไม่เคยอัปโหลดไว้ที่ path เดิม | เช็ค path บน Drive ตรงกับที่ Cell 1 อ้างอิงไหม (`DRIVE_BASE` เดิม) — ปกติไฟล์กลุ่มนี้ไม่ควรหายเองถ้าไม่มีใครลบ |
| `daily_update_colab.py` error หา path ไม่เจอ | ยังไม่ได้รัน Cell 1 สำเร็จในเซสชันนี้ (git clone ยังไม่เสร็จ) | รัน Cell 1 ใหม่ให้ผ่านก่อน แล้วค่อยรัน Cell 9 ต่อ (2026-09-08: ไม่ต้องพึ่ง `sync_to_drive.bat`/Drive sync จาก Windows อีกแล้ว — Cell 1 clone สดจาก GitHub เองทุก session) |
| วันที่ในไฟล์ที่ export ไม่ใช่วันนี้ (ช้าไป 1 วัน) | ข้อมูล gdrive_log/CHIRPS/ERA5T ของวันนี้ยังมาไม่ครบตอนที่รัน (ปกติถ้ารันเช้าเกินไป ข้อมูลกลางคืนยังไม่ sync) | รันใหม่อีกทีช่วงสาย/บ่าย หรือปล่อยผ่าน (ระบบมี fallback/interpolation รองรับอยู่แล้ว ไม่ block) |
| `push ไม่สำเร็จ` ในเซลล์ push หลัก | token GITHUB_PAT หมดอายุ/scope ไม่พอ, หรือมีคนอื่น push ทับ branch เดียวกันระหว่างนั้น | อ่าน error message ที่ print ออกมา (`result.stderr`) ถ้าเป็นเรื่อง auth ต้องสร้าง PAT ใหม่ตั้งเป็น secret ใหม่ ถ้าเป็นเรื่อง non-fast-forward ให้รันเซลล์ใหม่อีกรอบ (มี retry อัตโนมัติในตัวอยู่แล้ว 3 ครั้ง) |
| `sar_classification`: `"no_data_yet"` ทุกวันไม่เปลี่ยน | ทั้ง Cell 10 (Colab เอง) และ GitHub Actions SAR job ยังไม่เคยรันสำเร็จ/ยังไม่ถึงรอบ (`min_days_between_runs=30`) | เช็ค output ของ Cell 10 หรือแท็บ Actions ของ repo ว่า SAR job รันผ่านไหม |

---

## หมายเหตุทางเทคนิค (ไม่กระทบผลลัพธ์ แต่ควรรู้ไว้)

`data_pipeline_colab.py` เรียก `import mei_feature`/`import chirps_feature` แบบชื่อเดิม (ไม่ใช่
`mei_feature_colab`/`chirps_feature_colab`) ภายในตัวมันเอง เพราะเป็นไฟล์ copy จาก `data_pipeline.py`
เกือบทั้งดุ้น (แก้แค่ 2 จุดตามที่บันทึกไว้ใน `COLAB_MIGRATION_PLAN.md` Phase 5) ผลคือตอนรันจริงบน Colab
จะ resolve ไปเจอไฟล์ต้นฉบับใน `PIPELINE_DIR` ซึ่งไฟล์เหล่านั้นเขียน log ไปที่ `pipeline/logs/pipeline_log.txt`
**2026-09-08 อัปเดต**: ตั้งแต่เปลี่ยนเป็น git clone (แทน Drive-mounted mirror) ไฟล์ log นี้เขียนอยู่ใน
`/content/repos/maenaruea-water-web/...` ซึ่งเป็น session ชั่วคราวของ Colab เอง (ไม่ใช่ Drive อีกต่อไป)
หายไปเองตอนจบ session ไม่กระทบไฟล์จริงบน Windows เลยเหมือนเดิม และไฟล์นี้ก็ไม่ถูก push ขึ้น GitHub
อยู่แล้ว (อยู่ใน `.gitignore`) ไม่ต้องแก้อะไรเพิ่ม เป็นแค่ side-effect ที่ไม่มีอันตราย

---

## เมื่อจะปิด Windows Task Scheduler จริง (cutover)

รอให้รันคู่ขนานแล้วเทียบผล `latest.json`/`flood_latest.json` ระหว่าง Windows กับที่ Colab push
ขึ้น GitHub ตรงกันสม่ำเสมอสัก 1-2 สัปดาห์ก่อน ค่อยปิด task `MaeNaRua_Pipeline_Weekly` ใน Windows
Task Scheduler (คำสั่ง `schtasks /delete /tn "<ชื่อ task>" /f`)

**2026-09-08 อัปเดต**: `reservoir_daily_orchestration.py`/`monitoring_data_builder.py`/
`sar_background_job.py` พอร์ตไปรันบน **GitHub Actions** แล้วด้วย (`.github/workflows/`) — Windows
ยังรัน 3 ตัวนี้ขนานเป็น shadow/backup อยู่ (ยังไม่ปิด รอพิสูจน์ว่า Actions เสถียรพอก่อน — ดู
`PLAN_github_actions_detail_20260907.md`) ไม่เกี่ยวกับ cutover ของ Colab ในไฟล์นี้โดยตรง
