"""
era5t_worker.py
==================
Worker script สำหรับดึงข้อมูล ERA5T (ERA5 preliminary/near-real-time, dataset
'reanalysis-era5-single-levels' — ไม่ใช่ ERA5-Land ที่ archive/Phase3 step1 era5 download
et0.ipynb ใช้ตอน train) จาก Copernicus Climate Data Store (CDS) แล้ว decode ด้วย cfgrib

ทำไมต้องแยกเป็นสคริปต์ต่างหาก (ไม่ import cdsapi/cfgrib ตรงๆ ใน data_pipeline.py):
environment ที่ยืนยันแล้วว่า import cdsapi + cfgrib + eccodes ได้สำเร็จจริง (ผ่าน conda-forge
stack ที่มากับ ArcGIS Pro: "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\era5-grib\\python.exe"
— selfcheck ยืนยันแล้วโดยผู้ใช้) เป็นคนละ Python interpreter กับ .venv หลักของโปรเจกต์ที่
data_pipeline.py รันอยู่ ดังนั้น data_pipeline.py::_fetch_era5t_via_subprocess() จึงเรียกสคริปต์นี้
ผ่าน subprocess ไปยัง python.exe ของ conda env นั้นโดยเฉพาะ แทนที่จะ import ตรงๆ

Contract กับผู้เรียก (subprocess):
  - รับ argument ผ่าน command line เท่านั้น (ดู --help)
  - เขียนผลลัพธ์เป็น JSON ไปที่ path ที่ระบุด้วย --out-json เท่านั้น (ไม่ print JSON ไปที่ stdout
    เพื่อไม่ให้ปนกับข้อความ log บรรทัดอื่นที่ผู้เรียกอาจอ่านสับสน)
  - "ไม่ raise ออกไปนอก main()" เหมือน pattern ของ mei_feature.py/chirps_feature.py: ถ้าเกิด
    error ระหว่างทาง (network, parse, ฯลฯ) จะเขียน {"fetch_error": "..."} ลง --out-json แทน
    แล้ว exit code != 0 — ผู้เรียกเช็คได้ทั้งจาก exit code และเนื้อหาไฟล์ (เผื่อกรณี exit code
    หาย/ผิดเพี้ยนระหว่างทาง ให้เช็คไฟล์เป็นหลัก)

โหมดทดสอบ (--grib-in <path>): ข้ามการยิง CDS จริง ใช้ไฟล์ .grib ที่มีอยู่แล้วแทน (เช่นไฟล์จาก
test_era5_live.py ใน era5_test_output/) สำหรับตรวจสอบ logic การ parse/เขียน JSON โดยไม่ต้องรอ
CDS queue ทุกครั้งที่ทดสอบ

โหมดรายสัปดาห์ (--as-of-date <YYYY-MM-DD>): คำนวณ ET0_mm_week/T_mean/RH_pct/VPD_kPa/u2_ms/Rn_MJ
ของ ISO week ที่ as-of-date อยู่ ตามสูตร Penman-Monteith เดียวกับที่ archive/Phase3 step1 era5
download et0.ipynb ใช้ตอน train (คัดลอกฟังก์ชัน kelvin_to_celsius/saturation_vp/slope_vp/
psychrometric_const/wind_2m + ค่าคงที่ ELEV_M/ALPHA/MJ_DAY มาตรงตัวจาก cell สุดท้ายที่ export
ET0_weekly_phayao_2018_2024.csv จริง — ไม่ใช่ cell ทดลองก่อนหน้าที่ใช้ ELEV_M ต่างกัน) ดึงเฉพาะวันที่
"เกิดขึ้นแล้วจริง" ของสัปดาห์นั้น (Monday ถึง as_of_date - 1 วัน เป็นอย่างมาก — ข้อมูลของวันนี้เองยัง
ไม่ควรถือว่าพร้อมใช้) ถ้า CDS ปฏิเสธบางวันล่าสุด (ยังไม่ผ่าน ERA5T latency) จะตัดวันล่าสุดออกแล้วลองใหม่
ทีละวันจนกว่าจะสำเร็จหรือหมดวันให้ลอง (ดู _fetch_week_with_retry())
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# 7 ตัวแปรเดียวกับที่ใช้คำนวณ ETo เดิม (ดู feature_schema.md, archive/Phase3 step1 era5 download
# et0.ipynb, และ test_era5_live.py) — dataset นี้คือ 'reanalysis-era5-single-levels' (latency สั้น
# กว่า ERA5-Land มาก ยืนยันแล้วด้วย test_era5_live.py: ดึงข้อมูลของเมื่อวาน (ตอนทดสอบคือ 2026-06-29
# เทียบกับวันที่ทดสอบ 2026-07-05 ห่างกัน 6 วัน) ได้จริง)
DATASET = "reanalysis-era5-single-levels"
CDS_VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_dewpoint_temperature",
    "2m_temperature",
    "total_precipitation",
    "surface_net_solar_radiation",
    "surface_net_thermal_radiation",
]
DEFAULT_AREA = [19.3, 99.6, 19, 99.95]  # Mae Na Rua, Phayao (N, W, S, E) — เดียวกับที่ทดสอบไว้

# แก้ไข (2026-07-05, พบจากการตรวจสอบผลทดสอบจริง): เดิม DEFAULT_TIME_UTC ตัวเดียว ("07:00") ถูกใช้ทั้ง
# โหมด single-day และโหมดรายสัปดาห์ — แต่ "07:00" เป็นแค่เวลาที่เลือกเอง (arbitrary) ตอนทำ
# sanity/connectivity test ครั้งแรก (test_era5_live.py) ไม่ใช่เวลาที่ใช้ตอน train จริง เปิดดู
# archive/Phase3 step1 era5 download et0.ipynb แล้วยืนยันว่า cell ที่ export ET0_weekly_phayao_
# 2018_2024.csv จริง (cell สุดท้าย) ใช้ 'time': '12:00' เท่านั้น (valid_time ที่ได้คือ
# YYYY-MM-DDT12:00:00 ทุกแถว) — ถ้าโหมดรายสัปดาห์ยังคง fetch ด้วย 07:00 อยู่ ETo ที่คำนวณได้จะไม่ตรง
# กับ methodology ตอน train (ERA5 accumulated fields อย่าง ssr/str ขึ้นกับเวลาที่ขอด้วย) จึงแยก
# ค่า default ของแต่ละโหมดออกจากกันชัดเจน: single-day (sanity test เท่านั้น) ยังคง 07:00 ไว้เหมือนเดิม
# (ไม่กระทบผลลัพธ์ที่เคย verify ไว้กับ test_era5_live.py) ส่วนโหมดรายสัปดาห์ (ใช้จริงใน
# _fetch_climate_features_step()) เปลี่ยนเป็น 12:00 ให้ตรงกับ training methodology
DEFAULT_SINGLE_DAY_TIME_UTC = "07:00"
DEFAULT_WEEKLY_TIME_UTC = "12:00"
DEFAULT_TIME_UTC = DEFAULT_SINGLE_DAY_TIME_UTC  # เก็บชื่อเดิมไว้เพื่อ backward-compat (ใช้เป็นค่า default ของ argparse เฉยๆ ไม่ใช้ตรงๆ อีกต่อไป — ดู parse_args()/main())

# short name ตาม ECMWF grib table ที่คาดว่าจะเจอหลัง parse (ตรงกับ 7 variable ที่ request)
EXPECTED_SHORT_NAMES = {"u10", "v10", "d2m", "t2m", "tp", "ssr", "str"}

# ---------------------------------------------------------------------------
# ค่าคงที่ + สูตร Penman-Monteith (FAO-56) สำหรับคำนวณ ET0_mm_week — คัดลอกตรงตัวจาก
# archive/Phase3 step1 era5 download et0.ipynb cell สุดท้าย (cell ที่ export
# ET0_weekly_phayao_2018_2024.csv จริง) ไม่ใช่ cell ทดลองก่อนหน้า (ซึ่งใช้ ELEV_M=400.0 ต่างกัน)
# ห้ามเปลี่ยนสูตร/ค่าคงที่นอกจาก sync กับ archive notebook เท่านั้น (เดียวกับหลักการที่ยึดใน
# mei_feature.py/chirps_feature.py)
# ---------------------------------------------------------------------------
ELEV_M = 300.0   # ความสูงเฉลี่ยพื้นที่ศึกษา (เมตร) — ตรงกับ cell สุดท้ายของ archive notebook
ALPHA = 0.23     # albedo (FAO-56 reference grass)
MJ_DAY = 1e-6    # J -> MJ


def kelvin_to_celsius(k: float) -> float:
    return k - 273.15


def saturation_vp(t_c: float) -> float:
    """es (kPa) จาก temperature (°C) — สูตร FAO-56"""
    import math
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def slope_vp(t_c: float) -> float:
    """Δ (kPa/°C)"""
    return 4098 * saturation_vp(t_c) / (t_c + 237.3) ** 2


def psychrometric_const(elev_m: float) -> float:
    """γ (kPa/°C) จาก elevation"""
    p = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26  # kPa
    return 0.000665 * p


def wind_2m(u10: float, v10: float) -> float:
    """แปลง wind 10m -> 2m (FAO-56 eq. 47)"""
    import math
    ws10 = math.sqrt(u10 ** 2 + v10 ** 2)
    return ws10 * (4.87 / math.log(67.8 * 10 - 5.42))


def _eto_for_day(day_vars: dict, elev_m: float = ELEV_M) -> dict:
    """
    คำนวณ ETo_mm_day + สถิติรายวันอื่นๆ ตามสูตรเดียวกับ compute_eto_daily() ใน archive cell 6
    (ไม่มีเทอม soil heat flux G เพราะ archive ตั้งเป็น 0 ทุกกรณีอยู่แล้ว) จาก spatial-mean ของ
    t2m/d2m/u10/v10/ssr/str ของวันนั้น (หน่วยดิบตรงจาก ERA5: K, K, m/s, m/s, J/m^2, J/m^2)
    """
    t_c = kelvin_to_celsius(day_vars["t2m"])
    td_c = kelvin_to_celsius(day_vars["d2m"])
    es = saturation_vp(t_c)
    ea = saturation_vp(td_c)
    delta = slope_vp(t_c)
    gamma = psychrometric_const(elev_m)
    rs = day_vars["ssr"] * MJ_DAY
    rnl = -day_vars["str"] * MJ_DAY
    rn = (1 - ALPHA) * rs - rnl
    u2 = wind_2m(day_vars["u10"], day_vars["v10"])

    eto = (0.408 * delta * rn + gamma * (900 / (t_c + 273)) * u2 * (es - ea)) / (
        delta + gamma * (1 + 0.34 * u2)
    )

    return {
        "ETo_mm_day": eto,
        "T_c": t_c,
        "RH_pct": min(100.0, (ea / es) * 100) if es else None,
        "VPD_kPa": max(0.0, es - ea),
        "u2_ms": u2,
        "Rn_MJ": rn,
    }


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ดึง + decode ERA5T single-levels (worker เรียกโดย data_pipeline.py ผ่าน subprocess)"
    )
    p.add_argument("--date", type=str, default=None,
                    help="[โหมด 1 วัน] วันที่ต้องการ (YYYY-MM-DD, UTC) — จำเป็นถ้าไม่ได้ใช้ --grib-in/--as-of-date")
    p.add_argument("--as-of-date", type=str, default=None,
                    help="[โหมดรายสัปดาห์] คำนวณ ET0_mm_week ของ ISO week ที่วันนี้อยู่ (YYYY-MM-DD)")
    p.add_argument("--time-utc", type=str, default=None,
                    help=(
                        "เวลา UTC ที่ต้องการต่อวัน (ถ้าไม่ระบุ: ใช้ "
                        f"{DEFAULT_SINGLE_DAY_TIME_UTC} สำหรับโหมด 1 วัน (--date), "
                        f"{DEFAULT_WEEKLY_TIME_UTC} สำหรับโหมดรายสัปดาห์ (--as-of-date) — "
                        f"{DEFAULT_WEEKLY_TIME_UTC} ตรงกับ archive training methodology, "
                        f"{DEFAULT_SINGLE_DAY_TIME_UTC} เป็นแค่ค่าที่ใช้ตอน sanity/connectivity "
                        "test ครั้งแรกเท่านั้น)"
                    ))
    p.add_argument("--area", type=float, nargs=4, default=DEFAULT_AREA, metavar=("N", "W", "S", "E"))
    p.add_argument("--out-json", type=str, required=True, help="path ที่จะเขียนผลลัพธ์ JSON")
    p.add_argument("--grib-in", type=str, default=None,
                    help="[โหมดทดสอบ 1 วัน] ใช้ .grib ไฟล์นี้แทนการยิง CDS จริง (ข้าม cdsapi ทั้งหมด)")
    p.add_argument("--grib-out", type=str, default=None,
                    help="path ที่จะเก็บ .grib ดิบไว้ (ถ้าไม่ระบุ จะเก็บไว้ข้าง --out-json)")
    p.add_argument("--grib-in-week", type=str, nargs="+", default=None,
                    help="[โหมดทดสอบรายสัปดาห์] ใช้ .grib ไฟล์เหล่านี้แทนการยิง CDS จริง "
                         "(แต่ละไฟล์ = การดึงของกลุ่มวันหนึ่งๆ ในสัปดาห์ — สำหรับทดสอบ logic "
                         "aggregate โดยไม่ต้องรอ CDS)")
    return p.parse_args(argv)


def _fetch_grib_from_cds(as_of: date, time_utc: str, area, grib_out: Path) -> float:
    """เรียก cdsapi.Client().retrieve().download() จริง — คืนค่าเวลาที่ใช้ทั้งหมด (วินาที, รวม
    queue delay ของ CDS ด้วย ไม่ใช่แค่เวลาดาวน์โหลดไฟล์)"""
    import cdsapi

    request = {
        "product_type": ["reanalysis"],
        "variable": CDS_VARIABLES,
        "year": [f"{as_of.year:04d}"],
        "month": [f"{as_of.month:02d}"],
        "day": [f"{as_of.day:02d}"],
        "time": [time_utc],
        "data_format": "grib",
        "download_format": "unarchived",
        "area": list(area),
    }
    client = cdsapi.Client()
    t0 = time.monotonic()
    client.retrieve(DATASET, request).download(str(grib_out))
    return time.monotonic() - t0


def _fetch_grib_from_cds_days(year: int, month: int, day_nums: list, time_utc: str, area, grib_out: Path) -> float:
    """
    เหมือน _fetch_grib_from_cds() แต่ขอได้หลายวันในเดือนเดียวกันพร้อมกันในคำขอ CDS เดียว (ประหยัด
    queue delay — ไม่ต้องรอคิวทีละวัน) ใช้เฉพาะโหมดรายสัปดาห์ (--as-of-date) ซึ่งต้องแยกคำขอตาม
    (year, month) เพราะ ISO week อาจคาบเกี่ยว 2 เดือนได้ (ดู _iso_week_days() ด้านล่าง)
    """
    import cdsapi

    request = {
        "product_type": ["reanalysis"],
        "variable": CDS_VARIABLES,
        "year": [f"{year:04d}"],
        "month": [f"{month:02d}"],
        "day": [f"{d:02d}" for d in day_nums],
        "time": [time_utc],
        "data_format": "grib",
        "download_format": "unarchived",
        "area": list(area),
    }
    client = cdsapi.Client()
    t0 = time.monotonic()
    client.retrieve(DATASET, request).download(str(grib_out))
    return time.monotonic() - t0


def _iso_week_days(as_of: date) -> list:
    """
    คืนค่า list ของ date object ตั้งแต่วันจันทร์ของ ISO week ที่ as_of อยู่ ไปจนถึง as_of - 1 วัน
    (ไม่รวมวันนี้เอง เพราะข้อมูลของวันนี้ยังไม่ควรถือว่า ERA5T พร้อมใช้แน่นอน) ถ้า as_of เป็นวันจันทร์
    ของสัปดาห์นั้นเองจะได้ list ว่าง (ยังไม่มีวันไหนของสัปดาห์นี้ที่ "ผ่านไปแล้ว" เลย)

    ใช้ pattern การ reconstruct วันจันทร์แบบเดียวกับ mei_feature.py/chirps_feature.py
    (ISO calendar ผ่าน date.isocalendar() + timedelta ธรรมดา ไม่ต้องพึ่ง pandas เพราะทำงานกับ
    date object ตรงๆ ได้อยู่แล้ว)
    """
    iso_year, iso_week, iso_weekday = as_of.isocalendar()
    monday = as_of - timedelta(days=iso_weekday - 1)
    candidate_days = [monday + timedelta(days=i) for i in range(7)]
    return [d for d in candidate_days if d < as_of]


def _fetch_week_with_retry(days: list, time_utc: str, area, grib_dir: Path, warnings: list) -> tuple:
    """
    ดึงข้อมูลของ days (ต้องอยู่ในเดือน/ปีเดียวกันทั้งหมด — เรียกทีละกลุ่มจาก main() ที่ group by
    (year, month) มาให้แล้ว) ด้วยคำขอ CDS เดียว ถ้าล้มเหลว (เช่น 1-2 วันล่าสุดยังไม่ผ่าน ERA5T
    latency จริง) จะตัดวันที่ล่าสุดออกทีละวันแล้วลองใหม่ จนกว่าจะสำเร็จหรือไม่เหลือวันให้ลองเลย

    คืนค่า (days_fetched, grib_path) — grib_path เป็น None ถ้าไม่สำเร็จเลยแม้แต่วันเดียว
    """
    remaining = sorted(days)
    while remaining:
        year, month = remaining[0].year, remaining[0].month
        day_nums = [d.day for d in remaining]
        grib_path = grib_dir / f"era5t_week_{year}{month:02d}_{min(day_nums):02d}-{max(day_nums):02d}.grib"
        try:
            _fetch_grib_from_cds_days(year, month, day_nums, time_utc, area, grib_path)
            return remaining, grib_path
        except Exception as exc:
            warnings.append(
                f"ดึงข้อมูลวัน {remaining} ไม่สำเร็จ ({type(exc).__name__}: {exc}) — "
                f"ตัดวันล่าสุด ({remaining[-1]}) ออกแล้วลองใหม่ (อาจเป็นเพราะ ERA5T ยังไม่ปล่อยข้อมูล "
                f"ของวันนั้นจริงๆ)"
            )
            remaining = remaining[:-1]
    return [], None


def _as_flat_list(values) -> list:
    try:
        return values.reshape(-1).tolist()
    except AttributeError:
        return [values]


def _decode_grib(grib_path: Path) -> dict:
    """
    เปิด .grib ด้วย cfgrib.open_datasets() (ไม่ใช่ xr.open_dataset(engine='cfgrib') เดี่ยวๆ) —
    ยืนยันจากการทดสอบจริงกับไฟล์จาก test_era5_live.py แล้วว่า grib ที่มีตัวแปรคนละ typeOfLevel ปนกัน
    (2m temperature/dewpoint + 10m wind อยู่กลุ่ม heightAboveGround, surface net radiation/
    precipitation อยู่กลุ่ม surface) ถูก cfgrib แยกเป็นหลาย "hypercube dataset" อัตโนมัติ — ต้องวน
    รวมทุก dataset เข้าด้วยกันจึงจะได้ครบทั้ง 7 ตัวแปร
    """
    import cfgrib

    datasets = cfgrib.open_datasets(str(grib_path))
    variables: dict = {}
    valid_time = None
    latitude = None
    longitude = None

    for ds in datasets:
        for v in ds.data_vars:
            flat = _as_flat_list(ds[v].values)
            variables[v] = {
                "values": [round(float(x), 6) for x in flat],
                "mean": round(float(sum(flat) / len(flat)), 6) if flat else None,
            }
        if valid_time is None and "valid_time" in ds.coords:
            valid_time = str(ds["valid_time"].values)
        if latitude is None and "latitude" in ds.coords:
            latitude = [round(float(x), 4) for x in _as_flat_list(ds["latitude"].values)]
        if longitude is None and "longitude" in ds.coords:
            longitude = [round(float(x), 4) for x in _as_flat_list(ds["longitude"].values)]

    return {
        "variables": variables,
        "valid_time": valid_time,
        "latitude": latitude,
        "longitude": longitude,
        "n_grib_datasets": len(datasets),
    }


def _decode_grib_multiday(grib_path: Path) -> dict:
    """
    เหมือน _decode_grib() แต่รองรับ grib ที่มีหลาย time step (หลายวัน) ในไฟล์เดียว — คืนค่า
    spatial-mean ของแต่ละตัวแปร "แยกตามวัน" (ไม่ flatten รวมทุกวันเป็นก้อนเดียวเหมือน _decode_grib())
    เพื่อให้คำนวณ ETo_mm_day ทีละวันได้ก่อนค่อย sum เป็น ET0_mm_week

    คืนค่า: {date_str: {var_short_name: spatial_mean_value, ...}, ...}
    """
    import numpy as np
    import cfgrib

    datasets = cfgrib.open_datasets(str(grib_path))
    per_day: dict = {}

    for ds in datasets:
        time_coord = ds["valid_time"] if "valid_time" in ds.coords else ds.get("time")
        if time_coord is None:
            continue

        # แปลง valid_time -> "YYYY-MM-DD" ด้วย np.datetime_as_string() ตรงๆ แทนการพึ่ง
        # str(x.tolist()) — เพราะ numpy datetime64 ที่ precision ระดับ nanosecond (datetime64[ns],
        # ซึ่งเป็น dtype ที่ cfgrib/xarray มักคืนมาจริง) จะทำให้ .tolist()/.item() คืนค่าเป็น int
        # (nanosecond timestamp) แทนที่จะเป็น datetime object เพราะ python datetime ไม่รองรับ
        # ความละเอียดระดับ ns — ถ้าใช้ str(t)[:10] แบบเดิมจะได้ตัวเลขมั่วๆ แทนวันที่จริง
        # (พบบั๊กนี้จาก fixture test ที่ mock cfgrib ด้วย datetime64[ns] array ก่อนใช้งานจริง)
        raw_times = np.asarray(time_coord.values).reshape(-1)
        if np.issubdtype(raw_times.dtype, np.datetime64):
            date_strs = np.datetime_as_string(raw_times, unit="D").tolist()
        else:
            date_strs = [str(t)[:10] for t in raw_times]

        for v in ds.data_vars:
            da = ds[v]
            spatial_dims = [d for d in da.dims if d in ("latitude", "longitude")]
            reduced = da.mean(dim=spatial_dims) if spatial_dims else da
            values = _as_flat_list(reduced.values)
            if len(date_strs) != len(values):
                # ไม่ควรเกิดขึ้น (มิติเวลาไม่ตรงกับค่าที่ reduce แล้ว) — กันเหนียวไว้ ข้ามตัวแปรนี้
                continue
            for date_str, val in zip(date_strs, values):
                per_day.setdefault(date_str, {})[v] = float(val)

    return per_day


def _run_single_day_mode(args, out_json_path: Path, result: dict) -> tuple:
    """โหมดเดิม (--date / --grib-in) — คืนค่า (missing_variables, warnings) เขียนผลลง result ตรงๆ"""
    if args.grib_in:
        grib_path = Path(args.grib_in)
        if not grib_path.exists():
            raise FileNotFoundError(f"--grib-in ระบุไฟล์ที่ไม่มีอยู่จริง: {grib_path}")
        result["grib_source"] = f"existing_file:{grib_path}"
    else:
        if not args.date:
            raise ValueError("ต้องระบุ --date เมื่อไม่ได้ใช้ --grib-in (โหมดทดสอบ)")
        as_of = datetime.strptime(args.date, "%Y-%m-%d").date()
        grib_path = Path(args.grib_out) if args.grib_out else out_json_path.with_suffix(".grib")
        grib_path.parent.mkdir(parents=True, exist_ok=True)
        # โหมด 1 วัน: default 07:00 (ค่าที่ใช้ตอน sanity/connectivity test ครั้งแรก — ไม่ใช่ methodology
        # ตอน train) ผู้เรียกยังระบุ --time-utc เองได้เสมอถ้าต้องการค่าอื่น
        time_utc = args.time_utc or DEFAULT_SINGLE_DAY_TIME_UTC
        result["time_utc_used"] = time_utc
        elapsed = _fetch_grib_from_cds(as_of, time_utc, args.area, grib_path)
        result["fetch_elapsed_sec"] = round(elapsed, 1)
        result["grib_source"] = f"cds_live:{grib_path}"

    result["grib_size_bytes"] = grib_path.stat().st_size

    decoded = _decode_grib(grib_path)
    result["variables"] = decoded["variables"]
    result["valid_time"] = decoded["valid_time"]
    result["latitude"] = decoded["latitude"]
    result["longitude"] = decoded["longitude"]
    result["n_grib_datasets"] = decoded["n_grib_datasets"]

    found = set(decoded["variables"].keys())
    missing = EXPECTED_SHORT_NAMES - found
    result["missing_variables"] = sorted(missing) if missing else []
    return result["missing_variables"], []


def _run_weekly_mode(args, out_json_path: Path, result: dict) -> tuple:
    """
    โหมดรายสัปดาห์ (--as-of-date) — ดึงวันที่ "เกิดขึ้นแล้วจริง" ของ ISO week นั้น (แยกกลุ่มตาม
    (year, month) เพราะสัปดาห์อาจคาบเกี่ยว 2 เดือน) คำนวณ ETo_mm_day ต่อวันด้วย Penman-Monteith
    แล้ว sum เป็น ET0_mm_week พร้อมค่าเฉลี่ยตัวแปรอื่นตาม feature_schema.md
    (T_mean/RH_pct/VPD_kPa/u2_ms/Rn_MJ)

    คืนค่า (missing_note, warnings)
    """
    as_of = datetime.strptime(args.as_of_date, "%Y-%m-%d").date()
    iso_year, iso_week, _ = as_of.isocalendar()
    result["iso_year"] = int(iso_year)
    result["iso_week"] = int(iso_week)

    warnings: list = []
    per_day: dict = {}
    days_fetched_total: list = []
    grib_paths_used: list = []

    if args.grib_in_week:
        # โหมดทดสอบ: ใช้ไฟล์ .grib ที่มีอยู่แล้วแทนการยิง CDS จริง (แต่ละไฟล์ = กลุ่มวันหนึ่ง)
        for grib_in_path in args.grib_in_week:
            p = Path(grib_in_path)
            if not p.exists():
                raise FileNotFoundError(f"--grib-in-week ระบุไฟล์ที่ไม่มีอยู่จริง: {p}")
            per_day.update(_decode_grib_multiday(p))
            grib_paths_used.append(str(p))
        result["grib_source"] = f"existing_files_week:{grib_paths_used}"
    else:
        candidate_days = _iso_week_days(as_of)
        result["candidate_days"] = [d.isoformat() for d in candidate_days]

        if not candidate_days:
            warnings.append(
                f"as_of_date={as_of.isoformat()} เป็นวันจันทร์ของสัปดาห์นี้เอง (หรือก่อนหน้านั้น) "
                "— ยังไม่มีวันไหนของสัปดาห์นี้ที่ผ่านไปแล้วเลย ข้ามการยิง CDS รอบนี้"
            )
        else:
            # group ตาม (year, month) เพราะ ISO week อาจคาบเกี่ยว 2 เดือน — CDS request แยกตามเดือน
            groups: dict = {}
            for d in candidate_days:
                groups.setdefault((d.year, d.month), []).append(d)

            # โหมดรายสัปดาห์: default 12:00 UTC — ตรงกับ archive/Phase3 step1 era5 download
            # et0.ipynb (cell ที่ export ET0_weekly_phayao_2018_2024.csv จริงใช้ 'time': '12:00'
            # เท่านั้น) แก้ไข 2026-07-05 หลังพบว่าเดิมใช้ 07:00 ผิดจาก methodology ตอน train
            time_utc = args.time_utc or DEFAULT_WEEKLY_TIME_UTC
            result["time_utc_used"] = time_utc
            grib_dir = out_json_path.parent
            for (_, _), days_in_group in sorted(groups.items()):
                fetched_days, grib_path = _fetch_week_with_retry(
                    days_in_group, time_utc, args.area, grib_dir, warnings
                )
                if grib_path is None:
                    warnings.append(f"ไม่สามารถดึงข้อมูลของกลุ่มวัน {days_in_group} ได้เลยแม้แต่วันเดียว")
                    continue
                days_fetched_total.extend(fetched_days)
                grib_paths_used.append(str(grib_path))
                per_day.update(_decode_grib_multiday(grib_path))

        result["grib_source"] = f"cds_live_week:{grib_paths_used}" if grib_paths_used else "cds_live_week:none"

    # คำนวณ ETo ต่อวัน เฉพาะวันที่มีตัวแปรครบทั้ง 6 ตัวที่ต้องใช้ (t2m/d2m/u10/v10/ssr/str — ไม่นับ tp
    # เพราะไม่ได้ใช้ในสูตร ETo แต่ยังคงดึงมาเผื่อใช้ที่อื่น)
    daily_results = []
    for date_str in sorted(per_day.keys()):
        dv = per_day[date_str]
        required = ("t2m", "d2m", "u10", "v10", "ssr", "str")
        if not all(k in dv for k in required):
            warnings.append(f"วันที่ {date_str} มีตัวแปรไม่ครบ ({sorted(dv.keys())}) — ข้ามวันนี้ในการ sum ET0_mm_week")
            continue
        day_eto = _eto_for_day(dv)
        day_eto["date"] = date_str
        daily_results.append(day_eto)

    n_days = len(daily_results)
    result["n_days_in_week"] = n_days
    result["daily_breakdown"] = daily_results
    result["warnings"] = warnings

    if n_days > 0:
        result["ET0_mm_week"] = round(sum(r["ETo_mm_day"] for r in daily_results), 4)
        result["T_mean"] = round(sum(r["T_c"] for r in daily_results) / n_days, 4)
        result["RH_pct"] = round(sum(r["RH_pct"] for r in daily_results) / n_days, 4)
        result["VPD_kPa"] = round(sum(r["VPD_kPa"] for r in daily_results) / n_days, 4)
        result["u2_ms"] = round(sum(r["u2_ms"] for r in daily_results) / n_days, 4)
        result["Rn_MJ"] = round(sum(r["Rn_MJ"] for r in daily_results) / n_days, 4)
    else:
        result["ET0_mm_week"] = None
        result["T_mean"] = None
        result["RH_pct"] = None
        result["VPD_kPa"] = None
        result["u2_ms"] = None
        result["Rn_MJ"] = None

    return (None if n_days > 0 else "no_days_available_yet"), warnings


def main(argv=None) -> int:
    args = parse_args(argv)
    out_json_path = Path(args.out_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)

    weekly_mode = bool(args.as_of_date)

    result: dict = {
        "worker_script": "era5t_worker.py",
        "run_at": datetime.utcnow().isoformat() + "Z",
        "mode": "weekly" if weekly_mode else "single_day",
        "requested_date": args.date,
        "as_of_date": args.as_of_date,
        "dataset": DATASET,
        "time_utc_used": None,  # เติมค่าจริงใน _run_single_day_mode()/_run_weekly_mode() — ไว้ตรวจสอบ
                                 # ย้อนหลังว่ารอบนี้ fetch ด้วยเวลา UTC ไหน (07:00 = sanity test เดิม,
                                 # 12:00 = training methodology สำหรับโหมดรายสัปดาห์)
        "grib_source": None,
        "fetch_elapsed_sec": None,
        "grib_size_bytes": None,
        "variables": None,
        "valid_time": None,
        "latitude": None,
        "longitude": None,
        "n_grib_datasets": None,
        "missing_variables": None,
        # ฟิลด์เฉพาะโหมดรายสัปดาห์ (เป็น None ในโหมด single_day)
        "iso_year": None,
        "iso_week": None,
        "candidate_days": None,
        "n_days_in_week": None,
        "daily_breakdown": None,
        "ET0_mm_week": None,
        "T_mean": None,
        "RH_pct": None,
        "VPD_kPa": None,
        "u2_ms": None,
        "Rn_MJ": None,
        "warnings": None,
        "fetch_error": None,
    }

    try:
        if weekly_mode:
            missing_note, warnings = _run_weekly_mode(args, out_json_path, result)
        else:
            missing_note, warnings = _run_single_day_mode(args, out_json_path, result)

        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        if warnings:
            for w in warnings:
                print(f"[WARN] {w}", file=sys.stderr)

        if weekly_mode and missing_note:
            print(f"[WARN] {missing_note} (n_days_in_week=0 — ET0_mm_week=None รอบนี้)", file=sys.stderr)
            return 1
        if not weekly_mode and missing_note:
            print(f"[WARN] ตัวแปรหายไป: {missing_note}", file=sys.stderr)
            return 1

        print(f"[OK] เขียนผลลัพธ์ไปที่ {out_json_path}")
        return 0

    except Exception as exc:
        result["fetch_error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        try:
            with open(out_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        except Exception as write_exc:
            print(f"[FATAL] เขียน --out-json ไม่ได้ด้วย: {write_exc}", file=sys.stderr)
        print(f"[FAILED] {result['fetch_error']}", file=sys.stderr)
        print(result["traceback"], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
