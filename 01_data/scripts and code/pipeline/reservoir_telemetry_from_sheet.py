"""
reservoir_telemetry_from_sheet.py
===================================
2026-07-14 เพิ่ม — อ่าน log โทรมาตรที่ผู้ใช้ตั้ง schedule ให้ดึงจาก API (สสน.) ทุก 10 นาที
แล้วบันทึกลง Google Sheet เอง (แทนที่จะให้ pipeline นี้ poll API ตรงเอง — ผู้ใช้มี
infrastructure การ poll อยู่แล้วผ่าน Apps Script ของตัวเอง) รูปแบบชีตอ้างอิงจากไฟล์ตัวอย่าง
Telemetry_Mae_Na_Rua.xlsx ที่ผู้ใช้ส่งให้ (แท็บ "wide_log" — 1 แถวต่อรอบ poll, คอลัมน์
<station_code>_<data_type> เช่น RES002_water_level, RES002_rainfall_1h)

โมดูลนี้แทนที่แนวทาง "poll API ตรงเองทุกชั่วโมง" ที่เสนอไว้ใน reservoir_telemetry_client.py /
RESERVOIR_AUTOMATION_DESIGN.md (TODO เดิม) — reservoir_telemetry_client.py ยังใช้ได้สำหรับ
ดึงค่าล่าสุดแบบ ad-hoc/debug แต่สำหรับ production ให้ใช้โมดูลนี้อ่านจาก log ที่สะสมไว้แล้วแทน

=== การตั้งค่า ===

รองรับ 2 แหล่งข้อมูล (ตั้งค่าอย่างใดอย่างหนึ่ง):

  1. ไฟล์ local (.xlsx ที่ export/ดาวน์โหลดมาจาก Google Sheet ด้วยมือ หรือ sync อัตโนมัติ
     ผ่านโปรแกรมอื่น เช่น Google Drive Desktop ที่ mount โฟลเดอร์ไว้) — ส่ง path ตรงๆ ให้
     load_wide_log(source=<path>)
  2. Google Sheet ที่ "Publish to web" เป็น CSV (File > Share > Publish to web > เลือกแท็บ
     "wide_log" > รูปแบบ CSV) จะได้ link ประมาณ
     https://docs.google.com/spreadsheets/d/e/<id>/pub?gid=<gid>&single=true&output=csv
     ซึ่งดึงด้วย HTTP GET ธรรมดาไม่ต้องมี OAuth — ตั้ง env var
     RESERVOIR_TELEMETRY_SHEET_CSV_URL เป็น link นี้ แล้วเรียก
     load_wide_log(source=None) (จะไปอ่านจาก env var เอง)

     ข้อควรระวัง: การ publish to web ทำให้ใครก็ได้ที่มี link เข้าถึงข้อมูลได้ (ไม่ต้อง login) —
     ถ้าข้อมูลอ่อนไหวเกินกว่าจะเผยแพร่แบบนี้ ให้ใช้ Google Sheets API + Service Account แทน
     (รูปแบบเดียวกับ gee_auth.py) — ยังไม่ได้ implement เส้นทางนี้ในไฟล์นี้ (ไฟล์นี้ทำแค่เส้นทาง
     publish-to-web เพราะตั้งค่าง่ายกว่ามากสำหรับ use case นี้)

=== สิ่งสำคัญที่ต้องรู้ก่อนใช้ผลจากไฟล์นี้ ===

1. **rainfall_1h เป็นค่าสะสมแบบ rolling 1 ชั่วโมง ไม่ใช่ค่าเพิ่มต่อรอบ poll (10 นาที)** —
   ถ้าเอาทุกแถว (poll ทุก 10 นาที, 6 แถว/ชม.) มาบวกกันตรงๆ จะนับซ้ำฝนเดิมประมาณ 6 เท่า
   ฟังก์ชันในไฟล์นี้ป้องกันปัญหานี้ด้วยการหาแถวที่ "ใกล้เวลาหลักชั่วโมง" ที่สุด (เช่น ใกล้ 07:00,
   08:00, ...) แล้วเอาแค่ 24 ค่านั้นมาบวกกัน

   **แก้บั๊กแล้ว 2026-07-14**: เดิมใช้วิธี "แถวล่าสุดภายในชั่วโมงนั้น" (เช่น ชั่วโมง 07:00-07:59
   เอาแถวล่าสุดที่เจอในช่วงนั้น) ซึ่งพบว่าผิด — ยืนยันจากข้อมูลจริง 2026-07-11 ที่ระดับน้ำขยับจาก
   489.224 (อ่านที่ 07:00 น. พอดี) เป็น 489.216 (อ่านที่ 07:40-07:50 น.) วิธีเดิมจะไปหยิบ 489.216
   มาใช้แทนที่จะเป็น 489.224 ที่ถูกต้อง ทำให้ Storage/ΔS ของวันถัดไปเพี้ยนไปหลักพัน m3 (ตรวจพบ
   จากการรัน reservoir_daily_orchestration.py จริงแล้วเทียบกับไฟล์ทางการ ไม่ตรงกันเกินคาด) แก้เป็น
   หาแถว "ใกล้เวลาเป้าหมายที่สุด" (ภายใน ±30 นาที) แทน — ดู _nearest_reading_per_hour_mark()

2. **ผลหลังแก้บั๊กข้อ 1**: รัน reservoir_daily_orchestration.py เต็มสาย (telemetry + release_log
   + water_balance) เทียบกับ Inflow จริงในไฟล์ 2026_July_MNR.xlsx ได้ผล:
     - 2026-07-12: คำนวณได้ 1548.45 m3 เทียบกับไฟล์ทางการ 1548.48 m3 (ตรงกันแทบสนิท)
     - 2026-07-13: คำนวณได้ 0.00 m3 เทียบกับไฟล์ทางการ 0.00 m3 (ตรงกัน)
     - 2026-07-14: คำนวณได้ 14343.76 m3 เทียบกับไฟล์ทางการ 12175.07 m3 (ต่างกัน ~2169 m3)
   วันที่ 14 ต่างกันมากกว่าเพราะฝน 24 ชม. คำนวณได้ 17.0mm แต่ไฟล์ทางการมี 24.4mm — ผลต่าง
   7.4mm × พื้นที่ผิวน้ำ (~360,000 m2) ≈ 2,660 m3 ใกล้เคียงกับผลต่าง Inflow ที่เห็น ยืนยันว่า
   ต้นเหตุคือ **window ของฝน 24 ชม. ยังไม่ตรงกับที่ไฟล์ทางการใช้เป๊ะ** (สมมติฐาน 07:00→07:00
   ยังไม่ยืนยัน 100%) ไม่ใช่บั๊กใน storage/level lookup อีกต่อไป (ข้อ 1 แก้แล้ว 2 ใน 3 วันตรงเป๊ะ)
   ควรเก็บข้อมูลขนานกันมากกว่านี้ (หลายๆ วัน โดยเฉพาะวันฝนตกหนัก) ถึงจะสรุปได้ชัดว่า window ที่
   ถูกต้องคืออะไร (ดู TODO ท้ายไฟล์)

3. station ที่ใช้คือ RES002 (อ่างเก็บน้ำแม่นาเรือ) เท่านั้น — ไฟล์ log มีอีก 3 อ่างปนมาด้วย
   (RES004, RES005/RES006) ถูกกรองทิ้งอัตโนมัติ

TODO:
  - เก็บข้อมูลขนานกับไฟล์ MNR.xlsx ทางการอีกหลายวัน เพื่อยืนยัน/ปรับ window convention ของฝน
    24 ชม. ให้ตรงกับที่ใช้จริง (ข้อ 2 ด้านบน)
  - เพิ่มเส้นทาง Google Sheets API + Service Account เป็นทางเลือกแทน publish-to-web ถ้าผู้ใช้
    ต้องการความเป็นส่วนตัวมากกว่านี้
  - เขียน orchestration script ที่เรียก load_wide_log() + compute_daily_inputs() ทุกวัน
    (เช่นตอน 07:05 น. หลังข้อมูล 07:00 เข้า log) แล้วป้อนต่อให้
    reservoir_water_balance.compute_daily_row() + O จาก Google Form (ยังไม่มี) → เขียนผลลง
    live data source ที่ data_pipeline.py._ri_load_raw_monthly_data() อ่านได้
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import os
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("data_pipeline")

RESERVOIR_TELEMETRY_SHEET_CSV_URL_ENV = "RESERVOIR_TELEMETRY_SHEET_CSV_URL"

# 2026-07-14: ผู้ใช้ให้ link "Publish to web" จริงมา (แก้จากที่ถูกใส่ผิดตำแหน่งไว้ในค่าคงที่ด้านบน
# โดยไม่ตั้งใจ -- ค่าคงที่ด้านบนต้องเป็น "ชื่อ" env var ไม่ใช่ตัว URL เอง) เก็บไว้เป็นค่า default
# ที่นี่แทน เพื่อให้ใช้งานได้ทันทีแม้ไม่ได้ตั้ง env var (สะดวกกว่าตอน dev/ทดสอบ) แต่แนะนำให้ย้ายไป
# ตั้งเป็น env var RESERVOIR_TELEMETRY_SHEET_CSV_URL แทนตอนใช้งานจริงบนเครื่องที่รัน scheduled task
# (ความเสี่ยงต่ำกว่า credential ของ reservoir_telemetry_client.py มาก เพราะ publish-to-web
# เป็น read-only แชร์แบบ public link อยู่แล้ว แต่หลักการเดียวกัน -- ไม่ผูกกับซอร์สโค้ดถาวร)
#
# หมายเหตุ 2026-07-14: ทดสอบ fetch link นี้แล้วได้ response ว่างเปล่า (ไม่มี error แต่ไม่มีข้อมูล) --
# ทั้งแบบมี gid=32321322 และไม่มี gid สงสัยว่า gid นี้อาจชี้ไปที่แท็บ "ชีต1" (แท็บว่างเปล่าในไฟล์
# ตัวอย่างที่ส่งมา) แทนที่จะเป็นแท็บ "wide_log" -- ต้องตรวจสอบว่า publish ตั้งค่าให้แท็บ "wide_log"
# หรือยัง (Google Sheets ต้อง publish ทีละแท็บแยกกัน ถ้า publish "Entire Document" ต้องดู gid ให้ตรง
# แท็บที่ต้องการ) หรือรอ 2-3 นาทีให้ publish settings propagate แล้วลองใหม่
DEFAULT_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZaUw7h38I-vxVO7OMxl6UDZwGiGDoZLqj2sPGG29uepQ4WNG1NBVklhVdLONeRayrleL24giIA8gu"
    "/pub?gid=32321322&single=true&output=csv"
)

STATION_CODE = "RES002"


def _parse_wide_log_xlsx(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["wide_log"]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if r[1] is not None]


_DT_RE = __import__("re").compile(r"^(\d+)-(\d+)-(\d+)\s+(\d+):(\d+):(\d+)")


def _parse_dt_lenient(s: str) -> dt.datetime:
    """
    Google Sheets CSV export ไม่ zero-pad ชั่วโมง/นาที/วินาทีที่เป็นเลขหลักเดียว (เช่น
    "2026-07-11 0:00:00" แทนที่จะเป็น "00:00:00") ซึ่งทำให้ dt.datetime.fromisoformat() ของ
    Python < 3.11 error ทันที (ยืนยันบั๊กนี้จากไฟล์ CSV จริงที่ export จากลิงก์ publish-to-web
    2026-07-14) — parse ด้วย regex เองแทนเพื่อรองรับทั้งสองแบบ
    """
    m = _DT_RE.match(s.strip())
    if not m:
        return dt.datetime.fromisoformat(s)
    y, mo, d, h, mi, se = (int(x) for x in m.groups())
    return dt.datetime(y, mo, d, h, mi, se)


def _parse_wide_log_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        if not row.get("measure_datetime"):
            continue
        row["measure_datetime"] = _parse_dt_lenient(row["measure_datetime"])
        out.append(row)
    return out


def load_wide_log(source: Optional[str] = None) -> list[dict]:
    """
    โหลด log แบบ wide (1 แถว/รอบ poll, คอลัมน์ <station>_<data_type>) จาก:
      - source เป็น path ไฟล์ .xlsx local -> อ่านแท็บ "wide_log" ด้วย openpyxl
      - source เป็น path ไฟล์ .csv local -> อ่านตรงๆ (เช่นไฟล์ที่ได้จากเปิดลิงก์ publish-to-web
        ในเบราว์เซอร์แล้วดาวน์โหลดมาเอง — ยืนยันรูปแบบตรงกับที่ parser นี้รองรับแล้ว 2026-07-14)
      - source เป็น None -> อ่านจาก env var RESERVOIR_TELEMETRY_SHEET_CSV_URL (CSV publish-to-web)
      - source เป็น string ที่ขึ้นต้นด้วย http -> ปฏิบัติเป็น CSV URL ตรงๆ

    คืนค่า list ของ dict ต่อแถว (key เป็นชื่อคอลัมน์ตรงตัวจาก header)
    """
    if source and not source.startswith("http"):
        path = Path(source)
        if path.suffix.lower() == ".csv":
            with open(path, encoding="utf-8") as f:
                return _parse_wide_log_csv(f.read())
        return _parse_wide_log_xlsx(path)

    url = source or os.environ.get(RESERVOIR_TELEMETRY_SHEET_CSV_URL_ENV)
    if not url:
        url = DEFAULT_SHEET_CSV_URL
        logger.warning(
            "ไม่ได้ระบุ source และไม่ได้ตั้ง env var %s -- ใช้ DEFAULT_SHEET_CSV_URL แทน "
            "(แนะนำให้ตั้ง env var บนเครื่องที่รัน scheduled task จริงแทนการพึ่งค่า default นี้)",
            RESERVOIR_TELEMETRY_SHEET_CSV_URL_ENV,
        )
    req = urllib.request.Request(url, headers={"Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8")
    return _parse_wide_log_csv(text)


def _nearest_reading_per_hour_mark(
    rows: list[dict], hour_marks: list[dt.datetime], station_code: str = STATION_CODE,
    tolerance_minutes: int = 30,
) -> dict[dt.datetime, dict]:
    """
    หาแถว (จาก poll ทุก ~10 นาที) ที่ "ใกล้เวลาเป้าหมายที่สุด" สำหรับแต่ละ hour_mark ที่ระบุ
    (ไม่ใช่ "แถวล่าสุดภายในชั่วโมงนั้น" — เคยมีบั๊กจากวิธีนั้นมาก่อน: ถ้า poll ล่าสุดในชั่วโมง
    07:00-07:59 ดันเป็น 07:50 น. จะได้ระดับน้ำของ 07:50 ไปใช้แทนที่จะเป็นระดับน้ำ ณ 07:00 น. จริงๆ
    ซึ่งกระทบ Storage lookup ที่ต้องการค่า ณ เวลาอ้างอิงที่แน่นอน ไม่ใช่ค่าประมาณในช่วงนั้น —
    ยืนยันบั๊กนี้จากข้อมูลจริง 2026-07-11 ที่ระดับน้ำขยับจาก 489.224 (07:00) เป็น 489.216 (07:40-07:50)
    ทำให้ Storage/ΔS ของวันถัดไปเพี้ยนไปหลักพัน m3)

    ถ้าไม่มีแถวไหนอยู่ในช่วง ±tolerance_minutes ของ hour_mark นั้น จะไม่มี key นั้นใน dict ที่คืนค่า
    (แปลว่าข้อมูลขาดช่วงจริง ไม่ใช่แค่ประมาณเอา)
    """
    level_key = f"{station_code}_water_level"
    rain_key = f"{station_code}_rainfall_1h"
    candidates = []
    for r in rows:
        mt = r["measure_datetime"]
        level = r.get(level_key)
        if mt is None or level in (None, ""):
            continue
        rain_raw = r.get(rain_key)
        candidates.append((mt, float(level), float(rain_raw) if rain_raw not in (None, "") else None))
    candidates.sort(key=lambda c: c[0])

    result: dict[dt.datetime, dict] = {}
    tol = dt.timedelta(minutes=tolerance_minutes)
    for mark in hour_marks:
        best = None
        best_dist = None
        for mt, level, rain in candidates:
            dist = abs(mt - mark)
            if dist > tol:
                continue
            if best_dist is None or dist < best_dist:
                best, best_dist = (mt, level, rain), dist
        if best is not None:
            result[mark] = {"measure_datetime": best[0], "level_msl": best[1], "rain_1h_mm": best[2]}
    return result


def compute_daily_inputs(rows: list[dict], target_date: dt.date, station_code: str = STATION_CODE) -> dict:
    """
    คำนวณอินพุตดิบสำหรับ reservoir_water_balance.compute_daily_row() ของวันที่ target_date
    โดยใช้ window "07:00 ของ target_date ย้อนหลัง 24 ชม." (สมมติฐานตาม header ไฟล์ต้นฉบับ —
    ยังไม่ยืนยัน 100% ดูข้อ 2 ใน docstring หัวไฟล์)

    คืนค่า dict:
        {
            "level_msl": <ระดับน้ำที่ 07:00 ของ target_date หรือ None ถ้าไม่มีข้อมูล>,
            "rain_24h_mm": <รวมฝน 24 ชม. หรือ None ถ้าไม่มีข้อมูลครบ>,
            "hourly_levels_msl": <list ระดับน้ำ 24 ค่า สำหรับ compute_spillway_overflow_m3(),
                                   ค่าไหนขาดหายจะเติมด้วยค่าที่ใกล้ที่สุดที่มี (forward/backward
                                   fill) — ถ้าขาดทั้งหมดจะเป็น list ว่าง>,
            "hours_covered": <จำนวนชั่วโมงที่มีข้อมูลจริงจาก 24 ชม. (ไว้เช็คความสมบูรณ์)>,
            "data_complete": <bool — True ถ้า hours_covered == 24 และมีค่าที่ 07:00 พอดี>,
        }
    """
    end_dt = dt.datetime.combine(target_date, dt.time(7, 0))
    start_dt = end_dt - dt.timedelta(hours=24)
    hour_marks = [start_dt + dt.timedelta(hours=h) for h in range(1, 25)]  # ...end_dt เป็นตัวสุดท้าย

    marks = _nearest_reading_per_hour_mark(rows, hour_marks, station_code)

    hourly_levels = []
    rain_total = 0.0
    hours_covered = 0
    last_known_level = None
    for mark in hour_marks:
        b = marks.get(mark)
        if b is not None:
            hours_covered += 1
            if b["rain_1h_mm"] is not None:
                rain_total += b["rain_1h_mm"]
            last_known_level = b["level_msl"]
            hourly_levels.append(b["level_msl"])
        else:
            # เติมช่องว่างด้วยค่าระดับน้ำล่าสุดที่รู้ (ระดับน้ำเปลี่ยนช้า ต่างจากฝนที่ห้าม
            # ประมาณเพราะจะทำให้ผิดทันที) -- ถ้ายังไม่มีค่าใดๆ มาก่อนเลยจะเป็น None
            hourly_levels.append(last_known_level)

    level_07 = marks.get(end_dt, {}).get("level_msl")

    return {
        "level_msl": level_07,
        "rain_24h_mm": rain_total if hours_covered > 0 else None,
        "hourly_levels_msl": [h for h in hourly_levels if h is not None],
        "hours_covered": hours_covered,
        "data_complete": hours_covered == 24 and level_07 is not None,
    }
