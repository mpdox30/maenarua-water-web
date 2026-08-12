# Daily Runbook — รัน pipeline บน Colab ทุกวัน

เขียนขึ้น 2026-07-19/20 (Phase 7 ตาม `COLAB_MIGRATION_PLAN.md`) — สรุปสั้นๆ ว่าทุกวันต้องทำอะไรบ้าง
ให้ข้อมูลเว็บ (`03_website/assets/data/*.json`) อัปเดตถึงวันปัจจุบัน ไม่ต้องเปิด `COLAB_MIGRATION_PLAN.md`
ทั้งไฟล์ (ไฟล์นั้นคือ log ประวัติการย้าย ยาวและเป็นอดีต ไฟล์นี้คือของที่ใช้จริงทุกวัน)

**สถานะปัจจุบัน (อัปเดต 2026-08-12 — ตัดสินใจแล้ว)**: **Colab คือช่องทางหลัก** สำหรับรันพยากรณ์ +
push ข้อมูลขึ้นเว็บจริง (ทำตาม runbook นี้ทุกวัน) **Windows Task Scheduler เปลี่ยนบทบาทเป็น backup +
ทวนสอบ** (ยังรันตามปกติ ไม่ต้องปิด แต่ไม่ใช่ตัวหลักที่ทำให้เว็บอัปเดตอีกต่อไป) ทั้งสองฝั่งอ่าน/เขียนไฟล์
เดียวกันจริงผ่าน git (ไม่ใช่คนละสำเนาที่ไม่ sync กัน — ดูเซลล์ #7.5/#8.5 ด้านล่างสำหรับ
`ml_features_live.csv` โดยเฉพาะ ซึ่งเป็นไฟล์ที่เคยมีปัญหานี้มาก่อน)

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

| # | เซลล์ | ทำอะไร | จำเป็นทุกวัน? |
|---|---|---|---|
| 1 | **Cell 1** (mount Drive + path constants) | mount Drive, ตั้ง `PROJECT_WEB`/`PIPELINE_DIR`/`COLAB_MIGRATION_DIR`/`PROJECT_WMB`/`WMB_COLAB_MIGRATION_DIR` | ✅ ทุกวัน (แรกสุดเสมอ) |
| 2 | **Cell 3** (`pip install cdsapi cfgrib eccodes ecmwflibs xarray`) | ติดตั้ง dependency ERA5T | ✅ ทุกวัน (ไม่ persist ข้าม session) |
| 3 | **Cell 4** (โหลด `.cdsapirc`) | ตั้ง credential CDS — ใช้วิธี Colab Secret (`CDSAPI_URL`/`CDSAPI_KEY`) จะได้ไม่ต้องอัปโหลดไฟล์มือทุกวัน | ✅ ทุกวัน |
| 4 | **Cell 5** (sys.path setup) | เพิ่ม `PIPELINE_DIR`/`COLAB_MIGRATION_DIR` เข้า `sys.path` | ✅ ทุกวัน |
| 5 | **Cell 8** (โหลด GEE secret → env var) | ตั้ง `GEE_SERVICE_ACCOUNT_EMAIL`/`GEE_SERVICE_ACCOUNT_KEY` จาก Colab Secret | ✅ ทุกวัน |
| 6 | **Cell 15** (`pip install catboost==1.2.10 lightgbm==4.6.0 openpyxl==3.1.5`) | ติดตั้ง dependency โมเดลทำนาย | ✅ ทุกวัน |
| 7 | **เซลล์ใหม่ (ด้านล่าง) — รัน WMB_Phayao (พยากรณ์น้ำท่วม + inflow อ่าง)** | ดึงข้อมูลสด + พยากรณ์กว๊าน 7 วัน + export `flood_latest.json`/`reservoir_inflow.json` | ✅ ทุกวัน |
| 7.5 | **เซลล์ใหม่ (ด้านล่าง, 2026-08-12) — sync `ml_features_live.csv` จาก GitHub** | ดึงไฟล์ล่าสุดจาก GitHub มาวางก่อนรัน กัน Colab สะสมประวัติแยกจากเครื่อง Windows | ✅ ทุกวัน (ก่อน Cell 8 เสมอ) |
| 8 | **เซลล์ใหม่ (ด้านล่าง) — รัน Mae Na Rua หลัก (`run_pipeline()`)** | climate features (MEI/CHIRPS/ERA5T) → อ่าน SAR ที่แคชไว้ → ทำนาย Water Demand + Reservoir Inflow → เขียน `latest.json` | ✅ ทุกวัน |
| 8.5 | **เซลล์ใหม่ (ด้านล่าง, 2026-08-12) — push `ml_features_live.csv` กลับขึ้น GitHub** | commit+push ไฟล์เดียวนี้แยกจาก Cell 17 | ✅ ทุกวัน (ต่อจาก Cell 8 ทันที) |
| 9 | **Cell 17** (`push_daily_data()`) | push 3 ไฟล์ข้อมูลขึ้น GitHub (`latest.json`/`flood_latest.json`/`reservoir_inflow.json`) | ✅ ทุกวัน (ท้ายสุดเสมอ) |

