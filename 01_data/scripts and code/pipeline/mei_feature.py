"""
mei_feature.py
==================
โมดูลแยกสำหรับดึงและคำนวณ feature "MEI" (Multivariate ENSO Index) ที่โมเดล Water Demand
ต้องการ (ดู feature_schema.md หัวข้อ 3-4: คอลัมน์ MEI, MEI_lag4, MEI_lag8)

ที่มา: ต่อยอดจาก download_mei() ใน
01_data/scripts and code/Water_demand/archive/combined_final_pipeline.py (บรรทัด 2511-2567)
— logic การ parse ไฟล์ meiv2.data (bimonthly wide-table -> long format [year, month, MEI])
คัดลอกมาตรงตัว ไม่เปลี่ยน ต่างจากต้นฉบับตรงที่:

  1. เอา hardcoded year filter (`df[(year>=2018)&(year<=2024)]`, เป็นช่วง training เดิม) ออก
     เพราะโมดูลนี้ใช้ตอน inference จริง ต้องการข้อมูลปีล่าสุดที่มีเสมอ ไม่ใช่ช่วง training คงที่
  2. ไม่เขียนไฟล์ mei_monthly.csv ทับเอง — เป็น pure function คืนค่าเป็น DataFrame ในหน่วยความจำ
  3. เพิ่มการคำนวณ MEI_lag4/MEI_lag8 บน weekly-resampled series ตาม build_feature_matrix()
     ในไฟล์เดียวกัน (บรรทัด 2639-2641, 2693) และเพิ่มการตรวจ/log ความเก่าของข้อมูล (ดู
     get_mei_feature() ด้านล่าง) ซึ่งต้นฉบับไม่มี

ความรู้พื้นฐานที่ต้องเข้าใจก่อนใช้โมดูลนี้ (สรุปไว้ก่อนหน้าแล้วตอนสำรวจ ERA5/CHIRPS/MEI):
  - MEI เป็นดัชนีรายเดือนแบบ "bimonthly overlapping" (ทับซ้อน 2 เดือน) ไม่ใช่รายสัปดาห์เอง
  - MEI_lag4 / MEI_lag8 ในโค้ดต้นฉบับคำนวณด้วย .shift(4)/.shift(8) บน DataFrame ที่ resample
    เป็นรายสัปดาห์แล้ว (1 แถว = 1 สัปดาห์) ไม่ใช่ lag 4/8 เดือนของ MEI จริง (~1 และ ~2 รอบ
    อัปเดตจริงของ MEI ตามลำดับ) — โมดูลนี้คง logic เดิมไว้เป๊ะ (นับเป็นแถว/สัปดาห์) เพื่อให้ output
    ตรงกับที่โมเดลถูก train มา ห้ามเปลี่ยนเป็น lag เดือนโดยไม่ retrain โมเดลใหม่
  - หน้าเว็บทางการ (https://psl.noaa.gov/enso/mei/) ระบุว่าอัปเดต "by the 10th of each month"
    แต่ตอนตรวจสอบจริง (2026-07-05) หน้าเว็บแสดง "Last data update: 4 May 2026" คือช้ากว่าที่
    ประกาศไว้เองราว 2 เดือน — get_mei_feature() จึงมีการเช็ค/log คำเตือนเรื่องนี้โดยเฉพาะ (ดู
    STALE_THRESHOLD_DAYS ด้านล่าง) แทนที่จะปล่อยให้ forward-fill ค่าเก่าไปเงียบๆ
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MEI_DATA_URL = "https://psl.noaa.gov/enso/mei/data/meiv2.data"
MEI_REQUEST_TIMEOUT_SEC = 30

# ถ้าข้อมูล MEI จริงล่าสุดที่ดึงได้ (bimonthly period สุดท้ายที่ค่าไม่ใช่ NaN) เก่ากว่านี้ (วัน)
# ให้ log WARNING ให้เห็นชัด — 60 วัน ≈ 2 เดือน ตามที่พบว่าหน้าเว็บ NOAA จริงอัปเดตช้ากว่าที่ประกาศ
# ไว้เอง ("by the 10th of each month") ดู docstring ด้านบนของไฟล์สำหรับหลักฐาน
STALE_THRESHOLD_DAYS = 60

# lag windows ที่ต้องการ (นับเป็น "แถว" บน weekly-resampled series ตาม build_feature_matrix()
# ในไฟล์ archive/combined_final_pipeline.py บรรทัด 2693 — add_lag_features(z, "MEI", [4, 8]))
MEI_LAG_WEEKS = [4, 8]

# จำนวนสัปดาห์ย้อนหลังที่สร้าง skeleton ไว้คำนวณ lag ต้อง >= max(MEI_LAG_WEEKS) เสมอ เผื่อไว้
# มากกว่านั้นพอสมควรเพราะ MEI เป็นข้อมูลรายเดือน ต้องมี anchor point จริงย้อนหลังพอที่จะ shift
# ได้ค่าที่สมเหตุสมผล (ไม่ใช่ NaN เพราะ skeleton สั้นเกินไป)
DEFAULT_WEEKS_BACK = 20

# --- ค่าเทียบเคียง (cross-check) ENSO จาก NOAA CPC ---
# เพิ่มเข้ามาเพื่อแก้ปัญหาที่พบจริง: เมื่อ MEI ล่าสุดถูก forward-fill หลายสัปดาห์ติดกัน (ดู
# mei_reporting_lag_risk ใน get_mei_feature()) ค่า MEI เดิมอาจ "ล้าหลัง" เหตุการณ์ ENSO ที่กำลัง
# พัฒนาเร็ว (เช่น ตอนตรวจสอบจริง 2026-07-05 พบว่าผลค้นหาเว็บทั่วไปอ้างว่ากำลังเป็น El Niño กำลัง
# แรงขึ้น (+1.7C) แต่ข้อมูลทางการ ONI ล่าสุดจาก NOAA CPC ตรงนี้กลับแสดง JFM 2026 = -0.16 (ใกล้ neutral/
# La Nina อ่อนๆ) ซึ่งขัดแย้งกันชัดเจน — เป็นเหตุผลว่าทำไมต้องดึงจากแหล่งทางการโดยตรงมาเทียบเสมอ
# แทนที่จะเชื่อผลสรุปจาก web search เพียงอย่างเดียว) ONI (Oceanic Nino Index) เป็นดัชนีทางการที่ NOAA
# CPC ใช้ประกาศสถานะ El Nino/La Nina/Neutral จริง (ต่างจาก MEI ซึ่งเป็นดัชนี multivariate ของ NOAA PSL
# คนละหน่วยงาน/คนละสูตร) ใช้แค่เป็นค่าอ้างอิงให้ตรวจสอบไขว้ ไม่ใช่ feature ที่โมเดลใช้จริง (โมเดล
# train ด้วย MEI เท่านั้น)
ONI_DATA_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
ENSO_ADVISORY_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline_log.txt"


def _get_logger() -> logging.Logger:
    """
    ใช้ logger ชื่อ "data_pipeline" — ชื่อเดียวกับใน data_pipeline.py โดยตั้งใจ (ไม่ได้ import
    data_pipeline.py เข้ามาโดยตรงเพื่อกันปัญหา circular import ในอนาคตตอนที่ data_pipeline.py
    เริ่ม import โมดูลนี้กลับไปใช้) เพราะ logging.getLogger(ชื่อเดียวกัน) คืนค่า logger object
    ตัวเดียวกันเสมอไม่ว่าจะเรียกจากโมดูลไหนในโปรเซสเดียวกัน — ถ้า data_pipeline.py เรียก
    setup_logging() ไปแล้วก่อนหน้า (เช่นตอน import โมดูลนี้เข้าไปใช้ใน pipeline จริง) logger ตัวนี้
    จะได้ handler เดิม (console + logs/pipeline_log.txt) มาใช้ต่อทันที ไม่สร้างซ้ำ (guard ด้วย
    `if log.handlers` เหมือนกับใน data_pipeline.setup_logging() ทุกตัวอักษร) ถ้ารันไฟล์นี้แบบ
    standalone (เช่นตอนเทส) ก็จะสร้าง handler ให้เองเป็นครั้งแรก เขียนลงไฟล์ log เดียวกัน
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
# Step 1: ดึง + parse meiv2.data (ต่อยอดจาก download_mei() ต้นฉบับ)
# ---------------------------------------------------------------------------
def _parse_mei_text(raw_text: str) -> pd.DataFrame:
    """
    Parse เนื้อหา text ของ meiv2.data เป็น long-format DataFrame [year, month, MEI]

    Logic คัดลอกมาจาก download_mei() ใน combined_final_pipeline.py บรรทัด 2524-2562 ตรงตัว
    (ไม่เปลี่ยน parsing logic เดิมแม้แต่จุดเดียว) — format ไฟล์คือตารางกว้าง แถวละ 1 ปี, 12 คอลัมน์
    = ค่า MEI ของ 12 ช่วง "bimonthly overlapping season" (DJ, JF, FM, ..., ND) โดย map ค่าแต่ละ
    ช่วงเข้ากับ "เดือนที่สองของคู่" (เช่น DJ (ธ.ค.-ม.ค.) -> map เป็นเดือน 1) ค่า -999.00 = missing -> NaN
    """
    lines = raw_text.strip().split("\n")

    data_lines: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("MEI"):
            continue
        parts = stripped.split()
        # หมายเหตุ (ข้อแตกต่างจากต้นฉบับ): download_mei() เดิมเช็คแค่ `len(parts) >= 2` ซึ่งจะจับ
        # เอาบรรทัดหัวไฟล์ "startyear endyear" (มี 2 คอลัมน์ตัวเลข เช่น "1979  2026") มาเป็น
        # data row ผิดๆ ด้วย (ได้ record ปลอม {year: 1979, month: 1, MEI: 2026.0}) — ต้นฉบับไม่พังเพราะ
        # มี filter `df[(year>=2018)&(year<=2024)]` ต่อท้ายคอยกรองปีที่ผิดปกติออกไปอีกชั้นหนึ่งเสมอ
        # (เป็น safety net ที่บังเอิญช่วยกันบั๊กนี้ไว้) โมดูลนี้ตัด filter ปีตายตัวนั้นออกไปแล้ว (ต้องการ
        # ข้อมูลทุกปีตอน inference) จึงต้องเช็คให้ถูกต้องตรงนี้แทน: แถวข้อมูลจริงต้องมี 13 คอลัมน์เสมอ
        # (ปี + ค่า MEI 12 เดือน) จึงจะถือว่าเป็น data row ป้องกันไม่ให้บรรทัดหัวไฟล์หลุดเข้ามาปนได้
        if len(parts) == 13 and parts[0].isdigit():
            data_lines.append(parts)

    # bimonth_labels ต้นฉบับ = ["DJ","JF","FM","MA","AM","MJ","JJ","JA","AS","SO","ON","ND"]
    # ค่าแต่ละช่วง map เข้ากับ "เดือนที่สองของคู่" (1-indexed) ตรงตามต้นฉบับบรรทัด 2536-2540
    second_month = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    records: list[dict] = []
    for parts in data_lines:
        year = int(parts[0])
        values = parts[1:]
        for i, val_str in enumerate(values[:12]):
            try:
                mei_val = float(val_str)
                if mei_val == -999.0:
                    mei_val = float("nan")
            except ValueError:
                mei_val = float("nan")
            records.append({"year": year, "month": second_month[i], "MEI": mei_val})

    df = pd.DataFrame(records)
    # หมายเหตุ: ต้นฉบับ (download_mei()) กรอง df[(year>=2018)&(year<=2024)] เพราะเป็นช่วง training
    # คงที่ (ดู docstring หัวไฟล์ ข้อ 1) — โมดูลนี้ตัดการกรองนี้ออก เพราะใช้ตอน inference ต้องการ
    # "ทุกปีที่มี" รวมถึงปีล่าสุดเสมอ ไม่ใช่ค้างอยู่ที่ปี 2024
    df = df.sort_values(["year", "month"]).reset_index(drop=True)
    return df


