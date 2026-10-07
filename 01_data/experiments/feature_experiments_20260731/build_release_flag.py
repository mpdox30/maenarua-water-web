# -*- coding: utf-8 -*-
"""
เพิ่ม feature "อยู่ระหว่างปล่อยน้ำ" (is_release_active, release_rate_m3day) ย้อนหลังทั้ง 393 แถวของ
Training_Values_Nofct_7day_Extended_lagfeat.csv

อ้างอิงจาก release_events.csv (event#1: start_date=2026-06-26, rate=9446.4 m3/day, end_date=2026-10-14
ตามไฟล์ local — หมายเหตุสำคัญด้านล่าง) -- วันที่ >= start_date ถือว่า release active

ข้อจำกัดที่ต้องรู้ (สำคัญ): release_events.csv local นี้มีแค่ 1 event (event#1) แต่ log จริงของ
reservoir_daily_orchestration.py (pipeline_log.txt) อ้างถึง "event#2" ตั้งแต่ 2026-07-18 เป็นต้นมา
(อัตราเดียวกันคือ 9446.4 m3/day ทั้งคู่ -- แปลว่าน่าจะเป็นการปล่อยต่อเนื่องจริง ไม่มีช่วงว่าง แค่ label
event เปลี่ยนใน source จริง คือ Google Sheet ที่ RESERVOIR_RELEASE_SHEET_CSV_URL ชี้ไป ซึ่งสคริปต์นี้
เข้าไม่ถึง) -- ใช้สมมติฐาน "active ต่อเนื่องตั้งแต่ 2026-06-26 จนถึงวันสุดท้ายของ training data
(2026-07-24)" ซึ่งสอดคล้องกับสิ่งที่เห็นใน RES002_daily_computed.csv (release_o_m3=9446.4 คงที่ทุกแถว
ตั้งแต่ 07-15 เป็นต้นมา ไม่เคยเป็น 0)

ข้อจำกัดอีกข้อ: ก่อน 2026-06-26 (เกือบทั้งหมดของ training data 393 แถว ย้อนไปถึง 2025-06-27) ไม่มี
เหตุการณ์ปล่อยน้ำบันทึกไว้เลย -- ถือว่า is_release_active=0 ตลอดช่วงนั้น แต่นี่คือ "ไม่มีข้อมูล" ไม่ใช่
"ยืนยันแล้วว่าไม่มีปล่อยน้ำจริง" (release_events.csv สร้างจากการย้อนรอยสูตรไฟล์ ก.ค. 2569 เท่านั้น
ไม่ได้ครอบคลุมปีก่อนหน้า) -- ควรระวังตอนตีความผล
"""
import pandas as pd
import os

HERE = os.path.dirname(os.path.abspath(__file__))

df = pd.read_csv(f"{HERE}/Training_Values_Nofct_7day_Extended_lagfeat.csv")
df["Date_dt"] = pd.to_datetime(df["Date"], errors="coerce")

RELEASE_START = pd.Timestamp("2026-06-26")
RELEASE_RATE = 9446.4

df["is_release_active"] = (df["Date_dt"] >= RELEASE_START).astype(int)
df["release_rate_m3day"] = df["is_release_active"] * RELEASE_RATE

n_active = df["is_release_active"].sum()
print(f"Rows with is_release_active=1: {n_active}/{len(df)} "
      f"({df.loc[df['is_release_active']==1,'Date'].min()} to {df.loc[df['is_release_active']==1,'Date'].max()})")

out_cols = [c for c in df.columns if c != "Date_dt"]
df[out_cols].to_csv(f"{HERE}/Training_Values_with_release_flag.csv", index=False)
print("Saved Training_Values_with_release_flag.csv")
