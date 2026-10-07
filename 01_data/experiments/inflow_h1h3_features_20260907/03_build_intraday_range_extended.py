# -*- coding: utf-8 -*-
"""
ขยาย daily_max_level_24h / daily_min_level_24h / daily_range_24h ให้ครอบคลุมถึงปัจจุบัน โดยรวม 3 แหล่ง:
  1. "Raw Data_RES002 station.xlsx" -- 2025-06-26 18:00 ถึง 2026-06-27 09:00 (รายชั่วโมง)
  2. wide_log ฉบับเก่า (wide_log_20260731.csv) -- 2026-07-10 ถึง 2026-07-31
  3. wide_log ฉบับใหม่ที่ผู้ใช้เพิ่งอัปโหลด (Telemetry_Mae_Na_Rua - wide_log (3).csv) -- 2026-07-10 ถึง
     2026-09-07 (ทับซ้อนกับ #2 บางส่วน แต่ยาวกว่ามาก ครอบคลุมเกือบทั้งช่วง forecast_accuracy_log.csv)

window ต่อวันที่ D: (D-1 07:00, D 07:00] ตรงกับ convention เดิมของระบบ (rain_24h_mm/ΔS)
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl

FEATEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/feature_experiments_20260731")
UPLOADS = Path("/sessions/busy-awesome-cerf/mnt/uploads")
HERE = Path.cwd()


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


raw_series = parse_raw_data_xlsx(FEATEXP / "Raw Data_RES002 station.xlsx")
wide_old = parse_wide_log_csv(FEATEXP / "wide_log_20260731.csv")
wide_new = parse_wide_log_csv(UPLOADS / "Telemetry_Mae_Na_Rua - wide_log (3).csv")

print(f"Raw Data hourly:  {len(raw_series)} pts, {min(t for t,_ in raw_series)} .. {max(t for t,_ in raw_series)}")
print(f"wide_log (old):   {len(wide_old)} pts, {min(t for t,_ in wide_old)} .. {max(t for t,_ in wide_old)}")
print(f"wide_log (new):   {len(wide_new)} pts, {min(t for t,_ in wide_new)} .. {max(t for t,_ in wide_new)}")

# รวม 3 แหล่ง -- ใหม่กว่า/ความถี่สูงกว่าทับของเก่า (raw -> wide_old -> wide_new เรียงตามความสด)
combined = {}
for t, v in raw_series:
    combined[t] = v
for t, v in wide_old:
    combined[t] = v
for t, v in wide_new:
    combined[t] = v
all_pts = sorted(combined.items())
print(f"Combined: {len(all_pts)} pts, {all_pts[0][0]} .. {all_pts[-1][0]}")

start_date = datetime(2025, 6, 27).date()
end_date = datetime(2026, 9, 7).date()

results = []
d = start_date
while d <= end_date:
    end_dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=7)
    start_dt = end_dt - timedelta(hours=24)
    window = [v for t, v in all_pts if start_dt < t <= end_dt]
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

out_path = HERE / "intraday_range_full_history_extended.csv"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["Date", "n_readings_24h", "min_level_24h", "max_level_24h", "range_24h"])
    w.writeheader()
    w.writerows(results)
print(f"Saved {out_path}")

# show gaps
have = {r["Date"] for r in results}
d = start_date
gaps = []
while d <= end_date:
    if d.isoformat() not in have:
        gaps.append(d.isoformat())
    d += timedelta(days=1)
print(f"\nMissing days ({len(gaps)}):", gaps[:5], "..." if len(gaps) > 10 else "", gaps[-5:] if len(gaps) > 5 else "")
