"""
chirps_feature.py
==================
โมดูลแยกสำหรับดึงและคำนวณ feature ที่มาจาก CHIRPS rainfall ที่โมเดล Water Demand ต้องการ
(ดู feature_schema.md หัวข้อ 3-4: คอลัมน์ P_mm_week, P_eff_mm, SPI_4, drought_flag)

ที่มา: ต่อยอดจาก archive/Phase3 step2 chirps rainfall.ipynb ซึ่ง comment ไว้เองในโค้ดต้นฉบับว่า
"Method: GEE export (แนะนำ) หรือ rasterio extract จาก GeoTIFF" — โมดูลนี้เลือกใช้ทาง GEE export
ตามที่แนะนำ (ไม่ใช้วิธี download .tif.gz ทีละวันจาก data.chc.ucsb.edu ที่ notebook เดิมใช้เป็น
fallback เพราะเปราะบางกว่ามาก: ต้องยิง request แยกทุกวัน, ไฟล์ 404/เปลี่ยน path บ่อย, ไม่มี retry)

ต่างจากต้นฉบับตรงที่:
  1. ใช้ Earth Engine Python API (`ee`) ดึงค่าฝนตรงที่พิกัด ต.แม่นาเรือ แทนการวนดาวน์โหลด
     GeoTIFF รายวันด้วย requests+rasterio+gzip ทีละไฟล์
  2. แยกแหล่งข้อมูลสองชั้นตาม latency จริงของ CHIRPS (ดู docstring ของ _fetch_chirps_daily_from_gee
     ด้านล่าง): CHIRPS Final (ทางการใน GEE catalog, ล่าช้า ~20 วัน) กับ CHIRPS-Prelim (community
     catalog, ล่าช้า <5 วัน) แล้ว log ให้ชัดเจนว่าค่าของแต่ละสัปดาห์มาจากแหล่งไหน — ต้นฉบับไม่ได้
     แยกแยะเรื่องนี้เลย (ใช้ final อย่างเดียวและไม่บอกว่าข้อมูลล่าสุดอาจยังไม่ผ่านการันตีด้วย gauge)
  3. เพิ่มการโหลด "ประวัติ P_mm_week หลายปี" จากไฟล์ training ที่มีอยู่แล้วในเครื่อง
     (Water_demand/active/ml_features_phase4.csv) เป็น baseline สำหรับคำนวณ SPI_4 แบบ real-time
     แทนที่จะต้องดึง CHIRPS ย้อนหลังทุกปีใหม่ทุกครั้ง (ดู _load_historical_p_mm_week ด้านล่าง)
  4. เพิ่ม error isolation แบบเดียวกับ mei_feature.py/data_pipeline.py — ไม่ raise exception ออก
     นอกฟังก์ชัน get_chirps_feature()

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
    feature_schema.md หัวข้อ 3.5 (บรรทัด 272-278):
        SPI_4 = groupby('week')['P_4week'].transform(
                    lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0
                ).fillna(0.0).round(3)
        drought_flag = (SPI_4 < -1.0).astype(int)
    ผลตามมา (ระบุไว้ในเอกสารเองบรรทัด 289-291): การคำนวณ SPI_4 ของสัปดาห์ปัจจุบันแบบ real-time
    "ต้องมีข้อมูล P_4week ของสัปดาห์เดียวกันจากปีก่อนๆ ครบ ไม่ใช่แค่ปีเดียว" — นี่คือเหตุผลที่โมดูลนี้
    ต้องโหลด "ประวัติ" (historical baseline) ก่อนเสมอ ไม่ใช่แค่ดึง CHIRPS ของสัปดาห์ล่าสุดอย่างเดียว
  - CHIRPS ไม่ได้อัปเดตทันที มี 2 ระดับความสมบูรณ์ (ดู _fetch_chirps_daily_from_gee):
      Prelim: ล่าช้า <5 วัน (อัปเดตทุก pentad คือทุก 5 วัน วันที่ 2,7,12,17,22,27 ของเดือน)
      Final : ล่าช้า ~20 วันหลังจากสิ้นเดือน (รอ station gauge data มา unbias ให้เสร็จก่อน)
    ค่าของสัปดาห์ล่าสุด (as_of week) แทบทุกครั้งจะเป็น prelim หรือยังไม่มีเลย ไม่ใช่ final

สถานะการทดสอบ / TODO ก่อน deploy จริง (อัปเดตล่าสุด 2026-07-05):
  - ทดสอบกับ GEE จริงแล้วสำเร็จทั้ง CHIRPS Final และ CHIRPS-Prelim (รวมถึงแก้บั๊ก pentad-vs-daily
    ที่เจอระหว่างเทสแล้ว — ดู _expand_pentad_to_daily()) ด้วย project 'maenaruea-water-pipeline'
  - ⚠️ TODO (สำคัญ ต้องทำก่อน deploy จริงผ่าน scheduled task/run_pipeline.bat): การทดสอบข้างต้นใช้
    "personal credential" (ee.Authenticate() แบบ interactive, เปิด browser login เอง) ซึ่ง**ไม่
    เหมาะกับการรันแบบ scheduled/unattended** เพราะ token ส่วนตัวอาจหมดอายุ/ต้อง re-authenticate
    เป็นระยะ ทำให้ pipeline ที่รันอัตโนมัติ (เช่นผ่าน Windows Task Scheduler) พังกลางทางได้โดยไม่มี
    คนคอย login ซ้ำให้ ก่อน wire โมดูลนี้เข้ากับ data_pipeline.py จริงต้องเปลี่ยนไปใช้ **Service
    Account** แทน (สร้าง service account ใน GCP project 'maenaruea-water-pipeline' + ออก JSON key
    + ใช้ ee.ServiceAccountCredentials() แทน ee.Initialize(project=...) เฉยๆ ใน
    _fetch_chirps_daily_from_gee() — ดู https://developers.google.com/earth-engine/guides/service_account)
    ตามที่ตกลงกันไว้ว่ายังไม่ต้องตั้งค่าตอนนี้ (รอให้ครบทุกแหล่งข้อมูล ERA5/CHIRPS/MEI พิสูจน์เสร็จ
    ก่อน) — แต่ **ห้ามลืมขั้นตอนนี้ก่อน deploy จริง**
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

# GEE dataset ตามที่ archive notebook แนะนำไว้เอง ("Method: GEE export (แนะนำ)") แทนการดาวน์โหลด
# .tif.gz ทีละวันจาก data.chc.ucsb.edu ที่เปราะบางกว่า
#
# CHIRPS_FINAL_COLLECTION_ID: catalog ทางการของ Google Earth Engine (Version 2.0 Final) —
# https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY
# ล่าช้า ~20 วันหลังสิ้นเดือน (รอ gauge data มา unbias ก่อนถึงจะปล่อยเป็น final)
CHIRPS_FINAL_COLLECTION_ID = "UCSB-CHG/CHIRPS/DAILY"

# CHIRPS_PRELIM_COLLECTION_ID: จาก Awesome GEE Community Catalog (ไม่ใช่ catalog ทางการของ Google)
# เป็นข้อมูล pentad (ราย 5 วัน ไม่ใช่รายวัน) ล่าช้า <5 วัน เหมาะกับสัปดาห์ล่าสุดที่ final ยังไม่ออก
# ⚠️ หมายเหตุสำคัญ: asset ID นี้มาจากการค้นคว้า ณ วันที่เขียนโมดูลนี้ (2026-07) — เนื่องจาก
# community catalog อาจย้าย/เปลี่ยน asset ID ได้โดยไม่แจ้งล่วงหน้า (ต่างจาก catalog ทางการที่เสถียรกว่า)
# ให้ตรวจสอบ https://gee-community-catalog.org/projects/chirps_prelim/ ว่า asset ID ยังตรงก่อนใช้งานจริง
# ครั้งแรก ถ้า id เปลี่ยนไปแล้วให้ปรับค่านี้ หรือส่ง prelim_collection_id เข้า get_chirps_feature() เอง
#
# ✅ ทดสอบกับ GEE จริงแล้ว (2026-07-05, project='maenaruea-water-pipeline'): asset ID นี้ยังใช้ได้
# จริง ดึงข้อมูลได้ (ตัวอย่าง: pentad 26-30 มิ.ย. 2026 = 24.66 มม. รวม 5 วัน) และยืนยันว่าค่า "time"
# ของแต่ละภาพคือวันเริ่มต้นของ pentad จริง (ตรงตามสมมติฐานที่ _expand_pentad_to_daily() ใช้)
# **ต้องแปลงผ่าน _expand_pentad_to_daily() ก่อนใช้เสมอ** เพราะเป็นข้อมูล pentad (สะสม 5 วัน)
# ไม่ใช่รายวัน — ถ้าไม่แปลงก่อนจะเอาค่าฝนสะสม 5 วันไปนับเป็น 1 วันปนกับ Final ผิดเพี้ยนไปมาก
CHIRPS_PRELIM_COLLECTION_ID = "projects/climate-engine-pro/assets/ce-chirps-prelim-pentad"

CHIRPS_BAND_NAME = "precipitation"

# Google Cloud Project ที่เปิดใช้ Earth Engine API แล้ว (ยืนยันแล้วโดยผู้ใช้ว่า
# ee.Initialize(project='maenaruea-water-pipeline') + ee.String('test').getInfo() ทำงานได้จริง
# บนเครื่องนี้ — ใช้ project เดียวกับที่เคยตั้งค่าไว้แล้วสำหรับงาน Sentinel-1/2 crop classification
# ไม่ต้องสร้าง credential ใหม่) ใช้เป็นค่า default ของ gee_project ทุกฟังก์ชันในไฟล์นี้ ยังคง
# override ได้ผ่าน parameter gee_project ถ้าต้องการใช้ project อื่นในอนาคต
#
# 🔴 TODO ก่อน deploy จริง: ทดสอบผ่านทั้งหมด (2026-07-05) ด้วย personal credential
# (ee.Authenticate() แบบ interactive) เท่านั้น — ยังไม่ได้ตั้งค่า Service Account (ตั้งใจเว้นไว้
# ก่อน รอให้ทุกแหล่งข้อมูล ERA5/CHIRPS/MEI พิสูจน์ใช้งานได้ครบก่อนค่อยตั้ง) personal credential
# ไม่เหมาะกับการรันแบบ scheduled/unattended ผ่าน run_pipeline.bat เพราะ token อาจหมดอายุโดยไม่มี
# คน login ซ้ำให้ — ต้องเปลี่ยนเป็น Service Account ก่อน wire โมดูลนี้เข้ากับ data_pipeline.py จริง
# (รายละเอียดวิธีเปลี่ยน ดู TODO ใน docstring ของ _fetch_chirps_daily_from_gee() ด้านล่าง)
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
# Step 2: ดึง CHIRPS สดใหม่ผ่าน GEE (final ก่อน, ตามด้วย prelim สำหรับสัปดาห์ล่าสุดที่ final ไม่ทัน)
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

    ต้องมีการตั้งค่า Earth Engine ไว้ก่อนแล้ว (ครั้งเดียวต่อเครื่อง ไม่ใช่ทุกครั้งที่เรียกฟังก์ชันนี้):
      1. มี Google Cloud Project ที่เปิดใช้ Earth Engine API แล้ว (ส่งชื่อ project เข้ามาทาง
         gee_project — ต้องตั้งค่าเอง ไม่มีค่า default เพราะเป็น project เฉพาะของผู้ใช้)
      2. รัน `ee.Authenticate()` อย่างน้อยหนึ่งครั้งบนเครื่องที่จะรัน pipeline นี้ (เปิด browser
         ให้ login ครั้งแรก)

      ฟังก์ชันนี้เรียกแค่ `ee.Initialize(project=gee_project)` เฉยๆ โดยสมมติว่า credentials
      ถูกตั้งค่าไว้แล้วจากขั้นตอนข้างต้น (ไม่ทำ auth flow เองในนี้ เพราะเป็น one-time environment
      setup ไม่ใช่ per-call operation)

      🔴 TODO ก่อน deploy จริง (ยืนยันแล้ว 2026-07-05 ว่าโค้ดใช้งานได้จริงด้วยวิธีนี้ แต่ยังไม่พร้อม
      สำหรับ production): ตอนนี้ทดสอบผ่านด้วย **personal credential** (ee.Authenticate() แบบ
      interactive) เท่านั้น ซึ่ง**ไม่เหมาะกับการรันแบบ scheduled/unattended** (เช่นผ่าน Windows
      Task Scheduler ตาม run_pipeline.bat) เพราะ OAuth token ส่วนตัวอาจหมดอายุหรือถูก revoke โดยไม่
      มีใครคอย login ซ้ำให้ ทำให้ pipeline พังกลางทางแบบเงียบๆ ได้ ก่อนนำไป deploy จริงต้องเปลี่ยนเป็น
      **service account** แทน (ดู https://developers.google.com/earth-engine/guides/service_account
      — จะเปลี่ยนจาก `ee.Initialize(project=...)` เฉยๆ เป็น
      `ee.Initialize(credentials=ee.ServiceAccountCredentials(email, key_file))`) — ตอนนี้ตั้งใจ
      ยังไม่ทำขั้นตอนนี้ (รอให้ทุกแหล่งข้อมูล ERA5/CHIRPS/MEI พิสูจน์ใช้งานได้ครบก่อน) แต่ห้ามลืม
      ก่อนต่อเข้ากับ pipeline จริง

    คืนค่า DataFrame [date, precipitation] รายวัน (อาจมีวันที่ขาดถ้า collection ไม่มีภาพวันนั้น)
    ถ้าดึงไม่สำเร็จ (network / auth / collection ผิด) จะ raise exception ออกไปให้ผู้เรียก
    (get_chirps_feature) จัดการเป็น error isolation อีกที — ฟังก์ชันระดับล่างนี้ไม่ silent-fail เอง
    เพื่อให้ผู้เรียกรู้ได้ว่าดึง final/prelim อันไหนไม่สำเร็จบ้าง
    """
    import ee

    ee.Initialize(project=gee_project)

    point = ee.Geometry.Point([lon, lat])
    collection = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date.isoformat(), end_date.isoformat())
        .select(band_name)
    )

    # getRegion() คืนค่าเป็น time series ที่จุดเดียวแบบ efficient (เรียก server-side ครั้งเดียว
    # ไม่ต้องวน reduceRegion ทีละภาพจากฝั่ง client) — แถวแรกเป็น header
    scale_m = 5500  # ความละเอียด CHIRPS ~0.05° ~ 5.5 กม. (ตาม comment ใน archive notebook เดิม)
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


