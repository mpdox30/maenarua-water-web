# -*- coding: utf-8 -*-
"""
ทดสอบว่า smoothing ระดับน้ำ (moving average หลายขนาดหน้าต่าง) ช่วยลด noise floor รายชั่วโมงให้ต่ำกว่า
สัญญาณฝนจริงพอจะใช้สร้างชุด training รายชั่วโมงได้หรือไม่

วิธี:
  1. โหลดข้อมูลรวม (Raw Data_RES002 station.xlsx รายชั่วโมงเต็มปี + wide_log ราย ~10 นาที)
  2. Resample เป็นตาราง 10 นาทีสม่ำเสมอ (ffill ช่องว่างสั้นๆ ไม่เกิน 30 นาที ให้ตรงกับ tolerance เดิม
     ของระบบใน _nearest_reading_per_hour_mark)
  3. ลอง smoothing 4 ระดับ: raw (ไม่ smooth), MA 1 ชม., MA 3 ชม., MA 6 ชม.
  4. วัด noise floor ที่แต่ละระดับ smoothing จากผลต่างรายชั่วโมง (t) - (t-1) ในช่วงฤดูแล้ง
     (2026-02-10 ถึง 2026-04-30, สมมติ inflow จริงใกล้ 0)
  5. วัดสัญญาณจริงช่วงฝนตกหนักเช้า 30 ก.ค. 2569 (01:00-08:00) ที่ smoothing ระดับเดียวกัน
  6. เทียบ noise:signal ratio ของแต่ละระดับ smoothing

ไม่แตะไฟล์ deploy ใดๆ ทำในโฟลเดอร์นี้ทั้งหมด
"""
import csv
import os
import statistics
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
combined = {}
for t, v in raw_series:
    combined[t] = v
for t, v in wide_series:
    combined[t] = v
pts = sorted(combined.items())
print(f"Combined raw points: {len(pts)}, {pts[0][0]} to {pts[-1][0]}")


def nearest_value(target_t, pts, tolerance_min=30):
    """หาแถวที่ใกล้ target_t ที่สุดภายใน tolerance -- ตาม pattern เดียวกับ
    _nearest_reading_per_hour_mark ที่ระบบใช้จริง"""
    best = None
    best_diff = None
    for t, v in pts:
        diff = abs((t - target_t).total_seconds())
        if diff > tolerance_min * 60:
            continue
        if best_diff is None or diff < best_diff:
            best, best_diff = v, diff
    return best


def build_hourly_grid(pts, start, end):
    """สร้างตาราง hourly (ทุกชั่วโมงตรง :00) จาก pts ด้วย nearest-within-30min"""
    grid = []
    t = start
    while t <= end:
        v = nearest_value(t, pts)
        grid.append((t, v))
        t += timedelta(hours=1)
    return grid


def moving_average(grid, window_hours):
    """MA แบบ trailing (ใช้ค่าที่มีอยู่แล้วเท่านั้น ไม่ look-ahead -- สำคัญสำหรับใช้จริงใน pipeline)"""
    vals = [v for _, v in grid]
    smoothed = []
    for i in range(len(vals)):
        lo = max(0, i - window_hours + 1)
        window = [v for v in vals[lo:i + 1] if v is not None]
        smoothed.append(sum(window) / len(window) if window else None)
    return [(grid[i][0], smoothed[i]) for i in range(len(grid))]


def hourly_diffs_in_range(grid, start, end):
    diffs = []
    gmap = dict(grid)
    t = start
    while t <= end:
        v0, v1 = gmap.get(t - timedelta(hours=1)), gmap.get(t)
        if v0 is not None and v1 is not None:
            diffs.append(v1 - v0)
        t += timedelta(hours=1)
    return diffs


# ---------- build hourly grid over full available range ----------
grid_start, grid_end = pts[0][0].replace(minute=0, second=0), pts[-1][0].replace(minute=0, second=0)
raw_grid = build_hourly_grid(pts, grid_start, grid_end)
n_missing = sum(1 for _, v in raw_grid if v is None)
print(f"Hourly grid: {len(raw_grid)} hours, {n_missing} missing (>30min from any reading)")

DRY_START, DRY_END = datetime(2026, 2, 10), datetime(2026, 4, 30)
RAIN_START, RAIN_END = datetime(2026, 7, 30, 1), datetime(2026, 7, 30, 8)

results = []
for label, window in [("raw (no smoothing)", 1), ("MA 3h", 3), ("MA 6h", 6), ("MA 12h", 12)]:
    smoothed = moving_average(raw_grid, window) if window > 1 else raw_grid
    dry_diffs = hourly_diffs_in_range(smoothed, DRY_START, DRY_END)
    rain_diffs = hourly_diffs_in_range(smoothed, RAIN_START, RAIN_END)

    dry_stdev = statistics.stdev(dry_diffs)
    dry_absmean = statistics.mean([abs(x) for x in dry_diffs])
    dry_max = max(abs(x) for x in dry_diffs)
    rain_mean = statistics.mean(rain_diffs) if rain_diffs else float("nan")
    rain_max = max(rain_diffs) if rain_diffs else float("nan")

    snr = rain_mean / dry_stdev if dry_stdev else float("inf")

    results.append({
        "smoothing": label,
        "dry_n": len(dry_diffs), "dry_stdev_m": round(dry_stdev, 5),
        "dry_absmean_m": round(dry_absmean, 5), "dry_max_m": round(dry_max, 5),
        "rain_mean_diff_m": round(rain_mean, 5), "rain_max_diff_m": round(rain_max, 5),
        "signal_to_noise (rain_mean/dry_stdev)": round(snr, 2),
    })
    print(f"\n{label}:")
    print(f"  dry season hourly diff: stdev={dry_stdev:.5f} m, mean|diff|={dry_absmean:.5f} m, max|diff|={dry_max:.5f} m")
    print(f"  rain event hourly diff: mean={rain_mean:.5f} m, max={rain_max:.5f} m")
    print(f"  signal-to-noise (rain_mean / dry_stdev): {snr:.2f}")

out_path = os.path.join(HERE, "smoothing_noise_comparison.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)
print(f"\nSaved {out_path}")
