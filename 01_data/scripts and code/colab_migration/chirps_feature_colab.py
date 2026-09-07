"""
chirps_feature_colab.py
=========================
**Colab migration variant ของ chirps_feature.py (ต้นฉบับอยู่ที่
01_data/scripts and code/pipeline/chirps_feature.py — ห้ามแก้ไฟล์เดิม)**

Business logic (GEE fetch final+prelim, pentad-to-daily expansion, P_eff ตาม zone, lag,
SPI_4/drought_flag) **เหมือนต้นฉบับทุกจุด ไม่มีการแก้ไข**

**สิ่งที่ต่างจากต้นฉบับ — จุดเดียว เหมือนที่เจอกับ `mei_feature_colab.py`**: ต้นฉบับตั้ง
`LOG_DIR = SCRIPT_DIR / "logs"` ซึ่งชี้ไปที่ `pipeline/logs/pipeline_log.txt` เสมอ — ถ้า import
ตรงจาก Drive-mirrored `pipeline/` จะเขียนทับ/ต่อท้ายไฟล์ log ของจริง (ผิดกฎ "ห้ามเขียนลง
pipeline/") จึง copy มาเปลี่ยนแค่ `LOG_DIR` เป็น `SCRIPT_DIR / "test_output"` (ไฟล์นี้อยู่ใน
`colab_migration/` เอง log จึงไปลง `colab_migration/test_output/` แทน)

**จุดที่ตรวจสอบแล้วว่า "ไม่ต้องแก้" (ต่างจากที่คาดไว้แรกๆ)**:
- `DEFAULT_HISTORICAL_CSV_PATH = SCRIPT_DIR.parent / "Water_demand" / "active" / "ml_features_phase4.csv"`
  — ใช้ `SCRIPT_DIR.parent` ซึ่งเท่ากับ `01_data/scripts and code/` ทั้งจาก `pipeline/` และจาก
  `colab_migration/` เหมือนกัน (สองโฟลเดอร์นี้เป็น sibling อยู่ใต้ parent เดียวกัน) — path จึงชี้ไปที่
  ไฟล์ประวัติจริงถูกต้องโดยไม่ต้องแก้อะไร (อ่านอย่างเดียว ไม่มีความเสี่ยงเรื่องเขียนทับ)
- `_fetch_chirps_daily_from_gee()` เรียก `import gee_auth` ข้างในฟังก์ชัน (local import) — เจอไฟล์
  ได้เองผ่าน `sys.path` ที่ตั้งไว้แล้วใน Cell 5/8 ของ `COLAB_MIGRATION_PLAN.md` ไม่ต้องแก้อะไร
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
# Config (เหมือนต้นฉบับทุกประการ)
# ---------------------------------------------------------------------------
TARGET_LAT = 19.05
TARGET_LON = 99.80

CHIRPS_FINAL_COLLECTION_ID = "UCSB-CHG/CHIRPS/DAILY"
CHIRPS_PRELIM_COLLECTION_ID = "projects/climate-engine-pro/assets/ce-chirps-prelim-pentad"

CHIRPS_BAND_NAME = "precipitation"

DEFAULT_GEE_PROJECT = "maenaruea-water-pipeline"

FINAL_DATA_SAFE_LAG_DAYS = 50

ZONE_P_EFF_KIND = {
    "zone_A": "upland",  # rainfed -> P_eff_upland
    "zone_B": "paddy",   # irrigated (rice-dominant) -> P_eff_paddy
}

P_MM_WEEK_LAG_WEEKS = [1, 2, 4]

SPI_DROUGHT_THRESHOLD = -1.0

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "test_output"  # Colab variant: เขียนที่ colab_migration/test_output/ ไม่ใช่ pipeline/logs/ (ดู docstring หัวไฟล์)
LOG_FILE = LOG_DIR / "chirps_feature_colab_log.txt"

# ประวัติ P_mm_week ที่มีอยู่แล้วในเครื่อง — path นี้ resolve เหมือนกันไม่ว่าไฟล์นี้จะอยู่ใน
# pipeline/ หรือ colab_migration/ (ทั้งคู่เป็น sibling ใต้ "01_data/scripts and code/" เดียวกัน)
DEFAULT_HISTORICAL_CSV_PATH = SCRIPT_DIR.parent / "Water_demand" / "active" / "ml_features_phase4.csv"


def _get_logger() -> logging.Logger:
    """เหมือนต้นฉบับ ต่างแค่ path ของ FileHandler (ดู LOG_DIR ด้านบน)"""
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
    return pd.to_datetime(f"{iso_year}-W{iso_week:02d}-1", format="%G-W%V-%u")


# ---------------------------------------------------------------------------
# Step 1: โหลดประวัติ P_mm_week หลายปีที่มีอยู่แล้ว (สำหรับ SPI_4 baseline) — เหมือนต้นฉบับ
# ---------------------------------------------------------------------------
def _load_historical_p_mm_week(csv_path: Path = DEFAULT_HISTORICAL_CSV_PATH) -> pd.DataFrame:
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
# Step 2: ดึง CHIRPS สดใหม่ผ่าน GEE (final ก่อน, ตามด้วย prelim) — เหมือนต้นฉบับ
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
    import ee
    import gee_auth

    gee_auth.init_ee(gee_project)

    point = ee.Geometry.Point([lon, lat])
    collection = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date.isoformat(), end_date.isoformat())
        .select(band_name)
    )

    scale_m = 5500
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
    final_cutoff = date.today() - timedelta(days=FINAL_DATA_SAFE_LAG_DAYS)

    frames = []

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
# Step 3: รวมประวัติ + ข้อมูลสด, คำนวณ P_eff และ lag — เหมือนต้นฉบับ
# ---------------------------------------------------------------------------
def _compute_p_eff(p_mm_week: pd.Series, zone: str) -> pd.Series:
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
    hist = historical.copy()
    hist["n_days"] = 7
    hist["data_type"] = "historical"

    fresh_keys = set(zip(fresh["year"], fresh["week"])) if not fresh.empty else set()
    hist = hist[~hist.apply(lambda r: (r["year"], r["week"]) in fresh_keys, axis=1)]

    frames = [f for f in (hist, fresh) if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["year", "week", "P_mm_week", "n_days", "data_type"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["year", "week"]).reset_index(drop=True)
    return combined


# ---------------------------------------------------------------------------
# Step 4: SPI_4 / drought_flag — เหมือนต้นฉบับ
# ---------------------------------------------------------------------------
def _add_spi4_drought_flag(combined: pd.DataFrame) -> pd.DataFrame:
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
# Step 5: จุดเรียกหลัก — get_chirps_feature() — เหมือนต้นฉบับ
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
        "is_partial_week": as_of_ts.dayofweek != 6,
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
    fresh_end = as_of + timedelta(days=1)

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
    import json

    for demo_zone in ("zone_A", "zone_B"):
        print(f"--- {demo_zone} ---")
        print(json.dumps(get_chirps_feature(zone=demo_zone), indent=2, ensure_ascii=False))
