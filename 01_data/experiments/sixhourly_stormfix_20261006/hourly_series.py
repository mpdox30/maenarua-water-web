# -*- coding: utf-8 -*-
"""
Build the hourly level/rain grids for RES002 exactly as shadow_predict.build_6hourly_rows() does
(same sources, same nearest-to-the-hour rule), but EXPOSE the hourly grids so issue-time features
can be computed. Offline: reads the local accumulating store only (no network).

Optional tail extension: the local store stops at the last time shadow_predict.py ran on Windows.
`extend_from_display_json=True` appends hourly levels (and rain=0 where the display file shows no
rain) from 03_website/assets/data/inflow_6h_display.json for hours AFTER the store ends -- used ONLY
for the 2026-10-05 storm replay, and flagged in the returned `extended_hours` set.
"""
import json, os, sys
from datetime import datetime, timedelta
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "sixhourly_refresh_20260918"))
sys.path.insert(0, SRC)
import shadow_predict as sp  # noqa: E402  (module-level constants/functions only; no network at import)

DISPLAY_JSON = os.path.normpath(os.path.join(HERE, "..", "..", "..", "03_website", "assets", "data", "inflow_6h_display.json"))


def load_hourly(extend_from_display_json=False):
    raw_level, raw_rain = sp.parse_raw_data_xlsx(os.path.join(SRC, "Raw Data_RES002 station.xlsx"))
    july_level, july_rain = sp.parse_res002_july_csv(os.path.join(SRC, "RES002 July.csv"))
    store = pd.read_csv(os.path.join(SRC, "shadow_gdrive_raw_store.csv"))
    snap_level, snap_rain = sp.parse_snapshot_store_df(store)

    level_pts = {**raw_level, **july_level, **snap_level}
    rain_pts = {**raw_rain, **july_rain, **snap_rain}
    level_sorted = sorted(level_pts.items())
    rain_sorted = sorted(rain_pts.items())
    start = min(level_sorted[0][0], rain_sorted[0][0]).replace(minute=0, second=0, microsecond=0)
    end = max(level_sorted[-1][0], rain_sorted[-1][0]).replace(minute=0, second=0, microsecond=0)
    hl = sp.build_hourly_grid(level_sorted, start, end)
    hr = sp.build_hourly_grid(rain_sorted, start, end)
    extended = set()

    if extend_from_display_json:
        d = json.load(open(DISPLAY_JSON, encoding="utf-8"))
        disp_level = {}
        disp_rain6 = {}
        for w in d["windows"]:
            we = datetime.fromisoformat(w["window_end"])
            disp_level[we] = w["water_level_end_m"]
            disp_rain6[we] = w["rain_6h_mm"]
        # validation on the overlap: display levels must equal store levels
        diffs = [abs(disp_level[t] - hl[t]) for t in disp_level if t in hl and hl[t] is not None]
        print(f"[hourly_series] overlap store vs display json: n={len(diffs)} max|dlevel|={max(diffs):.4f}")
        t = end + timedelta(hours=1)
        last = max(disp_level)
        while t <= last:
            if t in disp_level:
                hl[t] = disp_level[t]
                # rain after the store ends: the display file shows 0 mm for every window that
                # ends after 19:00 on 2026-10-05 (checked), so hourly rain = 0 here
                hr[t] = 0.0
                extended.add(t)
            t += timedelta(hours=1)
    return hl, hr, extended
