"""
forecast_accuracy_logger.py
==============================
เพิ่ม 2026-07-31 — รันประจำ (ทุก 15 นาที ผ่าน run_monitoring_data_builder.bat) เพื่อเก็บ log
เปรียบเทียบ "ค่าพยากรณ์ Q_in (h1-h7)" กับ "ค่าจริงที่คำนวณจาก water balance รายวัน" สำหรับใช้ปรับจูน
โมเดลในอนาคต (ตอบคำถามที่ผู้ใช้ถาม 2026-07-31: อยากมีระบบเก็บ log เปรียบเทียบ predicted vs actual)

=== การทำงาน (idempotent -- รันซ้ำได้ปลอดภัย ไม่ต้องกลัวรันบ่อยเกิน) ===

  ขั้นที่ 1 (บันทึกค่าพยากรณ์ใหม่): อ่าน 03_website/assets/data/latest.json -- ถ้า as_of_date ของมัน
  ยังไม่เคยถูกบันทึกใน log มาก่อน (เช็คจากคอลัมน์ recorded_as_of_date) ให้เพิ่มแถวใหม่ 7 แถว (h1-h7)
  ทันที (ยังไม่มี actual เพราะเพิ่งพยากรณ์)

  ขั้นที่ 2 (เติมค่าจริงย้อนหลัง): อ่าน 01_data/Reservoirs/inflow_auto/RES002_daily_computed.csv --
  สำหรับทุกแถวใน log ที่ยังไม่มี actual_m3_per_day (ว่าง) แต่ target_date ของมันมีค่า data_complete=True
  อยู่ใน CSV แล้ว ให้เติม actual + คำนวณ error ให้

  **ไม่แก้ไข/ไม่ยุ่งกับ**: latest.json, RES002_daily_computed.csv, โมเดล CatBoost, หรือ pipeline
  พยากรณ์ใดๆ เลย -- อ่านอย่างเดียว เขียนแค่ forecast_accuracy_log.csv ไฟล์เดียว

ดู backfill_forecast_log_from_git.py สำหรับการสร้างข้อมูลย้อนหลังครั้งแรกจากประวัติ git ของ
latest.json (รันครั้งเดียวตอนเริ่มไปแล้ว 2026-07-31) -- ไฟล์นี้ใช้ต่อยอดบันทึกแถวใหม่ทุกวันจากนี้ไป
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LATEST_JSON = REPO_ROOT / "03_website" / "assets" / "data" / "latest.json"
DAILY_COMPUTED_CSV = REPO_ROOT / "01_data" / "Reservoirs" / "inflow_auto" / "RES002_daily_computed.csv"
LOG_CSV = REPO_ROOT / "01_data" / "forecasting_results" / "Reservoir_inflow" / "forecast_accuracy_log.csv"

LOG_FIELDS = [
    "recorded_as_of_date", "horizon", "target_date", "predicted_m3_per_day",
    "model_name", "test_nse", "walkforward_cv_nse_mean", "low_confidence",
    "actual_m3_per_day", "abs_error_m3", "pct_error", "actual_data_complete",
    "source", "logged_at",
]


def _read_log() -> list[dict]:
    if not LOG_CSV.exists():
        return []
    with open(LOG_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_log(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (str(r.get("target_date", "")), int(r.get("horizon") or 0)))
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in LOG_FIELDS})


def _load_actuals() -> dict[str, dict]:
    actuals = {}
    if not DAILY_COMPUTED_CSV.exists():
        return actuals
    with open(DAILY_COMPUTED_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            actuals[row["date"]] = {
                "inflow_m3": float(row["inflow_m3"]) if row.get("inflow_m3") not in (None, "") else None,
                "data_complete": row.get("data_complete", "").strip().lower() == "true",
            }
    return actuals


def append_new_forecast(rows: list[dict]) -> tuple[list[dict], int]:
    if not LATEST_JSON.exists():
        print(f"[WARN] ไม่พบ {LATEST_JSON} -- ข้ามขั้นตอนบันทึกค่าพยากรณ์ใหม่รอบนี้")
        return rows, 0

    with open(LATEST_JSON, encoding="utf-8") as f:
        d = json.load(f)

    try:
        f_data = d["forecasts"]["inflow"]["forecast"]
        as_of_date = f_data["as_of_date"]
        horizons = f_data.get("horizons")
    except (KeyError, TypeError):
        print("[WARN] latest.json ไม่มีโครงสร้าง forecasts.inflow.forecast ที่คาดไว้ -- ข้ามรอบนี้")
        return rows, 0

    if not horizons:
        print(f"[INFO] as_of_date={as_of_date} ไม่มี horizons (อาจเป็น stale_data_blocked) -- ข้ามรอบนี้")
        return rows, 0

    already_logged = {r["recorded_as_of_date"] for r in rows}
    if as_of_date in already_logged:
        return rows, 0  # ปกติ -- ส่วนใหญ่ที่รันจะเจอกรณีนี้ (บันทึกไปแล้วตั้งแต่รอบก่อน)

    try:
        as_of_dt = dt.date.fromisoformat(as_of_date)
    except ValueError:
        print(f"[WARN] as_of_date={as_of_date!r} parse ไม่ได้ -- ข้ามรอบนี้")
        return rows, 0

    now_iso = dt.datetime.now().isoformat()
    n_added = 0
    for h in range(1, 8):
        hd = horizons.get(f"h{h}")
        if not hd:
            continue
        wf = hd.get("walkforward_cv_nse")
        rows.append({
            "recorded_as_of_date": as_of_date,
            "horizon": h,
            "target_date": (as_of_dt + dt.timedelta(days=h)).isoformat(),
            "predicted_m3_per_day": hd.get("prediction_m3_per_day"),
            "model_name": hd.get("model_name"),
            "test_nse": hd.get("test_nse"),
            "walkforward_cv_nse_mean": wf.get("mean") if isinstance(wf, dict) else None,
            "low_confidence": hd.get("low_confidence"),
            "actual_m3_per_day": "",
            "abs_error_m3": "",
            "pct_error": "",
            "actual_data_complete": False,
            "source": "daily_logger",
            "logged_at": now_iso,
        })
        n_added += 1

    if n_added:
        print(f"[OK] บันทึกค่าพยากรณ์ใหม่สำหรับ as_of_date={as_of_date} ({n_added} horizon)")
    return rows, n_added


def fill_missing_actuals(rows: list[dict]) -> int:
    actuals = _load_actuals()
    n_filled = 0
    for r in rows:
        if r.get("actual_m3_per_day") not in (None, "", "None"):
            continue  # เติมไปแล้ว
        a = actuals.get(r["target_date"])
        if not a or not a["data_complete"] or a["inflow_m3"] is None:
            continue
        pred = r.get("predicted_m3_per_day")
        try:
            pred_f = float(pred) if pred not in (None, "") else None
        except ValueError:
            pred_f = None
        r["actual_m3_per_day"] = a["inflow_m3"]
        r["actual_data_complete"] = True
        if pred_f is not None:
            abs_err = abs(pred_f - a["inflow_m3"])
            r["abs_error_m3"] = abs_err
            r["pct_error"] = (abs_err / a["inflow_m3"] * 100.0) if a["inflow_m3"] else ""
        n_filled += 1
    if n_filled:
        print(f"[OK] เติมค่า actual ย้อนหลังให้ {n_filled} แถว")
    return n_filled


def main() -> int:
    rows = _read_log()
    rows, n_added = append_new_forecast(rows)
    n_filled = fill_missing_actuals(rows)

    if n_added or n_filled:
        _write_log(rows)
        print(f"[INFO] เขียน {LOG_CSV} ({len(rows)} แถวทั้งหมด)")
    else:
        print("[INFO] ไม่มีอะไรใหม่ต้องบันทึก/เติมรอบนี้")
    return 0


if __name__ == "__main__":
    sys.exit(main())
