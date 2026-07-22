"""
chirps_feature.py
==================
โมดูลแยกสำหรับดึงและคำนวณ feature ที่มาจาก CHIRPS rainfall ที่โมเดล Water Demand ต้องการ
(ดู feature_schema.md หัวข้อ 3-4: คอลัมน์ P_mm_week, P_eff_mm, SPI_4, drought_flag)

ที่มา: ต่อยอดจาก archive/Phase3 step2 chirps rainfall.ipynb ซึ่ง comment ไว้เองในโค้ดต้นฉบับว่า
"Method: GEE export (แนะนำ) หรือ rasterio extract จาก GeoTIFF" — โมดูลนี้เลือกใช้ทาง GEE export
เป็นแหล่งหลัก (Final + Prelim เดิม) และเพิ่มทาง rasterio extract ตรงจาก CHC FTP เป็นแหล่งเสริม
(Prelim FTP — ดูประวัติการแก้ไขด้านล่าง) แทนที่จะใช้วิธี download .tif.gz ทีละวันจาก
data.chc.ucsb.edu ตรงๆ แบบที่ notebook เดิมใช้เป็น fallback (เปราะบางกว่ามาก: ต้องยิง request
แยกทุกวัน, ไฟล์ 404/เปลี่ยน path บ่อย, ไม่มี retry — ตอนนี้ปรับให้ทนทานขึ้นด้วย ftplib + cache +
retry-skip แทน ดู _fetch_chirps_prelim_from_ftp())

ต่างจากต้นฉบับตรงที่:
  1. ใช้ Earth Engine Python API (`ee`) ดึงค่าฝนตรงที่พิกัด ต.แม่นาเรือ เป็นแหล่งหลัก (Final +
     Prelim เดิม) และใช้ ftplib+rasterio ดึงตรงจาก CHC FTP เป็นแหล่งเสริม (Prelim FTP)
  2. แยกแหล่งข้อมูลตาม latency จริงของ CHIRPS เป็น 3 ชั้น (ดู docstring ของ _fetch_chirps_weekly
     ด้านล่าง): CHIRPS Final (ทางการใน GEE catalog, ล่าช้า ~20 วัน) -> CHIRPS Prelim FTP (ตรงจาก
     CHC FTP, ล่าช้า ~7 วัน) -> CHIRPS-Prelim เดิม (community catalog บน GEE, fallback สุดท้าย)
     แล้ว log ให้ชัดเจนว่าค่าของแต่ละสัปดาห์มาจากแหล่งไหน
  3. เพิ่มการโหลด "ประวัติ P_mm_week หลายปี" จากไฟล์ training ที่มีอยู่แล้วในเครื่อง
     (Water_demand/active/ml_features_phase4.csv) เป็น baseline สำหรับคำนวณ SPI_4 แบบ real-time
     แทนที่จะต้องดึง CHIRPS ย้อนหลังทุกปีใหม่ทุกครั้ง (ดู _load_historical_p_mm_week ด้านล่าง)
  4. เพิ่ม error isolation แบบเดียวกับ mei_feature.py/data_pipeline.py — ไม่ raise exception ออก
     นอกฟังก์ชัน get_chirps_feature()
  5. เพิ่ม rolling 7-day window fallback สำหรับกรณีสัปดาห์ปฏิทิน ISO ปัจจุบันไม่มีข้อมูลจริงเลยสักวัน
     (ดู _rolling_window_estimate() — data_type="rolling_estimate")

ความรู้พื้นฐานที่ต้องเข้าใจก่อนใช้โมดูลนี้:
  - พิกัดอ้างอิง: TARGET_LAT/TARGET_LON = (19.05, 99.80) ตรงตามที่ระบุใน archive notebook
    (comment "Mae Na Rua Sub-District, Phayao (19.05°N, 99.80°E)")
  - P_eff คำนวณต่างสูตรตาม zone (ตรงตาม ZONE_CONFIG ใน feature_schema.md หัวข้อ 3):
      zone_A (rainfed/upland)  -> P_eff_upland = max(0, P_mm_week - 5) * 0.85
      zone_B (irrigated/paddy) -> P_eff_paddy  = P_mm_week * 0.8
    เก็บเป็นคอลัมน์ชื่อ "P_eff_mm" เสมอ (ตาม rename ที่ build_feature_matrix() ทำไว้บรรทัด 213
    ของ feature_schema.md — ไม่ใช่ค้างชื่อ P_eff_paddy/P_eff_upland)
  - Lag ที่ต้องการสำหรับ P_mm_week คือ [1, 2, 4] เท่านั้น (ตาม
    `add_lag_features(z, "P_mm_week", [1, 2, 4])` บรรทัด 221 ของ feature_schema.md — ไม่ใช่
    LAG_WINDOWS เต็มชุด [1,2,3,4,8,12] ซึ่งใช้กับ target เท่านั้น)
  - SPI_4 คำนวณเป็น z-score ของ P_4week (rolling 4-week sum ของ P_mm_week) **เทียบกับสัปดาห์
    เดียวกันข้ามปีทั้งหมด** (`groupby('week')` ไม่ใช่ `groupby(['year','week'])`) ตามสูตรตรงจาก
    feature_schema.md หัวข้อ 3.5:
        SPI_4 = groupby('week')['P_4week'].transform(
                    lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0
                ).fillna(0.0).round(3)
        drought_flag = (SPI_4 < -1.0).astype(int)
    ผลตามมา: การคำนวณ SPI_4 ของสัปดาห์ปัจจุบันแบบ real-time "ต้องมีข้อมูล P_4week ของสัปดาห์
    เดียวกันจากปีก่อนๆ ครบ ไม่ใช่แค่ปีเดียว" — นี่คือเหตุผลที่โมดูลนี้ต้องโหลด "ประวัติ" (historical
    baseline) ก่อนเสมอ ไม่ใช่แค่ดึง CHIRPS ของสัปดาห์ล่าสุดอย่างเดียว
  - CHIRPS ไม่ได้อัปเดตทันที มีหลายระดับความสมบูรณ์/latency (ดู _fetch_chirps_weekly ด้านล่างสำหรับ
    รายละเอียดเต็มของ waterfall 3 ชั้น):
      Final     : ล่าช้า ~20 วันหลังสิ้นเดือน (รอ station gauge data มา unbias ก่อน) — แม่นสุด
      Prelim FTP: ล่าช้า ~7 วัน (ตรงจาก CHC FTP, publish เป็นรอบ pentad ทุก 5 วัน) — ยังไม่ผ่าน
                  gauge correction แต่เร็วกว่า Final มาก
      Prelim เดิม (community, GEE): fallback สุดท้ายเท่านั้น
    ค่าของสัปดาห์ล่าสุด (as_of week) แทบทุกครั้งจะเป็น prelim_ftp หรือ rolling_estimate ไม่ใช่ final

ประวัติการแก้ไข:
  - 2026-07-05: ทดสอบกับ GEE จริงสำเร็จทั้ง CHIRPS Final และ CHIRPS-Prelim ด้วย project
    'maenaruea-water-pipeline' (รวมถึงแก้บั๊ก pentad-vs-daily ที่เจอระหว่างเทส — ดู
    _expand_pentad_to_daily())
  - 2026-07-14: เปลี่ยน _fetch_chirps_daily_from_gee() จากเรียก ee.Initialize(project=...) ตรงๆ
    เป็นเรียกผ่าน gee_auth.init_ee(gee_project) (ดู gee_auth.py) เพื่อรองรับ Service Account
  - ✅ 2026-07-22: ยืนยันแล้วว่า Service Account auth ทำงานได้จริงบนเครื่อง production (log
    "GEE auth: ใช้ Service Account" ปรากฏจริงตอนรัน) ไม่ใช่ personal credential แบบ interactive
    อีกต่อไป
  - 2026-07-22 (รอบ 2 — Prelim FTP): เพิ่มแหล่งข้อมูลที่ 3 "CHIRPS v3.0 Preliminary" ตรงจาก CHC
    FTP (ftp.chc.ucsb.edu) แทนที่จะใช้ทาง GEE-native ของ CHIRPS v3 (asset
    UCSB-CHC/CHIRPS/V3/DAILY_SAT) ซึ่งทดสอบจริงแล้วพบว่า lag ยังเท่า Final เดิม (~22 วัน) ไม่ช่วย
    อะไร (แม้หน้า catalog จะเขียนว่า "Near-Real-Time" ก็ตาม) ส่วน CHIRPS v3 Preliminary ทาง FTP
    ยืนยันด้วยการ list ไดเรกทอรีจริงว่า lag จริง ~7 วัน (เร็วกว่า Final ~3 เท่า) และไฟล์เป็นรายวัน
    จริงอยู่แล้ว (ชื่อไฟล์ chirps-v3.0.prelim.YYYY.MM.DD.tif ต่อวัน ไม่ต้องแปลง pentad-to-daily แบบ
    Prelim เดิม) ไม่มี official GEE mirror สำหรับตัวนี้ จึงดึงด้วย ftplib (anonymous login) แล้วอ่าน
    ค่าที่จุดด้วย rasterio แทน (ดู _fetch_chirps_prelim_from_ftp()) waterfall กลายเป็น 3 ชั้น:
    Final (GEE) -> Prelim FTP (ใหม่, เร็วสุดจริง) -> Prelim เดิม (community, GEE, fallback สุดท้าย)
    data_type ที่เป็นไปได้เพิ่ม "prelim_ftp"
  - 2026-07-22 (รอบ 3 — rolling window): เพิ่ม _rolling_window_estimate() สำหรับกรณีสัปดาห์ปฏิทิน
    ISO ของ as_of เองไม่มีข้อมูลจริงเลยสักวัน (0/7 วัน — เกิดขึ้นได้เสมอเพราะ Prelim FTP publish
    เป็นรอบ pentad ทุก 5 วัน ไม่ใช่ทุกวัน ดังนั้นสัปดาห์ที่กำลังดำเนินอยู่มักจะยังไม่มีวันไหนถูก
    ครอบคลุมเลยจนกว่า pentad ถัดไปจะปิดรอบ) แทนที่จะคืน "missing" ทันที จะมองหาวันล่าสุดที่มีข้อมูล
    จริงแล้วรวมฝน 7 วันปฏิทินล่าสุดนับถอยจากวันนั้นแทน (ข้ามขอบเขตสัปดาห์ ISO ได้) ติดแท็ก
    data_type="rolling_estimate" ให้รู้ชัดว่าไม่ใช่ผลรวมของสัปดาห์ปฏิทินจริง พร้อมฟิลด์ผลลัพธ์ใหม่
    is_rolling_estimate (bool) และ rolling_window ({"start":..., "end":...}) ทดสอบยืนยันแล้วบน
    เครื่อง production จริงทั้ง zone_A/zone_B (2026-07-22): ได้ data_type="rolling_estimate" แทน
    "missing" สำเร็จ ไม่มี error
    (ทั้งรอบ 2 และรอบ 3 พัฒนา/ทดสอบใน pipeline/chirps_v3_test_20260722/ ก่อน promote มาทับไฟล์นี้ —
    โฟลเดอร์นั้นยังเก็บสคริปต์วินิจฉัย find_chirps_v3_latest.py และ list_chirps_v3_ftp_dirs.py ไว้
    เป็น reference ถ้าต้องตรวจสอบ latency ของแหล่งข้อมูลซ้ำในอนาคต)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
from scipy.stats import zscore


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TARGET_LAT = 19.05
TARGET_LON = 99.80

# CHIRPS_FINAL_COLLECTION_ID: catalog ทางการของ Google Earth Engine (Version 2.0 Final) —
# https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
# ล่าช้า ~20 วันหลังสิ้นเดือน (รอ gauge data มา unbias ก่อนถึงจะปล่อยเป็น final)
CHIRPS_FINAL_COLLECTION_ID = "UCSB-CHG/CHIRPS/DAILY"

# 2026-07-22 (รอบ 2, เลิกใช้แล้ว): CHIRPS v3.0 DAILY_SAT ผ่าน GEE — ทดสอบจริงแล้วพบว่า lag = 22
# วัน แทบเท่า Final เดิม ไม่ช่วยอะไร เก็บ collection ID ไว้เป็น reference เฉยๆ ไม่ได้ใช้แล้วใน
# waterfall ด้านล่าง (ดู CHIRPS_FTP_* ที่แทนที่ tier นี้แทน)
CHIRPS_V3_REALTIME_COLLECTION_ID_UNUSED = "UCSB-CHC/CHIRPS/V3/DAILY_SAT"

# 2026-07-22 (รอบ 2, ตัวที่ใช้จริง): CHIRPS v3.0 **Preliminary** ตรงจาก CHC FTP เอง (ไม่มี
# official GEE mirror สำหรับตัวนี้) ยืนยัน lag จริง = 7 วัน เร็วกว่า Final ~3 เท่า และไฟล์เป็น
# รายวันจริงอยู่แล้ว โครงสร้าง path บน FTP: {CHIRPS_FTP_BASE}/daily/{prelim|final}/sat/{year}/
# ชื่อไฟล์: chirps-v3.0.prelim.YYYY.MM.DD.tif (หรือ chirps-v3.0.sat.YYYY.MM.DD.tif สำหรับ final —
# ไม่ได้ใช้ final ทาง FTP เพราะ Final ผ่าน GEE ที่มีอยู่แล้วทำงานได้ดีอยู่แล้ว ไม่จำเป็นต้องเปลี่ยน)
CHIRPS_FTP_HOST = "ftp.chc.ucsb.edu"
CHIRPS_FTP_BASE = "/pub/org/chc/products/CHIRPS/v3.0"
CHIRPS_PRELIM_FTP_SUBPATH = "daily/prelim/sat"
CHIRPS_PRELIM_FTP_PREFIX = "chirps-v3.0.prelim"

# CHIRPS_PRELIM_COLLECTION_ID: จาก Awesome GEE Community Catalog (ไม่ใช่ catalog ทางการของ Google)
# เป็นข้อมูล pentad (ราย 5 วัน ไม่ใช่รายวัน) ล่าช้า <5 วัน — ตอนนี้ถูกลดบทบาทเป็น fallback ชั้น
# สุดท้ายเท่านั้น (ใช้เฉพาะวันที่ Prelim FTP ด้านบนก็ยังไม่ครอบคลุม เช่น pentad ล่าสุดยังไม่ปิดรอบ
# หรือ FTP เข้าไม่ได้วันนั้น) แทนที่จะเป็นชั้นเติมช่องว่างหลักเหมือนเดิม เพราะ Prelim FTP เร็วกว่า
# จริง (lag ~7 วัน ยืนยันแล้ว)
# ⚠️ หมายเหตุสำคัญ: asset ID นี้มาจากการค้นคว้า ณ วันที่เขียนโมดูลนี้ (2026-07) — เนื่องจาก
# community catalog อาจย้าย/เปลี่ยน asset ID ได้โดยไม่แจ้งล่วงหน้า (ต่างจาก catalog ทางการที่เสถียรกว่า)
# ให้ตรวจสอบ https://gee-community-catalog.org/projects/chirps_prelim/ ว่า asset ID ยังตรงก่อนใช้งานจริง
# ครั้งแรก ถ้า id เปลี่ยนไปแล้วให้ปรับค่านี้ หรือส่ง prelim_collection_id เข้า get_chirps_feature() เอง
CHIRPS_PRELIM_COLLECTION_ID = "projects/climate-engine-pro/assets/ce-chirps-prelim-pentad"

CHIRPS_BAND_NAME = "precipitation"

# Google Cloud Project ที่เปิดใช้ Earth Engine API แล้ว ใช้เป็นค่า default ของ gee_project ทุก
# ฟังก์ชันในไฟล์นี้ ยังคง override ได้ผ่าน parameter gee_project ถ้าต้องการใช้ project อื่นในอนาคต
DEFAULT_GEE_PROJECT = "maenaruea-water-pipeline"

# ข้อมูลของวันที่เก่ากว่านี้ (วัน) ถือว่าน่าจะมี Final แล้ว (20 วันหลังสิ้นเดือน ~ ปัดขึ้นเป็น 50 วัน
# นับจากวันที่ในสัปดาห์นั้นเพื่อความชัวร์ เพราะ 20 วันนับจาก "สิ้นเดือน" ไม่ใช่จาก "วันนั้น" โดยตรง)
FINAL_DATA_SAFE_LAG_DAYS = 50

# P_eff ต่างสูตรตาม zone (ตรงตาม ZONE_CONFIG ใน feature_schema.md หัวข้อ 3 — บรรทัด 133-136)
ZONE_P_EFF_KIND = {
    "zone_A": "upland",  # rainfed -> P_eff_upland
    "zone_B": "paddy",   # irrigated (rice-dominant) -> P_eff_paddy
}

# lag windows ของ P_mm_week (ตาม add_lag_features(z, "P_mm_week", [1, 2, 4]) บรรทัด 221 ของ
# feature_schema.md — ไม่ใช่ LAG_WINDOWS เต็มชุดที่ใช้กับ target)
P_MM_WEEK_LAG_WEEKS = [1, 2, 4]

SPI_DROUGHT_THRESHOLD = -1.0

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline_log.txt"

# 2026-07-22 (รอบ 2): แคชไฟล์ .tif ที่ดาวน์โหลดจาก CHIRPS FTP ไว้ในเครื่อง กันโหลดซ้ำถ้ารันหลายรอบ
# ในวันเดียวกัน
CHIRPS_FTP_CACHE_DIR = SCRIPT_DIR / "ftp_cache"

# ประวัติ P_mm_week ที่มีอยู่แล้วในเครื่อง (output ของ build_feature_matrix() ตอน train โมเดล) —
# ใช้เป็น baseline หลายปีสำหรับคำนวณ SPI_4 แบบ real-time โดยไม่ต้องดึง CHIRPS ย้อนหลังใหม่ทุกครั้ง
DEFAULT_HISTORICAL_CSV_PATH = SCRIPT_DIR.parent / "Water_demand" / "active" / "ml_features_phase4.csv"


def _get_logger() -> logging.Logger:
    """
    ใช้ logger ชื่อ "data_pipeline" เดียวกับ data_pipeline.py และ mei_feature.py โดยตั้งใจ
    (ดูเหตุผลเต็มใน mei_feature.py._get_logger() — logging.getLogger(ชื่อเดียวกัน) คืน object
    เดียวกันเสมอในโปรเซสเดียวกัน จึงไม่ต้อง import ข้ามโมดูลกันตรงๆ) เขียนลงไฟล์ log ร่วมเดียวกัน
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


