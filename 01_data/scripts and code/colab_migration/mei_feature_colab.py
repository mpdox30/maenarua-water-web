"""
mei_feature_colab.py
=====================
**Colab migration variant ของ mei_feature.py (ต้นฉบับอยู่ที่
01_data/scripts and code/pipeline/mei_feature.py — ห้ามแก้ไฟล์เดิม)**

Business logic (parse `meiv2.data`, resample รายสัปดาห์ + คำนวณ MEI_lag4/MEI_lag8,
stale-check, cross-check กับ ONI) **เหมือนต้นฉบับทุกจุด ไม่มีการแก้ไข**

**สิ่งที่ต่างจากต้นฉบับ — จุดเดียว (ไม่ใช่ environment ผูก native library เหมือน ERA5T แต่เป็น
side-effect ของการเขียนไฟล์)**: ต้นฉบับตั้ง `LOG_DIR = SCRIPT_DIR / "logs"` ซึ่งหมายถึง
`pipeline/logs/pipeline_log.txt` เสมอ (คำนวณจาก `Path(__file__).resolve().parent`) — ถ้า import
`mei_feature.py` ตรงจาก Drive-mirrored `pipeline/` (ตามหลักการ "ไม่ต้องแก้ก็ import ตรงได้" ที่ตั้งไว้
ใน COLAB_MIGRATION_PLAN.md) ทุกครั้งที่เรียก `get_mei_feature()` จะ **เขียนทับ/ต่อท้ายไฟล์ log ของ
จริงบน Drive ที่ mirror มาจาก Windows** ซึ่งผิดกฎ "ห้ามเขียนลงโฟลเดอร์ pipeline/" (ดูหัวข้อ 2.2 ใน
COLAB_MIGRATION_PLAN.md — Windows Task Scheduler ยังใช้งาน `pipeline/` จริงอยู่ แม้ Drive จะเป็นแค่
snapshot ก็ไม่ควรสร้างความสับสนโดยไม่จำเป็น) — จึงต้อง copy ไฟล์นี้มาแก้ **แค่ปลายทางของ log** จุด
เดียว ไม่แก้อะไรอื่นเลย: เปลี่ยน `LOG_DIR` จาก `SCRIPT_DIR / "logs"` เป็น
`SCRIPT_DIR / "test_output"` — เพราะไฟล์นี้อยู่ใน `colab_migration/` เอง `SCRIPT_DIR` จึงชี้มาที่
`colab_migration/` โดยอัตโนมัติ ผลคือ log ไปลงที่ `colab_migration/test_output/` (ที่กันไว้สำหรับผล
ทดสอบ Colab ทั้งหมดอยู่แล้ว) ไม่ไปแตะ `pipeline/logs/` เดิมเลย
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
# ไว้เอง ("by the 10th of each month") ดู docstring ของต้นฉบับสำหรับหลักฐาน
STALE_THRESHOLD_DAYS = 60

# lag windows ที่ต้องการ (นับเป็น "แถว" บน weekly-resampled series ตาม build_feature_matrix()
# ในไฟล์ archive/combined_final_pipeline.py บรรทัด 2693 — add_lag_features(z, "MEI", [4, 8]))
MEI_LAG_WEEKS = [4, 8]

# จำนวนสัปดาห์ย้อนหลังที่สร้าง skeleton ไว้คำนวณ lag ต้อง >= max(MEI_LAG_WEEKS) เสมอ เผื่อไว้
# มากกว่านั้นพอสมควรเพราะ MEI เป็นข้อมูลรายเดือน ต้องมี anchor point จริงย้อนหลังพอที่จะ shift
# ได้ค่าที่สมเหตุสมผล (ไม่ใช่ NaN เพราะ skeleton สั้นเกินไป)
DEFAULT_WEEKS_BACK = 20

# --- ค่าเทียบเคียง (cross-check) ENSO จาก NOAA CPC ---
ONI_DATA_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
ENSO_ADVISORY_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "test_output"  # Colab variant: เขียนที่ colab_migration/test_output/ ไม่ใช่ pipeline/logs/ (ดู docstring หัวไฟล์)
LOG_FILE = LOG_DIR / "mei_feature_colab_log.txt"


def _get_logger() -> logging.Logger:
    """
    ใช้ logger ชื่อ "data_pipeline" เหมือนต้นฉบับ (เหตุผลเดิม: กันปัญหา circular import ถ้า
    data_pipeline.py มา import โมดูลนี้ในอนาคต) — ต่างแค่ path ของ FileHandler (ดู LOG_DIR ด้านบน)
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
# Step 1: ดึง + parse meiv2.data (เหมือนต้นฉบับทุกประการ)
# ---------------------------------------------------------------------------
def _parse_mei_text(raw_text: str) -> pd.DataFrame:
    """
    Parse เนื้อหา text ของ meiv2.data เป็น long-format DataFrame [year, month, MEI]
    (เหมือนต้นฉบับทุกประการ — ดู docstring ของ mei_feature.py สำหรับที่มา/เหตุผลเต็ม)
    """
    lines = raw_text.strip().split("\n")

    data_lines: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("MEI"):
            continue
        parts = stripped.split()
        if len(parts) == 13 and parts[0].isdigit():
            data_lines.append(parts)

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
    df = df.sort_values(["year", "month"]).reset_index(drop=True)
    return df


