import pandas as pd, numpy as np
from pathlib import Path

arc = pd.read_csv("rain_forecast_archive_raw.csv", parse_dates=["issue_date","forecast_date"])
print("rows:", len(arc))
print("issue_date range:", arc["issue_date"].min(), "to", arc["issue_date"].max())
print("unique issue dates:", arc["issue_date"].nunique())
print("lead_day values:", sorted(arc["lead_day"].unique()))

counts = arc.groupby("issue_date")["lead_day"].nunique()
bad = counts[counts != 8]
print(f"\nissue_dates with != 8 lead days: {len(bad)}")
if len(bad):
    print(bad.head(20))

print("\nnull precipitation rows:", arc["precipitation_sum_mm"].isna().sum())
print("negative precipitation rows:", (arc["precipitation_sum_mm"] < 0).sum())
print("\nprecip stats:", arc["precipitation_sum_mm"].describe())

# sanity: compare lead_day=0 forecast (same-day "forecast") against actual observed Rain_obs_t
# from training CSV, to gauge whether the archive is credible
ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
train = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"])
lead0 = arc[arc["lead_day"]==0][["issue_date","precipitation_sum_mm"]].rename(columns={"issue_date":"Date","precipitation_sum_mm":"fcst_lead0_mm"})
merged = train.merge(lead0, on="Date", how="inner")
merged["abs_diff"] = (merged["fcst_lead0_mm"] - merged["Rain_obs_t (mm)"]).abs()
print(f"\nlead0-vs-observed sanity check (n={len(merged)}):")
print("correlation:", merged["fcst_lead0_mm"].corr(merged["Rain_obs_t (mm)"]))
print("MAE lead0 vs Rain_obs_t:", merged["abs_diff"].mean())
print(merged[["Date","Rain_obs_t (mm)","fcst_lead0_mm"]].sample(10, random_state=1).sort_values("Date"))
