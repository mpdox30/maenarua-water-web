# pipeline/ — สถาปัตยกรรม environment (2 environment แยกกัน โดยตั้งใจ)

โฟลเดอร์นี้ (`data_pipeline.py` และ helper module ทั้งหมด) **ไม่ได้รันอยู่ใน Python environment เดียว**
— มี 2 environment แยกกันคนละที่ คนละเหตุผล ห้ามสับสนว่าเป็น environment เดียวกัน โดยเฉพาะตอนย้ายเครื่อง
หรือ deploy จริง (ดูหัวข้อ 4 ท้ายไฟล์นี้)

| | Environment 1 | Environment 2 |
|---|---|---|
| ชื่อ | `.venv` (โปรเจกต์หลัก) | `era5-grib` (conda, มากับ ArcGIS Pro) |
| ใช้ทำอะไร | โมเดล ML ทั้งหมด + MEI + CHIRPS | **เฉพาะ** decode ไฟล์ ERA5T (.grib) |
| รันโดย | `data_pipeline.py` โดยตรง (import ปกติ) | เรียกผ่าน `subprocess` เท่านั้น |
| Path บนเครื่องนี้ | `D:\maenaruea-water-web\.venv\Scripts\python.exe` | `C:\Program Files\ArcGIS\Pro\bin\Python\envs\era5-grib\python.exe` |

---

## 1. `.venv` หลักใช้ทำอะไร

Environment เดียวที่ `data_pipeline.py` รันอยู่จริง (เรียกด้วย `run_pipeline.bat` หรือ Task Scheduler)
รับผิดชอบทุกอย่างยกเว้น ERA5T:

- **โมเดล ML ทั้งหมด**: โหลด/ทำนายทั้ง Water Demand (`_wd_*`) และ Reservoir Inflow (`_ri_*`) —
  ต้องการ `catboost`, `lightgbm`, `scikit-learn`, `joblib`, `pandas`, `numpy`, `openpyxl`
- **MEI** (`mei_feature.py`): ดึง `https://psl.noaa.gov/enso/mei/data/meiv2.data` +
  ONI cross-check จาก NOAA CPC ด้วย `requests` ตรงๆ — ไม่มีปัญหา native library ใดๆ
  (เป็น text file ธรรมดา)
- **CHIRPS** (`chirps_feature.py`): ดึงผ่าน Google Earth Engine ด้วย package `earthengine-api`
  (project GEE: `maenaruea-water-pipeline`) — เป็น pure-Python/HTTPS API ไม่มี native binary
  dependency ที่มีปัญหาเหมือน eccodes

Package หลักที่ต้องมี (ดู `requirements.txt` สำหรับเวอร์ชันล็อกจริง): `requests`, `pandas`, `numpy`,
`joblib`, `scikit-learn`, `lightgbm`, `catboost`, `openpyxl`, `scipy`, `earthengine-api`

ติดตั้งด้วย pip ปกติ — **ไม่มี** native C library ที่ต้องพึ่ง system-level binary (ต่างจาก environment 2
ด้านล่าง) จึงไม่เจอปัญหาการติดตั้งบน Windows

## 2. `era5-grib` (conda, มากับ ArcGIS Pro) ใช้ทำอะไร — และทำไมต้องแยก

**ใช้ทำอย่างเดียวเท่านั้น**: รัน `era5t_worker.py` เพื่อดึง ERA5T (`reanalysis-era5-single-levels`)
จาก Copernicus CDS แล้ว decode ไฟล์ `.grib` ที่ได้ด้วย `cfgrib` — ไม่ทำอะไรอื่นเลย ไม่โหลดโมเดล ไม่ยุ่งกับ
MEI/CHIRPS

**เหตุผลที่ต้องแยกจาก `.venv` หลัก (ไม่ใช่แค่ชอบแยก แต่เป็นข้อจำกัดทางเทคนิคจริง):**

`cfgrib` ต้องพึ่ง `eccodes` ซึ่งเป็น Python binding ที่ห่อ **native C library** (ecCodes ของ ECMWF)
ไว้อีกที — ไม่ใช่ pure-Python package ธรรมดา ปัญหาที่พบจริงระหว่างพัฒนา:

