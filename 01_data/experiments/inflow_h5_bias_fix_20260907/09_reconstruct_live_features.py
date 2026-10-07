import re, json
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime

RAW_DIR = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/Reservoirs/inflow")
LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")

RESERVOIR_STORAGE_MAX_M3 = 1625463.7590197
RESERVOIR_API_K = 0.95
RESERVOIR_PLAUSIBLE_PERCENT_FULL_MAX = 105.0
MONTH_NAME_TO_NUM = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,"July":7,"August":8,
    "September":9,"October":10,"November":11,"December":12,
}

FILE_PATTERN = re.compile(r"^(\d{4})_([A-Za-z]+)_MNR\.xlsx(\.bak_before_live_write_(\d{8})_(\d{6}))?$")

def parse_one_file(fpath: Path):
    """Read one monthly xlsx (or backup) and return list-of-dict daily raw rows."""
    m = re.match(r"^(\d{4})_([A-Za-z]+)_MNR\.xlsx", fpath.name)
    year_str, month_name = m.group(1), m.group(2)
    month_num = MONTH_NAME_TO_NUM.get(month_name)
    if month_num is None:
        return []
    raw_preview = pd.read_excel(fpath, sheet_name="บัญชีน้ำ", header=None, nrows=15)
    header_row = None
    for i in range(len(raw_preview)):
        if raw_preview.iloc[i].astype(str).str.strip().eq("Date").any():
            header_row = i
            break
    if header_row is None:
        return []
    df_month = pd.read_excel(fpath, sheet_name="บัญชีน้ำ", header=header_row)
    df_month.columns = [str(c).strip() for c in df_month.columns]
    date_col = next((c for c in df_month.columns if c == "Date"), None)
    level_col = next((c for c in df_month.columns if "Water Level" in c), None)
    storage_col = next((c for c in df_month.columns if "Water Volume" in c), None)
    inflow_col = next((c for c in df_month.columns if c.startswith("Inflow")), None)
    rain_col = next((c for c in df_month.columns if "Cumulative rainfall" in c), None)
    if date_col is None:
        return []
    day_numeric = pd.to_numeric(df_month[date_col], errors="coerce")
    valid_mask = day_numeric.notna()
    rows = []
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
        })
    return rows

def build_features_df(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
    df["Q_in_t"] = df["inflow"]
    df["Water_Level_t"] = df["water_level"]
    df["Storage_S_t"] = df["storage"]
    df["DeltaS_t"] = df["Storage_S_t"].diff()
    df["%Full_t"] = df["Storage_S_t"] / RESERVOIR_STORAGE_MAX_M3 * 100
    df["Rain_obs_t"] = df["rain_mm"]
    api_values = []
    prev_api = None
    for _, row in df.iterrows():
        rain = row["Rain_obs_t"]
        if pd.isna(rain):
            api_values.append(float("nan")); continue
        if prev_api is None:
            api_val = rain
        elif pd.isna(prev_api):
            api_val = rain
        else:
            api_val = RESERVOIR_API_K * prev_api + rain
        api_values.append(api_val)
        prev_api = api_val
    df["API_t"] = api_values
    df["Qin_lag1"] = df["Q_in_t"].shift(1)
    df["Qin_lag2"] = df["Q_in_t"].shift(2)
    df["Rain_roll3"] = df["Rain_obs_t"].rolling(3, min_periods=1).sum()
    df["Rain_roll5"] = df["Rain_obs_t"].rolling(5, min_periods=1).sum()
    df["Rain_roll7"] = df["Rain_obs_t"].rolling(7, min_periods=1).sum()
    feature_cols_clean = ["Q_in_t","Water_Level_t","Storage_S_t","DeltaS_t","%Full_t","Rain_obs_t","API_t",
                           "Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]
    complete = df[feature_cols_clean].notna().all(axis=1)
    plausible = df["%Full_t"].le(RESERVOIR_PLAUSIBLE_PERCENT_FULL_MAX)
    df["valid"] = complete & plausible
    return df

# discover all monthly base files and backups, grouped by (year,month)
all_files = list(RAW_DIR.glob("*/*.xlsx*"))
base_files = {}   # (year,month) -> Path (current/latest)
backups = {}       # (year,month) -> list of (timestamp, Path)
for f in all_files:
    m = FILE_PATTERN.match(f.name)
    if not m:
        continue
    year_str, month_name, is_bak, bdate, btime = m.groups()
    month_num = MONTH_NAME_TO_NUM.get(month_name)
    if month_num is None:
        continue
    key = (int(year_str), month_num)
    if is_bak:
        ts = datetime.strptime(bdate + btime, "%Y%m%d%H%M%S")
        backups.setdefault(key, []).append((ts, f))
    else:
        base_files[key] = f

for key in backups:
    backups[key].sort()

def get_file_for_asof(year, month, as_of_dt: pd.Timestamp):
    """Pick the earliest backup taken ON as_of_dt's calendar date for (year,month), else the base file
    if as_of_dt is beyond all backups (i.e. current month with no later backup needed), else the base file
    as last resort."""
    key = (year, month)
    cands = backups.get(key, [])
    same_day = [f for ts, f in cands if ts.date() == as_of_dt.date()]
    if same_day:
        return same_day[0]
    # else, find latest backup strictly before end of as_of_dt (best point-in-time match)
    before = [(ts, f) for ts, f in cands if ts.date() <= as_of_dt.date()]
    if before:
        before.sort()
        return before[-1][1]
    return base_files.get(key)

def build_raw_df_as_of(as_of_dt: pd.Timestamp):
    """Reconstruct the full continuous raw_df as production would have seen it on as_of_dt morning."""
    rows_all = []
    # walk months from 2025-06 through as_of_dt's month
    y, mo = 2025, 6
    while (y, mo) <= (as_of_dt.year, as_of_dt.month):
        fpath = get_file_for_asof(y, mo, as_of_dt) if (y, mo) == (as_of_dt.year, as_of_dt.month) else base_files.get((y, mo))
        if fpath and fpath.exists():
            try:
                rows_all.extend(parse_one_file(fpath))
            except Exception as e:
                print(f"  warn: failed parsing {fpath.name}: {e}")
        mo += 1
        if mo > 12:
            mo = 1; y += 1
    df = build_features_df(rows_all)
    if df.empty:
        return df
    # enforce no-lookahead: drop rows with date > as_of_dt
    df = df[df["date"] <= as_of_dt].reset_index(drop=True)
    return df

if __name__ == "__main__":
    # quick sanity test on one date
    test_date = pd.Timestamp("2026-08-13")
    df = build_raw_df_as_of(test_date)
    valid = df[df["valid"]]
    print(f"as_of {test_date.date()}: {len(df)} raw rows, {len(valid)} valid, latest valid date: {valid['date'].max() if not valid.empty else None}")
    print(valid.iloc[-1][["date","Q_in_t","Water_Level_t","Storage_S_t","%Full_t","Rain_obs_t","API_t","Qin_lag1","Qin_lag2","Rain_roll3","Rain_roll5","Rain_roll7"]] if not valid.empty else "NONE")
