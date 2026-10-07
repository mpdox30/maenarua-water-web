# -*- coding: utf-8 -*-
"""
find_chirps_v3_latest.py — chirps_v3_test_20260722 (สคริปต์วินิจฉัยเฉพาะกิจ ไม่ใช่ส่วนหนึ่งของ
chirps_feature.py) หาวันที่ล่าสุดจริงที่ CHIRPS v3 DAILY_SAT มีภาพอยู่บน GEE ณ ตอนนี้ — ไม่เดาจาก
จำนวนแถวที่ได้ (29/51 วัน อาจไม่ต่อเนื่องกันจากต้นช่วง) query ตรงๆ แบบเดียวกับที่เคยใช้เช็ค IMERG
latest boundary ตอนทำ WMB model (find_imerg_latest.py)

ใช้งาน (จากโฟลเดอร์นี้): python find_chirps_v3_latest.py
"""
import sys
sys.path.insert(0, ".")
import gee_auth

import ee

gee_auth.init_ee("maenaruea-water-pipeline")

point = ee.Geometry.Point([99.80, 19.05])  # TARGET_LON, TARGET_LAT (ต.แม่นาเรือ)

col = ee.ImageCollection("UCSB-CHC/CHIRPS/V3/DAILY_SAT").filterDate("2026-05-01", "2026-08-01")

n = col.size().getInfo()
print("จำนวนภาพในช่วง 2026-05-01 ถึง 2026-08-01:", n)

latest = col.sort("system:time_start", False).first()
latest_time = ee.Date(latest.get("system:time_start")).format("YYYY-MM-dd").getInfo()
print("ภาพล่าสุดจริงที่มี:", latest_time)

# นับภาพต่อวันของ 30 วันล่าสุดก่อนวันที่ล่าสุด เพื่อดูว่ามีวันไหนขาดหายเป็นช่วงๆ หรือขาดรวดเดียว
from datetime import datetime, timedelta
last_dt = datetime.strptime(latest_time, "%Y-%m-%d")
print("\nเช็คว่าวันไหนมีภาพบ้างใน 35 วันก่อนวันล่าสุด (1 = มี, 0 = ไม่มี):")
missing_streak = 0
for i in range(34, -1, -1):
    d = (last_dt - timedelta(days=i)).strftime("%Y-%m-%d")
    cnt = col.filterDate(d, (last_dt - timedelta(days=i - 1)).strftime("%Y-%m-%d")).size().getInfo()
    print(f"  {d}: {'1' if cnt else '0'}")

# วันนี้ (ตามเวลาเครื่อง) เทียบกับวันล่าสุดที่มี -> lag เป็นวัน
today = datetime.now().date()
lag_days = (today - last_dt.date()).days
print(f"\nวันนี้: {today} | ภาพล่าสุดที่มี: {latest_time} | lag = {lag_days} วัน")