def _download_mei_raw(
    url: str = MEI_DATA_URL,
    timeout: int = MEI_REQUEST_TIMEOUT_SEC,
    fetch_fn: Callable[..., Any] = requests.get,
) -> pd.DataFrame:
    """
    ดึงไฟล์ meiv2.data ดิบจาก NOAA PSL แล้ว parse เป็น DataFrame [year, month, MEI]

    fetch_fn: จุด inject สำหรับเทส (ค่าเริ่มต้นคือ requests.get จริง) — ให้เทสเรียกด้วยฟังก์ชันปลอมที่
    คืนค่า object ซึ่งมี .text และ .raise_for_status() ได้ โดยไม่ต้องยิง network จริง ไม่กระทบ
    พฤติกรรมตอน production เพราะ default ยังเป็น requests.get เหมือนเดิมทุกประการ
    """
    logger.info("Downloading MEI v2 from %s ...", url)
    resp = fetch_fn(url, timeout=timeout)
    resp.raise_for_status()
    return _parse_mei_text(resp.text)


# ---------------------------------------------------------------------------
# Step 1b: ดึง ONI (Nino 3.4) จาก NOAA CPC มาเป็นค่าเทียบเคียง (ไม่ใช่ feature หลัก)
# ---------------------------------------------------------------------------
def _parse_oni_text(raw_text: str) -> list[dict]:
    """
    Parse เนื้อหา text ของ oni.ascii.txt (Oceanic Nino Index, NOAA CPC) เป็น
    list of dict [{"season": str, "year": int, "total": float, "anom": float}, ...]
    เรียงตามลำดับเวลาเดิมในไฟล์ (เก่า -> ใหม่ อยู่แล้ว ไม่ต้อง sort เพิ่ม)

    Format จริง (ตรวจสอบแล้วตอน 2026-07-05): บรรทัดแรกเป็น header
    " SEAS  YR   TOTAL   ANOM" บรรทัดข้อมูลมี 4 คอลัมน์เสมอ เช่น "  JFM 2026  26.57  -0.16"
    (season = 3-month running season, ANOM = Nino 3.4 SST anomaly องศาเซลเซียส ซึ่งคือค่าที่ใช้
    นิยาม El Nino (>= +0.5 ต่อเนื่อง 5 ฤดู)/La Nina (<= -0.5 ต่อเนื่อง 5 ฤดู)/Neutral ทางการ)
    """
    lines = raw_text.strip().split("\n")
    records: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.upper().startswith("SEAS"):
            continue
        parts = stripped.split()
        if len(parts) != 4:
            continue
        season, year_str, total_str, anom_str = parts
        try:
            records.append({
                "season": season,
                "year": int(year_str),
                "total": float(total_str),
                "anom": float(anom_str),
            })
        except ValueError:
            continue
    return records