**ไม่ต้องรันทุกวัน** (เป็นเซลล์ทดสอบตอน migration เท่านั้น ปิดจบไปแล้ว): Cell 2, 6, 7 (ERA5T manual
test), Cell 9 (GEE auth test — รันได้เฉยๆ ถ้าอยากเช็คว่า secret ยังอ่านได้ปกติ), Cell 10/11 (MEI/CHIRPS
เดี่ยวๆ), Cell 12–14 (SAR classification test — **หนักมาก โหลด GeoTIFF หลายนาที ห้ามรันทุกวันโดยไม่จำเป็น**),
Cell 16 (Phase 4 prediction เดี่ยวๆ ไม่มี climate/SAR — ใช้ `run_pipeline()` แทนซึ่งครบกว่า)

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

### เซลล์ #7.5 (ใหม่ 2026-08-12) — sync ml_features_live.csv จาก GitHub ก่อนรัน

**เหตุผลที่ต้องมี**: Colab เป็นช่องทางหลักที่ push ข้อมูลขึ้นเว็บแล้ว (ตัดสินใจ 2026-08-12) แต่เดิม
`data_pipeline_colab.py::ML_FEATURES_LIVE_CSV` ชี้ไปที่ไฟล์บน Drive คนละไฟล์กับที่ repo/เว็บใช้จริง
(`01_data/scripts and code/pipeline/ml_features_live.csv`) ทำให้ Colab สะสมประวัติแยกไม่ sync กัน
ทุกวัน — เคยทำให้ข้อมูลเกือบหายจริงมาแล้ว (ดูบทสนทนา 2026-08-12) เซลล์นี้แก้ด้วยการ "ดึงไฟล์ล่าสุดจาก
GitHub มาวางที่ path ที่ `dp` จะเขียน/อ่านจริงก่อนรัน Cell 8 เสมอ" ให้ทั้ง 2 ระบบ (เครื่อง Windows +
Colab) มองไฟล์เดียวกันเป๊ะ ผ่าน git แทนที่จะเป็นคนละสำเนา — ต้องรันเซลล์นี้**ทุกครั้งก่อน Cell 8**

**หมายเหตุ 2026-08-12 (แก้บั๊ก)**: เซลล์นี้ต้อง `import data_pipeline_colab as dp` เอง (ห้ามพึ่ง Cell 8
import ไว้ให้ เพราะเซลล์นี้รัน**ก่อน** Cell 8) — เวอร์ชันแรกที่ให้ไปลืมบรรทัดนี้ ทำให้เจอ
`NameError: name 'dp' is not defined` ถ้าเคยเจอ error นี้ ให้แทนที่โค้ดเซลล์เดิมด้วยเวอร์ชันนี้:

```python
import subprocess, shutil, importlib
from pathlib import Path

import data_pipeline_colab as dp
importlib.reload(dp)   # กันแคชกรณีเคย import ไฟล์เก่าไว้ใน session นี้แล้ว (เซลล์นี้รันก่อน Cell 8
                        # จึงต้อง import เองตรงนี้ ไม่ใช่พึ่ง Cell 8 import ให้)

ML_FEATURES_SYNC_DIR = "/content/repo_sync_mlfeatures"
if Path(ML_FEATURES_SYNC_DIR).exists():
    shutil.rmtree(ML_FEATURES_SYNC_DIR)
subprocess.run(
    ["git", "clone", "--depth", "1", "https://github.com/mpdox30/maenarua-water-web.git", ML_FEATURES_SYNC_DIR],
    check=True, capture_output=True, text=True,
)

_canonical_src = Path(ML_FEATURES_SYNC_DIR) / "01_data/scripts and code/pipeline/ml_features_live.csv"
_local_dst = dp.ML_FEATURES_LIVE_CSV  # path จริงที่ data_pipeline_colab.py เขียน/อ่านตอนรัน pipeline

if _canonical_src.exists():
    _local_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_canonical_src, _local_dst)
    print(f"sync แล้ว: GitHub ({_canonical_src.stat().st_size} bytes) -> {_local_dst}")
else:
    print("[WARN] ไม่พบไฟล์บน GitHub เลย -- ข้าม (Cell 8 จะสร้างไฟล์ใหม่เอง ถ้านี่คือรันครั้งแรกจริงๆ)")
```

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

