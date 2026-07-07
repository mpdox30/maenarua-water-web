"""
test_era5_live.py
====================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline) สำหรับดึงข้อมูล ERA5 (single-levels, ไม่ใช่
ERA5-Land ที่ archive/Phase3 step1 era5 download et0.ipynb ใช้) จริง 1 ครั้งจาก Copernicus Climate
Data Store (CDS) — ยังไม่เคยรันทดสอบแบบนี้มาก่อนเลย เหตุผลที่ทดสอบ ERA5 single-levels แยกจาก
ERA5-Land: ต้องการเช็คว่า latency (ความล่าช้าของข้อมูล) สั้นกว่า ERA5-Land จริงหรือไม่ (ERA5-Land
มักมี latency ~2-3 เดือน ส่วน ERA5 single-levels ควรสั้นกว่ามาก อาจแค่ไม่กี่วัน) โดยลองดึงข้อมูลของ
วันที่ 29 มิ.ย. 2569 (เมื่อวานเทียบกับวันนี้ 5 ก.ค. 2569 ตอนเขียนสคริปต์นี้ — ห่างกัน 6 วัน) ดูว่า
ดึงได้จริงไหม

request ที่ใช้คัดลอกมาจากโค้ดที่ผู้ใช้ generate จากหน้าเว็บ CDS ตรงตัว (dataset
'reanalysis-era5-single-levels', format='grib', 7 ตัวแปรเดียวกับที่ใช้คำนวณ ETo ใน
ET0_weekly_phayao_2020_2024.csv เดิม — ดู feature_schema.md แถว ET0_mm_week/T_mean/RH_pct/
VPD_kPa/u2_ms/Rn_MJ)

รันบนเครื่องที่มี (Claude sandbox ยิง network ไปหา CDS ไม่ได้ + ไม่มี .cdsapirc/cdsapi ติดตั้ง
เหมือนกับ NOAA/GEE ก่อนหน้า — ต้องรันบนเครื่อง user เอง):
  - .cdsapirc ตั้งค่าไว้แล้ว (C:\\Users\\<user>\\.cdsapirc หรือ ~/.cdsapirc)
  - pip install cdsapi cfgrib eccodes xarray pandas (ใน .venv)

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_era5_live.py
"""
import sys
import time
from datetime import date
from pathlib import Path

import cdsapi
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent / "era5_test_output"
OUT_DIR.mkdir(exist_ok=True)
OUT_GRIB = OUT_DIR / "era5_single_levels_test_20260629.grib"

DATASET = "reanalysis-era5-single-levels"
REQUEST = {
    "product_type": ["reanalysis"],
    "variable": [
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "2m_dewpoint_temperature",
        "2m_temperature",
        "total_precipitation",
        "surface_net_solar_radiation",
        "surface_net_thermal_radiation",
    ],
    "year": ["2026"],
    "month": ["06"],
    "day": ["29"],
    "time": ["07:00"],
    "data_format": "grib",
    "download_format": "unarchived",
    "area": [19.3, 99.6, 19, 99.95],  # Mae Na Rua, Phayao — ตามที่ผู้ใช้ระบุ (ไม่แก้ไข)
}

REQUESTED_DATE = date(2026, 6, 29)

# short name ตาม ECMWF grib table ที่คาดว่าจะเจอหลัง parse (7 ตัวตรงกับ 7 variable ที่ request)
EXPECTED_SHORT_NAMES = {"u10", "v10", "d2m", "t2m", "tp", "ssr", "str"}

# ช่วงค่าดิบ (หน่วยเดิมจาก ERA5 ก่อนแปลง) ที่ "สมเหตุสมผล" สำหรับแม่นาเรือ พะเยา ปลาย มิ.ย.
# (ต้นฤดูฝน เขตร้อนชื้น) — t2m/d2m: K, u10/v10: m/s, tp: m สะสม 1 ชม., ssr/str: J/m^2 สะสม 1 ชม.
SANITY_RANGES_RAW = {
    "t2m": (293.0, 313.0),   # ~20-40 C
    "d2m": (288.0, 303.0),   # ~15-30 C
    "u10": (-10.0, 10.0),
    "v10": (-10.0, 10.0),
    "tp":  (0.0, 0.05),      # 0-50 mm ในชั่วโมงเดียว (เกินนี้ถือว่าฝนตกหนักผิดปกติสำหรับ 1 ชม.)
    "ssr": (0.0, 3.6e6),     # เทียบเท่า 0-1000 W/m^2 เฉลี่ย x 3600 วินาที
    "str": (-1.5e6, 5.0e5),
}


