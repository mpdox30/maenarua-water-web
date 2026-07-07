"""
telemetry_hourly_aggregate.py
================================
รวมข้อมูล telemetry ราย 10-30 นาที (จาก telemetry_history_<station>.csv ที่ telemetry_history_store.py
สะสมไว้) เป็น "รายชั่วโมง" (24 แถว/วัน) สำหรับใช้เป็น input ของการคำนวณ Spill ในอนาคต -- สูตรเดิมของ
Spill ต้องการ water_level 24 ค่า/ชม./วัน ป้อนเข้า weir formula ทีละชั่วโมง (ดู
reservoir_reference_data.py docstring: "Spill = sum ของ weir formula 24 ค่า/ชม. ใน 1 วัน")

สถานะ (2026-07-06): เป็นโครง (skeleton) -- ฟังก์ชันทำงานได้จริงและทดสอบแล้วด้วยข้อมูลจำลอง แต่
"ยังไม่เชื่อมเข้ากับการคำนวณ Spill จริง" ใน reservoir_reference_data.py ตามที่ผู้ใช้สั่งชัดเจน
(2026-07-06) -- รอการตัดสินใจเรื่อง gap-fallback ก่อน (ดู telemetry_gap_fallback_design.md ที่ร่างคู่กัน
ไว้ ยังไม่ implement จริง เป็นแค่เอกสารออกแบบ)

การตัดสินใจสำคัญที่บันทึกไว้ที่นี่ (สำหรับตอนเชื่อมจริงในอนาคต ห้ามเปลี่ยนโดยไม่ทบทวนเหตุผลนี้ก่อน):

  1. Aggregation method ต่อคอลัมน์ไม่เหมือนกัน (ไม่ใช้ mean กับทุกคอลัมน์ เพราะความหมายทาง
     กายภาพต่างกัน):
       - water_level -> "last" (ค่าล่าสุดในชั่วโมงนั้น = สภาพระดับน้ำ ณ ตอนสิ้นชั่วโมง ตรงกับที่
         weir formula เดิมต้องการ (ค่า ณ จุดเวลาหนึ่ง) การใช้ mean จะ smooth เหตุการณ์เปลี่ยนแปลง
         เร็ว (เช่นช่วงฝนตกหนัก) ออกไปโดยไม่ตั้งใจ)
       - rainfall_1h -> "last" (field นี้เป็นค่า "สะสม 1 ชั่วโมงที่ผ่านมา" อยู่แล้วในตัวมันเอง ต่อ
         1 reading ถ้ามีหลาย reading ในชั่วโมงเดียวกันแล้วเอามา sum จะนับซ้ำข้อมูลเดิม -- ต้องใช้
         reading ล่าสุดของชั่วโมงนั้นเท่านั้น ซึ่งควรจะครอบคลุมทั้งชั่วโมงอยู่แล้วในตัวมันเอง)
       - temperature/humidity/pressure/solar -> "mean" (สัญญาณต่อเนื่อง ไม่ได้ใช้ตรงกับ Spill
         แต่เก็บไว้เผื่อ feature อื่นในอนาคต ใช้ mean ตามปกติของสัญญาณต่อเนื่องที่ไม่ใช่ค่าสะสม)

  2. n_readings ต่อชั่วโมงต้อง track เสมอ -- ใช้แยกแยะ "ชั่วโมงที่มีข้อมูลจริง (แม้จะไม่ครบตาม
     cadence ปกติ)" ออกจาก "ชั่วโมงที่เป็น gap สนิท (n_readings=0)" สองอย่างนี้มีนัยต่างกันเวลาเอาไป
     ตัดสินใจ fallback (ดู telemetry_gap_fallback_design.md) -- ไม่ควรถือว่า "มี 1 reading" เหมือนกับ
     "ไม่มี reading เลย"

  3. ไม่ใช้ cadence คงที่ในการคำนวณ (เช่นไม่สมมติว่าต้องมี 2 หรือ 6 reading ต่อชั่วโมงเป๊ะ) เพราะ
     ยืนยันแล้วจากการทดสอบ API จริง (ดู telemetry_feature.py docstring) ว่าความถี่จริงไม่คงที่ (เจอ
     ทั้ง step 30 นาที และ non-monotonic) -- resample(\'1h\') ของ pandas จัดการ irregular interval ได้
     เองอยู่แล้วโดยไม่ต้องสมมติ cadence

โครงสร้าง output: pandas.DataFrame, index = hour_start (Timestamp, ต้นชั่วโมง เช่น 10:00:00 แทน
ช่วง 10:00:00-10:59:59), คอลัมน์:
    water_level_last, rainfall_1h_last, temperature_mean, humidity_mean, pressure_mean,
    solar_mean, n_readings (int), is_gap (bool = n_readings==0)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

_LAST_VALUE_COLS = ["water_level", "rainfall_1h"]
_MEAN_VALUE_COLS = ["temperature", "humidity", "pressure", "solar"]


def load_telemetry_history(history_csv_path):
    """โหลด telemetry_history_<station>.csv เป็น DataFrame พร้อม parse measure_datetime เป็น
    datetime index (ไม่ sort/dedupe เพิ่ม เพราะ telemetry_history_store.py รับประกันแล้วว่าไฟล์นี้
    เรียงเวลาจริงเสมอ ไม่มี non-monotonic/duplicate ปนอยู่ -- ดู append_telemetry_record())"""
    df = pd.read_csv(history_csv_path, parse_dates=["measure_datetime"])
    df = df.set_index("measure_datetime").sort_index()
    return df


def aggregate_telemetry_hourly(history_csv_path, date_range=None):
    """รวมข้อมูล raw (ราย 10-30 นาที ตามที่สังเกตได้จริง ไม่คงที่) เป็นรายชั่วโมง

    date_range: (pd.Timestamp, pd.Timestamp) หรือ None -- resample("1h") เติมชั่วโมงว่างระหว่าง
    ข้อมูลจริงให้เองอยู่แล้ว ไม่ต้องระบุ date_range เพื่อการนี้ -- ใช้เฉพาะตอนต้องการขยายขอบเขตเกิน
    กว่าข้อมูลจริงที่มี (เช่นเช็คครบ 24 ชม.ของวันที่สนใจ แต่ไฟล์มีข้อมูลจริงแค่บางช่วง)
    """
    df = load_telemetry_history(history_csv_path)

    if df.empty:
        return pd.DataFrame(columns=[
            "water_level_last", "rainfall_1h_last",
            "temperature_mean", "humidity_mean", "pressure_mean", "solar_mean",
            "n_readings", "is_gap",
        ])

    hourly_last = df[_LAST_VALUE_COLS].resample("1h").last()
    hourly_last.columns = [c + "_last" for c in hourly_last.columns]

    hourly_mean = df[_MEAN_VALUE_COLS].resample("1h").mean()
    hourly_mean.columns = [c + "_mean" for c in hourly_mean.columns]

    n_readings = df[_LAST_VALUE_COLS[0]].resample("1h").count().rename("n_readings")

    result = pd.concat([hourly_last, hourly_mean, n_readings], axis=1)

    if date_range is not None:
        start, end = date_range
        full_index = pd.date_range(start=start.floor("h"), end=end.ceil("h"), freq="1h", inclusive="left")
        result = result.reindex(full_index)
        result["n_readings"] = result["n_readings"].fillna(0).astype(int)

    result["is_gap"] = result["n_readings"] == 0
    result.index.name = "hour_start"

    return result


def _build_sample_history_csv(path):
    """Helper สำหรับ __main__ เท่านั้น -- สร้างไฟล์ history จำลองไว้ทดสอบ aggregate_telemetry_hourly()"""
    rows = []
    rows.append({
        "fetch_time": "2026-07-06T10:05:00", "measure_datetime": "2026-07-06 10:05:00",
        "water_level": 489.10, "rainfall_1h": 0.0, "temperature": 27.0, "humidity": 80.0,
        "pressure": 951.0, "solar": 3.0, "gap_hours_since_last": None,
        "data_gap_flag": False, "remark": "x",
    })
    rows.append({
        "fetch_time": "2026-07-06T10:35:00", "measure_datetime": "2026-07-06 10:35:00",
        "water_level": 489.12, "rainfall_1h": 0.5, "temperature": 27.5, "humidity": 79.0,
        "pressure": 951.2, "solar": 3.5, "gap_hours_since_last": 0.5,
        "data_gap_flag": False, "remark": "x",
    })
    rows.append({
        "fetch_time": "2026-07-06T12:50:00", "measure_datetime": "2026-07-06 12:50:00",
        "water_level": 489.20, "rainfall_1h": 2.0, "temperature": 28.0, "humidity": 78.0,
        "pressure": 950.8, "solar": 4.0, "gap_hours_since_last": 1.25,
        "data_gap_flag": True, "remark": "x",
    })
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "telemetry_history_TEST.csv"
        _build_sample_history_csv(p)

        print("=== resample เติม gap ระหว่างข้อมูลให้เองอยู่แล้ว (ชม. 11:00) ===")
        print(aggregate_telemetry_hourly(p))

        print()
        print("=== date_range ขยายเกินข้อมูลจริง (08:00-14:00) ===")
        print(aggregate_telemetry_hourly(
            p, date_range=(pd.Timestamp("2026-07-06 08:00:00"), pd.Timestamp("2026-07-06 14:00:00"))
        ))
