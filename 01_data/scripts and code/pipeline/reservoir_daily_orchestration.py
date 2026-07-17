"""
reservoir_daily_orchestration.py
==================================
2026-07-14 เพิ่ม — สคริปต์รายวันที่รวมทุกส่วนของระบบอัตโนมัติบัญชีน้ำเข้าด้วยกัน:

    reservoir_telemetry_from_sheet.py  (ระดับน้ำ 07:00 + ฝนสะสม 24 ชม. + ระดับน้ำรายชั่วโมง)
    + release_log/release_events.csv    (ปริมาณน้ำที่ปล่อยออก O -- ชั่วคราว จนกว่าจะมี
                                          Google Form จริง ดู docstring ด้านล่าง)
    + reservoir_water_balance.py        (สูตร water balance -> Storage/ΔS/Inflow)
    -> เขียนผลลง 01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv (append-only,
       idempotent ต่อวันที่)

=== สถานะ: SHADOW MODE เท่านั้น -- ยังไม่ได้ต่อเข้ากับ prediction pipeline จริง ===

จงใจ**ไม่เขียนทับ**ไฟล์ <year>_<month>_MNR.xlsx ที่มีอยู่ (ทั้งเพื่อความปลอดภัยของข้อมูล -- ไฟล์นั้น
มีชีตอื่นๆ เช่น Rating Curve/ตารางปล่อยน้ำ/น้ำล้นสปิลเวย์ ที่ไม่ควรเสี่ยงทำหาย -- และเพื่อให้มีข้อมูล
คู่ขนานสำหรับเทียบความแม่นยำ) และ**ยังไม่ได้แก้ _ri_load_raw_monthly_data() ใน data_pipeline.py
ให้มาอ่านจาก inflow_auto/**  เหตุผล: ยังมีจุดที่ไม่แน่ใจ 100% อยู่ (ดู
reservoir_telemetry_from_sheet.py หัวข้อ "สิ่งสำคัญที่ต้องรู้" ข้อ 2 -- ฝนสะสม 24 ชม.
คำนวณได้ไม่ตรงกับไฟล์ทางการเป๊ะ) -- ควรรันสคริปต์นี้ขนานไปกับการอัปโหลดไฟล์ xlsx มือแบบเดิมต่อไป
อีกระยะ (แนะนำอย่างน้อย 2-4 สัปดาห์) เพื่อเทียบ Inflow ที่คำนวณได้จากทั้งสองทางว่าตรงกันแค่ไหน
ก่อนตัดสินใจ "cutover" ให้ pipeline ใช้ inflow_auto/ แทนไฟล์มือจริงๆ (เป็นงานถัดไป ไม่ใช่ของไฟล์นี้)

=== วิธีใช้ ===

    python reservoir_daily_orchestration.py                     # รันของ "เมื่อวาน" (ค่า default)
    python reservoir_daily_orchestration.py --date 2026-07-13   # รันของวันที่ระบุ (backfill)
    python reservoir_daily_orchestration.py --sheet-source /path/to/local_export.xlsx
                                                                  # ใช้ไฟล์ local แทน CSV URL

ต้องตั้ง env var RESERVOIR_TELEMETRY_SHEET_CSV_URL ไว้ก่อน (ดู reservoir_telemetry_from_sheet.py)
ถ้าไม่ใช้ --sheet-source

=== เรื่อง O (ปริมาณน้ำที่ปล่อยออก) -- ยังไม่มี Google Form จริง ===

ตอนนี้อ่านจาก 01_data/Reservoirs/release_log/release_events.csv (สร้างไว้ให้แล้วพร้อมข้อมูลจริง
1 เหตุการณ์ที่ย้อนรอยได้จากไฟล์ 2026_July_MNR.xlsx -- อัตราคงที่ 9446.4 m3/day ตั้งแต่ 26 มิ.ย
ถึง 14 ต.ค. 2569) โครงสร้างไฟล์นี้ตรงกับที่ Google Form จะบันทึก (ดู
RESERVOIR_AUTOMATION_DESIGN.md หัวข้อ Google Form) -- เมื่อสร้าง Form จริงแล้ว แค่เปลี่ยนให้
Form เขียนลง Google Sheet แล้วดึงมาแทนที่ CSV นี้ (เปลี่ยนแค่ load_release_events() ฟังก์ชันเดียว
ส่วนที่เหลือของสคริปต์นี้ไม่ต้องแก้) ถ้าวันไหนไม่มีเหตุการณ์ครอบคลุม -> O=0 (log warning ให้เห็นชัด
ไม่ silent)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reservoir_telemetry_from_sheet as rts
import reservoir_water_balance as rwb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reservoir_daily_orchestration")

RELEASE_LOG_CSV = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "release_log" / "release_events.csv"
OUTPUT_CSV = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "inflow_auto" / "RES002_daily_computed.csv"

OUTPUT_COLUMNS = [
    "date", "level_msl", "storage_m3", "prev_storage_m3", "delta_s_m3",
    "rain_24h_mm", "release_o_m3", "spill_m3", "evap_m3", "infiltration_m3",
    "inflow_m3", "hours_covered", "data_complete", "release_source_note",
    "computed_at",
]


def load_release_events(csv_path: Path = RELEASE_LOG_CSV) -> list[dict]:
    """
    อ่าน release_events.csv -- โครงสร้างเดียวกับที่ Google Form จะผลิต (ดู docstring หัวไฟล์)
    เมื่อมี Form จริงให้แทนที่ฟังก์ชันนี้เป็นตัวดึงจาก Google Sheet ที่ Form เขียนลง แทน CSV local
    """
    if not csv_path.exists():
        logger.warning("ไม่พบไฟล์ release log ที่ %s -- ถือว่าไม่มีการปล่อยน้ำเลย (O=0 ทุกวัน)", csv_path)
        return []
    events = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["start_dt"] = dt.datetime.strptime(f"{row['start_date']} {row['start_time']}", "%Y-%m-%d %H:%M")
            row["end_dt"] = dt.datetime.strptime(f"{row['end_date']} {row['end_time']}", "%Y-%m-%d %H:%M")
            row["rate_m3_per_day"] = float(row["rate_m3_per_day"])
            events.append(row)
    return events


def get_release_o_for_date(events: list[dict], target_date: dt.date) -> tuple[float, str]:
    """
    หาอัตราปล่อยน้ำ (O, m3/day) ของ target_date จาก events -- เอาเหตุการณ์ที่ "ครอบคลุม" วันนั้น
    (start_dt <= 07:00 ของ target_date <= end_dt) ถ้ามีหลายเหตุการณ์ทับซ้อนกันจะบวกรวมกัน
    (เผื่อกรณีปล่อยพร้อมกัน 2 ทาง เช่น สปิลเวย์ + ทางเข้าอ่าง เหมือนที่เห็นในข้อมูลจริง)

    คืนค่า (O_m3_per_day, note) -- note อธิบายว่าใช้เหตุการณ์ไหนบ้าง หรือ "ไม่มีเหตุการณ์ปล่อยน้ำ"
    """
    ref_dt = dt.datetime.combine(target_date, dt.time(7, 0))
    matching = [e for e in events if e["start_dt"] <= ref_dt <= e["end_dt"]]
    if not matching:
        logger.warning(
            "ไม่มีเหตุการณ์ปล่อยน้ำใน release_events.csv ที่ครอบคลุมวันที่ %s -- ใช้ O=0 "
            "(ตรวจสอบว่านี่คือความจริงหรือแค่ยังไม่ได้บันทึกเหตุการณ์)",
            target_date,
        )
        return 0.0, "ไม่มีเหตุการณ์ปล่อยน้ำครอบคลุมวันนี้ (O=0)"
    total = sum(e["rate_m3_per_day"] for e in matching)
    note = "; ".join(f"event#{e['event_no']}({e['rate_m3_per_day']}m3/d)" for e in matching)
    return total, note


def _storage_from_level(level_msl: float) -> float:
    rc_row = rwb._xlookup_floor(level_msl, rwb._rating_curve())
    return rc_row[3]


def compute_for_date(
    target_date: dt.date,
    sheet_source: str | None = None,
    release_csv: Path = RELEASE_LOG_CSV,
) -> dict:
    """
    รวมทุกส่วน คำนวณแถวเดียวสำหรับ target_date คืนค่า dict ตรงกับ OUTPUT_COLUMNS
    (ไม่เขียนไฟล์ -- แค่คำนวณ ให้ main()/run_and_append() เป็นคนตัดสินใจเขียน)

    raises ไม่จับ exception จาก reservoir_telemetry_from_sheet/reservoir_water_balance เอง
    (เช่น RuntimeError ถ้าไม่ได้ตั้ง env var, KeyError ถ้าไม่มีค่า evap ของเดือนนั้น) -- ให้ caller
    เห็น error ชัดเจนแทนที่จะกลืน error แล้วเขียนแถวผิดๆ ลง output
    """
    rows = rts.load_wide_log(sheet_source)

    today_inputs = rts.compute_daily_inputs(rows, target_date)
    yesterday_inputs = rts.compute_daily_inputs(rows, target_date - dt.timedelta(days=1))

    if today_inputs["level_msl"] is None:
        raise ValueError(
            f"ไม่มีข้อมูลระดับน้ำที่ 07:00 ของวันที่ {target_date} ใน telemetry log -- "
            "ไม่สามารถคำนวณได้ (ตรวจสอบว่า log อัปเดตถึงวันนี้แล้วหรือยัง)"
        )
    if yesterday_inputs["level_msl"] is None:
        raise ValueError(
            f"ไม่มีข้อมูลระดับน้ำที่ 07:00 ของวันก่อนหน้า ({target_date - dt.timedelta(days=1)}) "
            "ใน telemetry log -- คำนวณ ΔS ไม่ได้ (ต้องมีข้อมูลอย่างน้อย 2 วันติดกัน)"
        )

    prev_storage_m3 = _storage_from_level(yesterday_inputs["level_msl"])

    spill_m3 = rwb.compute_spillway_overflow_m3(today_inputs["hourly_levels_msl"])

    events = load_release_events(release_csv)
    release_o_m3, release_note = get_release_o_for_date(events, target_date)

    result = rwb.compute_daily_row(
        level_msl=today_inputs["level_msl"],
        rain_mm=today_inputs["rain_24h_mm"] or 0.0,
        release_o_m3=release_o_m3,
        spill_m3=spill_m3,
        prev_storage_m3=prev_storage_m3,
        month=target_date.month,
    )

    if not today_inputs["data_complete"]:
        logger.warning(
            "ข้อมูล telemetry ของวันที่ %s ไม่ครบ 24 ชม. (มีแค่ %d/24) -- ผลที่คำนวณได้อาจ "
            "คลาดเคลื่อน ควรตรวจสอบก่อนใช้งานจริง",
            target_date, today_inputs["hours_covered"],
        )

    return {
        "date": target_date.isoformat(),
        "level_msl": result["Water_Level_t"],
        "storage_m3": result["Storage_S_t"],
        "prev_storage_m3": prev_storage_m3,
        "delta_s_m3": result["DeltaS_t"],
        "rain_24h_mm": result["Rain_obs_t"],
        "release_o_m3": release_o_m3,
        "spill_m3": spill_m3,
        "evap_m3": result["Evap_m3"],
        "infiltration_m3": result["Infiltration_m3"],
        "inflow_m3": result["Q_in_t"],
        "hours_covered": today_inputs["hours_covered"],
        "data_complete": today_inputs["data_complete"],
        "release_source_note": release_note,
        "computed_at": dt.datetime.now().isoformat(timespec="seconds"),
    }


def run_and_append(
    target_date: dt.date,
    sheet_source: str | None = None,
    output_csv: Path = OUTPUT_CSV,
) -> dict:
    """
    เรียก compute_for_date() แล้วเขียนผลลง output_csv (append-only) -- idempotent ต่อวันที่:
    ถ้ามีแถวของ target_date อยู่แล้ว จะแทนที่ด้วยผลใหม่ (เผื่อ backfill/re-run ซ้ำ) ไม่ใช่เพิ่มซ้ำ
    """
    result = compute_for_date(target_date, sheet_source)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = []
    if output_csv.exists():
        with open(output_csv, newline="", encoding="utf-8") as f:
            existing_rows = [r for r in csv.DictReader(f) if r["date"] != result["date"]]

    existing_rows.append({k: result[k] for k in OUTPUT_COLUMNS})
    existing_rows.sort(key=lambda r: r["date"])

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(existing_rows)

    logger.info(
        "เขียนผลวันที่ %s ลง %s สำเร็จ: Inflow=%.2f m3, data_complete=%s",
        result["date"], output_csv, result["inflow_m3"], result["data_complete"],
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, default=None, help="วันที่ต้องการคำนวณ (YYYY-MM-DD) default=เมื่อวาน")
    parser.add_argument("--sheet-source", type=str, default=None, help="path ไฟล์ local หรือ CSV URL (default: env var)")
    args = parser.parse_args()

    target_date = (
        dt.date.fromisoformat(args.date) if args.date
        else dt.date.today() - dt.timedelta(days=1)
    )

    result = run_and_append(target_date, sheet_source=args.sheet_source)
    print(result)


if __name__ == "__main__":
    main()
