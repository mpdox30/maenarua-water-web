"""
inflow_6h_display_estimate.py
================================
เพิ่ม 2026-07-31 — คำนวณ "ประมาณการน้ำไหลเข้าอ่างสูงสุดในหน้าต่าง 6 ชม. ล่าสุด" สำหรับแสดงผลเสริม
บนเว็บ (inflow-forecast.html พาแนล "น้ำไหลเข้าอ่างสุทธิ" ข้อ 4) เพราะค่า Q_in รายวันหลัก (07:00→07:00)
บางวันแสดง 0 ทั้งที่มีฝนตก/ระดับน้ำขึ้นจริงระหว่างวัน (ดู
01_data/experiments/hourly_feasibility_20260731/FINDINGS_6hourly_dataset.md) — ตัวเลขนี้ช่วยให้เห็น
สัญญาณ intraday ที่ค่ารายวันพลาดไป

=== สำคัญ: เป็น DISPLAY-ONLY ไม่ใช่โมเดลพยากรณ์ ===

  - **ไม่แก้ไข/ไม่แทนที่ Q_in รายวันหลัก** ที่ reservoir_daily_orchestration.py คำนวณและเขียนลง
    inflow_auto/RES002_daily_computed.csv + ไฟล์ทางการ .xlsx เลย -- สคริปต์นี้แค่ "อ่าน" ข้อมูล
    โทรมาตรชุดเดียวกัน มาคำนวณเพิ่มที่ resolution ละเอียดกว่า (6 ชม.) แล้วเขียนผลลงไฟล์ JSON คนละไฟล์
    ต่างหาก (03_website/assets/data/inflow_6h_display.json) ไม่แตะไฟล์ทางการ/โมเดล CatBoost ใดๆ
  - **ไม่ใช่ input ของโมเดลพยากรณ์ CatBoost** (deployment_regressors_no_stage1.pkl) — โมเดลนั้นยังใช้
    ข้อมูลรายวันเหมือนเดิมทุกประการ ไม่เปลี่ยนแปลง
  - สรุปจากการทดลองจริงที่ตัดสินใจไม่นำโมเดล ML ไปใช้ที่ resolution 6 ชม. (ดู FINDINGS_6hourly_dataset.md
    ในโฟลเดอร์ experiments — walk-forward CV ยังแพ้โมเดลรายวัน) — สิ่งนี้เป็นแค่การคำนวณ "บริบท"
    ประกอบตัวเลข ไม่ใช่การกลับไปทำโมเดล 6 ชม. ใหม่

=== สูตร ===

reuse สูตร/ค่าคงที่ตรงจาก reservoir_water_balance.py (import โมดูลนั้นตรงๆ ไม่ copy ค่าคงที่มาเขียนซ้ำ
กันข้อมูลเพี้ยนถ้าไฟล์ต้นทางแก้ไขแล้วลืมอัปเดตที่นี่):

    Q_in_6h = ΔStorage_6h - R_runoff_6h + Release_6h + Spill_6h + Evap_6h + Infiltration_6h
    (floor ที่ 0 เหมือนสูตรรายวัน)

  - ΔStorage_6h, R_runoff_6h, Spill_6h: คำนวณจาก rating curve / area_terrain / weir formula ตรงจาก
    reservoir_water_balance.py (rwb._xlookup_floor, rwb._rating_curve, rwb._area_terrain,
    rwb.compute_spillway_overflow_m3) — ระดับน้ำรายชั่วโมงจาก reservoir_telemetry_from_sheet.py
    (rts.load_wide_log + rts._nearest_reading_per_hour_mark) แหล่งเดียวกับที่ orchestration รายวันใช้
  - Evap_6h, Infiltration_6h: หารอัตรารายวัน (rwb.MONTHLY_EVAP_CONST_MM ฯลฯ) ด้วย 4 -- ประมาณอัตรา
    คงที่ตลอดวัน แบ่งเท่าๆกัน 4 ช่วง (แนวทางเดียวกับที่ทดสอบไว้ใน
    01_data/experiments/hourly_feasibility_20260731/build_6hourly_training.py — ยอมรับได้สำหรับค่า
    display-only ไม่ใช่ training data)
  - Release_6h: หา event ที่ทับซ้อนกับหน้าต่าง 6 ชม. จาก get_release_events() (เหมือน orchestration
    รายวัน) แล้ว weight ตามสัดส่วนชั่วโมงที่ทับซ้อนจริง (ไม่ใช่ step function ทั้งวันเหมือนแบบ 07:00
    เดียวที่ compute_for_date() ใช้ — ที่ resolution 6 ชม. ควร weight ตามช่วงเวลาจริงที่ event
    เริ่ม/จบตรงกลางหน้าต่างได้)

=== วิธีใช้ ===

    python inflow_6h_display_estimate.py                       # ใช้ค่าปัจจุบัน, lookback 30 ชม.
    python inflow_6h_display_estimate.py --lookback-hours 48
    python inflow_6h_display_estimate.py --sheet-source /path/to/local_wide_log.csv   # ทดสอบ/backfill
    python inflow_6h_display_estimate.py --now 2026-07-31T09:00:00                    # backfill เวลาที่ระบุ

ต้องตั้ง env var RESERVOIR_TELEMETRY_SHEET_CSV_URL ไว้ก่อน (ตัวเดียวกับที่
reservoir_daily_orchestration.py ใช้) ถ้าไม่ใช้ --sheet-source — ถ้าไม่ตั้งจะ fallback ไปใช้
DEFAULT_SHEET_CSV_URL ที่ฝังในโค้ด (เหมือน orchestration รายวัน)

=== Scheduling ===

ควรรันถี่กว่า orchestration รายวัน (เช่น ทุก 1-2 ชม.) เพราะเป็นค่า "ล่าสุด ณ ตอนนี้" ไม่ใช่สรุปของเมื่อวาน
— ดู run_inflow_6h_display_estimate.bat + คำสั่ง schtasks ตัวอย่างในไฟล์นั้น

=== ข้อจำกัดที่ต้องรู้ ===

  1. Evap/Infiltration เป็นการประมาณ (หาร 4) ไม่ใช่ข้อมูลย่อยจริง
  2. ถ้าข้อมูลระดับน้ำ/ฝนรายชั่วโมงในหน้าต่างไม่ครบ (ขาดช่วง) จะข้ามหน้าต่างนั้นไปเงียบๆ (ไม่ประมาณเอา)
     — ถ้าไม่มีหน้าต่างไหนครบเลยในช่วง lookback ที่กำหนด ไฟล์ output จะมี windows=[] และ
     peak_window=None (หน้าเว็บต้อง handle กรณีนี้ -- ดู inflow-forecast.html)
  3. ยังไม่ผ่าน bit-exact verification กับข้อมูลจริงแบบที่ reservoir_water_balance.py ทำกับสูตรรายวัน
     (เพราะไม่มี "ค่าจริง" รายชั่วโมงจากไฟล์ทางการมาเทียบ — สูตรรายวันเดิมมีไฟล์ MNR.xlsx เทียบได้)
     ควรตีความเป็น "ประมาณการ" ไม่ใช่ตัวเลขที่แม่นยำระดับเดียวกับ Q_in รายวันหลัก
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reservoir_daily_orchestration as rdo  # noqa: E402
import reservoir_telemetry_from_sheet as rts  # noqa: E402
import reservoir_water_balance as rwb  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("inflow_6h_display_estimate")

OUTPUT_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent / "03_website" / "assets" / "data" / "inflow_6h_display.json"
)
LOOKBACK_HOURS_DEFAULT = 30
WINDOW_HOURS = 6


def _release_rate_for_window(
    events: list[dict], window_start: dt.datetime, window_end: dt.datetime,
) -> tuple[float, str]:
    """
    ปริมาณน้ำที่ปล่อยออก (m3) เฉพาะหน้าต่าง [window_start, window_end] — weight ตามสัดส่วนชั่วโมง
    ที่ event ทับซ้อนกับหน้าต่างจริง (event ที่ end_dt เป็น None = ยังไม่ปิด ถือว่าคลุมถึง window_end)
    """
    total = 0.0
    notes = []
    for e in events:
        ev_start = e["start_dt"]
        ev_end = e["end_dt"] if e["end_dt"] is not None else window_end
        overlap_start = max(window_start, ev_start)
        overlap_end = min(window_end, ev_end)
        overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600.0
        if overlap_hours > 0:
            contrib = e["rate_m3_per_day"] * (overlap_hours / 24.0)
            total += contrib
            notes.append(
                f"event#{e.get('event_no')}({overlap_hours:.1f}h@{e['rate_m3_per_day']:.1f}m3/d"
                + (", ยังไม่ปิด" if e["end_dt"] is None else "") + ")"
            )
    return total, ("; ".join(notes) if notes else "ไม่มีเหตุการณ์ปล่อยน้ำในหน้าต่างนี้ (O=0)")


def compute_6h_windows(
    rows: list[dict], release_events: list[dict], now: dt.datetime,
    lookback_hours: int = LOOKBACK_HOURS_DEFAULT,
) -> tuple[list[dict], dict | None]:
    """
    สไลด์หน้าต่าง 6 ชม. ทีละ 1 ชม. ย้อนหลัง lookback_hours ชั่วโมงจาก now — คำนวณ Q_in_6h ทุกหน้าต่าง
    ที่มีข้อมูลครบ คืนค่า (list ของหน้าต่างทั้งหมด, หน้าต่างที่ Q_in_6h สูงสุด หรือ None ถ้าไม่มีเลย)
    """
    now_hour = now.replace(minute=0, second=0, microsecond=0)
    earliest = now_hour - dt.timedelta(hours=lookback_hours)
    all_marks = [earliest + dt.timedelta(hours=h) for h in range(0, lookback_hours + 1)]
    readings = rts._nearest_reading_per_hour_mark(rows, all_marks)

    windows = []
    for end_mark in all_marks:
        start_mark = end_mark - dt.timedelta(hours=WINDOW_HOURS)
        if start_mark < earliest:
            continue
        start_r = readings.get(start_mark)
        end_r = readings.get(end_mark)
        if start_r is None or end_r is None:
            continue

        window_hour_marks = [start_mark + dt.timedelta(hours=h) for h in range(1, WINDOW_HOURS + 1)]
        window_readings = [readings.get(m) for m in window_hour_marks]
        if any(r is None for r in window_readings):
            continue  # ข้อมูลไม่ครบในหน้าต่างนี้ -- ข้าม ไม่ประมาณเอา

        level_start = start_r["level_msl"]
        level_end = end_r["level_msl"]
        hourly_levels = [r["level_msl"] for r in window_readings]
        rain_6h = sum((r["rain_1h_mm"] or 0.0) for r in window_readings)

        rc_row_end = rwb._xlookup_floor(level_end, rwb._rating_curve())
        surface_area_m2 = rc_row_end[2]
        storage_end = rc_row_end[3]
        storage_start = rwb._xlookup_floor(level_start, rwb._rating_curve())[3]
        terrain_area_m2 = rwb._xlookup_floor(level_end, rwb._area_terrain())[2]

        month = end_mark.month
        if month not in rwb.MONTHLY_EVAP_CONST_MM:
            continue
        days_in_month = calendar.monthrange(end_mark.year, month)[1]
        evap_const_mm = rwb.MONTHLY_EVAP_CONST_MM[month]

        delta_s = storage_end - storage_start
        r_runoff = surface_area_m2 * (rain_6h / 1000.0)
        evap_6h = surface_area_m2 * ((evap_const_mm / days_in_month / 4.0) * rwb.EVAP_PAN_COEFFICIENT) / 1000.0
        infiltration_6h = terrain_area_m2 * ((rwb.INFILTRATION_RATE_MM_PER_DAY / 4.0) / 1000.0)
        release_6h, release_note = _release_rate_for_window(release_events, start_mark, end_mark)
        spill_6h = rwb.compute_spillway_overflow_m3(hourly_levels)

        q_in_raw = delta_s - r_runoff + release_6h + spill_6h + evap_6h + infiltration_6h
        q_in_6h = max(0.0, q_in_raw)

        windows.append({
            "window_start": start_mark.isoformat(),
            "window_end": end_mark.isoformat(),
            "q_in_6h_m3": round(q_in_6h, 1),
            "water_level_start_m": round(level_start, 3),
            "water_level_end_m": round(level_end, 3),
            "rain_6h_mm": round(rain_6h, 2),
            "release_6h_m3": round(release_6h, 1),
            "spill_6h_m3": round(spill_6h, 1),
            "release_note": release_note,
        })

    peak = max(windows, key=lambda w: w["q_in_6h_m3"]) if windows else None
    return windows, peak


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-source", default=None, help="path/URL ของ wide_log (ไม่ระบุ = ใช้ env var/DEFAULT)")
    parser.add_argument("--release-csv", default=None, help="path ของ release_events.csv (ไม่ระบุ = ค่า default)")
    parser.add_argument("--lookback-hours", type=int, default=LOOKBACK_HOURS_DEFAULT)
    parser.add_argument("--out", default=None, help="path ไฟล์ output JSON (ไม่ระบุ = ค่า default)")
    parser.add_argument("--now", default=None, help="กำหนดเวลา 'ปัจจุบัน' เอง (ISO format) -- สำหรับทดสอบ/backfill")
    args = parser.parse_args(argv)

    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now()

    rows = rts.load_wide_log(args.sheet_source)
    release_events = rdo.get_release_events(Path(args.release_csv) if args.release_csv else None)

    windows, peak = compute_6h_windows(rows, release_events, now, args.lookback_hours)
    if not windows:
        logger.warning(
            "ไม่มีหน้าต่าง 6 ชม.ไหนคำนวณได้เลยในช่วง lookback %d ชม. ที่ผ่านมา "
            "(ข้อมูลระดับน้ำ/ฝนรายชั่วโมงอาจขาดช่วง) -- เขียนไฟล์ที่มี windows=[]",
            args.lookback_hours,
        )

    out_path = Path(args.out) if args.out else OUTPUT_JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "computed_at": dt.datetime.now().isoformat(),
        "reference_now": now.isoformat(),
        "target_reservoir": "อ่างเก็บน้ำแม่นาเรือ (Mae Na Rua Reservoir)",
        "method": (
            "display-only water-balance estimate ที่ resolution 6 ชม. (สไลด์ทีละ 1 ชม. ย้อนหลัง "
            f"{args.lookback_hours} ชม.) reuse สูตร/ค่าคงที่ตรงจาก reservoir_water_balance.py "
            "(rating curve, spillway weir, evap/infiltration รายเดือน หาร 4) -- ไม่ใช่ค่าที่โมเดล "
            "พยากรณ์ CatBoost ใช้ ใช้แสดงผลเสริมบนเว็บเท่านั้น (ดู docstring หัวไฟล์ script นี้)"
        ),
        "lookback_hours": args.lookback_hours,
        "window_hours": WINDOW_HOURS,
        "n_windows_computed": len(windows),
        "windows": windows,
        "peak_window": peak,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info(
        "เขียน %s (%d หน้าต่างที่คำนวณได้, peak_q_in_6h=%s m3)",
        out_path, len(windows), f"{peak['q_in_6h_m3']:.1f}" if peak else "N/A",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
