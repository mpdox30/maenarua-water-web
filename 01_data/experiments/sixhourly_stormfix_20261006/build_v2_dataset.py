# -*- coding: utf-8 -*-
"""
Build the v2 6-hourly dataset: END-OF-WINDOW ("issue-time") Q_in and features.

Why (finding of 2026-10-06, 5 Oct storm): the production-shadow dataset smooths the water level with a
trailing 6h moving average BEFORE computing DeltaS, so a surge that happens inside the window is
smeared into the NEXT mark. At the 13:00 mark on 2026-10-05 (49 mm rain, level 489.42 -> 489.90)
the smoothed Q_in was 176 m3/6h while the physical inflow of that window was ~95,000 m3/6h, so every
lag/persistence feature said "nothing is happening".

v2 definition (all quantities use ONLY data available at the mark t):
  Qend_t = max(0, S(L_t) - S(L_{t-6h}) - runoff + release + spill(6 hourly levels) + evap + infil)
  with L_t the hourly level AT the mark (no smoothing). Same constants/formula pieces as
  shadow_predict.py (same spillway lookup, same release_events.csv, same evap/infiltration).
Extra issue-time features: level rate of change (1h/3h/6h), head above crest, last-1/2/3h rain,
max hourly rain in the window.
Targets: y_h = Qend_{t+h}.  Old-definition columns/targets are merged in from the existing
Training_6hourly_full_extended_20260918.csv (variant A) so all variants share the same rows.
"""
import calendar, os, sys
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hourly_series as hs
sp = hs.sp

OLD_CSV = os.path.join(hs.SRC, "Training_6hourly_full_extended_20260918.csv")
CREST_ADJ = sp.SPILLWAY_CREST_LEVEL_MSL


def mark_times(hl):
    ts = sorted(hl)
    t = ts[0].replace(hour=0)
    out = []
    while t <= ts[-1]:
        for h in sp.MARK_HOURS:
            m = t.replace(hour=h)
            if ts[0] <= m <= ts[-1]:
                out.append(m)
        t += timedelta(days=1)
    return sorted(out)


def window_levels(hl, t):
    return [hl.get(t - timedelta(hours=i)) for i in range(0, 6)]


def compute_mark_rows(hl, hr):
    rows = []
    for t in mark_times(hl):
        L = hl.get(t)
        L6 = hl.get(t - timedelta(hours=6))
        lv6 = [v for v in window_levels(hl, t) if v is not None]
        rn6 = [hr.get(t - timedelta(hours=i)) for i in range(0, 6)]
        rn_ok = [v for v in rn6 if v is not None]
        if L is None or L6 is None or len(lv6) < 4 or not rn_ok:
            continue
        S, S6 = sp.storage_from_level(L), sp.storage_from_level(L6)
        area = sp.surface_area_from_level(L)
        terr = sp.terrain_area_from_level(L)
        rain_6h = float(sum(rn_ok))
        dim = calendar.monthrange(2000, t.month)[1]
        evap = area * ((sp.MONTHLY_EVAP_CONST_MM[t.month] / dim / 4) * sp.EVAP_PAN_COEFFICIENT) / 1000.0
        infil = terr * ((sp.INFILTRATION_RATE_MM_PER_DAY / 4) / 1000.0)
        runoff = area * (rain_6h / 1000.0)
        release = sp.release_rate_m3_per_day(t) / 4
        spill = sp.spillway_overflow_m3(lv6)
        qend = max(0.0, (S - S6) - runoff + release + spill + evap + infil)
        def lvl(h):
            return hl.get(t - timedelta(hours=h))
        def dl(h):
            a = lvl(h)
            return (L - a) if a is not None else np.nan
        def rn(i):
            v = hr.get(t - timedelta(hours=i))
            return 0.0 if v is None else float(v)
        rows.append({
            "Datetime": t, "Qend": qend, "L_end": L, "S_end": S,
            "pctfull_end": S / sp.RESERVOIR_STORAGE_MAX_M3 * 100,
            "dL_1h": dl(1), "dL_3h": dl(3), "dL_6h": L - L6,
            "head_end": max(0.0, L - sp.SPILLWAY_LEVEL_ADJ_OFFSET_M - CREST_ADJ),
            "rain_h1": rn(0), "rain_h2": rn(0) + rn(1), "rain_h3": rn(0) + rn(1) + rn(2),
            "rain_max1h": float(max(rn_ok)), "rain_6h_end": rain_6h,
            "spill_end": spill, "release_end": release,
        })
    df = pd.DataFrame(rows).sort_values("Datetime").reset_index(drop=True)
    # contiguity-safe lags + targets
    idx = df.set_index("Datetime")["Qend"]
    for k in (1, 2):
        df[f"Qend_lag{k}"] = [idx.get(t - timedelta(hours=6 * k), np.nan) for t in df.Datetime]
    for h in range(1, 13):
        df[f"y{h}_end"] = [idx.get(t + timedelta(hours=6 * h), np.nan) for t in df.Datetime]
    ridx = df.set_index("Datetime")["rain_6h_end"]
    for k in (1, 2):
        df[f"rain6_lag{k}"] = [ridx.get(t - timedelta(hours=6 * k), np.nan) for t in df.Datetime]
    return df


def build(extend=False):
    hl, hr, ext = hs.load_hourly(extend_from_display_json=extend)
    return compute_mark_rows(hl, hr), ext


if __name__ == "__main__":
    df, _ = build(False)
    old = pd.read_csv(OLD_CSV, parse_dates=["Datetime"])
    m = old.merge(df, on="Datetime", how="inner")
    out = os.path.join(HERE, "Training_v2_6h.csv")
    m.to_csv(out, index=False)
    print("v2 rows:", len(m), m.Datetime.min(), m.Datetime.max())
    # sanity: relation old smoothed Q_in vs new end-based Q
    print("corr(Q_in smoothed, Qend) =", round(m["Q_in_t (m3/6h)"].corr(m["Qend"]), 3))
    print(m[["Q_in_t (m3/6h)", "Qend"]].describe().round(0).to_string())
    # lead/lag: which shift of Qend best matches the smoothed Q_in?
    for k in (-1, 0, 1):
        print("corr(smoothed_t, Qend_t%+d) =" % k, round(m["Q_in_t (m3/6h)"].corr(m["Qend"].shift(k)), 3))
