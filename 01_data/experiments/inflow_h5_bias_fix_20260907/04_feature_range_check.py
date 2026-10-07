import pandas as pd, numpy as np
from pathlib import Path

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")
FEATS = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
         '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
         'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']

df = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"])
print("Training date range:", df["Date"].min(), "to", df["Date"].max())
print("\nFeature ranges in training data:")
print(df[FEATS].describe().T[["min","25%","50%","75%","max"]])

print("\ny5 target range:", df["y5=Q_in_t+5 (m3/day)"].min(), df["y5=Q_in_t+5 (m3/day)"].max())
print("Q_in_t max:", df["Q_in_t (m3/day)"].max(), "at", df.loc[df["Q_in_t (m3/day)"].idxmax(), "Date"])
print("Rain_roll7 max:", df["Rain_roll7 (mm)"].max())
print("API_t max:", df["API_t (mm)"].max())

# Which rows have extreme y5 (large deltas) that h5 model may have overfit to?
df["delta5"] = df["y5=Q_in_t+5 (m3/day)"] - df["Q_in_t (m3/day)"]
print("\nTop 5 rows by |delta5|:")
print(df.nlargest(5, "delta5")[["Date","Q_in_t (m3/day)","y5=Q_in_t+5 (m3/day)","delta5","Rain_roll7 (mm)","API_t (mm)"]])