def _iso_week_monday(iso_year: int, iso_week: int) -> pd.Timestamp:
    """สร้างวันจันทร์ของ ISO week ที่กำหนด (ตาม pattern เดียวกับที่ใช้ทั้งไฟล์ mei_feature.py
    และ build_feature_matrix() ต้นฉบับ — `pd.to_datetime(..., format="%G-W%V-%u")`)"""
    return pd.to_datetime(f"{iso_year}-W{iso_week:02d}-1", format="%G-W%V-%u")


# ---------------------------------------------------------------------------
# Step 1: โหลดประวัติ P_mm_week หลายปีที่มีอยู่แล้ว (สำหรับ SPI_4 baseline)
# ---------------------------------------------------------------------------
def _load_historical_p_mm_week(csv_path: Path = DEFAULT_HISTORICAL_CSV_PATH) -> pd.DataFrame:
    """
    โหลด P_mm_week ย้อนหลังหลายปีจาก ml_features_phase4.csv (ไฟล์ที่ build_feature_matrix()
    สร้างไว้แล้วตอน train โมเดล — ดู feature_schema.md บรรทัด 240 `ml.to_csv("ml_features_phase4.csv")`)

    ไฟล์นี้มี 2 แถวต่อ (year, week) เพราะแยกตาม zone (zone_A/zone_B) แต่ P_mm_week เป็นค่าเดียวกัน
    ไม่ขึ้นกับ zone (ฝนตกที่พิกัดเดียวกัน ไม่ได้แยกโซน) — ฟังก์ชันนี้จึง dedup เอาแค่ 1 แถวต่อ
    (year, week)

    คืนค่า DataFrame [year, week, P_mm_week] เรียงตาม (year, week) ถ้าไฟล์ไม่มีหรืออ่านไม่ได้
    จะ log warning แล้วคืน DataFrame ว่างเปล่า (ไม่ raise) — get_chirps_feature() จะยังทำงานต่อได้
    แค่ SPI_4 จะเป็นค่า 0.0 ตาม fallback ของสูตรเดิม (len(x)>1 else 0.0) เพราะไม่มีประวัติเทียบ
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.warning(
            "ไม่พบไฟล์ประวัติ CHIRPS ที่ %s (ควรเป็น output ของ build_feature_matrix() ตอน train) "
            "— SPI_4 รอบนี้จะคำนวณได้จากเฉพาะข้อมูลที่ดึงสดใหม่เท่านั้น ถ้ามีน้อยกว่า 2 ปีของสัปดาห์ "
            "เดียวกัน ค่าจะ fallback เป็น 0.0 ตามสูตรเดิม (climatological normal)",
            csv_path,
        )
        return pd.DataFrame(columns=["year", "week", "P_mm_week"])

    try:
        df = pd.read_csv(csv_path, usecols=["year", "week", "P_mm_week"])
    except Exception:
        logger.exception("อ่านไฟล์ประวัติ CHIRPS ที่ %s ไม่สำเร็จ", csv_path)
        return pd.DataFrame(columns=["year", "week", "P_mm_week"])

    df = df.drop_duplicates(subset=["year", "week"]).sort_values(["year", "week"]).reset_index(drop=True)

    years_covered = sorted(df["year"].unique().tolist())
    logger.info(
        "โหลดประวัติ P_mm_week จาก %s สำเร็จ: %d สัปดาห์ ครอบคลุมปี %s "
        "(นี่คือข้อมูล 'เก็บไว้แล้ว' จากตอน train โมเดล ไม่ใช่ข้อมูลสดจาก GEE — ถ้าปีล่าสุดในนี้ "
        "เก่ากว่าปีปัจจุบันมาก SPI_4 baseline จะไม่รวมปีล่าสุดๆ ด้วย ควร backfill CHIRPS ผ่าน GEE "
        "เพิ่มเติมเป็นระยะเพื่อให้ baseline นี้ทันสมัยขึ้น)",
        csv_path, len(df), years_covered,
    )
    return df


# ---------------------------------------------------------------------------
# Step 2: ดึง CHIRPS สดใหม่ผ่าน GEE (final และ prelim เดิม)
# ---------------------------------------------------------------------------
def _fetch_chirps_daily_from_gee(
    start_date: date,
    end_date: date,
    collection_id: str,
    band_name: str = CHIRPS_BAND_NAME,
    lat: float = TARGET_LAT,
    lon: float = TARGET_LON,
    gee_project: Optional[str] = DEFAULT_GEE_PROJECT,
) -> pd.DataFrame:
    """
    ดึงค่าฝนรายวันที่พิกัด (lat, lon) จาก GEE ImageCollection ที่ระบุ ในช่วง [start_date, end_date)
    (ใช้ได้กับทั้ง Final และ Prelim เดิมก่อนแปลง pentad — โครงสร้างข้อมูลที่ GEE คืนมาเหมือนกันหมด
    ไม่ว่า collection ไหน)

    Auth: เรียกผ่าน gee_auth.init_ee(gee_project) — ใช้ Service Account อัตโนมัติถ้าตั้ง env var
    GEE_SERVICE_ACCOUNT_EMAIL/GEE_SERVICE_ACCOUNT_KEY ไว้ครบ (ดู gee_auth.py) ไม่งั้น fallback ไปใช้
    personal credential เหมือนเดิม

    คืนค่า DataFrame [date, precipitation] รายวัน (อาจมีวันที่ขาดถ้า collection ไม่มีภาพวันนั้น)
    ถ้าดึงไม่สำเร็จ (network / auth / collection ผิด) จะ raise exception ออกไปให้ผู้เรียก
    (_fetch_chirps_weekly) จัดการเป็น error isolation อีกที — ฟังก์ชันระดับล่างนี้ไม่ silent-fail เอง
    เพื่อให้ผู้เรียกรู้ได้ว่าดึง final/prelim อันไหนไม่สำเร็จบ้าง
    """
    import ee
    import gee_auth

    gee_auth.init_ee(gee_project)

    point = ee.Geometry.Point([lon, lat])
    collection = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date.isoformat(), end_date.isoformat())
        .select(band_name)
    )

    # getRegion() คืนค่าเป็น time series ที่จุดเดียวแบบ efficient (เรียก server-side ครั้งเดียว
    # ไม่ต้องวน reduceRegion ทีละภาพจากฝั่ง client) — แถวแรกเป็น header
    scale_m = 5500  # ความละเอียด CHIRPS ~0.05° ~ 5.5 กม. (v3 catalog ระบุ 5566 ม. ใกล้เคียงกันมาก
                     # ไม่ต่างกันมีนัยสำคัญสำหรับการดึงค่าจุดเดียวแบบนี้)
    raw = collection.getRegion(point, scale_m).getInfo()

    if not raw or len(raw) < 2:
        return pd.DataFrame(columns=["date", "precipitation"])

    header, rows = raw[0], raw[1:]
    band_idx = header.index(band_name)
    time_idx = header.index("time")

    records = [
        {
            "date": pd.to_datetime(row[time_idx], unit="ms").normalize(),
            "precipitation": float(row[band_idx]) if row[band_idx] is not None else np.nan,
        }
        for row in rows
    ]
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 2026-07-22 (รอบ 2): CHIRPS v3 Preliminary ผ่าน FTP+rasterio
# ---------------------------------------------------------------------------
def _fetch_chirps_prelim_from_ftp(
    start_date: date,
    end_date: date,
    lat: float = TARGET_LAT,
    lon: float = TARGET_LON,
    ftp_host: str = CHIRPS_FTP_HOST,
    ftp_base: str = CHIRPS_FTP_BASE,
    ftp_subpath: str = CHIRPS_PRELIM_FTP_SUBPATH,
    filename_prefix: str = CHIRPS_PRELIM_FTP_PREFIX,
    cache_dir: Path = CHIRPS_FTP_CACHE_DIR,
) -> pd.DataFrame:
    """
    ดาวน์โหลดไฟล์ CHIRPS v3 รายวัน (.tif) ตรงจาก CHC FTP (ftp.chc.ucsb.edu, anonymous login —
    ไม่ต้องมี credential ใดๆ) เฉพาะวันที่อยู่ในช่วง [start_date, end_date) แล้วอ่านค่าฝนที่จุดพิกัด
    (lat, lon) ด้วย rasterio (จุดเดียว ไม่ใช่ zonal average — ตรงกับที่ _fetch_chirps_daily_from_gee()
    ทำผ่าน getRegion(point, scale) อยู่แล้ว ดังนั้นรูปแบบผลลัพธ์ [date, precipitation] เหมือนกันทุก
    ประการ ใช้แทนกันได้ในโครงสร้าง waterfall ของ _fetch_chirps_weekly())

    ไม่ผ่าน Earth Engine เลย — ไม่ต้องมี GEE credentials/network สำหรับ tier นี้ (path นี้ใช้ ftplib
    ธรรมดา) หมายเหตุ CRS: ไฟล์ CHIRPS เป็น GeoTIFF แบบ EPSG:4326 (lat/lon ตรงๆ ไม่ต้อง reproject)
    ตามมาตรฐานของผลิตภัณฑ์นี้ — rasterio .sample() จึงรับพิกัด (lon, lat) ตรงๆ ได้เลย

    ไฟล์ที่ยังไม่ publish บน FTP (เช่นวันที่อยู่ใน pentad ที่ยังไม่ปิดรอบ) จะเจอ error ตอน RETR —
    ถือเป็นเรื่องปกติสำหรับวันล่าสุดที่ยังไม่ออก ข้ามวันนั้นไปเงียบๆ (ไม่ raise) เพื่อให้ waterfall
    ชั้นถัดไป (Prelim เดิม/community) มีโอกาสเติมช่องว่างแทนถ้าจำเป็น

    ไฟล์ที่ดาวน์โหลดสำเร็จแล้วจะถูก cache ไว้ที่ cache_dir ไม่โหลดซ้ำรอบถัดไป (skip-if-cached)
    """
    from ftplib import FTP, error_perm

    import rasterio

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    dates = pd.date_range(start_date, end_date, freq="D", inclusive="left")

    ftp: Optional[FTP] = None
    n_downloaded = 0
    n_cached = 0
    n_unavailable = 0
    records: list[dict] = []

    try:
        for d in dates:
            fname = f"{filename_prefix}.{d.year}.{d.month:02d}.{d.day:02d}.tif"
            local_path = cache_dir / fname

            if local_path.exists():
                n_cached += 1
            else:
                if ftp is None:
                    ftp = FTP(ftp_host, timeout=60)
                    ftp.login()
                    ftp.set_pasv(True)
                remote_path = f"{ftp_base}/{ftp_subpath}/{d.year}/{fname}"
                try:
                    with open(local_path, "wb") as f:
                        ftp.retrbinary(f"RETR {remote_path}", f.write)
                    n_downloaded += 1
                except error_perm:
                    # ไฟล์ยังไม่มีบน FTP (ปกติสำหรับวันล่าสุดที่ pentad ยังไม่ปิดรอบ) -- ข้ามเงียบๆ
                    if local_path.exists():
                        local_path.unlink()
                    n_unavailable += 1
                    continue
                except Exception:
                    logger.exception(
                        "ดาวน์โหลด CHIRPS Prelim FTP ล้มเหลว (ไม่ใช่ 550/ไม่มีไฟล์): %s", remote_path,
                    )
                    if local_path.exists():
                        local_path.unlink()
                    n_unavailable += 1
                    continue

            try:
                with rasterio.open(local_path) as src:
                    sampled = next(src.sample([(lon, lat)]))
                    val = sampled[0] if sampled is not None and len(sampled) > 0 else None
                records.append({
                    "date": pd.Timestamp(d).normalize(),
                    "precipitation": float(val) if val is not None else np.nan,
                })
            except Exception:
                logger.exception("อ่านค่าจากไฟล์ CHIRPS Prelim FTP ไม่สำเร็จ: %s -- ข้ามวันนี้", local_path)
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except Exception:
                pass

    logger.info(
        "CHIRPS Prelim FTP: ช่วง %s ถึง %s -- ดาวน์โหลดใหม่ %d ไฟล์, ใช้แคชเดิม %d ไฟล์, "
        "ยังไม่มีบน FTP %d วัน, อ่านค่าได้จริง %d วัน",
        start_date, end_date, n_downloaded, n_cached, n_unavailable, len(records),
    )

    if not records:
        return pd.DataFrame(columns=["date", "precipitation"])
    return pd.DataFrame(records)


def _pentad_period_length_days(pentad_start: pd.Timestamp) -> int:
    """
    คืนจำนวนวันจริงของ pentad period ที่เริ่มต้นที่ pentad_start (ใช้เฉพาะกับ Prelim เดิม/community
    เท่านั้น — Prelim FTP เป็นรายวันจริงไม่ต้องผ่านฟังก์ชันนี้)

    Pentad มาตรฐาน (ที่ CHIRPS ใช้) แบ่งเดือนเป็น 6 ช่วง: วันที่ 1-5, 6-10, 11-15, 16-20, 21-25,
    26-สิ้นเดือน — 5 ช่วงแรกยาว 5 วันเท่ากันเสมอ มีแค่ช่วงสุดท้าย (เริ่มวันที่ 26) ที่ยาวไม่เท่ากัน
    (3, 5 หรือ 6 วัน ขึ้นกับเดือนนั้นมีกี่วัน) — ใช้แยก precipitation total ของ pentad ให้เป็น
    ค่าเฉลี่ย "ต่อวัน" ที่ถูกต้อง แทนที่จะหารด้วย 5 เสมอซึ่งจะผิดสำหรับ pentad สุดท้ายของเดือน

    ถ้า pentad_start ไม่ตรงกับวันที่ 1/6/11/16/21/26 เลย (แปลว่าสมมติฐานเรื่อง "time = pentad
    start date" ของ asset นี้อาจไม่ตรง — ดู comment ที่ CHIRPS_PRELIM_COLLECTION_ID) จะ log warning
    แล้ว fallback เป็น 5 วัน (ค่ามาตรฐานที่พบบ่อยที่สุด)
    """
    day = pentad_start.day
    if day == 26:
        last_day_of_month = (pentad_start + pd.offsets.MonthEnd(0)).day
        return last_day_of_month - 26 + 1
    if day in (1, 6, 11, 16, 21):
        return 5
    logger.warning(
        "พบวันที่เริ่ม pentad ที่ไม่ตรงกับ schedule มาตรฐาน (1/6/11/16/21/26 ของเดือน): %s "
        "(วันที่ %d) — สมมติฐานเรื่อง time_start ของ %s อาจไม่ตรงตามที่คาดไว้ fallback เป็น 5 วัน",
        pentad_start.date(), day, CHIRPS_PRELIM_COLLECTION_ID,
    )
    return 5


def _expand_pentad_to_daily(pentad_df: pd.DataFrame) -> pd.DataFrame:
    """
    แปลงข้อมูล CHIRPS-Prelim เดิม (community, GEE) ที่เป็น pentad — ค่าฝนสะสม 5 วัน ต่อ 1
    "แถว/ภาพ" ไม่ใช่รายวันจริง — ให้เป็นค่าประมาณ "ต่อวัน" โดยสมมติว่าฝนตกสม่ำเสมอตลอด pentad นั้น
    (หาร total ด้วยจำนวนวันจริงของ pentad นั้นๆ) ใช้เฉพาะกับ Prelim เดิมเท่านั้น — Prelim FTP เป็น
    รายวันจริงอยู่แล้วไม่ต้องผ่านฟังก์ชันนี้

    **ทำไมต้องมีฟังก์ชันนี้ (บั๊กที่พบจากการทดสอบจริงกับ GEE เมื่อ 2026-07-05):** ทดสอบดึง
    CHIRPS-Prelim จริงพบว่า asset ที่ใช้ (`ce-chirps-prelim-pentad`) เป็นข้อมูล **pentad ราย 5 วัน**
    ไม่ใช่รายวัน (ชื่อ asset ก็บอกอยู่แล้ว "pentad" แต่ตอนเขียนโค้ดครั้งแรกพลาดไม่ได้ทำ transform
    ให้ตรงกับความจริงข้อนี้) ถ้าไม่แปลงก่อน โค้ดเดิมจะเอาค่าฝนสะสม 5 วัน (เช่น 24.66 มม.) ไปนับเป็น
    "1 วัน" ปนกับข้อมูลรายวันจริงของ Final ตรงๆ ทำให้ P_mm_week ผิดเพี้ยนไปมาก — ฟังก์ชันนี้แก้โดย
    "กระจาย" ค่า pentad ให้เป็นแถวรายวัน (ค่าเท่ากันทุกวันใน pentad เดียวกัน = total/n_days) ก่อนส่ง
    ต่อไป groupby รายสัปดาห์ตามปกติ

    ⚠️ สมมติฐาน: ค่า "time" ของแต่ละภาพใน asset นี้คือ **วันเริ่มต้น** ของ pentad นั้น (ยืนยันแล้ว
    จากการทดสอบจริง 2026-07-05) ถ้า asset เปลี่ยนหรือ id เปลี่ยนไปในอนาคต ควรตรวจสอบสมมติฐานนี้ซ้ำอีกครั้ง
    """
    if pentad_df.empty:
        return pentad_df

    rows = []
    for _, r in pentad_df.iterrows():
        pentad_start = r["date"]
        n_days = _pentad_period_length_days(pentad_start)
        per_day_value = float(r["precipitation"]) / n_days if n_days > 0 else 0.0
        for i in range(n_days):
            rows.append({"date": pentad_start + pd.Timedelta(days=i), "precipitation": per_day_value})

    return pd.DataFrame(rows)


def _fetch_chirps_weekly(
    start_date: date,
    end_date: date,
    final_collection_id: str = CHIRPS_FINAL_COLLECTION_ID,
    prelim_collection_id: str = CHIRPS_PRELIM_COLLECTION_ID,
    gee_project: Optional[str] = DEFAULT_GEE_PROJECT,
    gee_fetch_fn: Callable[..., pd.DataFrame] = _fetch_chirps_daily_from_gee,
    prelim_ftp_fetch_fn: Callable[..., pd.DataFrame] = _fetch_chirps_prelim_from_ftp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    ดึงฝนรายวัน 3 ชั้นเรียงลำดับ (แม่นสุดก่อน):
      1. CHIRPS Final      (ถึงประมาณ "วันนี้ - 50 วัน" เท่านั้น — ผ่าน GEE, ผ่าน gauge correction)
      2. CHIRPS Prelim FTP (เติมช่วงตั้งแต่ final_cutoff ถึง end_date — ตรงจาก CHC FTP, รายวันจริง,
         lag จริง ~7 วัน)
      3. CHIRPS Prelim เดิม (community pentad ผ่าน GEE — เติมเฉพาะวันที่ FTP ก็ยังไม่มี เช่น
         pentad ปัจจุบันยังไม่ปิดรอบ หรือ FTP เข้าไม่ได้วันนั้น — fallback สุดท้ายเท่านั้น)

    แต่ละชั้นดึงเฉพาะช่วงที่ชั้นก่อนหน้ายังไม่ครอบคลุม (ไม่ดึงซ้ำ) วันไหนมีข้อมูลจากหลายชั้นปนกัน
    (ไม่ควรเกิดถ้า cutoff คำนวณถูก แต่กันเหนียวไว้) ให้ชั้นที่แม่นกว่าชนะเสมอตามลำดับข้างต้น

    gee_fetch_fn: จุด inject สำหรับเทส tier Final/Prelim-community (ค่าเริ่มต้นคือ
    _fetch_chirps_daily_from_gee จริงที่ยิง GEE จริง)
    prelim_ftp_fetch_fn: จุด inject แยกต่างหากสำหรับ tier Prelim FTP (ค่าเริ่มต้นคือ
    _fetch_chirps_prelim_from_ftp จริงที่ยิง FTP จริง — แยกจาก gee_fetch_fn เพราะไม่ใช่ GEE call)
    ทั้งสองให้เทสเรียกด้วยฟังก์ชันปลอมที่คืน DataFrame [date, precipitation] โดยไม่ต้องมี
    credentials หรือยิง network จริงเลย

    คืนค่า tuple (weekly, daily):
      weekly: DataFrame [year, week, P_mm_week, n_days, data_type] โดย data_type ต่อสัปดาห์เป็น:
        "final"      ถ้าทุกวันในสัปดาห์นั้นมาจาก CHIRPS Final
        "prelim"     ถ้ามีอย่างน้อยหนึ่งวันมาจาก CHIRPS-Prelim เดิม (community, ความมั่นใจต่ำสุด)
        "prelim_ftp" ถ้าไม่มี prelim (community) แต่มีอย่างน้อยหนึ่งวันมาจาก CHIRPS Prelim FTP
        "missing"    ถ้าไม่มีข้อมูลเลยทั้งสัปดาห์ (P_mm_week จะเป็น NaN)
      daily: DataFrame [date, precipitation, data_type, year, week] รายวันดิบก่อน groupby — เก็บไว้
        ให้ get_chirps_feature() ใช้ทำ rolling-window fallback ตอนที่สัปดาห์ปฏิทิน ISO ของ as_of
        เองไม่มีข้อมูลจริงเลยสักวัน (ดู _rolling_window_estimate())
    """
    final_cutoff = date.today() - timedelta(days=FINAL_DATA_SAFE_LAG_DAYS)

    frames = []
    covered_dates: set = set()

    # ── ชั้น 1: Final ────────────────────────────────────────────────────────────────────
    final_end = min(end_date, final_cutoff)
    if start_date < final_end:
        try:
            daily_final = gee_fetch_fn(
                start_date=start_date, end_date=final_end,
                collection_id=final_collection_id, gee_project=gee_project,
            )
            daily_final["data_type"] = "final"
            frames.append(daily_final)
            covered_dates |= set(daily_final["date"])
        except Exception:
            logger.exception(
                "ดึง CHIRPS Final จาก GEE (%s) ไม่สำเร็จ ช่วง %s ถึง %s",
                final_collection_id, start_date, final_end,
            )

    # ── ชั้น 2: Prelim FTP — เติมช่วงตั้งแต่ final_cutoff ถึง end_date ──────────────────────
    prelim_ftp_start = max(start_date, final_cutoff)
    if prelim_ftp_start < end_date:
        try:
            daily_prelim_ftp = prelim_ftp_fetch_fn(start_date=prelim_ftp_start, end_date=end_date)
            daily_prelim_ftp = daily_prelim_ftp[~daily_prelim_ftp["date"].isin(covered_dates)]
            daily_prelim_ftp["data_type"] = "prelim_ftp"
            frames.append(daily_prelim_ftp)
            covered_dates |= set(daily_prelim_ftp["date"])
            logger.info(
                "CHIRPS Prelim FTP: ดึงได้ %d วัน ในช่วง %s ถึง %s",
                len(daily_prelim_ftp), prelim_ftp_start, end_date,
            )
        except Exception:
            logger.exception(
                "ดึง CHIRPS Prelim FTP ไม่สำเร็จ ช่วง %s ถึง %s — จะพึ่ง Prelim เดิม (community) "
                "แทนสำหรับช่วงนี้ (ชั้นถัดไป)",
                prelim_ftp_start, end_date,
            )

    # ── ชั้น 3: Prelim เดิม (community) — เติมเฉพาะวันที่ยังไม่มีข้อมูลจากชั้นก่อนหน้าเลย ────
    prelim_start = max(start_date, final_cutoff)
    if prelim_start < end_date:
        try:
            daily_prelim_raw = gee_fetch_fn(
                start_date=prelim_start, end_date=end_date,
                collection_id=prelim_collection_id, gee_project=gee_project,
            )
            daily_prelim = _expand_pentad_to_daily(daily_prelim_raw)
            daily_prelim = daily_prelim[~daily_prelim["date"].isin(covered_dates)]
            daily_prelim["data_type"] = "prelim"
            frames.append(daily_prelim)
            covered_dates |= set(daily_prelim["date"])
        except Exception:
            logger.exception(
                "ดึง CHIRPS-Prelim จาก GEE (%s) ไม่สำเร็จ ช่วง %s ถึง %s — ตรวจสอบว่า asset ID "
                "ยังถูกต้องอยู่หรือไม่ (community catalog อาจย้าย/เปลี่ยน id ได้ ดู comment ที่ "
                "CHIRPS_PRELIM_COLLECTION_ID ด้านบนไฟล์)",
                prelim_collection_id, prelim_start, end_date,
            )

    # เช็ค frames ว่างเฉยๆ ไม่พอ ต้องเช็คหลัง concat ด้วยว่าผลรวมมี 0 แถวจริงหรือไม่ (เช่นทุก tier
    # คืน DataFrame ว่างเปล่าเพราะไม่มีข้อมูลเลย ไม่ใช่เพราะช่วงวันที่ถูกข้าม) เพราะ
    # pd.DataFrame(columns=[...]) ว่างเปล่าจะมี dtype คอลัมน์ "date" เป็น object ไม่ใช่ datetime --
    # เรียก .dt.isocalendar() ด้านล่างจะ raise AttributeError ทันที ถ้าไม่กันไว้ตรงนี้
    daily = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "precipitation", "data_type"])
    if daily.empty:
        empty_weekly = pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])
        empty_daily = pd.DataFrame(columns=["date", "precipitation", "data_type", "year", "week"])
        return empty_weekly, empty_daily

    # ลำดับความน่าเชื่อถือ: final > prelim_ftp > prelim (ใช้ตอน dedup ถ้าวันไหนซ้อนกันข้ามชั้น)
    priority = {"final": 0, "prelim_ftp": 1, "prelim": 2}
    daily["_priority"] = daily["data_type"].map(priority)
    daily = daily.sort_values("_priority").drop_duplicates(subset=["date"], keep="first").drop(columns="_priority")

    daily["precipitation"] = pd.to_numeric(daily["precipitation"], errors="coerce").clip(lower=0)
    daily["year"] = daily["date"].dt.isocalendar().year.astype(int)
    daily["week"] = daily["date"].dt.isocalendar().week.astype(int)

    def _week_data_type(types: pd.Series) -> str:
        # ความมั่นใจของทั้งสัปดาห์ = แหล่งที่ "ด้อยที่สุด" ที่ปรากฏในสัปดาห์นั้น (ให้ผู้ใช้รู้ว่า
        # ต้องระวังแค่ไหน) ลำดับ final (มั่นใจสุด) > prelim_ftp > prelim (มั่นใจน้อยสุด)
        s = set(types)
        if s == {"final"}:
            return "final"
        if "prelim" in s:
            return "prelim"
        if "prelim_ftp" in s:
            return "prelim_ftp"
        return "final"

    weekly = daily.groupby(["year", "week"]).agg(
        P_mm_week=("precipitation", "sum"),
        n_days=("precipitation", "count"),
        data_type=("data_type", _week_data_type),
    ).reset_index()

    return weekly, daily


