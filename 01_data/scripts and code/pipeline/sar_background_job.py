"""
sar_background_job.py
======================
2026-07-11 เพิ่ม — สคริปต์ background job แยกต่างหากจาก data_pipeline.py หลัก สำหรับรัน
check_new_sar_image() + trigger_crop_classification() (ซึ่งตอนนี้ใช้เวลานาน — นาทีถึงหลายนาที
เพราะต้อง export+download GeoTIFF จาก GEE แล้ว classify ทุก pixel local — ดู docstring ของ
trigger_crop_classification() ใน sar_classification.py) โดยไม่บล็อก pipeline หลักที่ต้องรันจบ
เร็วทุกสัปดาห์ผ่าน Task Scheduler

เหตุผลที่แยก (ตามที่ผู้ใช้ระบุ): SAR ควรอัปเดตแค่ ~ทุก 7-10 วัน (ตาม revisit cycle ของ Sentinel-1)
ไม่ต้องรันพร้อมกับ pipeline หลักทุกรอบ — pattern เดียวกับ telemetry_history_store.py (โมดูลแยกที่
ตั้งใจให้รันซ้ำๆ ผ่าน scheduler ของตัวเอง เขียนผลสะสม/ล่าสุดไว้ที่ไฟล์ ให้ตัวอื่นมาอ่านทีหลัง)

การใช้งาน:
  - ตั้ง Windows Task Scheduler ให้รันไฟล์นี้แยกจาก run_pipeline.bat ทุก 7-10 วัน (หรือถี่กว่านั้นก็ได้
    เพราะ check_new_sar_image() มี min_days_between_runs=30 gate อยู่แล้ว — รัน job นี้บ่อยแค่ไหนก็ตาม
    จะ classify จริงแค่เมื่อถึงรอบ ไม่ใช่ทุกครั้งที่ job นี้ทำงาน)
  - data_pipeline.py หลัก เรียก read_latest_sar_result() (ฟังก์ชันในไฟล์นี้) แทนการเรียก
    check_new_sar_image()/trigger_crop_classification() ตรงๆ — อ่านไฟล์ JSON ที่ job นี้เขียนไว้
    ล่าสุด (เร็ว ไม่ต้องรอ GEE เลย) แทน

ไฟล์ที่เขียน (ใน 01_data/gis/sar_output/):
  - sar_result_latest.json      : ผลล่าสุดเสมอ (overwrite, atomic .tmp+replace) — ใช้โดย
                                   read_latest_sar_result()
  - sar_result_<year>_<date>.json : สำเนาแบบ dated เก็บไว้เป็น audit trail ทุกรอบที่ classify จริง
                                   (ไม่ overwrite ทับกัน)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sar_classification as sc

logger = logging.getLogger("sar_background_job")

SAR_JOB_OUTPUT_DIR = sc.GIS_DIR / "sar_output"
SAR_LATEST_RESULT_PATH = SAR_JOB_OUTPUT_DIR / "sar_result_latest.json"

# ผลลัพธ์ถือว่า "เก่าเกินไปให้เชื่อ" ถ้าเกินกี่วัน — data_pipeline.py ใช้ค่านี้เตือนใน step_status
# แทนที่จะ fail ทั้ง step (ไม่มีผล SAR ใหม่ไม่ควรทำให้ pipeline หลักล้มทั้งรอบ)
SAR_RESULT_STALE_AFTER_DAYS = 45  # กว้างกว่า min_days_between_runs=30 ของ check_new_sar_image() พอสมควร


def _write_json_atomic(path: Path, payload: dict) -> None:
    """เขียน JSON แบบ atomic (.tmp แล้วค่อย replace) — pattern เดียวกับ data_pipeline.py's save_results()"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    tmp_path.replace(path)


