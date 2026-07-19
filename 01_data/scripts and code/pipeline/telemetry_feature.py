"""
telemetry_feature.py
=====================
โมดูลแยกสำหรับดึงและ parse ข้อมูลสถานีโทรมาตรจริง (API ของ กช.สสน., ทดสอบและยืนยันเมื่อ
2026-07-06) — เก็บ Water_Level_t (m) และข้อมูลอากาศประกอบของสถานี RES002 (อ่างเก็บน้ำแม่นาเรือ)

ที่มา API: https://wea.hii.or.th:3005/api/v1/<token>?username=...&password=...
(username/password ฝังอยู่ใน query string เอง ไม่ใช่ header — เป็นแบบแผนของผู้ให้บริการ)
project="แม่นาเรือ", expire_datetime="2028-07-06" (ยังใช้ได้อีกนาน ณ วันที่เขียนโมดูลนี้)

**สถานะการทดสอบ (2026-07-06) — ยังไม่เชื่อมเข้า data_pipeline.py จริง ตามที่ผู้ใช้สั่งชัดเจน
ว่า "ยังไม่ต้องเชื่อมเข้า data_pipeline.py จริง แค่ทดสอบฟังก์ชัน parse ก่อน":**

  1. Response format = JSON เดียว ไม่ใช่ time-series array — คืนค่า "ล่าสุดเท่านั้น" (latest-only)
     ไม่มี pagination หรือ time-series ในการเรียกแบบไม่ระบุ parameter เพิ่ม
  2. มี 5 สถานีตามที่ผู้ให้บริการวางแผนไว้ แต่ ณ วันที่ทดสอบใช้งานได้จริงแค่ 4 สถานี:
     RES002 (อ่างแม่นาเรือ, เป้าหมายหลักของ pipeline นี้), RES004, RES005, RES006 — RES003
     อยู่ระหว่างซ่อมบำรุง (ยืนยันจากผู้ใช้ 2026-07-06) ไม่ต้องรอ/ตามหาอีก
  3. Response เป็น "long format": 1 แถวต่อ 1 (station_code x data_type) ไม่ใช่ 1 แถวต่อสถานี
     data_type ที่เจอต่อสถานี (6 ค่าเสมอ ทั้ง 4 สถานี): water_level, rainfall_1h, temperature,
     humidity, pressure, solar
  4. **ทดสอบ query parameter หา historical endpoint แล้วไม่สำเร็จ**: ลอง start_date/end_date และ
     date (รูปแบบ YYYY-MM-DD) ทั้งหมดถูก "เพิกเฉย" (ignore) — API ยังคืนค่า snapshot ล่าสุดเสมอ
     ไม่ว่าจะใส่ parameter อะไรเพิ่มไป แปลว่า **ไม่มีทางเรียกข้อมูลย้อนหลังทั้งวันมาเช็คจำนวน
     144 records/วัน (24hr x 6 ครั้ง/hr) ได้จากการเดา parameter เอง** — ถ้าต้องการ historical
     query จริง ต้องขอเอกสาร API จาก กช.สสน. โดยตรงว่ามี endpoint/parameter ชื่ออะไรบ้าง
  5. **ความถี่จริงที่สังเกตได้ (ยืนยันด้วยการเรียกจริงหลายรอบ ห่างกันจริงตามเวลานาฬิกา ไม่ใช่แค่
     เดา):**
       - เรียกครั้งที่ 1 เวลาประมาณ 19:12-19:13 น. (เวลาไทย) -> measure_datetime = 19:00:00
         (latency ~12-13 นาที)
       - เรียกครั้งที่ 2 (parameter ต่างกันแต่เวลาใกล้กันมาก) -> measure_datetime = 19:00:00 (เหมือนเดิม)
       - เรียกครั้งที่ 3 เวลาประมาณ 19:30 น. (ห่างจากครั้งแรก ~24-25 นาทีจริง) -> measure_datetime
         เปลี่ยนเป็น 19:30:00 แล้ว (latency ~7 นาที)
     สรุป: **step ที่สังเกตได้จริงคือ 19:00 -> 19:30 = 30 นาที ไม่ใช่ 10 นาทีตามที่คาดไว้แต่แรก**
       - เรียกครั้งที่ 4 เวลาประมาณ 19:42 น. (ห่างจากครั้งที่ 3 อีก ~4-5 นาที) -> measure_datetime
         **ย้อนกลับไปเป็น 19:00:00 อีกครั้ง!** ทั้งที่เวลาผ่านไปแล้วกว่า 41 นาทีจากรอบแรก และเคย
         เห็น 19:30:00 ไปแล้วในรอบก่อนหน้า
     **นี่ไม่ใช่แค่คำถามเรื่อง "10 นาทีหรือ 30 นาที" แต่เป็นสัญญาณว่า response ไม่ monotonic จริง**
     (measure_datetime ล่าสุดที่ได้ ไม่รับประกันว่าจะใหม่กว่าหรือเท่ากับรอบก่อนหน้าเสมอ — น่าจะมาจาก
     backend หลายตัว/cache ไม่ sync กันฝั่งผู้ให้บริการ) **ผลกระทบสำคัญ: ห้ามเขียนทับค่าที่เก็บไว้ด้วย
     ข้อมูลรอบใหม่แบบไม่เช็คก่อนเด็ดขาด ต้องเทียบ measure_datetime ใหม่กับล่าสุดที่เก็บไว้เสมอ (ดู
     telemetry_history_store.py ซึ่ง implement การเช็คนี้โดยเฉพาะ พร้อม log แยกประเภท non-monotonic
     ออกจาก data-gap ให้ตรวจสอบความถี่ของปัญหานี้ในระยะยาวได้)** ยังไม่ได้เก็บข้อมูลต่อเนื่องนานพอ
     (หลายชั่วโมงขึ้นไป) เพื่อสรุปว่า cadence ที่แท้จริงคือเท่าไหร่ หรือ non-monotonic เกิดถี่แค่ไหน
     — compute_evap_term() และฟังก์ชันอื่นใน reservoir_reference_data.py ที่อ้างอิง "รายวัน" ไม่กระทบ
     จากเรื่องนี้ แต่ถ้าจะทำ feature ระดับ sub-daily ในอนาคต ห้ามสมมติความถี่ใดๆ จนกว่าจะมีข้อมูล
     สะสมพอ (ดู telemetry_history_store.py) หรือได้เอกสาร API อย่างเป็นทางการจาก กช.สสน.
  6. `remark` field ("ข้อมูลเบื้องต้น ยังไม่ผ่านการตรวจสอบขั้นสุดท้าย") ต้องเก็บ/log ไว้ทุกครั้งที่ดึง
     ข้อมูลจริง (ตามที่ผู้ใช้สั่ง) — เก็บอยู่ใน key "remark" ของ dict ที่ parse_telemetry_response()
     คืนค่า เพื่อให้ผู้เรียกใช้ log ต่อได้เอง (โมดูลนี้เอง log ให้อัตโนมัติผ่าน logger ด้วย)

โครงสร้าง JSON จริงที่ทดสอบแล้ว (2026-07-06):
    {
      "project_name": str, "owner": str, "expire_datetime": str, "link": str, "remark": str,
      "data": [
        {"station_code": str, "station_name": str, "latitude": float, "longitude": float,
         "tambon": str, "amphoe": str, "province": str, "station_type": str,
         "station_type_name": str, "left_bank_msl": float|null, "right_bank_msl": float|null,
         "ground_level_msl": float, "measure_datetime": "YYYY-MM-DD HH:MM:SS",
         "data": float, "data_type": str},
        ...
      ]
    }
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# 2026-07-20 แก้ — เดิมไฟล์นี้ hardcode URL/password ของ API สถานีโทรมาตรไว้ตรงๆ แล้วหลุดติดไปกับ
# git commit จนถูกดันขึ้น GitHub (repo เปลี่ยนเป็น public แล้วตอนที่พบ) ได้ลบออกจาก git history ทั้งหมด
# ด้วย git filter-repo แล้ว (2026-07-20) และแก้ให้อ่านจาก environment variable แทน ตาม convention
# เดียวกับ reservoir_telemetry_client.py (RESERVOIR_TELEMETRY_API_URL) — **ต้องขอรหัสผ่านใหม่จาก
# กช.สสน. มาแทนตัวเดิมที่หลุดไปด้วย เพราะถือว่ารั่วแล้วไม่ว่าจะลบออกจาก git หรือไม่**
#
# วิธีตั้งค่า (ทำครั้งเดียวต่อเครื่องที่จะรัน): ตั้ง environment variable ชื่อ
# TELEMETRY_API_URL เป็น URL เต็มที่ได้จาก กช.สสน. (รูปแบบ
# https://wea.hii.or.th:3005/api/v1/<uuid>?username=...&password=...) ห้าม hardcode ค่าจริงลง
# ไฟล์นี้อีกเด็ดขาด ไม่ตั้ง env var ไว้ -> TELEMETRY_URL จะเป็น None และฟังก์ชันดึงข้อมูลจริงใน
# โมดูลนี้จะ raise RuntimeError ตอนเรียก (ดู reservoir_telemetry_client.py เป็นตัวอย่าง)
TELEMETRY_URL: Optional[str] = os.environ.get("TELEMETRY_API_URL")
TELEMETRY_REQUEST_TIMEOUT_SEC = 20

# สถานีเป้าหมายหลักของ pipeline นี้ (อ่างเก็บน้ำแม่นาเรือ) — สถานีอื่น (RES004/005/006) มีอยู่ใน
# response เดียวกันแต่ไม่ใช่เป้าหมายของโมเดล Reservoir_inflow นี้
TARGET_STATION_CODE = "RES002"

# data_type ที่คาดว่าจะเจอต่อสถานี (ยืนยันจากการทดสอบจริง 2026-07-06) — ใช้เป็น schema สำหรับ
# wide-format output คงที่ (คีย์เดิมเสมอแม้บาง data_type จะหายไปจาก response จริงบางรอบ ใช้ None แทน)
EXPECTED_DATA_TYPES = [
    "water_level",
    "rainfall_1h",
    "temperature",
    "humidity",
    "pressure",
    "solar",
]

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline_log.txt"


def _get_logger() -> logging.Logger:
    """
    ใช้ logger ชื่อ "data_pipeline" เดียวกับ mei_feature.py/chirps_feature.py โดยตั้งใจ (ดู
    docstring เดียวกันในไฟล์เหล่านั้นสำหรับเหตุผลเต็ม) — ให้ handler เดิมถ้า data_pipeline.py
    เรียก setup_logging() ไปแล้ว หรือสร้างเองถ้ารันไฟล์นี้แบบ standalone
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger("data_pipeline")
    log.setLevel(logging.INFO)
    log.propagate = False

    if log.handlers:
        return log

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    log.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)

    return log