# ---------------------------------------------------------------------------
# Step 3: รวมประวัติ + ข้อมูลสด, คำนวณ P_eff และ lag
# ---------------------------------------------------------------------------
def _compute_p_eff(p_mm_week: pd.Series, zone: str) -> pd.Series:
    """
    คำนวณ P_eff ตาม zone (สูตรตรงจาก archive notebook + feature_schema.md ZONE_CONFIG):
      zone_A (upland/rainfed)  -> max(0, P_mm_week - 5) * 0.85
      zone_B (paddy/irrigated) -> P_mm_week * 0.8
    """
    kind = ZONE_P_EFF_KIND.get(zone)
    if kind == "upland":
        return np.maximum(0, p_mm_week - 5) * 0.85
    if kind == "paddy":
        return p_mm_week * 0.8
    raise ValueError(f"zone ไม่รู้จัก: {zone!r} (ต้องเป็น 'zone_A' หรือ 'zone_B')")


def _build_combined_weekly_series(
    historical: pd.DataFrame,
    fresh: pd.DataFrame,
) -> pd.DataFrame:
    """
    รวมประวัติ (จากไฟล์ training, ไม่มี data_type/n_days) กับข้อมูลสดจาก GEE/FTP (มี
    data_type/n_days) เป็น series รายสัปดาห์ต่อเนื่องเดียว ถ้าสัปดาห์ไหนมีทั้งสองแหล่ง (ซ้อนทับกัน)
    ให้ข้อมูลสดชนะเสมอ (ประวัติอาจเป็นค่าที่ train ไว้นานแล้ว ข้อมูลสดใหม่กว่าและตรงกับที่จะใช้
    inference จริง)

    คืนค่า DataFrame [year, week, P_mm_week, n_days, data_type] เรียงตาม (year, week) —
    data_type ของแถวที่มาจากประวัติ (ไม่ใช่ fresh) จะเป็น "historical"
    """
    hist = historical.copy()
    hist["n_days"] = 7
    hist["data_type"] = "historical"

    fresh_keys = set(zip(fresh["year"], fresh["week"])) if not fresh.empty else set()
    hist = hist[~hist.apply(lambda r: (r["year"], r["week"]) in fresh_keys, axis=1)]

    # กรอง frame ที่ว่างเปล่าออกก่อน concat (ถ้า fresh ดึงไม่ได้เลยจะเป็น DataFrame ว่าง) — กัน
    # FutureWarning ของ pandas เรื่อง concat กับ frame ว่าง/all-NA และผลลัพธ์ dtype ที่อาจเปลี่ยนไป
    # ในเวอร์ชันหน้า ผลลัพธ์ทางตรรกะเหมือนเดิมทุกกรณี แค่เขียนให้ปลอดภัยกับ pandas เวอร์ชันใหม่ด้วย
    frames = [f for f in (hist, fresh) if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["year", "week"]).reset_index(drop=True)
    return combined


