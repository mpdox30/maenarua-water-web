import pandas as pd, numpy as np
from pathlib import Path

LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")
df = pd.read_csv(LOG, parse_dates=["recorded_as_of_date", "target_date"])
df_c = df[df["actual_data_complete"] == True].copy()
print("total rows:", len(df), "complete:", len(df_c))
print(df_c["horizon"].value_counts().sort_index())

def nse(actual, pred):
    actual = np.asarray(actual, dtype=float); pred = np.asarray(pred, dtype=float)
    denom = np.sum((actual - actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom != 0 else np.nan

print(f"\n{'h':>2} {'n':>4} {'MAE':>12} {'Bias':>12} {'MedAE':>12} {'NSE':>8} {'corr':>8}")
summary = {}
for h, g in df_c.groupby("horizon"):
    mae = (g["predicted_m3_per_day"] - g["actual_m3_per_day"]).abs().mean()
    bias = (g["predicted_m3_per_day"] - g["actual_m3_per_day"]).mean()
    medae = (g["predicted_m3_per_day"] - g["actual_m3_per_day"]).abs().median()
    n_ = nse(g["actual_m3_per_day"], g["predicted_m3_per_day"])
    corr = g["predicted_m3_per_day"].corr(g["actual_m3_per_day"])
    summary[h] = dict(n=len(g), mae=mae, bias=bias, medae=medae, nse=n_, corr=corr)
    print(f"{h:>2} {len(g):>4} {mae:>12.1f} {bias:>12.1f} {medae:>12.1f} {n_:>8.3f} {corr:>8.3f}")

# cross-horizon same-day pivot to re-confirm h5 anomaly
piv = df_c.pivot_table(index="recorded_as_of_date", columns="horizon", values="predicted_m3_per_day")
piv = piv.dropna(subset=[4,5,6]) if 4 in piv.columns and 5 in piv.columns and 6 in piv.columns else piv
if all(c in piv.columns for c in [4,5,6]):
    piv["h5_vs_h4h6_avg_ratio"] = piv[5] / ((piv[4]+piv[6])/2 + 1e-9)
    print("\nh5 vs avg(h4,h6) ratio stats:")
    print(piv["h5_vs_h4h6_avg_ratio"].describe())
    print("\nDays where h5 predicted >1.5x the avg of h4,h6:")
    print(piv[piv["h5_vs_h4h6_avg_ratio"] > 1.5][[4,5,6,"h5_vs_h4h6_avg_ratio"]])

import json
with open("log_baseline_summary.json", "w") as f:
    json.dump({str(k): {kk: (float(vv) if vv==vv else None) for kk,vv in v.items()} for k,v in summary.items()}, f, indent=2)
