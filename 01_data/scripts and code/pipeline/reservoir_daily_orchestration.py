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

=== สถานะ: LIVE ตั้งแต่ 2026-07-18 -- เขียนทับไฟล์ทางการจริงแล้ว ===

**อัปเดต 2026-07-18**: ผู้ใช้ยืนยันให้ตัดจาก shadow mode ไป live ทันที โดยยอมรับความเสี่ยง
คลาดเคลื่อนบางวันจาก rain-window convention (07:00→07:00) ที่ยังไม่ยืนยัน 100% (ดู
reservoir_telemetry_from_sheet.py หัวข้อ "สิ่งสำคัญที่ต้องรู้" ข้อ 2 — ผลต่างที่เคยเจอสูงสุดคือ
~2,169 m3 ในวันที่ฝนตกหนัก ส่วนวันฝนน้อย/ไม่ตกตรงเป๊ะ)

`run_and_append()` ตอนนี้เขียนผล **2 ที่พร้อมกัน**:
  1. `inflow_auto/RES002_daily_computed.csv` (shadow CSV เดิม — เก็บไว้เป็น audit trail คู่ขนาน
     เหมือนเดิม ไม่ได้ตัดออก)
  2. **ไฟล์ทางการจริง** `01_data/Reservoirs/inflow/<year>/<year>_<month>_MNR.xlsx` ผ่าน
     `reservoir_official_file_writer.write_computed_days()` (backup ไฟล์เดิมอัตโนมัติทุกครั้งก่อนเขียน
     — ดู docstring ของไฟล์นั้นสำหรับรายละเอียดสำคัญเรื่อง openpyxl flatten formula→value)

ถ้าอยากปิดการเขียนไฟล์ทางการชั่วคราว (กลับไป shadow-only) ใช้ `--skip-official-write`

=== วิธีใช้ ===

    python reservoir_daily_orchestration.py                     # รันของ "เมื่อวาน" (ค่า default)
    python reservoir_daily_orchestration.py --date 2026-07-13   # รันของวันที่ระบุ (backfill)
    python reservoir_daily_orchestration.py --sheet-source /path/to/local_export.xlsx
                                                                  # ใช้ไฟล์ local แทน CSV URL

ต้องตั้ง env var RESERVOIR_TELEMETRY_SHEET_CSV_URL ไว้ก่อน (ดู reservoir_telemetry_from_sheet.py)
ถ้าไม่ใช้ --sheet-source

=== เรื่อง O (ปริมาณน้ำที่ปล่อยออก) ===

`compute_for_date()` เรียก `get_release_events()` (dispatcher) เพื่อหาแหล่งข้อมูล -- ถ้าตั้ง env var
`RESERVOIR_RELEASE_SHEET_CSV_URL` ไว้ (link publish-to-web CSV ของ Google Sheet ที่ Form บันทึกการ
ปล่อยน้ำเขียนลง ผ่าน Apps Script onFormSubmit) จะดึงจาก Sheet นั้นอัตโนมัติทุกครั้งที่รัน -- ถ้าไม่ได้
ตั้ง env var นี้ (เช่น ยังไม่ได้สร้าง/เชื่อม Form) จะ fallback ไปอ่าน local CSV
`01_data/Reservoirs/release_log/release_events.csv` เหมือนเดิม (มีข้อมูลจริง 1 เหตุการณ์ย้อนรอยจาก
ไฟล์ 2026_July_MNR.xlsx -- อัตราคงที่ 9446.4 m3/day ตั้งแต่ 26 มิ.ย ถึง 14 ต.ค. 2569) ทั้งสองแหล่งใช้
โครงสร้างคอลัมน์เดียวกัน (event_no, start_date, start_time, end_date, end_time, outlet_side,
rate_m3_per_day, purpose, note) รองรับแถวที่ end_date/end_time ว่าง = เหตุการณ์ที่ยังไม่ปิด
(เปิดต่อเนื่องจนกว่าจะมีแถวปิดจริง -- ดู `_parse_release_events_rows()`) ถ้าวันไหนไม่มีเหตุการณ์
ครอบคลุม -> O=0 (log warning ให้เห็นชัด ไม่ silent)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reservoir_telemetry_from_sheet as rts
import reservoir_water_balance as rwb
import reservoir_official_file_writer as rofw

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reservoir_daily_orchestration")