# ---------------------------------------------------------------------------
# Step 4: SPI_4 / drought_flag (z-score เทียบสัปดาห์เดียวกันข้ามปี ตาม feature_schema.md 3.5)
# ---------------------------------------------------------------------------
def _add_spi4_drought_flag(combined: pd.DataFrame) -> pd.DataFrame:
    """
    เพิ่มคอลัมน์ P_4week, SPI_4, drought_flag บน combined weekly series ตามสูตรตรงจาก
    feature_schema.md บรรทัด 267-281 (คัดลอกมาเป๊ะ ไม่ปรับ):

        climate['P_4week'] = climate['P_mm_week'].rolling(4, min_periods=4).sum()
        climate['SPI_4'] = (
            climate.groupby('week')['P_4week']
            .transform(lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0)
            .fillna(0.0)
            .round(3)
        )
        climate['drought_flag'] = (climate['SPI_4'] < -1.0).astype(int)

    หมายเหตุ: groupby('week') คือ group ตามเลขสัปดาห์ ISO (1-52) เฉยๆ ไม่รวม year — จึงเป็นการ
    เทียบ "สัปดาห์เดียวกันข้ามทุกปีที่มีอยู่ใน combined" ตรงตามที่ feature_schema.md อธิบายไว้ว่า
    ต้องมีประวัติหลายปีของสัปดาห์เดียวกันถึงจะคำนวณ SPI_4 ได้อย่างมีความหมาย (ถ้ามีปีเดียว/ไม่มี
    ประวัติเลย จะ fallback เป็น 0.0 ตามสูตรเดิม ไม่ error)
    """
    combined = combined.sort_values(["year", "week"]).reset_index(drop=True)
    combined["P_4week"] = combined["P_mm_week"].rolling(4, min_periods=4).sum()
    combined["SPI_4"] = (
        combined.groupby("week")["P_4week"]
        .transform(lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0)
        .fillna(0.0)
        .round(3)
    )
    combined["drought_flag"] = (combined["SPI_4"] < SPI_DROUGHT_THRESHOLD).astype(int)
    return combined


