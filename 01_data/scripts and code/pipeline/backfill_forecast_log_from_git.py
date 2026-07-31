"""
backfill_forecast_log_from_git.py
====================================
เพิ่ม 2026-07-31 — สคริปต์ one-off (รันได้ซ้ำได้อย่างปลอดภัย, idempotent) สำหรับสร้างข้อมูลย้อนหลังของ
forecast_accuracy_log.csv จากประวัติ git ของ 03_website/assets/data/latest.json

**เหตุผลที่ทำได้**: latest.json ถูก Colab commit/push ทับใหม่ทุกวัน (auto-update ผ่าน pipeline) --
เท่ากับว่า git history ของไฟล์นี้ "ดักจับ" ค่าพยากรณ์ ณ วันที่ต่างๆ ไว้แล้วโดยไม่ได้ตั้งใจ ทำให้สร้าง
ข้อมูลย้อนหลังของ log เปรียบเทียบ predicted vs actual ได้ทันทีโดยไม่ต้องรอสะสมข้อมูลใหม่ทีละวัน

วิธีใช้:
    python backfill_forecast_log_from_git.py                 # เขียน/อัปเดต forecast_accuracy_log.csv
    python backfill_forecast_log_from_git.py --dry-run        # แสดงตัวอย่างไม่เขียนไฟล์จริง

ดู forecast_accuracy_logger.py สำหรับสคริปต์ที่รันประจำวัน (เพิ่มแถวใหม่ทุกวันแทนการย้อนหลังจาก git)
-- ไฟล์นี้ควรรันแค่ครั้งเดียวตอนเริ่ม (หรือรันซ้ำได้ปลอดภัยถ้าอยากรีเซ็ต เพราะ merge แบบ idempotent
กับ log ที่มีอยู่ ไม่ทับข้อมูล actual ที่ forecast_accuracy_logger.py เติมไปแล้ว)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LATEST_JSON_REL = "03_website/assets/data/latest.json"
DAILY_COMPUTED_CSV = REPO_ROOT / "01_data" / "Reservoirs" / "inflow_auto" / "RES002_daily_computed.csv"
LOG_CSV = REPO_ROOT / "01_data" / "forecasting_results" / "Reservoir_inflow" / "forecast_accuracy_log.csv"

LOG_FIELDS = [
    "recorded_as_of_date", "horizon", "target_date", "predicted_m3_per_day",
    "model_name", "test_nse", "walkforward_cv_nse_mean", "low_confidence",
    "actual_m3_per_day", "abs_error_m3", "pct_error", "actual_data_complete",
    "source", "logged_at",
]


def _load_actuals() -> dict[str, dict]:
    """date -> {"inflow_m3": float, "data_complete": bool} จาก RES002_daily_computed.csv"""
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


def _git_commits_touching(path: str) -> list[str]:
    out = subprocess.run(
        ["git", "log", "--format=%H", "--", path], cwd=REPO_ROOT,
        capture_output=True, text=True, check=True,
    )
    return [h for h in out.stdout.splitlines() if h.strip()]


def _git_show_json(commit: str, path: str) -> dict | None:
    out = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=REPO_ROOT,
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def collect_historical_forecasts() -> dict[str, dict]:
    """
    เดินประวัติ git ของ latest.json (ใหม่ -> เก่า) เก็บค่าพยากรณ์ล่าสุดของแต่ละ as_of_date ที่ไม่ซ้ำ
    (ถ้ามีหลาย commit ในวันเดียวกัน เอา commit ล่าสุด/ใหม่สุดของ as_of_date นั้น เพราะ git log เรียง
    ใหม่ -> เก่าอยู่แล้ว ตัวแรกที่เจอ as_of_date นั้นคือตัวล่าสุด)
    คืนค่า: {as_of_date: forecast_dict}
    """
    commits = _git_commits_touching(LATEST_JSON_REL)
    seen: dict[str, dict] = {}
    for c in commits:
        d = _git_show_json(c, LATEST_JSON_REL)
        if not d:
            continue
        try:
            f = d["forecasts"]["inflow"]["forecast"]
            as_of = f["as_of_date"]
            horizons = f.get("horizons")
        except (KeyError, TypeError):
            continue
        if not horizons or as_of in seen:
            continue
        seen[as_of] = f
    return seen


def build_log_rows(forecasts_by_date: dict[str, dict], actuals: dict[str, dict]) -> list[dict]:
    rows = []
    now_iso = dt.datetime.now().isoformat()
    for as_of_date, f in forecasts_by_date.items():
        try:
            as_of_dt = dt.date.fromisoformat(as_of_date)
        except ValueError:
            continue
        for h in range(1, 8):
            key = f"h{h}"
            hd = f["horizons"].get(key)
            if not hd:
                continue
            target_date = (as_of_dt + dt.timedelta(days=h)).isoformat()
            actual = actuals.get(target_date)
            actual_val = actual["inflow_m3"] if actual and actual["data_complete"] else None
            pred = hd.get("prediction_m3_per_day")
            abs_err = abs(pred - actual_val) if (pred is not None and actual_val is not None) else None
            pct_err = (abs_err / actual_val * 100.0) if (abs_err is not None and actual_val not in (None, 0)) else None
            wf = hd.get("walkforward_cv_nse")
            rows.append({
                "recorded_as_of_date": as_of_date,
                "horizon": h,
                "target_date": target_date,
                "predicted_m3_per_day": pred,
                "model_name": hd.get("model_name"),
                "test_nse": hd.get("test_nse"),
                "walkforward_cv_nse_mean": wf.get("mean") if isinstance(wf, dict) else None,
                "low_confidence": hd.get("low_confidence"),
                "actual_m3_per_day": actual_val,
                "abs_error_m3": abs_err,
                "pct_error": pct_err,
                "actual_data_complete": bool(actual and actual["data_complete"]),
                "source": "git_backfill",
                "logged_at": now_iso,
            })
    rows.sort(key=lambda r: (r["target_date"], r["horizon"]))
    return rows


def merge_with_existing(new_rows: list[dict]) -> list[dict]:
    """
    ถ้ามี forecast_accuracy_log.csv อยู่แล้ว (เช่นจาก forecast_accuracy_logger.py ที่รันประจำวันไปแล้ว
    บางส่วน) -- ไม่ทับแถวเดิมที่มี actual กรอกไว้แล้ว (source อื่นที่ไม่ใช่ git_backfill ถือว่า "ของจริง"
    มากกว่า เพราะรันตอนข้อมูล actual สดกว่า) merge key = (recorded_as_of_date, horizon)
    """
    if not LOG_CSV.exists():
        return new_rows
    existing = {}
    with open(LOG_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["recorded_as_of_date"], row["horizon"])
            existing[key] = row

    merged = dict(existing)
    for row in new_rows:
        key = (row["recorded_as_of_date"], str(row["horizon"]))
        if key not in merged:
            merged[key] = row
        else:
            # ถ้าของเดิมยังไม่มี actual แต่ backfill มี actual ใหม่กว่า (เช่น ข้อมูล daily_computed.csv
            # อัปเดตเพิ่มตั้งแต่รอบก่อน) ให้เติม actual ให้ แต่ไม่ทับ predicted/logged_at เดิม
            old = merged[key]
            if (old.get("actual_m3_per_day") in (None, "", "None")) and row["actual_m3_per_day"] is not None:
                old["actual_m3_per_day"] = row["actual_m3_per_day"]
                old["abs_error_m3"] = row["abs_error_m3"]
                old["pct_error"] = row["pct_error"]
                old["actual_data_complete"] = row["actual_data_complete"]
    result = list(merged.values())
    result.sort(key=lambda r: (str(r["target_date"]), int(r["horizon"])))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    print("[INFO] กำลังเดินประวัติ git ของ", LATEST_JSON_REL, "...")
    forecasts_by_date = collect_historical_forecasts()
    print(f"[INFO] พบค่าพยากรณ์ย้อนหลัง {len(forecasts_by_date)} as_of_date ที่ไม่ซ้ำกัน")

    actuals = _load_actuals()
    print(f"[INFO] โหลดค่า actual จาก RES002_daily_computed.csv ได้ {len(actuals)} วัน")

    new_rows = build_log_rows(forecasts_by_date, actuals)
    merged_rows = merge_with_existing(new_rows)

    n_with_actual = sum(1 for r in merged_rows if r.get("actual_m3_per_day") not in (None, "", "None"))
    print(f"[INFO] รวม {len(merged_rows)} แถว (มี actual แล้ว {n_with_actual} แถว)")

    if args.dry_run:
        print("[DRY-RUN] ไม่ได้เขียนไฟล์จริง ตัวอย่าง 5 แถวแรก:")
        for r in merged_rows[:5]:
            print(" ", r)
        return 0

    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        for r in merged_rows:
            writer.writerow({k: r.get(k, "") for k in LOG_FIELDS})
    print(f"[OK] เขียน {LOG_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