### เซลล์ #8.5 (ใหม่ 2026-08-12) — push ml_features_live.csv กลับขึ้น GitHub

รันต่อจาก Cell 8 ทันที (ก่อนไป Cell 17) — ใช้ clone เดียวกับเซลล์ #7.5 (`ML_FEATURES_SYNC_DIR`)
เพื่อ commit เฉพาะไฟล์นี้แยกจาก `push_daily_data()` ของ Cell 17 (คนละไฟล์ คนละรอบ commit)

```python
from google.colab import userdata
import subprocess
from pathlib import Path
from datetime import datetime

GITHUB_PAT = userdata.get('GITHUB_PAT')
_repo_url_with_token = f"https://{GITHUB_PAT}@github.com/mpdox30/maenarua-water-web.git"
subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "remote", "set-url", "origin", _repo_url_with_token], check=True)
subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "config", "user.name", "Mae Na Rua Pipeline (Colab)"], check=True)
subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "config", "user.email", "mp.dox69@gmail.com"], check=True)

_rel_path = "01_data/scripts and code/pipeline/ml_features_live.csv"
_dst_in_clone = Path(ML_FEATURES_SYNC_DIR) / _rel_path
_dst_in_clone.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(dp.ML_FEATURES_LIVE_CSV, _dst_in_clone)

subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "add", _rel_path], check=True)
_diff = subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "diff", "--cached", "--stat"], capture_output=True, text=True)
if not _diff.stdout.strip():
    print("ไม่มีอะไรเปลี่ยน (สัปดาห์นี้ push ไปแล้วในรอบก่อน หรือยังไม่มีสัปดาห์ใหม่) -- ไม่ commit/push")
else:
    _msg = f"Auto-update: ml_features_live.csv {datetime.now().strftime('%Y-%m-%d %H:%M')} (Colab)"
    subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "commit", "-m", _msg], check=True)
    _result = subprocess.run(["git", "-C", ML_FEATURES_SYNC_DIR, "push", "origin", "HEAD:master"], capture_output=True, text=True)
    if _result.returncode == 0:
        print("push สำเร็จ:", _msg)
    else:
        print("push ไม่สำเร็จ (อาจมีเครื่อง Windows push ทับพร้อมกันพอดี -- รันเซลล์ #7.5+#8.5 ใหม่อีกรอบ):")
        print(_result.stderr[-800:])
```

**ถ้า push ไม่สำเร็จเพราะ non-fast-forward** (เครื่อง Windows push ไฟล์เดียวกันพอดีระหว่างที่ Colab
กำลังรัน — เกิดได้ยากแต่เป็นไปได้ ทั้งสองฝั่ง pull-then-push แบบปลอดภัยอยู่แล้วไม่ force ทับกัน) แค่รัน
เซลล์ #7.5 ใหม่ (sync ของล่าสุดมา) แล้วรัน #8.5 ซ้ำ **ไม่ต้องรัน Cell 8 ใหม่** (ผลทำนายรอบนี้ยังใช้ได้
แค่ต้อง sync ไฟล์ก่อน push เฉยๆ)

---

## รันเสร็จแล้ว รู้ได้ยังไงว่าสำเร็จจริง

เช็ค 3 อย่างนี้หลังรันครบทุกเซลล์:

1. เซลล์ #8 print `status: ok` (หรืออย่างน้อย errors ว่างเปล่า/ไม่มี error ที่ critical)
2. เซลล์ #9 (`push_daily_data()`) print `push สำเร็จ: Auto-update: pipeline data <วันที่ วันนี้>`
3. เปิด https://github.com/mpdox30/maenarua-water-web/commits/master ดูว่ามี commit ใหม่วันนี้จริง
   (ชื่อ commit ขึ้นต้นด้วย "Auto-update: pipeline data")

ถ้าเว็บจริง (GitHub Pages หรือที่ hosting ใช้อยู่) อ่านข้อมูลจาก repo นี้โดยตรง หน้าเว็บจะอัปเดตตาม
commit ใหม่อัตโนมัติ (ไม่ต้อง build/deploy เพิ่ม เพราะเป็นแค่ static JSON ที่ fetch ตรง)

---

## Troubleshooting

