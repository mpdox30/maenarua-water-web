"""
sar_classification.py
======================
โมดูลแยกสำหรับตรวจภาพ Sentinel-1 ใหม่ + จำแนกชนิดพืชด้วย RF classifier (v3b) ที่ train ไว้แล้ว
ต่อยอดจาก gee_step1_1_sentinel2_dryseason.js / gee_step1_2_sentinel1_sar_weekly.js (Water_demand/)
เป็นการ port ตรรกะจาก GEE JavaScript → Python (earthengine-api) ตาม feature_schema.md หัวข้อ 6

⚠️ หมายเหตุความเชื่อมั่นของ source ที่ port มา (สำคัญ อ่านก่อนใช้งานจริง):
ทั้ง 2 ไฟล์ JS ต้นทางมีคอมเมนต์หัวไฟล์ระบุไว้เองว่าเป็นการ "reconstructed" จากเอกสาร
(4_methodology_guide.docx) โดยเซสชันก่อนหน้า ไม่ใช่สคริปต์ต้นฉบับที่ยืนยันแล้ว 100% — ไฟล์ S1
ยังระบุว่ามี 2 จุดที่ผู้เขียน "ADDED" เอง (DESCENDING-orbit filter, VH/VV_linear band) เพราะเอกสาร
2 ฉบับขัดแย้งกัน จุดที่ลดความเสี่ยงได้: ยืนยันจาก col_medians_v3b_final.pkl (86 features) ว่า
RF classifier ใช้แค่ VV/VH ดิบ 2 แถบ/สัปดาห์เท่านั้น (ดู N_FEAT=6, band_idx=[w*6+0, w*6+1] ใน
feature_schema.md หัวข้อ 6) ไม่ได้ใช้ VH-VV_dB/VH-VV_linear/GLCM contrast/homogeneity ที่เป็นจุด
ไม่แน่นอนในสคริปต์เลย — โมดูลนี้จึงคำนวณเฉพาะ VV/VH weekly mean composite เท่านั้น (ไม่คำนวณ
GLCM/ratio bands ที่ไม่ถูกใช้งานจริง) เพื่อลดความเสี่ยงจากส่วนที่ไม่ยืนยัน

✅ 2026-07-14: check_new_sar_image()/trigger_crop_classification() เปลี่ยนจากเรียก
ee.Initialize(project=...) ตรงๆ เป็นเรียกผ่าน gee_auth.init_ee(gee_project) แล้ว (ดู gee_auth.py
สำหรับวิธีตั้งค่า Service Account เต็ม) จะใช้ Service Account อัตโนมัติถ้าตั้ง env var
GEE_SERVICE_ACCOUNT_EMAIL/GEE_SERVICE_ACCOUNT_KEY ไว้ครบ ไม่งั้น fallback ไปใช้ personal credential
(ee.Authenticate()) เหมือนเดิมอัตโนมัติ ไม่ error — **โค้ดพร้อมรองรับแล้ว แต่ผู้ใช้ยังต้องไปสร้าง
Service Account จริงใน GCP Console เองก่อน** ถึงจะเปลี่ยนโหมดจริง (ยังไม่ได้ทำขั้นตอนนั้น ณ วันที่
เขียนนี้ — เช็คได้จาก log "GEE auth: ใช้ personal credential" ตอนรัน pipeline จริง)

⚠️ สถานะการทดสอบ (2026-07-08): เขียน/ตรวจ logic แล้วแต่ "ยังไม่เคยรันกับ GEE จริง" เพราะ sandbox
นี้ไม่มี credential ที่ authenticate ไว้แล้ว (ee.Initialize() ล้มเหลวด้วย
"Please authorize access to your Earth Engine account" เหมือนที่เจอตอนทดสอบ chirps_feature.py
ในสภาพแวดล้อมเดียวกัน) — ทดสอบได้แค่ส่วนที่ไม่พึ่ง GEE (โหลดโมเดล/scaler/medians + รัน classify
บน synthetic feature vector) ส่วนการดึงภาพจริงจาก GEE ต้องให้ผู้ใช้ทดสอบบนเครื่องจริงที่มี
credential แล้ว (เหมือน CHIRPS/ERA5T)

โครงสร้างข้อมูล (ตาม col_medians_v3b_final.pkl ที่กู้คืนค่าไว้แล้ว — ดู col_medians_v3b_final.json):
  S2_0..S2_13   : Sentinel-2 dry-season composite (Nov-Apr, cloud<10%), 10 band ดิบ (B2,B3,B4,B5,
                  B6,B7,B8,B8A,B11,B12) + 4 spectral index (NDVI,NDWI,NDRE,SAVI) scale 20m
  S1d_0..S1d_31 : Sentinel-1 weekly VV/VH, สัปดาห์ 0-15 ของปี (flat index w*2+band ก่อนแยกเป็น
                  dry_vv=[w*6+0]/dry_vh=[w*6+1] ตาม N_FEAT=6 slicing ดั้งเดิม — ที่นี่คำนวณแค่ VV/VH
                  จึงเก็บเป็น S1d_0..15=VV(week0-15), S1d_16..31=VH(week0-15) ให้ตรงกับลำดับที่
                  col_medians_v3b_final.pkl ยืนยันไว้ (ดู _build_s1_weekly_vvvh_stack docstring)
  S1w_0..S1w_39 : เหมือน S1d แต่สัปดาห์ 16-35 (20 สัปดาห์) → S1w_0..19=VV, S1w_20..39=VH
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("data_pipeline")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# GEE project เดียวกับที่ chirps_feature.py ใช้ (ยืนยันแล้วว่า ee.Initialize() สำเร็จบนเครื่องผู้ใช้)
DEFAULT_GEE_PROJECT = "maenaruea-water-pipeline"

WATER_DEMAND_ACTIVE_DIR = PROJECT_ROOT / "01_data" / "scripts and code" / "Water_demand" / "active"
RF_MODEL_PATH = WATER_DEMAND_ACTIVE_DIR / "rf_model_v3b_final.pkl"
RF_SCALER_PATH = WATER_DEMAND_ACTIVE_DIR / "rf_scaler_v3b_final.pkl"
RF_COL_MEDIANS_PKL_PATH = WATER_DEMAND_ACTIVE_DIR / "col_medians_v3b_final.pkl"
# ไฟล์สำรอง JSON (กู้คืนจาก .pkl เมื่อ 2026-07-08 เพราะ pandas version บนเครื่อง dev/sandbox
# ปัจจุบันโหลด .pkl ต้นฉบับตรงๆ ไม่ได้ — ดู StringDtype(storage='python') incompat กับ
# NDArrayBacked.__setstate__ — ค่าตัวเลขยืนยันแล้วว่าตรงกับที่กู้คืนได้ ไม่ใช่การเดา)
RF_COL_MEDIANS_JSON_PATH = WATER_DEMAND_ACTIVE_DIR / "col_medians_v3b_final.json"

GIS_DIR = PROJECT_ROOT / "01_data" / "gis"
ZONE_A_SHP_PATH = GIS_DIR / "zone_a_rainfed.shp"
ZONE_B_SHP_PATH = GIS_DIR / "zone_b_irrigated.shp"

SAR_LAST_CLASSIFIED_MARKER = GIS_DIR / ".sar_last_classified"

# 2026-07-11 เพิ่ม — สำหรับ export+local-classify architecture (แทน sampleRegions()) ดู docstring
# ของ trigger_crop_classification() สำหรับเหตุผลเต็ม
SAR_RASTER_OUTPUT_DIR = GIS_DIR / "sar_rasters"  # เก็บ crop_map_v3b_<zone>_<year>.tif ที่ classify แล้ว
SAR_EXPORT_CRS = "EPSG:32647"  # native CRS ของ zone shapefile (เมตร) — ให้ scale=20 หมายถึง 20m จริง

# RF classifier class labels (ยืนยันจาก archive/Training Data.ipynb — 'etc' เป็น catch-all รวม
# ยางพารา/ปาล์ม/ยาสูบ/พืชอื่นนอกเป้าหมาย ดู feature_schema.md หัวข้อ 2 บันทึกการแก้ไข 2026-07-08)
CLASS_LABELS = {0: "rice", 1: "corn", 2: "cassava", 3: "longan", 4: "etc"}

# 2026-07-22 เพิ่ม — zone_b_irrigated.shp มี 3 feature/polygon แยกกันจริงตาม sub-catchment ของอ่างที่
# ส่งน้ำ (ยืนยันแล้วจาก load_zone_boundaries() docstring 2026-07-10) คอลัมน์ LU_DES_TH ระบุชื่ออ่าง
# ต่อ polygon ตรงตัว — ใช้ map เป็นชื่อไทยให้ตรงกับ Name_T ใน อ่างเก็บน้ำ.shp/reservoir_inflow.json
RESERVOIR_LABEL_TH = {
    "Mae Na Rua": "อ่างเก็บน้ำแม่นาเรือ",
    "Huay Tham": "อ่างเก็บน้ำห้วยถ้ำ",
    "Huay So": "อ่างเก็บน้ำห้วยโซ้",
}

N_FEAT_ORIGINAL = 6  # จำนวน band/สัปดาห์ในสคริปต์ GEE ต้นฉบับ (VV,VH,VH-VV_dB,VH/VV_lin,contrast,homogeneity)
N_DRY_WEEKS = 16   # week index 0-15
N_WET_WEEKS = 20   # week index 16-35

# Sentinel-2 dry season composite band order (ตรงกับ gee_step1_1_sentinel2_dryseason.js)
S2_RAW_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
S2_INDEX_BANDS = ["NDVI", "NDWI", "NDRE", "SAVI"]  # ต่อท้าย 10 band ดิบ รวม 14

# 2026-07-12 เพิ่ม — ลำดับ band ที่แน่นอนของ full_img composite (S2_0..13 + S1d_0..31 + S1w_0..39
# = 86 band) ตามลำดับที่ s2_img.addBands(s1_img) ต่อกันจริงใน trigger_crop_classification()
# ยืนยันจากการรันจริงบนเครื่อง user (2026-07-12): ee.Image.getDownloadURL() **ไม่เขียน band
# descriptions ลง GeoTIFF เลย** ไม่ว่าจะ single-shot หรือ tile-fallback ก็ตาม (src.descriptions
# เป็น (None,)*86 ตั้งแต่ tile แรกก่อน merge ด้วยซ้ำ ไม่ใช่แค่ merge() ที่ไม่ propagate อย่างที่เคย
# สันนิษฐานไว้ก่อนหน้านี้) จึงพึ่ง src.descriptions ไม่ได้เลยไม่ว่าจะแก้ merge อย่างไร ต้องรู้ลำดับ
# band เองจาก "สิ่งที่เราสร้างเอง" แทน — ตำแหน่ง/index ของ band ใน GeoTIFF (band 1, band 2, ...)
# รอดผ่าน download/merge แน่นอนเสมอ เพราะเป็นโครงสร้างพื้นฐานของไฟล์ (pixel data array) ไม่ใช่
# metadata ที่ optional แบบ description string ดู _classify_raster_local() ที่ใช้ constant นี้เป็น
# แหล่งความจริงหลักแทน src.descriptions (เดิมพึ่ง descriptions เป็นหลัก มี FULL_IMG_BAND_ORDER
# เป็นแค่ fallback — สลับกันแล้วหลังพบว่า descriptions ไม่เคยมีจริงเลย)
FULL_IMG_BAND_ORDER = (
    [f"S2_{i}" for i in range(14)]
    + [f"S1d_{i}" for i in range(N_DRY_WEEKS)]
    + [f"S1d_{i}" for i in range(N_DRY_WEEKS, 2 * N_DRY_WEEKS)]
    + [f"S1w_{i}" for i in range(N_WET_WEEKS)]
    + [f"S1w_{i}" for i in range(N_WET_WEEKS, 2 * N_WET_WEEKS)]
)


# ---------------------------------------------------------------------------
# ส่วนที่ 1: โหลดโมเดล RF + scaler + col_medians
# ---------------------------------------------------------------------------

def _load_col_medians() -> "pd.Series":
    """
    โหลด col_medians_v3b_final — ลองไฟล์ .json สำรองก่อน (เร็ว/ไม่พึ่ง pandas version) แล้วค่อย
    fallback ไปโหลด .pkl ต้นฉบับตรงๆ ถ้ายังไม่มีไฟล์ .json (เช่นบนเครื่องอื่นที่ pandas version ตรง
    กับตอน train เลยไม่มีปัญหา unpickle)
    """
    if RF_COL_MEDIANS_JSON_PATH.exists():
        with open(RF_COL_MEDIANS_JSON_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return pd.Series({k: (np.nan if v is None else v) for k, v in raw.items()})

    import joblib
    return joblib.load(RF_COL_MEDIANS_PKL_PATH)


def load_rf_classifier() -> dict:
    """โหลดโมเดล RF crop classifier (v3b) + scaler + col_medians ทั้งชุด"""
    import joblib

    logger.info("Loading RF crop classifier (v3b) จาก %s", WATER_DEMAND_ACTIVE_DIR)
    model = joblib.load(RF_MODEL_PATH)
    scaler = joblib.load(RF_SCALER_PATH)
    col_medians = _load_col_medians()

    feature_order = list(col_medians.index)
    if len(feature_order) != model.n_features_in_:
        raise ValueError(
            f"col_medians มี {len(feature_order)} feature แต่โมเดล RF ต้องการ "
            f"{model.n_features_in_} — ตรวจสอบว่าไฟล์ตรงกันหรือไม่"
        )

    logger.info(
        "Loaded RF classifier: n_estimators=%d, n_features=%d, classes=%s",
        model.n_estimators, model.n_features_in_, dict(CLASS_LABELS),
    )
    return {
        "model": model,
        "scaler": scaler,
        "col_medians": col_medians,
        "feature_order": feature_order,
    }


# 2026-07-16 ย้ายจาก local variable ในตัว trigger_crop_classification() มาเป็น module-level
# constant -- เหตุผล: data_pipeline.py (Water Demand FAO-56 live-wiring, เฟส 3) ต้องใช้ dict
# เดียวกันนี้เป็นค่า default/fallback ตอนที่ยังไม่มีผล SAR classification ใหม่ (หรือผลเก่าเกินไป)
# เดิมถ้าปล่อยเป็น local variable จะต้อง hardcode ซ้ำเป็นชุดที่ 3 ใน data_pipeline.py (ชุดที่ 1 คือ
# feature_schema.md เอกสาร, ชุดที่ 2 คือที่นี่) เสี่ยงหลุด sync กันถ้าแก้ที่เดียวแล้วลืมอีกที่ -- ย้าย
# มาเป็น constant เดียวที่ data_pipeline.py import ได้ตรงๆ (lazy import sar_classification) แทน
AREA_2020_HA_BY_ZONE = {
    "zone_A": {"rice": 1510.72, "corn": 621.36, "longan": 461.36, "cassava": 0.16, "etc": 156.68},
    "zone_B": {"rice": 282.88, "corn": 215.52, "longan": 170.64, "cassava": 0.32, "etc": 57.88},
}

SAR_MASK_SENTINEL = -9999.0
# 2026-07-11 เปลี่ยนกลยุทธ์: เดิมพยายามใช้ sampleRegions(..., dropNulls=False) แต่ยืนยันแล้วด้วย
# `help(ee.Image.sampleRegions)` จริง (import ee ได้โดยไม่ต้อง ee.Initialize()/credential เลย —
# แค่ inspect signature ของ client library เฉยๆ) ว่า sampleRegions() **ไม่มี** parameter ชื่อ
# dropNulls เลย (มีแค่ collection, properties, scale, projection, tileScale, geometries) — จะ error
# TypeError ทันทีถ้าใส่ dropNulls เข้าไปจริง (dropNulls มีแค่ใน ee.Image.sample() เท่านั้น ยืนยันด้วย
# help(ee.Image.sample) เห็น dropNulls ในนั้นจริง พร้อม docstring บอกชัดว่า sample() default จะทิ้ง
# feature ที่ intersect กับ masked pixel — sampleRegions() ไม่มีทางเลือกให้ override พฤติกรรมนี้เลย)
# แก้ด้วยวิธีอื่นแทน: .unmask(SAR_MASK_SENTINEL) บน image รวมทั้งหมดก่อนส่งเข้า sampleRegions()
# (ดู trigger_crop_classification()) ทำให้ไม่มี pixel ไหน masked อีกต่อไป (ทุก pixel มีค่าตัวเลขจริง
# เสมอ — ค่า sentinel แทนที่ตำแหน่งที่เคย masked) sampleRegions() จึงคืนทุกแถวแน่นอน ไม่มีอะไรถูกทิ้ง
# เลือก -9999 เพราะไกลจากช่วงค่าจริงที่เป็นไปได้ของทุก band มาก: VV/VH เป็น dB ปกติอยู่ -30 ถึง 0,
# S2 raw band เป็น surface reflectance ปกติ 0-10000, S2 index band (NDVI/NDWI/NDRE/SAVI) อยู่ -1 ถึง 1
# (ยืนยันจาก col_medians_v3b_final.json: S2_0=620, S2_10=0.41, S1d/S1w อยู่ -7 ถึง -17 — ไม่มีค่าไหน
# เข้าใกล้ -9999 เลย) ต้องแปลงกลับเป็น NaN ก่อนเข้า fillna(col_medians) ไม่งั้น -9999 จะหลุดเข้าโมเดล
# ตรงๆ ซึ่งเป็นค่าที่ RF ไม่เคยเห็นตอน train เลย ทำให้ผลผิดเพี้ยนรุนแรงกว่าปล่อยเป็น NaN เสียอีก

# 2026-07-12: เคยลองแก้บั๊ก n_pixels_outside_zone=0 ด้วย sentinel ตัวเลข (OUTSIDE_ZONE_SENTINEL=-8888,
# ผ่าน .clip(zone_geom).unmask(OUTSIDE_ZONE_SENTINEL) บนฝั่ง GEE ก่อน export) แทนการพึ่ง GDAL nodata
# metadata ล้วนๆ — แต่ยืนยันจากรันจริงรอบถัดมาบนเครื่อง user (2026-07-13) ว่า **ไม่ได้ผล**:
# n_pixels_outside_zone ยังคงเป็น 0 ทั้ง 2 zone เหมือนเดิม ทั้งที่โค้ด .clip().unmask() ยืนยันแล้วว่า
# อยู่ถูกที่ (อ่านจากไฟล์จริงตรงๆ) และผ่าน synthetic offline test ก่อนหน้านี้ — สาเหตุที่แท้จริงไม่ชัดเจน
# (อาจเป็นพฤติกรรม .clip()/.unmask() ฝั่ง GEE server กับ MultiPolygon ที่ซับซ้อน (zone_A มี 178
# polygon ย่อย) หรือจุดอื่นในสาย download/merge ที่ยังไม่พบ) หลักฐานยืนยันว่าเป็นบั๊กจริง ไม่ใช่แค่
# ข้อสงสัย: n_pixels_valid ที่ classify ได้จริงตรงกับพื้นที่ที่คำนวณจาก bounding box ทั้งกรอบ ไม่ใช่
# พื้นที่ zone จริง (zone_A: n_pixels_valid=301,232 พิกเซล = 12,049 ha เทียบกับพื้นที่จริงจาก
# load_zone_boundaries()["area_m2"] แค่ 3,472.8 ha — คลาดเคลื่อน ~3.47 เท่า; zone_B คลาดเคลื่อน
# ~5.56 เท่า) แทนที่จะพยายามแก้ที่ฝั่ง GEE ต่อ (พิสูจน์แล้วว่าไม่น่าเชื่อถือ 2 รอบติดต่อกันด้วยกลไกคนละแบบ —
# ทั้ง GDAL nodata และตอนนี้ sentinel-via-unmask) เปลี่ยนมาตัดสิน "ในโซนจริงหรือไม่" ที่ฝั่ง Python เอง
# ทั้งหมดแทน ด้วย rasterio.features.rasterize() ทับ geometry จริงจาก load_zone_boundaries()["geom_native"]
# (native CRS EPSG:32647 ตรงกับ SAR_EXPORT_CRS พอดี ไม่ต้อง reproject) บน grid เดียวกับ raster ที่
# ดาวน์โหลดมา — วิธีนี้ไม่ต้องพึ่งพฤติกรรม GEE server-side ใดๆ เลย ตรวจสอบ/ทดสอบได้เต็มที่แบบ offline
# ดู _classify_raster_local() สำหรับ implementation จริง


def classify_feature_matrix(rf: dict, X_raw: "pd.DataFrame") -> np.ndarray:
    """
    รับ DataFrame ที่มีคอลัมน์ตรงกับ rf['feature_order'] (อาจมีค่า sentinel SAR_MASK_SENTINEL
    (-9999) แทนตำแหน่งที่เคย masked ใน GEE — มาจาก full_img.unmask(SAR_MASK_SENTINEL) ก่อน
    sampleRegions() ใน trigger_crop_classification()) แปลง sentinel กลับเป็น NaN ก่อน แล้ว fillna
    ด้วย col_medians (ตาม archive/combined_final_pipeline.py บรรทัด 403-405:
    X_raw.fillna(medians).fillna(0)) scale ด้วย MinMaxScaler แล้ว predict คืน array ของ class id (0-4)
    """
    X_ordered = X_raw.reindex(columns=rf["feature_order"]).astype(float)
    # แปลง sentinel -9999 (ตำแหน่งที่เคย masked ก่อน unmask()) กลับเป็น NaN ก่อน fillna — ถ้าข้ามขั้น
    # นี้ไป -9999 จะถูกมองเป็นค่าจริงแล้วเข้า MinMaxScaler/RF ตรงๆ ผิดเพี้ยนรุนแรงกว่าเดิมมาก
    X_replaced = X_ordered.replace(SAR_MASK_SENTINEL, np.nan)
    X_filled = X_replaced.fillna(rf["col_medians"]).fillna(0.0)
    X_scaled = rf["scaler"].transform(X_filled)
    return rf["model"].predict(X_scaled)


# ---------------------------------------------------------------------------
# ส่วนที่ 2: โหลดขอบเขต zone A/B (สำหรับ zonal sampling)
# ---------------------------------------------------------------------------

def load_zone_boundaries() -> dict:
    """
    โหลด zone_a_rainfed.shp / zone_b_irrigated.shp (EPSG:32647) — คืนค่าเป็น dict ของ geopandas
    GeoDataFrame ต่อ zone พร้อม reproject เป็น EPSG:4326 (ที่ GEE ใช้) ไว้ในคอลัมน์แยก

    2026-07-10 แก้บั๊ก 2 จุดที่พบจากการทดสอบสร้าง ee.Geometry จริง (ก่อนหน้านี้ผ่านแค่ local
    model-loading test แต่ยังไม่เคยทดสอบสร้าง ee.Geometry จาก zone boundary จริง):
      1. zone_B มี 3 feature แยกกัน (Mae Na Rua/Huay Tham/Huay So sub-catchment) — โค้ดเดิมที่จุด
         เรียกใช้งานหยิบแค่ .geometry.iloc[0] (feature แรก) จะได้แค่ ~48% ของพื้นที่ zone_B ทั้งหมด
         (ยืนยันด้วยการเทียบ area) จึงต้อง union_all() รวมทั้ง 3 feature เป็น geometry เดียวก่อน
         เก็บไว้ที่ key "geom_4326" (union_all() = geopandas>=1.0 API, fallback ไป .unary_union
         อัตโนมัติถ้ารุ่นเก่ากว่าไม่มี)
      2. zone_A มี 1 feature เดียวแต่เป็น MultiPolygon ที่มี 178 polygon ย่อย — dissolve ให้เหมือนกัน
         เพื่อความสอดคล้อง (ไม่เปลี่ยนพื้นที่ เพราะมี 1 feature อยู่แล้ว) แต่ทำให้โค้ดฝั่งเรียกใช้ไม่ต้อง
         สนใจว่าแต่ละ zone มีกี่ feature อีกต่อไป — เรียก zdata["geom_4326"] ได้เลยเสมอ
    """
    import geopandas as gpd

    if not ZONE_A_SHP_PATH.exists() or not ZONE_B_SHP_PATH.exists():
        raise FileNotFoundError(
            f"ไม่พบไฟล์ zone boundary: {ZONE_A_SHP_PATH} หรือ {ZONE_B_SHP_PATH}"
        )

    zone_a = gpd.read_file(ZONE_A_SHP_PATH)
    zone_b = gpd.read_file(ZONE_B_SHP_PATH)
    zone_a_4326 = zone_a.to_crs(4326)
    zone_b_4326 = zone_b.to_crs(4326)

    def _dissolve(gdf):
        """รวมทุก feature ของ GeoDataFrame เป็น geometry เดียว (union) — กัน bug 'ใช้แค่ feature แรก'"""
        try:
            return gdf.geometry.union_all()
        except AttributeError:
            return gdf.unary_union  # fallback สำหรับ geopandas รุ่นเก่ากว่า 1.0

    # 2026-07-10 แก้ให้ area_m2 คำนวณจาก geometry ที่ union แล้ว (native CRS EPSG:32647 มีหน่วยเมตร
    # ถูกต้องสำหรับคำนวณพื้นที่ — ไม่ใช้ EPSG:4326/degrees) แทนการ sum พื้นที่ต่อ feature แบบ naive
    # (zone_b.geometry.area.sum()) เพราะ zone_B มี 3 feature ที่ขอบเขตซ้อนทับกันเล็กน้อย (~570 m^2,
    # 0.049% ของพื้นที่รวม — ยืนยันแล้วว่าไม่ใช่บั๊ก แค่พื้นที่ sub-catchment ที่ digitize มาขอบเกยกันนิดหน่อย)
    # ทำให้ naive sum นับพื้นที่ทับซ้อนซ้ำ ค่า area_m2 ควรตรงกับ geometry จริงที่ถูกส่งเข้า GEE (geom_4326)
    zone_a_geom_native = _dissolve(zone_a)
    zone_b_geom_native = _dissolve(zone_b)

    return {
        "zone_A": {
            "gdf": zone_a,
            "gdf_4326": zone_a_4326,
            "geom_4326": _dissolve(zone_a_4326),
            # 2026-07-13 เพิ่ม — geometry ที่ dissolve แล้วใน native CRS (EPSG:32647 ตรงกับ
            # SAR_EXPORT_CRS) เก็บไว้ใช้ rasterize() ทับ raster ที่ดาวน์โหลดมาโดยตรงใน
            # _classify_raster_local() (ดู OUTSIDE_ZONE_SENTINEL comment ด้านบน sar_classification.py
            # สำหรับเหตุผลว่าทำไมเลิกพึ่ง GEE .clip()/.unmask() แล้ว)
            "geom_native": zone_a_geom_native,
            "area_m2": float(zone_a_geom_native.area),
        },
        "zone_B": {
            "gdf": zone_b,
            "gdf_4326": zone_b_4326,
            "geom_4326": _dissolve(zone_b_4326),
            "geom_native": zone_b_geom_native,
            "area_m2": float(zone_b_geom_native.area),
        },
    }


def _to_ee_geometry(shapely_geom) -> Any:
    """
    แปลง shapely geometry (Polygon หรือ MultiPolygon) -> ee.Geometry ด้วย GeoJSON-like
    mapping() แทนการเรียก ee.Geometry.MultiPolygon(coords)/ee.Geometry.Polygon(coords) ตรงๆ
    ด้วยมือ

    เหตุผล (ยืนยันแล้วด้วยการทดสอบสร้าง client-side object เปล่าๆ — error ทันทีโดยไม่ต้องพึ่ง
    ee.Initialize()/GEE server เลย): วิธีเดิม `ee.Geometry.MultiPolygon([list(geom.__geo_interface__
    ["coordinates"])])` ห่อ coordinates ด้วย list ซ้ำอีกชั้นหนึ่งเกินความจำเป็น (__geo_interface__
    ของ MultiPolygon คืนค่าที่เป็น "list ของ polygon" อยู่แล้ว ตรงกับ signature ของ
    ee.Geometry.MultiPolygon(coordinates) พอดี ไม่ต้องห่อ [ ] เพิ่ม) ทำให้ได้ EEException:
    "Invalid geometry" ทุกครั้ง — ไม่ว่าจะ authenticate ไว้ถูกต้องแค่ไหนก็ตาม เพราะเป็นปัญหา
    โครงสร้าง array ไม่ใช่ปัญหา auth

    ee.Geometry(mapping(shapely_geom)) แก้ปัญหานี้เพราะรับ GeoJSON-like dict ตรงๆ (มี "type" ระบุ
    Polygon/MultiPolygon ในตัวเอง) แล้ว auto-detect เอง ไม่ต้องเดา/ระบุ type หรือ nesting เอง —
    ใช้ pattern เดียวกันได้ทั้ง zone_A (MultiPolygon) และ zone_B หลัง union_all() (MultiPolygon
    เช่นกัน) โดยไม่ต้องแยก branch ตาม geom_type
    """
    import ee
    from shapely.geometry import mapping

    return ee.Geometry(mapping(shapely_geom))


# ---------------------------------------------------------------------------
# ส่วนที่ 3: GEE composite building (port จาก gee_step1_1 / gee_step1_2)
# ---------------------------------------------------------------------------

def _build_s2_dry_season_composite(aoi_geom, year: int):
    """
    Port ตรงจาก gee_step1_1_sentinel2_dryseason.js — median composite ของ Sentinel-2 SR
    ช่วง พ.ย.(ปีก่อนหน้า)-เม.ย.(ปีนี้), cloud<10%, 10 band ดิบ + 4 spectral index = 14 bands
    ตั้งชื่อ band เป็น S2_0..S2_13 ให้ตรงลำดับกับ col_medians ที่กู้คืนไว้
    """
    import ee

    start = f"{year - 1}-11-01"
    end = f"{year}-04-30"

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi_geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10))
    )

    composite = s2.median().select(S2_RAW_BANDS)

    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndwi = composite.normalizedDifference(["B3", "B8"]).rename("NDWI")
    ndre = composite.normalizedDifference(["B8A", "B5"]).rename("NDRE")
    savi = composite.expression(
        "1.5*(NIR-RED)/(NIR+RED+0.5)",
        {"NIR": composite.select("B8"), "RED": composite.select("B4")},
    ).rename("SAVI")

    s2_final = composite.addBands([ndvi, ndwi, ndre, savi])
    new_names = [f"S2_{i}" for i in range(14)]
    return s2_final.rename(new_names)


def _get_s1_filtered_collection(aoi_geom, year: int):
    """
    filter chain ของ Sentinel-1 GRD ที่ใช้ทั้งใน _build_s1_weekly_vvvh_stack() และ
    _get_weekly_image_counts() (แยกออกมาเป็นฟังก์ชันเดียวเพื่อไม่ให้ filter 2 จุดเพี้ยนจากกัน)
    IW + DESCENDING + ต้องมี VV,VH + filterDate ทั้งปี (year-01-01 ถึง year-12-31)
    """
    import ee

    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi_geom)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .select(["VV", "VH"])
    )


def _weekly_mean_vvvh_or_masked(s1_coll, start, end):
    """
    2026-07-10 เพิ่ม — แก้บั๊กที่ยืนยันแล้วจาก test_s1_weekly_windows_debug.py: บางสัปดาห์ (36
    หน้าต่าง 7 วันคงที่นับจาก 1 ม.ค.) ไม่มีภาพ Sentinel-1 ผ่าน filter เลย (revisit cycle ของ S1
    ที่ล็อก DESCENDING อย่างเดียว ~12 วัน ไม่ตรงกับขอบเขตสัปดาห์ปฏิทิน 7 วันคงที่ทุกสัปดาห์) ทำให้
    week_coll.mean() ได้ Image 0 band แล้ว .select('VV') error "Pattern 'VV' did not match any
    bands" ทันทีที่ถูก evaluate

    แก้ด้วย ee.Algorithms.If() (server-side conditional): ถ้าสัปดาห์นั้นมีภาพ (>0) ใช้ .mean() จริง
    ถ้าไม่มีภาพเลย ใช้ ee.Image.constant([0,0]).rename(['VV','VH']).selfMask() แทน (ได้ Image ที่มี
    band ชื่อ VV,VH ครบ แต่ mask ทุก pixel ทั้ง 2 band — เป็น "no-data" ไม่ใช่ 0 จริง) ผลคือ
    sampleRegions() ที่ปลายทางจะได้ null แทนการ error ทำให้ NaN ไหลเข้า
    classify_feature_matrix()'s fillna(col_medians).fillna(0) ได้ตามสถาปัตยกรรมเดิม —
    ยืนยันแล้วว่าเป็นสถาปัตยกรรมที่ต้นฉบับตั้งใจไว้จริง (ดู Retrain3.ipynb cell 8: X_raw.fillna
    (medians).fillna(0), และ cell 16 inference: df.fillna(medians).fillna(0) — ใช้ pattern เดียวกัน
    ทั้งตอน train และตอน generate crop_map_v3b_2020..2023.tif ของจริง)

    หมายเหตุ: ee.Algorithms.If() ประเมินแบบ lazy (ไม่ execute ทั้ง 2 branch ตอนสร้าง object) —
    branch ที่ไม่ถูกเลือกจะไม่ error แม้จะมี .select('VV') อยู่ในนั้นก็ตาม เพราะ GEE ประเมินเฉพาะ
    branch ที่ condition เลือกจริงตอน request ไปยัง server เท่านั้น
    """
    import ee

    week_coll = s1_coll.filterDate(start, end)
    empty_masked = ee.Image.constant([0, 0]).rename(["VV", "VH"]).selfMask()
    real_mean = week_coll.mean().select(["VV", "VH"])
    return ee.Image(ee.Algorithms.If(week_coll.size().gt(0), real_mean, empty_masked))


def _get_weekly_image_counts(aoi_geom, year: int) -> list:
    """
    2026-07-10 เพิ่ม — คืน list ของ {"week": w, "n_images": n} สำหรับสัปดาห์ 0..35 (single
    round-trip ผ่าน ee.List.map() + .getInfo() ครั้งเดียว แทนการ .getInfo() ทีละสัปดาห์ 36 ครั้ง)
    ใช้สำหรับ diagnostic/reporting ใน trigger_crop_classification() (result["sar_data_quality"])
    ไม่กระทบ logic การสร้าง composite จริงใน _build_s1_weekly_vvvh_stack()
    """
    import ee

    s1_coll = _get_s1_filtered_collection(aoi_geom, year)
    n_weeks = N_DRY_WEEKS + N_WET_WEEKS
    weeks_list = ee.List.sequence(0, n_weeks - 1)

    def _count_for_week(w):
        w = ee.Number(w)
        start = ee.Date(f"{year}-01-01").advance(w.multiply(7), "day")
        end = start.advance(7, "day")
        n = s1_coll.filterDate(start, end).size()
        return ee.Dictionary({"week": w, "n_images": n})

    return weeks_list.map(_count_for_week).getInfo()


def _week_to_band_names(w: int) -> tuple:
    """
    คืนชื่อ band (VV, VH) ของสัปดาห์ w (0..35) ให้ตรงกับ naming convention ที่ col_medians ใช้จริง
    (ยืนยันจาก _build_s1_weekly_vvvh_stack()/col_medians_v3b_final.json): สัปดาห์ dry (w<16) ->
    S1d_{w}=VV, S1d_{w+16}=VH; สัปดาห์ wet (w>=16) -> S1w_{w-16}=VV, S1w_{w-16+20}=VH
    """
    if w < N_DRY_WEEKS:
        return f"S1d_{w}", f"S1d_{w + N_DRY_WEEKS}"
    wet_idx = w - N_DRY_WEEKS
    return f"S1w_{wet_idx}", f"S1w_{wet_idx + N_WET_WEEKS}"


# ยืนยันจาก col_medians_v3b_final.json (2026-07-10): นับ null โดยตรง — 14/32 S1d band (43.8%) และ
# 16/40 S1w band (40.0%) มี median=null คือ "ว่างทั้งคอลัมน์ตลอดทั้ง training set" (6,347 จุด)
# ตั้งแต่ตอน train แล้ว รวม 30/72 = 41.7% ของ SAR weekly feature ทั้งหมด — นี่คือ baseline สำหรับ
# เทียบกับสัดส่วน empty-week ที่เจอตอน inference จริง (ดู _assess_sar_data_quality())
TRAINING_NULL_BAND_COUNT = 30
TRAINING_TOTAL_SAR_BAND_COUNT = 72  # 32 (S1d) + 40 (S1w)


def _assess_sar_data_quality(weekly_counts: list, col_medians: "pd.Series") -> dict:
    """
    2026-07-10 เพิ่ม — ประเมินว่าสัดส่วนสัปดาห์ว่าง (0 ภาพ) ตอน inference สูงผิดปกติเทียบกับที่
    โมเดลเคยเจอตอน train ไหม (ยืนยันแล้วจาก Retrain3.ipynb + col_medians_v3b_final.json ว่า
    41.7% ของ SAR band ว่างทั้งคอลัมน์ตั้งแต่ train แล้ว — ไม่ใช่สถานการณ์ใหม่ แต่สัดส่วนที่สูงกว่า
    นี้มากอาจกระทบคุณภาพ classify ได้ ควรรายงานให้เห็นชัดก่อนเชื่อผลลัพธ์)

    แยกสัปดาห์ว่างเป็น 2 กลุ่ม:
      - weeks_matching_training_gap: band คู่กัน (VV,VH) มี median=null ตอน train อยู่แล้ว —
        โมเดลไม่เคยเรียนรู้จาก band นี้เลย (เป็น constant 0 ตลอด training) ความเสี่ยงต่ำ
      - weeks_diverging_from_training: band คู่กันมี median จริง (ไม่ null) ตอน train — แปลว่า
        โมเดลเคยเรียนรู้จากข้อมูลจริงของ band นี้ แต่ตอนนี้ถูกเซ็ตเป็น 0 แทนเพราะสัปดาห์นี้ไม่มีภาพ
        — เสี่ยงสูญเสียข้อมูลที่โมเดลเคยพึ่งพาจริง ควรระวังเป็นพิเศษ
    """
    empty_weeks = [c["week"] for c in weekly_counts if c["n_images"] == 0]
    n_total_weeks = len(weekly_counts)
    n_empty = len(empty_weeks)

    matches_training_gap = []
    diverges_from_training = []
    for w in empty_weeks:
        vv_band, vh_band = _week_to_band_names(w)
        vv_median = col_medians.get(vv_band)
        vh_median = col_medians.get(vh_band)
        vv_was_null = pd.isna(vv_median)
        vh_was_null = pd.isna(vh_median)
        if vv_was_null and vh_was_null:
            matches_training_gap.append(w)
        else:
            diverges_from_training.append(w)

    training_baseline_pct = round(
        TRAINING_NULL_BAND_COUNT / TRAINING_TOTAL_SAR_BAND_COUNT * 100, 1
    )
    empty_week_pct = round(n_empty / n_total_weeks * 100, 1) if n_total_weeks else None

    if diverges_from_training:
        risk_note = (
            f"[ควรระวัง] {len(diverges_from_training)}/{n_empty} สัปดาห์ว่างตรงกับ band ที่ตอน "
            f"train มี median จริง (ไม่ null) — โมเดลเคยเรียนรู้จากข้อมูลจริงของ band เหล่านี้ "
            f"แต่ตอนนี้ถูกเซ็ตเป็น 0 แทน (สัปดาห์: {diverges_from_training}) เสี่ยงกระทบคุณภาพ "
            f"classify มากกว่าแค่ 'เข้าเงื่อนไข NaN ที่ระบบรองรับอยู่แล้ว'"
        )
    elif n_empty > 0:
        risk_note = (
            f"สัปดาห์ว่างทั้งหมด ({n_empty} สัปดาห์: {empty_weeks}) ตรงกับ band ที่ตอน train ก็ "
            f"median=null อยู่แล้ว (โมเดลไม่เคยเรียนรู้จาก band เหล่านี้เลย เป็น constant 0 ตลอด "
            f"training) — ความเสี่ยงต่ำ ตรงกับ gap แบบเดียวกับที่ต้นฉบับเจอมาก่อนแล้ว"
        )
    else:
        risk_note = "ไม่มีสัปดาห์ว่างเลยในรอบนี้"

    return {
        "n_total_weeks": n_total_weeks,
        "n_empty_weeks": n_empty,
        "empty_week_pct": empty_week_pct,
        "empty_week_indices": empty_weeks,
        "training_baseline_null_band_pct": training_baseline_pct,
        "weeks_matching_training_gap": matches_training_gap,
        "weeks_diverging_from_training": diverges_from_training,
        "risk_note": risk_note,
    }


def _build_s1_weekly_vvvh_stack(aoi_geom, year: int):
    """
    Port แบบย่อจาก gee_step1_2_sentinel1_sar_weekly.js — คำนวณเฉพาะ VV/VH weekly mean composite
    (ไม่คำนวณ VH-VV_dB/VH-VV_linear/GLCM contrast/homogeneity เพราะยืนยันแล้วว่า RF classifier
    (col_medians 86 features) ไม่ได้ใช้ 4 band ที่เหลือนี้เลย — ดู docstring หัวไฟล์)

    สัปดาห์ 0-35 ของปี (36 สัปดาห์ = 16 "dry" + 20 "wet" ตาม slicing เดิมใน feature_schema.md
    หัวข้อ 6) — คืน image 72 bands: S1d_0..15=VV(wk0-15), S1d_16..31=VH(wk0-15),
    S1w_0..19=VV(wk16-35), S1w_20..39=VH(wk16-35)

    2026-07-10 แก้บั๊ก: สัปดาห์ที่ไม่มีภาพผ่าน filter เลย (0 ภาพ) ตอนนี้ใช้
    _weekly_mean_vvvh_or_masked() แทน .mean() ตรงๆ — ได้ band VV/VH แบบ masked (null ตอน sample)
    แทนที่จะ error "Pattern 'VV' did not match any bands" (ดู docstring ของฟังก์ชันนั้น)
    """
    import ee

    s1 = _get_s1_filtered_collection(aoi_geom, year)

    weekly_bands = []
    weekly_names = []
    for w in range(N_DRY_WEEKS + N_WET_WEEKS):  # 0..35
        start = ee.Date(f"{year}-01-01").advance(w * 7, "day")
        end = start.advance(7, "day")
        img = _weekly_mean_vvvh_or_masked(s1, start, end)
        # 2026-07-10 แก้: GEE band name ต้องขึ้นต้นด้วยตัวอักษร (a-z, A-Z) เท่านั้น ห้ามขึ้นต้นด้วย
        # "_" — เดิมใช้ f"_w{w}_VV"/f"_w{w}_VH" (ขึ้นต้นด้วย underscore ผิดกฎ) เปลี่ยนเป็น
        # f"w{w}_VV"/f"w{w}_VH" แทน (ขึ้นต้นด้วยตัวอักษร "w" ถูกต้อง) — ชื่อพวกนี้เป็นชื่อชั่วคราว
        # ภายในฟังก์ชันนี้เท่านั้น (ใช้แค่ระหว่าง .select()/.rename() ก่อนจะ rename รอบสุดท้ายเป็น
        # S1d_X/S1w_X ที่ตรงกับ col_medians) ไม่กระทบ _week_to_band_names()/col_medians เลย เพราะ
        # ฟังก์ชันนั้น map กับชื่อ S1d_X/S1w_X ตัวสุดท้ายเท่านั้น ไม่เคยอ้างอิงชื่อชั่วคราวนี้
        weekly_bands.append(img.select("VV").rename(f"w{w}_VV"))
        weekly_bands.append(img.select("VH").rename(f"w{w}_VH"))

    stacked = ee.Image.cat(weekly_bands)

    # จัดลำดับใหม่ตาม N_FEAT slicing เดิม: dry_vv(0-15) + dry_vh(0-15) + wet_vv(16-35) + wet_vh(16-35)
    dry_vv = [f"w{w}_VV" for w in range(0, N_DRY_WEEKS)]
    dry_vh = [f"w{w}_VH" for w in range(0, N_DRY_WEEKS)]
    wet_vv = [f"w{w}_VV" for w in range(N_DRY_WEEKS, N_DRY_WEEKS + N_WET_WEEKS)]
    wet_vh = [f"w{w}_VH" for w in range(N_DRY_WEEKS, N_DRY_WEEKS + N_WET_WEEKS)]

    ordered = stacked.select(dry_vv + dry_vh + wet_vv + wet_vh)
    new_names = (
        [f"S1d_{i}" for i in range(N_DRY_WEEKS)]
        + [f"S1d_{i}" for i in range(N_DRY_WEEKS, 2 * N_DRY_WEEKS)]
        + [f"S1w_{i}" for i in range(N_WET_WEEKS)]
        + [f"S1w_{i}" for i in range(N_WET_WEEKS, 2 * N_WET_WEEKS)]
    )
    return ordered.rename(new_names)


# ---------------------------------------------------------------------------
# ส่วนที่ 3.5: Export image เป็น GeoTIFF + classify แบบ local raster (แทน sampleRegions())
# ---------------------------------------------------------------------------
#
# 2026-07-11 เพิ่มทั้งหมด — เปลี่ยนสถาปัตยกรรมจาก synchronous sampleRegions().getInfo() เป็น
# "export ภาพเต็ม zone -> classify ทุก pixel แบบ local" ให้ตรงกับที่ Retrain3.ipynb cell 16 (ซึ่ง
# generate crop_map_v3b_2020..2023.tif ของจริง) ทำจริง — ยืนยันด้วยการอ่าน cell 16 ตรงๆ (ไม่มี
# ee.* เลยทั้ง notebook — 0 hit จากการ grep 'import ee'/'ee.Image'/'ee.Initialize' ทุก cell):
# อ่าน S2_drySeason_composite_{year}.tif/S1_fullYear_weekly_{year}.tif ที่ export จาก GEE ไว้ก่อน
# แล้วด้วย rasterio ล้วนๆ, reshape ทั้ง raster เป็น (n_pixel, n_feature), fillna(medians).fillna(0),
# rf.predict() ทุก pixel ในเครื่อง local — ไม่เคยผ่าน sampleRegions()/sample() เลยทั้งตอน train
# (6,347 จุดมาจาก rasterio.sample.sample_gen() บน TIF ท้องถิ่น ไม่ใช่ GEE sampling) และตอน
# generate crop map จริง เหตุผลที่ต้องแก้: sampleRegions() บน zone_A (3,472.8 ha) ที่ scale=20m
# จะได้ ~86,821 pixel/แถว — เกิน GEE synchronous element limit (~5,000) ไปมาก (17 เท่า) แม้จะแก้
# masked-band แล้วก็ตาม (ยืนยันด้วยการคำนวณ area_m2/(scale*scale) จริงจาก load_zone_boundaries())
#
# วิธี download ที่เลือก — ee.Image.getDownloadURL() แทน ee.batch.Export.image.toDrive():
# ผู้ใช้เสนอ Export.image.toDrive()+ee.batch.Task.status() polling ตามที่เอกสาร GEE แนะนำสำหรับภาพ
# ใหญ่ แต่ตรวจสอบแล้ว (grep ทั้ง repo) พบว่า**ไม่มีโครงสร้างพื้นฐานสำหรับดาวน์โหลดจาก Drive/GCS อยู่
# เลยในโค้ดเบสนี้**: ไม่มี google-cloud-storage, ไม่มี pydrive/Drive API OAuth, ไม่มี geemap,
# requirements.txt ไม่มี dependency พวกนี้เลย และ auth ปัจจุบันเป็น personal ee.Authenticate()
# (interactive) ไม่ใช่ Service Account (TODO ที่ยังไม่เสร็จอยู่แล้วในหัวไฟล์นี้) — การใช้ toDrive()
# จะต้องเพิ่ม OAuth flow ใหม่ทั้งหมดสำหรับ Drive API (client_secret.json, token storage, consent
# screen) ซึ่งเป็นโครงสร้างพื้นฐานใหม่ทั้งหมดที่ยังไม่เคยมีในโปรเจกต์นี้เลย
# getDownloadURL() ใช้ personal ee.Authenticate() session เดียวกับที่มีอยู่แล้ววันนี้ได้ทันที
# (เป็น synchronous HTTP GET ธรรมดา ไม่ใช่ async batch task — ไม่ต้อง poll/timeout หลักสิบนาที
# แบบ Export.image.toDrive() ทำงานจริง) และไม่ต้องเพิ่ม dependency ใหม่เลยนอกจาก rasterio (ซึ่ง
# ต้องใช้อยู่แล้วสำหรับ classify local แบบเดียวกับ Retrain3.ipynb cell 16) — ข้อแลกเปลี่ยน: ภาพ
# ใหญ่มากอาจชน GEE synchronous download size limit (เอกสารระบุ ~32MB/request) จึงเพิ่ม fallback
# แบ่ง region เป็น grid tile ดาวน์โหลดทีละส่วนแล้ว mosaic กลับด้วย rasterio.merge ถ้า single-shot
# ล้มเหลว (ดู _download_ee_image_geotiff())


def _download_ee_image_geotiff(
    image, region_geom, scale: int, out_path: Path, crs: str = SAR_EXPORT_CRS, grid_n: int = 1,
) -> Path:
    """
    ดาวน์โหลด ee.Image (ควร .clip() ตาม zone ไว้ก่อนแล้ว) เป็น GeoTIFF ไฟล์เดียว ผ่าน
    ee.Image.getDownloadURL() (synchronous HTTP, ไม่ใช่ ee.batch.Export — ดูเหตุผลด้านบน)

    ถ้า single-shot (grid_n=1) ล้มเหลว (มักเป็นเพราะเกิน GEE synchronous request size limit)
    จะ retry แบบแบ่ง region เป็น grid_n x grid_n tile ดาวน์โหลดทีละ tile แล้ว mosaic กลับด้วย
    rasterio.merge โดยไล่ grid_n = 2, 3, 4 ก่อนจะ raise ถ้ายังล้มเหลวอยู่
    """
    import requests

    def _fetch(geom, dest_path: Path) -> Path:
        url = image.getDownloadURL({
            "region": geom,
            "scale": scale,
            "crs": crs,
            "format": "GEO_TIFF",
            "filePerBand": False,
        })
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return dest_path

    if grid_n <= 1:
        try:
            return _fetch(region_geom, out_path)
        except Exception as exc:
            logger.warning(
                "getDownloadURL() single-shot ล้มเหลว (%s) -- ลอง fallback แบ่ง tile 2x2", exc,
            )
            return _download_ee_image_geotiff(image, region_geom, scale, out_path, crs=crs, grid_n=2)

    import rasterio
    from rasterio.merge import merge

    bounds_coords = region_geom.bounds().getInfo()["coordinates"][0]
    xs = [c[0] for c in bounds_coords]
    ys = [c[1] for c in bounds_coords]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = (maxx - minx) / grid_n
    dy = (maxy - miny) / grid_n

    import ee

    tile_paths = []
    for i in range(grid_n):
        for j in range(grid_n):
            tile_rect = ee.Geometry.Rectangle(
                [minx + i * dx, miny + j * dy, minx + (i + 1) * dx, miny + (j + 1) * dy]
            )
            tile_path = out_path.with_name(f"{out_path.stem}_tile{i}_{j}.tif")
            try:
                _fetch(tile_rect, tile_path)
                tile_paths.append(tile_path)
            except Exception as exc:
                logger.warning(
                    "ดาวน์โหลด tile (%d,%d)/%dx%d ล้มเหลว (%s) -- ข้าม tile นี้", i, j, grid_n, grid_n, exc,
                )

    if not tile_paths:
        if grid_n < 4:
            logger.warning("grid %dx%d ล้มเหลวทุก tile -- ลอง grid ละเอียดขึ้น", grid_n, grid_n)
            return _download_ee_image_geotiff(image, region_geom, scale, out_path, crs=crs, grid_n=grid_n + 1)
        raise RuntimeError(f"ดาวน์โหลด {out_path.name} ล้มเหลวทุก tile แม้ที่ grid {grid_n}x{grid_n}")

    srcs = [rasterio.open(p) for p in tile_paths]
    mosaic, out_transform = merge(srcs)
    profile = srcs[0].profile.copy()
    profile.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=out_transform)
    # 2026-07-12 แก้บั๊กวิกฤต: rasterio.merge.merge() คืนแค่ (array, transform) เฉยๆ -- "profile"
    # (driver/dtype/nodata/count/crs ฯลฯ) ไม่มี band descriptions รวมอยู่ด้วย (เป็น per-band metadata
    # แยกต่างหากใน GDAL ไม่ใช่ส่วนหนึ่งของ profile dict) เก็บ descriptions จาก tile แรกไว้ก่อนปิด
    # source ทั้งหมด แล้วเซ็ตกลับเข้า output หลัง write -- ถ้าไม่ทำขั้นนี้ _classify_raster_local()
    # จะอ่าน band names ไม่ได้เลย (band_names=None) ทำให้ columns กลายเป็น "band_0".."band_85"
    # ทั่วไปที่ไม่ตรงกับ feature_order ของโมเดล -> reindex() ได้ DataFrame ที่เป็น NaN ทั้งหมด ->
    # fillna(col_medians) เติมค่า median เดียวกันทุก pixel -> ทุก pixel classify เหมือนกันหมดทั้งภาพ
    # (บั๊กที่ยืนยันแล้วจากรันจริง: rice 100% ทุก pixel ทั้ง 2 zone ที่ไปเจอเส้นทาง tile-fallback นี้)
    band_descriptions = srcs[0].descriptions
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mosaic)
        if band_descriptions and all(band_descriptions) and len(band_descriptions) == mosaic.shape[0]:
            dst.descriptions = band_descriptions
        else:
            # 2026-07-14 แก้ข้อความ log: เดิมบอกว่า "_classify_raster_local() จะ raise ตอน validate
            # feature names" ซึ่ง**ไม่จริงอีกต่อไป**ตั้งแต่ Fix Round 2 (FULL_IMG_BAND_ORDER เป็นแหล่ง
            # ความจริงหลักแล้ว ไม่ใช่ fallback) -- ข้อความเดิมทำให้ผู้ใช้เข้าใจผิดว่าเจอ warning
            # ที่ "บอกว่าจะพัง" ทั้งที่ status=ok จริง (เจอจากรันจริง 2026-07-13) เปลี่ยนเป็นข้อความที่
            # ตรงกับพฤติกรรมจริง: นี่คือสถานการณ์ปกติที่คาดไว้แล้ว (ยืนยันแล้วว่า GEE ไม่เขียน band
            # descriptions ลง GeoTIFF เลยเสมอ) ไม่ใช่สัญญาณว่ามีอะไรผิดปกติ -- ระบบจะ fallback ไปใช้
            # FULL_IMG_BAND_ORDER (positional matching ตามลำดับ band ที่รู้ล่วงหน้าจากตอนสร้าง
            # composite) โดยอัตโนมัติใน _classify_raster_local() ความถูกต้องของวิธีนี้ขึ้นอยู่กับว่า
            # ลำดับ band จริงที่ GEE export ออกมาตรงกับ FULL_IMG_BAND_ORDER หรือไม่ -- จุดนี้ถูก verify
            # แยกต่างหากด้วย live bandNames() check ใน trigger_crop_classification() ก่อน export
            # ทุกครั้ง (ไม่ใช่แค่ assume เฉยๆ)
            logger.info(
                "%s: tile แรก (%s) ไม่มี band descriptions ในไฟล์ (ปกติ -- ยืนยันแล้วว่า GEE ไม่เขียนให้"
                "เสมอ ไม่ใช่สัญญาณปัญหา) -- mosaic output จะไม่มี band descriptions ด้วยเช่นกัน "
                "_classify_raster_local() จะ fallback ไปใช้ FULL_IMG_BAND_ORDER (positional matching) "
                "โดยอัตโนมัติ ไม่ raise",
                out_path.name, tile_paths[0].name,
            )
    for s in srcs:
        s.close()
    for p in tile_paths:
        p.unlink(missing_ok=True)

    logger.info("ดาวน์โหลด %s สำเร็จผ่าน grid %dx%d tile (%d tile จริง)", out_path.name, grid_n, grid_n, len(tile_paths))
    return out_path


def _classify_raster_local(tif_path: Path, rf: dict, zone_geom_native=None) -> dict:
    """
    Classify ทุก pixel ของ raster ที่ดาวน์โหลดมาแบบ local — ตาม pattern เดียวกับ
    Retrain3.ipynb cell 16 (generate_crop_map_v3b) เป๊ะ: reshape raster array ทั้งก้อนเป็น
    (n_pixel, n_feature) DataFrame แล้วส่งผ่าน classify_feature_matrix() เดียวกับที่ใช้กับ
    sampleRegions() แบบเดิม (logic fillna(col_medians)/sentinel-replace เหมือนกันทุกจุด)

    zone_geom_native: shapely geometry (native CRS, ต้องตรงกับ SAR_EXPORT_CRS/EPSG:32647) ของ
    zone จริง — ใช้ rasterize() ทับ grid ของ raster ที่ดาวน์โหลดมาโดยตรง เพื่อตัดสินว่าพิกเซลไหน
    "อยู่ในโซนจริง" (ต้องแยกออกจากพิกเซลที่ "อยู่ในโซนจริงแต่สัปดาห์ว่าง" ซึ่งมีค่า SAR_MASK_SENTINEL
    และยังต้องถูก classify ด้วย imputation ตามสถาปัตยกรรมเดิม — ไม่งั้นพื้นที่นอกโซนจะถูกนับพื้นที่
    พืชผิดๆ ไปด้วย เพราะ bounding-box ที่ใช้ตอน download กว้างกว่าขอบเขต polygon จริงของ zone เสมอ)
    ถ้าไม่ส่งมา (None) จะ fallback ไปนับทุก pixel เป็น "ในโซน" หมด พร้อม log warning ชัดเจน (ไม่ควร
    เกิดขึ้นใน production — trigger_crop_classification() ส่ง zdata["geom_native"] มาเสมอ)

    2026-07-12 แก้บั๊ก band name mismatch ที่ยืนยันแล้วจากการรันจริงบนเครื่อง user (ผลลัพธ์เดิม:
    rice 100% ทุก pixel ทั้ง 2 zone): ทั้ง 2 zone ตอนนั้นดาวน์โหลดผ่านเส้นทาง tile-fallback (2x2)
    เพราะภาพใหญ่เกิน 50MB single-request limit ทั้งคู่ — ยืนยันแล้วว่า **src.descriptions เป็น None
    ทั้ง 86 band ตั้งแต่ tile แรกก่อน merge ด้วยซ้ำ** สรุปว่า ee.Image.getDownloadURL() **ไม่เขียน
    band descriptions ลง GeoTIFF เลย** ไม่ว่าจะ single-shot หรือ tile-fallback ก็ตาม ทำให้
    band_names อ่านได้เป็น None เสมอ -> columns กลายเป็น "band_0".."band_85" ทั่วไป ->
    classify_feature_matrix()'s X_raw.reindex(columns=feature_order) ได้ DataFrame ที่เป็น NaN
    ทั้งหมด -> fillna(col_medians) เติมค่า median เดียวกันทุก pixel -> ทุก pixel ได้ feature vector
    เหมือนกันหมด -> classify ออกมาเป็น class เดียวกันทั้งภาพ (สังเกตตรงกับผลจริง: rice 100%) แก้ด้วย
    การเลิกพึ่ง src.descriptions เป็นหลัก เปลี่ยนไปใช้ FULL_IMG_BAND_ORDER (ลำดับ band ที่เรารู้เอง
    จากตอนสร้าง full_img composite) เป็นแหล่งความจริงหลักแทน — ตำแหน่ง/index ของ band ใน GeoTIFF
    รอดผ่าน download/merge แน่นอนเสมอ validation ด้านล่างยังคง raise ทันทีถ้าจำนวน band ไม่ตรงกับ
    ที่คาดไว้ ไม่ปล่อยให้ fail แบบเงียบๆ

    2026-07-13 แก้บั๊ก n_pixels_outside_zone=0 รอบที่ 2 (รอบแรกใช้ OUTSIDE_ZONE_SENTINEL ผ่าน GEE-side
    .clip().unmask() แล้วไม่ได้ผล — ยืนยันจากรันจริง n_pixels_outside_zone ยังเป็น 0 ทั้ง 2 zone
    เหมือนเดิม ทั้งที่โค้ดฝั่ง GEE ยืนยันแล้วว่าอยู่ถูกที่ และหลักฐานยืนยันว่าเป็นบั๊กจริง: n_pixels_valid
    ที่ classify ได้จริงตรงกับพื้นที่ bounding box ทั้งกรอบ ไม่ใช่พื้นที่ zone จริง — zone_A คลาดเคลื่อน
    ~3.47 เท่า, zone_B ~5.56 เท่า เทียบกับ area_m2 จาก load_zone_boundaries()) เปลี่ยนมาตัดสินที่ฝั่ง
    Python เองทั้งหมดแทน ด้วย rasterio.features.rasterize(zone_geom_native) ทับ grid ของ raster ที่
    ดาวน์โหลดมาโดยตรง ไม่ต้องพึ่งพฤติกรรม GEE .clip()/.unmask()/download ใดๆ เลย ตรวจสอบ/ทดสอบได้
    เต็มที่แบบ offline (ดู module-level comment เหนือ SAR_MASK_SENTINEL/เดิม OUTSIDE_ZONE_SENTINEL
    สำหรับรายละเอียดเต็มของทั้ง 2 รอบการแก้)

    คืน dict: {"class_map": np.ndarray (rows,cols) ค่า 0-4 หรือ 255=nodata นอกโซน,
               "pixel_area_ha": float, "crop_area_ha": dict, "n_pixels_valid": int}
    """
    import rasterio
    from rasterio.features import rasterize

    with rasterio.open(tif_path) as src:
        band_names = list(src.descriptions) if src.descriptions and all(src.descriptions) else None
        arr = src.read()  # (bands, rows, cols) -- ไม่ใช้ masked=True อีกต่อไป (เหตุผลดู docstring ด้านบน)
        rows, cols = src.height, src.width
        transform = src.transform

    n_bands = arr.shape[0]
    # 2026-07-12 แก้: สลับลำดับความสำคัญ -- ใช้ FULL_IMG_BAND_ORDER (ลำดับที่เรารู้เองจากตอนสร้าง
    # composite) เป็นหลักก่อน src.descriptions เพราะยืนยันแล้วจากรันจริงว่า GEE getDownloadURL()
    # ไม่เขียน band descriptions ลง GeoTIFF เลย (descriptions เป็น None เสมอในทางปฏิบัติ) เก็บ
    # src.descriptions ไว้เป็นทางเลือกสำรอง เผื่ออนาคต GEE เปลี่ยนพฤติกรรม export ให้เขียน
    # descriptions จริง (ถ้ามีวันนั้นจะใช้ descriptions จริงแทนอัตโนมัติ เพราะเชื่อถือได้กว่าถ้ามีจริง)
    if n_bands == len(FULL_IMG_BAND_ORDER):
        columns = FULL_IMG_BAND_ORDER
        # 2026-07-14 ชี้ให้ชัดเจนในข้อความ log: นี่คือ "positional matching" ล้วนๆ (column j ของ
        # DataFrame ได้ชื่อ FULL_IMG_BAND_ORDER[j] ตามตำแหน่ง/index ของ band ในไฟล์ ไม่ใช่การจับคู่
        # ตามชื่อ/เนื้อหาจริงของ band เลย) ไม่ใช่แค่ "ทางเลือกสำรอง" ที่ฟังดูไม่แน่ใจ -- ความถูกต้อง
        # ของวิธีนี้ถูก verify แยกต่างหากแล้วด้วย live full_img.bandNames().getInfo() check ใน
        # trigger_crop_classification() ก่อน export ทุกรอบ (ดู comment ตรงนั้น) ไม่ใช่แค่ assume เฉยๆ
        # พิสูจน์ด้วย offline synthetic test แล้วว่ากลไก positional นี้ sensitive ต่อการสลับตำแหน่ง
        # band จริง (ไม่ใช่ no-op ที่มองข้ามลำดับ/ค่า band ไป)
        logger.info(
            "%s: ใช้ FULL_IMG_BAND_ORDER matching แบบ POSITIONAL (column ตำแหน่ง j ในไฟล์ = ชื่อ "
            "FULL_IMG_BAND_ORDER[j] ตามตำแหน่ง ไม่ใช่ตามชื่อ/descriptions จริงจากไฟล์) -- %d band "
            "ตรงกับจำนวนที่คาดไว้พอดี (GeoTIFF band descriptions จากไฟล์เอง: %s -- ไม่ได้ใช้อยู่ดี "
            "เพราะ FULL_IMG_BAND_ORDER เป็นแหล่งความจริงหลักแล้ว) ความถูกต้องของลำดับนี้ผ่านการ "
            "verify สดกับ GEE จริงแล้วก่อน export รอบนี้ (ดู log 'ยืนยันแล้วจาก GEE จริง' ก่อนหน้า "
            "ใน trigger_crop_classification())",
            tif_path.name, n_bands, "มี" if band_names else "ไม่มี (ปกติ -- ยืนยันแล้วว่า GEE ไม่เขียนให้)",
        )
    elif band_names and len(band_names) == n_bands:
        columns = band_names
        logger.info("%s: n_bands=%d ไม่ตรงกับ FULL_IMG_BAND_ORDER (%d) -- fallback ไปใช้ GeoTIFF band descriptions จริงแทน",
                    tif_path.name, n_bands, len(FULL_IMG_BAND_ORDER))
    else:
        columns = [f"band_{i}" for i in range(n_bands)]
        logger.warning(
            "%s: n_bands=%d ไม่ตรงกับทั้ง FULL_IMG_BAND_ORDER (%d) และไม่มี GeoTIFF band descriptions "
            "ที่ใช้ได้ -- ใช้ชื่อ generic band_0..band_N (ผิดปกติมาก ควรตรวจสอบด่วน)",
            tif_path.name, n_bands, len(FULL_IMG_BAND_ORDER),
        )

    # --- validation 1: band names/count ต้องตรงกับ feature_order ที่โมเดลต้องการครบทุกตัว ---
    # 2026-07-14 หมายเหตุสำคัญ (ขอบเขตของ validation นี้): ตรวจแค่ "จำนวน band ตรงกัน" และ "set ของ
    # ชื่อ band ตรงกับ set ของ feature_order" เท่านั้น -- **ไม่ได้พิสูจน์ว่าตำแหน่ง/ลำดับ band ถูกต้อง
    # จริง** เมื่อ columns=FULL_IMG_BAND_ORDER (positional matching) เพราะ FULL_IMG_BAND_ORDER กับ
    # feature_order เป็น set เดียวกันเสมอโดยโครงสร้าง (86 ชื่อเดียวกัน) -- validation นี้จะ "ผ่าน"
    # เสมอไม่ว่าลำดับจริงจะถูกหรือผิดก็ตาม ความถูกต้องของลำดับ/ตำแหน่งจริงถูก verify แยกต่างหากแล้ว
    # ด้วย live full_img.bandNames().getInfo() check ใน trigger_crop_classification() ก่อน export
    # (ดู comment ตรงนั้น) -- validation ข้างล่างนี้จับได้แค่กรณี "จำนวน/ชื่อ band ผิดไปเลย" (เช่น
    # ที่เจอจริงตอน band descriptions หายไปทั้งที่ FULL_IMG_BAND_ORDER ยังไม่มีอยู่ -- Fix Round 1)
    expected_features = set(rf["feature_order"])
    matched_features = expected_features & set(columns)
    logger.info(
        "%s: ตรวจสอบจำนวน/set ชื่อ band (ไม่ใช่ตำแหน่ง) -- matched %d/%d feature ที่โมเดลต้องการ "
        "(columns มาจาก: %s)",
        tif_path.name, len(matched_features), len(expected_features),
        "FULL_IMG_BAND_ORDER (positional)" if columns is FULL_IMG_BAND_ORDER
        else ("GeoTIFF band descriptions จริง" if columns is band_names else "band_0..band_N แบบ generic (ผิดปกติ)"),
    )
    if len(matched_features) != len(expected_features):
        missing_sample = sorted(expected_features - matched_features)[:8]
        raise ValueError(
            f"{tif_path.name}: GeoTIFF band names ตรงกับ feature_order ที่โมเดลต้องการแค่ "
            f"{len(matched_features)}/{len(expected_features)} -- ตัวอย่าง feature ที่หาไม่เจอ: "
            f"{missing_sample} (คอลัมน์จริงที่อ่านได้ 5 ตัวแรก: {columns[:5]}) หยุด classify ทันที "
            "ไม่ปล่อยให้ reindex() เติม NaN ทั้งคอลัมน์แล้ว fillna(col_medians) กลายเป็นทุก pixel ได้ "
            "feature vector เดียวกันหมดแบบเงียบๆ (อาการที่เคยเจอจริง: ทุก pixel classify ออกมาเป็น "
            "class เดียวกันหมดทั้งภาพ) มักเกิดจาก rasterio.merge() ไม่ propagate band descriptions "
            "ตอน tile-fallback download (ดู _download_ee_image_geotiff())"
        )

    # --- outside-zone detection: rasterize zone_geom_native ทับ grid ของ raster นี้โดยตรง (ไม่พึ่ง
    # GEE .clip()/.unmask() หรือ GDAL nodata metadata เลย -- ดู docstring ด้านบนสำหรับเหตุผลว่าทำไม
    # ทั้ง 2 วิธีก่อนหน้านี้ยืนยันแล้วว่าใช้ไม่ได้จากการรันจริง) ---
    if zone_geom_native is not None:
        inside_zone_mask = rasterize(
            [(zone_geom_native, 1)],
            out_shape=(rows, cols),
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
        outside_zone_mask = ~inside_zone_mask
    else:
        logger.warning(
            "%s: ไม่ได้ส่ง zone_geom_native เข้ามา -- นับทุก pixel เป็น 'ในโซน' หมด (ผิดปกติมาก "
            "ไม่ควรเกิดขึ้นใน production -- trigger_crop_classification() ควรส่ง "
            "zdata['geom_native'] มาเสมอ ตรวจสอบจุดเรียกใช้ฟังก์ชันนี้ด่วน)",
            tif_path.name,
        )
        outside_zone_mask = np.zeros((rows, cols), dtype=bool)
    logger.info(
        "%s: outside_zone_mask (rasterize zone_geom_native local) -- พบ %d/%d pixel (%.1f%%) "
        "นอกขอบเขต zone จริง",
        tif_path.name, int(outside_zone_mask.sum()), outside_zone_mask.size,
        100.0 * outside_zone_mask.sum() / outside_zone_mask.size if outside_zone_mask.size else 0.0,
    )

    flat = arr.reshape(n_bands, -1).T  # (n_pixel, n_bands)
    df = pd.DataFrame(flat, columns=columns)

    # --- diagnostic: กี่แถวเป็น NaN ทั้งแถวก่อน fillna(col_medians) (ควรเป็นแค่ส่วนน้อย ไม่ใช่เกือบทั้งหมด) ---
    _diag = df.reindex(columns=rf["feature_order"]).astype(float).replace(SAR_MASK_SENTINEL, np.nan)
    all_nan_rows = int(_diag.isnull().all(axis=1).sum())
    logger.info(
        "%s: %d/%d pixel (%.1f%%) เป็น NaN ทั้งแถวก่อน fillna(col_medians) (ปกติควรใกล้เคียงสัดส่วน "
        "พิกเซลนอกโซน + สัปดาห์ว่างจริง ไม่ใช่เกือบ 100%%)",
        tif_path.name, all_nan_rows, len(df),
        100.0 * all_nan_rows / len(df) if len(df) else 0.0,
    )

    preds = classify_feature_matrix(rf, df)  # ใช้ pipeline เดียวกับตอน sampleRegions() ทุกจุด
    class_map = preds.reshape(rows, cols).astype(np.uint8)
    class_map_masked = class_map.copy()
    class_map_masked[outside_zone_mask] = 255  # nodata -- ตรงกับ convention ของ Retrain3.ipynb cell 16

    pixel_area_ha = abs(transform.a * transform.e) / 10000  # คำนวณจาก transform จริง ไม่ใช่ scale ที่ขอ
    valid = ~outside_zone_mask
    classes, counts = np.unique(class_map[valid], return_counts=True)
    crop_area_ha = {CLASS_LABELS[int(c)]: float(n) * pixel_area_ha for c, n in zip(classes, counts) if int(c) in CLASS_LABELS}

    return {
        "class_map": class_map_masked,
        "transform": transform,
        "pixel_area_ha": pixel_area_ha,
        "crop_area_ha": crop_area_ha,
        "n_pixels_valid": int(valid.sum()),
        "n_pixels_outside_zone": int(outside_zone_mask.sum()),
    }


def compute_zone_b_reservoir_area_ha(class_map: np.ndarray, transform, pixel_area_ha: float) -> dict:
    """
    2026-07-22 เพิ่ม — แบ่งพื้นที่ Zone B (irrigated) ต่อ crop ตาม "อ่างที่ส่งน้ำ" แทนที่จะรวมเป็นก้อน
    เดียวทั้งโซนแบบเดิม — ใช้ 3 sub-polygon ที่มีอยู่แล้วจริงใน zone_b_irrigated.shp (คอลัมน์
    LU_DES_TH: "Mae Na Rua"/"Huay Tham"/"Huay So" — ไม่ใช่ metadata เฉยๆ แต่คือขอบเขต sub-catchment
    จริงของแต่ละอ่าง ยืนยันจาก load_zone_boundaries() docstring 2026-07-10) map เป็นชื่อไทยผ่าน
    RESERVOIR_LABEL_TH

    รับ class_map/transform/pixel_area_ha ที่ classify ไปแล้วจาก _classify_raster_local() (หรืออ่าน
    จากไฟล์ crop_map_v3b_zone_B_<year>.tif ที่เขียนไว้ก็ได้ — grid/CRS เดียวกันเป๊ะ เพราะเขียนจาก
    class_map ตัวเดียวกันตรงๆ ดู compute_zone_b_reservoir_area_ha_from_tif() ด้านล่าง) ไม่ classify
    ซ้ำ — แค่ rasterize sub-polygon ทีละอันทับ grid เดิม (เทคนิคเดียวกับที่ _classify_raster_local()
    ใช้ตัดขอบเขต zone ทั้งก้อนออกจาก raster ที่ดาวน์โหลดมากว้างกว่าจริงเสมอ) แล้วนับ pixel ต่อ class
    เฉพาะในแต่ละ sub-polygon (ไม่นับ nodata=255) x pixel_area_ha

    หมายเหตุ: ผลรวมพื้นที่ทุกอ่างรวมกันจะใกล้เคียงแต่ไม่เป๊ะ 100% เท่ากับ crop_area_ha ของทั้งโซน
    (ต่างกัน ~0.05%) เพราะ 3 sub-polygon เกยกันเล็กน้อยตามที่ digitize มา (ดู load_zone_boundaries()
    docstring จุดเดียวกัน) — ไม่ใช่บั๊ก ยอมรับความคลาดเคลื่อนระดับนี้ได้

    คืน dict {reservoir_name_th: {crop: area_ha, ...}, ...} — ถ้า LU_DES_TH ค่าไหนไม่อยู่ใน
    RESERVOIR_LABEL_TH ที่รู้จัก (ไม่ควรเกิดขึ้น ยืนยันแล้วว่ามีแค่ 3 ค่าจริงในไฟล์) จะ log warning
    แล้วข้าม polygon นั้นไป ไม่ raise
    """
    import geopandas as gpd
    from rasterio.features import rasterize

    zone_b_gdf = gpd.read_file(ZONE_B_SHP_PATH)
    rows, cols = class_map.shape

    result: dict = {}
    for _, row in zone_b_gdf.iterrows():
        label_en = row.get("LU_DES_TH")
        label_th = RESERVOIR_LABEL_TH.get(label_en)
        if label_th is None:
            logger.warning(
                "zone_b_irrigated.shp: LU_DES_TH=%r ไม่อยู่ใน RESERVOIR_LABEL_TH ที่รู้จัก (%s) -- "
                "ข้าม polygon นี้ (ไม่รวมเข้า reservoir breakdown)",
                label_en, sorted(RESERVOIR_LABEL_TH.keys()),
            )
            continue

        poly_mask = rasterize(
            [(row.geometry, 1)],
            out_shape=(rows, cols),
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)

        valid = poly_mask & (class_map != 255)
        classes, counts = np.unique(class_map[valid], return_counts=True)
        crop_area_ha = {
            CLASS_LABELS[int(c)]: float(n) * pixel_area_ha
            for c, n in zip(classes, counts) if int(c) in CLASS_LABELS
        }
        result[label_th] = crop_area_ha

    return result


def compute_zone_b_reservoir_area_ha_from_tif(tif_path: Path) -> dict:
    """
    เหมือน compute_zone_b_reservoir_area_ha() แต่อ่าน class_map/transform/pixel_area_ha จากไฟล์
    crop_map_v3b_zone_B_<year>.tif ที่ classify ไว้แล้วโดยตรง (ไม่ต้องมี classify_result ในมืออยู่แล้ว)
    สะดวกสำหรับเรียกนอก trigger_crop_classification() เช่นตอน backfill/ทดสอบแบบ standalone
    """
    import rasterio

    with rasterio.open(tif_path) as src:
        class_map = src.read(1)
        transform = src.transform
        pixel_area_ha = abs(transform.a * transform.e) / 10000

    return compute_zone_b_reservoir_area_ha(class_map, transform, pixel_area_ha)


# ---------------------------------------------------------------------------
# ส่วนที่ 4: ตรวจภาพใหม่ + จำแนกพืช (จุดเชื่อมกับ data_pipeline.py)
# ---------------------------------------------------------------------------

def check_new_sar_image(
    as_of_date: Optional[date] = None,
    gee_project: str = DEFAULT_GEE_PROJECT,
    marker_path: Path = SAR_LAST_CLASSIFIED_MARKER,
    min_days_between_runs: int = 30,
) -> Optional[dict]:
    """
    เช็คว่าถึงรอบควรรัน crop classification ใหม่หรือยัง — ไม่ได้เช็คทีละภาพ SAR รายวัน (RF
    classifier ต้องการ composite ของทั้งปี ไม่ใช่ภาพเดียว) แต่เช็คว่า:
      1. ผ่านมา >= min_days_between_runs วันแล้วนับจากรอบล่าสุด (เก็บ state ไว้ที่ marker_path)
      2. มีภาพ Sentinel-1 ใหม่ของพื้นที่ AOI จริงในช่วงนั้น (ไม่ใช่แค่เวลาผ่านไปเฉยๆ)

    คืนค่า {"as_of_date": str, "year": int, "latest_s1_image_date": str} ถ้าควรรันใหม่ หรือ None
    ถ้ายังไม่ถึงรอบ/ดึง GEE ไม่สำเร็จ (ไม่ raise — ตาม convention เดียวกับ mei_feature.py)
    """
    as_of = as_of_date or datetime.now().date()

    if marker_path.exists():
        try:
            last_run = datetime.strptime(marker_path.read_text().strip(), "%Y-%m-%d").date()
            days_since = (as_of - last_run).days
            if days_since < min_days_between_runs:
                logger.info(
                    "SAR classification: รอบล่าสุด %s ผ่านมาแค่ %d วัน (< %d) — ยังไม่ถึงรอบ",
                    last_run, days_since, min_days_between_runs,
                )
                return None
        except Exception:
            logger.warning("อ่าน marker file %s ไม่สำเร็จ — ถือว่ายังไม่เคยรัน", marker_path)

    try:
        import ee
        import gee_auth

        gee_auth.init_ee(gee_project)
        zones = load_zone_boundaries()
        aoi = _to_ee_geometry(zones["zone_A"]["geom_4326"])

        recent_start = (as_of - timedelta(days=30)).isoformat()
        s1_recent = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi)
            .filterDate(recent_start, as_of.isoformat())
            .filter(ee.Filter.eq("instrumentMode", "IW"))
        )
        n_images = s1_recent.size().getInfo()
        if n_images == 0:
            logger.warning(
                "SAR classification: ไม่พบภาพ Sentinel-1 ใหม่ในช่วง 30 วันที่ผ่านมาเลย "
                "(AOI=zone A boundary) — ข้ามรอบนี้"
            )
            return None

        latest_date = (
            ee.Date(s1_recent.sort("system:time_start", False).first().get("system:time_start"))
            .format("YYYY-MM-dd")
            .getInfo()
        )
        logger.info(
            "SAR classification: พบภาพ S1 ใหม่ %d ภาพในช่วง 30 วัน ล่าสุด=%s — ถึงรอบรัน classification",
            n_images, latest_date,
        )
        return {"as_of_date": as_of.isoformat(), "year": as_of.year, "latest_s1_image_date": latest_date}

    except Exception as exc:
        logger.warning(
            "SAR classification: เช็คภาพ S1 ใหม่จาก GEE ไม่สำเร็จ (%s) — ข้ามรอบนี้ "
            "(ต้องมี ee credential ตั้งค่าไว้แล้วบนเครื่องที่รัน — ดู TODO Service Account ในหัวไฟล์)",
            exc,
        )
        return None


def trigger_crop_classification(sar_trigger: dict, marker_path: Path = SAR_LAST_CLASSIFIED_MARKER) -> dict:
    """
    รัน crop classification เต็มรูปแบบ: สร้าง S2 dry-season composite + S1 weekly VV/VH stack
    ของปีที่ระบุใน sar_trigger → export เป็น GeoTIFF ต่อ zone A/B → classify ทุก pixel แบบ local
    (rasterio+RF v3b) → รวมพื้นที่ต่อ crop ต่อ zone แล้วเทียบกับพื้นที่ hardcode ปี 2020
    (AREA_ZONE_A/AREA_ZONE_B ใน feature_schema.md)

    marker_path: ไฟล์ที่จะเขียนวันที่รันสำเร็จล่าสุดลงไป (default = SAR_LAST_CLASSIFIED_MARKER ตัวจริง
    ที่ check_new_sar_image() ใช้ gate 30 วัน) 2026-07-12 เพิ่ม parameter นี้เพื่อแก้บั๊กที่ยืนยันแล้ว
    จากรันจริง: test script (test_sar_classification_live.py) เรียกฟังก์ชันนี้ตรงๆ ใน step 3 (เพื่อ
    ทดสอบ classify แยกจาก check_new_sar_image()'s gate) ซึ่งเดิม hardcode เขียนทับ
    SAR_LAST_CLASSIFIED_MARKER ตัวจริงไปด้วย ทำให้ step 7 (ทดสอบ sar_background_job.py แบบ
    end-to-end) เรียก check_new_sar_image() ผ่าน marker ตัวเดียวกันแล้วเจอว่า "เพิ่งรันไปเมื่อกี้นี้
    เอง (0 วัน < 30)" เลย gate ตัวเองออกทันที (outcome.reason='not_due_or_no_new_image') ทั้งที่
    เพิ่งพิสูจน์ว่า classify สำเร็จจริงในรอบเดียวกัน — ไม่ใช่ logic คนละอันจริงๆ (sar_background_job.py
    เรียก check_new_sar_image() ตัวเดียวกันเป๊ะ) แต่เป็นเพราะ marker ถูกเขียนทับโดยไม่ตั้งใจจาก step
    ก่อนหน้าในสคริปต์ทดสอบเดียวกัน ให้ caller ที่ต้องการทดสอบแยกจาก production gate ส่ง marker_path
    อื่นเข้ามาแทน (ดู TEST_MARKER_PATH ใน test_sar_classification_live.py)

    2026-07-11 เปลี่ยนสถาปัตยกรรมทั้งหมด: จาก sampleRegions().getInfo() (synchronous, ชน GEE
    5,000-element limit เพราะ zone_A ที่ scale=20m มี ~86,821 pixel — เกิน limit 17 เท่า แม้แก้
    masked-band ด้วย unmask() แล้วก็ตาม) เป็น "export ภาพเต็ม zone -> classify ทุก pixel แบบ
    local" ให้ตรงกับวิธีที่ Retrain3.ipynb cell 16 ใช้จริงตอน generate crop_map_v3b_2020..2023.tif
    (ยืนยันแล้วว่า cell นั้นไม่มี ee.* เลย — อ่าน TIF ที่ export ไว้ก่อนด้วย rasterio ล้วนๆ) ดู
    docstring ของ _download_ee_image_geotiff()/_classify_raster_local() สำหรับรายละเอียดเต็ม
    รวมถึงเหตุผลที่เลือก getDownloadURL() แทน ee.batch.Export.image.toDrive()+Task.status() polling
    ตามที่เสนอมา (ไม่มี Drive/GCS download infra อยู่ในโปรเจกต์นี้เลย)

    ฟังก์ชันนี้ใช้เวลานานกว่าเดิมมาก (นาทีถึงหลายนาที ไม่ใช่วินาที เพราะต้องดาวน์โหลด GeoTIFF
    ขนาด ~สิบ MB ต่อ zone แล้ว classify ทุก pixel local) — ควรรันเป็น background job แยกจาก
    data_pipeline.py หลัก (ดู sar_background_job.py) ไม่ใช่รันตรงในทุกรอบ pipeline หลัก

    หมายเหตุ: ยังไม่ implement การอัปเดต AREA_ZONE_A/AREA_ZONE_B อัตโนมัติ (ตามที่ตกลงไว้ว่าเป็น
    เฟสถัดไป) — ฟังก์ชันนี้แค่คืนผล classify ให้ตรวจสอบว่าสมเหตุสมผลก่อน
    """
    year = sar_trigger["year"]
    result: dict = {
        "year": year,
        "status": "failed",
        "zone_crop_area_ha": {},
        # 2026-07-22 เพิ่ม — พื้นที่ zone_B แบ่งย่อยตามอ่างที่ส่งน้ำ (ดู compute_zone_b_reservoir_area_ha())
        # เติมเฉพาะตอน classify zone_B สำเร็จ (ไม่กระทบ zone_crop_area_ha หลักถ้าพังบางส่วน)
        "zone_b_reservoir_area_ha": {},
        "comparison_vs_2020_hardcoded": {},
        "sar_data_quality": None,
        "raster_meta": {},
        # 2026-07-14 เพิ่ม — เก็บผล live bandNames() check ไว้ใน result dict ตรงๆ (ไม่ใช่แค่ log)
        # เพื่อให้ caller (test_sar_classification_live.py) print() ยืนยันออกมาให้เห็นชัดเจนได้เสมอ
        # โดยไม่ต้องพึ่งว่า logging handler ถูกตั้งค่าไว้หรือไม่ (ยืนยันแล้วว่า test script เดิม
        # **ไม่มี logging.basicConfig() เลย** — logger.info()/logger.warning() ระดับต่ำกว่า WARNING
        # ไม่เคยถูกแสดงในผลทดสอบทุกรอบที่ผ่านมาเลย มีแค่ logger.warning()/error() ที่เห็นเพราะ Python's
        # lastResort handler แสดงแค่ WARNING ขึ้นไปเท่านั้น) ดู comment เต็มที่จุด check จริงด้านล่าง
        "band_order_check": None,
        "errors": [],
    }

    # พื้นที่ hardcode ปี 2020 จาก feature_schema.md หัวข้อ 2 (AREA_ZONE_A/AREA_ZONE_B, หน่วย ha)
    # 2026-07-16: ย้ายเป็น module-level constant AREA_2020_HA_BY_ZONE แล้ว (ดู comment ที่จุด define
    # ด้านบนไฟล์) -- ใช้ alias ชื่อเดิมตรงนี้เพื่อไม่ต้องแก้โค้ดข้างล่างที่อ้างอิงชื่อ area_2020_ha
    area_2020_ha = AREA_2020_HA_BY_ZONE

    try:
        import ee
        import gee_auth

        gee_auth.init_ee(DEFAULT_GEE_PROJECT)
        rf = load_rf_classifier()
        zones = load_zone_boundaries()

        aoi = _to_ee_geometry(zones["zone_A"]["geom_4326"])

        # 2026-07-10 เพิ่ม — เช็คสัดส่วนสัปดาห์ว่าง (0 ภาพ) ก่อน sample จริง แล้วเทียบกับ baseline
        # ตอน train (41.7% ของ SAR band ว่างทั้งคอลัมน์ตั้งแต่ train แล้ว — ยืนยันจาก
        # col_medians_v3b_final.json) ถ้าสัปดาห์ว่างตอนนี้สูงกว่ามากและตรงกับ band ที่ตอน train มี
        # ข้อมูลจริง (ไม่ใช่ band ที่ null ตั้งแต่ train) ต้อง flag ให้เห็นก่อนเชื่อผล classify
        try:
            weekly_counts = _get_weekly_image_counts(aoi, year)
            sar_quality = _assess_sar_data_quality(weekly_counts, rf["col_medians"])
            result["sar_data_quality"] = sar_quality
            logger.info(
                "SAR data quality: %d/%d สัปดาห์ว่าง (%.1f%%) เทียบกับ training baseline %.1f%% — %s",
                sar_quality["n_empty_weeks"], sar_quality["n_total_weeks"],
                sar_quality["empty_week_pct"] or 0.0,
                sar_quality["training_baseline_null_band_pct"], sar_quality["risk_note"],
            )
        except Exception as exc:
            logger.warning("คำนวณ sar_data_quality ไม่สำเร็จ (%s) — ไปต่อโดยไม่มี diagnostic นี้", exc)
            result["sar_data_quality"] = {"error": str(exc)}

        s2_img = _build_s2_dry_season_composite(aoi, year)
        s1_img = _build_s1_weekly_vvvh_stack(aoi, year)
        # 2026-07-11 แก้: เดิมพยายามพึ่ง sampleRegions(..., dropNulls=False) แต่ยืนยันแล้วด้วย
        # help(ee.Image.sampleRegions) จริง (ไม่ต้องมี GEE credential — แค่ import ee เฉยๆ) ว่า
        # sampleRegions() ไม่มี parameter dropNulls เลย (มีแค่ใน ee.Image.sample()) ใส่เข้าไปจะได้
        # TypeError ทันที แก้ด้วยวิธีอื่น: .unmask(SAR_MASK_SENTINEL) บน image รวมทั้งหมด (S2+S1)
        # ก่อนส่งเข้า sampleRegions() แทน — ทำให้ไม่มี pixel ไหน masked เหลืออีกต่อไป (ทุก pixel มี
        # ค่าตัวเลขจริงเสมอ ไม่ว่าจะมาจาก S1 สัปดาห์ว่างที่ .selfMask() ไว้ หรือขอบ AOI ที่ S2 composite
        # อาจไม่มีข้อมูลครอบคลุมถึง) sampleRegions() จึงคืนทุกแถวแน่นอน ไม่ทิ้งอะไรทิ้งจากไป —
        # SAR_MASK_SENTINEL (-9999) ถูกแปลงกลับเป็น NaN ใน classify_feature_matrix() ก่อน fillna
        # (ดู docstring/comment ที่ SAR_MASK_SENTINEL ด้านบนสำหรับเหตุผลที่เลือกค่านี้)
        full_img = s2_img.addBands(s1_img).unmask(SAR_MASK_SENTINEL)

        # 2026-07-14 เพิ่ม — live band-order check กับ GEE จริง ก่อน export/classify
        # ==========================================================================
        # _classify_raster_local() จับคู่ band ของ raster ที่ดาวน์โหลดมากับ feature_order ของโมเดล
        # แบบ "positional" ล้วนๆ (ใช้ FULL_IMG_BAND_ORDER เป็นชื่อ column ตามตำแหน่ง/index ของ band
        # ในไฟล์ ไม่ใช่ชื่อจริงจาก GDAL descriptions — เพราะยืนยันแล้วว่า getDownloadURL() ไม่เขียน
        # descriptions ให้เลย) พิสูจน์แล้วด้วย offline synthetic test (สลับตำแหน่ง band 2 ตัวโดยตั้งใจ
        # แล้วเห็นผล classify เปลี่ยนจริง) ว่ากลไก positional matching นี้ "sensitive ต่อลำดับจริง" —
        # แปลว่าความถูกต้องทั้งหมดขึ้นอยู่กับสมมติฐานเดียว: ลำดับ band จริงที่ full_img มี (และที่
        # getDownloadURL() เขียนลงไฟล์เป็น band index 1..N ตามลำดับนั้น) ต้องตรงกับ FULL_IMG_BAND_ORDER
        # เป๊ะ สมมติฐานนี้มีเหตุผลรองรับ (ee.Image.addBands() เอกสารยืนยันว่าต่อ band ของ image1 ตามด้วย
        # band ของ image2 ตามลำดับเดิม ไม่มีการสลับ, และ GeoTIFF band index เป็นโครงสร้างพื้นฐานที่ GEE
        # ต้องเขียนตามลำดับ bandNames() เสมอ ไม่ใช่ metadata optional แบบ descriptions) แต่ไม่เคย
        # verify ตรงๆ กับ GEE จริงมาก่อน (แค่ "assume" อยู่) เพิ่ม check นี้เพื่อเปลี่ยนจาก "assumption"
        # เป็น "verified precondition" ทุกรอบที่รันจริง — เช็คถูกที่สุดเท่าที่ทำได้ (getInfo() ของ
        # bandNames() เป็น request เล็กมาก ไม่ต้องดาวน์โหลดข้อมูลจริง) ก่อนจะเสียเวลา/bandwidth ดาวน์โหลด
        # GeoTIFF ขนาดสิบ MB ต่อ zone — ถ้าลำดับไม่ตรง raise ทันที ไม่ปล่อยให้ไป corrupt ผลลัพธ์แบบเงียบๆ
        actual_band_names = full_img.bandNames().getInfo()
        band_order_ok = actual_band_names == FULL_IMG_BAND_ORDER
        # เขียนผลลง result dict ตรงๆ ก่อน raise/log -- ให้ caller เห็นได้แน่นอนไม่ว่า logging จะตั้ง
        # ค่าไว้หรือไม่ (ดู comment ที่ template ของ result ด้านบน)
        result["band_order_check"] = {
            "verified": band_order_ok,
            "actual_band_count": len(actual_band_names),
            "expected_band_count": len(FULL_IMG_BAND_ORDER),
            "actual_first5": actual_band_names[:5],
            "expected_first5": FULL_IMG_BAND_ORDER[:5],
        }
        if not band_order_ok:
            raise ValueError(
                f"ลำดับ band จริงจาก full_img.bandNames() ไม่ตรงกับ FULL_IMG_BAND_ORDER ที่ "
                f"_classify_raster_local() ใช้ positional matching อยู่ -- classify จะผิดเพี้ยนแบบ "
                f"เงียบๆ ถ้าปล่อยผ่านไป (ค่า band จะถูกตั้งชื่อผิดตำแหน่ง) หยุดก่อน export "
                f"ตัวอย่าง 5 ตัวแรกที่ได้จริง: {actual_band_names[:5]} เทียบกับที่คาดไว้: "
                f"{FULL_IMG_BAND_ORDER[:5]} (รวม {len(actual_band_names)} band จริง vs "
                f"{len(FULL_IMG_BAND_ORDER)} band ที่คาดไว้) ต้องตรวจสอบว่า s2_img.addBands(s1_img) "
                f"หรือลำดับการสร้าง composite เปลี่ยนไปจากที่ FULL_IMG_BAND_ORDER สมมติไว้หรือไม่"
            )
        logger.info(
            "ยืนยันแล้วจาก GEE จริง (bandNames().getInfo()): ลำดับ band ของ full_img ตรงกับ "
            "FULL_IMG_BAND_ORDER เป๊ะทั้ง %d band -- positional matching ใน _classify_raster_local() "
            "ปลอดภัยสำหรับรอบนี้",
            len(actual_band_names),
        )

        SAR_RASTER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for zone_label, zdata in zones.items():
            zone_geom_4326 = _to_ee_geometry(zdata["geom_4326"])
            # 2026-07-13: เดิมเคยลอง .clip(zone_geom_4326).unmask(OUTSIDE_ZONE_SENTINEL) เพื่อให้
            # พิกเซลนอกโซนจริงมีค่าตัวเลขที่เราควบคุมเอง (-8888) แต่ยืนยันจากรันจริงบนเครื่อง user ว่า
            # **ไม่ได้ผล** (n_pixels_outside_zone ยังเป็น 0 ทั้ง 2 zone เหมือนเดิม ทั้งที่โค้ดยืนยันแล้ว
            # ว่าอยู่ถูกที่ — สาเหตุที่แท้จริงไม่ชัดเจน อาจเป็นพฤติกรรม .clip()/.unmask() ฝั่ง GEE server
            # กับ MultiPolygon ซับซ้อนของ zone เหล่านี้) เปลี่ยนกลยุทธ์ไปตัดสิน "ในโซนจริงหรือไม่" ที่ฝั่ง
            # Python เองทั้งหมดแทน (rasterize zone_geom_native ทับ raster grid ใน
            # _classify_raster_local() โดยตรง — ดู docstring ของฟังก์ชันนั้น) เก็บ .clip() ไว้เฉยๆ
            # (ไม่มีผลเสีย อาจช่วยลด compute ฝั่ง GEE ได้บ้าง) แต่เลิกพึ่งพา unmask(OUTSIDE_ZONE_SENTINEL)
            # เพื่อ "สื่อสาร" ขอบเขตโซนแล้ว — ค่า pixel ของพิกเซลนอกโซนตอนนี้ไม่สำคัญอีกต่อไป (ถูกตัดออก
            # ด้วย local rasterize mask เสมอ ไม่ว่าจะมีค่าอะไรก็ตาม)
            zone_img = full_img.clip(zone_geom_4326)

            raw_tif_path = SAR_RASTER_OUTPUT_DIR / f"_download_{zone_label}_{year}.tif"
            classified_tif_path = SAR_RASTER_OUTPUT_DIR / f"crop_map_v3b_{zone_label}_{year}.tif"

            try:
                logger.info("%s: เริ่มดาวน์โหลด composite image (S2+S1, %d bands)...", zone_label, 86)
                _download_ee_image_geotiff(zone_img, zone_geom_4326, scale=20, out_path=raw_tif_path)
                logger.info("%s: ดาวน์โหลดสำเร็จ (%s) -- เริ่ม classify local", zone_label, raw_tif_path.name)

                classify_result = _classify_raster_local(raw_tif_path, rf, zone_geom_native=zdata["geom_native"])
                crop_area_ha = classify_result["crop_area_ha"]
                result["zone_crop_area_ha"][zone_label] = crop_area_ha
                result["raster_meta"][zone_label] = {
                    "pixel_area_ha": classify_result["pixel_area_ha"],
                    "n_pixels_valid": classify_result["n_pixels_valid"],
                    "n_pixels_outside_zone": classify_result["n_pixels_outside_zone"],
                    "classified_tif_path": str(classified_tif_path),
                }
                logger.info(
                    "%s: classify เสร็จ -- %d pixel ในโซนจริง (%d pixel นอกโซนถูกตัดออก) พื้นที่: %s",
                    zone_label, classify_result["n_pixels_valid"], classify_result["n_pixels_outside_zone"],
                    {k: round(v, 1) for k, v in crop_area_ha.items()},
                )

                # 2026-07-22 เพิ่ม — เฉพาะ zone_B: แบ่งพื้นที่ต่อ crop ตามอ่างที่ส่งน้ำเพิ่ม (ใช้
                # class_map/transform/pixel_area_ha ที่ classify ไปแล้วในหน่วยความจำ ไม่ classify ซ้ำ)
                # ห่อ try/except แยกต่างหาก -- พังไม่กระทบ zone_crop_area_ha หลักที่ใช้เป็น feature จริง
                if zone_label == "zone_B":
                    try:
                        reservoir_area_ha = compute_zone_b_reservoir_area_ha(
                            classify_result["class_map"], classify_result["transform"],
                            classify_result["pixel_area_ha"],
                        )
                        result["zone_b_reservoir_area_ha"] = reservoir_area_ha
                        logger.info(
                            "zone_B: แบ่งพื้นที่ต่ออ่างสำเร็จ -- %s",
                            {res: {k: round(v, 1) for k, v in crops.items()} for res, crops in reservoir_area_ha.items()},
                        )
                    except Exception as exc:
                        logger.exception("zone_B: คำนวณพื้นที่แยกตามอ่างล้มเหลว (ไม่กระทบ zone_crop_area_ha หลัก)")
                        result["errors"].append(f"zone_B reservoir area breakdown: {exc}")

                # เขียน class_map เป็น GeoTIFF แยก (uint8, nodata=255) -- ไฟล์เล็กกว่า raw composite
                # มาก เก็บไว้เป็น audit trail เดียวกับที่ Retrain3.ipynb cell 16 เขียน
                # crop_map_v3b_{year}.tif ไว้จริง
                import rasterio

                with rasterio.open(raw_tif_path) as src:
                    profile = src.profile.copy()
                profile.update(count=1, dtype="uint8", nodata=255)
                with rasterio.open(classified_tif_path, "w", **profile) as dst:
                    dst.write(classify_result["class_map"], 1)

                comparison = {}
                for crop, area_2020 in area_2020_ha.get(zone_label, {}).items():
                    area_new = crop_area_ha.get(crop, 0.0)
                    comparison[crop] = {
                        "area_2020_ha": area_2020,
                        "area_new_ha": round(area_new, 2),
                        "delta_pct": round((area_new - area_2020) / area_2020 * 100, 1) if area_2020 else None,
                    }
                result["comparison_vs_2020_hardcoded"][zone_label] = comparison

            except Exception as exc:
                logger.exception("%s: export/classify local ล้มเหลว", zone_label)
                result["errors"].append(f"{zone_label}: export/classify ล้มเหลว - {exc}")
            finally:
                # ลบ raw composite ที่ดาวน์โหลดมา (อาจใหญ่หลายสิบ MB ต่อ zone) เก็บไว้แค่
                # classified_tif_path (uint8 เล็กกว่ามาก) เป็น audit trail
                raw_tif_path.unlink(missing_ok=True)

        result["status"] = "ok" if not result["errors"] else ("partial" if result["zone_crop_area_ha"] else "failed")

    except Exception as exc:
        logger.exception("trigger_crop_classification() ล้มเหลว")
        result["errors"].append(str(exc))
        result["status"] = "failed"

    if result["status"] in ("ok", "partial"):
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(datetime.now().date().isoformat())

    return result