def _fetch_oni_latest(
    url: str = ONI_DATA_URL,
    timeout: int = MEI_REQUEST_TIMEOUT_SEC,
    fetch_fn: Callable[..., Any] = requests.get,
) -> dict:
    """
    ดึงค่า ONI (Nino 3.4 SST anomaly เฉลี่ย 3 เดือนแบบ rolling) ล่าสุดจาก NOAA CPC มาเป็นค่า
    เทียบเคียง (cross-check) กับ MEI — ออกแบบให้ "ไม่ raise" เหมือนกับ _download_mei_raw() แต่
    ต่างกันตรงที่ error ที่นี่ log เป็น WARNING ไม่ใช่ ERROR เพราะเป็นข้อมูลเสริมสำหรับตรวจสอบไขว้
    เท่านั้น ไม่ใช่ feature หลักที่โมเดล Water Demand ต้องใช้ตรงๆ (โมเดล train ด้วย MEI ไม่ใช่ ONI)
    — ถ้าดึง/parse ไม่สำเร็จ ไม่ควรทำให้ get_mei_feature() ทั้งฟังก์ชันล้มเหลวไปด้วย

    คืนค่า: {"nino34_oni_latest": {"season": str, "year": int, "anom": float} | None,
             "fetch_error": str | None}
    """
    try:
        logger.info("Downloading ONI (Nino 3.4 cross-check) from %s ...", url)
        resp = fetch_fn(url, timeout=timeout)
        resp.raise_for_status()
        records = _parse_oni_text(resp.text)
        if not records:
            logger.warning(
                "ดึง ONI จาก %s สำเร็จ แต่ parse ไม่ได้ค่าเลย — ข้าม cross-check รอบนี้ "
                "(ไม่กระทบ MEI feature หลัก)",
                url,
            )
            return {"nino34_oni_latest": None, "fetch_error": "parsed_but_empty"}
        latest = records[-1]
        return {
            "nino34_oni_latest": {
                "season": latest["season"],
                "year": latest["year"],
                "anom": round(latest["anom"], 2),
            },
            "fetch_error": None,
        }
    except Exception as exc:
        logger.warning(
            "ดึงข้อมูล ONI (Nino 3.4 cross-check) จาก %s ไม่สำเร็จ (%s) — ข้าม cross-check "
            "รอบนี้ (ไม่กระทบ MEI feature หลักซึ่งดึงจาก NOAA PSL คนละแหล่งข้อมูล)",
            url, exc,
        )
        return {"nino34_oni_latest": None, "fetch_error": str(exc)}


