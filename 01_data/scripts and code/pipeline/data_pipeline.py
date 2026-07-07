"""
data_pipeline.py
==================
โครง (skeleton) สำหรับ data pipeline ของโครงการบริหารจัดการน้ำ ตำบลแม่นาเรือ

ขั้นตอนหลัก:
  1. ดึงข้อมูลโทรมาตร (get_telemetry_data) — ดึงจาก API จริงถ้ามีการตั้งค่า URL, ไม่งั้น fallback เป็น mock data
  2. เช็คว่ามีภาพ SAR ใหม่หรือไม่ ถ้ามี -> trigger การจำแนกพืชใหม่ (check_new_sar_image, trigger_crop_classification)
  3. โหลดโมเดลที่มีอยู่ และทำนายด้วย input ล่าสุด (load_latest_model, run_prediction)
  4. บันทึกผลเป็น JSON ไปที่ 01_data/forecasting_results/latest.json (save_results)

การออกแบบสำคัญ:
  - รันแบบ standalone ได้เต็มรูปแบบ ไม่มีจุดใดรอ input จากคน (เหมาะสำหรับ cron / Task Scheduler)
  - ทุก step ห่อด้วย try/except ใน run_pipeline() — step ไหนพังจะ log แล้วข้ามไป ไม่ทำให้ทั้ง pipeline ค้าง/crash
  - log ทุกครั้งที่รันทั้งขึ้นจอ (console) และไฟล์ logs/pipeline_log.txt (ดู setup_logging())
  - save_results() เขียน latest.json แบบ overwrite ทุกรอบ (ไม่ append) พร้อม step_status
    ต่อขั้นตอนไว้ debug ทีหลังว่ารอบนั้น step ไหนสำเร็จ/ล้มเหลวบ้าง

สถานะการ implement:
  - get_telemetry_data(): ทำงานได้จริง (mock mode)
  - save_results(): ทำงานได้จริง เขียน latest.json overwrite ทุกรอบ
  - Water Demand (_wd_* helpers): ทำงานได้จริงแล้ว รัน two-stage prediction
    (stage1 classifier x stage2 CatBoost/LightGBM stack) ตาม
    01_data/scripts and code/Water_demand/feature_schema.md — ใช้ feature ที่คำนวณไว้ล่วงหน้า
    ใน ml_features_phase4.csv (static snapshot, ยังไม่ได้ต่อ ERA5/CHIRPS/MEI/crop-area
    แบบ real-time)
  - Reservoir Inflow (_ri_* helpers): ทำงานได้จริงแล้ว รัน hurdle prediction (stage1
    classifier กรอง zero-inflow -> stage2 CatBoost regressor ทำนาย delta) ตาม
    01_data/scripts and code/Reservoir_inflow/active/model_metadata.json ("final_prediction_logic")
    — feature (Q_in_t/Water_Level_t/Storage_S_t/DeltaS_t/%Full_t/Rain_obs_t/API_t) คำนวณสด
    จากไฟล์ "บัญชีน้ำ" รายเดือนจริงของอ่างเก็บน้ำแม่นาเรือ (01_data/Reservoirs/inflow/<year>/
    <year>_<month>_MNR.xlsx อัปเดตทุกเดือนโดยผู้ใช้ — ดู _ri_load_raw_monthly_data()) เป็น live
    data_source ("live_monthly_account_files") ถ้าโหลดไม่สำเร็จจะ fallback ไปใช้แถวล่าสุดของ
    Training_Values_Nofct_7day_Final.csv แทน (data_source "static_snapshot_training_csv")
    latest.json.forecasts.inflow.status เป็นหนึ่งใน 4 ค่า: "ok" (ทำนายสำเร็จ ข้อมูลไม่เก่าเกิน 3 วัน),
    "stale_data_warning" (ทำนายสำเร็จ แต่ข้อมูลเก่า 4-14 วัน — มักเกิดเพราะยังไม่อัปโหลดไฟล์เดือนใหม่),
    "stale_data_blocked" (ข้อมูลเก่าเกิน 14 วัน — ไม่ทำนายเลย .forecast.horizons เป็น null แต่ยังมี
    gap_days/as_of_date/staleness_message ให้ตรวจสอบ), หรือ "model_missing_pending_retrain"
    (หาไฟล์โมเดล/feature ไม่เจอทั้ง live และ fallback) — ดู _ri_compute_staleness()/
    RESERVOIR_STALE_WARNING_THRESHOLD_DAYS/RESERVOIR_STALE_BLOCKED_THRESHOLD_DAYS (เพิ่ม 2026-07-05)
  - load_latest_model()/build_feature_vector()/run_prediction(): แต่ละฟังก์ชันครอบคลุมทั้ง
    Water Demand และ Reservoir Inflow พร้อม error isolation แยกต่อระบบ (ระบบหนึ่งพังไม่กระทบ
    อีกระบบ)
  - check_new_sar_image, trigger_crop_classification: ยังเป็น skeleton (มีคอมเมนต์ "# TODO:" กำกับ)

หมายเหตุการกู้คืนไฟล์ (2026-07-07): ไฟล์นี้เคยถูกลบโดยไม่ได้ตั้งใจ (บั๊ก stale bash-mount cache
ระหว่างการแก้ไข) แล้วสร้างใหม่จากความเข้าใจ/บริบทของบทสนทนา + เทียบสอบกับ __pycache__/*.pyc ที่มี
อยู่ (bytecode cache ก่อนแก้ไขล่าสุด) — logic/threshold/ค่าคงที่ตรวจสอบแล้วว่าตรงกับต้นฉบับ แต่
คอมเมนต์บางจุดอาจถูกเรียบเรียงใหม่เล็กน้อย (ไม่กระทบพฤติกรรมของโปรแกรม)
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]

TELEMETRY_API_URL: Optional[str] = None
TELEMETRY_API_KEY: Optional[str] = None
TELEMETRY_TIMEOUT_SEC = 10

SAR_WATCH_DIR = PROJECT_ROOT / "01_data" / "gis" / "sar_incoming"
SAR_LAST_PROCESSED_MARKER = PROJECT_ROOT / "01_data" / "gis" / ".sar_last_processed"

WATER_DEMAND_MODEL_DIR = PROJECT_ROOT / "01_data" / "scripts and code" / "Water_demand" / "active"
WATER_DEMAND_FEATURES_CSV = WATER_DEMAND_MODEL_DIR / "ml_features_phase4.csv"

WD_HORIZON = 12
WD_ZONES = {"zone_A": "NIR_A_m3", "zone_B": "GIR_B_m3"}
WD_CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
WD_TARGET_LAGS = [1, 2, 3, 4]

RESERVOIR_INFLOW_MODEL_DIR = PROJECT_ROOT / "01_data" / "scripts and code" / "Reservoir_inflow" / "active"
RESERVOIR_INFLOW_METADATA_PATH = RESERVOIR_INFLOW_MODEL_DIR / "model_metadata.json"
RESERVOIR_INFLOW_TRAINING_CSV = RESERVOIR_INFLOW_MODEL_DIR / "Training_Values_Nofct_7day_Final.csv"

RESERVOIR_INFLOW_RAW_DIR = PROJECT_ROOT / "01_data" / "Reservoirs" / "inflow"

RESERVOIR_STORAGE_MAX_M3 = 1625463.7590197
RESERVOIR_API_K = 0.95

RESERVOIR_PLAUSIBLE_PERCENT_FULL_MAX = 105.0
# (แก้ไข 2026-07-07: เดิม %Full_t คำนวณเป็นสัดส่วน 0-1.05 ผิดสเกลจาก training data ที่เป็นเปอร์เซ็นต์
# 85-107 — แก้ %Full_t ให้คูณ 100 แล้ว (ดู _ri_load_raw_monthly_data) จึงต้องปรับ threshold นี้จาก
# 1.05 เป็น 105.0 ให้คงความหมายเดิม "plausible ไม่เกิน 105% เต็ม" ไว้เหมือนเดิม)

RESERVOIR_MONTH_NAME_TO_NUM = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

RESERVOIR_STALE_WARNING_THRESHOLD_DAYS = 3
RESERVOIR_STALE_BLOCKED_THRESHOLD_DAYS = 14

OUTPUT_PATH = PROJECT_ROOT / "01_data" / "forecasting_results" / "latest.json"

WEBSITE_DATA_COPY_PATH = PROJECT_ROOT / "03_website" / "assets" / "data" / "latest.json"

LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline_log.txt"

ERA5_GRIB_PYTHON_EXE = Path(
    r"C:\Program Files\ArcGIS\Pro\bin\Python\envs\era5-grib\python.exe"
)
ERA5T_WORKER_SCRIPT = SCRIPT_DIR / "era5t_worker.py"
ERA5T_OUTPUT_DIR = SCRIPT_DIR / "era5t_output"
ERA5T_SUBPROCESS_TIMEOUT_SEC = 600

ML_FEATURES_LIVE_CSV = SCRIPT_DIR / "ml_features_live.csv"
ML_FEATURES_LIVE_COLUMNS = [
    "run_timestamp", "as_of_date", "year", "week", "zone",
    "MEI", "MEI_lag4", "MEI_lag8", "mei_reporting_lag_risk", "mei_fetch_error",
    "P_mm_week", "P_eff_mm", "P_mm_week_lag1", "P_mm_week_lag2", "P_mm_week_lag4",
    "SPI_4", "drought_flag", "chirps_data_type", "chirps_n_days_in_week", "chirps_fetch_error",
    "ET0_mm_week", "T_mean", "RH_pct", "VPD_kPa", "u2_ms", "Rn_MJ",
    "era5t_n_days_in_week", "era5t_fetch_error",
    "AI_week", "AI_week_status",
]


def setup_logging() -> logging.Logger:
    """ตั้งค่า logging ให้เขียนทั้งขึ้นจอ (console) และลงไฟล์ logs/pipeline_log.txt (append ทุกครั้งที่รัน)"""
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


logger = setup_logging()


@dataclass
class TelemetryReading:
    """โครงสร้างข้อมูลดิบจากสถานีโทรมาตร 1 ชุด (ปรับ field ตาม schema จริงของ API)"""
    station_id: str = ""
    timestamp: str = ""
    rainfall_mm: Optional[float] = None
    water_level_m: Optional[float] = None
    temperature_c: Optional[float] = None
    raw: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    """ผลลัพธ์รวมของ pipeline หนึ่งรอบ สำหรับ serialize เป็น JSON"""
    run_timestamp: str
    telemetry: list[dict]
    telemetry_source: str
    sar_triggered: bool
    crop_classification: Optional[dict]
    predictions: dict
    model_version: Optional[str] = None
    status: str = "ok"
    errors: list[str] = field(default_factory=list)
    step_status: dict[str, str] = field(default_factory=dict)


def fetch_telemetry_from_api(
    api_url: str,
    api_key: Optional[str] = TELEMETRY_API_KEY,
    timeout: int = TELEMETRY_TIMEOUT_SEC,
) -> list[TelemetryReading]:
    """ดึงข้อมูลล่าสุดจากสถานีโทรมาตรผ่าน API จริง (ไม่ raise, คืน list ว่างถ้าล้มเหลว)"""
    logger.info("Fetching telemetry data from API: %s", api_url)
    try:
        readings: list[TelemetryReading] = []
        return readings
    except Exception as exc:
        logger.warning("เรียก telemetry API ไม่สำเร็จ (%s) — ข้ามรอบนี้ไปโดยไม่มีข้อมูลโทรมาตร", exc)
        return []


def generate_mock_telemetry(num_stations: int = 3) -> list[TelemetryReading]:
    """สร้างข้อมูลโทรมาตรจำลอง (mock) สำหรับใช้ตอนยังไม่ได้เชื่อม API จริง"""
    logger.warning("ใช้ mock data - ยังไม่ได้เชื่อม API จริง (TELEMETRY_API_URL is None)")
    now_iso = datetime.now(timezone.utc).isoformat()
    readings: list[TelemetryReading] = []

    for i in range(1, num_stations + 1):
        has_rain = random.random() < 0.3
        rainfall = round(random.uniform(0.5, 45.0), 1) if has_rain else 0.0

        readings.append(
            TelemetryReading(
                station_id=f"MOCK-{i:02d}",
                timestamp=now_iso,
                rainfall_mm=rainfall,
                water_level_m=round(random.uniform(0.5, 4.0), 2),
                temperature_c=round(random.uniform(20.0, 38.0), 1),
                raw={"mock": True, "note": "generated by generate_mock_telemetry()"},
            )
        )

    return readings


def get_telemetry_data() -> tuple[list[TelemetryReading], str]:
    """จุดเรียกหลักสำหรับดึงข้อมูลโทรมาตร — mock หรือ api ตาม TELEMETRY_API_URL"""
    if TELEMETRY_API_URL:
        readings = fetch_telemetry_from_api(TELEMETRY_API_URL, TELEMETRY_API_KEY)
        if readings:
            return readings, "api"
        logger.warning("API ไม่คืนข้อมูล หรือดึงไม่สำเร็จ — fallback ไปใช้ mock data แทน")
        return generate_mock_telemetry(), "mock"

    return generate_mock_telemetry(), "mock"


def check_new_sar_image(
    watch_dir: Path = SAR_WATCH_DIR,
    marker_path: Path = SAR_LAST_PROCESSED_MARKER,
) -> Optional[Path]:
    """เช็คว่ามีไฟล์ภาพ SAR ใหม่หรือไม่ (ยัง skeleton)"""
    logger.info("Checking for new SAR imagery in %s", watch_dir)
    new_image_path: Optional[Path] = None
    return new_image_path


def trigger_crop_classification(sar_image_path: Path) -> dict:
    """เรียกกระบวนการจำแนกพืชใหม่ (ยัง skeleton)"""
    logger.info("Triggering crop classification for %s", sar_image_path)
    classification_result: dict = {}
    return classification_result


def _wd_get_feature_cols(df, df_zone) -> list[str]:
    """คัดลอกตรงตัวจาก get_feature_cols() ใน combined_final_pipeline.py"""
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, WD_HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def _wd_get_clf_features(df_zone, target_col: str) -> list[str]:
    """คัดลอกตรงตัวจาก get_clf_features() ใน combined_final_pipeline.py"""
    lag_cols = [f"{target_col}_lag{k}" for k in WD_TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted = WD_CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]


def _wd_load_models(model_dir: Path = WATER_DEMAND_MODEL_DIR) -> dict:
    """โหลดโมเดล Water Demand ทั้งหมดจาก Water_demand/active/"""
    import joblib

    model_dir = Path(model_dir)
    logger.info("Loading Water Demand models from %s", model_dir)

    models = {
        "catboost": joblib.load(model_dir / "catboost_models.pkl"),
        "lightgbm": joblib.load(model_dir / "lightgbm_models.pkl"),
        "stage1_classifiers": joblib.load(model_dir / "stage1_classifiers.pkl"),
        "stage1_thresholds": joblib.load(model_dir / "stage1_thresholds.pkl"),
        "stack_weights": joblib.load(model_dir / "stack_weights.pkl"),
    }

    logger.info(
        "Loaded Water Demand models: catboost=%d lightgbm=%d stage1_classifiers=%d stack_weights=%d",
        len(models["catboost"]), len(models["lightgbm"]),
        len(models["stage1_classifiers"]), len(models["stack_weights"]),
    )
    return models


def _fetch_era5t_via_subprocess(
    as_of_date: Optional[Any] = None,
    timeout_sec: int = ERA5T_SUBPROCESS_TIMEOUT_SEC,
    grib_in: Optional[Path] = None,
    weekly: bool = False,
    grib_in_week: Optional[list] = None,
) -> dict:
    """
    เรียก era5t_worker.py ผ่าน subprocess โดยใช้ python.exe ของ conda environment "era5-grib"
    (มากับ ArcGIS Pro) แทนที่จะ import cdsapi/cfgrib ตรงๆ ใน process ของ data_pipeline.py เอง
    """
    as_of = as_of_date or datetime.now(timezone.utc).date()
    ERA5T_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if grib_in_week is not None:
        stems = "_".join(Path(p).stem for p in grib_in_week)
        out_json_path = ERA5T_OUTPUT_DIR / f"era5t_week_test_{stems}.json"
    elif grib_in is not None:
        out_json_path = ERA5T_OUTPUT_DIR / f"era5t_test_{Path(grib_in).stem}.json"
    elif weekly:
        out_json_path = ERA5T_OUTPUT_DIR / f"era5t_week_{as_of.isoformat()}.json"
    else:
        out_json_path = ERA5T_OUTPUT_DIR / f"era5t_{as_of.isoformat()}.json"

    result: dict = {
        "as_of_date": as_of.isoformat(),
        "python_exe": str(ERA5_GRIB_PYTHON_EXE),
        "worker_script": str(ERA5T_WORKER_SCRIPT),
        "out_json_path": str(out_json_path),
        "weekly": bool(weekly or grib_in_week is not None),
        "grib_in": str(grib_in) if grib_in is not None else None,
        "grib_in_week": [str(p) for p in grib_in_week] if grib_in_week is not None else None,
        "returncode": None,
        "stdout": None,
        "stderr": None,
        "worker_output": None,
        "fetch_error": None,
    }

    if not ERA5_GRIB_PYTHON_EXE.exists():
        msg = f"ไม่พบ python.exe ของ conda env era5-grib ที่ {ERA5_GRIB_PYTHON_EXE}"
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    if not ERA5T_WORKER_SCRIPT.exists():
        msg = f"ไม่พบ era5t_worker.py ที่ {ERA5T_WORKER_SCRIPT}"
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    if grib_in is not None and not Path(grib_in).exists():
        msg = f"grib_in ระบุไฟล์ที่ไม่มีอยู่จริง: {grib_in}"
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    if grib_in_week is not None:
        missing_gribs = [str(p) for p in grib_in_week if not Path(p).exists()]
        if missing_gribs:
            msg = f"grib_in_week ระบุไฟล์ที่ไม่มีอยู่จริง: {missing_gribs}"
            logger.error(msg)
            result["fetch_error"] = msg
            return result

    if grib_in_week is not None:
        cmd = [
            str(ERA5_GRIB_PYTHON_EXE),
            str(ERA5T_WORKER_SCRIPT),
            "--as-of-date", as_of.isoformat(),
            "--grib-in-week", *[str(p) for p in grib_in_week],
            "--out-json", str(out_json_path),
        ]
    elif grib_in is not None:
        cmd = [
            str(ERA5_GRIB_PYTHON_EXE),
            str(ERA5T_WORKER_SCRIPT),
            "--grib-in", str(grib_in),
            "--out-json", str(out_json_path),
        ]
    elif weekly:
        cmd = [
            str(ERA5_GRIB_PYTHON_EXE),
            str(ERA5T_WORKER_SCRIPT),
            "--as-of-date", as_of.isoformat(),
            "--out-json", str(out_json_path),
        ]
    else:
        cmd = [
            str(ERA5_GRIB_PYTHON_EXE),
            str(ERA5T_WORKER_SCRIPT),
            "--date", as_of.isoformat(),
            "--out-json", str(out_json_path),
        ]

    logger.info("เรียก ERA5T worker ผ่าน subprocess: %s", cmd)

    env_root = ERA5_GRIB_PYTHON_EXE.parent
    library_bin = env_root / "Library" / "bin"

    subprocess_env = os.environ.copy()
    subprocess_env["CONDA_PREFIX"] = str(env_root)
    subprocess_env["ECCODES_DIR"] = str(env_root)
    subprocess_env["PATH"] = f"{library_bin}{os.pathsep}{subprocess_env.get('PATH', '')}"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env=subprocess_env,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"subprocess ไป era5t_worker.py timeout หลังผ่านไป {timeout_sec} วินาที (CDS queue อาจช้าผิดปกติ)"
        logger.error(msg)
        result["fetch_error"] = msg
        result["stdout"] = exc.stdout
        result["stderr"] = exc.stderr
        return result
    except Exception as exc:
        msg = f"เรียก subprocess ไป era5t_worker.py ไม่สำเร็จ: {type(exc).__name__}: {exc}"
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    result["returncode"] = proc.returncode
    result["stdout"] = proc.stdout
    result["stderr"] = proc.stderr

    if proc.stdout:
        logger.info("era5t_worker.py stdout:\n%s", proc.stdout)
    if proc.stderr:
        logger.warning("era5t_worker.py stderr:\n%s", proc.stderr)

    if not out_json_path.exists():
        msg = (
            f"era5t_worker.py จบด้วย returncode={proc.returncode} แต่ไม่พบไฟล์ output {out_json_path} "
            f"— ดู stderr ด้านบนประกอบ"
        )
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    try:
        with open(out_json_path, encoding="utf-8") as f:
            worker_output = json.load(f)
    except Exception as exc:
        msg = f"อ่าน/parse {out_json_path} ไม่สำเร็จ: {type(exc).__name__}: {exc}"
        logger.error(msg)
        result["fetch_error"] = msg
        return result

    result["worker_output"] = worker_output

    if worker_output.get("fetch_error"):
        logger.error("era5t_worker.py รายงาน fetch_error ของตัวเอง: %s", worker_output["fetch_error"])
        result["fetch_error"] = worker_output["fetch_error"]
        return result

    if result["weekly"]:
        if proc.returncode != 0:
            logger.warning(
                "era5t_worker.py (weekly) returncode=%d — มักหมายถึง n_days_in_week=0 หรือบางวันข้อมูลไม่ครบ "
                "(ไม่ใช่ fetch_error เสมอไป ดู n_days_in_week/ET0_mm_week ใน worker_output ประกอบ)",
                proc.returncode,
            )
        logger.info(
            "ERA5T weekly feature เสร็จสิ้น (as_of=%s, iso_year=%s, iso_week=%s, n_days_in_week=%s, "
            "ET0_mm_week=%s)",
            as_of.isoformat(),
            worker_output.get("iso_year"), worker_output.get("iso_week"),
            worker_output.get("n_days_in_week"), worker_output.get("ET0_mm_week"),
        )
        if not worker_output.get("n_days_in_week"):
            logger.warning(
                "ERA5T weekly: n_days_in_week=%s (ยังไม่มีวันไหนของสัปดาห์นี้พร้อมใช้จริง) — "
                "ET0_mm_week ไม่ควรถูกนำไปใช้เป็นค่าจริง แม้ fetch_error ของ worker เองจะเป็น None ก็ตาม",
                worker_output.get("n_days_in_week"),
            )
    else:
        if proc.returncode != 0:
            logger.warning(
                "era5t_worker.py (single-day) returncode=%d (อาจมาจาก missing_variables warning) — "
                "ดู worker_output ประกอบ",
                proc.returncode,
            )
        logger.info(
            "ERA5T single-day feature ดึงสำเร็จ (as_of=%s, valid_time=%s, n_variables=%d)",
            as_of.isoformat(), worker_output.get("valid_time"), len(worker_output.get("variables") or {}),
        )

    return result


def _append_ml_features_live(rows: list, csv_path: Path = ML_FEATURES_LIVE_CSV) -> None:
    """Append แถวใหม่เข้า ml_features_live.csv (เขียน header เฉพาะครั้งแรก)"""
    import csv

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ML_FEATURES_LIVE_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col) for col in ML_FEATURES_LIVE_COLUMNS})


def _fetch_climate_features_step(as_of_date: Optional[Any] = None) -> dict:
    """
    Integration step ที่เรียกต่อจาก Step 1 (telemetry) ใน run_pipeline() — เรียก MEI -> CHIRPS ->
    ERA5T ตามลำดับ เก็บผลลัพธ์รวมกัน คำนวณ AI_week ต่อ zone แล้ว append เข้า ml_features_live.csv
    ออกแบบให้ "ไม่ raise" — ห่อแต่ละการเรียกด้วย try/except แยกกัน
    """
    as_of = as_of_date or datetime.now(timezone.utc).date()
    result: dict = {
        "as_of_date": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
        "mei": None,
        "chirps": {"zone_A": None, "zone_B": None},
        "era5t": None,
        "ai_week": {"zone_A": {"value": None, "status": None}, "zone_B": {"value": None, "status": None}},
        "rows_appended": 0,
        "data_status": "ok",
        "prediction_readiness": {},
        "errors": [],
    }

    mei_result = None
    try:
        import mei_feature
        mei_result = mei_feature.get_mei_feature(as_of_date=as_of)
        if mei_result.get("fetch_error"):
            logger.warning(
                "MEI feature ดึงไม่สำเร็จ (fetch_error=%s) — ค่า MEI จะเป็น None ในแถวที่ append",
                mei_result["fetch_error"],
            )
    except Exception as exc:
        logger.exception("mei_feature.get_mei_feature() raise ออกมาโดยไม่คาดคิด (ควร \"ไม่ raise\" อยู่แล้วปกติ)")
        result["errors"].append("mei_feature: " + str(exc))
    result["mei"] = mei_result

    chirps_results = {}
    for zone in ("zone_A", "zone_B"):
        try:
            import chirps_feature
            chirps_result = chirps_feature.get_chirps_feature(zone=zone, as_of_date=as_of)
            if chirps_result.get("fetch_error"):
                logger.warning(
                    "CHIRPS feature (%s) ดึงไม่สำเร็จ (fetch_error=%s)",
                    zone, chirps_result["fetch_error"],
                )
        except Exception as exc:
            logger.exception("chirps_feature.get_chirps_feature(zone=%s) raise ออกมาโดยไม่คาดคิด", zone)
            result["errors"].append("chirps_feature[" + zone + "]: " + str(exc))
            chirps_result = None
        chirps_results[zone] = chirps_result
    result["chirps"] = chirps_results

    era5t_result = None
    try:
        era5t_result = _fetch_era5t_via_subprocess(as_of_date=as_of, weekly=True)
        if era5t_result.get("fetch_error"):
            logger.warning("ERA5T feature ดึงไม่สำเร็จ (fetch_error=%s)", era5t_result["fetch_error"])
    except Exception as exc:
        logger.exception("_fetch_era5t_via_subprocess(weekly=True) raise ออกมาโดยไม่คาดคิด")
        result["errors"].append("era5t: " + str(exc))
    result["era5t"] = era5t_result

    worker_output = (era5t_result or {}).get("worker_output") or {}
    n_days_in_week = worker_output.get("n_days_in_week")
    et0_mm_week = worker_output.get("ET0_mm_week")
    era5t_fetch_error = (era5t_result or {}).get("fetch_error")
    if not n_days_in_week:
        et0_mm_week = None
        if era5t_fetch_error is None:
            era5t_fetch_error = (
                "n_days_in_week=" + str(n_days_in_week) +
                " — ยังไม่มีวันไหนของสัปดาห์นี้ที่ ERA5T ดึงข้อมูลได้จริง (มักเกิดตอนต้นสัปดาห์ "
                "ที่ ERA5T latency ยังไม่ทันข้อมูลของวันก่อนหน้า) — ET0_mm_week/AI_week ของรอบนี้จึงไม่พร้อมใช้"
            )
            logger.warning("ERA5T weekly (integration step): %s", era5t_fetch_error)

    ai_week_results = {}
    for zone in ("zone_A", "zone_B"):
        chirps_z = chirps_results.get(zone) or {}
        p_mm_week = chirps_z.get("p_mm_week")

        reasons = []
        if et0_mm_week is None and p_mm_week is None:
            value, status = None, "AI_week unavailable (ทั้ง ET0_mm_week และ P_mm_week ไม่พร้อมใช้)"
        elif et0_mm_week is None:
            value, status = None, "AI_week unavailable (ET0_mm_week ไม่พร้อมใช้ — ERA5T ของสัปดาห์นี้ยังไม่ครบ)"
        elif p_mm_week is None:
            value, status = None, "AI_week unavailable (P_mm_week ไม่พร้อมใช้ — CHIRPS ของสัปดาห์นี้ยังไม่ครบ)"
        elif p_mm_week == 0:
            value, status = None, "AI_week unavailable (P_mm_week = 0, หารด้วยศูนย์ไม่ได้)"
        else:
            value = et0_mm_week / p_mm_week
            if chirps_z.get("data_type") == "prelim":
                reasons.append("CHIRPS เป็นข้อมูล prelim (ยังไม่ใช่ final)")
            if chirps_z.get("is_partial_week"):
                reasons.append("CHIRPS ของสัปดาห์นี้ยังไม่ครบ 7 วัน (as_of ไม่ใช่วันอาทิตย์)")
            if n_days_in_week is not None and n_days_in_week != 7:
                reasons.append("ERA5T มีข้อมูลแค่ " + str(n_days_in_week) + "/7 วันของสัปดาห์")
            status = "low_confidence: " + "; ".join(reasons) if reasons else "ok"

        ai_week_results[zone] = {"value": value, "status": status}
    result["ai_week"] = ai_week_results

    as_of_year, as_of_week, _ = as_of.isocalendar() if hasattr(as_of, "isocalendar") else (None, None, None)
    rows_to_append = []
    for zone in ("zone_A", "zone_B"):
        chirps_z = chirps_results.get(zone) or {}
        ai_week_z = ai_week_results.get(zone) or {}
        row = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of_date": result["as_of_date"],
            "year": as_of_year,
            "week": as_of_week,
            "zone": zone,
            "MEI": (mei_result or {}).get("mei_current"),
            "MEI_lag4": (mei_result or {}).get("mei_lag4"),
            "MEI_lag8": (mei_result or {}).get("mei_lag8"),
            "mei_reporting_lag_risk": (mei_result or {}).get("mei_reporting_lag_risk"),
            "mei_fetch_error": (mei_result or {}).get("fetch_error"),
            "P_mm_week": chirps_z.get("p_mm_week"),
            "P_eff_mm": chirps_z.get("p_eff_mm"),
            "P_mm_week_lag1": chirps_z.get("p_mm_week_lag1"),
            "P_mm_week_lag2": chirps_z.get("p_mm_week_lag2"),
            "P_mm_week_lag4": chirps_z.get("p_mm_week_lag4"),
            "SPI_4": chirps_z.get("spi_4"),
            "drought_flag": chirps_z.get("drought_flag"),
            "chirps_data_type": chirps_z.get("data_type"),
            "chirps_n_days_in_week": chirps_z.get("n_days_in_week"),
            "chirps_fetch_error": chirps_z.get("fetch_error"),
            "ET0_mm_week": et0_mm_week,
            "T_mean": worker_output.get("T_mean"),
            "RH_pct": worker_output.get("RH_pct"),
            "VPD_kPa": worker_output.get("VPD_kPa"),
            "u2_ms": worker_output.get("u2_ms"),
            "Rn_MJ": worker_output.get("Rn_MJ"),
            "era5t_n_days_in_week": n_days_in_week,
            "era5t_fetch_error": era5t_fetch_error,
            "AI_week": ai_week_z.get("value"),
            "AI_week_status": ai_week_z.get("status"),
        }
        rows_to_append.append(row)

    try:
        _append_ml_features_live(rows_to_append)
        result["rows_appended"] = len(rows_to_append)
    except Exception as exc:
        logger.exception("append เข้า ml_features_live.csv ไม่สำเร็จ")
        result["errors"].append("append_ml_features_live: " + str(exc))

    prediction_readiness = {}
    for zone in ("zone_A", "zone_B"):
        try:
            readiness = _wd_select_climate_features_for_prediction(zone=zone, as_of_date=as_of)
        except Exception as exc:
            logger.exception("_wd_select_climate_features_for_prediction(zone=%s) raise ออกมาโดยไม่คาดคิด", zone)
            readiness = {"zone": zone, "status": "blocked_insufficient_data", "row": None,
                         "selected_year": None, "selected_week": None,
                         "current_year": as_of_year, "current_week": as_of_week,
                         "note": "เกิดข้อผิดพลาดไม่คาดคิดตอนเลือกข้อมูล: " + str(exc)}
        prediction_readiness[zone] = readiness
        if readiness["status"] == "blocked_insufficient_data":
            logger.warning("Climate prediction readiness (%s): blocked_insufficient_data — %s", zone, readiness.get("note"))
        elif readiness["status"] == "fallback":
            logger.warning("Climate prediction readiness (%s): fallback — %s", zone, readiness.get("note"))
        else:
            logger.info(
                "Climate prediction readiness (%s): ok (as_of=%s-W%02d ตรงกับสัปดาห์ปัจจุบัน)",
                zone, readiness.get("selected_year"), readiness.get("selected_week") or 0,
            )
    result["prediction_readiness"] = prediction_readiness

    any_fetch_error = (
        (mei_result or {}).get("fetch_error") is not None
        or any((c or {}).get("fetch_error") is not None for c in chirps_results.values())
        or era5t_fetch_error is not None
    )
    any_ai_not_ok = any(v.get("status") != "ok" for v in ai_week_results.values())
    if result["errors"]:
        result["data_status"] = "failed"
    elif any_fetch_error or any_ai_not_ok:
        result["data_status"] = "partial"
    else:
        result["data_status"] = "ok"

    logger.info(
        "Climate features step เสร็จสิ้น (as_of=%s, data_status=%s): MEI fetch_error=%s, "
        "CHIRPS zone_A/B fetch_error=%s/%s, ERA5T n_days_in_week=%s fetch_error=%s, "
        "AI_week zone_A=%s (%s), zone_B=%s (%s), rows_appended=%d",
        result["as_of_date"], result["data_status"],
        (mei_result or {}).get("fetch_error"),
        (chirps_results.get("zone_A") or {}).get("fetch_error"),
        (chirps_results.get("zone_B") or {}).get("fetch_error"),
        n_days_in_week, era5t_fetch_error,
        ai_week_results["zone_A"]["value"], ai_week_results["zone_A"]["status"],
        ai_week_results["zone_B"]["value"], ai_week_results["zone_B"]["status"],
        result["rows_appended"],
    )

    return result


def _wd_select_climate_features_for_prediction(zone: str, as_of_date: Optional[Any] = None, csv_path: Path = ML_FEATURES_LIVE_CSV) -> dict:
    """
    เลือกแถวข้อมูล climate ที่ "ปลอดภัย" พอจะป้อนเข้าโมเดล Water Demand จริงในอนาคต — ต้องครบ
    7/7 วันพอดี (era5t_n_days_in_week==7 และ chirps_n_days_in_week==7) ไม่ยอมรับ partial-week
    ไม่ว่ากรณีใด (out-of-distribution เทียบกับตอน train)

    คืนค่า dict {zone, status: ok|fallback|blocked_insufficient_data, row, selected_year,
    selected_week, current_year, current_week, note}

    หมายเหตุ: ยังไม่ได้ถูกเรียกจาก _wd_build_feature_vector()/_wd_run_prediction() จริง — ทั้งสอง
    ยังคงอ่านจาก ml_features_phase4.csv แบบ static เหมือนเดิม
    """
    as_of = as_of_date or datetime.now(timezone.utc).date()
    current_year, current_week, _ = as_of.isocalendar()

    def _to_int(v: Any) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {
            "zone": zone, "status": "blocked_insufficient_data", "row": None,
            "selected_year": None, "selected_week": None,
            "current_year": current_year, "current_week": current_week,
            "note": "ยังไม่พบ " + str(csv_path) + " เลย (pipeline ยังไม่เคย append สำเร็จสักครั้ง) — ไม่มีประวัติให้เลือกใช้",
        }

    import csv as csv_module

    best_row = None
    best_key = None
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv_module.DictReader(f):
            if r.get("zone") != zone:
                continue
            if _to_int(r.get("era5t_n_days_in_week")) != 7 or _to_int(r.get("chirps_n_days_in_week")) != 7:
                continue
            year_i = _to_int(r.get("year"))
            week_i = _to_int(r.get("week"))
            if year_i is None or week_i is None:
                continue
            key = (year_i, week_i)
            if best_key is None or key > best_key:
                best_key = key
                best_row = r

    if best_row is None:
        return {
            "zone": zone, "status": "blocked_insufficient_data", "row": None,
            "selected_year": None, "selected_week": None,
            "current_year": current_year, "current_week": current_week,
            "note": (
                "ไม่มีสัปดาห์ไหนใน " + str(csv_path) + " (zone=" + zone + ") ที่ ERA5T และ CHIRPS "
                "ครบ 7/7 วันพร้อมกันเลย แม้แต่สัปดาห์เดียว — block การทำนายไว้ก่อน "
                "ไม่ใช้ข้อมูลที่ไม่ครบป้อนเข้าโมเดลไม่ว่ากรณีใด"
            ),
        }

    selected_year, selected_week = best_key
    if (selected_year, selected_week) == (current_year, current_week):
        status, note = "ok", None
    else:
        status = "fallback"
        note = (
            "climate data as_of สัปดาห์ " + str(selected_year) + "-W" + f"{selected_week:02d}" +
            " ไม่ใช่สัปดาห์ปัจจุบัน (" + str(current_year) + "-W" + f"{current_week:02d}" +
            ") เพราะสัปดาห์ปัจจุบันยังไม่มีข้อมูลครบ 7/7 วัน — ใช้สัปดาห์ล่าสุดที่ปิดแล้วและครบข้อมูลจริงแทน"
        )

    return {
        "zone": zone, "status": status, "row": best_row,
        "selected_year": selected_year, "selected_week": selected_week,
        "current_year": current_year, "current_week": current_week,
        "note": note,
    }


def _wd_build_feature_vector() -> dict:
    """
    เตรียม feature vector สำหรับ Water Demand โดยใช้ feature_schema.md เป็นอ้างอิงเดียว ใช้ค่าที่
    คำนวณไว้ล่วงหน้าแล้วใน ml_features_phase4.csv โดยดึงแถวล่าสุดที่มี feature ครบต่อ zone มาใช้
    (static snapshot ไม่ใช่ live — MEI/CHIRPS/ERA5T ทดสอบสำเร็จแล้วทั้ง 3 แหล่งแต่ยังไม่ wire เข้ามา)
    """
    import pandas as pd

    logger.info("Building feature vector from %s", WATER_DEMAND_FEATURES_CSV)
    if not WATER_DEMAND_FEATURES_CSV.exists():
        raise FileNotFoundError("ไม่พบไฟล์ feature: " + str(WATER_DEMAND_FEATURES_CSV))

    df = pd.read_csv(WATER_DEMAND_FEATURES_CSV)

    results = {}
    for zone, target_col in WD_ZONES.items():
        df_zone = df[df["zone"] == zone]
        if df_zone.empty:
            raise ValueError("ไม่พบข้อมูล zone=" + zone + " ใน " + str(WATER_DEMAND_FEATURES_CSV))

        df_zone = df_zone.sort_values(["year", "week"])
        reg_feats = _wd_get_feature_cols(df, df_zone)
        clf_feats = _wd_get_clf_features(df_zone, target_col)

        subset = df_zone.dropna(subset=reg_feats)
        if subset.empty:
            raise ValueError(
                "ไม่มีแถวที่feature ครบ (ไม่มี NaN) สำหรับ zone=" + zone + " — ตรวจสอบ warm-up period ของ lag/rolling"
            )

        latest_row = subset.iloc[-1]
        as_of_year = int(latest_row["year"])
        as_of_week = int(latest_row["week"])

        X_reg = latest_row[reg_feats].to_numpy(dtype=float).reshape(1, -1)
        X_clf = latest_row[clf_feats].to_numpy(dtype=float).reshape(1, -1)

        results[zone] = {
            "target_col": target_col,
            "as_of_year": as_of_year,
            "as_of_week": as_of_week,
            "X_reg": X_reg,
            "X_clf": X_clf,
            "reg_feature_count": len(reg_feats),
            "clf_feature_count": len(clf_feats),
        }
        logger.info(
            "Zone %s: as_of=%d-W%02d, reg_features=%d, clf_features=%d",
            zone, as_of_year, as_of_week, len(reg_feats), len(clf_feats),
        )

    return results


def _wd_run_prediction(model: dict, features: dict) -> tuple[Optional[dict], Optional[dict]]:
    """
    รัน two-stage prediction สำหรับ Water Demand (zone A/B):
      1. Stage 1 classifier  -> prob      = P(demand > 0)
      2. Stage 2 regressor   -> magnitude = w_cat * catboost.predict(X_reg) + w_lgb * lightgbm.predict(X_reg), clip(min=0)
      3. Final                -> final    = prob * magnitude
    คืนค่า tuple (zone_a_result, zone_b_result)
    """
    results = {}
    for zone in ("zone_A", "zone_B"):
        feat = features.get(zone)
        if feat is None:
            results[zone] = None
            continue

        target_col = feat["target_col"]
        h = 1
        key = (zone, h)

        clf = model["stage1_classifiers"].get(key)
        cat_model = model["catboost"].get(key)
        lgb_model = model["lightgbm"].get(key)
        weights = model["stack_weights"].get(key)

        if clf is None or cat_model is None or lgb_model is None or weights is None:
            results[zone] = None
            continue

        prob_active = float(clf.predict_proba(feat["X_clf"])[:, 1][0])

        cat_pred = float(cat_model.predict(feat["X_reg"])[0])
        lgb_pred = float(lgb_model.predict(feat["X_reg"])[0])
        magnitude = weights["w_cat"] * cat_pred + weights["w_lgb"] * lgb_pred
        magnitude = max(magnitude, 0.0)

        final = prob_active * magnitude

        results[zone] = {
            "as_of": {"year": feat["as_of_year"], "week": feat["as_of_week"]},
            "unit": "m3_per_week",
            "horizons": {
                "h1": {
                    "probability_active": round(prob_active, 4),
                    "magnitude_m3": round(magnitude, 2),
                    "final_m3": round(final, 2),
                },
            },
        }

    return results.get("zone_A"), results.get("zone_B")


def _ri_load_metadata() -> dict:
    """โหลด model_metadata.json ของ Reservoir Inflow — แหล่งความจริงเดียวสำหรับ feature_cols/targets/threshold logic"""
    if not RESERVOIR_INFLOW_METADATA_PATH.exists():
        raise FileNotFoundError("ไม่พบ model_metadata.json ที่ " + str(RESERVOIR_INFLOW_METADATA_PATH))
    with open(RESERVOIR_INFLOW_METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _ri_load_models(model_dir: Path = RESERVOIR_INFLOW_MODEL_DIR) -> dict:
    """
    โหลดโมเดล Reservoir Inflow ตาม model_metadata.json — โหลดเฉพาะไฟล์ deployment จริงตามที่
    deployment_model_choice.json เลือกไว้ (CatBoost ทุก horizon) ไม่โหลด
    stage2_regressors_all_models.pkl ซึ่งต้องพึ่ง xgboost/lightgbm เพิ่มโดยไม่จำเป็น
    """
    import joblib

    model_dir = Path(model_dir)
    logger.info("Loading Reservoir Inflow models from %s", model_dir)

    metadata = _ri_load_metadata()
    stage1_classifiers = joblib.load(model_dir / "stage1_classifiers.pkl")
    stage1_thresholds = joblib.load(model_dir / "stage1_thresholds.pkl")
    stage2_regressors = joblib.load(model_dir / "deployment_stage2_regressors.pkl")

    models = {
        "metadata": metadata,
        "stage1_classifiers": stage1_classifiers,
        "stage1_thresholds": stage1_thresholds,
        "stage2_regressors": stage2_regressors,
    }

    logger.info(
        "Loaded Reservoir Inflow models: stage1_classifiers=%d stage1_thresholds=%d stage2_regressors=%d",
        len(models["stage1_classifiers"]), len(models["stage1_thresholds"]), len(models["stage2_regressors"]),
    )
    return models


def _ri_compute_staleness(as_of_date: Any, run_date: Optional[Any] = None) -> dict:
    """
    คำนวณ gap_days = (วันที่รันจริง) - (as_of_date ของแถวข้อมูลล่าสุดที่ใช้ทำนาย) แล้วจัดสถานะ:
      gap_days <= 3   -> "ok"
      gap_days 4-14   -> "stale_data_warning"
      gap_days > 14   -> "stale_data_blocked"
    """
    if isinstance(as_of_date, str):
        as_of = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    elif hasattr(as_of_date, "date") and not hasattr(as_of_date, "isocalendar"):
        as_of = as_of_date.date()
    else:
        as_of = as_of_date

    run = run_date or datetime.now(timezone.utc).date()
    if isinstance(run, str):
        run = datetime.strptime(run, "%Y-%m-%d").date()
    elif hasattr(run, "date") and not hasattr(run, "isocalendar"):
        run = run.date()

    gap_days = (run - as_of).days

    if gap_days <= RESERVOIR_STALE_WARNING_THRESHOLD_DAYS:
        return {
            "gap_days": gap_days, "run_date": run.isoformat(),
            "staleness_status": "ok", "staleness_message": None,
        }
    elif gap_days <= RESERVOIR_STALE_BLOCKED_THRESHOLD_DAYS:
        message = (
            "ข้อมูลที่ใช้ทำนาย (as_of=" + as_of.isoformat() + ") เก่ากว่าวันที่รันจริง (" +
            run.isoformat() + ") อยู่ " + str(gap_days) +
            " วัน — มักเกิดเพราะยังไม่มีการอัปโหลด ไฟล์ 'บัญชีน้ำ' ของเดือนใหม่ "
            "(ดู ARCHITECTURE.md > Manual Dependencies) ยังคำนวณผลทำนายให้ตามปกติ "
            "แต่ควรพิจารณาด้วยความระมัดระวังเพิ่มขึ้น"
        )
        return {
            "gap_days": gap_days, "run_date": run.isoformat(),
            "staleness_status": "stale_data_warning", "staleness_message": message,
        }
    else:
        message = (
            "ข้อมูลที่มีล่าสุด (as_of=" + as_of.isoformat() + ") ถึง " + run.isoformat() + " อยู่ " +
            str(gap_days) + " วัน (เกิน " + str(RESERVOIR_STALE_BLOCKED_THRESHOLD_DAYS) +
            " วัน) — บล็อกการทำนายไว้ก่อน ไม่ใช้ข้อมูลที่เก่าเกินไปทำนาย "
            "(ดู ARCHITECTURE.md > Manual Dependencies — ตรวจสอบว่ามีการอัปโหลดไฟล์ 'บัญชีน้ำ' "
            "เดือนล่าสุดหรือยัง)"
        )
        return {
            "gap_days": gap_days, "run_date": run.isoformat(),
            "staleness_status": "stale_data_blocked", "staleness_message": message,
        }


def _ri_load_raw_monthly_data(raw_dir: Path = RESERVOIR_INFLOW_RAW_DIR):
    """
    โหลดและรวมไฟล์ "บัญชีน้ำ" รายเดือนทั้งหมด (เช่น 01_data/Reservoirs/inflow/2026/2026_June_MNR.xlsx)
    เป็นข้อมูลดิบรายวันต่อเนื่อง แล้วคำนวณ 7 feature ด้วยสูตรที่คัดลอกตรงตัวจาก sheet
    "Training_Ready"/"Data_Dictionary" ของ inflow_ml_training_template_3d.xlsx:

      Q_in_t        = คอลัมน์ "Inflow (M3)" ตรงตัว
      Water_Level_t = คอลัมน์ "Water Level (MSL)" ตรงตัว
      Storage_S_t   = คอลัมน์ "Water Volume (M3)" ตรงตัว
      DeltaS_t      = Storage_S_t(แถวนี้) - Storage_S_t(แถวก่อนหน้าที่มีข้อมูล)
      %Full_t       = Storage_S_t / RESERVOIR_STORAGE_MAX_M3 * 100 (หน่วยเปอร์เซ็นต์ ตรงกับสเกล
                      ที่ training data ใช้ 85-107 — แก้ไข 2026-07-05→2026-07-07 จากบั๊ก scale-mismatch)
      Rain_obs_t    = คอลัมน์ "Cumulative rainfall over the past 24 hours (mm.)" ตรงตัว
      API_t         = self-initializing: แถวแรกสุด = Rain_obs_t, แถวถัดไป =
                      RESERVOIR_API_K * API(แถวก่อนหน้า) + Rain_obs_t(แถวนี้)

    คืนค่าเป็น DataFrame เรียงตามวันที่ พร้อมคอลัมน์ feature ทั้ง 7 + "valid"
    """
    import re
    import pandas as pd

    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError("ไม่พบโฟลเดอร์ข้อมูลดิบรายเดือน: " + str(raw_dir))

    pattern = re.compile(r"^(\d{4})_([A-Za-z]+)_MNR\.xlsx$")
    xlsx_files = sorted(raw_dir.glob("*/*.xlsx"))
    if not xlsx_files:
        raise FileNotFoundError("ไม่พบไฟล์ <year>_<month>_MNR.xlsx ใน " + str(raw_dir) + "/<year>/")

    rows = []
    for fpath in xlsx_files:
        m = pattern.match(fpath.name)
        if not m:
            logger.warning("ข้ามไฟล์ที่ชื่อไม่ตรง pattern <year>_<month>_MNR.xlsx: %s", fpath.name)
            continue
        year_str, month_name = m.group(1), m.group(2)
        month_num = RESERVOIR_MONTH_NAME_TO_NUM.get(month_name)
        if month_num is None:
            logger.warning("ไม่รู้จักชื่อเดือน '%s' ในไฟล์ %s — ข้ามไฟล์นี้", month_name, fpath.name)
            continue

        raw_preview = pd.read_excel(fpath, sheet_name="บัญชีน้ำ", header=None, nrows=15)
        header_row = None
        for i in range(len(raw_preview)):
            if raw_preview.iloc[i].astype(str).str.strip().eq("Date").any():
                header_row = i
                break
        if header_row is None:
            logger.warning("หา header แถว 'Date' ไม่เจอใน %s — ข้ามไฟล์นี้", fpath.name)
            continue

        df_month = pd.read_excel(fpath, sheet_name="บัญชีน้ำ", header=header_row)
        df_month.columns = [str(c).strip() for c in df_month.columns]

        date_col = next((c for c in df_month.columns if c == "Date"), None)
        level_col = next((c for c in df_month.columns if "Water Level" in c), None)
        storage_col = next((c for c in df_month.columns if "Water Volume" in c), None)
        inflow_col = next((c for c in df_month.columns if c.startswith("Inflow")), None)
        rain_col = next((c for c in df_month.columns if "Cumulative rainfall" in c), None)

        if date_col is None:
            continue

        # หมายเหตุ (แก้ไข 2026-07-07): คอลัมน์ "Date" ในไฟล์จริงเก็บแค่ "วันที่ในเดือน" (1, 2, 3, ...)
        # ไม่ใช่ full date — ต้องประกอบวันที่จริงเองจาก year_str/month_num ที่ได้จากชื่อไฟล์
        # (ยืนยันจากการเปิดไฟล์จริงตรวจสอบ: row header อยู่ที่ index 4, แถวข้อมูลคอลัมน์ Date มีค่า
        # เป็นเลขวันที่ (day-of-month) ธรรมดา)
        day_numeric = pd.to_numeric(df_month[date_col], errors="coerce")
        valid_mask = day_numeric.notna()

        for idx in df_month.index[valid_mask]:
            day_int = int(day_numeric.loc[idx])
            try:
                date_val = pd.Timestamp(year=int(year_str), month=month_num, day=day_int)
            except (ValueError, TypeError):
                continue
            rows.append({
                "date": date_val,
                "water_level": df_month.loc[idx, level_col] if level_col else None,
                "storage": df_month.loc[idx, storage_col] if storage_col else None,
                "inflow": df_month.loc[idx, inflow_col] if inflow_col else None,
                "rain_mm": df_month.loc[idx, rain_col] if rain_col else None,
                "source_file": fpath.name,
            })

    if not rows:
        raise ValueError("ไม่มีแถวข้อมูลที่อ่านได้จากไฟล์รายเดือนใน " + str(raw_dir))

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset="date", keep="last")
    df = df.sort_values("date").reset_index(drop=True)

    df["Q_in_t"] = df["inflow"]
    df["Water_Level_t"] = df["water_level"]
    df["Storage_S_t"] = df["storage"]
    df["DeltaS_t"] = df["Storage_S_t"].diff()
    # (แก้ไข 2026-07-07: เดิมคำนวณเป็นสัดส่วน 0-1.05 ไม่ตรงกับ training data ที่เก็บเป็นเปอร์เซ็นต์
    # 85-107 — คูณ 100 ให้สเกลตรงกัน มิฉะนั้นค่าที่ป้อนเข้าโมเดล live จะ out-of-distribution ทุกครั้ง)
    df["%Full_t"] = df["Storage_S_t"] / RESERVOIR_STORAGE_MAX_M3 * 100
    df["Rain_obs_t"] = df["rain_mm"]

    api_values = []
    api_t_reset_dates = []
    api_t_undefined_dates = []
    prev_api = None
    for idx, row in df.iterrows():
        rain = row["Rain_obs_t"]
        date_iso = row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"])
        if pd.isna(rain):
            if prev_api is None:
                logger.warning("API_t คำนวณไม่ได้ที่ %s เพราะ Rain_obs_t เป็น NaN (ต้นฉบับไม่มี logic รองรับ)", date_iso)
                api_values.append(float("nan"))
                api_t_undefined_dates.append(date_iso)
                continue
            else:
                api_values.append(float("nan"))
                api_t_undefined_dates.append(date_iso)
                continue
        if prev_api is None:
            api_val = rain
        elif pd.isna(prev_api):
            logger.warning(
                "API_t reset (fallback ที่ไม่ตรงสูตรต้นฉบับ) ที่ %s เพราะวันก่อนหน้าไม่มี "
                "ข้อมูลฝน (Rain_obs_t เป็น NaN) — ใช้ rain ของวันนี้ตรงๆ แทนการสะสมประวัติ",
                date_iso,
            )
            api_val = rain
            api_t_reset_dates.append(date_iso)
        else:
            api_val = RESERVOIR_API_K * prev_api + rain
        api_values.append(api_val)
        prev_api = api_val

    df["API_t"] = api_values

    feature_cols_clean = ["Q_in_t", "Water_Level_t", "Storage_S_t", "DeltaS_t", "%Full_t", "Rain_obs_t", "API_t"]
    complete = df[feature_cols_clean].notna().all(axis=1)
    plausible = df["%Full_t"].le(RESERVOIR_PLAUSIBLE_PERCENT_FULL_MAX)
    df["valid"] = complete & plausible

    df.attrs["api_t_undefined_dates"] = api_t_undefined_dates
    df.attrs["api_t_reset_dates"] = api_t_reset_dates
    if api_t_reset_dates:
        logger.warning(
            "รวม %d วันที่ API_t ใช้ fallback logic (reset) ที่ไม่ตรงสูตรต้นฉบับ Excel — "
            "ดูรายละเอียดใน latest.json.forecasts.inflow.forecast.api_t_deviation",
            len(api_t_reset_dates),
        )

    return df


def _ri_build_feature_vector_from_static_csv() -> dict:
    """
    Fallback: ใช้แถวล่าสุดของ Training_Values_Nofct_7day_Final.csv เรียกใช้เฉพาะตอนที่
    _ri_load_raw_monthly_data() ล้มเหลว — ไม่ใช่ live แต่เป็น static snapshot ล่าสุดที่มี
    """
    import numpy as np
    import pandas as pd

    metadata = _ri_load_metadata()
    feature_cols: list[str] = metadata["feature_cols"]
    date_col_raw = metadata["date_col_raw"]
    qin_col = metadata["qin_col"]

    logger.info("Building feature vector from %s", RESERVOIR_INFLOW_TRAINING_CSV)
    if not RESERVOIR_INFLOW_TRAINING_CSV.exists():
        raise FileNotFoundError("ไม่พบไฟล์ feature: " + str(RESERVOIR_INFLOW_TRAINING_CSV))

    df = pd.read_csv(RESERVOIR_INFLOW_TRAINING_CSV)

    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(
            "model_metadata.json ระบุ feature_cols ที่ไม่มีใน " + RESERVOIR_INFLOW_TRAINING_CSV.name + ": " + str(missing_cols)
        )

    valid = df.dropna(subset=feature_cols)
    if valid.empty:
        raise ValueError("ไม่มีแถวที่feature ครบใน " + str(RESERVOIR_INFLOW_TRAINING_CSV))

    df_sorted = valid.copy()
    df_sorted[date_col_raw] = pd.to_datetime(df_sorted[date_col_raw])
    df_sorted = df_sorted.sort_values(date_col_raw)
    latest_row = df_sorted.iloc[-1]

    as_of_date_str = latest_row[date_col_raw].strftime("%Y-%m-%d")
    staleness = _ri_compute_staleness(as_of_date_str)

    result = {
        "as_of_date": as_of_date_str,
        "current_qin": float(latest_row[qin_col]),
        "X": latest_row[feature_cols].to_numpy(dtype=float).reshape(1, -1),
        "data_source": "static_snapshot_training_csv",
        "api_t_deviation": {
            "deviates_from_original_excel_formula": False,
            "reset_event_dates": [],
            "undefined_event_dates": [],
            "note": "ใช้ static snapshot CSV (ไม่ได้คำนวณ API_t เอง) จึงไม่มี deviation นี้",
        },
        "gap_days": staleness["gap_days"],
        "staleness_status": staleness["staleness_status"],
        "staleness_message": staleness["staleness_message"],
    }

    logger.info(
        "Reservoir Inflow (fallback): as_of=%s, current_qin=%.2f, n_features=%d (data_source=%s, "
        "gap_days=%d, staleness_status=%s)",
        result["as_of_date"], result["current_qin"], len(feature_cols), result["data_source"],
        result["gap_days"], result["staleness_status"],
    )
    if staleness["staleness_status"] != "ok":
        logger.warning("Reservoir Inflow (fallback) staleness: %s", staleness["staleness_message"])

    return result


def _ri_build_feature_vector() -> dict:
    """
    จุดเรียกหลักสำหรับเตรียม feature vector ของ Reservoir Inflow:
      1. พยายามโหลดจากไฟล์ "บัญชีน้ำ" รายเดือนจริงก่อน (_ri_load_raw_monthly_data() — live)
         แล้วใช้แถวล่าสุดที่ "valid"
      2. ถ้าล้มเหลว จะ fallback ไปใช้ _ri_build_feature_vector_from_static_csv() แทน

    การ map ค่าที่คำนวณได้เข้ากับ feature_cols ใน model_metadata.json ใช้วิธี "startswith"
    """
    try:
        raw_df = _ri_load_raw_monthly_data()
        valid_df = raw_df[raw_df["valid"]]
        if valid_df.empty:
            raise ValueError("ไม่มีแถวข้อมูลรายเดือนที่ครบและสมเหตุสมผลเลยสักแถว")

        latest = valid_df.iloc[-1]
        feature_values = {
            "Q_in_t": float(latest["Q_in_t"]),
            "Water_Level_t": float(latest["Water_Level_t"]),
            "Storage_S_t": float(latest["Storage_S_t"]),
            "DeltaS_t": float(latest["DeltaS_t"]),
            "%Full_t": float(latest["%Full_t"]),
            "Rain_obs_t": float(latest["Rain_obs_t"]),
            "API_t": float(latest["API_t"]),
        }

        metadata = _ri_load_metadata()
        feature_cols: list[str] = metadata["feature_cols"]
        ordered_values: list[float] = []
        for col in feature_cols:
            match_key = next((k for k in feature_values if col.startswith(k)), None)
            if match_key is None:
                raise ValueError(f"model_metadata.json ระบุ feature_cols '{col}' ที่ไม่รู้จักจากข้อมูลรายเดือน")
            ordered_values.append(feature_values[match_key])

        import numpy as np

        api_t_reset_dates: list[str] = raw_df.attrs.get("api_t_reset_dates", [])
        api_t_undefined_dates: list[str] = raw_df.attrs.get("api_t_undefined_dates", [])
        api_t_deviation = {
            "deviates_from_original_excel_formula": bool(api_t_reset_dates or api_t_undefined_dates),
            "reset_event_dates": api_t_reset_dates,
            "undefined_event_dates": api_t_undefined_dates,
            "note": (
                "API_t ในบางวันคำนวณด้วย fallback logic ที่ผู้ implement เพิ่มเอง (reset กลับไปเริ่ม "
                "นับจาก Rain_obs_t ของวันนั้นตรงๆ เมื่อวันก่อนหน้าไม่มีข้อมูลฝน) ซึ่งไม่มีอยู่ในสูตร Excel "
                "ต้นฉบับ (Training_Ready!API_t ใน inflow_ml_training_template_3d.xlsx) — ดูรายละเอียดใน "
                "model_metadata.json > known_deviations_from_original_template"
                if (api_t_reset_dates or api_t_undefined_dates)
                else None
            ),
        }

        latest_date = latest["date"]
        as_of_date_str = (
            latest_date.strftime("%Y-%m-%d") if hasattr(latest_date, "strftime") else str(latest_date)
        )

        staleness = _ri_compute_staleness(as_of_date_str)

        result = {
            "as_of_date": as_of_date_str,
            "current_qin": feature_values["Q_in_t"],
            "X": np.array(ordered_values, dtype=float).reshape(1, -1),
            "data_source": "live_monthly_account_files",
            "api_t_deviation": api_t_deviation,
            "gap_days": staleness["gap_days"],
            "staleness_status": staleness["staleness_status"],
            "staleness_message": staleness["staleness_message"],
        }

        logger.info(
            "Reservoir Inflow (live): as_of=%s, current_qin=%.2f, n_valid_days=%d/%d (data_source=%s, "
            "gap_days=%d, staleness_status=%s)",
            result["as_of_date"], result["current_qin"], len(valid_df), len(raw_df), result["data_source"],
            result["gap_days"], result["staleness_status"],
        )
        if staleness["staleness_status"] != "ok":
            logger.warning("Reservoir Inflow (live) staleness: %s", staleness["staleness_message"])
        return result

    except Exception as exc:
        logger.warning(
            "โหลด feature จากไฟล์ข้อมูลดิบรายเดือนไม่สำเร็จ (%s) — fallback ไปใช้ static snapshot CSV แทน",
            exc,
        )
        return _ri_build_feature_vector_from_static_csv()


def _ri_run_prediction(model: dict, features: dict) -> dict:
    """
    รัน hurdle prediction สำหรับ Reservoir Inflow ตาม "final_prediction_logic" ใน model_metadata.json:
      ถ้า stage1_classifier.predict_proba(X)[:,1] >= stage1_thresholds[h] => prediction = 0
      มิฉะนั้น => prediction = clip(Q_in_t(ปัจจุบัน) + stage2_regressor.predict(X), 0, None)

    predict_proba(X)[:,1] คือ "P(Q_in_t+h = 0)" — ทิศทางตรงข้ามกับ classifier ของ Water Demand

    Staleness gate: ถ้า staleness_status == "stale_data_blocked" จะไม่รัน prediction เลย
    คืนค่า horizons=None พร้อม gap_days/staleness_message
    """
    metadata = model["metadata"]
    staleness_status: str = features.get("staleness_status", "ok")
    gap_days = features.get("gap_days")
    staleness_message = features.get("staleness_message")

    if staleness_status == "stale_data_blocked":
        logger.warning(
            "Reservoir Inflow: ข้ามการทำนายทั้งหมด (staleness_status=stale_data_blocked, "
            "gap_days=%s) — %s",
            gap_days, staleness_message,
        )
        return {
            "as_of_date": features["as_of_date"],
            "current_qin_m3_per_day": round(float(features["current_qin"]), 2),
            "unit": "m3_per_day",
            "data_source": features["data_source"],
            "target_reservoir": metadata.get("target_reservoir"),
            "horizons": None,
            "known_limitations": metadata.get("known_limitations", []),
            "known_deviations_from_original_template": metadata.get(
                "known_deviations_from_original_template", []
            ),
            "threshold_instability_from_correction": metadata.get(
                "threshold_instability_from_correction"
            ),
            "api_t_deviation": features.get("api_t_deviation"),
            "gap_days": gap_days,
            "staleness_status": staleness_status,
            "staleness_message": staleness_message,
        }

    stage1_classifiers = model["stage1_classifiers"]
    stage1_thresholds = model["stage1_thresholds"]
    stage2_regressors = model["stage2_regressors"]

    targets: list[str] = metadata["targets"]
    horizons: list[int] = metadata["horizons"]
    deployment_info: dict = metadata.get("deployment_model_per_horizon", {})

    X = features["X"]
    current_qin = features["current_qin"]

    horizon_results: dict = {}
    for h, target_col in zip(horizons, targets):
        key = f"h{h}"

        if target_col not in stage1_classifiers or target_col not in stage1_thresholds \
                or h not in stage2_regressors:
            horizon_results[key] = None
            continue

        clf = stage1_classifiers[target_col]
        threshold = float(stage1_thresholds[target_col])

        prob_zero = float(clf.predict_proba(X)[:, 1][0])

        if prob_zero >= threshold:
            prediction = 0.0
            stage_used = "stage1_zero"
        else:
            delta = float(stage2_regressors[h].predict(X)[0])
            prediction = max(current_qin + delta, 0.0)
            stage_used = "stage2_regressor"

        info = deployment_info.get(str(h), {})
        hurdle_nse = info.get("hurdle_nse_on_test")

        horizon_results[key] = {
            "prediction_m3_per_day": round(prediction, 2),
            "prob_zero": round(prob_zero, 4),
            "threshold": round(threshold, 4),
            "stage_used": stage_used,
            "model_name": info.get("model_name"),
            "hurdle_nse_on_test": hurdle_nse,
            "low_confidence": bool(hurdle_nse is not None and hurdle_nse < 0),
        }

    if staleness_status != "ok":
        logger.warning(
            "Reservoir Inflow: staleness_status=%s (gap_days=%s) — %s (ยังคำนวณผลทำนายต่อ "
            "เพราะยังไม่เกินเกณฑ์ blocked)",
            staleness_status, gap_days, staleness_message,
        )

    return {
        "as_of_date": features["as_of_date"],
        "current_qin_m3_per_day": round(current_qin, 2),
        "unit": "m3_per_day",
        "data_source": features["data_source"],
        "target_reservoir": metadata.get("target_reservoir"),
        "horizons": horizon_results,
        "known_limitations": metadata.get("known_limitations", []),
        "known_deviations_from_original_template": metadata.get(
            "known_deviations_from_original_template", []
        ),
        "threshold_instability_from_correction": metadata.get(
            "threshold_instability_from_correction"
        ),
        "api_t_deviation": features.get("api_t_deviation"),
        "gap_days": gap_days,
        "staleness_status": staleness_status,
        "staleness_message": staleness_message,
    }


def load_latest_model() -> dict:
    """โหลดโมเดลทั้งสองระบบ (Water Demand + Reservoir Inflow) แยก try/except ต่อระบบ"""
    models: dict = {"water_demand": None, "reservoir_inflow": None}

    try:
        models["water_demand"] = _wd_load_models()
    except Exception:
        logger.exception("โหลดโมเดล Water Demand ไม่สำเร็จ")

    try:
        models["reservoir_inflow"] = _ri_load_models()
    except Exception:
        logger.exception("โหลดโมเดล Reservoir Inflow ไม่สำเร็จ")

    return models


def build_feature_vector(telemetry: list[TelemetryReading], crop_classification: Optional[dict]) -> dict:
    """เตรียม feature vector ของทั้งสองระบบ แยก try/except ต่อระบบเช่นเดียวกับ load_latest_model()"""
    features: dict = {"water_demand": None, "reservoir_inflow": None}

    try:
        features["water_demand"] = _wd_build_feature_vector()
    except Exception:
        logger.exception("เตรียม feature vector Water Demand ไม่สำเร็จ")

    try:
        features["reservoir_inflow"] = _ri_build_feature_vector()
    except Exception:
        logger.exception("เตรียม feature vector Reservoir Inflow ไม่สำเร็จ")

    return features


def run_prediction(model: dict, features: dict) -> dict:
    """
    รันทำนายทั้งสองระบบ แยก try/except ต่อระบบ คืนค่าเป็น dict ที่มี key ตายตัวสามชุดเสมอ
    (demand_zone_a, demand_zone_b, inflow)
    """
    logger.info("Running prediction with latest features")
    predictions: dict = {"demand_zone_a": None, "demand_zone_b": None, "inflow": None}

    wd_model = model.get("water_demand")
    wd_features = features.get("water_demand")
    if wd_model is not None and wd_features is not None:
        try:
            zone_a, zone_b = _wd_run_prediction(wd_model, wd_features)
            predictions["demand_zone_a"] = zone_a
            predictions["demand_zone_b"] = zone_b
        except Exception:
            logger.exception("ทำนาย Water Demand ไม่สำเร็จ")
    else:
        logger.warning("ข้าม prediction ของ Water Demand (ไม่มีโมเดลหรือ feature พร้อมใช้)")

    ri_model = model.get("reservoir_inflow")
    ri_features = features.get("reservoir_inflow")
    if ri_model is not None and ri_features is not None:
        try:
            predictions["inflow"] = _ri_run_prediction(ri_model, ri_features)
        except Exception:
            logger.exception("ทำนาย Reservoir Inflow ไม่สำเร็จ")
    else:
        logger.warning("ข้าม prediction ของ Reservoir Inflow (ไม่มีโมเดลหรือ feature พร้อมใช้)")

    return predictions


def save_results(result: PipelineResult, output_path: Path = OUTPUT_PATH, website_copy_path: Optional[Path] = WEBSITE_DATA_COPY_PATH) -> None:
    """
    บันทึกผลลัพธ์ของ pipeline รอบนี้เป็นไฟล์ JSON ที่ output_path (overwrite ทุกครั้งที่รัน)
    เขียนแบบ atomic (.tmp แล้วค่อย replace) และสำเนาไปที่ website_copy_path ด้วย
    """
    logger.info("Saving pipeline results to %s", output_path)

    inflow_pred = result.predictions.get("inflow")
    if inflow_pred is not None:
        forecast_status = inflow_pred.get("staleness_status") or "ok"
    else:
        forecast_status = "model_missing_pending_retrain"

    demand_zone_a = result.predictions.get("demand_zone_a")
    demand_zone_b = result.predictions.get("demand_zone_b")

    payload = {
        "run_timestamp": result.run_timestamp,
        "telemetry": {
            "source": result.telemetry_source,
            "is_mock": result.telemetry_source == "mock",
            "readings": result.telemetry,
        },
        "forecasts": {
            "demand_zone_a": demand_zone_a,
            "demand_zone_b": demand_zone_b,
            "inflow": {"status": forecast_status, "forecast": inflow_pred} if inflow_pred is not None else {"status": forecast_status, "forecast": None},
        },
        "sar_triggered": result.sar_triggered,
        "crop_classification": result.crop_classification,
        "model_version": result.model_version,
        "status": result.status,
        "step_status": result.step_status,
        "errors": result.errors,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp_path.replace(output_path)

    if website_copy_path is not None:
        try:
            website_copy_path = Path(website_copy_path)
            website_copy_path.parent.mkdir(parents=True, exist_ok=True)
            with open(website_copy_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info("Copied pipeline results to website data folder: %s", website_copy_path)
        except Exception:
            logger.warning(
                "คัดลอก latest.json ไปที่ %s ไม่สำเร็จ — หน้าเว็บอาจแสดงข้อมูลเก่าค้างอยู่ "
                "(output_path หลักที่ %s เขียนสำเร็จแล้วตามปกติ ไม่กระทบ)",
                website_copy_path, output_path,
            )


def run_pipeline() -> PipelineResult:
    """เรียกทุกขั้นตอนของ pipeline ตามลำดับ พร้อม error handling แยกต่อ step"""
    run_timestamp = datetime.now(timezone.utc).isoformat()
    step_status: dict[str, str] = {}
    errors: list[str] = []

    logger.info("Step 1/5: ดึงข้อมูลโทรมาตร")
    try:
        telemetry, telemetry_source = get_telemetry_data()
        step_status["telemetry"] = "ok"
    except Exception as exc:
        logger.exception("Step 1/5 ล้มเหลว (get_telemetry_data)")
        telemetry, telemetry_source = [], "unknown"
        step_status["telemetry"] = "failed"
        errors.append("get_telemetry_data: " + str(exc))

    logger.info("Step 2/5: ดึง MEI + CHIRPS + ERA5T (climate features)")
    try:
        climate_result = _fetch_climate_features_step()
        step_status["climate_features"] = climate_result["data_status"]
        if climate_result.get("errors"):
            errors.extend("climate_features: " + e for e in climate_result["errors"])
        readiness = climate_result.get("prediction_readiness", {})
        readiness_statuses = [v.get("status") for v in readiness.values()]
        if any(s == "blocked_insufficient_data" for s in readiness_statuses):
            step_status["climate_prediction_readiness"] = "blocked_insufficient_data"
        elif any(s == "fallback" for s in readiness_statuses):
            step_status["climate_prediction_readiness"] = "fallback"
        else:
            step_status["climate_prediction_readiness"] = "ok"
    except Exception as exc:
        logger.exception(
            "Step 2/5 ล้มเหลว (_fetch_climate_features_step) — ไม่ควรเกิดขึ้นปกติเพราะฟังก์ชันนี้ออกแบบให้ไม่ raise"
        )
        step_status["climate_features"] = "failed"
        errors.append("climate_features: " + str(exc))

    logger.info("Step 3/5: ตรวจสอบภาพ SAR ใหม่ + จำแนกพืช")
    sar_triggered = False
    crop_classification: Optional[dict] = None
    try:
        new_sar_image = check_new_sar_image()
        if new_sar_image is not None:
            crop_classification = trigger_crop_classification(new_sar_image)
            sar_triggered = True
        else:
            logger.info("ไม่พบภาพ SAR ใหม่ในรอบนี้ ข้ามการจำแนกพืช")
        step_status["sar_classification"] = "ok"
    except Exception as exc:
        logger.exception("Step 3/5 ล้มเหลว (SAR check / crop classification)")
        step_status["sar_classification"] = "failed"
        errors.append("sar_pipeline: " + str(exc))

    logger.info("Step 4/5: โหลดโมเดล และทำนาย")
    predictions: dict = {"demand_zone_a": None, "demand_zone_b": None, "inflow": None}
    model_version_parts: list[str] = []
    try:
        model = load_latest_model()
        features = build_feature_vector(telemetry, crop_classification)
        predictions = run_prediction(model, features)

        wd_model = model.get("water_demand")
        if wd_model is not None:
            model_version_parts.append(
                "water_demand_2stage(n_zone_horizon_models=" + str(len(wd_model["catboost"])) + ")"
            )
        else:
            model_version_parts.append("water_demand=unavailable")

        ri_model = model.get("reservoir_inflow")
        if ri_model is not None:
            model_version_parts.append(
                "reservoir_inflow_hurdle(n_horizon_models=" + str(len(ri_model["stage2_regressors"])) + ")"
            )
        else:
            model_version_parts.append("reservoir_inflow=unavailable")

        step_status["prediction"] = "ok"
        step_status["prediction_water_demand"] = "ok" if (predictions["demand_zone_a"] is not None or predictions["demand_zone_b"] is not None) else "failed"
        step_status["prediction_reservoir_inflow"] = "ok" if predictions["inflow"] is not None else "failed"
    except Exception as exc:
        logger.exception("Step 4/5 ล้มเหลว (load_latest_model / run_prediction)")
        step_status["prediction"] = "failed"
        errors.append("prediction: " + str(exc))

    model_version = "; ".join(model_version_parts) if model_version_parts else None
    status = "ok" if not errors else "partial_failure"

    result = PipelineResult(
        run_timestamp=run_timestamp,
        telemetry=[t.__dict__ for t in telemetry],
        telemetry_source=telemetry_source,
        sar_triggered=sar_triggered,
        crop_classification=crop_classification,
        predictions=predictions,
        model_version=model_version,
        status=status,
        errors=errors,
        step_status=step_status,
    )

    logger.info("Step 5/5: บันทึกผลลัพธ์เป็น JSON")
    try:
        save_results(result)
        step_status["save_results"] = "ok"
    except Exception as exc:
        logger.exception("Step 5/5 ล้มเหลว (save_results)")
        step_status["save_results"] = "failed"
        errors.append("save_results: " + str(exc))
        result.status = "partial_failure"

    return result


def main() -> int:
    """
    Entry point แบบ standalone — ไม่รอ input จากผู้ใช้ระหว่างทาง เหมาะสำหรับตั้งเวลารันอัตโนมัติ
    คืนค่า exit code: 0 = สำเร็จทั้งหมด, 1 = สำเร็จบางส่วน, 2 = ล้มเหลวรุนแรง
    """
    logger.info("=" * 70)
    logger.info("=== Starting data pipeline run (%s) ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        result = run_pipeline()
    except Exception:
        logger.exception("Pipeline crashed นอกเหนือจาก error handling ปกติ — ต้องตรวจสอบด่วน")
        logger.info("=== Pipeline finished with status: crashed ===")
        return 2

    logger.info("=== Pipeline finished with status: %s ===", result.status)
    if result.status == "ok":
        return 0
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