logger = _get_logger()


# ---------------------------------------------------------------------------
# Step 1: parse_telemetry_response() — long format -> wide format เฉพาะสถานีเป้าหมาย
# ---------------------------------------------------------------------------
def parse_telemetry_response(
    response_json: dict[str, Any],
    target_station_code: str = TARGET_STATION_CODE,
) -> dict[str, Any]:
    """
    แปลง response ดิบของ API โทรมาตร (long format: 1 แถว/1 station x 1 data_type) เป็น
    wide format (1 dict, 1 คีย์ต่อ 1 data_type) เฉพาะสถานี target_station_code (ค่าเริ่มต้น
    RES002 = อ่างเก็บน้ำแม่นาเรือ)

    ออกแบบตามหลัก error isolation เดียวกับ mei_feature.py/chirps_feature.py: **ไม่ raise
    exception ออกนอกฟังก์ชันนี้เลย** ไม่ว่า response จะผิดรูปแบบแค่ไหน — คืนค่า dict ที่มี
    "fetch_error"/"station_found" ระบุปัญหาแทนเสมอ เพื่อให้ pipeline หลัก (เวลาเชื่อมจริงในอนาคต)
    ตัดสินใจต่อได้เองว่าจะ fallback อย่างไร ไม่ล้มทั้ง pipeline เพราะสถานีเดียวมีปัญหา

    Parameters
    ----------
    response_json : dict
        JSON ที่ parse แล้วจาก response ของ API (เช่น requests.Response.json())
    target_station_code : str
        รหัสสถานีที่ต้องการดึง (ค่าเริ่มต้น "RES002")

    คืนค่า: dict
      {
        "station_code": str,
        "station_found": bool,          # False ถ้าไม่เจอสถานีนี้เลยใน response (ดู log WARNING)
        "station_name": str | None,
        "measure_datetime": str | None,  # "YYYY-MM-DD HH:MM:SS" ของแถวแรกที่เจอ (ทุก data_type
                                          # ของสถานีเดียวกัน ควรมี measure_datetime ตรงกันเสมอ
                                          # ตามที่ทดสอบจริง — ถ้าไม่ตรงกัน log WARNING เพิ่ม)
        "water_level": float | None,
        "rainfall_1h": float | None,
        "temperature": float | None,
        "humidity": float | None,
        "pressure": float | None,
        "solar": float | None,
        "missing_data_types": list[str],  # data_type ที่คาดไว้ (EXPECTED_DATA_TYPES) แต่หายไปจาก
                                           # response รอบนี้ของสถานีนี้
        "remark": str | None,             # คำเตือนจากผู้ให้บริการ ("ข้อมูลเบื้องต้น...") — เก็บทุกครั้ง
        "project_name": str | None,
        "fetch_error": str | None,        # None ถ้าไม่มีปัญหา, string อธิบายปัญหาถ้ามี
      }
    """
    result: dict[str, Any] = {
        "station_code": target_station_code,
        "station_found": False,
        "station_name": None,
        "measure_datetime": None,
        **{dt: None for dt in EXPECTED_DATA_TYPES},
        "missing_data_types": list(EXPECTED_DATA_TYPES),
        "remark": None,
        "project_name": None,
        "fetch_error": None,
    }

    if not isinstance(response_json, dict):
        msg = f"response_json ไม่ใช่ dict (ได้ type={type(response_json).__name__}) — parse ไม่ได้"
        logger.error("parse_telemetry_response(): %s", msg)
        result["fetch_error"] = msg
        return result

    # remark/project_name เก็บไว้เสมอไม่ว่าสถานีเป้าหมายจะเจอหรือไม่ (ผู้ใช้สั่งให้ log ทุกครั้ง)
    result["remark"] = response_json.get("remark")
    result["project_name"] = response_json.get("project_name")
    if result["remark"]:
        logger.info("Telemetry API remark: %s", result["remark"])

    data_rows = response_json.get("data")
    if not isinstance(data_rows, list):
        msg = "response_json ไม่มี key 'data' เป็น list ที่ใช้ได้ (โครงสร้าง API อาจเปลี่ยนไปจากที่ทดสอบไว้)"
        logger.error("parse_telemetry_response(): %s", msg)
        result["fetch_error"] = msg
        return result

    # กรองเฉพาะแถวของสถานีเป้าหมาย
    station_rows = [row for row in data_rows if row.get("station_code") == target_station_code]

    if not station_rows:
        # *** ห้าม silent fail — log WARNING ให้เห็นชัดเจนตามที่ผู้ใช้สั่ง ***
        # เผื่อวันหน้า RES002 เองซ่อมบำรุงบ้าง (เหมือน RES003 ตอนนี้) ต้องรู้ทันทีไม่ใช่รู้ทีหลังตอน
        # โมเดลทำนายพังเพราะ feature เป็น None เงียบๆ
        all_codes_found = sorted({row.get("station_code") for row in data_rows if row.get("station_code")})
        msg = (
            f"ไม่เจอสถานี {target_station_code} เลยใน response รอบนี้ "
            f"(สถานีที่เจอจริง: {all_codes_found}) — RES002 อาจอยู่ระหว่างซ่อมบำรุงชั่วคราว "
            f"เหมือนที่ RES003 เคยเป็น หรือ API มีปัญหา ตรวจสอบก่อนใช้ feature Water_Level_t "
            f"รอบนี้ (จะได้ค่า None ทั้งหมด)"
        )
        logger.warning("parse_telemetry_response(): %s", msg)
        result["fetch_error"] = msg
        return result

    result["station_found"] = True
    result["station_name"] = station_rows[0].get("station_name")

    measure_datetimes = {row.get("measure_datetime") for row in station_rows}
    if len(measure_datetimes) > 1:
        logger.warning(
            "parse_telemetry_response(): สถานี %s มี measure_datetime ไม่ตรงกันข้าม data_type "
            "ในรอบเดียวกัน (%s) — ใช้ค่าของแถวแรกที่เจอ แต่ควรตรวจสอบว่า API ส่งข้อมูลสอดคล้องกันจริงหรือไม่",
            target_station_code, sorted(measure_datetimes),
        )
    result["measure_datetime"] = station_rows[0].get("measure_datetime")

    found_data_types = set()
    for row in station_rows:
        dtype = row.get("data_type")
        if dtype in EXPECTED_DATA_TYPES:
            result[dtype] = row.get("data")
            found_data_types.add(dtype)
        else:
            logger.info(
                "parse_telemetry_response(): เจอ data_type '%s' ที่ไม่อยู่ใน EXPECTED_DATA_TYPES "
                "ของสถานี %s (ไม่ได้ error แค่ไม่ได้ map เข้า schema wide-format ตอนนี้ — เพิ่มใน "
                "EXPECTED_DATA_TYPES ถ้าต้องการใช้ค่านี้ด้วย)",
                dtype, target_station_code,
            )

    result["missing_data_types"] = [dt for dt in EXPECTED_DATA_TYPES if dt not in found_data_types]
    if result["missing_data_types"]:
        logger.warning(
            "parse_telemetry_response(): สถานี %s ขาด data_type ต่อไปนี้ในรอบนี้: %s",
            target_station_code, result["missing_data_types"],
        )

    logger.info(
        "parse_telemetry_response(): สถานี %s (%s) measure_datetime=%s water_level=%s "
        "rainfall_1h=%s temperature=%s humidity=%s pressure=%s solar=%s",
        result["station_code"], result["station_name"], result["measure_datetime"],
        result["water_level"], result["rainfall_1h"], result["temperature"],
        result["humidity"], result["pressure"], result["solar"],
    )

    return result