# ---------------------------------------------------------------------------
# Step 2: resample เป็นรายสัปดาห์ + คำนวณ lag (ตาม build_feature_matrix() ต้นฉบับ)
# ---------------------------------------------------------------------------
def _build_weekly_mei_series(
    mei_raw: pd.DataFrame,
    as_of_date: date,
    weeks_back: int,
) -> pd.DataFrame:
    """
    สร้าง DataFrame รายสัปดาห์ต่อเนื่อง ตั้งแต่ (as_of_date - weeks_back สัปดาห์) ถึง as_of_date
    (รวม as_of_date เอง) แล้ว merge ค่า MEI ตาม (year, month) ของแต่ละสัปดาห์ + interpolate/
    bfill/ffill + คำนวณ lag ตาม logic เดียวกับ build_feature_matrix() ในบรรทัด 2639-2641, 2693
    ของ combined_final_pipeline.py ตรงตัว:

        df = df.merge(mei[["year","month","MEI"]], on=["year","month"], how="left")
        df["MEI"] = df["MEI"].interpolate(method="linear").bfill().ffill()
        ...
        z = add_lag_features(z, "MEI", [4, 8])   # shift(4)/shift(8) บนแถวรายสัปดาห์

    คืนค่า DataFrame เรียงตาม (year, week) พร้อมคอลัมน์ year, week, date, month, MEI,
    MEI_lag4, MEI_lag8, mei_is_actual (bool บอกว่าค่า MEI ของแถวนั้นมาจากข้อมูลจริงที่โหลดได้
    ตรงๆ ก่อน interpolate/ffill หรือถูกเติมมาแทน — ใช้ตรวจ stale_fallback_used ใน get_mei_feature())

    หมายเหตุสำคัญ (บั๊กที่พบและแก้ระหว่างเทส integration): ห้ามใช้วันที่ดิบจากการลบสัปดาห์
    (as_of_ts - N สัปดาห์) มาหา "เดือน" สำหรับ merge ตรงๆ เพราะ as_of_date อาจเป็นวันไหนก็ได้ในสัปดาห์
    นั้น (เช่นถ้า pipeline รันวันอาทิตย์ที่ 5 ก.ค. ซึ่งเป็นวันสุดท้ายของสัปดาห์ ISO ที่ต้นสัปดาห์ (วันจันทร์)
    อยู่ในเดือน มิ.ย.) — ถ้าใช้ .month ของวันที่ดิบตรงๆ จะได้เดือนไม่คงที่ขึ้นอยู่กับว่ารันวันไหนของสัปดาห์
    ทำให้ MEI ของ "สัปดาห์เดียวกัน" ผูกกับคนละเดือนได้ถ้ารันคนละวันในสัปดาห์เดียวกัน จึงต้อง reconstruct
    วันจันทร์ของแต่ละ ISO week ก่อนเสมอ (ด้วย pattern "%G-W%V-%u" ที่ใช้ตรงกันทั้งไฟล์นี้และต้นฉบับ
    combined_final_pipeline.py) แล้วค่อยหาเดือนจากวันจันทร์นั้น ให้ผลลัพธ์คงที่ไม่ว่าจะรันวันไหนของสัปดาห์
    """
    as_of_ts = pd.Timestamp(as_of_date)

    rows = []
    for delta in range(weeks_back, -1, -1):
        raw_date = as_of_ts - pd.Timedelta(weeks=delta)
        iso_year, iso_week, _ = raw_date.isocalendar()
        # reconstruct วันจันทร์ของสัปดาห์นี้เสมอ (ไม่ใช้ raw_date ตรงๆ) — ดูหมายเหตุด้านบน
        monday_date = pd.to_datetime(f"{iso_year}-W{iso_week:02d}-1", format="%G-W%V-%u")
        rows.append({"year": int(iso_year), "week": int(iso_week), "date": monday_date})

    skel = pd.DataFrame(rows).drop_duplicates(subset=["year", "week"]).reset_index(drop=True)
    skel["month"] = skel["date"].dt.month

    merged = skel.merge(mei_raw[["year", "month", "MEI"]], on=["year", "month"], how="left")
    merged["mei_is_actual"] = merged["MEI"].notna()

    # interpolate/bfill/ffill ตรงตามต้นฉบับ (บรรทัด 2640-2641) — ลำดับ bfill ก่อน ffill ห้ามสลับ
    merged["MEI"] = merged["MEI"].interpolate(method="linear").bfill().ffill()

    merged = merged.sort_values(["year", "week"]).reset_index(drop=True)
    for lag in MEI_LAG_WEEKS:
        merged[f"MEI_lag{lag}"] = merged["MEI"].shift(lag)

    return merged