def _download_mei_raw(
    url: str = MEI_DATA_URL,
    timeout: int = MEI_REQUEST_TIMEOUT_SEC,
    fetch_fn: Callable[..., Any] = requests.get,
) -> pd.DataFrame:
    logger.info("Downloading MEI v2 from %s ...", url)
    resp = fetch_fn(url, timeout=timeout)
    resp.raise_for_status()
    return _parse_mei_text(resp.text)


# ---------------------------------------------------------------------------
# Step 1b: ดึง ONI (Nino 3.4) จาก NOAA CPC มาเป็นค่าเทียบเคียง (ไม่ใช่ feature หลัก)
# ---------------------------------------------------------------------------
def _parse_oni_text(raw_text: str) -> list[dict]:
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
# Step 2: resample เป็นรายสัปดาห์ + คำนวณ lag (เหมือนต้นฉบับทุกประการ)
# ---------------------------------------------------------------------------
def _build_weekly_mei_series(
    mei_raw: pd.DataFrame,
    as_of_date: date,
    weeks_back: int,
) -> pd.DataFrame:
    as_of_ts = pd.Timestamp(as_of_date)

    rows = []
    for delta in range(weeks_back, -1, -1):
        raw_date = as_of_ts - pd.Timedelta(weeks=delta)
        iso_year, iso_week, _ = raw_date.isocalendar()
        monday_date = pd.to_datetime(f"{iso_year}-W{iso_week:02d}-1", format="%G-W%V-%u")
        rows.append({"year": int(iso_year), "week": int(iso_week), "date": monday_date})

    skel = pd.DataFrame(rows).drop_duplicates(subset=["year", "week"]).reset_index(drop=True)
    skel["month"] = skel["date"].dt.month

    merged = skel.merge(mei_raw[["year", "month", "MEI"]], on=["year", "month"], how="left")
    merged["mei_is_actual"] = merged["MEI"].notna()

    merged["MEI"] = merged["MEI"].interpolate(method="linear").bfill().ffill()

    merged = merged.sort_values(["year", "week"]).reset_index(drop=True)
    for lag in MEI_LAG_WEEKS:
        merged[f"MEI_lag{lag}"] = merged["MEI"].shift(lag)

    return merged


# ---------------------------------------------------------------------------
# Step 3: จุดเรียกหลัก — get_mei_feature() (เหมือนต้นฉบับทุกประการ)
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
    import json

    print(json.dumps(get_mei_feature(), indent=2, ensure_ascii=False))
