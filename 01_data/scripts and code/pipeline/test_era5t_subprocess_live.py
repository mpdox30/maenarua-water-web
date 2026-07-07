"""
test_era5t_subprocess_live.py
====================
สคริปต์ทดสอบแบบ manual (ไม่ใช่ส่วนหนึ่งของ pipeline) สำหรับยืนยันว่า
data_pipeline.py::_fetch_era5t_via_subprocess() เรียก python.exe ของ conda environment
"era5-grib" จริง (มากับ ArcGIS Pro) ได้สำเร็จบนเครื่อง Windows จริง — ยังไม่เคยรันทดสอบแบบนี้มา
ก่อนเลย (การทดสอบก่อนหน้าใน Claude sandbox ใช้ "fake python.exe" ปลอมแทน เพราะ sandbox เป็น
Linux รัน python.exe ของ Windows จริงไม่ได้)

ใช้ --grib-in โหมดทดสอบ (ข้าม CDS จริง) กับไฟล์ .grib ที่ดาวน์โหลดไว้แล้วจาก test_era5_live.py
(era5_test_output/era5_single_levels_test_20260629.grib) เพื่อแยกปัญหาให้ชัดว่า ถ้าพังจะพังที่
"subprocess เรียก python.exe ของ era5-grib ไม่ได้" (path/permission/conda env) ไม่ใช่ "CDS
queue ช้า/เน็ตหลุด" (ซึ่งเป็นคนละปัญหากัน)

รันสคริปต์นี้ด้วย python ของ .venv หลักของโปรเจกต์ (ไม่ใช่ python.exe ของ era5-grib) เพราะสคริปต์นี้
แค่ import data_pipeline แล้วเรียกฟังก์ชัน — ตัว subprocess เป้าหมายต่างหากที่จะไปเรียก python.exe
ของ era5-grib เอง ไม่ต้องรันสคริปต์นี้เองด้วย python ของ era5-grib

วิธีรัน (จากโฟลเดอร์ 01_data/scripts and code/pipeline/):
    ..\\..\\..\\.venv\\Scripts\\python.exe test_era5t_subprocess_live.py
"""
import json
import sys
from pathlib import Path

import data_pipeline

SCRIPT_DIR = Path(__file__).resolve().parent
EXISTING_GRIB = SCRIPT_DIR / "era5_test_output" / "era5_single_levels_test_20260629.grib"

# ค่าที่เคย verify ไว้แล้วครั้งก่อน (จาก cfgrib.open_datasets() ตรงๆ ในขั้นตอนก่อนหน้า) — ใช้เทียบ
# ว่าค่าที่ได้จาก subprocess รอบนี้ตรงกันไหม (tolerance เผื่อ floating point เล็กน้อยจาก
# rounding ต่างเวอร์ชัน cfgrib/eccodes)
EXPECTED_MEANS = {
    "t2m": (306.421631, 0.01),
    "d2m": (296.030823, 0.01),
    "u10": (2.634186, 0.01),
    "v10": (1.692169, 0.01),
    "tp": (5e-06, 1e-07),
    "ssr": (1924608.0, 100.0),
    "str": (-243304.0, 100.0),
}


def main() -> int:
    print("=== 1) เช็คว่า python.exe ของ conda env era5-grib และ era5t_worker.py มีอยู่จริงไหม ===")
    print(f"    ERA5_GRIB_PYTHON_EXE = {data_pipeline.ERA5_GRIB_PYTHON_EXE}")
    print(f"    exists: {data_pipeline.ERA5_GRIB_PYTHON_EXE.exists()}")
    print(f"    ERA5T_WORKER_SCRIPT  = {data_pipeline.ERA5T_WORKER_SCRIPT}")
    print(f"    exists: {data_pipeline.ERA5T_WORKER_SCRIPT.exists()}")
    print(f"    EXISTING_GRIB        = {EXISTING_GRIB}")
    print(f"    exists: {EXISTING_GRIB.exists()}")

    if not EXISTING_GRIB.exists():
        print(
            "\n[FAILED] ไม่พบไฟล์ .grib ทดสอบ — ต้องรัน test_era5_live.py ก่อน (จะสร้างไฟล์นี้ไว้ที่ "
            f"{EXISTING_GRIB})"
        )
        return 1

    print()
    print("=== 2) เรียก _fetch_era5t_via_subprocess(grib_in=...) จริง (ผ่าน conda env era5-grib จริง) ===")
    result = data_pipeline._fetch_era5t_via_subprocess(grib_in=EXISTING_GRIB)

    print(json.dumps(
        {k: v for k, v in result.items() if k not in ("worker_output",)},
        indent=2, ensure_ascii=False,
    ))

    print()
    print("=== 3) ตรวจสอบ returncode + fetch_error ===")
    print(f"    returncode: {result['returncode']}")
    print(f"    fetch_error: {result['fetch_error']}")

    subprocess_ok = (result["returncode"] == 0) and (result["fetch_error"] is None)
    print(f"    [{'PASS' if subprocess_ok else 'FAIL'}] subprocess เรียกสำเร็จ (returncode=0, ไม่มี fetch_error)")

    if not subprocess_ok:
        print("\n[FAILED] subprocess เรียกไม่สำเร็จ — ดู stdout/stderr ด้านล่างเพื่อ debug")
        print("--- stdout ---")
        print(result.get("stdout"))
        print("--- stderr ---")
        print(result.get("stderr"))
        return 1

    print()
    print("=== 4) ตรวจสอบ JSON output เทียบกับค่าที่เคย verify ไว้ก่อนหน้า ===")
    worker_output = result["worker_output"] or {}
    variables = worker_output.get("variables") or {}
    missing = worker_output.get("missing_variables")
    print(f"    n_grib_datasets: {worker_output.get('n_grib_datasets')}")
    print(f"    valid_time: {worker_output.get('valid_time')}")
    print(f"    missing_variables: {missing}")

    all_match = True
    for var, (expected_mean, tol) in EXPECTED_MEANS.items():
        actual = variables.get(var, {}).get("mean")
        if actual is None:
            print(f"    {var:<5} [FAIL] ไม่พบตัวแปรนี้ในผลลัพธ์")
            all_match = False
            continue
        match = abs(actual - expected_mean) <= tol
        all_match = all_match and match
        status = "PASS" if match else "FAIL"
        print(f"    {var:<5} actual={actual:>14.6g}  expected={expected_mean:>14.6g}  (tol={tol}) [{status}]")

    print()
    if subprocess_ok and all_match and not missing:
        print("=== สรุป: [CONFIRMED] subprocess เรียก conda env era5-grib จริงสำเร็จ + ค่าตรงกับที่ verify ไว้ก่อนหน้าทุกตัว ===")
        return 0
    else:
        print("=== สรุป: [FAILED] มีบางจุดไม่ผ่าน ดูรายละเอียดด้านบน ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