# ---------------------------------------------------------------------------
# Step 3: จุดเรียกหลัก — get_mei_feature()
# ---------------------------------------------------------------------------
def get_mei_feature(
    as_of_date: Optional[date] = None,
    weeks_back: int = DEFAULT_WEEKS_BACK,
    url: str = MEI_DATA_URL,
    stale_threshold_days: int = STALE_THRESHOLD_DAYS,
    fetch_fn: Callable[..., Any] = requests.get,
    oni_url: str = ONI_DATA_URL,
    oni_fetch_fn: Callable[..., Any] = requests.get,
) -> dict:
    """
    จุดเรียกหลักของโมดูลนี้: ดึง MEI ล่าสุดจาก NOAA PSL แล้วคำนวณ feature MEI/MEI_lag4/MEI_lag8
    ของสัปดาห์ as_of_date (ค่าเริ่มต้น = วันนี้)

    ออกแบบให้ "ไม่ raise exception ออกไปนอกฟังก์ชันนี้" (สอดคล้องกับหลักการ error isolation ทั้งไฟล์
    ของ data_pipeline.py) — ถ้าดึง/parse ข้อมูลไม่สำเร็จ (network error, format เปลี่ยน ฯลฯ) จะ log
    error แล้วคืนค่า dict ที่มี fetch_error ระบุสาเหตุ พร้อมค่า MEI เป็น None ทั้งหมดแทนการ raise

    คืนค่าเป็น dict:
      {
        "as_of_date": "YYYY-MM-DD",
        "as_of_year": int, "as_of_week": int,
        "mei_current": float | None,
        "mei_lag4": float | None,
        "mei_lag8": float | None,
        "latest_available_period": {"year": int, "month": int} | None,
        "data_age_days": int | None,
        "is_stale": bool | None,             # True ถ้าข้อมูลจริงล่าสุดเก่ากว่า stale_threshold_days
        "stale_threshold_days": int,
        "stale_fallback_used": bool,         # True ถ้าค่าของสัปดาห์ as_of ต้องพึ่ง ffill (ไม่มีข้อมูลจริงตรงเดือนนั้น)
        "data_source": url,
        "fetch_error": str | None,
        "mei_reporting_lag_risk": bool,       # True เมื่อ mei_current == mei_lag4 == mei_lag8 ทุกค่า
                                               # (แปลว่า MEI ของ 3 จุดนี้มาจาก forward-fill ค่าเดียวกันหมด
                                               # เพราะ MEI เป็นข้อมูลรายเดือน/bimonthly ไม่ได้อัปเดตทุกสัปดาห์
                                               # — ค่านี้อาจ "ล้าหลัง" เหตุการณ์ ENSO ที่กำลังพัฒนาเร็วได้)
        "mei_reporting_lag_risk_note": str | None,  # คำอธิบายภาษาไทย มีค่าเมื่อ mei_reporting_lag_risk=True เท่านั้น
        "nino34_oni_latest": {"season": str, "year": int, "anom": float} | None,  # ค่าเทียบเคียงจาก NOAA CPC (ONI)
        "nino34_oni_fetch_error": str | None,
        "enso_advisory_url": str,             # ลิงก์ NOAA CPC ENSO advisory ให้ผู้ใช้ตรวจสอบไขว้ด้วยตาเอง
      }

    หมายเหตุ (เพิ่มเข้ามา 2026-07-05 หลังพบว่า MEI=0.27 ที่ได้จริง ดูไม่สอดคล้องกับผลค้นหาเว็บทั่วไป
    ที่อ้างว่ากำลังเป็น El Nino กำลังแรงขึ้น — ตรวจสอบไขว้ด้วย ONI ทางการจาก NOAA CPC (ดึงจริงตอนนั้น)
    กลับพบว่า JFM 2026 = -0.16 (ใกล้ neutral/La Nina อ่อนๆ) ซึ่งสอดคล้องกับ MEI=0.27 มากกว่า ไม่ใช่ El Nino
    แรงอย่างที่ web search อ้าง — เป็นหลักฐานว่าเว็บค้นหาทั่วไปเชื่อถือไม่ได้เท่าดึงจากแหล่งทางการตรงๆ
    จึงเพิ่ม nino34_oni_latest/enso_advisory_url ไว้ให้ตรวจสอบไขว้ได้เองทุกครั้งที่เรียกฟังก์ชันนี้)
    """
    as_of = as_of_date or date.today()
    as_of_ts = pd.Timestamp(as_of)
    as_of_year, as_of_week, _ = as_of_ts.isocalendar()

    result: dict = {
        "as_of_date": as_of.isoformat(),
        "as_of_year": int(as_of_year),
        "as_of_week": int(as_of_week),
        "mei_current": None,
        "mei_lag4": None,
        "mei_lag8": None,
        "latest_available_period": None,
        "data_age_days": None,
        "is_stale": None,
        "stale_threshold_days": stale_threshold_days,
        "stale_fallback_used": False,
        "data_source": url,
        "fetch_error": None,
        "mei_reporting_lag_risk": False,
        "mei_reporting_lag_risk_note": None,
        "nino34_oni_latest": None,
        "nino34_oni_fetch_error": None,
        "enso_advisory_url": ENSO_ADVISORY_URL,
    }

    # ดึง ONI มาเทียบเคียงก่อนเลย (independent จากการดึง MEI หลัก) — ทำแม้ MEI หลักจะดึงไม่สำเร็จก็ตาม
    # เพราะเป็นค่าเสริมคนละแหล่ง ไม่ควรให้ความล้มเหลวของฝั่งใดฝั่งหนึ่งกระทบอีกฝั่ง (ดู _fetch_oni_latest()
    # ซึ่งไม่ raise เองอยู่แล้ว)
    oni_info = _fetch_oni_latest(url=oni_url, fetch_fn=oni_fetch_fn)
    result["nino34_oni_latest"] = oni_info["nino34_oni_latest"]
    result["nino34_oni_fetch_error"] = oni_info["fetch_error"]

    try:
        mei_raw = _download_mei_raw(url=url, fetch_fn=fetch_fn)
    except Exception as exc:
        logger.error("ดึงข้อมูล MEI จาก %s ไม่สำเร็จ (%s) — ไม่มีค่า MEI ให้ใช้ในรอบนี้", url, exc)
        result["fetch_error"] = str(exc)
        return result

    actual_rows = mei_raw.dropna(subset=["MEI"])
    if actual_rows.empty:
        logger.error(
            "ดึงข้อมูล MEI จาก %s สำเร็จ แต่ parse ไม่ได้ค่าที่ใช้ได้เลยสักแถว (ทุกแถวเป็น NaN) "
            "— ตรวจสอบว่า format ไฟล์ต้นทางเปลี่ยนไปจากที่ _parse_mei_text() รองรับหรือไม่",
            url,
        )
        result["fetch_error"] = "parsed_but_empty"
        return result

    latest_row = actual_rows.sort_values(["year", "month"]).iloc[-1]
    latest_year = int(latest_row["year"])
    latest_month = int(latest_row["month"])
    result["latest_available_period"] = {"year": latest_year, "month": latest_month}

    # วันที่ประมาณ "สิ้นสุด" ของช่วง bimonthly ล่าสุดที่มีข้อมูลจริง ใช้วันสุดท้ายของ "เดือนที่สอง
    # ของคู่" (second_month ตาม _parse_mei_text()) เป็นตัวแทน เพื่อคำนวณอายุของข้อมูล
    latest_period_end = pd.Timestamp(year=latest_year, month=latest_month, day=1) + pd.offsets.MonthEnd(0)
    data_age_days = (as_of_ts.normalize() - latest_period_end.normalize()).days
    result["data_age_days"] = int(data_age_days)

    is_stale = data_age_days > stale_threshold_days
    result["is_stale"] = bool(is_stale)

    if is_stale:
        logger.warning(
            "MEI ล่าสุดที่ดึงได้จาก NOAA คือช่วง %d-%02d (อายุ %d วัน > เกณฑ์ %d วัน ~%.1f เดือน) — "
            "หน้าเว็บทางการระบุว่าอัปเดต 'by the 10th of each month' แต่ข้อมูลจริงช้ากว่านั้น "
            "ใช้ค่า MEI ล่าสุดนี้ต่อไปแบบ fallback (forward-fill) สำหรับสัปดาห์ %d-W%02d — ผลกระทบ: "
            "MEI/MEI_lag4/MEI_lag8 ของรอบนี้อาจไม่สะท้อนสถานะ ENSO ปัจจุบันจริงๆ ควรตรวจสอบ "
            "https://psl.noaa.gov/enso/mei/ ด้วยตาก่อนเชื่อผลทำนายที่พึ่ง feature นี้",
            latest_year, latest_month, data_age_days, stale_threshold_days,
            stale_threshold_days / 30.0, as_of_year, as_of_week,
        )
    else:
        logger.info(
            "MEI ล่าสุดที่ดึงได้จาก NOAA คือช่วง %d-%02d (อายุ %d วัน ไม่เกินเกณฑ์ %d วัน) — ปกติ",
            latest_year, latest_month, data_age_days, stale_threshold_days,
        )

    weekly = _build_weekly_mei_series(mei_raw, as_of_date=as_of, weeks_back=weeks_back)
    as_of_row = weekly[(weekly["year"] == as_of_year) & (weekly["week"] == as_of_week)]

    if as_of_row.empty:
        # ไม่ควรเกิดขึ้นเพราะ _build_weekly_mei_series() สร้างแถวของ as_of ไว้เสมอ แต่กันเหนียวไว้
        # เผื่อ weeks_back ถูกเรียกด้วยค่าผิดปกติ (เช่นติดลบ) จากภายนอก
        logger.error(
            "สร้าง weekly series ของ MEI ไม่มีแถวของสัปดาห์ปัจจุบัน (%d-W%02d) — ตรวจสอบค่า weeks_back=%d ที่ส่งเข้ามา",
            as_of_year, as_of_week, weeks_back,
        )
        result["fetch_error"] = "weekly_series_missing_as_of_row"
        return result

    row = as_of_row.iloc[0]
    result["mei_current"] = None if pd.isna(row["MEI"]) else round(float(row["MEI"]), 4)
    result["mei_lag4"] = None if pd.isna(row["MEI_lag4"]) else round(float(row["MEI_lag4"]), 4)
    result["mei_lag8"] = None if pd.isna(row["MEI_lag8"]) else round(float(row["MEI_lag8"]), 4)
    result["stale_fallback_used"] = bool(not row["mei_is_actual"])

    # mei_reporting_lag_risk: True เมื่อ current/lag4/lag8 เท่ากันหมดทุกค่า (ไม่มี None ปนอยู่) — บอกว่า
    # ทั้ง 3 จุดพึ่งค่า forward-fill เดียวกัน (เกิดขึ้นเป็นปกติเมื่อ MEI เป็นข้อมูลรายเดือน/bimonthly แต่
    # สัปดาห์ล่าสุดหลายสัปดาห์ยังไม่มีค่าจริงใหม่มาแทน) ไม่ใช่ bug — แต่ต้องเตือนเพราะแปลว่า feature นี้
    # อาจไม่ทันเหตุการณ์ ENSO ที่กำลังเปลี่ยนเร็ว (ดู nino34_oni_latest/enso_advisory_url สำหรับตรวจสอบไขว้)
    values = (result["mei_current"], result["mei_lag4"], result["mei_lag8"])
    result["mei_reporting_lag_risk"] = bool(
        all(v is not None for v in values) and values[0] == values[1] == values[2]
    )

    if result["mei_reporting_lag_risk"]:
        result["mei_reporting_lag_risk_note"] = (
            "MEI, MEI_lag4, MEI_lag8 มีค่าเท่ากันทั้งหมด (forward-fill จากค่าจริงเดือนเดียวกัน) "
            "เพราะข้อมูล MEI รายเดือน/bimonthly ยังไม่มีค่าจริงใหม่มาแทนในช่วงสัปดาห์ล่าสุดๆ นี้ — "
            "ค่านี้อาจไม่สะท้อนสถานะ ENSO ปัจจุบันจริงๆ หาก ENSO กำลังเปลี่ยนแปลงเร็ว ควรเทียบกับ "
            "nino34_oni_latest (ค่า ONI ล่าสุดจาก NOAA CPC) และ/หรือเปิด enso_advisory_url ตรวจสอบ "
            "ด้วยตาก่อนเชื่อผลทำนายที่พึ่ง feature MEI นี้ต่อเนื่องหลายสัปดาห์"
        )
        logger.warning(
            "mei_reporting_lag_risk=True: MEI=MEI_lag4=MEI_lag8=%s (forward-fill ต่อเนื่อง) "
            "— เทียบเคียง ONI ล่าสุดจาก NOAA CPC: %s (fetch_error=%s) ดู %s ประกอบก่อนเชื่อค่านี้",
            result["mei_current"], result["nino34_oni_latest"], result["nino34_oni_fetch_error"],
            ENSO_ADVISORY_URL,
        )

    logger.info(
        "MEI feature พร้อมใช้: as_of=%d-W%02d, MEI=%s, MEI_lag4=%s, MEI_lag8=%s "
        "(latest_actual_period=%d-%02d, data_age_days=%d, is_stale=%s, stale_fallback_used=%s, "
        "mei_reporting_lag_risk=%s, nino34_oni_latest=%s)",
        as_of_year, as_of_week, result["mei_current"], result["mei_lag4"], result["mei_lag8"],
        latest_year, latest_month, data_age_days, is_stale, result["stale_fallback_used"],
        result["mei_reporting_lag_risk"], result["nino34_oni_latest"],
    )

    return result


if __name__ == "__main__":
    # รันไฟล์นี้ตรงๆ เพื่อดึง MEI จริงจาก NOAA แล้ว print ผลลัพธ์ — ยังไม่เชื่อมกับโมเดล/pipeline หลัก
    # ตามที่ระบุไว้ในขอบเขตงานนี้ (แค่ทดสอบว่าโมดูลดึง/คำนวณ feature ได้ถูกต้องก่อน)
    import json

    print(json.dumps(get_mei_feature(), indent=2, ensure_ascii=False))
