"""
backfill_nir_gir_weeks.py
============================
2026-08-12 เพิ่ม -- คำนวณ NIR_A_m3/GIR_B_m3 ย้อนหลังให้สัปดาห์ที่ ml_features_live.csv มีแค่
"backfill row" (climate feature ครบแล้วจาก backfill_historical_weeks() แต่ wd_nir_gir_status ยัง
เป็น "blocked"/ไม่เคยคำนวณ) -- ใช้กรณีเฉพาะ: สัปดาห์ 27-29/2026 ที่ climate feature เพิ่ง backfill
สำเร็จ (ดู DAILY_RUNBOOK.md / บทสนทนา 2026-08-12) แต่ NIR/GIR ยังว่างอยู่ ทำให้ lag12/roll8 ของ
Water Demand live-path ยังใช้สัปดาห์เหล่านี้เป็นฐานไม่ได้

=== หลักการสำคัญ — ต้องใช้พื้นที่ crop "ตามช่วงเวลาจริง" ไม่ใช่ล่าสุดตอนนี้ ===

ยึดหลักเดียวกับที่ตกลงกับผู้ใช้ไว้แล้วตอนออกแบบ _wd_get_area_zone_ha() (ดู docstring "ไม่แตะ
ประวัติเก่าที่ผูกกับ area ปี 2020 เดิม") -- ถ้าจะคำนวณ NIR/GIR ย้อนหลังของสัปดาห์ใด ต้องใช้ผล SAR
classification ที่ "active อยู่จริง ณ ตอนนั้น" ไม่ใช่ผลล่าสุดวันนี้ (ผิดหลักการเดียวกับ look-ahead
bias) -- สคริปต์นี้จึงสแกนไฟล์ dated SAR result (01_data/gis/sar_output/sar_result_<year>_<date>.json
-- ไฟล์เหล่านี้เป็น audit trail ที่เก็บไว้ทุกรอบ classify จริง ไม่ overwrite ทับกัน) หาไฟล์ที่
generated_at เก่ากว่าหรือเท่ากับ as_of_date ของสัปดาห์เป้าหมาย เอาไฟล์ล่าสุดในกลุ่มนั้น ถ้าไม่มีไฟล์
ไหนเข้าเงื่อนไขเลย (สัปดาห์นั้นเกิดก่อน SAR classification ครั้งแรก) fallback ไปใช้
sar_classification.AREA_2020_HA_BY_ZONE เหมือนที่ pipeline หลักทำตอน live

=== การทำงาน ===

  1. อ่าน ml_features_live.csv หาแถวล่าสุด (ตาม run_timestamp) ของแต่ละ (zone, year, week) ที่ระบุ
  2. ดึง ET0_mm_week/P_eff_mm จากแถวนั้น (ต้อง non-null แล้ว ไม่งั้นข้ามสัปดาห์นั้นไปพร้อม log เตือน)
  3. หา area_ha_by_crop ที่ถูกต้องตามเวลาจริงตามหลักการข้างบน
  4. เรียก data_pipeline.py::_wd_compute_live_nir_gir() ตรงๆ (import มาใช้ ไม่ reimplement สูตร
     เอง -- กันสูตรสองชุดหลุด sync กันในอนาคต)
  5. Append แถวใหม่ (ไม่แก้แถวเดิม -- เหมือน pattern audit-trail ของ backfill_historical_weeks()/
     _backfill_incomplete_climate_weeks() ที่มีอยู่แล้ว) run_timestamp ใหม่ + wd_nir_gir_status
     ระบุชัดว่าเป็น retroactive backfill พร้อมวันที่ทำจริง -- _wd_build_live_df() จะเลือกแถวนี้เป็น
     ตัวล่าสุดของสัปดาห์นั้นเองอัตโนมัติ (drop_duplicates keep="last" ตาม run_timestamp)

=== วิธีใช้ ===

    python backfill_nir_gir_weeks.py --year 2026 --weeks 27,28,29
    python backfill_nir_gir_weeks.py --year 2026 --weeks 27,28,29 --dry-run   (ดูผลก่อน ไม่เขียนไฟล์จริง)

ไม่แตะ/ไม่ยุ่งกับโมเดลหรือ pipeline การพยากรณ์ใดๆ เลย -- อ่าน ml_features_live.csv + ไฟล์ SAR ผลลัพธ์
เก่า เขียนแค่แถวใหม่เพิ่มเข้า ml_features_live.csv ไฟล์เดียว
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_pipeline as dp  # noqa: E402  -- import หลังตั้ง sys.path

ML_FEATURES_LIVE_CSV = dp.ML_FEATURES_LIVE_CSV
ML_FEATURES_LIVE_COLUMNS = dp.ML_FEATURES_LIVE_COLUMNS


def _read_rows() -> list[dict]:
    if not ML_FEATURES_LIVE_CSV.exists():
        raise FileNotFoundError(f"ไม่พบ {ML_FEATURES_LIVE_CSV}")
    with open(ML_FEATURES_LIVE_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _latest_row_for(rows: list[dict], zone: str, year: int, week: int) -> Optional[dict]:
    matching = [
        r for r in rows
        if r["zone"] == zone and int(r["year"]) == year and int(r["week"]) == week
    ]
    if not matching:
        return None
    matching.sort(key=lambda r: r["run_timestamp"])
    return matching[-1]


def _find_area_source(as_of_date: dt.date) -> tuple[dict, dict, str]:
    """
    หา area_ha_by_crop ที่ "active อยู่จริง" ณ as_of_date -- คืนค่า
    (area_by_zone: {"zone_A": {...}, "zone_B": {...}}, meta: dict สำหรับ log, basis: str)

    2026-08-20 แก้: เปลี่ยนมาเรียก dp._wd_find_area_source_for_date() แทนการมี logic หาไฟล์ SAR
    แยกชุดของตัวเอง -- เพราะตอนนี้ _backfill_incomplete_climate_weeks() ใน data_pipeline.py ก็ต้องหา
    area basis แบบเดียวกันนี้ด้วย (แก้บั๊กแถว NIR/GIR ถูกทับเงียบๆ) ย้าย logic ไปไว้ที่เดียว (data_pipeline.py)
    กันสองจุดหลุด sync กัน เหมือนหลักการเดียวกับที่ทำไว้แล้วกับ _wd_compute_live_nir_gir()
    """
    return dp._wd_find_area_source_for_date(as_of_date)


def backfill(year: int, weeks: list[int], dry_run: bool = False) -> list[dict]:
    rows = _read_rows()
    new_rows: list[dict] = []
    now_iso = dt.datetime.now().isoformat()

    for week in weeks:
        # หา area source เดียวกันสำหรับทั้ง 2 zone ของสัปดาห์นี้ (ใช้ as_of_date จากแถว zone_A ถ้ามี
        # ไม่งั้น zone_B -- ทั้งสอง zone ของสัปดาห์เดียวกันควรมี as_of_date เดียวกันเป๊ะอยู่แล้ว)
        probe_row = _latest_row_for(rows, "zone_A", year, week) or _latest_row_for(rows, "zone_B", year, week)
        if probe_row is None:
            print(f"[WARN] สัปดาห์ {year}-W{week}: ไม่มีแถวเลยใน ml_features_live.csv -- ข้าม")
            continue
        as_of_date = dt.date.fromisoformat(probe_row["as_of_date"])
        area_by_zone, area_meta, basis = _find_area_source(as_of_date)
        print(f"[INFO] สัปดาห์ {year}-W{week} (as_of={as_of_date}): area basis={basis} ({area_meta})")

        for zone in ("zone_A", "zone_B"):
            old_row = _latest_row_for(rows, zone, year, week)
            if old_row is None:
                print(f"[WARN]   {zone} W{week}: ไม่มีแถวเลย -- ข้าม")
                continue

            existing_status = (old_row.get("wd_nir_gir_status") or "")
            if existing_status == "ok":
                print(f"[INFO]   {zone} W{week}: มี NIR/GIR อยู่แล้ว (status=ok) -- ข้าม ไม่เขียนซ้ำ")
                continue

            et0 = old_row.get("ET0_mm_week")
            p_eff = old_row.get("P_eff_mm")
            et0_f = float(et0) if et0 not in (None, "") else None
            p_eff_f = float(p_eff) if p_eff not in (None, "") else None
            if et0_f is None or p_eff_f is None:
                print(f"[WARN]   {zone} W{week}: ET0_mm_week/P_eff_mm ยังว่างอยู่ ({et0!r}/{p_eff!r}) -- คำนวณ NIR/GIR ไม่ได้ ข้าม")
                continue

            area_ha_by_crop = area_by_zone.get(zone, {})
            nir_gir = dp._wd_compute_live_nir_gir(
                zone=zone, iso_week=week,
                et0_mm_week=et0_f, p_eff_mm=p_eff_f,
                area_ha_by_crop=area_ha_by_crop,
            )

            new_row = dict(old_row)  # copy ทุกคอลัมน์ climate เดิมมาเป๊ะ ไม่แตะ
            new_row["run_timestamp"] = now_iso
            new_row["NIR_A_m3"] = ""
            new_row["GIR_B_m3"] = ""

            if nir_gir is None:
                print(f"[WARN]   {zone} W{week}: _wd_compute_live_nir_gir() คืน None (ไม่ควรเกิดขึ้นเพราะเช็ค et0/p_eff แล้ว) -- ข้าม")
                continue

            if zone == "zone_A":
                new_row["NIR_A_m3"] = nir_gir["total_m3"]
            else:
                new_row["GIR_B_m3"] = nir_gir["total_m3"]
            new_row["wd_area_basis"] = basis
            new_row["wd_nir_gir_status"] = (
                f"ok (retroactive backfill {dt.date.today().isoformat()} -- ดู backfill_nir_gir_weeks.py, "
                f"area_source={area_meta.get('sar_file', 'hardcoded_2020')})"
            )
            print(f"[OK]   {zone} W{week}: {'NIR_A_m3' if zone=='zone_A' else 'GIR_B_m3'}={nir_gir['total_m3']} m3 (basis={basis})")
            new_rows.append(new_row)

    if not new_rows:
        print("[INFO] ไม่มีแถวใหม่ต้องเพิ่มเลย")
        return new_rows

    if dry_run:
        print(f"[DRY-RUN] จะเพิ่ม {len(new_rows)} แถว แต่ไม่เขียนไฟล์จริง (ตัด --dry-run ออกเพื่อเขียนจริง)")
        return new_rows

    with open(ML_FEATURES_LIVE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ML_FEATURES_LIVE_COLUMNS)
        for r in new_rows:
            writer.writerow({k: r.get(k, "") for k in ML_FEATURES_LIVE_COLUMNS})

    print(f"[OK] เขียน {len(new_rows)} แถวใหม่เข้า {ML_FEATURES_LIVE_CSV} เรียบร้อย")
    return new_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--weeks", type=str, required=True, help="เช่น 27,28,29")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    weeks = [int(w.strip()) for w in args.weeks.split(",") if w.strip()]
    backfill(args.year, weeks, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