# ---------------------------------------------------------------------------
# Step 2: fetch_telemetry_latest() — เรียก API จริง + parse ในฟังก์ชันเดียว (สำหรับเทส standalone)
# ---------------------------------------------------------------------------
def fetch_telemetry_latest(
    url: str = TELEMETRY_URL,
    target_station_code: str = TARGET_STATION_CODE,
    timeout: int = TELEMETRY_REQUEST_TIMEOUT_SEC,
    fetch_fn: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """
    ดึงข้อมูลล่าสุดจาก API โทรมาตรจริง แล้ว parse ด้วย parse_telemetry_response() ในฟังก์ชันเดียว
    — ใช้สำหรับเทส standalone (ดู __main__ ด้านล่าง) **ยังไม่ได้เชื่อมเข้า data_pipeline.py จริง**
    ตามที่ผู้ใช้สั่งไว้ชัดเจน (2026-07-06)

    fetch_fn: จุด inject สำหรับเทส (ดู pattern เดียวกับ mei_feature._download_mei_raw()) ค่าเริ่มต้น
    เป็น requests.get จริง

    ไม่ raise exception ออกนอกฟังก์ชัน (เหมือน parse_telemetry_response()) — ถ้าเรียก API ไม่สำเร็จ
    (network error, HTTP error, JSON parse ไม่ได้) คืนค่า dict schema เดียวกับ parse_telemetry_response()
    โดย fetch_error ระบุสาเหตุ
    """
    try:
        logger.info("Fetching telemetry จาก %s ...", url.split("?")[0])
        resp = fetch_fn(url, timeout=timeout)
        resp.raise_for_status()
        response_json = resp.json()
    except Exception as exc:
        msg = f"เรียก/parse response จาก telemetry API ไม่สำเร็จ: {exc}"
        logger.error("fetch_telemetry_latest(): %s", msg)
        result: dict[str, Any] = {
            "station_code": target_station_code,
            "station_found": False,
            "station_name": None,
            "measure_datetime": None,
            **{dt: None for dt in EXPECTED_DATA_TYPES},
            "missing_data_types": list(EXPECTED_DATA_TYPES),
            "remark": None,
            "project_name": None,
            "fetch_error": msg,
        }
        return result

    return parse_telemetry_response(response_json, target_station_code=target_station_code)


if __name__ == "__main__":
    # รันไฟล์นี้ตรงๆ เพื่อทดสอบดึง+parse ข้อมูลจริงจาก API แล้ว print ผลลัพธ์ — ยังไม่เชื่อมกับ
    # data_pipeline.py/โมเดลหลัก ตามขอบเขตงานที่ระบุไว้ (แค่ทดสอบว่า parse ถูกต้องก่อน)
    import json

    print(json.dumps(fetch_telemetry_latest(), indent=2, ensure_ascii=False))
