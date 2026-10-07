# -*- coding: utf-8 -*-
"""
6-hourly reservoir-inflow SHADOW-TEST predictor (2026-09-18 investigation).
[2026-09-25 SPILLWAY FORMULA แก้] -- เดิมสคริปต์นี้มีสำเนาสูตร spillway แบบ constant-Cd
(Q=C*L*H^1.5, C=1.82) ฝังอยู่ในตัวเอง (บรรทัด spillway_overflow_m3() เดิม) ใช้คำนวณ Q_in_t
"สด" ทุกครั้งที่ predict -- ถ้าจะ "แทนที่ shadow-test เดิม" ด้วย label ที่แก้แล้ว (critical-flow+
friction model, ดู Spillway_check/03_experiment/weir_friction_model.py) แค่เปลี่ยน frozen
models ใน shadow_models/ อย่างเดียวไม่พอ เพราะ base_qin (persistence baseline + สิ่งที่โมเดล
บวกเพิ่ม/ลบ) และ Qin_lag1/2 ของรอบถัดๆ ไปจะยังคำนวณด้วยสูตรเก่าอยู่ -- เกิด train/inference skew
แบบเดียวกับบั๊ก RELEASE_EVENTS ที่เคยเจอ (ดู comment RELEASE_EVENTS_CSV_PATH ด้านล่าง) จึงแก้
spillway_overflow_m3() ในไฟล์นี้ให้ตรงกับสูตรที่ใช้เทรน label ชุดใหม่เป๊ะๆ ด้วย

วิธีที่เลือก: precompute lookup table (head_m -> q_per_m, Manning n=0.017 กลาง, b=10m ตาม
weir_friction_model.py) เป็นไฟล์ spillway_friction_curve_n017.csv แล้ว interp ด้วย numpy
(ไม่ import scipy.optimize.brentq สดในสคริปต์นี้ -- คง "self-contained, งานdependency น้อยที่สุด"
ตามปรัชญาเดิมของสคริปต์นี้ที่ต้องรันไม่มีคนเฝ้าผ่าน Task Scheduler ทุก 6 ชม. ไม่อยากเพิ่ม
dependency ใหม่ที่อาจพังเงียบๆ ถ้า Python env ไม่มี scipy)

--- เอกสารเดิม (ไม่เปลี่ยน) ---

SELF-CONTAINED as of 2026-09-18: downloads the same public Google Sheet the user's Apps
Script writes to every 10 minutes (gdrive_log, file_id below -- same one 09_live/config.json
and daily_update.py point at) DIRECTLY over HTTPS. Does not read WMB_Phayao/09_live/data/
api_snapshots.csv, and does not depend on Google Drive for Desktop, Colab, or daily_update.py
having run recently. The only external dependency is: this PC has internet access, and the
Sheet is still shared "Anyone with the link" (same prerequisite the rest of the project's
telemetry ingestion has always had).

Run this every 6 hours (Task Scheduler). Each run:
  1. Downloads the raw_log sheet fresh, merges into a local accumulating store
     (shadow_gdrive_raw_store.csv, dedup'd) -- falls back to whatever's already in that
     store if the download fails (no internet at that moment), never crashes.
  2. Rebuilds the 6-hourly water-balance history (same methodology as
     build_6hourly_extended.py) from that store + 2 static historical files bundled in
     this same folder (Raw Data_RES002 station.xlsx, RES002 July.csv -- these never change,
     not a live dependency).
  3. Finds every 6h mark (01:00/07:00/13:00/19:00) not yet logged and backfills all of them
     (see DEPLOY_START_MARK below -- never backfills into the training period).
  4. Loads the FROZEN models trained by train_final_shadow_models.py (shadow_models/) --
     these are NOT retrained here. That is the point of a shadow test: fixed candidate,
     scored against reality as it arrives.
  5. Predicts H1..H12 (6h..72h ahead), logs alongside the naive persistence baseline to
     shadow_predictions_log.csv. Idempotent: re-running before new data has landed is a
     harmless no-op (skips, does not duplicate).

Does NOT touch the live production pipeline or the deployed daily model in any way.
"""
import calendar
import csv
import io
import os
import sys
from datetime import datetime, timedelta