- `pip install eccodes` บน Windows ติดตั้งได้ (import ไม่ error ทันที) แต่ตัว native `.dll` ที่
  `gribapi`/`findlibs` ต้องหาให้เจอ **ไม่เสถียร** — พบจริงว่าแม้ conda-forge ยืนยันว่า package
  `eccodes` ติดตั้งอยู่แล้วและไฟล์ `.dll` มีอยู่จริงตามตำแหน่งที่ถูกต้อง (`<env>\Library\bin\eccodes.dll`)
  การ `import cfgrib` ก็ยังพังด้วย `RuntimeError: Cannot find the ecCodes library` เพราะ
  `findlibs` หาตำแหน่งไฟล์จาก environment variable `CONDA_PREFIX`/`ECCODES_DIR` (ไม่ใช่แค่
  `sys.prefix`) ซึ่งจะถูกตั้งค่าให้ก็ต่อเมื่อผ่าน `conda activate <env>` เท่านั้น
- `conda-forge` (ที่มากับ ArcGIS Pro's Python distribution) เป็นทางที่ **ยืนยันแล้วว่าใช้งานได้จริง**
  (ผ่าน selfcheck ของผู้ใช้ + ทดสอบ live ดึง+decode ERA5T สำเร็จจริงหลายรอบ — ดู `test_era5_live.py`)
  หลังแก้ปัญหา environment variable ข้างต้นแล้ว (ดู `_fetch_era5t_via_subprocess()` ใน
  `data_pipeline.py` ที่ตั้งค่า `CONDA_PREFIX`/`ECCODES_DIR`/`PATH` ให้ subprocess โดยเฉพาะ
  ก่อนเรียก เพื่อไม่ต้องพึ่ง `conda activate` เอง)

สรุปสั้นๆ: **eccodes/cfgrib บน Windows ผ่าน pip ใน `.venv` หลัก ไม่น่าเชื่อถือพอ** ส่วน conda-forge
เสถียรกว่ามาก แต่ ArcGIS Pro เท่านั้นที่มี conda environment พร้อม conda-forge stack นี้อยู่แล้วบนเครื่องนี้
— จึงเลือกใช้ environment ที่พิสูจน์แล้วว่าทำงานได้ แทนที่จะพยายามแก้ปัญหา binary dependency ใน `.venv`
หลักเอง

### กลไกการเชื่อมสอง environment เข้าด้วยกัน

`data_pipeline.py` (รันใน `.venv`) **ไม่ import `cfgrib`/`cdsapi` เอง** — เรียก `era5t_worker.py`
ผ่าน `subprocess.run()` ไปยัง `python.exe` ของ `era5-grib` โดยตรง (ไม่ผ่าน `conda activate`) แล้วอ่านผล
กลับมาเป็นไฟล์ JSON (ดูฟังก์ชัน `_fetch_era5t_via_subprocess()`) ข้อควรระวัง 2 จุดที่แก้ไว้แล้วในโค้ด:

1. **Quote ครอบ path ที่มีเว้นวรรค**: ทั้ง `C:\Program Files\ArcGIS\...` และ
   `...\scripts and code\pipeline\era5t_worker.py` มีเว้นวรรค — ใช้ `subprocess.run()` แบบส่ง
   argument เป็น **list** (ไม่ใช่ string เดียวรวมกัน + `shell=True`) เพื่อให้ Python จัดการ quote ให้เอง
   อัตโนมัติ **ห้ามเติม quote เองด้วยมือ** (ต่างจาก `run_pipeline.bat` ซึ่งเป็น batch string ธรรมดา
   ต้องใส่ `"%VAR%"` เอง)
2. **Environment variable สำหรับ eccodes**: ตั้ง `CONDA_PREFIX`/`ECCODES_DIR`/`PATH` ให้ subprocess
   นี้โดยเฉพาะก่อนเรียก (ดูรายละเอียดหัวข้อ 2 ด้านบน)

## 3. Path ของทั้ง 2 environment บนเครื่องนี้

```
.venv หลัก:      D:\maenaruea-water-web\.venv\Scripts\python.exe
                 (สร้างจาก C:\Python314\python.exe — ดู run_pipeline.bat)

era5-grib:       C:\Program Files\ArcGIS\Pro\bin\Python\envs\era5-grib\python.exe
                 (conda environment ที่มากับ ArcGIS Pro ติดตั้งไว้แล้ว)
```

ค่าคงที่ในโค้ดที่อ้างอิง path เหล่านี้:

- `data_pipeline.py::ERA5_GRIB_PYTHON_EXE` — path เต็มของ `era5-grib`'s python.exe (hardcode)
- `run_pipeline.bat::VENV_PYTHON` — path ของ `.venv` (คำนวณ relative จากตำแหน่งไฟล์ .bat เอง
  ไม่ hardcode absolute path)

## 4. ⚠️ คำเตือนสำคัญก่อนย้ายเครื่อง/deploy จริง

**ถ้าย้าย pipeline นี้ไปรันบนเครื่องอื่น (หรือ deploy บน server จริง) ต้องตั้งค่า 2 environment แยกกัน
ทั้งคู่ — ไม่ใช่แค่สร้าง `.venv` เดียวแล้วจบ:**

1. สร้าง `.venv` ตามปกติ + `pip install -r requirements.txt` (ตามที่ `run_pipeline.bat`
   อธิบายไว้อยู่แล้ว)
2. **แยกต่างหาก**: ต้องมี Python environment ที่สอง (ไม่จำเป็นต้องเป็น ArcGIS Pro เป๊ะๆ — แต่ต้องเป็น
   **conda environment ที่ติดตั้ง `eccodes` ผ่าน `conda install -c conda-forge eccodes`**
   ไม่ใช่ `pip install eccodes`) พร้อม `cdsapi` + `cfgrib`
3. แก้ `ERA5_GRIB_PYTHON_EXE` ใน `data_pipeline.py` ให้ชี้ไปที่ python.exe ของ environment ที่สองนี้
   บนเครื่องใหม่ (path จะไม่เหมือนเครื่องนี้แน่นอน — ดูหัวข้อ TODO ในโค้ดตรงจุดนี้ด้วย ควรย้ายไปตั้งค่า
   ผ่าน environment variable/config file แทนการ hardcode ในซอร์สโค้ด)
4. ตั้งค่า CDS API credential (`.cdsapirc`) ให้ environment ที่สองนี้เข้าถึงได้ — **แนะนำ Service
   Account/non-interactive credential ก่อน deploy จริงเช่นเดียวกับที่ต้องทำกับ GEE credential ของ
   CHIRPS** (ดู TODO ใน `chirps_feature.py` — ยังไม่ได้ทำเพราะรอทุกแหล่งข้อมูลพิสูจน์เสร็จก่อนตามที่
   ตกลงกันไว้ ไม่ใช่เพราะลืม)
5. ถ้าเครื่องใหม่ไม่มี ArcGIS Pro เลย (เช่น deploy บน Linux server) **ห้ามลืม**: ต้องหา conda-forge
   `eccodes` มาติดตั้งเองในเครื่องนั้น (Linux ปกติมักไม่เจอปัญหา findlibs เท่า Windows แต่ก็ควรทดสอบ
   `import cfgrib` ให้ผ่านก่อนเชื่อว่าใช้ได้จริง — อย่าสมมติเอาเองว่าเหมือนเครื่องนี้)

**สรุปในประโยคเดียว**: MEI/CHIRPS/โมเดล ทำงานใน `.venv` เดียวได้สบายๆ แต่ **ERA5T ต้องมี Python
environment ที่สองเสมอ** ที่มี conda-forge `eccodes` ติดตั้งไว้ถูกต้อง — ลืมข้อนี้แล้ว pipeline จะพัง
เฉพาะส่วน ERA5T (ส่วนอื่นยังทำงานต่อได้ตามปกติ เพราะ `_fetch_era5t_via_subprocess()` ออกแบบให้
"ไม่ raise" คืน `fetch_error` แทน ไม่ทำให้ทั้ง pipeline ล้ม)

---

## สถานะการทดสอบ (2026-07-05)

ทั้ง 3 แหล่งข้อมูลภายนอกที่ต้องพิสูจน์ก่อน wire เข้ากับโมเดลจริง — ทดสอบกับข้อมูล/infrastructure จริง
สำเร็จแล้วทั้งหมด (รายละเอียดดู docstring ของแต่ละไฟล์ + `test_*_live.py` ที่เกี่ยวข้อง):

| แหล่งข้อมูล | Environment | สถานะ | ทดสอบด้วย |
|---|---|---|---|
| MEI (NOAA PSL) | `.venv` | ✅ ทดสอบ live สำเร็จ | `test_mei_live.py` |
| CHIRPS (GEE) | `.venv` | ✅ ทดสอบ live สำเร็จ (personal credential — ต้องเปลี่ยน Service Account ก่อน deploy) | `test_chirps_live.py` |
| ERA5T (CDS) | `era5-grib` ผ่าน subprocess | ✅ ทดสอบ live สำเร็จ (ทั้ง live-fetch และ subprocess bridge) | `test_era5_live.py`, `test_era5t_subprocess_live.py` |

**ยังไม่ได้ wire เข้ากับ `_wd_build_feature_vector()`/โมเดลจริง** ตามที่ตกลงไว้ — ยังใช้ static snapshot
จาก `ml_features_phase4.csv` อยู่จนกว่าจะตัดสินใจเชื่อมจริง

---

## Manual Dependencies (ต้องมีคนทำเอง ไม่ใช่ automated)

เพิ่ม 2026-07-05 จากผลตรวจสอบ "ประเมินสถานะ live เต็มรูปแบบของ Reservoir_inflow pipeline" — จุดนี้เป็น
**manual dependency จริง** ที่ pipeline เองแก้ไขให้อัตโนมัติไม่ได้ (ต่างจากปัญหาอื่นในไฟล์นี้ที่เป็นเรื่อง
environment/infrastructure) ต้องบันทึกไว้ชัดเจนเพื่อไม่ให้ใครเข้าใจผิดว่าทั้ง pipeline นี้ automated 100%

Reservoir_inflow pipeline ต้องการให้มีคนอัปโหลดไฟล์
`01_data/Reservoirs/inflow/<year>/<year>_<month>_MNR.xlsx` ทุกเดือนตาม pattern ชื่อไฟล์และ sheet
structure ที่กำหนดไว้ (ชื่อเดือนเป็นภาษาอังกฤษเต็ม เช่น `2026_July_MNR.xlsx` — ดูรายการที่รู้จักใน
`data_pipeline.py::RESERVOIR_MONTH_NAME_TO_NUM`, sheet ต้องชื่อ "บัญชีน้ำ" และมีแถว header ที่คอลัมน์แรก
ตรงคำว่า "Date" เป๊ะ ตามด้วย Water Level (MSL)/Water Volume (M3)/Inflow (M3)/... ตามลำดับคอลัมน์ที่คัดลอก
สูตรมาจาก `01_data/Reservoirs/inflow/inflow_ml_training_template_3d.xlsx` > sheet "Data_Dictionary" —
ดูรายละเอียดคอลัมน์เต็มใน docstring ของ `data_pipeline.py::_ri_load_raw_monthly_data()`)

**ถ้าไม่มีการอัปโหลดไฟล์เดือนใหม่** ระบบจะยังคงทำนายต่อไปโดยใช้ข้อมูลเดือนก่อนหน้า (glob ไฟล์ทุกเดือน/
ทุกปีที่มีอยู่ ไม่ได้กรองเฉพาะเดือนปัจจุบัน — ดู `_ri_load_raw_monthly_data()`) พร้อม staleness warning
เมื่อข้อมูลเก่าเกิน `RESERVOIR_STALE_WARNING_THRESHOLD_DAYS` วัน (ค่าเริ่มต้น 3 วัน — สถานะ
`stale_data_warning` ใน `latest.json.forecasts.inflow.status`) แต่จะ**ไม่หยุดทำงานเอง**จนกว่าจะเก่าเกิน
`RESERVOIR_STALE_BLOCKED_THRESHOLD_DAYS` วัน (ค่าเริ่มต้น 14 วัน — สถานะ `stale_data_blocked` ซึ่งจะไม่
ทำนายเลย) ดู `data_pipeline.py::_ri_compute_staleness()` สำหรับ logic เต็ม และ
`inflow-forecast.html`'s staleness banner (`#staleBanner`) สำหรับวิธีที่หน้าเว็บแสดงคำเตือนนี้ให้ผู้ใช้เห็น

ยืนยันแล้วว่าสถานการณ์นี้เกิดขึ้นจริงตอนตรวจสอบ (2026-07-05): ไฟล์ `2026_July_MNR.xlsx` ยังไม่มี
ระบบใช้ข้อมูลล่าสุดที่ valid จริงคือ 2026-06-27 แทน (`gap_days=8` -> `stale_data_warning`)

**ผู้รับผิดชอบ**: [ระบุชื่อ/ตำแหน่งคนที่ต้องอัปโหลดไฟล์นี้ — ยังไม่ได้ระบุไว้ ณ ตอนเขียนเอกสารนี้]

**กำหนดเวลาที่ควรอัปโหลด**: [ระบุ เช่น ทุกวันที่ 1 ของเดือน — ยังไม่ได้ตกลงกำหนดเวลาแน่นอน ณ ตอนนี้
แนะนำให้อัปโหลดภายใน 3 วันแรกของเดือนใหม่ เพื่อให้ gap_days ไม่เกินเกณฑ์ `stale_data_warning`]
