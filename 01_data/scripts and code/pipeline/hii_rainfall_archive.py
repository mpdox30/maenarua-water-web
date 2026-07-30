"""
hii_rainfall_archive.py
========================
2026-07-30 เพิ่ม — ดึงข้อมูลฝนรายชั่วโมง "ทางการ" จาก HII open data
(https://tiservice.hii.or.th/opendata/data_catalog/hourly_rain/) มาใช้แทนค่าที่ monitoring_data_
builder.py ประมาณเอง จาก wide_log Google Sheet (rolling snapshot poll ทุก ~10 นาที)

เหตุผล (สรุปจากที่คุยกับผู้ใช้ 2026-07-30 หลังผู้ใช้ทักว่ากราฟฝนของเว็บเราไม่ตรงกับเว็บโทรมาตร
ทางการของ สสน./HII):

  1. เว็บทางการใช้ไฟล์ข้อมูลชุดนี้ (หรือต้นทางเดียวกัน) ซึ่งเป็นค่าฝนรายชั่วโมง "ตรงชั่วโมงปฏิทินจริง"
     ผ่าน QC แล้ว (มี quality_flag แยก "ไม่มีข้อมูล" (null,null) ออกจาก "ฝน 0 มม.จริง" (0,N) อย่าง
     ชัดเจน) -- ต่างจากของเราที่ประมาณจากค่า rolling 1-ชม. ที่สุ่มเวลา poll เอง (last-value-per-hour
     trick ใน monitoring_data_builder.build_station_rainfall_hourly())
  2. ยืนยัน station_code ตรงกับที่เราใช้เป๊ะ (RES002/RES004/RES005/RES006) -- เช็คแล้วทั้ง 3 สถานี
     (RES002, RES005, RES006) มี schema เดียวกัน: station_code,measure_datetime,rainfall_1h,
     quality_flag
  3. Public, ไม่ต้อง auth, license Creative Commons Attribution Non-Commercial (data.hii.or.th/
     en/dataset/hii-rainfall) -- ข้อมูลสาธารณะ ไม่มีการจำกัดการเข้าถึง

ข้อจำกัดสำคัญที่ต้องรู้ก่อนใช้:
  - อัปเดตเป็น "รายเดือน" เท่านั้น -- ไฟล์ของเดือน M จะถูกเผยแพร่หลังเดือน M ปิดแล้ว (สังเกตจาก
    last-modified ของโฟลเดอร์ก่อนหน้า: 202601 ปรับปรุง 2026-02-02, 202602 ปรับปรุง 2026-03-02 ฯลฯ)
    ดังนั้น**เดือนปัจจุบัน (เดือนที่ยังไม่จบ) จะไม่มีข้อมูลเลย** -- ฟังก์ชันในไฟล์นี้จะคืนค่าว่างเปล่า
    (ไม่ error) สำหรับเดือนที่ยังไม่ปิด ให้ผู้เรียก fallback ไปใช้ wide_log ของเราเองสำหรับช่วงนั้น
  - เช็คแล้ว RES005 เพิ่งมีไฟล์ปรากฏใน archive นี้ตั้งแต่ ม.ค. 2569 เป็นต้นมา (ม.ค. 2568 ยังไม่มี
    ไฟล์ของสถานีนี้เลย) -- อย่าสมมติว่ามีข้อมูลย้อนไปถึงปี 2012 ที่ dataset ระบุไว้ (นั่นคือปีที่เริ่ม
    ทำ dataset โดยรวม ไม่ใช่ปีที่เริ่มมีสถานีนี้)
  - ค่า "null" ในคอลัมน์ rainfall_1h/quality_flag (เป็น string "null" ไม่ใช่ CSV field ว่างเปล่า)
    หมายถึงไม่มีข้อมูลจริง -- parse เป็น None ไม่ใช่ 0.0

หมายเหตุเรื่อง "วันอุตุนิยมวิทยา" (สำคัญมาก ถ้าจะเทียบ/รวมเป็นรายวัน): dataset นี้มี resource
คู่กันชื่อ "ข้อมูลฝน รายวัน" ซึ่งนิยามวันว่า "7.01 น. ของวันนี้ ถึง 7 โมงเช้าของวันถัดไป" (ไม่ใช่
เที่ยงคืน-เที่ยงคืนแบบปฏิทิน) -- ยืนยันด้วยตัวเลขจริงแล้ว (ดู docstring ของ monitoring_data_builder.py
build_station_rainfall_hourly()) -- ไฟล์นี้ (hii_rainfall_archive.py) คืนค่าเป็นรายชั่วโมงดิบเท่านั้น
ไม่ได้ทำ daily rollup เอง -- ฝั่งที่ทำ daily/weekly/monthly aggregation (ปัจจุบันคือ JS ใน
monitoring.html) ต้องใช้ boundary 7:01-7:00 เองตอน bucket ถ้าจะให้ตรงกับเว็บทางการ

Cache: ดาวน์โหลดครั้งเดียวต่อ (station_code, year, month) ที่ "ปิด" แล้วเท่านั้น เก็บที่
01_data/Reservoirs/reference/hii_rainfall_archive/<year>/<month:02d>/<station_code>.csv --
ไฟล์เดือนที่ปิดแล้วไม่เปลี่ยนแปลงอีก (immutable) จึงไม่ต้อง re-fetch ซ้ำ ลดโหลด HII และเร็วขึ้นมาก
สำหรับ pipeline ที่รันถี่ (ทุก ~15 นาที)
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("data_pipeline")

HOURLY_RAIN_BASE_URL = "https://tiservice.hii.or.th/opendata/data_catalog/hourly_rain"
REQUEST_TIMEOUT_SEC = 20

CACHE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "Reservoirs" / "reference" / "hii_rainfall_archive"
)


def _is_month_closed(year: int, month: int, today: Optional[dt.date] = None) -> bool:
    """เดือน (year, month) 'ปิด' แล้วหรือยัง (ผ่านไปแล้วอย่างน้อย 1 เดือนเต็ม) -- HII เผยแพร่ไฟล์ของ
    เดือน M หลังเดือน M จบจริงเท่านั้น (สังเกตจาก last-modified ของโฟลเดอร์ archive จริง)"""
    today = today or dt.date.today()
    return (year, month) < (today.year, today.month)


def _cache_path(station_code: str, year: int, month: int) -> Path:
    return CACHE_DIR / str(year) / f"{month:02d}" / f"{station_code}.csv"


def _parse_hourly_csv(text: str, station_code: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for r in reader:
        if r.get("station_code") != station_code:
            continue
        mt_raw = r.get("measure_datetime")
        if not mt_raw:
            continue
        try:
            mt = dt.datetime.strptime(mt_raw.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning("hii_rainfall_archive: parse measure_datetime ไม่สำเร็จ (%r) ข้ามแถวนี้", mt_raw)
            continue

        rain_raw = (r.get("rainfall_1h") or "").strip()
        qf_raw = (r.get("quality_flag") or "").strip()
        rain_val = None if rain_raw in ("", "null") else _safe_float(rain_raw)
        qf_val = None if qf_raw in ("", "null") else qf_raw

        rows.append({"measure_datetime": mt, "rainfall_1h": rain_val, "quality_flag": qf_val})
    return rows


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except ValueError:
        return None


def fetch_station_month(
    station_code: str, year: int, month: int, today: Optional[dt.date] = None, use_cache: bool = True
) -> list[dict]:
    """
    ดึงข้อมูลฝนรายชั่วโมงของ station_code สำหรับเดือน (year, month) เดียว

    คืนค่า list of {"measure_datetime": datetime, "rainfall_1h": float|None, "quality_flag": str|None}
    เรียงเวลาเก่า -> ใหม่ตามที่ไฟล์ต้นทางให้มา (ไม่ sort ซ้ำ เพราะไฟล์ HII เรียงอยู่แล้ว)

    คืนค่า [] เสมอถ้า:
      - เดือนนั้นยังไม่ปิด (ยังไม่มีไฟล์เผยแพร่)
      - เครือข่ายมีปัญหา / HTTP error / สถานีนี้ไม่มีไฟล์ในเดือนนั้น (เช่นสถานีเพิ่งติดตั้งทีหลัง)
    ไม่ raise exception ออกนอกฟังก์ชันนี้เลย (ตาม convention เดียวกับโมดูลอื่นในไพพ์ไลน์นี้ --
    ปัญหาแหล่งข้อมูลเสริมไม่ควรทำให้ทั้ง pipeline ล้ม)
    """
    if not _is_month_closed(year, month, today):
        logger.debug(
            "hii_rainfall_archive: เดือน %04d-%02d ยังไม่ปิด (หรือเป็นเดือนอนาคต) -- HII ยังไม่เผยแพร่ไฟล์ ข้ามไป",
            year, month,
        )
        return []

    cache_path = _cache_path(station_code, year, month)
    if use_cache and cache_path.exists():
        try:
            text = cache_path.read_text(encoding="utf-8")
            return _parse_hourly_csv(text, station_code)
        except Exception:
            logger.warning("hii_rainfall_archive: อ่าน cache %s ไม่สำเร็จ -- จะลองดึงใหม่จาก HII", cache_path, exc_info=True)

    url = f"{HOURLY_RAIN_BASE_URL}/{year}/{year}{month:02d}/{station_code}.csv"
    try:
        req = urllib.request.Request(url, headers={"Accept": "text/csv"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.info(
                "hii_rainfall_archive: ไม่มีไฟล์ %s (HTTP 404) -- สถานี %s อาจยังไม่มีข้อมูลในเดือนนี้ ถือเป็นเรื่องปกติ",
                url, station_code,
            )
        else:
            logger.warning("hii_rainfall_archive: ดึง %s ไม่สำเร็จ (HTTP %s)", url, exc.code)
        return []
    except Exception:
        logger.warning("hii_rainfall_archive: ดึง %s ไม่สำเร็จ (เครือข่าย/timeout)", url, exc_info=True)
        return []

    if use_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
            tmp_path.write_text(text, encoding="utf-8")
            tmp_path.replace(cache_path)
        except Exception:
            logger.warning("hii_rainfall_archive: เขียน cache %s ไม่สำเร็จ (ไม่กระทบผลลัพธ์รอบนี้)", cache_path, exc_info=True)

    return _parse_hourly_csv(text, station_code)


def load_archive_hourly(
    station_code: str, start_date: dt.date, end_date: dt.date, today: Optional[dt.date] = None
) -> list[dict]:
    """
    ดึงข้อมูลฝนรายชั่วโมงของ station_code ครอบคลุมช่วง [start_date, end_date] โดยไล่ดึงทีละเดือนที่
    เกี่ยวข้องแล้วรวมกัน (เฉพาะเดือนที่ "ปิด" แล้วเท่านั้น -- เดือนที่ยังไม่ปิดจะไม่มีข้อมูลจากฟังก์ชัน
    นี้ ผู้เรียกต้องเติมช่วงนั้นเองจากแหล่งอื่น เช่น wide_log)

    คืนค่า list เรียงเวลาเก่า -> ใหม่ กรองเฉพาะแถวที่ measure_datetime อยู่ในช่วงที่ขอ
    """
    if start_date > end_date:
        return []

    months: list[tuple[int, int]] = []
    y, m = start_date.year, start_date.month
    while (y, m) <= (end_date.year, end_date.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    all_rows: list[dict] = []
    for y, m in months:
        all_rows.extend(fetch_station_month(station_code, y, m, today=today))

    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_dt = dt.datetime.combine(end_date, dt.time.max)
    return [r for r in all_rows if start_dt <= r["measure_datetime"] <= end_dt]