def run_sar_background_job(
    as_of_date: Optional[date] = None,
    gee_project: str = sc.DEFAULT_GEE_PROJECT,
) -> dict:
    """
    รัน 1 รอบของ background job: เช็คว่าถึงรอบ classify ใหม่หรือยัง (check_new_sar_image()) —
    ถ้ายัง ไม่ทำอะไรเลย (ไม่แตะ sar_result_latest.json เดิม ปล่อยให้ผลรอบก่อนหน้ายังใช้ได้ต่อ)
    ถ้าถึงรอบ รัน trigger_crop_classification() (ใช้เวลานาน) แล้วเขียนผลลง
    sar_result_latest.json + ไฟล์ dated แยกต่างหาก

    คืน dict {"ran": bool, "reason": str, "result": dict|None} — ไม่ raise (ตาม convention
    เดียวกับฟังก์ชันอื่นในไฟล์นี้/sar_classification.py — ให้ Task Scheduler เห็น exit code
    ปกติแม้ GEE ล้มเหลว จะได้ไม่ retry รัวๆ โดยไม่จำเป็น)
    """
    logger.info("=== sar_background_job เริ่มรอบใหม่ (as_of_date=%s) ===", as_of_date or "today")

    try:
        new_sar_image = sc.check_new_sar_image(as_of_date=as_of_date, gee_project=gee_project)
    except Exception as exc:
        logger.exception("check_new_sar_image() ล้มเหลวไม่คาดคิด")
        return {"ran": False, "reason": f"check_new_sar_image_error: {exc}", "result": None}

    if new_sar_image is None:
        logger.info("ยังไม่ถึงรอบ classify ใหม่ (หรือไม่มีภาพ S1 ใหม่) -- ไม่แตะผลลัพธ์เดิม จบรอบนี้")
        return {"ran": False, "reason": "not_due_or_no_new_image", "result": None}

    logger.info("ถึงรอบ classify ใหม่ (%s) -- เริ่ม trigger_crop_classification() (ใช้เวลานาน)", new_sar_image)
    try:
        result = sc.trigger_crop_classification(new_sar_image)
    except Exception as exc:
        logger.exception("trigger_crop_classification() ล้มเหลวไม่คาดคิด (นอกเหนือจาก try/except ภายในตัวมันเอง)")
        return {"ran": True, "reason": f"trigger_crop_classification_error: {exc}", "result": None}

    payload = {
        "generated_at": datetime.now().isoformat(),
        "sar_trigger": new_sar_image,
        **result,
    }

    year = new_sar_image.get("year", "unknown")
    as_of_str = new_sar_image.get("as_of_date", datetime.now().date().isoformat())
    dated_path = SAR_JOB_OUTPUT_DIR / f"sar_result_{year}_{as_of_str}.json"

    try:
        _write_json_atomic(dated_path, payload)
        _write_json_atomic(SAR_LATEST_RESULT_PATH, payload)
        logger.info(
            "เขียนผลลัพธ์สำเร็จ: %s (status=%s, zones=%s)",
            SAR_LATEST_RESULT_PATH, result.get("status"), list(result.get("zone_crop_area_ha", {}).keys()),
        )
    except Exception as exc:
        logger.exception("เขียนไฟล์ผลลัพธ์ล้มเหลว (%s) -- ผล classify สำเร็จแต่บันทึกไฟล์ไม่ได้", exc)
        return {"ran": True, "reason": f"write_result_error: {exc}", "result": payload}

    return {"ran": True, "reason": result.get("status", "unknown"), "result": payload}


def read_latest_sar_result(max_age_days: int = SAR_RESULT_STALE_AFTER_DAYS) -> Optional[dict]:
    """
    อ่านผล SAR classification ล่าสุดที่ background job เขียนไว้ — เร็ว ไม่ต้องรอ GEE เลย
    (สำหรับ data_pipeline.py หลักเรียกใช้แทน check_new_sar_image()/trigger_crop_classification()
    ตรงๆ ซึ่งตอนนี้ใช้เวลานานเกินกว่าจะรันในทุกรอบ pipeline หลักได้)

    คืน None ถ้ายังไม่เคยมีผลลัพธ์เลย (ไฟล์ไม่มี) หรืออ่านไฟล์ไม่สำเร็จ (ไม่ raise)
    ถ้ามีผลลัพธ์แต่เก่าเกิน max_age_days วัน จะยังคืนค่ากลับไป (ไม่ใช่ None) แต่แนบ
    "is_stale": True ไว้ให้ผู้เรียกตัดสินใจเอง (ไม่ใช่หน้าที่ของฟังก์ชันนี้ที่จะตัดสินว่า stale
    แล้วต้อง fail อะไร — data_pipeline.py step_status ควรรายงานเป็น "stale" ไม่ใช่ "failed")
    """
    if not SAR_LATEST_RESULT_PATH.exists():
        logger.info("ยังไม่มี sar_result_latest.json เลย -- background job ยังไม่เคยรันสำเร็จ")
        return None

    try:
        with open(SAR_LATEST_RESULT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning("อ่าน %s ไม่สำเร็จ (%s) -- ถือว่าไม่มีผลลัพธ์", SAR_LATEST_RESULT_PATH, exc)
        return None

    generated_at_str = payload.get("generated_at")
    is_stale = True
    age_days: Optional[int] = None
    if generated_at_str:
        try:
            generated_at = datetime.fromisoformat(generated_at_str)
            age_days = (datetime.now() - generated_at).days
            is_stale = age_days > max_age_days
        except Exception:
            logger.warning("parse generated_at (%s) ไม่สำเร็จ -- ถือว่า stale ไว้ก่อน", generated_at_str)

    payload["is_stale"] = is_stale
    payload["age_days"] = age_days

    if is_stale:
        logger.warning(
            "sar_result_latest.json เก่าเกิน %d วัน (age=%s) -- background job อาจไม่ได้รันมานาน "
            "หรือ GEE ล้มเหลวติดต่อกันหลายรอบ ควรเช็ค Task Scheduler ของ sar_background_job.py",
            max_age_days, age_days,
        )

    return payload


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    outcome = run_sar_background_job()
    print(json.dumps(outcome, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if outcome["reason"] != "check_new_sar_image_error" else 1)