def _pentad_period_length_days(pentad_start: pd.Timestamp) -> int:
    """
    คืนจำนวนวันจริงของ pentad period ที่เริ่มต้นที่ pentad_start

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
    แปลงข้อมูล CHIRPS-Prelim ที่ได้จาก GEE (เป็น pentad — ค่าฝนสะสม 5 วัน ต่อ 1 "แถว/ภาพ" ไม่ใช่
    รายวันจริงแม้ว่า _fetch_chirps_daily_from_gee() จะคืนมาในรูปแบบ DataFrame [date, precipitation]
    เดียวกับข้อมูลรายวันของ Final ก็ตาม) ให้เป็นค่าประมาณ "ต่อวัน" โดยสมมติว่าฝนตกสม่ำเสมอตลอด
    pentad นั้น (หาร total ด้วยจำนวนวันจริงของ pentad นั้นๆ)

    **ทำไมต้องมีฟังก์ชันนี้ (บั๊กที่พบจากการทดสอบจริงกับ GEE เมื่อ 2026-07-05):** ทดสอบดึง
    CHIRPS-Prelim จริงพบว่า asset ที่ใช้ (`ce-chirps-prelim-pentad`) เป็นข้อมูล **pentad ราย 5 วัน**
    ไม่ใช่รายวัน (ชื่อ asset ก็บอกอยู่แล้ว "pentad" แต่ตอนเขียนโค้ดครั้งแรกพลาดไม่ได้ทำ transform
    ให้ตรงกับความจริงข้อนี้) ถ้าไม่แปลงก่อน โค้ดเดิมจะเอาค่าฝนสะสม 5 วัน (เช่น 24.66 มม.) ไปนับเป็น
    "1 วัน" ปนกับข้อมูลรายวันจริงของ Final ตรงๆ ทำให้ P_mm_week ผิดเพี้ยนไปมาก (นับจำนวนวันในสัปดาห์
    ผิด และ sum ผิด) — ฟังก์ชันนี้แก้โดย "กระจาย" ค่า pentad ให้เป็นแถวรายวัน (ค่าเท่ากันทุกวันใน
    pentad เดียวกัน = total/n_days) ก่อนส่งต่อไป groupby รายสัปดาห์ตามปกติ ผลคือสัปดาห์ปัจจุบันที่ยัง
    ไม่มี pentad ล่าสุดออก (รอ ~2 วันหลัง pentad จบ) จะแสดงเป็นสัปดาห์ที่ "ข้อมูลไม่ครบ" (n_days < 7)
    อย่างถูกต้อง แทนที่จะเป็น all-or-nothing แบบเดิม

    ⚠️ สมมติฐาน: ค่า "time" ของแต่ละภาพใน asset นี้คือ **วันเริ่มต้น** ของ pentad นั้น (ยืนยันแล้ว
    จากการทดสอบจริง 2026-07-05 — ภาพที่ได้ลงวันที่ 2026-06-26 ตรงกับ pentad 26-30 มิ.ย. พอดี ไม่ใช่
    กลางหรือปลาย pentad) ถ้า asset เปลี่ยนหรือ id เปลี่ยนไปในอนาคต ควรตรวจสอบสมมติฐานนี้ซ้ำอีกครั้ง
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
) -> pd.DataFrame:
    """
    ดึงฝนรายวันจาก CHIRPS Final ก่อนเสมอ (ครอบคลุมได้ถึงประมาณ "วันนี้ - 20 วัน" เท่านั้น เพราะ
    final ต้องรอ gauge data) แล้วเติมช่วงท้าย (วันที่ final ยังไม่ครอบคลุม) ด้วย CHIRPS-Prelim
    แทน จากนั้น resample รวมเป็นรายสัปดาห์ (ISO week) พร้อม tag แหล่งข้อมูลของแต่ละสัปดาห์

    gee_fetch_fn: จุด inject สำหรับเทส (ค่าเริ่มต้นคือ _fetch_chirps_daily_from_gee จริงที่ยิง GEE
    จริง) — ให้เทสเรียกด้วยฟังก์ชันปลอมที่คืน DataFrame [date, precipitation] โดยไม่ต้องมี
    Earth Engine credentials หรือยิง network จริงเลย

    คืนค่า DataFrame [year, week, P_mm_week, n_days, data_type] โดย data_type ต่อสัปดาห์เป็น:
      "final"   ถ้าทุกวันในสัปดาห์นั้นมาจาก CHIRPS Final
      "prelim"  ถ้ามีอย่างน้อยหนึ่งวันมาจาก CHIRPS-Prelim (ผสมหรือทั้งหมด)
      "missing" ถ้าไม่มีข้อมูลเลยทั้งสัปดาห์ (P_mm_week จะเป็น NaN)
    """
    final_cutoff = date.today() - timedelta(days=FINAL_DATA_SAFE_LAG_DAYS)

    frames = []

    # ── Final: ดึงเท่าที่คาดว่าจะมี (ถึง final_cutoff หรือ end_date แล้วแต่อันไหนถึงก่อน) ──────
    final_end = min(end_date, final_cutoff)
    if start_date < final_end:
        try:
            daily_final = gee_fetch_fn(
                start_date=start_date, end_date=final_end,
                collection_id=final_collection_id, gee_project=gee_project,
            )
            daily_final["data_type"] = "final"
            frames.append(daily_final)
        except Exception:
            logger.exception(
                "ดึง CHIRPS Final จาก GEE (%s) ไม่สำเร็จ ช่วง %s ถึง %s",
                final_collection_id, start_date, final_end,
            )

    # ── Prelim: เติมช่วงตั้งแต่ final_cutoff ถึง end_date (ส่วนที่ final คาดว่ายังไม่ครอบคลุม) ──
    # หมายเหตุ: asset ที่ CHIRPS_PRELIM_COLLECTION_ID ชี้ไปเป็นข้อมูล pentad (ราย 5 วัน) ไม่ใช่
    # รายวัน (ยืนยันจากการทดสอบจริงกับ GEE) ต้อง _expand_pentad_to_daily() ก่อนเสมอ ไม่งั้นจะเอา
    # ค่าฝนสะสม 5 วันไปนับเป็น 1 วันปนกับ Final ตรงๆ (ดู docstring ของ _expand_pentad_to_daily())
    prelim_start = max(start_date, final_cutoff)
    if prelim_start < end_date:
        try:
            daily_prelim_raw = gee_fetch_fn(
                start_date=prelim_start, end_date=end_date,
                collection_id=prelim_collection_id, gee_project=gee_project,
            )
            daily_prelim = _expand_pentad_to_daily(daily_prelim_raw)
            daily_prelim["data_type"] = "prelim"
            frames.append(daily_prelim)
        except Exception:
            logger.exception(
                "ดึง CHIRPS-Prelim จาก GEE (%s) ไม่สำเร็จ ช่วง %s ถึง %s — ตรวจสอบว่า asset ID "
                "ยังถูกต้องอยู่หรือไม่ (community catalog อาจย้าย/เปลี่ยน id ได้ ดู comment ที่ "
                "CHIRPS_PRELIM_COLLECTION_ID ด้านบนไฟล์)",
                prelim_collection_id, prelim_start, end_date,
            )

    if not frames:
        return pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])

    daily = pd.concat(frames, ignore_index=True)
    # ถ้าวันไหนมีทั้ง final และ prelim ซ้อนกัน (ไม่ควรเกิดถ้า cutoff คำนวณถูก แต่กันเหนียวไว้)
    # ให้ final ชนะเสมอ (final แม่นกว่าเพราะผ่าน gauge correction แล้ว)
    daily = daily.sort_values("data_type").drop_duplicates(subset=["date"], keep="first")

    daily["precipitation"] = pd.to_numeric(daily["precipitation"], errors="coerce").clip(lower=0)
    daily["year"] = daily["date"].dt.isocalendar().year.astype(int)
    daily["week"] = daily["date"].dt.isocalendar().week.astype(int)

    def _week_data_type(types: pd.Series) -> str:
        return "final" if (types == "final").all() else "prelim"

    weekly = daily.groupby(["year", "week"]).agg(
        P_mm_week=("precipitation", "sum"),
        n_days=("precipitation", "count"),
        data_type=("data_type", _week_data_type),
    ).reset_index()

    return weekly


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
    รวมประวัติ (จากไฟล์ training, ไม่มี data_type/n_days) กับข้อมูลสดจาก GEE (มี data_type/n_days)
    เป็น series รายสัปดาห์ต่อเนื่องเดียว ถ้าสัปดาห์ไหนมีทั้งสองแหล่ง (ซ้อนทับกัน) ให้ข้อมูลสดชนะ
    เสมอ (ประวัติอาจเป็นค่าที่ train ไว้นานแล้ว ข้อมูลสดใหม่กว่าและตรงกับที่จะใช้ inference จริง)

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
) -> dict:
    """
    จุดเรียกหลักของโมดูลนี้: โหลดประวัติ P_mm_week หลายปี + ดึง CHIRPS สดล่าสุด (weeks_fresh
    สัปดาห์ย้อนหลังจาก as_of_date ผ่าน GEE) แล้วคำนวณ P_mm_week/P_eff_mm/lag1,2,4/SPI_4/
    drought_flag ของสัปดาห์ as_of_date (ค่าเริ่มต้น = วันนี้) สำหรับ zone ที่ระบุ

    zone: "zone_A" (rainfed/upland) หรือ "zone_B" (irrigated/paddy) — ตรงตาม ZONE_CONFIG ใน
    feature_schema.md กำหนดว่าจะใช้สูตร P_eff ไหน

    ออกแบบให้ "ไม่ raise exception ออกไปนอกฟังก์ชันนี้" (สอดคล้องกับหลักการ error isolation ของ
    data_pipeline.py/mei_feature.py) — ถ้าดึง GEE ไม่สำเร็จทั้งคู่ (final และ prelim) จะยังคำนวณ
    ต่อได้จากประวัติอย่างเดียว (แค่ไม่มีสัปดาห์ล่าสุดจริงๆ) และ log ให้เห็นชัดเสมอว่าใช้แหล่งไหน

    คืนค่าเป็น dict:
      {
        "as_of_date": "YYYY-MM-DD", "as_of_year": int, "as_of_week": int, "zone": str,
        "p_mm_week": float | None,
        "p_eff_mm": float | None,
        "p_mm_week_lag1": float | None, "p_mm_week_lag2": float | None, "p_mm_week_lag4": float | None,
        "spi_4": float | None,
        "drought_flag": int | None,
        "data_type": "final" | "prelim" | "historical" | "missing" | None,  # แหล่งของสัปดาห์ as_of เอง
        "n_days_in_week": int | None,       # จำนวนวันที่มีข้อมูลจริงในสัปดาห์ as_of (7 = ครบสัปดาห์)
        "is_partial_week": bool,            # True ถ้า as_of ยังไม่ใช่วันสุดท้ายของสัปดาห์ (ข้อมูลจะยังไม่ครบ 7 วัน แม้ final ก็ตาม)
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
        fresh = _fetch_chirps_weekly(
            start_date=fresh_start, end_date=fresh_end,
            final_collection_id=final_collection_id, prelim_collection_id=prelim_collection_id,
            gee_project=gee_project, gee_fetch_fn=gee_fetch_fn,
        )
    except Exception as exc:
        logger.exception("ดึง CHIRPS สดจาก GEE ล้มเหลวทั้งหมด (ช่วง %s ถึง %s)", fresh_start, fresh_end)
        fresh = pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])
        result["fetch_error"] = str(exc)

    combined = _build_combined_weekly_series(historical, fresh)
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
            "ไม่มีข้อมูล CHIRPS ของสัปดาห์ as_of เอง (%d-W%02d) เลย (ทั้งประวัติและสดจาก GEE) — "
            "คืนค่า None สำหรับ feature ของสัปดาห์นี้ (ปีก่อนๆ ของสัปดาห์เดียวกันมี %d ปีในฐาน)",
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

    # ── Log ชัดเจนว่า as_of week เป็น preliminary หรือ final (ข้อ 4 ของ requirement) ──────────
    if result["data_type"] == "final":
        logger.info(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — ใช้ข้อมูล FINAL (ผ่าน gauge "
            "correction แล้ว, %d/7 วัน) มั่นใจได้เต็มที่",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
        )
    elif result["data_type"] == "prelim":
        logger.warning(
            "CHIRPS สัปดาห์ %d-W%02d (zone=%s): P_mm_week=%.2f mm — ใช้ข้อมูล PRELIMINARY เท่านั้น "
            "(%d/7 วัน, ยังไม่ผ่าน gauge correction ที่ CHIRPS Final จะทำ ~20 วันหลังสิ้นเดือน) "
            "ค่าอาจเปลี่ยนแปลงได้เมื่อ final ออกภายหลัง%s",
            as_of_year, as_of_week, zone, result["p_mm_week"], result["n_days_in_week"],
            " — และสัปดาห์นี้ยังไม่ครบ 7 วัน (as_of_date อยู่กลางสัปดาห์)" if result["is_partial_week"] else "",
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
    # รันไฟล์นี้ตรงๆ เพื่อดึง CHIRPS จริงจาก GEE แล้ว print ผลลัพธ์ — ใช้ DEFAULT_GEE_PROJECT
    # ("maenaruea-water-pipeline") ที่ผู้ใช้ยืนยันแล้วว่า ee.Initialize()+ee.String('test').getInfo()
    # ทำงานได้จริงบนเครื่องนี้ (project เดียวกับที่เคยตั้งค่าไว้สำหรับงาน Sentinel SAR/crop classification)
    # ยังไม่เชื่อมกับโมเดล/pipeline หลัก ตามที่ระบุไว้ในขอบเขตงานนี้
    import json

    for demo_zone in ("zone_A", "zone_B"):
        print(f"--- {demo_zone} ---")
        print(json.dumps(get_chirps_feature(zone=demo_zone), indent=2, ensure_ascii=False))
