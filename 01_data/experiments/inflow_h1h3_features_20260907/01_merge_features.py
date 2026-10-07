import pandas as pd
from pathlib import Path

EXP = Path.cwd()
RAINEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_rain_forecast_feature_20260907")
FEATEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/feature_experiments_20260731")
RELEASE_CSV = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/Reservoirs/release_log/release_events.csv")

# base training data (393 rows, 2025-06-27 .. 2026-07-24), already has rain-forecast columns
df = pd.read_csv(RAINEXP / "training_with_rain_forecast_features.csv", parse_dates=["Date"])

# --- feature 2/3: daily_max_level_24h / daily_range_24h (reuse already-built 386-day history) ---
rng = pd.read_csv(FEATEXP / "intraday_range_full_history.csv", parse_dates=["Date"])
df = df.merge(rng[["Date", "max_level_24h", "min_level_24h", "range_24h"]], on="Date", how="left")
print("range feature coverage:", df["range_24h"].notna().sum(), "/", len(df))

# --- feature 1: is_release_active / release_rate_m3day, recomputed fresh from release_events.csv ---
# (release_events.csv may have been updated since 2026-07-31; recompute rather than reuse old copy)
rel = pd.read_csv(RELEASE_CSV, parse_dates=["start_date", "end_date"])

def release_state(d):
    active = rel[(rel["start_date"] <= d) & (d <= rel["end_date"])]
    if len(active) == 0:
        return 0, 0.0
    return 1, float(active["rate_m3_per_day"].sum())

states = df["Date"].apply(release_state)
df["is_release_active"] = [s[0] for s in states]
df["release_rate_m3day"] = [s[1] for s in states]
print("release-active rows:", df["is_release_active"].sum(), "/", len(df),
      "date range active:", df.loc[df.is_release_active==1, "Date"].min(), "..",
      df.loc[df.is_release_active==1, "Date"].max())

df.to_csv(EXP / "training_with_new_features.csv", index=False)
print("\nsaved training_with_new_features.csv", df.shape)
print(df[["Date","max_level_24h","range_24h","is_release_active","release_rate_m3day"]].tail(10).to_string())
