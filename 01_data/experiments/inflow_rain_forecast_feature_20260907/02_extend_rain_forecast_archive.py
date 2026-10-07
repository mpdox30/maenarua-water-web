"""
02_extend_rain_forecast_archive.py
===================================
2026-09-18 เพิ่ม -- ดึงเฉพาะ "ช่วงที่ขาดไป" ของ rain_forecast_archive_raw.csv (เดิมมีถึงแค่
2026-09-06) มาต่อท้ายไฟล์เดิม แทนที่จะดึงใหม่ทั้งหมดตั้งแต่ 2025-06-20 (ของเดิม 01_fetch_
rain_forecast_archive.py ใช้เวลา 10-20 นาที เพราะดึงซ้ำทุกวันที่มีอยู่แล้ว) สคริปต์นี้ดึงแค่
ไม่กี่สิบวันที่ขาด ใช้เวลาไม่ถึง 1 นาที

**ทำไมต้องรันจากเครื่องนี้ (ไม่ใช่ Claude รันให้)**: sandbox ที่ Claude รันโค้ดอยู่ไม่มี
internet access ออกไปยัง historical-forecast-api.open-meteo.com เลย (ตรวจสอบแล้ว
2026-09-18 -- เรียกแล้วได้ response ว่างทั้ง historical-forecast-api และ api.open-meteo.com
ปกติ) ต้องรันจากเครื่องที่มีเน็ตใช้งานได้ตามปกติ (เครื่อง Windows นี้ หรือ Colab)

วิธีรัน:
    "D:\\maenaruea-water-web\\.venv\\Scripts\\python.exe" "D:\\maenaruea-water-web\\01_data\\experiments\\inflow_rain_forecast_feature_20260907\\02_extend_rain_forecast_archive.py"

(ถ้า .venv ไม่มี requests ให้ลง pip install requests ก่อน -- pandas ควรมีอยู่แล้วเพราะ
data_pipeline.py ใช้)

Output: ต่อท้าย (append) เข้า rain_forecast_archive_raw.csv ไฟล์เดิมในโฟลเดอร์เดียวกัน
(ไม่ทับของเดิม, ไม่มี duplicate เพราะกรอง issue_date ที่มีอยู่แล้วออกก่อนดึง)
"""
import time
from pathlib import Path
from datetime import date, timedelta

import requests
import pandas as pd

TARGET_LAT = 19.05
TARGET_LON = 99.80
LEAD_DAYS = 7
MODEL = "best_match"
API_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

OUT_PATH = Path(__file__).parent / "rain_forecast_archive_raw.csv"
LOG_PATH = Path(__file__).parent / "fetch_errors_extend.log"


def fetch_one_issue_date(issue_dt: date) -> list[dict]:
    end_dt = issue_dt + timedelta(days=LEAD_DAYS)
    params = {
        "latitude": TARGET_LAT,
        "longitude": TARGET_LON,
        "start_date": issue_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "daily": "precipitation_sum",
        "timezone": "Asia/Bangkok",
        "models": MODEL,
    }
    resp = requests.get(API_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "daily" not in data or "precipitation_sum" not in data.get("daily", {}):
        raise ValueError(f"unexpected response shape for issue_date={issue_dt}: {str(data)[:500]}")
    dates = data["daily"]["time"]
    precip = data["daily"]["precipitation_sum"]
    return [
        {"issue_date": issue_dt.isoformat(), "lead_day": lead_day, "forecast_date": d_str,
         "precipitation_sum_mm": p, "model": MODEL}
        for lead_day, (d_str, p) in enumerate(zip(dates, precip))
    ]


def main():
    if not OUT_PATH.exists():
        raise SystemExit(f"ไม่พบไฟล์เดิม {OUT_PATH} -- รัน 01_fetch_rain_forecast_archive.py ก่อน (ครั้งแรกเท่านั้น)")

    existing = pd.read_csv(OUT_PATH)
    existing_issue_dates = set(pd.to_datetime(existing["issue_date"]).dt.date)
    last_existing = max(existing_issue_dates)
    print(f"ไฟล์เดิมมีถึง issue_date={last_existing} ({len(existing)} แถว)")

    end_issue_date = date.today() - timedelta(days=1)  # เมื่อวาน กันข้อมูลวันนี้ยังไม่ครบ
    start_issue_date = last_existing + timedelta(days=1)

    if start_issue_date > end_issue_date:
        print("ไม่มีวันที่ขาดเลย -- ไฟล์เป็นปัจจุบันอยู่แล้ว")
        return

    n_days = (end_issue_date - start_issue_date).days + 1
    print(f"ดึงเพิ่ม {n_days} วัน: {start_issue_date} ถึง {end_issue_date}")

    new_rows, errors = [], []
    d = start_issue_date
    i = 0
    while d <= end_issue_date:
        i += 1
        try:
            new_rows.extend(fetch_one_issue_date(d))
            print(f"  [{i}/{n_days}] {d} ok")
        except Exception as e:
            print(f"  [{i}/{n_days}] {d} FAILED: {e}")
            errors.append(f"{d}: {e}")
        d += timedelta(days=1)
        time.sleep(0.15)

    if not new_rows:
        raise SystemExit("ไม่ได้ข้อมูลใหม่เลยสักแถว -- เช็ค internet connection")

    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["issue_date", "lead_day"], keep="last")
    combined.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    print(f"\nต่อท้ายสำเร็จ: +{len(new_df)} แถวใหม่ -> รวมทั้งหมด {len(combined)} แถว")
    print(f"บันทึกที่: {OUT_PATH}")
    if errors:
        Path(LOG_PATH).write_text("\n".join(errors), encoding="utf-8")
        print(f"{len(errors)} วันที่ดึงไม่สำเร็จ -- ดู {LOG_PATH}")
    else:
        print("ไม่มี error")


if __name__ == "__main__":
    main()
