# -*- coding: utf-8 -*-
"""
เพิ่ม lag/rolling feature + forward target ให้ Training_6hourly_raw.csv (คล้าย
Qin_lag1/2, Rain_roll3/5/7 ของเวอร์ชันรายวัน แต่หน่วยเป็น "6h-step" แทน "วัน"):

  Qin_lag1  = Q_in_t ของ step ก่อนหน้า (6 ชม.ก่อน)
  Qin_lag2  = Q_in_t ของ 2 step ก่อนหน้า (12 ชม.ก่อน)
  Rain_lag1 = Rain_obs_t ของ step ก่อนหน้า (6 ชม.ก่อน) -- ทดสอบว่าช่วยไหมนอกเหนือจาก Rain_roll
  Rain_lag2 = Rain_obs_t ของ 2 step ก่อนหน้า (12 ชม.ก่อน)
  Rain_roll3/5/7 = ผลรวม Rain_obs_t ของ 3/5/7 step ล่าสุด (18/30/42 ชม.)
  y1..y12   = Q_in_t ของ 1-12 step ข้างหน้า (6h ถึง 72h ahead)

ต้อง "ตัดตอน" ตรงรอยต่อที่ไม่ใช่ข้อมูลติดกันจริง (ตรง gap 2026-06-28..2026-07-09 ที่แถวหายไปเลย
ไม่ใช่ NaN) -- ตรวจจับด้วยการเช็คว่าห่างกันเกิน 6 ชม.พอดีหรือไม่ ถ้าใช่ถือว่าเป็นคนละช่วง ไม่ลาก
lag/rolling/target ข้ามช่วงกัน
"""
import csv
import os
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "Training_6hourly_raw.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

for r in rows:
    r["_t"] = datetime.fromisoformat(r["Datetime"])
    r["_qin"] = float(r["Q_in_t (m3/6h)"])
    r["_rain"] = float(r["Rain_obs_t (mm)"])

rows.sort(key=lambda r: r["_t"])

# ---------- หา segment ID (คนละ segment ถ้าห่างกันไม่ใช่ 6h พอดี) ----------
seg_id = 0
prev_t = None
for r in rows:
    if prev_t is not None and (r["_t"] - prev_t) != timedelta(hours=6):
        seg_id += 1
    r["_seg"] = seg_id
    prev_t = r["_t"]

print(f"n segments: {seg_id + 1}")
from collections import Counter

seg_sizes = Counter(r["_seg"] for r in rows)
print("segment sizes:", sorted(seg_sizes.values(), reverse=True)[:10], "...")

# ---------- lag / rolling ----------
by_seg = {}
for r in rows:
    by_seg.setdefault(r["_seg"], []).append(r)

for seg_rows in by_seg.values():
    for i, r in enumerate(seg_rows):
        r["Qin_lag1 (m3/6h)"] = seg_rows[i - 1]["_qin"] if i >= 1 else None
        r["Qin_lag2 (m3/6h)"] = seg_rows[i - 2]["_qin"] if i >= 2 else None
        r["Rain_lag1 (mm)"] = seg_rows[i - 1]["_rain"] if i >= 1 else None
        r["Rain_lag2 (mm)"] = seg_rows[i - 2]["_rain"] if i >= 2 else None
        r["Rain_roll3 (mm)"] = sum(seg_rows[j]["_rain"] for j in range(max(0, i - 2), i + 1)) if i >= 2 else None
        r["Rain_roll5 (mm)"] = sum(seg_rows[j]["_rain"] for j in range(max(0, i - 4), i + 1)) if i >= 4 else None
        r["Rain_roll7 (mm)"] = sum(seg_rows[j]["_rain"] for j in range(max(0, i - 6), i + 1)) if i >= 6 else None
        for h in range(1, 13):
            key = f"y{h}=Q_in_t+{h} (m3/6h)"
            r[key] = seg_rows[i + h]["_qin"] if i + h < len(seg_rows) else None

out_cols = [
    "Datetime", "Q_in_t (m3/6h)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/6h)",
    "%Full_t", "Rain_obs_t (mm)", "API_t (mm)", "is_release_active", "release_rate_daily (m3/day)", "spill_m3",
    "Qin_lag1 (m3/6h)", "Qin_lag2 (m3/6h)", "Rain_lag1 (mm)", "Rain_lag2 (mm)",
    "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
] + [f"y{h}=Q_in_t+{h} (m3/6h)" for h in range(1, 13)]

out_path = os.path.join(HERE, "Training_6hourly_full.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=out_cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in out_cols})

n_with_all_targets = sum(1 for r in rows if r.get(f"y12=Q_in_t+12 (m3/6h)") is not None)
n_with_lag_and_targets = sum(
    1 for r in rows
    if r.get("Qin_lag2 (m3/6h)") is not None and r.get("y12=Q_in_t+12 (m3/6h)") is not None
)
print(f"Total rows: {len(rows)}")
print(f"Rows with all y1-y12 targets available: {n_with_all_targets}")
print(f"Rows usable for training (lag2 + all targets present): {n_with_lag_and_targets}")
print(f"Saved {out_path}")
