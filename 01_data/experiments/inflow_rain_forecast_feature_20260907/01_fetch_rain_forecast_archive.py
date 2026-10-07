"""
ดึง archive พยากรณ์ฝนย้อนหลัง (forward-looking, ตามที่เคยพยากรณ์จริง ณ วันนั้นๆ) จาก
Open-Meteo Historical Forecast API สำหรับพิกัดอ่างเก็บน้ำแม่นาเรือ (lat=19.05, lon=99.80
-- พิกัดเดียวกับที่ chirps_feature.py ใช้ TARGET_LAT/TARGET_LON)

**ทำไมต้องรันเอง**: sandbox ที่ Claude รันอยู่ตอนนี้ไม่มี internet access ออกไปยัง external
API ใดๆ เลย (ตรวจสอบแล้ว: DNS/proxy บล็อกทุก domain ที่ไม่อยู่ใน allowlist ภายใน) จึงต้องรัน
สคริปต์นี้จากเครื่องที่มี internet ปกติ (เครื่อง Windows ของคุณ หรือ Colab ก็ได้ -- ไม่ต้องมี
API key เพราะ Open-Meteo free tier ไม่ต้อง auth)

**ทำไมเลือก Open-Meteo แทน DeepMind WeatherNext**: WeatherNext เข้าถึงผ่าน Google Cloud
BigQuery/Earth Engine ซึ่งซับซ้อนกว่ามาก (ต้องตั้งค่า GCP billing/credential เพิ่มเติม) ส่วน
Open-Meteo Historical Forecast API เป็น REST ธรรมดา ไม่ต้อง auth, มี archive ย้อนหลังตั้งแต่
ปี 2022, และให้ค่าพยากรณ์ "ตามที่โมเดลพยากรณ์จริง ณ ตอนนั้น" (ไม่ใช่ reanalysis ย้อนหลัง)
ซึ่งตรงกับสิ่งที่เราต้องการสำหรับ feature "รู้ล่วงหน้าว่าฝนจะตกไหม" แบบไม่มี look-ahead bias

**หลักการ**: สำหรับแต่ละวัน issue_date ในช่วง training period เรียก API โดยกำหนด
start_date=issue_date, end_date=issue_date+7 -- ค่าที่ได้กลับมาคือพยากรณ์สำหรับ 8 วันนั้น
"ตามข้อมูลโมเดลพยากรณ์ที่มีล่าสุด ณ issue_date" ไม่ใช่ค่าจริงที่เกิดขึ้น (ป้องกัน look-ahead)

วิธีรัน:
    pip install requests pandas  (ถ้ายังไม่มี)
    python 01_fetch_rain_forecast_archive.py

Output: rain_forecast_archive_raw.csv ในโฟลเดอร์เดียวกับสคริปต์นี้
    columns: issue_date, lead_day (0-7), forecast_date, precipitation_sum_mm, model

หมายเหตุ: ใช้เวลานานพอสมควร (~400+ วัน x 1 call ต่อวัน = ~400 API calls, มี sleep กันโดน
rate-limit) คาดว่าใช้เวลา 10-20 นาที รันครั้งเดียวพอ (cache เป็น CSV แล้ว)
"""
import time
import json
from pathlib import Path
from datetime import date, timedelta

import requests
import pandas as pd

TARGET_LAT = 19.05
TARGET_LON = 99.80

# ครอบคลุมช่วง training data ทั้งหมด (2025-06-27 ถึงปัจจุบัน) เผื่อไว้เริ่มก่อนหน้านั้นเล็กน้อย
START_ISSUE_DATE = date(2025, 6, 20)
END_ISSUE_DATE = date.today() - timedelta(days=1)  # เมื่อวาน (กัน edge case ของวันนี้ที่ข้อมูลยังไม่ครบ)

LEAD_DAYS = 7  # ต้องการพยากรณ์ล่วงหน้าสูงสุด 7 วัน (ตรงกับ horizon 1-7 ของโมเดล inflow)
MODEL = "best_match"  # Open-Meteo auto-blend โมเดลที่ดีที่สุดสำหรับพิกัดนี้ (ง่ายสุด ไม่ต้องเดา
                       # ชื่อโมเดลเฉพาะ -- ถ้าพบว่าผลลัพธ์ดูแปลก ค่อยลอง "gfs_seamless" หรือ
                       # "ecmwf_ifs04" แทนทีหลัง)

API_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

OUT_PATH = Path(__file__).parent / "rain_forecast_archive_raw.csv"
LOG_PATH = Path(__file__).parent / "fetch_errors.log"


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
        raise ValueError(f"unexpected response shape for issue_date={issue_dt}: {json.dumps(data)[:500]}")

    dates = data["daily"]["time"]
    precip = data["daily"]["precipitation_sum"]
    rows = []
    for lead_day, (d_str, p) in enumerate(zip(dates, precip)):
        rows.append({
            "issue_date": issue_dt.isoformat(),
            "lead_day": lead_day,
            "forecast_date": d_str,
            "precipitation_sum_mm": p,
            "model": MODEL,
        })
    return rows


def main():
    all_rows = []
    errors = []
    n_days = (END_ISSUE_DATE - START_ISSUE_DATE).days + 1
    print(f"Fetching {n_days} issue dates from {START_ISSUE_DATE} to {END_ISSUE_DATE} "
          f"(lead 0-{LEAD_DAYS} days each)...")

    d = START_ISSUE_DATE
    i = 0
    while d <= END_ISSUE_DATE:
        i += 1
        try:
            rows = fetch_one_issue_date(d)
            all_rows.extend(rows)
            if i % 20 == 0:
                print(f"  [{i}/{n_days}] {d} ok ({len(all_rows)} rows so far)")
        except Exception as e:
            print(f"  [{i}/{n_days}] {d} FAILED: {e}")
            errors.append(f"{d}: {e}")
        d += timedelta(days=1)
        time.sleep(0.15)  # เผื่อ rate limit (free tier ~600 calls/min ก็เกินพอแล้ว แต่กันไว้)

    if not all_rows:
        raise SystemExit("ไม่ได้ข้อมูลเลยสักแถว -- ตรวจสอบ error log / internet connection")

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\nSaved {len(df)} rows -> {OUT_PATH}")

    if errors:
        LOG_PATH.write_text("\n".join(errors), encoding="utf-8")
        print(f"{len(errors)} issue dates failed -- see {LOG_PATH}")
    else:
        print("No errors.")

    print("\nSample (first 10 rows):")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
