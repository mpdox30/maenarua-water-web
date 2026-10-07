# -*- coding: utf-8 -*-
"""
Extended 6-hourly training set through 2026-09-17 -- reuses the EXACT water-balance
methodology from 01_data/experiments/hourly_feasibility_20260731/build_6hourly_training.py
(same constants, same RELEASE_EVENTS timeline, same rating curve, same evap/infiltration
approximation, same sensor-glitch plausibility band) but stitches in the two NEW raw
sources discovered 2026-09-18 that extend coverage from 2026-07-31 to today:
  - WMB_Phayao/01_raw_data/Reservoirs/RES002 July.csv (10-min, fills the 2026-06-27..07-06
    tail gap after the original Raw Data xlsx ends)
  - WMB_Phayao/09_live/data/api_snapshots.csv (10-min nominal, 2026-07-10 -> today, this
    IS the live gdrive_log telemetry store, growing daily)
"""
import calendar
import csv
import os
from datetime import datetime, timedelta

import openpyxl
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WMB_ROOT = "/sessions/busy-awesome-cerf/mnt/WMB_Phayao"

SPILLWAY_LEVEL_ADJ_OFFSET_M = 0.155
SPILLWAY_CREST_LEVEL_MSL = 489.545
SPILLWAY_WEIR_COEFFICIENT_C = 1.82
SPILLWAY_WEIR_LENGTH_M = 30
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