import joblib
import numpy as np
import openpyxl
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "shadow_models")
LOG_PATH = os.path.join(HERE, "shadow_predictions_log.csv")

# Same public Sheet as 09_live/config.json -> gdrive_log.file_id (sheet "raw_log", 10-min
# telemetry, shared "Anyone with the link"). Export-as-xlsx URL pattern copied from the
# already-working ingest_gdrive_log() in 09_live/daily_update.py.
GDRIVE_FILE_ID = "1C04iw2g8mBR62dpI7dE_FrF4XE-FdURsNcxxl569Dj4"
GDRIVE_SHEET_NAME = "raw_log"
GDRIVE_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{GDRIVE_FILE_ID}/export?format=xlsx"
RAW_STORE_PATH = os.path.join(HERE, "shadow_gdrive_raw_store.csv")

# ---------------- exact same water-balance constants as build_6hourly_extended.py ----------------
SPILLWAY_LEVEL_ADJ_OFFSET_M = 0.155
SPILLWAY_CREST_LEVEL_MSL = 489.545
SPILLWAY_WEIR_LENGTH_M = 30
# [2026-09-25] C=1.82 คงที่เดิมไม่ใช้คำนวณ Q_in แล้ว (เก็บไว้อ้างอิง/debug เทียบเท่านั้น) --
# แทนที่ด้วย critical-flow+friction lookup table ด้านล่าง (spillway_overflow_m3())
SPILLWAY_WEIR_COEFFICIENT_C_OLD_UNUSED = 1.82

# critical-flow+friction lookup table (Manning n=0.017, b=10m) -- precomputed by
# Spillway_check/03_experiment/weir_friction_model.py (q_broad_crested_friction), เก็บเป็น
# CSV เพื่อไม่ต้อง import scipy.optimize.brentq สดในสคริปต์ live นี้
_FRICTION_CURVE_PATH = os.path.join(HERE, "spillway_friction_curve_n017.csv")