# ---------------------------------------------------------------------------
# 2026-07-22 (รอบ 3): rolling 7-day window fallback
# ---------------------------------------------------------------------------
def _rolling_window_estimate(
    daily: pd.DataFrame,
    as_of: date,
    window_days: int = 7,
) -> Optional[dict]:
    """
    ใช้เมื่อสัปดาห์ปฏิทิน ISO ของ as_of เอง**ไม่มีข้อมูลจริงเลยสักวัน** (0/7 วัน) — เกิดขึ้นได้เสมอ
    เพราะ Prelim FTP publish เป็นรอบ pentad (ทุก 5 วัน ที่ 2/7/12/17/22/27 ของเดือน) ไม่ใช่ทุกวัน
    ดังนั้นสัปดาห์ที่กำลังดำเนินอยู่มักจะยังไม่มีวันไหนถูกครอบคลุมเลยจนกว่า pentad ถัดไปจะปิดรอบ

    ⚠️ นี่คนละกรณีกับสัปดาห์ที่มีข้อมูล "ไม่ครบ 7 วัน" (เช่น 3/7 วัน) ซึ่งโค้ดเดิมรองรับอยู่แล้วโดย
    ไม่ต้องผ่านฟังก์ชันนี้ (ดู n_days ในผลลัพธ์ปกติ) — ฟังก์ชันนี้ใช้เฉพาะกรณี 0/7 วันเท่านั้น ซึ่ง
    "ผ่อนเกณฑ์ความครบ" ตรงๆ ช่วยไม่ได้ (0 ยังไงก็ไม่พอ) ต้องขยับกรอบเวลาที่มองแทน

    วิธี: มองหาวันล่าสุดที่มีข้อมูลจริง (ไม่เกิน as_of) ใน `daily` แล้วรวมฝนของ window_days วัน
    ปฏิทินล่าสุดนับถอยจากวันนั้น (ข้ามขอบเขตสัปดาห์ ISO ได้ — เป็น "รอบ 7 วันล่าสุด" ไม่ใช่
    "สัปดาห์ปฏิทิน") เป็นค่าประมาณการของสัปดาห์ปัจจุบัน คืน None ถ้า `daily` ที่ส่งเข้ามาไม่มีข้อมูล
    จริงเลยแม้แต่วันเดียว (เช่น ทุก tier ล้มเหลวทั้งหมดจริงๆ ไม่ใช่แค่ latency ปกติ — กรณีนี้ยังต้อง
    คืน "missing" ตามเดิม)
    """
    if daily is None or daily.empty:
        return None

    valid = daily.dropna(subset=["precipitation"]).copy()
    valid = valid[valid["date"].dt.date <= as_of]
    if valid.empty:
        return None

    latest_date = valid["date"].max()
    window_start = latest_date - pd.Timedelta(days=window_days - 1)
    window = valid[(valid["date"] >= window_start) & (valid["date"] <= latest_date)]
    if window.empty:
        return None

    return {
        "p_mm_week": float(window["precipitation"].sum()),
        "n_days": int(len(window)),
        "window_start": window_start.date().isoformat(),
        "window_end": latest_date.date().isoformat(),
    }


