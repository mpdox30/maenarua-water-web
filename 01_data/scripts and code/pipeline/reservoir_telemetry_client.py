"""
reservoir_telemetry_client.py
==============================
2026-07-14 เพิ่ม — client สำหรับดึงข้อมูลสถานีโทรมาตร (สสน.) ของอ่างเก็บน้ำแม่นาเรือ
(station_code="RES002") มาใช้แทนการกรอกระดับน้ำ/ฝนด้วยมือในไฟล์ <year>_<month>_MNR.xlsx
(ดู RESERVOIR_AUTOMATION_DESIGN.md และ reservoir_water_balance.py)

=== การตั้งค่า (ทำครั้งเดียวต่อเครื่องที่จะรัน scheduled task) ===

ตั้ง environment variable ชื่อ RESERVOIR_TELEMETRY_API_URL เป็น link เต็มที่ได้จาก สสน.
(รูปแบบ https://wea.hii.or.th:3005/api/v1/<uuid>?username=...&password=...) — ตาม convention
เดียวกับ gee_auth.py (GEE_SERVICE_ACCOUNT_KEY) คือ **ห้าม hardcode credential ลงซอร์สโค้ดที่
commit เข้า git เด็ดขาด** เพราะ URL นี้มี password ฝังอยู่ตรงๆ ใน query string

ไม่ตั้ง env var ไว้ -> ฟังก์ชันใน module นี้จะ raise RuntimeError ทันทีตอนเรียก (ไม่ fallback
เงียบๆ เพราะไม่มี "โหมด personal credential" แบบ GEE ให้ fallback ไปใช้)

=== ข้อจำกัดสำคัญของ API นี้ (ยืนยันจากการเรียกจริง 2026-07-14) ===

1. คืนค่าเฉพาะ "ค่าล่าสุด" ของแต่ละ data_type เท่านั้น ไม่มี query parameter สำหรับดึงข้อมูล
   ย้อนหลังเป็นช่วงเวลา (ไม่พบใน response structure ที่ทดสอบ) -- ถ้าต้องการประวัติรายชั่วโมง
   (เพื่อรวมฝน 24 ชม. และคำนวณ spillway overflow ที่ต้องใช้ระดับน้ำรายชั่วโมง) ต้อง **poll
   API นี้เป็นระยะเอง** (เช่นทุก 1 ชม. ผ่าน Windows Task Scheduler แบบเดียวกับ
   sar_background_job.py) แล้วสะสมผลไว้ในไฟล์ log ของตัวเอง -- ยังไม่ได้ implement ส่วนนี้
   (ดู TODO ท้ายไฟล์)
2. response มีหลายสถานีปนกันมาด้วย (RES002=แม่นาเรือ, RES004/RES005/RES006=อ่างอื่นในพื้นที่
   ใกล้เคียง) -- ต้อง filter ด้วย station_code="RES002" เสมอ (ทำให้อัตโนมัติแล้วใน
   fetch_latest_readings())
3. rainfall ที่ได้เป็น data_type="rainfall_1h" (สะสม 1 ชม.) ไม่ใช่ "24 ชม." แบบที่สูตรใน
   บัญชีน้ำต้องการ (คอลัมน์ G "Cumulative rainfall over the past 24 hours") -- ต้องรวม 24 ค่า
   จากการ poll เอง (ดู TODO)
4. expire_datetime ของ link นี้ = 2028-07-06 (ตาม response จริง) -- ถ้าเลยวันนี้ไปแล้วต้องขอ
   link ใหม่จาก สสน.

TODO (ยังไม่ implement — เป็นงานถัดไปหลัง client พื้นฐานนี้):
  - ฟังก์ชัน append_reading_to_log() / load_telemetry_log() -- เก็บผลแต่ละรอบ poll ลง CSV
    local (เสนอ path: 01_data/Reservoirs/telemetry_log/RES002_hourly.csv)
  - ฟังก์ชัน aggregate_rain_24h(log, as_of) -- รวม rainfall_1h 24 ค่าล่าสุดก่อน as_of
  - ฟังก์ชัน get_hourly_levels_for_day(log, date) -- ดึงระดับน้ำ 24 ค่าของวันนั้น (สำหรับ
    reservoir_water_balance.compute_spillway_overflow_m3())
  - สคริปต์ reservoir_telemetry_background_job.py (poll ทุก 1 ชม. ผ่าน Task Scheduler) --
    เสนอให้ mirror โครงสร้างเดียวกับ sar_background_job.py ที่มีอยู่แล้วในโปรเจกต์นี้
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Optional

logger = logging.getLogger("data_pipeline")

RESERVOIR_TELEMETRY_API_URL_ENV = "RESERVOIR_TELEMETRY_API_URL"
DEFAULT_STATION_CODE = "RES002"  # อ่างเก็บน้ำแม่นาเรือ (ยืนยันจาก response จริง 2026-07-14)

# data_type ที่ API นี้คืนมาต่อสถานี (ยืนยันจากการเรียกจริง 2026-07-14)
KNOWN_DATA_TYPES = (
    "water_level", "rainfall_1h", "temperature", "humidity", "pressure", "solar",
)


def _get_api_url() -> str:
    url = os.environ.get(RESERVOIR_TELEMETRY_API_URL_ENV)
    if not url:
        raise RuntimeError(
            f"ไม่พบ environment variable {RESERVOIR_TELEMETRY_API_URL_ENV} -- ต้องตั้งค่าก่อนเรียก "
            "reservoir_telemetry_client (ดู docstring หัวไฟล์นี้สำหรับวิธีตั้งค่า) "
            "ห้าม hardcode URL/password ลงซอร์สโค้ดที่ commit เข้า git"
        )
    return url


def fetch_latest_readings(station_code: str = DEFAULT_STATION_CODE, timeout: float = 15.0) -> dict:
    """
    เรียก API สถานีโทรมาตรจริง แล้วกรองเฉพาะ station_code ที่ต้องการ (default RES002 =
    แม่นาเรือ) คืนค่าเป็น dict แบนราบ (flat):

        {
            "station_code": "RES002",
            "station_name": "...",
            "measure_datetime": "2026-07-14 15:20:00",
            "water_level": 489.146,
            "rainfall_1h": 0,
            "temperature": 28.97,
            "humidity": 81.08,
            "pressure": 950.07,
            "solar": <float หรือ None ถ้า API ไม่ส่งมารอบนี้>,
        }

    raises RuntimeError ถ้า env var ไม่ได้ตั้ง, ValueError ถ้าเรียก API สำเร็จแต่ไม่พบ
    station_code ที่ขอใน response (เช่น station_code พิมพ์ผิด หรือ สสน. เปลี่ยนโครงสร้าง)
    """
    url = _get_api_url()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rows = [r for r in payload.get("data", []) if r.get("station_code") == station_code]
    if not rows:
        available = sorted({r.get("station_code") for r in payload.get("data", [])})
        raise ValueError(
            f"ไม่พบ station_code={station_code!r} ใน response ของ API "
            f"(station_code ที่มีจริงตอนนี้: {available})"
        )

    result = {
        "station_code": station_code,
        "station_name": rows[0].get("station_name"),
        "measure_datetime": rows[0].get("measure_datetime"),
    }
    for r in rows:
        dtype = r.get("data_type")
        if dtype in KNOWN_DATA_TYPES:
            result[dtype] = r.get("data")

    missing = [dt for dt in KNOWN_DATA_TYPES if dt not in result]
    if missing:
        logger.warning(
            "reservoir_telemetry_client: station %s ไม่มี data_type %s ในรอบนี้ "
            "(อาจเป็นปกติถ้าเซนเซอร์บางตัวไม่ได้ส่งค่ามาชั่วคราว)",
            station_code, missing,
        )

    return result