def _load_friction_curve(path):
    heads, qs = [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            heads.append(float(row[0]))
            qs.append(float(row[1]))
    return np.array(heads), np.array(qs)


_FRICTION_HEAD_GRID, _FRICTION_Q_GRID = _load_friction_curve(_FRICTION_CURVE_PATH)

MONTHLY_EVAP_CONST_MM = {
    1: 103.0692307692308, 2: 115.03999999999999, 3: 136.92461538461538,
    4: 152.96692307692308, 5: 146.68923076923076, 6: 140.09307692307695,
    7: 120.02538461538461, 8: 125.63923076923078, 9: 120.25076923076925,
    10: 112.23615384615384, 11: 101.06923076923077, 12: 99.02,
}
EVAP_PAN_COEFFICIENT = 0.7
INFILTRATION_RATE_MM_PER_DAY = 1.0
RESERVOIR_STORAGE_MAX_M3 = 1625463.7590197
API_K_DAILY = 0.95
API_K_6H = API_K_DAILY ** (1 / 4)

RELEASE_RATE_SPILLWAY_6TURNS = 393.6 * 24
RELEASE_RATE_INLET_6TURNS = 232.2 * 24

# 2026-09-21 แก้ -- เดิมเป็น hardcoded list สำเนาที่ 3 แยกจาก release_events.csv (สำเนาที่ 1 คือ
# release_events.csv เอง, สำเนาที่ 2 คือ RELEASE_EVENTS ใน build_6hourly_extended.py ที่ใช้สร้าง
# ข้อมูลเทรน) -- สำเนานี้ไม่เคยถูกอัปเดตตอนแก้ release_events.csv เมื่อ 2026-09-19 (ปิดเหตุการณ์ปัจจุบัน
# ที่ 4 ส.ค. 2569 ไม่ใช่ 14 ต.ค., เพิ่มเหตุการณ์ 21-27 มี.ค. ที่ขาดไป) เลยยังปล่อยน้ำผีเข้า Q_in ทุก 6ชม.
# ตั้งแต่ 4 ส.ค. เป็นต้นมา (รวมทั้งช่วง shadow-test ทั้งหมดที่ผ่านมา -- ตรวจพบตอนขุดหาสาเหตุ shadow-test
# NSE ติดลบ) แก้โดยอ่านจาก release_events.csv ตรงๆ แทนที่จะ hardcode ซ้ำอีกรอบ กันบั๊กแบบนี้เกิดซ้ำเป็น
# ครั้งที่ 3 ในอนาคต -- ถ้าจะเพิ่ม/แก้เหตุการณ์ปล่อยน้ำ แก้ที่ release_events.csv ที่เดียว ไฟล์นี้จะเห็นผล
# อัตโนมัติโดยไม่ต้องแก้โค้ด
RELEASE_EVENTS_CSV_PATH = os.path.normpath(
    os.path.join(HERE, "..", "..", "Reservoirs", "release_log", "release_events.csv")
)

def load_release_events_from_csv(csv_path):
    """
    อ่าน release_events.csv (แหล่งข้อมูล canonical เดียวกับที่ build_6hourly_extended.py ใช้สร้าง
    ข้อมูลเทรน) แปลงเป็น list ของ (start_dt, end_dt, rate_m3_per_day, label) รูปแบบเดียวกับ
    RELEASE_EVENTS เดิม (จุดต่อจุด ไม่ weight ตามสัดส่วนชั่วโมงทับซ้อน) -- ใช้รูปแบบนี้ตั้งใจ ไม่ใช่แบบ
    hour-weighted overlap ที่ inflow_6h_display_estimate.py ใช้ เพราะ build_6hourly_extended.py
    (ที่สร้างข้อมูลเทรนของโมเดลชุดนี้) ใช้วิธีจุดต่อจุดเหมือนกัน -- ถ้าเปลี่ยนวิธีคำนวณตรงนี้จะทำให้
    input ตอน inference ไม่ตรงกับตอนเทรนอีกแบบหนึ่ง (train/inference skew)

    raise FileNotFoundError ชัดเจนถ้าอ่านไฟล์ไม่ได้ -- ไม่ fallback ไปใช้ list ว่างเงียบๆ เพราะจะทำให้
    Q_in คำนวณผิดแบบไม่มีใครรู้ตัว (เหมือนบั๊กที่เพิ่งเจอ)
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"ไม่พบ release_events.csv ที่ {csv_path} -- ต้องมีไฟล์นี้ถึงจะคำนวณ Q_in ได้ถูกต้อง "
            f"(ไม่ fallback ไปใช้ empty list เพราะจะทำให้ Q_in สูงเกินจริงทุกช่วงที่มีการปล่อยน้ำจริง)"
        )
    events = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            start_dt = datetime.strptime(f"{row['start_date']} {row['start_time']}", "%Y-%m-%d %H:%M")
            if row.get("end_date") and row.get("end_time"):
                end_dt = datetime.strptime(f"{row['end_date']} {row['end_time']}", "%Y-%m-%d %H:%M")
            else:
                end_dt = None  # ยังไม่ปิด -- ถือว่าคลุมตลอดตั้งแต่ start_dt เป็นต้นไป
            rate = float(row["rate_m3_per_day"])
            label = f"event#{row['event_no']}({row.get('outlet_side', '?')})"
            events.append((start_dt, end_dt, rate, label))
    return events


RELEASE_EVENTS = load_release_events_from_csv(RELEASE_EVENTS_CSV_PATH)

PLAUSIBLE_LEVEL_MIN = 487.5
PLAUSIBLE_LEVEL_MAX = 491.0
MARK_HOURS = [1, 7, 13, 19]

QIN_COL = "Q_in_t (m3/6h)"
FEATS = [
    "Q_in_t (m3/6h)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/6h)", "%Full_t",
    "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/6h)", "Qin_lag2 (m3/6h)",
    "Rain_lag1 (mm)", "Rain_lag2 (mm)", "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)",
]
# [2026-09-25] อัปเดตตาม honest holdout comparison บนข้อมูลที่แก้ label แล้ว (ดู
# Spillway_check/06_ri_6h_experiment/train_final_shadow_models_CORRECTED.py -- BEST_FAMILY
# ต้องตรงกันเป๊ะระหว่าง 2 ไฟล์นี้ ไม่งั้น load_all_frozen_models() จะโหลดไฟล์โมเดลผิดตระกูล)
BEST_FAMILY = {
    1: "CatBoost_hurdle",
    2: "CatBoost_hurdle",
    3: "LightGBM",
    4: "LightGBM",
    5: "LightGBM",
    6: "CatBoost_hurdle",
    7: "XGBoost",
    8: "XGBoost",
    9: "XGBoost",
    10: "CatBoost_hurdle",
    11: "CatBoost_hurdle",
    12: "XGBoost",
}

# The frozen models were trained on ALL history through 2026-09-18 (see shadow_models/
# shadow_model_metadata.json). Marks at/after this point are the first ones NOT seen at
# training time for every horizon uniformly -- the true start of the shadow-test window.
# IMPORTANT: never lower this to backfill further into the past -- earlier marks were part
# of the training set for at least some horizons, so "predicting" them would be in-sample,
# not a real shadow test (this bit us once already: an early full-history backfill run had
# to be discarded for exactly this reason).
DEPLOY_START_MARK = datetime(2026, 9, 18, 7, 0)


def release_rate_m3_per_day(t):
    # end=None -- ยังไม่ปิด (load_release_events_from_csv() คืนแบบนี้ถ้าแถวไม่มี end_date/end_time)
    # ถือว่าคลุมตลอดตั้งแต่ start เป็นต้นไป ไม่มี upper bound
    return sum(
        rate for start, end, rate, _label in RELEASE_EVENTS
        if start <= t and (end is None or t <= end)
    )


def load_curve(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            rows.append([float(x) for x in row])
    rows.sort(key=lambda r: r[0])
    return rows


def xlookup_floor(level, table):
    best = table[0]
    for row in table:
        if row[0] <= level:
            best = row
        else:
            break
    return best


rating_curve = load_curve(os.path.join(HERE, "rating_curve_1cm.csv"))
area_terrain = load_curve(os.path.join(HERE, "area_terrain.csv"))


def storage_from_level(level):
    return xlookup_floor(level, rating_curve)[3]


def surface_area_from_level(level):
    return xlookup_floor(level, rating_curve)[2]


def terrain_area_from_level(level):
    return xlookup_floor(level, area_terrain)[2]


def spillway_overflow_m3(hourly_levels):
    """[2026-09-25 แก้] critical-flow+friction model (Manning n=0.017, b=10m) แทน constant-Cd
    เดิม (C=1.82) -- interp จาก lookup table ที่ precompute ไว้ (ดูคอมเมนต์บนสุดของไฟล์). สูตร
    เดียวกับที่ใช้สร้าง label เทรนโมเดลชุดนี้ (Training_6hourly_full_extended_CORRECTED.csv ->
    Spillway_check/06_ri_6h_experiment/build_corrected_6h_labels.py) -- ต้องตรงกันเป๊ะ ไม่งั้น
    train/inference skew"""
    total = 0.0
    for level in hourly_levels:
        adj = level - SPILLWAY_LEVEL_ADJ_OFFSET_M
        head = max(0.0, adj - SPILLWAY_CREST_LEVEL_MSL)
        q_m3_s = np.interp(head, _FRICTION_HEAD_GRID, _FRICTION_Q_GRID,
                            left=0.0, right=_FRICTION_Q_GRID[-1]) * SPILLWAY_WEIR_LENGTH_M
        total += float(q_m3_s) * 3600
    return total


def parse_raw_data_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["20260202_RES002"]
    rows = list(ws.iter_rows(values_only=True))[1:]
    level, rain = {}, {}
    for r in rows:
        if not r[0]:
            continue
        t = datetime.strptime(str(r[0])[:19], "%Y-%m-%d %H:%M:%S")
        if r[7] == "water_level":
            v = float(r[2])
            if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                level[t] = v
        elif r[7] == "rainfall_1h":
            rain[t] = float(r[2]) if r[2] is not None else None
    return level, rain


def parse_res002_july_csv(path):
    df = pd.read_csv(path)
    df = df[df["station_code"] == "RES002"]
    df["t"] = pd.to_datetime(df["measure_datetime"].str.replace(r"\+07$", "", regex=True))
    level, rain = {}, {}
    for _, r in df.iterrows():
        t = r["t"].to_pydatetime()
        v = r["data"]
        if pd.isna(v):
            continue
        v = float(v)
        if r["data_type"] == "water_level":
            if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                level[t] = v
        elif r["data_type"] == "rainfall_1h":
            rain[t] = v
    return level, rain


def parse_snapshot_store_df(df):
    """Same station/dt/dtype/value long format as the old api_snapshots.csv -- shared by
    the direct-download path and the local accumulating store."""
    df = df[df["station"] == "RES002"].copy()
    df["t"] = pd.to_datetime(df["dt"])
    level, rain = {}, {}
    lv = df[df["dtype"] == "water_level"]
    for _, r in lv.iterrows():
        v = pd.to_numeric(r["value"], errors="coerce")
        if pd.isna(v):
            continue
        v = float(v)
        if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
            level[r["t"].to_pydatetime()] = v
    rn = df[df["dtype"] == "rainfall_1h"]
    for _, r in rn.iterrows():
        v = pd.to_numeric(r["value"], errors="coerce")
        if pd.isna(v):
            continue
        rain[r["t"].to_pydatetime()] = float(v)
    return level, rain


def fetch_and_update_gdrive_store():
    """Download the raw_log sheet directly (same public link the Apps Script feeds and
    daily_update.py's ingest_gdrive_log() already downloads), merge into our own local
    accumulating store (dedup on station+dt+dtype, keep newest), and return the merged
    DataFrame. On any download failure, warn and fall back to whatever's already in the
    local store -- never crashes the run just because the network hiccuped."""
    new_df = None
    try:
        resp = requests.get(GDRIVE_EXPORT_URL, timeout=60)
        resp.raise_for_status()
        if resp.content[:2] != b"PK":  # xlsx = zip magic bytes
            raise RuntimeError("response is not an xlsx file (likely an HTML permission/login page "
                                "-- check the Sheet is still shared 'Anyone with the link')")
        raw = pd.read_excel(io.BytesIO(resp.content), sheet_name=GDRIVE_SHEET_NAME)
        raw = raw.rename(columns={"station_code": "station", "measure_datetime": "dt",
                                   "data_type": "dtype", "data": "value"})
        new_df = raw[["station", "dt", "dtype", "value"]].dropna(subset=["dt", "dtype"])
        print(f"[shadow_predict] Downloaded gdrive_log fresh: {len(new_df)} rows "
              f"(sheet={GDRIVE_SHEET_NAME!r})")
    except Exception as e:
        print(f"[shadow_predict] WARNING: gdrive_log download failed ({e}) -- "
              f"falling back to local store as-is.")

    if os.path.exists(RAW_STORE_PATH):
        old_df = pd.read_csv(RAW_STORE_PATH)
    else:
        old_df = pd.DataFrame(columns=["station", "dt", "dtype", "value"])

    if new_df is not None:
        merged = pd.concat([old_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["station", "dt", "dtype"], keep="last")
        merged.to_csv(RAW_STORE_PATH, index=False)
    else:
        merged = old_df

    if merged.empty:
        sys.exit("[shadow_predict] ERROR: no data in local store and download failed -- "
                  "cannot proceed (need at least one successful download to seed the store).")
    return merged


def build_hourly_grid(pts_sorted_list, start, end):
    by_hour = {}
    for t, v in pts_sorted_list:
        key = t.replace(minute=0, second=0, microsecond=0)
        by_hour.setdefault(key, []).append((t, v))
    grid = {}
    t = start
    while t <= end:
        candidates = by_hour.get(t, []) + by_hour.get(t - timedelta(hours=1), []) + by_hour.get(t + timedelta(hours=1), [])
        best, best_diff = None, None
        for ct, v in candidates:
            diff = abs((ct - t).total_seconds())
            if diff > 30 * 60:
                continue
            if best_diff is None or diff < best_diff:
                best, best_diff = v, diff
        grid[t] = best
        t += timedelta(hours=1)
    return grid


def build_6hourly_rows():
    raw_level, raw_rain = parse_raw_data_xlsx(os.path.join(HERE, "Raw Data_RES002 station.xlsx"))
    july_level, july_rain = parse_res002_july_csv(os.path.join(HERE, "RES002 July.csv"))
    store_df = fetch_and_update_gdrive_store()
    snap_level, snap_rain = parse_snapshot_store_df(store_df)

    level_pts = {**raw_level, **july_level, **snap_level}
    rain_pts = {**raw_rain, **july_rain, **snap_rain}
    level_sorted = sorted(level_pts.items())
    rain_sorted = sorted(rain_pts.items())

    grid_start = min(level_sorted[0][0], rain_sorted[0][0]).replace(minute=0, second=0, microsecond=0)
    grid_end = max(level_sorted[-1][0], rain_sorted[-1][0]).replace(minute=0, second=0, microsecond=0)
    hourly_level = build_hourly_grid(level_sorted, grid_start, grid_end)
    hourly_rain = build_hourly_grid(rain_sorted, grid_start, grid_end)

    # 2026-10-06: กรอง spike ชั่วคราวของระดับน้ำ (ดู spike_filter.py) ปิดได้ด้วย env SHADOW_DESPIKE=0
    # ไม่แก้ข้อมูลดิบ/store -- กรองเฉพาะกริดชั่วโมงในหน่วยความจำของรอบนี้
    if os.environ.get("SHADOW_DESPIKE", "1") != "0":
        try:
            sys.path.insert(0, HERE)
            from spike_filter import despike_hourly
            hourly_level, _spike_events = despike_hourly(hourly_level, hourly_rain)
            print(f"[shadow_predict] despike: แก้ {len(_spike_events)} เหตุการณ์ "
                  f"({', '.join(e['kind'] + '@' + e['start'].strftime('%m-%d %H') for e in _spike_events[-3:])}"
                  f"{' ...' if len(_spike_events) > 3 else ''})")
        except Exception as exc:  # ห้ามให้ตัวกรองล้ม pipeline -- ใช้ค่าดิบต่อ
            print(f"[shadow_predict] WARNING despike ล้มเหลว ({exc}) -- ใช้ระดับน้ำดิบ")

    def ma6h_trailing(t):
        vals = [hourly_level.get(t - timedelta(hours=i)) for i in range(0, 6)]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    def sum_rain_6h(t):
        vals = [hourly_rain.get(t - timedelta(hours=i)) for i in range(0, 6)]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    def raw_hourly_levels_6h(t):
        vals = [hourly_level.get(t - timedelta(hours=i)) for i in range(0, 6)]
        return [v for v in vals if v is not None]

    marks = []
    d = grid_start.date()
    end_date = grid_end.date()
    while d <= end_date:
        for h in MARK_HOURS:
            t = datetime(d.year, d.month, d.day, h)
            if grid_start <= t <= grid_end:
                marks.append(t)
        d += timedelta(days=1)
    marks.sort()

    rows = []
    prev_storage = None
    prev_api = None
    for t in marks:
        smoothed_level = ma6h_trailing(t)
        rain_6h = sum_rain_6h(t)
        raw_levels = raw_hourly_levels_6h(t)

        if smoothed_level is None or rain_6h is None or len(raw_levels) < 4:
            prev_storage = None
            prev_api = None
            continue

        storage = storage_from_level(smoothed_level)
        surface_area = surface_area_from_level(smoothed_level)
        terrain_area = terrain_area_from_level(smoothed_level)

        if prev_storage is None:
            prev_storage = storage
            prev_api = rain_6h
            continue

        delta_s = storage - prev_storage
        r_runoff = surface_area * (rain_6h / 1000.0)
        days_in_month = calendar.monthrange(2000, t.month)[1]
        evap_6h = surface_area * ((MONTHLY_EVAP_CONST_MM[t.month] / days_in_month / 4) * EVAP_PAN_COEFFICIENT) / 1000.0
        infiltration_6h = terrain_area * ((INFILTRATION_RATE_MM_PER_DAY / 4) / 1000.0)
        release_6h = release_rate_m3_per_day(t) / 4
        spill_6h = spillway_overflow_m3(raw_levels)

        q_in_raw = delta_s - r_runoff + release_6h + spill_6h + evap_6h + infiltration_6h
        q_in_6h = max(0.0, q_in_raw)
        api_t = API_K_6H * prev_api + rain_6h

        rows.append({
            "Datetime": t,
            "Q_in_t (m3/6h)": q_in_6h,
            "Water_Level_t (m)": smoothed_level,
            "Storage_S_t (m3)": storage,
            "DeltaS_t (m3/6h)": delta_s,
            "%Full_t": storage / RESERVOIR_STORAGE_MAX_M3 * 100,
            "Rain_obs_t (mm)": rain_6h,
            "API_t (mm)": api_t,
        })
        prev_storage = storage
        prev_api = api_t

    return rows


def add_segment_lag_feats(rows):
    """Same segment-aware logic as add_lag_and_targets_6h_extended.py, but we only need
    lag/rolling feats for the LAST row of each contiguous 6h segment."""
    rows = sorted(rows, key=lambda r: r["Datetime"])
    seg_id = 0
    prev_t = None
    for r in rows:
        if prev_t is not None and (r["Datetime"] - prev_t) != timedelta(hours=6):
            seg_id += 1
        r["_seg"] = seg_id
        prev_t = r["Datetime"]

    by_seg = {}
    for r in rows:
        by_seg.setdefault(r["_seg"], []).append(r)

    for seg_rows in by_seg.values():
        for i, r in enumerate(seg_rows):
            r["Qin_lag1 (m3/6h)"] = seg_rows[i - 1]["Q_in_t (m3/6h)"] if i >= 1 else None
            r["Qin_lag2 (m3/6h)"] = seg_rows[i - 2]["Q_in_t (m3/6h)"] if i >= 2 else None
            r["Rain_lag1 (mm)"] = seg_rows[i - 1]["Rain_obs_t (mm)"] if i >= 1 else None
            r["Rain_lag2 (mm)"] = seg_rows[i - 2]["Rain_obs_t (mm)"] if i >= 2 else None
            r["Rain_roll3 (mm)"] = sum(seg_rows[j]["Rain_obs_t (mm)"] for j in range(max(0, i - 2), i + 1)) if i >= 2 else None
            r["Rain_roll5 (mm)"] = sum(seg_rows[j]["Rain_obs_t (mm)"] for j in range(max(0, i - 4), i + 1)) if i >= 4 else None
            r["Rain_roll7 (mm)"] = sum(seg_rows[j]["Rain_obs_t (mm)"] for j in range(max(0, i - 6), i + 1)) if i >= 6 else None
    return rows


def load_all_frozen_models():
    models = {}
    for h in range(1, 13):
        family = BEST_FAMILY[h]
        if family == "CatBoost_hurdle":
            clf = joblib.load(os.path.join(MODELS_DIR, f"h{h}_clf.joblib"))
            reg = joblib.load(os.path.join(MODELS_DIR, f"h{h}_reg.joblib"))
            models[h] = (family, (clf, reg))
        else:
            model = joblib.load(os.path.join(MODELS_DIR, f"h{h}_model.joblib"))
            models[h] = (family, model)
    return models


def predict_for_horizon(models, h, X_row_df, base_qin):
    family, m = models[h]
    if family == "CatBoost_hurdle":
        clf, reg = m
        is_zero = bool(clf.predict(X_row_df)[0])
        if is_zero:
            return family, 0.0
        pred = float(np.clip(base_qin + reg.predict(X_row_df)[0], 0, None))
        return family, pred
    pred = float(np.clip(base_qin + m.predict(X_row_df)[0], 0, None))
    return family, pred


def build_prediction_row(models, row):
    """Build one shadow_predictions_log.csv row for a single (already causal, point-in-time)
    feature row. Safe to call for a historical mark, since add_segment_lag_feats() only ever
    looks backward within a row's own contiguous segment -- no future leakage."""
    issued_at = row["Datetime"]
    X_row_df = pd.DataFrame([{c: row[c] for c in FEATS}])
    base_qin = row["Q_in_t (m3/6h)"]
    out_row = {
        "issued_at": issued_at.isoformat(),
        "run_at": datetime.now().isoformat(),
        "persistence_qin_now": round(base_qin, 2),
    }
    for h in range(1, 13):
        target_t = issued_at + timedelta(hours=6 * h)
        family, pred = predict_for_horizon(models, h, X_row_df, base_qin)
        out_row[f"h{h}_family"] = family
        out_row[f"h{h}_target_datetime"] = target_t.isoformat()
        out_row[f"h{h}_pred_qin"] = round(pred, 2)
    return out_row, base_qin


def main():
    print(f"[shadow_predict] {datetime.now().isoformat()} -- self-contained mode "
          f"(direct gdrive_log download, store={RAW_STORE_PATH})")
    rows = build_6hourly_rows()
    rows = add_segment_lag_feats(rows)

    # ALL rows with complete features, oldest -> newest
    candidates = [r for r in rows if all(r.get(c) is not None for c in FEATS)]
    if not candidates:
        sys.exit("[shadow_predict] ERROR: no row with complete features found -- check raw data sources.")

    already_logged = set()
    write_header = not os.path.exists(LOG_PATH)
    if os.path.exists(LOG_PATH):
        existing = pd.read_csv(LOG_PATH)
        if not existing.empty:
            already_logged = set(existing["issued_at"].astype(str))

    # BACKFILL: if the PC/task was off for a while and several 6h marks piled up in the raw
    # data since the last run, log a prediction for every mark we haven't logged yet -- not
    # just the newest one. Each is computed causally (point-in-time, no future leakage), so
    # this is a legitimate retroactive shadow prediction, not just a gap-filler.
    to_log = [r for r in candidates
              if r["Datetime"] >= DEPLOY_START_MARK and r["Datetime"].isoformat() not in already_logged]
    if not to_log:
        print(f"[shadow_predict] Latest available mark ({candidates[-1]['Datetime'].isoformat()}) "
              f"already logged. No new complete 6h mark since last run -- nothing to do.")
        return

    models = load_all_frozen_models()
    print(f"[shadow_predict] {len(to_log)} new mark(s) to log "
          f"({'backfilling ' + str(len(to_log)-1) + ' missed run(s) + ' if len(to_log) > 1 else ''}"
          f"latest={to_log[-1]['Datetime'].isoformat()})")

    new_out_rows = []
    for row in to_log:
        out_row, base_qin = build_prediction_row(models, row)
        new_out_rows.append(out_row)
        print(f"[shadow_predict] issued_at={out_row['issued_at']}  Q_in_now={base_qin:.1f} m3/6h  "
              f"%Full={row['%Full_t']:.2f}")
        for h in range(1, 13):
            print(f"  H{h} ({6*h}h -> {out_row[f'h{h}_target_datetime']}, {out_row[f'h{h}_family']}): "
                  f"pred={out_row[f'h{h}_pred_qin']:.1f} m3/6h (persistence would say {base_qin:.1f})")

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(new_out_rows[0].keys()))
        if write_header:
            w.writeheader()
        w.writerows(new_out_rows)
    print(f"[shadow_predict] Logged {len(new_out_rows)} row(s) to {LOG_PATH}")


if __name__ == "__main__":
    main()