# ---------------------------------------------------------------------------
# Step 5: จุดเรียกหลัก — get_chirps_feature()
# ---------------------------------------------------------------------------
def get_chirps_feature(
    zone: str,
    as_of_date: Optional[date] = None,
    weeks_fresh: int = 8,
    gee_project: Optional[str] = DEFAULT_GEE_PROJECT,
    historical_csv_path: Path = DEFAULT_HISTORICAL_CSV_PATH,
    final_collection_id: str = CHIRPS_FINAL_COLLECTION_ID,
    prelim_collection_id: str = CHIRPS_PRELIM_COLLECTION_ID,
    gee_fetch_fn: Callable[..., pd.DataFrame] = _fetch_chirps_daily_from_gee,
    prelim_ftp_fetch_fn: Callable[..., pd.DataFrame] = _fetch_chirps_prelim_from_ftp,
) -> dict:
    """
    จุดเรียกหลักของโมดูลนี้: โหลดประวัติ P_mm_week หลายปี + ดึง CHIRPS สดล่าสุด (weeks_fresh
    สัปดาห์ย้อนหลังจาก as_of_date ผ่าน GEE + FTP) แล้วคำนวณ P_mm_week/P_eff_mm/lag1,2,4/SPI_4/
    drought_flag ของสัปดาห์ as_of_date (ค่าเริ่มต้น = วันนี้) สำหรับ zone ที่ระบุ

    zone: "zone_A" (rainfed/upland) หรือ "zone_B" (irrigated/paddy) — ตรงตาม ZONE_CONFIG ใน
    feature_schema.md กำหนดว่าจะใช้สูตร P_eff ไหน

    ออกแบบให้ "ไม่ raise exception ออกไปนอกฟังก์ชันนี้" (สอดคล้องกับหลักการ error isolation ของ
    data_pipeline.py/mei_feature.py) — ถ้าดึงทุกแหล่งไม่สำเร็จ จะยังคำนวณต่อได้จากประวัติอย่างเดียว
    (แค่ไม่มีสัปดาห์ล่าสุดจริงๆ) และ log ให้เห็นชัดเสมอว่าใช้แหล่งไหน

    คืนค่าเป็น dict:
      {
        "as_of_date": "YYYY-MM-DD", "as_of_year": int, "as_of_week": int, "zone": str,
        "p_mm_week": float | None,
        "p_eff_mm": float | None,
        "p_mm_week_lag1": float | None, "p_mm_week_lag2": float | None, "p_mm_week_lag4": float | None,
        "spi_4": float | None,
        "drought_flag": int | None,
        "data_type": "final" | "prelim_ftp" | "prelim" | "rolling_estimate" | "historical" | "missing" | None,
        "n_days_in_week": int | None,       # จำนวนวันที่มีข้อมูลจริงในสัปดาห์ as_of (7 = ครบสัปดาห์)
        "is_partial_week": bool,            # True ถ้า as_of ยังไม่ใช่วันสุดท้ายของสัปดาห์
        "is_rolling_estimate": bool,        # True เฉพาะตอน data_type == "rolling_estimate"
        "rolling_window": {"start": str, "end": str} | None,  # ช่วงวันที่ใช้จริงถ้าเป็น rolling estimate
        "history_years_available": int,     # จำนวนปีของสัปดาห์เดียวกันที่มีในฐานสำหรับคำนวณ SPI_4
        "historical_source": str,
        "fetch_error": str | None,
      }
    """
    as_of = as_of_date or date.today()
    as_of_ts = pd.Timestamp(as_of)
    as_of_year, as_of_week, _ = as_of_ts.isocalendar()

    result: dict = {
        "as_of_date": as_of.isoformat(),
        "as_of_year": int(as_of_year),
        "as_of_week": int(as_of_week),
        "zone": zone,
        "p_mm_week": None,
        "p_eff_mm": None,
        "p_mm_week_lag1": None,
        "p_mm_week_lag2": None,
        "p_mm_week_lag4": None,
        "spi_4": None,
        "drought_flag": None,
        "data_type": None,
        "n_days_in_week": None,
        "is_partial_week": as_of_ts.dayofweek != 6,  # ISO weekday 7 (อาทิตย์) = สัปดาห์ครบ 7 วันแล้ว
        # true เฉพาะตอนสัปดาห์ as_of เองไม่มีข้อมูลจริงเลย (0/7 วัน) และต้องใช้ rolling 7-day window
        # แทน (ดู _rolling_window_estimate()) — ต่างจาก is_partial_week ที่ true แค่เพราะ as_of ยัง
        # ไม่ใช่วันอาทิตย์ (สัปดาห์ยังไม่จบ)
        "is_rolling_estimate": False,
        "rolling_window": None,
        "history_years_available": 0,
        "historical_source": str(historical_csv_path),
        "fetch_error": None,
    }

    if zone not in ZONE_P_EFF_KIND:
        logger.error("get_chirps_feature() ได้รับ zone ที่ไม่รู้จัก: %r (ต้องเป็น 'zone_A' หรือ 'zone_B')", zone)
        result["fetch_error"] = f"unknown_zone:{zone}"
        return result

    historical = _load_historical_p_mm_week(historical_csv_path)

    monday_of_as_of_week = _iso_week_monday(as_of_year, as_of_week)
    fresh_start = (monday_of_as_of_week - pd.Timedelta(weeks=weeks_fresh)).date()
    fresh_end = as_of + timedelta(days=1)  # GEE filterDate() เป็น exclusive ที่ปลาย ต้อง +1 ให้รวมวันนี้

    try:
        fresh, fresh_daily = _fetch_chirps_weekly(
            start_date=fresh_start, end_date=fresh_end,
            final_collection_id=final_collection_id,
            prelim_collection_id=prelim_collection_id,
            gee_project=gee_project, gee_fetch_fn=gee_fetch_fn,
            prelim_ftp_fetch_fn=prelim_ftp_fetch_fn,
        )
    except Exception as exc:
        logger.exception("ดึง CHIRPS สดล้มเหลวทั้งหมด (ช่วง %s ถึง %s)", fresh_start, fresh_end)
        fresh = pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])
        fresh_daily = pd.DataFrame(columns=["date", "precipitation", "data_type", "year", "week"])
        result["fetch_error"] = str(exc)

    combined = _build_combined_weekly_series(historical, fresh)

    # ถ้าสัปดาห์ as_of เอง (ปฏิทิน ISO Mon-Sun) ไม่มีข้อมูลจริงเลยสักวัน (0/7 วัน) ลอง rolling
    # 7-day window ก่อนยอมแพ้เป็น "missing" — กรณี "ไม่ครบ 7 วัน" (เช่น 3/7) ไม่เข้าเงื่อนไขนี้
    # (already_has_as_of = True อยู่แล้ว เพราะ groupby ของ _fetch_chirps_weekly() สร้างแถวให้แม้มี
    # แค่ 1 วัน)
    already_has_as_of = (
        ((combined["year"] == as_of_year) & (combined["week"] == as_of_week)).any()
        if not combined.empty else False
    )
    if not already_has_as_of:
        rolling = _rolling_window_estimate(fresh_daily, as_of=as_of, window_days=7)
        if rolling is not None:
            rolling_row = pd.DataFrame([{
                "year": int(as_of_year), "week": int(as_of_week),
                "P_mm_week": float(rolling["p_mm_week"]), "n_days": int(rolling["n_days"]),
                "data_type": "rolling_estimate",
            }])
            combined = pd.concat(
                [f for f in (combined, rolling_row) if not f.empty], ignore_index=True
            )
            combined["year"] = combined["year"].astype(int)
            combined["week"] = combined["week"].astype(int)
            combined = combined.sort_values(["year", "week"]).reset_index(drop=True)
            result["is_rolling_estimate"] = True
            result["rolling_window"] = {"start": rolling["window_start"], "end": rolling["window_end"]}
            logger.info(
                "สัปดาห์ %d-W%02d (ปฏิทิน ISO) ไม่มีข้อมูลจริงเลยสักวัน — ใช้ rolling 7-day window "
                "แทน (%s ถึง %s, มีข้อมูลจริง %d วันในช่วงนั้น, รวม %.2f mm) เป็นค่าประมาณการของ "
                "สัปดาห์นี้ (data_type=rolling_estimate — ไม่ใช่ผลรวมของสัปดาห์ปฏิทินจริง)",
                as_of_year, as_of_week, rolling["window_start"], rolling["window_end"],
                rolling["n_days"], rolling["p_mm_week"],
            )
        else:
            logger.warning(
                "สัปดาห์ %d-W%02d ไม่มีข้อมูลจริงเลยสักวัน และไม่มีข้อมูลจริงในช่วง weeks_fresh=%d "
                "สัปดาห์ย้อนหลังเลยแม้แต่วันเดียว (ทุก tier ล้มเหลวจริง ไม่ใช่แค่ latency ปกติ) — "
                "rolling window ช่วยไม่ได้เช่นกัน",
                as_of_year, as_of_week, weeks_fresh,
            )

    if combined.empty:
        logger.error("ไม่มีข้อมูล P_mm_week เลยทั้งประวัติและข้อมูลสด — คำนวณ feature ของ CHIRPS ไม่ได้เลยรอบนี้")
        result["fetch_error"] = result["fetch_error"] or "no_data_available"
        return result

    combined["p_eff_mm"] = _compute_p_eff(combined["P_mm_week"], zone)
    for lag in P_MM_WEEK_LAG_WEEKS:
        combined[f"P_mm_week_lag{lag}"] = combined["P_mm_week"].shift(lag)

    combined = _add_spi4_drought_flag(combined)

    as_of_row = combined[(combined["year"] == as_of_year) & (combined["week"] == as_of_week)]
    history_years_available = int(
        combined.loc[combined["week"] == as_of_week, "year"].nunique()
    )
    result["history_years_available"] = history_years_available

    if as_of_row.empty:
        logger.warning(
            "ไม่มีข้อมูล CHIRPS ของสัปดาห์ as_of เอง (%d-W%02d) เลย (ทั้งประวัติ, Final, Prelim FTP, "
            "Prelim เดิม, และ rolling window) — คืนค่า None สำหรับ feature ของสัปดาห์นี้ (ปีก่อนๆ "
            "ของสัปดาห์เดียวกันมี %d ปีในฐาน)",
            as_of_year, as_of_week, history_years_available,
        )
        result["data_type"] = "missing"
        result["fetch_error"] = result["fetch_error"] or "as_of_week_missing"
        return result

    row = as_of_row.iloc[0]
    result["p_mm_week"] = None if pd.isna(row["P_mm_week"]) else round(float(row["P_mm_week"]), 3)
    result["p_eff_mm"] = None if pd.isna(row["p_eff_mm"]) else round(float(row["p_eff_mm"]), 3)
    result["p_mm_week_lag1"] = None if pd.isna(row["P_mm_week_lag1"]) else round(float(row["P_mm_week_lag1"]), 3)
    result["p_mm_week_lag2"] = None if pd.isna(row["P_mm_week_lag2"]) else round(float(row["P_mm_week_lag2"]), 3)
    result["p_mm_week_lag4"] = None if pd.isna(row["P_mm_week_lag4"]) else round(float(row["P_mm_week_lag4"]), 3)
    result["spi_4"] = float(row["SPI_4"])
    result["drought_flag"] = int(row["drought_flag"])
    result["data_type"] = row["data_type"]
    result["n_days_in_week"] = int(row["n_days"])

    # ── Log ชัดเจนว่า as_of week มาจากแหล่งไหน ────────────────────────────────────────────
    if result["data_type"] == "final":
        logger.info(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — ใช้ข้อมูล FINAL (ผ่าน gauge "
            "correction แล้ว, %d/7 วัน) มั่นใจได้เต็มที่",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
        )
    elif result["data_type"] == "prelim_ftp":
        logger.info(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — ใช้ข้อมูล CHIRPS PRELIM FTP "
            "(ตรงจาก CHC FTP, lag จริง ~7 วัน, %d/7 วัน) ยังไม่ผ่าน gauge correction แบบ Final "
            "แต่เร็วกว่า Prelim เดิม (community) มาก%s",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
            " — และสัปดาห์นี้ยังไม่ครบ 7 วัน (as_of_date อยู่กลางสัปดาห์)" if result["is_partial_week"] else "",
        )
    elif result["data_type"] == "prelim":
        logger.warning(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — ใช้ข้อมูล PRELIMINARY (community "
            "catalog เดิม, pentad) เท่านั้น (%d/7 วัน) — แปลว่า Prelim FTP ก็ยังไม่ครอบคลุมบางวันใน "
            "สัปดาห์นี้ (เช่น pentad ล่าสุดยังไม่ปิดรอบ) ค่าอาจเปลี่ยนแปลงได้เมื่อ final ออกภายหลัง%s",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
            " — และสัปดาห์นี้ยังไม่ครบ 7 วัน (as_of_date อยู่กลางสัปดาห์)" if result["is_partial_week"] else "",
        )
    elif result["data_type"] == "rolling_estimate":
        logger.warning(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — เป็นค่า ROLLING ESTIMATE "
            "(ไม่ใช่ผลรวมของสัปดาห์ปฏิทินจริง เพราะสัปดาห์นี้ไม่มีข้อมูลจริงเลยสักวัน ณ ตอนดึง) "
            "รวมจาก %d วันล่าสุดที่มีข้อมูลจริงในช่วง %s ถึง %s — ใช้ระวังกว่า final/prelim_ftp/"
            "prelim ตามปกติ เหมาะสำหรับ readiness signal เบื้องต้นเท่านั้น",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
            result["rolling_window"]["start"], result["rolling_window"]["end"],
        )
    elif result["data_type"] == "historical":
        logger.info(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — มาจากไฟล์ประวัติที่เก็บไว้แล้ว "
            "(ไม่ใช่ค่าที่ดึงสดจาก GEE รอบนี้ — สัปดาห์นี้เก่ากว่าช่วง weeks_fresh=%d ที่ตั้งไว้)",
            as_of_year, as_of_week, zone, result["p_mm_week"], weeks_fresh,
        )

    if history_years_available <= 1:
        logger.warning(
            "SPI_4 ของสัปดาห์ %d-W%02d คำนวณจากประวัติของสัปดาห์เดียวกันแค่ %d ปี (ต้องการอย่างน้อย "
            "2 ปีขึ้นไปถึงจะมีความหมาย) ค่า SPI_4 จึง fallback เป็น 0.0 (climatological normal) "
            "ตามสูตรเดิม — ควร backfill ประวัติ CHIRPS ผ่าน GEE เพิ่มถ้าต้องการ SPI_4 ที่แม่นขึ้น",
            as_of_year, as_of_week, history_years_available,
        )

    logger.info(
        "CHIRPS feature พร้อมใช้: zone=%s as_of=%d-W%02d, P_mm_week=%s, P_eff_mm=%s, "
        "lag1/2/4=%s/%s/%s, SPI_4=%s, drought_flag=%s, data_type=%s, history_years=%d",
        zone, as_of_year, as_of_week, result["p_mm_week"], result["p_eff_mm"],
        result["p_mm_week_lag1"], result["p_mm_week_lag2"], result["p_mm_week_lag4"],
        result["spi_4"], result["drought_flag"], result["data_type"], history_years_available,
    )

    return result


if __name__ == "__main__":
    # รันไฟล์นี้ตรงๆ เพื่อดึง CHIRPS จริง (GEE + FTP) แล้ว print ผลลัพธ์ — ต้องรันบนเครื่องที่มีทั้ง
    # GEE credentials (Service Account หรือ personal) และอินเทอร์เน็ตออก FTP (ftp.chc.ucsb.edu) ได้
    import json

    for demo_zone in ("zone_A", "zone_B"):
        print(f"--- {demo_zone} ---")
        print(json.dumps(get_chirps_feature(zone=demo_zone), indent=2, ensure_ascii=False))
