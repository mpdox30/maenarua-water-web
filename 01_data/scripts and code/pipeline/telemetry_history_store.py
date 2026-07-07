"""
telemetry_history_store.py
============================
สร้าง "ประวัติข้อมูลของตัวเอง" สำหรับสถานีโทรมาตร (telemetry_feature.py) เพราะ API จริง
(กช.สสน., ทดสอบ 2026-07-06) **ไม่รองรับ query ย้อนหลัง** — ลองแล้วทั้ง start_date/end_date/date
ถูกเพิกเฉยหมด คืนค่า snapshot ปัจจุบันเสมอ (ดู docstring telemetry_feature.py หัวข้อ 4)

แนวทาง (แทนที่จะรอ query ย้อนหลังจาก API ภายนอกที่ยังไม่รองรับ): ให้ pipeline เก็บสะสมเองทุกครั้ง
ที่ดึงสำเร็จ ต่อท้ายไฟล์ CSV เรื่อยๆ (append-only) กลายเป็นแหล่งข้อมูลย้อนหลังของตัวเอง

ที่มาของ 2 ปัญหาที่โมดูลนี้ต้องรับมือ (พบจากการทดสอบเรียก API จริงหลายรอบ 2026-07-06 — ดู
telemetry_feature.py docstring หัวข้อ 5 สำหรับ timeline เต็ม):

  1. **Non-monotonic timestamp**: เรียก 5 รอบตามเวลานาฬิกาจริง ได้ measure_datetime =
     19:00 -> 19:00 -> 19:30 -> 19:30 -> **19:00 (ย้อนกลับ!)** แปลว่า response ล่าสุดไม่รับประกัน
     ว่าจะ "ใหม่กว่าหรือเท่ากับ" รอบก่อนหน้าเสมอ (backend/cache ฝั่งผู้ให้บริการน่าจะไม่ sync กัน)
     ถ้าเขียนทับ state โดยไม่เช็คก่อน จะทำให้ประวัติที่เก็บเองมีข้อมูลสลับหน้า-หลังปนกันแบบไม่รู้ตัว

  2. **Data gap**: ถ้าสถานี RES002 หายไปจาก response หลายรอบติดกัน (เช่นซ่อมบำรุงเหมือน RES003
     ตอนนี้) parse_telemetry_response() จะคืนค่า None ทุก field แต่ **ไม่มีใครไปเช็คว่าช่วงเวลา
     ระหว่างข้อมูลจริงล่าสุดกับตอนนี้ห่างกันผิดปกติหรือไม่** — ถ้าไม่เช็ค ผลลัพธ์คือ feature
     (Water_Level_t, ที่จะใช้คำนวณ Spill/API_t ต่อ) จะดู "เหมือนไม่มีอะไรเปลี่ยน" ทั้งที่จริงคือ
     "ไม่มีข้อมูลช่วงนี้เลย" ซึ่งเป็นคนละความหมายกัน (ตามที่ผู้ใช้ระบุ 2026-07-06) ต้อง flag
     เป็น data gap ให้ชัดเจนแยกออกจากกรณี "ค่าจริงไม่เปลี่ยนเพราะระดับน้ำนิ่งจริง"

ทั้ง 2 กรณี log เป็น WARNING **คนละ tag กัน** ("[TELEMETRY_NON_MONOTONIC]" / "[TELEMETRY_DATA_GAP]")
ใน pipeline_log.txt ตัวเดียวกับโมดูลอื่น เพื่อให้ grep นับความถี่ย้อนหลังได้ง่าย และเพิ่มบันทึก
โครงสร้าง (telemetry_anomalies_<station>.csv) แยกต่างหากสำหรับวิเคราะห์เชิงปริมาณ (กี่ครั้ง/สัปดาห์
ฯลฯ) โดยไม่ต้อง parse text log เอง — ตามที่ผู้ใช้ขอ ("ต้องรู้ตัวว่าเป็นปัญหาเรื้อรัง ไม่ใช่ fluke
ครั้งเดียว")

ไฟล์ที่โมดูลนี้เขียน (ต่อสถานี, default RES002):
  - telemetry_history_<station>.csv   : แถวใหม่ทุกครั้งที่ measure_datetime ใหม่กว่าที่เก็บไว้จริง
                                         (ไม่มี duplicate/non-monotonic ปนอยู่ — เป็น "ความจริง
                                         เรียงเวลา" ล้วนๆ สำหรับใช้แทน historical query ของ API)
  - telemetry_anomalies_<station>.csv : 1 แถวต่อ 1 เหตุการณ์ผิดปกติ (non_monotonic หรือ data_gap)
                                         พร้อมรายละเอียดเปรียบเทียบ ใช้วิเคราะห์ความถี่ย้อนหลังได้

**สถานะ (2026-07-06): ยังไม่เชื่อมเข้า data_pipeline.py จริง เป็นโมดูลแยกสำหรับรันซ้ำๆ เก็บข้อมูล
สะสมด้วยตัวเอง (เช่นผ่าน scheduler ทุก 10-15 นาที) ตามที่ผู้ใช้สั่ง — ทดสอบ standalone ก่อน**
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from telemetry_feature import (
    TARGET_STATION_CODE,
    TELEMETRY_URL,
    EXPECTED_DATA_TYPES,
    fetch_telemetry_latest,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline_log.txt"
HISTORY_DIR = SCRIPT_DIR / "telemetry_history"

# เกณฑ์ช่องว่าง (ชั่วโมง) ที่ถือว่าเป็น "data gap" — ตั้งไว้ที่ 1 ชม. = ~2 เท่าของ step ที่สังเกตได้
# จริงสั้นที่สุด (30 นาที ดู telemetry_feature.py) แบบระมัดระวังไว้ก่อน **เป็นค่าประมาณชั่วคราว
# เท่านั้น** ยังไม่ยืนยัน cadence จริงจาก กช.สสน. — ปรับได้ผ่าน parameter gap_threshold_hours
# ทุกครั้งที่เรียก เมื่อมีข้อมูลสะสมมากพอหรือได้เอกสารทางการแล้วควรทบทวนค่านี้ใหม่
DEFAULT_GAP_THRESHOLD_HOURS = 1.0

HISTORY_FIELDS = [
    "fetch_time",           # เวลาจริงตอนโมดูลนี้ดึงสำเร็จ (ISO, ไม่ใช่ measure_datetime)
    "measure_datetime",
    "water_level",
    "rainfall_1h",
    "temperature",
    "humidity",
    "pressure",
    "solar",
    "gap_hours_since_last",  # None ถ้าเป็นแถวแรกของไฟล์ (ไม่มีอะไรเทียบ)
    "data_gap_flag",
    "remark",
]

ANOMALY_FIELDS = [
    "detected_at",           # เวลาจริงตอนตรวจพบ (ISO)
    "anomaly_type",          # "non_monotonic" | "data_gap"
    "station_code",
    "measure_datetime_new",
    "measure_datetime_last_stored",
    "gap_hours",             # None สำหรับ non_monotonic (ไม่มีความหมายเดียวกัน)
]


def _get_logger() -> logging.Logger:
    """ใช้ logger ชื่อ "data_pipeline" เดียวกับโมดูลอื่นทั้งหมดในไฟล์นี้ (ดู mei_feature.py/
    telemetry_feature.py สำหรับเหตุผลเต็ม)"""
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


def _history_path(station_code: str) -> Path:
    return HISTORY_DIR / f"telemetry_history_{station_code}.csv"


def _anomalies_path(station_code: str) -> Path:
    return HISTORY_DIR / f"telemetry_anomalies_{station_code}.csv"


def _read_last_history_row(history_csv_path: Path) -> Optional[dict[str, str]]:
    """อ่านแถวสุดท้ายของไฟล์ history (ถ้ามี) — ใช้ไฟล์เปิดอ่านตรงๆ ทีละแถว ไม่โหลด pandas
    เพราะไฟล์นี้จะยาวขึ้นเรื่อยๆ ตามเวลา (append-only log) ไม่จำเป็นต้องโหลดทั้งไฟล์เข้าหน่วยความจำ
    ทุกครั้งที่จะ append แค่ 1 แถว"""
    if not history_csv_path.exists():
        return None
    last_row = None
    with open(history_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_row = row
    return last_row


def _append_csv_row(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def append_telemetry_record(
    station_code: str = TARGET_STATION_CODE,
    url: str = TELEMETRY_URL,
    history_dir: Path = HISTORY_DIR,
    gap_threshold_hours: float = DEFAULT_GAP_THRESHOLD_HOURS,
    fetch_fn: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """
    จุดเรียกหลักของโมดูลนี้: ดึงข้อมูลล่าสุด (fetch_telemetry_latest) 1 ครั้ง แล้วตัดสินใจว่าจะ
    append เข้า telemetry_history_<station>.csv หรือไม่ ตามการเทียบ measure_datetime ใหม่กับ
    แถวสุดท้ายที่เก็บไว้จริง (ไม่ใช่แค่ "เก็บค่าล่าสุด" เฉยๆ — ดู docstring หัวไฟล์)

    Logic (ตามที่ผู้ใช้ระบุ 2026-07-06):
      1. Fetch ไม่สำเร็จเลย (fetch_error จาก fetch_telemetry_latest) -> ไม่แตะ history/anomalies
         เลย, คืนค่า status="fetch_failed", log ERROR (fetch_telemetry_latest ทำให้แล้ว)
      2. Fetch สำเร็จแต่สถานีเป้าหมายหายไป (station_found=False) -> เหมือนกรณี 1 (ไม่มี
         measure_datetime ให้เทียบ) แต่ log แยกว่าเป็น "สถานีหาย" ไม่ใช่ fetch พัง — คืนค่า
         status="station_missing"
      3. ไฟล์ history ยังไม่มี (แถวแรก) -> append ทันที ไม่มีอะไรเทียบ, gap_hours_since_last=None,
         status="appended_first"
      4. measure_datetime ใหม่ "ใหม่กว่า" แถวสุดท้ายที่เก็บไว้จริง (>) -> append ปกติ คำนวณ
         gap_hours_since_last = ผลต่างเป็นชั่วโมง ถ้า > gap_threshold_hours -> log
         "[TELEMETRY_DATA_GAP]" WARNING แยกประเภท + บันทึกลง anomalies_csv + data_gap_flag=True
         ในแถวที่ append, status="appended"
      5. measure_datetime ใหม่ "เท่ากับหรือเก่ากว่า" แถวสุดท้ายที่เก็บไว้ (<=) -> **ไม่ append**
         เข้า history หลัก (กันข้อมูลสลับหน้า-หลังปนกัน) แต่ log "[TELEMETRY_NON_MONOTONIC]"
         WARNING แยกประเภท + บันทึกลง anomalies_csv เสมอ (ไม่ error แต่ต้องรู้ตัวตามที่ผู้ใช้สั่ง),
         status="skipped_non_monotonic"

    คืนค่า: dict {"status": str, "station_code": str, "history_csv": str, "anomalies_csv": str,
                   "record": dict | None}  (record = แถวที่เพิ่ง append เข้า history, None ถ้า skip)
    """
    history_csv_path = history_dir / f"telemetry_history_{station_code}.csv"
    anomalies_csv_path = history_dir / f"telemetry_anomalies_{station_code}.csv"
    now_iso = datetime.now().isoformat(timespec="seconds")

    fetched = fetch_telemetry_latest(url=url, target_station_code=station_code, fetch_fn=fetch_fn)

    if fetched.get("fetch_error") and not fetched.get("station_found"):
        # แยก 2 สาเหตุที่ทำให้ไม่มี measure_datetime ให้ใช้: fetch พังจริง (network/HTTP/JSON)
        # vs fetch สำเร็จแต่สถานีหาย (เช่นซ่อมบำรุง) — สาเหตุหลังยังคืน dict ที่มี remark ได้
        # (fetch_telemetry_latest คืน remark=None เฉพาะตอน fetch พังจริงเท่านั้น ดู telemetry_feature.py)
        status = "station_missing" if fetched.get("remark") is not None or "ไม่เจอสถานี" in str(fetched.get("fetch_error")) else "fetch_failed"
        logger.warning(
            "append_telemetry_record(): ไม่ได้ append ข้อมูลรอบนี้ของสถานี %s (status=%s, "
            "reason=%s) — history/anomalies ไม่ถูกแก้ไข",
            station_code, status, fetched.get("fetch_error"),
        )
        return {
            "status": status,
            "station_code": station_code,
            "history_csv": str(history_csv_path),
            "anomalies_csv": str(anomalies_csv_path),
            "record": None,
        }

    new_measure_dt_str = fetched["measure_datetime"]
    new_measure_dt = datetime.strptime(new_measure_dt_str, "%Y-%m-%d %H:%M:%S")

    last_row = _read_last_history_row(history_csv_path)

    if last_row is None:
        # แถวแรกของไฟล์ — ไม่มีอะไรเทียบ append ได้เลย
        record = {
            "fetch_time": now_iso,
            "measure_datetime": new_measure_dt_str,
            "water_level": fetched["water_level"],
            "rainfall_1h": fetched["rainfall_1h"],
            "temperature": fetched["temperature"],
            "humidity": fetched["humidity"],
            "pressure": fetched["pressure"],
            "solar": fetched["solar"],
            "gap_hours_since_last": None,
            "data_gap_flag": False,
            "remark": fetched["remark"],
        }
        _append_csv_row(history_csv_path, HISTORY_FIELDS, record)
        logger.info(
            "append_telemetry_record(): แถวแรกของ %s — append measure_datetime=%s ไม่มีข้อมูลเก่าให้เทียบ",
            history_csv_path.name, new_measure_dt_str,
        )
        return {
            "status": "appended_first",
            "station_code": station_code,
            "history_csv": str(history_csv_path),
            "anomalies_csv": str(anomalies_csv_path),
            "record": record,
        }

    last_measure_dt = datetime.strptime(last_row["measure_datetime"], "%Y-%m-%d %H:%M:%S")

    if new_measure_dt <= last_measure_dt:
        # *** Non-monotonic — ต้อง log แยกประเภทชัดเจน (tag [TELEMETRY_NON_MONOTONIC]) ไม่ปนกับ
        # WARNING ทั่วไป เพื่อให้ grep นับความถี่ระยะยาวได้ตามที่ผู้ใช้ขอ ***
        logger.warning(
            "[TELEMETRY_NON_MONOTONIC] สถานี %s: measure_datetime รอบนี้ (%s) <= รอบที่เก็บไว้ล่าสุด "
            "(%s) — ข้าม (ไม่ append) กันข้อมูลสลับหน้า-หลังปนในประวัติ ดู telemetry_anomalies_%s.csv "
            "สำหรับสถิติสะสมของปัญหานี้",
            station_code, new_measure_dt_str, last_row["measure_datetime"], station_code,
        )
        anomaly_record = {
            "detected_at": now_iso,
            "anomaly_type": "non_monotonic",
            "station_code": station_code,
            "measure_datetime_new": new_measure_dt_str,
            "measure_datetime_last_stored": last_row["measure_datetime"],
            "gap_hours": None,
        }
        _append_csv_row(anomalies_csv_path, ANOMALY_FIELDS, anomaly_record)
        return {
            "status": "skipped_non_monotonic",
            "station_code": station_code,
            "history_csv": str(history_csv_path),
            "anomalies_csv": str(anomalies_csv_path),
            "record": None,
        }

    gap_hours = (new_measure_dt - last_measure_dt).total_seconds() / 3600.0
    is_gap = gap_hours > gap_threshold_hours

    record = {
        "fetch_time": now_iso,
        "measure_datetime": new_measure_dt_str,
        "water_level": fetched["water_level"],
        "rainfall_1h": fetched["rainfall_1h"],
        "temperature": fetched["temperature"],
        "humidity": fetched["humidity"],
        "pressure": fetched["pressure"],
        "solar": fetched["solar"],
        "gap_hours_since_last": round(gap_hours, 4),
        "data_gap_flag": is_gap,
        "remark": fetched["remark"],
    }
    _append_csv_row(history_csv_path, HISTORY_FIELDS, record)

    if is_gap:
        # *** Data gap — log แยก tag [TELEMETRY_DATA_GAP] ไม่ปนกับ non-monotonic ตามที่ผู้ใช้ขอ
        # ชัดเจนว่าเป็นคนละปัญหากัน (ช่วงเวลาห่างผิดปกติ vs ข้อมูลย้อนหลัง) ***
        logger.warning(
            "[TELEMETRY_DATA_GAP] สถานี %s: ช่องว่างระหว่างข้อมูล %.2f ชม. (เกณฑ์ %.2f ชม.) "
            "ระหว่าง %s -> %s — สถานีอาจหายไปจาก response หลายรอบติดกัน (เช่นซ่อมบำรุง) ต้องถือว่า "
            "'ไม่มีข้อมูลช่วงนี้จริง' ไม่ใช่ 'ค่าเดิมไม่เปลี่ยน' เมื่อคำนวณ feature ต่อ (Spill/API_t ฯลฯ)",
            station_code, gap_hours, gap_threshold_hours, last_row["measure_datetime"], new_measure_dt_str,
        )
        anomaly_record = {
            "detected_at": now_iso,
            "anomaly_type": "data_gap",
            "station_code": station_code,
            "measure_datetime_new": new_measure_dt_str,
            "measure_datetime_last_stored": last_row["measure_datetime"],
            "gap_hours": round(gap_hours, 4),
        }
        _append_csv_row(anomalies_csv_path, ANOMALY_FIELDS, anomaly_record)
    else:
        logger.info(
            "append_telemetry_record(): append สำเร็จ สถานี %s measure_datetime=%s "
            "(gap_hours_since_last=%.2f, ปกติ)",
            station_code, new_measure_dt_str, gap_hours,
        )

    return {
        "status": "appended",
        "station_code": station_code,
        "history_csv": str(history_csv_path),
        "anomalies_csv": str(anomalies_csv_path),
        "record": record,
    }


if __name__ == "__main__":
    # รันไฟล์นี้ตรงๆ 1 ครั้งเพื่อดึง+append 1 แถวเข้า telemetry_history_RES002.csv — ยังไม่เชื่อมกับ
    # data_pipeline.py ตามขอบเขตงานที่ระบุไว้ (ทดสอบสะสมข้อมูลด้วยตัวเองก่อน) รันซ้ำผ่าน scheduler
    # ทุก 10-15 นาทีตามที่ผู้ใช้ต้องการทดสอบ (ดู schedule_telemetry_poll ใน scheduled task ที่ตั้งไว้
    # แยกต่างหาก ถ้ามี)
    import json

    print(json.dumps(append_telemetry_record(), indent=2, ensure_ascii=False, default=str))
