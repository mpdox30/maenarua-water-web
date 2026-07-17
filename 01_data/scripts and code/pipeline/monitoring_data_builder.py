"""
monitoring_data_builder.py
============================
2026-07-17 เพิ่ม — สร้าง 03_website/assets/data/monitoring.json จากข้อมูลโทรมาตรสด (wide_log
Google Sheet เดียวกับที่ reservoir_telemetry_from_sheet.py ใช้) ครอบคลุมทั้ง 4 สถานีโทรมาตรใน
ตำบลแม่นาเรือ (ยืนยัน station_code จาก attribute "Tele_Code" ของ 01_data/gis/อ่างเก็บน้ำ.shp):

    RES002 — อ่างเก็บน้ำแม่นาเรือ (Mae Na Rua)
    RES004 — อ่างเก็บน้ำวิทยาลัยเกษตร (Phayao C.A.T.)
    RES005 — อ่างเก็บน้ำห้วยถ้ำ (Huai Tham)
    RES006 — อ่างเก็บน้ำห้วยโซ้ (Huai So)

(อ่างที่ 5 ในตำบล "ห้วยจำตุ้ม" ไม่มี Tele_Code ในชีป = ไม่มีสถานีโทรมาตร ไม่รวมในไฟล์นี้
แต่ยังโชว์ในตาราง static ของหน้าเว็บได้)

API ต้นทาง (สสน.) ส่งสถานีอื่นนอกตำบลปนมาด้วย (PYO001, RES001, RES003, WBYN) — โมดูลนี้กรองทิ้ง
อัตโนมัติ (ดึงเฉพาะ 4 station_code ข้างบน)

=== %ความจุ ===
คำนวณจาก rating curve เฉพาะของแต่ละอ่าง (01_data/Reservoirs/reference/rating_curve_<code>.csv
สำหรับ RES004/005/006, และ rating_curve_1cm.csv สำหรับ RES002) เทียบ storage ที่ระดับน้ำปัจจุบัน
กับ storage ที่ระดับ spillway (ยืนยัน storage-at-spillway ของทั้ง 4 อ่างตรงกับตัวเลขที่มีอยู่แล้ว
ใน assets/data/monitoring.json เดิม (capacity_display) แบบ exact ทุกอ่าง 2026-07-17 — ดู
git log/แชทประกอบ)

ใช้ linear interpolation ระหว่างจุด grid ของ rating curve (ต่างจาก reservoir_water_balance.py ที่
ต้อง floor-match แบบ Excel XLOOKUP เป๊ะเพราะต้อง reproduce สูตร Inflow ให้ตรงเดิม — แต่ตัวเลข
%ความจุ ที่นี่เป็นค่าที่แสดงผลอย่างเดียว ไม่ต้อง bit-exact กับอะไร interpolation ให้ผลลื่นกว่า)

หมายเหตุ 2026-07-17: พบว่ามีโฟลเดอร์ 01_data/Reservoirs/reference/ เตรียมไว้ล่วงหน้าแล้วตั้งแต่
5 ก.ค. 2569 (README.md, monthly_evap_norm.json, weir_constants.json, flow_rate_*.csv) ซึ่งมีค่า
คงที่ evap/weir ตรงกับที่ผมสกัดเองจาก Excel ทุกตัวเลข (ยืนยันความถูกต้องไขว้กัน) — ไฟล์
flow_rate_spillway.csv/flow_rate_inlet.csv มีตาราง "จำนวนรอบวาล์ว -> อัตราการไหล" ที่ตอบโจทย์
TODO เดิมของ RESERVOIR_AUTOMATION_DESIGN.md (แปลง "จำนวนรอบที่เปิดวาล์ว" เป็น O m3/day) — ยังไม่ได้
เอามาต่อกับ release_events.csv/reservoir_daily_orchestration.py (คนละงานกับไฟล์นี้ เป็น TODO แยก)
README.md ยังระบุด้วยว่า Infiltration ควรใช้ rating_curve_1cm.csv (ไม่ใช่ area_terrain.csv ที่
reservoir_water_balance.py ใช้อยู่ตอนนี้) -- **ยังไม่ได้ reconcile จุดนี้** (reservoir_water_balance.py
สอบทาน bit-exact กับสูตรจริงในไฟล์ 2026_July_MNR.xlsx ที่ใช้ area_terrain.csv แล้ว แต่ README นี้
อ้างอิงไฟล์ 2026_May_MNR.xlsx ที่อาจมีสูตรต่างออกไป -- ต้องถามผู้ใช้ก่อนแก้)
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reservoir_telemetry_from_sheet as rts

REFERENCE_DIR = Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "reference"
OUTPUT_JSON = Path(__file__).resolve().parent.parent.parent.parent / "03_website" / "assets" / "data" / "monitoring.json"

FIELDS = ["water_level", "rainfall_1h", "temperature", "humidity", "pressure", "solar"]

# station_code -> (name_th, name_en, spillway_msl, rating_curve_csv_filename, on_map)
STATIONS = {
    "RES002": {"name_th": "อ่างเก็บน้ำแม่นาเรือ", "name_en": "Mae Na Rua Reservoir",
               "spillway_msl": 489.54, "curve": "rating_curve_1cm.csv",
               "area_display": "188.0 ไร่ (0.301 ตร.กม.)", "capacity_display": "1.625 ล้าน ลบ.ม."},
    "RES004": {"name_th": "อ่างเก็บน้ำวิทยาลัยเกษตร", "name_en": "Phayao C.A.T. Reservoir",
               "spillway_msl": 457.07, "curve": "rating_curve_RES004.csv",
               "area_display": "35.4 ไร่ (0.057 ตร.กม.)", "capacity_display": "0.348 ล้าน ลบ.ม."},
    "RES005": {"name_th": "อ่างเก็บน้ำห้วยถ้ำ", "name_en": "Huai Tham Reservoir",
               "spillway_msl": 478.10, "curve": "rating_curve_RES005.csv",
               "area_display": "54.9 ไร่ (0.088 ตร.กม.)", "capacity_display": "0.495 ล้าน ลบ.ม."},
    "RES006": {"name_th": "อ่างเก็บน้ำห้วยโซ้", "name_en": "Huai So Reservoir",
               "spillway_msl": 508.00, "curve": "rating_curve_RES006.csv",
               "area_display": "21.4 ไร่ (0.034 ตร.กม.)", "capacity_display": "0.119 ล้าน ลบ.ม."},
}

# อ่างที่ไม่มีสถานีโทรมาตร (Tele_Code เป็นค่าว่างใน อ่างเก็บน้ำ.shp) -- โชว์ในตาราง static เฉยๆ
RESERVOIR_NO_TELEMETRY = {
    "name_th": "อ่างเก็บน้ำห้วยจำตุ้ม", "name_en": "Huai Cham Tum Reservoir",
    "spillway_msl": 497.50, "area_display": "38.2 ไร่ (0.061 ตร.กม.)", "capacity_display": "0.314 ล้าน ลบ.ม.",
}

CADENCE_TABLE = [
    {"source": "สถานีโทรมาตร (อากาศ/ระดับน้ำ)", "frequency": "ทุก 10 นาที",
     "note": "ดึงจาก API สสน. ผ่าน Google Apps Script อัตโนมัติ (wide_log Google Sheet)"},
    {"source": "Sentinel-1 SAR", "frequency": "ทุก ~7–10 วัน", "note": "ตาม revisit cycle ของดาวเทียม"},
    {"source": "MODIS ET", "frequency": "ทุก ~2 สัปดาห์", "note": "ต้องมี gap-filling สำหรับช่วงที่ latency ค้าง"},
]


def _load_curve(path: Path) -> list[list[float]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            rows.append([float(x) for x in row])
    rows.sort(key=lambda r: r[0])
    return rows


def _interp_storage(level: float, table: list[list[float]]) -> float:
    if level <= table[0][0]:
        return table[0][3]
    if level >= table[-1][0]:
        return table[-1][3]
    for i in range(len(table) - 1):
        a, b = table[i], table[i + 1]
        if a[0] <= level <= b[0]:
            frac = (level - a[0]) / (b[0] - a[0])
            return a[3] + frac * (b[3] - a[3])
    return table[-1][3]


def _latest_non_null(rows: list[dict], code: str, field: str):
    """
    คืนค่า (value, measure_datetime) ของแถวล่าสุดที่ไม่ใช่ None สำหรับ station+field นั้นๆ
    (ไม่ใช้แค่แถวสุดท้ายของทั้งชีต เพราะสถานีบางตัว เช่น RES005 รายงานไม่ครบทุกรอบ poll 10 นาที
    — แถวสุดท้ายอาจเป็น None สำหรับสถานีนั้นได้ ถึงจะมีข้อมูลจริงเมื่อไม่กี่รอบก่อนหน้า)
    """
    key = f"{code}_{field}"
    for row in reversed(rows):
        val = row.get(key)
        if val not in (None, ""):
            mt = row.get("measure_datetime")
            # ไฟล์ .xlsx ที่ export มา บางครั้ง openpyxl อ่านคอลัมน์เวลาเป็น str ธรรมดา (ไม่ใช่
            # datetime object) ถ้า cell ไม่ได้ format เป็นวันที่ในไฟล์ต้นทาง -- normalize ผ่าน
            # parser ตัวเดียวกับที่ reservoir_telemetry_from_sheet.py ใช้กับ CSV เพื่อความสม่ำเสมอ
            if isinstance(mt, str):
                mt = rts._parse_dt_lenient(mt)
            return float(val), mt
    return None, None


def build_station_history(rows: list[dict], code: str, max_hours: int = 24 * 14) -> list[dict]:
    """
    ประวัติระดับน้ำรายชั่วโมงย้อนหลัง (สำหรับกราฟ trend ในหน้า monitoring.html — เพิ่ม 2026-07-17)

    ใช้เทคนิคเดียวกับ reservoir_telemetry_from_sheet._nearest_reading_per_hour_mark() (หาแถวที่
    "ใกล้เวลาหลักชั่วโมง" ที่สุด ภายใน ±30 นาที) แทนที่จะหยิบทุกแถว raw (poll ทุก ~10 นาที) มาพล็อต
    ตรงๆ — เหตุผลเดียวกับที่แก้บั๊กใน reservoir_telemetry_from_sheet.py: การหยิบ "แถวล่าสุดในชั่วโมง
    นั้น" มาใช้แทนค่า ณ เวลาเป้าหมายจะทำให้จุดบนกราฟไม่ได้อยู่ตรงเวลาที่ label จริง (เพี้ยนได้หลาย
    นาทีถึงเกือบชั่วโมง) — ที่นี่ไม่กระทบสูตรคำนวณอะไร (แค่กราฟแสดงผล) แต่ใช้วิธีเดียวกันเพื่อความ
    สม่ำเสมอและถูกต้องของ timestamp ที่แสดง

    ช่วงเวลาที่คืนค่า: นับถอยหลังจาก reading ล่าสุดที่มีจริงของสถานีนั้น (ไม่ใช่ "ตอนนี้" ตามนาฬิกา
    เครื่อง) ไป max_hours ชั่วโมง — ถ้าข้อมูลจริงสั้นกว่า max_hours (เช่น sheet เพิ่งเริ่มเก็บ) จะได้
    history สั้นกว่าที่ขอเฉยๆ ไม่ error

    คืนค่า list of {"t": <ISO datetime>, "level": <float>} เรียงเวลาเก่า -> ใหม่ (ช่องไหนไม่มีข้อมูล
    จริงในช่วง ±30 นาทีของ hour mark นั้นจะไม่มีจุดนั้นเลย ไม่เติมค่าประมาณ ปล่อยให้กราฟเว้นช่วงแทน)
    """
    level_key = f"{code}_water_level"
    candidates = []
    for r in rows:
        mt = r.get("measure_datetime")
        val = r.get(level_key)
        if mt is None or val in (None, ""):
            continue
        if isinstance(mt, str):
            mt = rts._parse_dt_lenient(mt)
        candidates.append((mt, float(val)))
    if not candidates:
        return []
    candidates.sort(key=lambda c: c[0])

    latest = candidates[-1][0]
    earliest_allowed = latest - dt.timedelta(hours=max_hours)
    end_hour = latest.replace(minute=0, second=0, microsecond=0)
    hour_marks = []
    t = end_hour
    while t >= earliest_allowed:
        hour_marks.append(t)
        t -= dt.timedelta(hours=1)
    hour_marks.reverse()

    tol = dt.timedelta(minutes=30)
    history = []
    for mark in hour_marks:
        best = None
        best_dist = None
        for mt, level in candidates:
            dist = abs(mt - mark)
            if dist > tol:
                continue
            if best_dist is None or dist < best_dist:
                best, best_dist = (mt, level), dist
        if best is not None:
            history.append({"t": best[0].isoformat(), "level": best[1]})
    return history


def build_station_snapshot(rows: list[dict], code: str, history_hours: int = 24 * 14) -> dict:
    info = STATIONS[code]
    snapshot: dict = {
        "station_code": code,
        "name_th": info["name_th"],
        "name_en": info["name_en"],
        "spillway_msl": info["spillway_msl"],
    }
    latest_mt: Optional[dt.datetime] = None
    for field in FIELDS:
        val, mt = _latest_non_null(rows, code, field)
        snapshot[field] = val
        if mt is not None and (latest_mt is None or mt > latest_mt):
            latest_mt = mt
    snapshot["measure_datetime"] = latest_mt.isoformat() if latest_mt else None

    level = snapshot.get("water_level")
    if level is not None:
        curve = _load_curve(REFERENCE_DIR / info["curve"])
        storage_now = _interp_storage(level, curve)
        storage_max = _interp_storage(info["spillway_msl"], curve)
        snapshot["storage_m3"] = round(storage_now, 1)
        snapshot["storage_max_m3"] = round(storage_max, 1)
        snapshot["capacity_pct"] = round(storage_now / storage_max * 100, 1) if storage_max else None
        snapshot["distance_to_spillway_m"] = round(level - info["spillway_msl"], 3)
    else:
        snapshot["storage_m3"] = snapshot["storage_max_m3"] = snapshot["capacity_pct"] = None
        snapshot["distance_to_spillway_m"] = None

    snapshot["history"] = build_station_history(rows, code, max_hours=history_hours)

    return snapshot


def build_monitoring_json(sheet_source: Optional[str] = None, history_hours: int = 24 * 14) -> dict:
    rows = rts.load_wide_log(sheet_source)
    stations = [build_station_snapshot(rows, code, history_hours=history_hours) for code in STATIONS]

    latest_overall = max(
        (dt.datetime.fromisoformat(s["measure_datetime"]) for s in stations if s["measure_datetime"]),
        default=None,
    )

    reservoirs_static = [
        {
            "name_th": info["name_th"], "name_en": info["name_en"],
            "spillway_msl": info["spillway_msl"], "area_display": info["area_display"],
            "capacity_display": info["capacity_display"], "on_map": True,
            "station_code": code,
        }
        for code, info in STATIONS.items()
    ] + [{**RESERVOIR_NO_TELEMETRY, "on_map": True, "station_code": None}]

    return {
        "meta": {
            "source": "สถานีโทรมาตร สสน. (API) ผ่าน Google Sheet wide_log (poll ทุก 10 นาที) + "
                       "01_data/Reservoirs/reference (rating curve ต่ออ่าง)",
            "updated": latest_overall.isoformat() if latest_overall else None,
            "data_connected": True,
        },
        "stations": stations,
        "reservoirs": reservoirs_static,
        "cadence_table": CADENCE_TABLE,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-source", type=str, default=None)
    parser.add_argument("--output", type=str, default=str(OUTPUT_JSON))
    parser.add_argument("--history-hours", type=int, default=24 * 14,
                         help="ความยาวย้อนหลังของกราฟ trend ระดับน้ำ (ชั่วโมง) default=14 วัน")
    args = parser.parse_args()

    result = build_monitoring_json(args.sheet_source, history_hours=args.history_hours)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    n_hist = sum(len(s["history"]) for s in result["stations"])
    print(f"wrote {out_path} — {len(result['stations'])} stations, updated={result['meta']['updated']}, history_points={n_hist}")


if __name__ == "__main__":
    main()
