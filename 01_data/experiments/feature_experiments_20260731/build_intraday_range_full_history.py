# -*- coding: utf-8 -*-
"""
สร้าง daily_max_level_24h / daily_min_level_24h / daily_range_24h ครอบคลุมเกือบทั้ง training data
(393 วัน) โดยรวม 2 แหล่ง:
  1. "Raw Data_RES002 station.xlsx" (01_data/Reservoirs/inflow/) -- ข้อมูลรายชั่วโมงจริง
     2025-06-26 18:00 ถึง 2026-06-27 09:00 (8775 แถว, ขาดแค่ 1 ช่วง 2 ชม. ที่ 2025-08-05) ผู้ใช้ชี้ให้ดู
  2. wide_log ที่ผู้ใช้อัปโหลดก่อนหน้า (wide_log_20260731.csv) -- 2026-07-10 ถึง 2026-07-31

ช่องว่างที่ยังไม่มีข้อมูล: 2026-06-28 ถึง 2026-07-09 (~12 วัน, ไม่มีทั้งสองแหล่ง) -- คำนวณ
daily_range ไม่ได้เฉพาะช่วงนี้ ที่เหลือ (~381/393 วัน = 97%) ครอบคลุมครบ

window ต่อวันที่ D: (D-1 07:00, D 07:00] ตรงกับ convention เดิมของระบบ (rain_24h_mm/ΔS)
"""
import csv
import os
from datetime import datetime, timedelta

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_raw_data_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["20260202_RES002"]
    rows = list(ws.iter_rows(values_only=True))[1:]
    series = []
    for r in rows:
        if r[7] != "water_level" or not r[0]:
            continue
        t = datetime.strptime(str(r[0])[:19], "%Y-%m-%d %H:%M:%S")
        series.append((t, float(r[2])))
    return series


def parse_wide_log_csv(path):
    series = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("measure_datetime") or not row.get("RES002_water_level"):
                continue
            try:
                t = datetime.strptime(row["measure_datetime"], "%Y-%m-%d %H:%M:%S")
                lvl = float(row["RES002_water_level"])
            except (ValueError, TypeError):
                continue
            series.append((t, lvl))
    return series


raw_series = parse_raw_data_xlsx(os.path.join(HERE, "Raw Data_RES002 station.xlsx"))
wide_series = parse_wide_log_csv(os.path.join(HERE, "wide_log_20260731.csv"))

print(f"Raw Data hourly series: {len(raw_series)} pts, {min(t for t,_ in raw_series)} to {max(t for t,_ in raw_series)}")
print(f"wide_log series: {len(wide_series)} pts, {min(t for t,_ in wide_series)} to {max(t for t,_ in wide_series)}")

# รวม 2 แหล่ง -- ถ้าช่วงเวลาซ้อนกัน ให้ wide_log (ความถี่สูงกว่า, สดกว่า) ทับ raw
combined = {}
for t, v in raw_series:
    combined[t] = v
for t, v in wide_series:
    combined[t] = v
all_pts = sorted(combined.items())
print(f"Combined series: {len(all_pts)} pts, {all_pts[0][0]} to {all_pts[-1][0]}")

# ---------- คำนวณ daily max/min/range สำหรับทุกวันที่ 2025-06-27 ถึง 2026-07-31 ----------
start_date = datetime(2025, 6, 27).date()
end_date = datetime(2026, 7, 31).date()

results = []
d = start_date
while d <= end_date:
    end_dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=7)
    start_dt = end_dt - timedelta(hours=24)
    window = [v for t, v in all_pts if start_dt < t <= end_dt]
    # ต้องมีอย่างน้อย 20 จุดใน window ถึงจะเชื่อถือได้ (คาดหวัง 24 ถ้าเป็น hourly ล้วน หรือ ~144
    # ถ้าเป็นช่วง wide_log ความถี่สูง)
    if len(window) >= 20:
        results.append({
            "Date": d.isoformat(),
            "n_readings_24h": len(window),
            "min_level_24h": min(window),
            "max_level_24h": max(window),
            "range_24h": round(max(window) - min(window), 4),
        })
    d += timedelta(days=1)

print(f"\nComputable days: {len(results)} / {(end_date - start_date).days + 1}")

out_path = os.path.join(HERE, "intraday_range_full_history.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["Date", "n_readings_24h", "min_level_24h", "max_level_24h", "range_24h"])
    w.writeheader()
    w.writerows(results)
print(f"Saved {out_path}")