| อาการ | สาเหตุที่เป็นไปได้ | แก้ยังไง |
|---|---|---|
| `ModuleNotFoundError` ตอน import | ลืมรัน pip install เซลล์ก่อนหน้า (Cell 3/15) ใน session นี้ | รัน cell pip install ที่ตกไปใหม่ |
| `NameError: PROJECT_WEB not defined` | ยังไม่ได้รัน Cell 1 ใน session นี้ | รัน Cell 1 ก่อนเสมอ |
| `daily_update_colab.py` error หา path ไม่เจอ / ไฟล์เก่าเกินคาด | ยังไม่ได้ sync `D:\WMB_Phayao`/`D:\maenaruea-water-web` ขึ้น Drive ล่าสุด (Drive เป็น snapshot นิ่ง ไม่ auto-sync) | ไปรัน `sync_to_drive.bat` ที่เครื่อง Windows ก่อน แล้วค่อยกลับมารัน Colab ต่อ (ถ้าตั้ง Task Scheduler อัตโนมัติของ sync ไว้แล้ว — ดู `sync_to_drive.bat` หัวข้อ 2.5 — ข้ามได้) |
| วันที่ในไฟล์ที่ export ไม่ใช่วันนี้ (ช้าไป 1 วัน) | ข้อมูล gdrive_log/CHIRPS/ERA5T ของวันนี้ยังมาไม่ครบตอนที่รัน (ปกติถ้ารันเช้าเกินไป ข้อมูลกลางคืนยังไม่ sync) | รันใหม่อีกทีช่วงสาย/บ่าย หรือปล่อยผ่าน (ระบบมี fallback/interpolation รองรับอยู่แล้ว ไม่ block) |
| `push ไม่สำเร็จ` ใน Cell 17 | token GITHUB_PAT หมดอายุ/scope ไม่พอ, หรือมีคนอื่น push ทับ branch เดียวกันระหว่างนั้น | อ่าน error message ที่ print ออกมา (`result.stderr`) ถ้าเป็นเรื่อง auth ต้องสร้าง PAT ใหม่ตั้งเป็น secret ใหม่ ถ้าเป็นเรื่อง non-fast-forward ให้รันเซลล์ใหม่อีกรอบ (clone สดใหม่จะดึง HEAD ล่าสุดมาเอง) |
| `sar_classification`: `"no_data_yet"` ทุกวันไม่เปลี่ยน | `sar_background_job.py` (แยกอยู่ Windows Task Scheduler เดิม ไม่ได้ย้ายมา Colab) ยังไม่เคยรันสำเร็จ หรือ Drive ยังไม่ sync ผลล่าสุด | เช็คที่เครื่อง Windows ว่า `sar_background_job.py` รันผ่านไหม แล้ว sync ขึ้น Drive |

---

## หมายเหตุทางเทคนิค (ไม่กระทบผลลัพธ์ แต่ควรรู้ไว้)

`data_pipeline_colab.py` เรียก `import mei_feature`/`import chirps_feature` แบบชื่อเดิม (ไม่ใช่
`mei_feature_colab`/`chirps_feature_colab`) ภายในตัวมันเอง เพราะเป็นไฟล์ copy จาก `data_pipeline.py`
เกือบทั้งดุ้น (แก้แค่ 2 จุดตามที่บันทึกไว้ใน `COLAB_MIGRATION_PLAN.md` Phase 5) ผลคือตอนรันจริงบน Colab
จะ resolve ไปเจอไฟล์ต้นฉบับใน `PIPELINE_DIR` (อ่านอย่างเดียวปกติ) ซึ่งไฟล์เหล่านั้นเขียน log ไปที่
`pipeline/logs/pipeline_log.txt` **บนสำเนา Drive เท่านั้น** — ไม่กระทบไฟล์จริงบน Windows เลย (Drive
เป็น snapshot แยกทางกายภาพ ไม่ sync ย้อนกลับ) และไฟล์ log นี้ก็ไม่ถูก push ขึ้น GitHub อยู่แล้ว (อยู่ใน
`.gitignore`) — เขียนทิ้งเปล่าๆ ทุกวัน แล้วโดนเขียนทับกลับเป็นของ Windows ทุกครั้งที่ `sync_to_drive.bat`
รันรอบถัดไป ไม่ต้องแก้อะไรเพิ่ม เป็นแค่ side-effect ที่ไม่มีอันตราย

---

## เมื่อจะปิด Windows Task Scheduler จริง (cutover)

รอให้รันคู่ขนานแล้วเทียบผล `latest.json`/`flood_latest.json` ระหว่าง Windows กับที่ Colab push
ขึ้น GitHub ตรงกันสม่ำเสมอสัก 1-2 สัปดาห์ก่อน ค่อยปิด task `MaeNaRua_Pipeline_Weekly`/
`MaeNaRua_Reservoir_Daily_Orchestration`/`WMB_daily` ใน Windows Task Scheduler (คำสั่ง
`schtasks /delete /tn "<ชื่อ task>" /f`) — **ยกเว้น** `sar_background_job.py`/
`monitoring_data_builder.py`/`reservoir_daily_orchestration.py` ที่ยังไม่ย้าย (ดู
`COLAB_MIGRATION_PLAN.md` หัวข้อ 7) ต้องปล่อยรันบน Windows ต่อไปเหมือนเดิม