RELEASE_LOG_CSV = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "release_log" / "release_events.csv"
OUTPUT_CSV = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "inflow_auto" / "RES002_daily_computed.csv"

# 2026-07-18 เพิ่ม -- Google Form บันทึกการปล่อยน้ำ เขียนลง Google Sheet แท็บที่ publish-to-web
# เป็น CSV ไว้ (แบบเดียวกับ RESERVOIR_TELEMETRY_SHEET_CSV_URL ใน reservoir_telemetry_from_sheet.py)
# ตั้ง env var นี้เป็น link นั้นเพื่อให้ get_release_events() ดึงจาก Sheet อัตโนมัติแทน local CSV
# -- ถ้าไม่ตั้ง env var นี้ ระบบจะ fallback ไปอ่าน RELEASE_LOG_CSV local เหมือนเดิมทุกประการ (ไม่มี
# ผลกระทบย้อนหลังถ้ายังไม่ได้สร้าง Form จริง)
RESERVOIR_RELEASE_SHEET_CSV_URL_ENV = "RESERVOIR_RELEASE_SHEET_CSV_URL"

OUTPUT_COLUMNS = [
    "date", "level_msl", "storage_m3", "prev_storage_m3", "delta_s_m3",
    "rain_24h_mm", "release_o_m3", "spill_m3", "evap_m3", "infiltration_m3",
    "inflow_m3", "hours_covered", "data_complete", "release_source_note",
    "computed_at",
]


def _parse_release_events_rows(dict_reader) -> list[dict]:
    """
    Logic กลางในการแปลงแถว CSV (จาก csv.DictReader ไม่ว่าจะมาจากไฟล์ local หรือ CSV text ที่ดึงจาก
    Google Sheet) ให้เป็น event dict พร้อม start_dt/end_dt/rate_m3_per_day -- ใช้ร่วมกันทั้ง
    load_release_events() (local CSV) และ load_release_events_from_sheet() (Google Sheet ที่ Form
    เขียนลง) กันโค้ด parse ไม่ตรงกันระหว่างสองแหล่ง

    **แก้ 2026-07-18**: รองรับ "เหตุการณ์ที่ยังไม่ปิด" (end_date/end_time ยังว่างอยู่ -- กรณีชุมชน
    กรอกแค่ตอนเปิดวาล์ว ยังไม่ได้กรอกตอนปิด) โดยตั้ง row["end_dt"] = None แทนการ crash --
    get_release_o_for_date() จะตีความ end_dt=None ว่า "เปิดต่อเนื่องไปเรื่อยๆ จนกว่าจะมีแถวปิด"
    เดิมโค้ดนี้ใช้ dt.datetime.strptime() ตรงๆ กับ end_date/end_time ซึ่ง crash ทันทีถ้าเป็นค่าว่าง
    (ValueError: time data ' ' does not match format) และเพราะฟังก์ชันนี้ parse ทั้งไฟล์รวดเดียว
    ก่อน return ทำให้เหตุการณ์เปิดค้างแค่ 1 แถวพังการคำนวณ "ทุกวันที่" ไม่ใช่แค่วันของเหตุการณ์นั้น
    """
    events = []
    for row in dict_reader:
        row["start_dt"] = dt.datetime.strptime(f"{row['start_date']} {row['start_time']}", "%Y-%m-%d %H:%M")
        end_date = (row.get("end_date") or "").strip()
        end_time = (row.get("end_time") or "").strip()
        if not end_date or not end_time:
            row["end_dt"] = None  # ยังไม่ปิด -- ถือว่าเปิดต่อเนื่องไปเรื่อยๆ
            if end_date or end_time:
                logger.warning(
                    "event#%s มี end_date/end_time กรอกไม่ครบ (end_date=%r, end_time=%r) -- "
                    "ถือว่ายังไม่ปิดทั้งคู่ (เปิดต่อเนื่อง)",
                    row.get("event_no"), row.get("end_date"), row.get("end_time"),
                )
        else:
            row["end_dt"] = dt.datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        row["rate_m3_per_day"] = float(row["rate_m3_per_day"])
        events.append(row)
    return events