def main() -> int:
    print(f"=== 1) ส่ง request ไป CDS: dataset={DATASET} ===")
    print(f"    variable = {REQUEST['variable']}")
    print(f"    date/time = {REQUEST['year'][0]}-{REQUEST['month'][0]}-{REQUEST['day'][0]} "
          f"{REQUEST['time'][0]} UTC")
    print(f"    area (N,W,S,E) = {REQUEST['area']}")
    print("    (หมายเหตุ: CDS มักมี queue delay — เวลาที่วัดนี้รวมเวลารอคิวด้วย ไม่ใช่แค่เวลาดาวน์โหลดไฟล์)")

    client = cdsapi.Client()

    t0 = time.monotonic()
    try:
        client.retrieve(DATASET, REQUEST).download(str(OUT_GRIB))
    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"    [FAILED] request ล้มเหลวหลังผ่านไป {elapsed:.1f} วินาที ({elapsed / 60:.1f} นาที)")
        print(f"    error: {exc}")
        return 1
    elapsed = time.monotonic() - t0
    print(f"    [OK] ใช้เวลาทั้งหมด {elapsed:.1f} วินาที ({elapsed / 60:.1f} นาที) รวม queue delay ของ CDS")

    print()
    print("=== 2) ตรวจสอบไฟล์ .grib ที่ดาวน์โหลดได้ ===")
    if not OUT_GRIB.exists():
        print(f"    [FAILED] ไม่พบไฟล์ {OUT_GRIB}")
        return 1
    size_bytes = OUT_GRIB.stat().st_size
    print(f"    path: {OUT_GRIB}")
    print(f"    ขนาดไฟล์: {size_bytes:,} bytes ({size_bytes / 1024:.1f} KB)")
    if size_bytes < 1000:
        print("    [WARN] ไฟล์เล็กผิดปกติ (<1KB) — อาจเป็น error message ที่ CDS บันทึกเป็น .grib แทนข้อมูลจริง")

    print()
    print("=== 3) เปิดไฟล์ด้วย cfgrib + ตรวจสอบตัวแปรทั้ง 7 ตัว ===")
    try:
        import cfgrib
    except ImportError:
        print("    [FAILED] ไม่มี cfgrib ติดตั้งอยู่ — pip install cfgrib eccodes")
        return 1

    # ใช้ cfgrib.open_datasets() แทน xr.open_dataset(engine='cfgrib') ตรงๆ เพราะ grib ที่มีตัวแปร
    # คนละ typeOfLevel ปนกัน (เช่น 2m variables กับ 10m wind กับ surface radiation/precip) มักถูก
    # cfgrib แยกเป็นหลาย "hypercube dataset" อัตโนมัติ — เปิดแบบ xr.open_dataset() เดี่ยวๆ อาจได้
    # ตัวแปรไม่ครบ 7 ตัว (เจอปัญหานี้เป็นเรื่องปกติกับ ERA5 grib ที่รวมหลายกลุ่มตัวแปรในไฟล์เดียว)
    try:
        datasets = cfgrib.open_datasets(str(OUT_GRIB))
    except Exception as exc:
        print(f"    [FAILED] เปิดไฟล์ด้วย cfgrib.open_datasets() ไม่สำเร็จ: {exc}")
        print("    ตรวจสอบว่าติดตั้ง cfgrib + eccodes ครบหรือยัง (pip install cfgrib eccodes)")
        return 1

    print(f"    cfgrib แยกไฟล์เป็น {len(datasets)} dataset(s) "
          f"(ปกติถ้า grib มีหลาย typeOfLevel ปนกัน ไม่ใช่ปัญหา)")

    all_vars: dict = {}
    time_coord = None
    for i, ds_i in enumerate(datasets):
        var_names = list(ds_i.data_vars)
        print(f"      dataset[{i}]: variables={var_names}, dims={dict(ds_i.sizes)}")
        for v in var_names:
            all_vars[v] = ds_i[v]
        if time_coord is None:
            if "valid_time" in ds_i.coords:
                time_coord = ds_i["valid_time"]
            elif "time" in ds_i.coords:
                time_coord = ds_i["time"]

    found_names = set(all_vars.keys())
    missing = EXPECTED_SHORT_NAMES - found_names
    extra = found_names - EXPECTED_SHORT_NAMES
    print(f"\n    รวมตัวแปรทั้งหมดที่อ่านได้ (จากทุก dataset): {sorted(found_names)}")
    if missing:
        print(f"    [WARN] ตัวแปรที่คาดว่าจะมีแต่หายไป: {missing}")
    else:
        print("    [OK] ครบทั้ง 7 ตัวแปรตามที่ request ไป")
    if extra:
        print(f"    [INFO] ตัวแปรเพิ่มเติมที่ไม่ได้คาดไว้: {extra}")

    print()
    print("=== 4) ตรวจค่าแต่ละตัวแปรว่าอยู่ในช่วงที่สมเหตุสมผลไหม (ปลาย มิ.ย. พะเยา ต้นฤดูฝน) ===")
    all_ok = True
    for name, (lo, hi) in SANITY_RANGES_RAW.items():
        if name not in all_vars:
            print(f"    {name:<5} [SKIP] ไม่มีตัวแปรนี้ในไฟล์ที่อ่านได้")
            all_ok = False
            continue
        vals = all_vars[name].values
        vmin, vmax, vmean = float(vals.min()), float(vals.max()), float(vals.mean())
        ok = (vmin >= lo) and (vmax <= hi)
        all_ok = all_ok and ok
        status = "OK" if ok else "OUT-OF-RANGE"
        print(f"    {name:<5} min={vmin:>13.4f}  mean={vmean:>13.4f}  max={vmax:>13.4f}  "
              f"(คาดหวัง {lo} ถึง {hi}) [{status}]")

    if "t2m" in all_vars:
        print(f"\n    t2m แปลงเป็น: {float(all_vars['t2m'].values.mean()) - 273.15:.1f} °C "
              f"(ควรอยู่ราว 25-38°C ตอนกลางวัน เขตร้อนปลาย มิ.ย.)")
    if "d2m" in all_vars:
        print(f"    d2m แปลงเป็น: {float(all_vars['d2m'].values.mean()) - 273.15:.1f} °C")
    if "tp" in all_vars:
        print(f"    tp แปลงเป็น: {float(all_vars['tp'].values.mean()) * 1000:.3f} mm (สะสม 1 ชม.)")

    print()
    print("=== 5) ตรวจสอบว่าดึงข้อมูลของวันที่ 29 มิ.ย. 2569 ได้จริงไหม (latency check) ===")
    got_requested_date = False
    if time_coord is None:
        print("    [WARN] ไม่พบ coordinate เวลา (time/valid_time) ใน dataset ใดเลย — ข้ามการตรวจสอบนี้")
    else:
        actual_values = time_coord.values
        actual_dates = pd.to_datetime(
            actual_values.ravel() if hasattr(actual_values, "ravel") else [actual_values]
        )
        today = date.today()
        got_requested_date = any(d.date() == REQUESTED_DATE for d in actual_dates)
        print(f"    วันที่ขอ: {REQUESTED_DATE} | วันนี้: {today} | ห่างกัน {(today - REQUESTED_DATE).days} วัน")
        print(f"    วันที่จริงในไฟล์: {sorted(set(str(d.date()) for d in actual_dates))}")
        if got_requested_date:
            print(
                f"    [CONFIRMED] ดึงข้อมูลของวันที่ {REQUESTED_DATE} "
                f"(ห่างจากวันนี้ {(today - REQUESTED_DATE).days} วัน) ได้จริง — ยืนยันว่า ERA5 "
                f"(single-levels) latency สั้นกว่า ERA5-Land มาก (ไม่ใช่ 2-3 เดือนแบบ ERA5-Land)"
            )
        else:
            print(f"    [WARN] วันที่ในไฟล์ไม่ตรงกับที่ขอ ({REQUESTED_DATE}) — ตรวจสอบ request/response อีกครั้ง")

    print("\n=== เสร็จสิ้น ===")
    return 0 if (all_ok and got_requested_date and not missing) else 1


if __name__ == "__main__":
    sys.exit(main())
