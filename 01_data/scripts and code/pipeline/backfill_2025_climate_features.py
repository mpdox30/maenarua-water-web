r"""
backfill_2025_climate_features.py
=====================================
2026-09-23 เพิ่ม -- ข้อ 6 (เพิ่มชุดข้อมูลปี 2025 เข้าโมเดล Water Demand)

**ต้องรันบนเครื่อง Windows ของคุณเอง (ไม่ใช่ sandbox นี้)** เพราะต้องใช้:
  - GEE (Google Earth Engine) credential -- สำหรับ CHIRPS rainfall (ดู chirps_feature.py/gee_auth.py)
  - Copernicus CDS credential (cdsapi) -- สำหรับ ERA5T ET0 (ดู era5t_worker.py, เรียกผ่าน conda env
    "era5-grib" ที่ตั้งค่าไว้แล้วสำหรับ run_pipeline.bat ปกติ)
ทั้งสองอย่างนี้ตั้งค่าไว้แล้วในเครื่องคุณสำหรับ pipeline รายวันปกติ -- สคริปต์นี้ใช้ credential
ชุดเดียวกัน ไม่ต้องตั้งอะไรเพิ่ม

**วิธีรัน** (Command Prompt, ที่โฟลเดอร์ pipeline นี้ ใช้ .venv เดียวกับ run_pipeline.bat):
    cd "D:\maenaruea-water-web\01_data\scripts and code\pipeline"
    ..\..\..\..\.venv\Scripts\python.exe backfill_2025_climate_features.py

รันครั้งเดียวจบ (loop 52 สัปดาห์ของปี 2025) ใช้เวลานานพอสมควร (ERA5T ต้องรอคิว CDS ทีละสัปดาห์
+ CHIRPS ต้องรอ GEE query ทีละสัปดาห์ -- ประมาณ 1-3 นาที/สัปดาห์ x 52 = อาจถึง 1-2 ชม.) มี resume
logic ในตัว (เช็คว่า (zone, year=2025, week) มีอยู่ใน ml_features_live.csv แล้วหรือยัง ข้ามถ้ามี) --
รันซ้ำได้ปลอดภัยถ้าโดน interrupt กลางทาง

**หลักการทำงาน:** เรียกใช้ `_fetch_climate_features_step()` ใน data_pipeline.py ตรงๆ (ฟังก์ชันเดียวกับ
ที่ pipeline รายวันใช้จริงทุกวันสำหรับสัปดาห์ปัจจุบัน) แค่ override `as_of_date` เป็นวันอาทิตย์ของแต่ละ
สัปดาห์ ISO ของปี 2025 แทนวันนี้ -- **ไม่ได้เขียนสูตรใหม่เอง** เพื่อเลี่ยงความเสี่ยงสูตรไม่ตรงกับที่
ใช้เทรนโมเดล 2020-2024 เดิม (CHIRPS/ERA5T ของปี 2025 ที่ผ่านมานานแล้วควรได้ข้อมูลคุณภาพ "final"
เต็มที่ ดีกว่าที่ pipeline รายวันได้จากสัปดาห์ปัจจุบันซึ่งมักเป็นแค่ prelim/rolling_estimate)

**สิ่งที่ต้องเช็คหลังรันเสร็จ (สำคัญมาก):** NIR_A_m3/GIR_B_m3 คำนวณจากพื้นที่ปลูกต่อ crop
(AREA_ZONE_A/B) ซึ่งโมเดลเทรนด้วยค่า static ปี 2020 มาตลอด (ดู feature_schema.md หัวข้อ 2) --
ถ้าเครื่องคุณมีผล SAR crop classification ของปีอื่น cache ไว้อยู่ (จาก sar_background_job.py)
`_wd_get_area_zone_ha()` อาจเลือกใช้พื้นที่ปีนั้นแทน static 2020 โดยอัตโนมัติ ทำให้แถวปี 2025 ที่ได้
ใช้พื้นที่ไม่ตรงกับแถวปี 2020-2024 เดิม (จะทำให้ NIR/GIR ปี 2025 เทียบกับปีอื่นไม่ตรงกัน สร้างปัญหา
ใหม่แทนที่จะแก้ปัญหาเดิม) -- สคริปต์นี้เช็คให้อัตโนมัติผ่าน `row["wd_area_basis"]` ที่บันทึกไว้ทุกแถว
แล้ว **หยุดพร้อม error ทันทีถ้าเจอ basis ที่ไม่ใช่ "static_2020"** ให้คุณตัดสินใจเองก่อนว่าจะยอมรับ
พื้นที่ใหม่หรือจะบังคับ fallback (ดู FORCE_STATIC_2020_AREA ด้านล่าง)

ผลลัพธ์ถูก append เข้า `ml_features_live.csv` (ไฟล์เดียวกับที่ pipeline รายวันใช้สะสมข้อมูลปี 2026
อยู่แล้ว -- ปลอดภัย ไม่ทับของเดิม เพราะ key (zone,year,week) ต่างกัน) หลังรันเสร็จ ส่งไฟล์นี้ (หรือ
บอกให้ผมอ่านผ่าน mounted folder) กลับมาให้ผมช่วยสร้าง ml_features_phase4.csv รุ่นขยาย (2020-2025)
+ retrain ต่อ
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import pandas as pd  # noqa: E402

import data_pipeline  # noqa: E402

BACKFILL_YEAR = 2025
ML_FEATURES_LIVE_CSV = data_pipeline.ML_FEATURES_LIVE_CSV

# ถ้า True: ถ้าเจอ wd_area_basis != "static_2020" จะแค่ log warning แล้วรันต่อ (ยอมรับพื้นที่ใหม่)
# ถ้า False (ค่าเริ่มต้น, แนะนำ): หยุดทันทีให้ตรวจสอบก่อน -- ดู docstring หัวไฟล์
ALLOW_NON_STATIC_2020_AREA = False


def iso_week_sunday(year: int, week: int) -> date:
    """วันอาทิตย์ (วันสุดท้าย) ของ ISO week นั้น -- ใช้เป็น as_of_date เพื่อให้ CHIRPS/ERA5T
    ดึงข้อมูลของสัปดาห์ปฏิทินเต็มสัปดาห์ (ไม่ partial)"""
    monday = date.fromisocalendar(year, week, 1)
    return monday + timedelta(days=6)


def already_backfilled(year: int, week: int) -> set:
    """คืน set ของ zone ที่มีแถว (zone, year, week) นี้อยู่แล้วใน ml_features_live.csv (resume logic)"""
    if not ML_FEATURES_LIVE_CSV.exists():
        return set()
    try:
        df = pd.read_csv(ML_FEATURES_LIVE_CSV, usecols=["zone", "year", "week"])
    except Exception:
        return set()
    sub = df[(df["year"] == year) & (df["week"] == week)]
    return set(sub["zone"].unique())


def main():
    print(f"=== Backfill climate features ปี {BACKFILL_YEAR} เข้า {ML_FEATURES_LIVE_CSV} ===")
    print("ใช้ _fetch_climate_features_step() เดียวกับ pipeline รายวันจริง (ไม่เขียนสูตรใหม่)\n")

    n_weeks = 52
    for week in range(1, n_weeks + 1):
        existing = already_backfilled(BACKFILL_YEAR, week)
        if existing >= {"zone_A", "zone_B"}:
            print(f"week {week:2d}/2025: ข้าม (มีอยู่แล้วทั้ง 2 zone ใน ml_features_live.csv)")
            continue

        as_of = iso_week_sunday(BACKFILL_YEAR, week)
        print(f"week {week:2d}/2025 (as_of={as_of.isoformat()}): กำลังดึง MEI+CHIRPS+ERA5T ...")

        t0 = time.monotonic()
        result = data_pipeline._fetch_climate_features_step(as_of_date=as_of)
        elapsed = time.monotonic() - t0

        if result.get("errors"):
            print(f"  [WARN] errors: {result['errors']}")

        for zone in ("zone_A", "zone_B"):
            chirps_z = (result.get("chirps") or {}).get(zone) or {}
            print(
                f"  {zone}: chirps_data_type={chirps_z.get('data_type')} "
                f"P_mm_week={chirps_z.get('p_mm_week')}"
            )

        print(f"  rows_appended={result.get('rows_appended')} (ใช้เวลา {elapsed:.0f} วิ)\n")

        # ---- ตรวจสอบ wd_area_basis ของแถวที่เพิ่งเขียน ----
        live_df = pd.read_csv(ML_FEATURES_LIVE_CSV)
        just_written = live_df[(live_df["year"] == BACKFILL_YEAR) & (live_df["week"] == week)]
        bad_basis = just_written[
            just_written.get("wd_area_basis", pd.Series(dtype=object)) != "static_2020"
        ]
        if len(bad_basis) > 0 and not ALLOW_NON_STATIC_2020_AREA:
            print("!" * 78)
            print("หยุดทำงาน: พบแถวที่ wd_area_basis ไม่ใช่ 'static_2020'")
            print(bad_basis[["zone", "year", "week", "wd_area_basis"]].to_string(index=False))
            print(
                "โมเดลเดิม (2020-2024) เทรนด้วยพื้นที่ crop แบบ static ปี 2020 ทั้งหมด -- ถ้าปี 2025 "
                "ใช้พื้นที่จาก SAR classification รุ่นใหม่แทน จะทำให้ NIR/GIR ของปี 2025 เทียบกับปีอื่น "
                "ไม่ตรงกัน (scale ต่างกัน) อ่าน docstring หัวไฟล์นี้ก่อนตัดสินใจ:\n"
                "  - ถ้ายอมรับพื้นที่ใหม่ได้ (เช่นพื้นที่จริงเปลี่ยนไปมากแล้ว): ตั้ง "
                "ALLOW_NON_STATIC_2020_AREA = True ในไฟล์นี้แล้วรันใหม่\n"
                "  - ถ้าต้องการบังคับ static 2020 เหมือนเดิม: ต้องแก้ _wd_get_area_zone_ha() ใน "
                "data_pipeline.py ชั่วคราวให้ไม่อ่าน SAR cache ระหว่าง backfill นี้ (บอกผมให้ช่วยแก้)"
            )
            print("!" * 78)
            sys.exit(1)

    print("=== เสร็จสิ้น backfill ปี 2025 (52 สัปดาห์) ===")
    print(f"ตรวจผลได้ที่ {ML_FEATURES_LIVE_CSV} -- ส่งกลับมาให้ผมช่วย merge เข้า "
          "ml_features_phase4.csv (recompute lag/rolling/y_h1..h12 ข้ามปี 2024->2025) + retrain ต่อ")


if __name__ == "__main__":
    main()