def load_release_events(csv_path: Path = RELEASE_LOG_CSV) -> list[dict]:
    """
    อ่าน release_events.csv local -- โครงสร้างเดียวกับที่ Google Form จะผลิต (ดู docstring หัวไฟล์)
    ใช้ตอนยังไม่ได้ตั้ง RESERVOIR_RELEASE_SHEET_CSV_URL (ดู get_release_events() ซึ่งเป็น dispatcher
    ที่ควรเรียกจาก compute_for_date() แทนฟังก์ชันนี้ตรงๆ)
    """
    if not csv_path.exists():
        logger.warning("ไม่พบไฟล์ release log ที่ %s -- ถือว่าไม่มีการปล่อยน้ำเลย (O=0 ทุกวัน)", csv_path)
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return _parse_release_events_rows(csv.DictReader(f))


def load_release_events_from_sheet(source: Optional[str] = None) -> list[dict]:
    """
    2026-07-18 เพิ่ม -- อ่าน release events จาก Google Sheet ที่ Google Form บันทึกการปล่อยน้ำ
    เขียนลง (ผ่าน Apps Script onFormSubmit -- ดู RESERVOIR_AUTOMATION_DESIGN.md หัวข้อ Google Form
    สำหรับ setup เต็ม) publish-to-web เป็น CSV แบบเดียวกับที่ตั้งไว้กับข้อมูลโทรมาตรใน
    reservoir_telemetry_from_sheet.py::load_wide_log()

    source:
      - None -> อ่านจาก env var RESERVOIR_RELEASE_SHEET_CSV_URL
      - string ขึ้นต้นด้วย http -> ปฏิบัติเป็น CSV URL ตรงๆ
      - path ไฟล์ .csv local -> อ่านตรงๆ (เผื่อดาวน์โหลดมาทดสอบเอง)

    คอลัมน์ที่คาดหวัง (Sheet ต้องมีหัวคอลัมน์ตรงนี้เป๊ะ -- Apps Script ฝั่ง Form ต้องเขียนให้ตรง):
    event_no, start_date, start_time, end_date, end_time, outlet_side, rate_m3_per_day, purpose, note
    (เหมือน release_events.csv local ทุกประการ -- แถวที่ end_date/end_time ว่างถือว่ายังไม่ปิด
    ดู _parse_release_events_rows())
    """
    if source and not source.startswith("http"):
        path = Path(source)
        with open(path, newline="", encoding="utf-8") as f:
            return _parse_release_events_rows(csv.DictReader(f))

    url = source or os.environ.get(RESERVOIR_RELEASE_SHEET_CSV_URL_ENV)
    if not url:
        raise RuntimeError(
            f"load_release_events_from_sheet() ถูกเรียกแต่ไม่ได้ระบุ source และไม่ได้ตั้ง env var "
            f"{RESERVOIR_RELEASE_SHEET_CSV_URL_ENV} -- ตั้ง env var นี้เป็นลิงก์ publish-to-web CSV "
            f"ของ Sheet ที่ Form เขียนลงก่อน (ดู docstring ฟังก์ชันนี้)"
        )
    req = urllib.request.Request(url, headers={"Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8")
    return _parse_release_events_rows(csv.DictReader(io.StringIO(text)))


def get_release_events(release_csv: Optional[Path] = None) -> list[dict]:
    """
    Dispatcher: ถ้าตั้ง env var RESERVOIR_RELEASE_SHEET_CSV_URL ไว้ -> ดึงจาก Google Sheet (Form
    บันทึกการปล่อยน้ำเขียนลง) เสมอ ไม่ว่า release_csv จะถูกส่งมาหรือไม่ -- ถ้าไม่ได้ตั้ง env var นี้
    (เช่น ยังไม่สร้าง Form) -> fallback ไปอ่าน local CSV (release_csv หรือ RELEASE_LOG_CSV ถ้าไม่ระบุ)
    เหมือนพฤติกรรมเดิมทุกประการ -- ควรเรียกฟังก์ชันนี้จาก compute_for_date() แทน load_release_events()
    ตรงๆ เพื่อให้สลับแหล่งข้อมูลได้ด้วย env var เดียวโดยไม่ต้องแก้โค้ดที่เรียกใช้
    """
    sheet_url = os.environ.get(RESERVOIR_RELEASE_SHEET_CSV_URL_ENV)
    if sheet_url:
        return load_release_events_from_sheet(sheet_url)
    return load_release_events(release_csv or RELEASE_LOG_CSV)


def get_release_o_for_date(events: list[dict], target_date: dt.date) -> tuple[float, str]:
    """
    หาอัตราปล่อยน้ำ (O, m3/day) ของ target_date จาก events -- เอาเหตุการณ์ที่ "ครอบคลุม" วันนั้น
    (start_dt <= 07:00 ของ target_date <= end_dt) ถ้ามีหลายเหตุการณ์ทับซ้อนกันจะบวกรวมกัน
    (เผื่อกรณีปล่อยพร้อมกัน 2 ทาง เช่น สปิลเวย์ + ทางเข้าอ่าง เหมือนที่เห็นในข้อมูลจริง)

    **แก้ 2026-07-18**: เหตุการณ์ที่ end_dt เป็น None (ยังไม่ปิด, ดู load_release_events()) จะถือว่า
    ครอบคลุม target_date ตลอดไปตั้งแต่ start_dt เป็นต้นมา จนกว่าจะมีแถวปิดจริงมาแทน -- คำนวณ inflow
    รายวันของช่วงที่ยังเปิดค้างได้ตามปกติ ไม่ต้องรอให้ปิดก่อน

    คืนค่า (O_m3_per_day, note) -- note อธิบายว่าใช้เหตุการณ์ไหนบ้าง หรือ "ไม่มีเหตุการณ์ปล่อยน้ำ"
    """
    ref_dt = dt.datetime.combine(target_date, dt.time(7, 0))
    matching = [
        e for e in events
        if e["start_dt"] <= ref_dt and (e["end_dt"] is None or ref_dt <= e["end_dt"])
    ]
    if not matching:
        logger.warning(
            "ไม่มีเหตุการณ์ปล่อยน้ำใน release_events.csv ที่ครอบคลุมวันที่ %s -- ใช้ O=0 "
            "(ตรวจสอบว่านี่คือความจริงหรือแค่ยังไม่ได้บันทึกเหตุการณ์)",
            target_date,
        )
        return 0.0, "ไม่มีเหตุการณ์ปล่อยน้ำครอบคลุมวันนี้ (O=0)"
    total = sum(e["rate_m3_per_day"] for e in matching)
    note = "; ".join(
        f"event#{e['event_no']}({e['rate_m3_per_day']}m3/d"
        + (", ยังไม่ปิด" if e["end_dt"] is None else "") + ")"
        for e in matching
    )
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

    events = get_release_events(release_csv)
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
    write_official: bool = True,
) -> dict:
    """
    เรียก compute_for_date() แล้วเขียนผลลง output_csv (append-only) -- idempotent ต่อวันที่:
    ถ้ามีแถวของ target_date อยู่แล้ว จะแทนที่ด้วยผลใหม่ (เผื่อ backfill/re-run ซ้ำ) ไม่ใช่เพิ่มซ้ำ

    write_official=True (default ตั้งแต่ 2026-07-18): เขียนผลลงไฟล์ทางการจริงด้วย ผ่าน
    reservoir_official_file_writer.write_computed_days() -- ถ้าล้มเหลว (เช่น ยังไม่มีไฟล์ของเดือนนั้น
    เตรียมไว้) จะ log warning แต่ไม่ raise ต่อ (shadow CSV ที่เขียนสำเร็จแล้วยังคงอยู่ ไม่เสียหาย)
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

    if write_official:
        try:
            official_results = rofw.write_computed_days([target_date], sheet_source=sheet_source)
            result["official_file_row"] = official_results[0]["written_row"]
        except Exception:
            logger.exception(
                "เขียนไฟล์ทางการจริงล้มเหลวสำหรับวันที่ %s -- shadow CSV เขียนสำเร็จแล้ว "
                "(ไม่เสียหาย) แต่ควรตรวจสอบว่าทำไมเขียนไฟล์ทางการไม่ได้", target_date,
            )
            result["official_file_row"] = None

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, default=None, help="วันที่ต้องการคำนวณ (YYYY-MM-DD) default=เมื่อวาน")
    parser.add_argument("--sheet-source", type=str, default=None, help="path ไฟล์ local หรือ CSV URL (default: env var)")
    parser.add_argument("--skip-official-write", action="store_true",
                         help="ปิดการเขียนไฟล์ทางการจริง (กลับไปเขียนแค่ shadow CSV เหมือนก่อน 2026-07-18)")
    args = parser.parse_args()

    target_date = (
        dt.date.fromisoformat(args.date) if args.date
        else dt.date.today() - dt.timedelta(days=1)
    )

    result = run_and_append(target_date, sheet_source=args.sheet_source, write_official=not args.skip_official_write)
    print(result)


if __name__ == "__main__":
    main()
