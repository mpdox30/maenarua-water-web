# -*- coding: utf-8 -*-
"""
คำนวณ daily_max_level_24h / daily_min_level_24h / daily_range_24h ของ RES002 จาก wide_log ที่ผู้ใช้
อัปโหลดมา (wide_log_20260731.csv, ครอบคลุม 2026-07-10 ถึง 2026-07-31 เท่านั้น -- แค่ 22 วัน)

Window ต่อวันที่ D: (D-1 07:00, D 07:00] ให้ตรงกับ convention เดียวกับที่ระบบใช้คำนวณ rain_24h_mm/
DeltaS_t (ดู reservoir_telemetry_from_sheet.py::compute_daily_inputs)

**ข้อจำกัดสำคัญ**: คำนวณได้จริงแค่สำหรับวันที่ 2026-07-11 ถึง 2026-07-31 (ต้องมีข้อมูลของวันก่อนหน้า
ด้วยเพื่อหา window เต็ม) — เทียบกับ training data ที่มี 393 แถวย้อนไปถึง 2025-06-27 นี่คือแค่ ~5%
ของประวัติทั้งหมด **ไม่พอสำหรับ retrain/walk-forward CV ทั้งโมเดล** สคริปต์นี้เป็นแค่ diagnostic
พิสูจน์แนวคิดว่า feature นี้ "เห็น" สัญญาณฝนที่ Water_Level_t (จุดเดียว 07:00) มองไม่เห็น ไม่ใช่การ
validate ผลลัพธ์โมเดล
"""
import csv
import os
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "wide_log_20260731.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

parsed = []
for r in rows:
    if not r.get("measure_datetime") or not r.get("RES002_water_level"):
        continue
    try:
        t = datetime.strptime(r["measure_datetime"], "%Y-%m-%d %H:%M:%S")
        level = float(r["RES002_water_level"])
    except (ValueError, TypeError):
        continue
    parsed.append((t, level))
parsed.sort(key=lambda x: x[0])

all_dates = sorted(set(t.date() for t, _ in parsed))
print(f"wide_log covers {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

results = []
for d in all_dates:
    end_dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=7)
    start_dt = end_dt - timedelta(hours=24)
    window_levels = [lvl for t, lvl in parsed if start_dt < t <= end_dt]
    if len(window_levels) < 20:  # ต้องมีข้อมูลพอสมควรถึงจะเชื่อถือได้ (คาดหวัง ~144 จุดถ้าครบ)
        continue
    lvl_at_07 = next((lvl for t, lvl in parsed if t == end_dt), None)
    results.append({
        "date": d.isoformat(),
        "n_readings": len(window_levels),
        "level_at_07": lvl_at_07,
        "min_level_24h": min(window_levels),
        "max_level_24h": max(window_levels),
        "range_24h": round(max(window_levels) - min(window_levels), 4),
    })

print(f"\nComputable days (>=20 readings in window): {len(results)}")
print(f"{'date':12} {'lvl@07':>9} {'min24h':>9} {'max24h':>9} {'range24h':>9}")
for r in results:
    print(f"{r['date']:12} {r['level_at_07']!s:>9} {r['min_level_24h']:>9.3f} "
          f"{r['max_level_24h']:>9.3f} {r['range_24h']:>9.4f}")

out_path = os.path.join(HERE, "intraday_range_diagnostic.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["date", "n_readings", "level_at_07", "min_level_24h",
                                       "max_level_24h", "range_24h"])
    w.writeheader()
    w.writerows(results)
print(f"\nSaved {out_path}")