RELEASE_EVENTS = [
    # 2026-09-18 CORRECTED against the user's authoritative source file
    # "ตารางเก็บข้อมูลการจ่ายน้ำของอ่างเก็บน้ำ.xlsx" (ครั้งที่ 1-9). Replaces the earlier
    # guessed placeholder for the current 2026 event, which wrongly assumed release
    # continued through 2026-10-14 (copied from the 2025 seasonal pattern) -- the real
    # closing date is 2026-08-04, over 2 months earlier. That bug added a phantom ~9,446
    # m3/day of "release" into every day's Q_in calc from 2026-08-04 through whenever this
    # fix lands, including the entire September flood event. Two events (ครั้งที่ 6 and 8)
    # were also missing entirely from the old list.
    (datetime(2025, 6, 26, 10, 0), datetime(2025, 10, 14, 13, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.1"),
    (datetime(2025, 6, 26, 10, 0), datetime(2025, 10, 14, 13, 0), RELEASE_RATE_INLET_6TURNS, "no.2"),
    (datetime(2025, 10, 18, 10, 0), datetime(2025, 11, 6, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.1(2)"),
    (datetime(2025, 10, 18, 10, 0), datetime(2025, 11, 7, 10, 0), RELEASE_RATE_INLET_6TURNS, "no.2(2)"),
    (datetime(2026, 1, 6, 10, 0), datetime(2026, 1, 8, 10, 0), RELEASE_RATE_INLET_6TURNS, "no.3"),
    (datetime(2026, 2, 2, 10, 0), datetime(2026, 2, 5, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.4"),
    # ครั้งที่ 5: sheet shows start 27 มี.ค. 69, close 21 มี.ค. 69 (close BEFORE start --
    # data-entry error in the source file). Using the more physically plausible reading
    # (dates swapped: 21->27 Mar, a 6-day release matching the duration of similar short
    # events elsewhere in the table). Flag to user: confirm the real dates if this matters
    # for any period-specific analysis (low impact here -- outside the Sep 2026 window).
    (datetime(2026, 3, 21, 10, 0), datetime(2026, 3, 27, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.5(ambiguous dates, see comment)"),
    (datetime(2026, 3, 29, 10, 0), datetime(2026, 3, 30, 10, 0), RELEASE_RATE_INLET_6TURNS, "no.6"),
    (datetime(2026, 4, 10, 10, 0), datetime(2026, 4, 18, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.7"),
    (datetime(2026, 6, 15, 10, 0), datetime(2026, 6, 18, 10, 0), RELEASE_RATE_SPILLWAY_6TURNS, "no.8"),
    # ครั้งที่ 9: the CORRECTED current event -- closes 2026-08-04, NOT 2026-10-14.
    # Closing time in source = "17.3" (unusual format vs. others' plain hour) -- read as
    # 17:18. No release event covers 2026-08-04 onward as of this fix.
    (datetime(2026, 6, 29, 10, 0), datetime(2026, 8, 4, 17, 18), RELEASE_RATE_SPILLWAY_6TURNS, "no.9"),
]

PLAUSIBLE_LEVEL_MIN = 487.5
PLAUSIBLE_LEVEL_MAX = 491.0


def release_rate_m3_per_day(t):
    return sum(rate for start, end, rate, _label in RELEASE_EVENTS if start <= t <= end)


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
    total = 0.0
    for level in hourly_levels:
        adj = level - SPILLWAY_LEVEL_ADJ_OFFSET_M
        head = max(0.0, adj - SPILLWAY_CREST_LEVEL_MSL)
        q_m3_s = SPILLWAY_WEIR_COEFFICIENT_C * SPILLWAY_WEIR_LENGTH_M * (head ** 1.5)
        total += q_m3_s * 3600
    return total


def parse_raw_data_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["20260202_RES002"]
    rows = list(ws.iter_rows(values_only=True))[1:]
    level, rain = {}, {}
    n_rejected = 0
    for r in rows:
        if not r[0]:
            continue
        t = datetime.strptime(str(r[0])[:19], "%Y-%m-%d %H:%M:%S")
        if r[7] == "water_level":
            v = float(r[2])
            if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                level[t] = v
            else:
                n_rejected += 1
        elif r[7] == "rainfall_1h":
            rain[t] = float(r[2]) if r[2] is not None else None
    if n_rejected:
        print(f"  parse_raw_data_xlsx: rejected {n_rejected} implausible readings")
    return level, rain


def parse_res002_july_csv(path):
    """WMB_Phayao/01_raw_data/Reservoirs/RES002 July.csv -- station_code,measure_datetime
    (has +07 tz suffix), time, data, station_name, lat, lon, quality_flag, data_type"""
    df = pd.read_csv(path)
    df = df[df["station_code"] == "RES002"]
    df["t"] = pd.to_datetime(df["measure_datetime"].str.replace(r"\+07$", "", regex=True))
    level, rain = {}, {}
    n_rejected = 0
    for _, r in df.iterrows():
        t = r["t"].to_pydatetime()
        v = r["data"]
        if pd.isna(v):
            continue
        v = float(v)
        if r["data_type"] == "water_level":
            if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
                level[t] = v
            else:
                n_rejected += 1
        elif r["data_type"] == "rainfall_1h":
            rain[t] = v
    if n_rejected:
        print(f"  parse_res002_july_csv: rejected {n_rejected} implausible readings")
    return level, rain


def parse_api_snapshots_csv(path):
    """WMB_Phayao/09_live/data/api_snapshots.csv -- long format: station,dt,dtype,value"""
    df = pd.read_csv(path)
    df = df[df["station"] == "RES002"]
    df["t"] = pd.to_datetime(df["dt"])
    level, rain = {}, {}
    n_rejected = 0
    lv = df[df["dtype"] == "water_level"]
    for _, r in lv.iterrows():
        v = pd.to_numeric(r["value"], errors="coerce")
        if pd.isna(v):
            continue
        v = float(v)
        if PLAUSIBLE_LEVEL_MIN <= v <= PLAUSIBLE_LEVEL_MAX:
            level[r["t"].to_pydatetime()] = v
        else:
            n_rejected += 1
    rn = df[df["dtype"] == "rainfall_1h"]
    for _, r in rn.iterrows():
        v = pd.to_numeric(r["value"], errors="coerce")
        if pd.isna(v):
            continue
        rain[r["t"].to_pydatetime()] = float(v)
    if n_rejected:
        print(f"  parse_api_snapshots_csv: rejected {n_rejected} implausible readings")
    return level, rain


raw_level, raw_rain = parse_raw_data_xlsx(os.path.join(HERE, "Raw Data_RES002 station.xlsx"))
print(f"Raw Data xlsx: {len(raw_level)} level pts ({min(raw_level):%Y-%m-%d}..{max(raw_level):%Y-%m-%d})")

july_level, july_rain = parse_res002_july_csv(os.path.join(WMB_ROOT, "01_raw_data/Reservoirs/RES002 July.csv"))
print(f"RES002 July.csv: {len(july_level)} level pts ({min(july_level):%Y-%m-%d}..{max(july_level):%Y-%m-%d})")

snap_level, snap_rain = parse_api_snapshots_csv(os.path.join(WMB_ROOT, "09_live/data/api_snapshots.csv"))
print(f"api_snapshots.csv: {len(snap_level)} level pts ({min(snap_level):%Y-%m-%d}..{max(snap_level):%Y-%m-%d})")

# merge -- later/more-authoritative sources override earlier ones on exact-timestamp overlap
level_pts = {**raw_level, **july_level, **snap_level}
rain_pts = {**raw_rain, **july_rain, **snap_rain}
level_sorted = sorted(level_pts.items())
rain_sorted = sorted(rain_pts.items())
print(f"\nMerged: level points: {len(level_sorted)} ({level_sorted[0][0]} .. {level_sorted[-1][0]}), "
      f"rain points: {len(rain_sorted)}")


def nearest_value(target_t, pts_sorted_list, tolerance_min=30):
    best, best_diff = None, None
    for t, v in pts_sorted_list:
        diff = abs((t - target_t).total_seconds())
        if diff > tolerance_min * 60:
            continue
        if best_diff is None or diff < best_diff:
            best, best_diff = v, diff
    return best


def build_hourly_grid(pts_sorted_list, start, end):
    # index by hour bucket for speed (linear nearest_value over full list is O(n) per call --
    # too slow now with ~50k points; use a dict keyed by rounded hour instead with a small
    # local window search)
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


grid_start = min(level_sorted[0][0], rain_sorted[0][0]).replace(minute=0, second=0, microsecond=0)
grid_end = max(level_sorted[-1][0], rain_sorted[-1][0]).replace(minute=0, second=0, microsecond=0)
print(f"Building hourly grid {grid_start} .. {grid_end} ...")
hourly_level = build_hourly_grid(level_sorted, grid_start, grid_end)
hourly_rain = build_hourly_grid(rain_sorted, grid_start, grid_end)
n_hours_with_level = sum(1 for v in hourly_level.values() if v is not None)
print(f"Hourly grid built: {len(hourly_level)} hours total, {n_hours_with_level} with a level reading "
      f"({n_hours_with_level/len(hourly_level)*100:.1f}% coverage)")


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


def is_release_active(t):
    return release_rate_m3_per_day(t) > 0


MARK_HOURS = [1, 7, 13, 19]
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
print(f"6h marks in range: {len(marks)}")

rows = []
prev_storage = None
prev_api = None
n_gap_skips = 0
for t in marks:
    smoothed_level = ma6h_trailing(t)
    rain_6h = sum_rain_6h(t)
    raw_levels = raw_hourly_levels_6h(t)

    if smoothed_level is None or rain_6h is None or len(raw_levels) < 4:
        prev_storage = None
        prev_api = None
        n_gap_skips += 1
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
        "Datetime": t.isoformat(),
        "Q_in_t (m3/6h)": round(q_in_6h, 4),
        "Water_Level_t (m)": round(smoothed_level, 4),
        "Storage_S_t (m3)": round(storage, 2),
        "DeltaS_t (m3/6h)": round(delta_s, 2),
        "%Full_t": round(storage / RESERVOIR_STORAGE_MAX_M3 * 100, 4),
        "Rain_obs_t (mm)": round(rain_6h, 3),
        "API_t (mm)": round(api_t, 4),
        "is_release_active": int(is_release_active(t)),
        "release_rate_daily (m3/day)": round(release_rate_m3_per_day(t), 1),
        "spill_m3": round(spill_6h, 2),
    })

    prev_storage = storage
    prev_api = api_t

print(f"\nRows built: {len(rows)} / {len(marks)} possible marks ({len(rows)/len(marks)*100:.1f}% coverage), "
      f"{n_gap_skips} marks skipped due to data gaps")
print(f"Date range of built rows: {rows[0]['Datetime']} .. {rows[-1]['Datetime']}")

out_path = os.path.join(HERE, "Training_6hourly_raw_extended_20260918.csv")
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"Saved {out_path}")
