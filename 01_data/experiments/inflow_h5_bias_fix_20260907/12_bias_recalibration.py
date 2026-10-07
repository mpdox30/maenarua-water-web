import json
import pandas as pd, numpy as np
from pathlib import Path

LOG = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/forecasting_results/Reservoir_inflow/forecast_accuracy_log.csv")
EXP = Path.cwd()

log = pd.read_csv(LOG, parse_dates=["recorded_as_of_date","target_date"])
log_c = log[log["actual_data_complete"] == True].copy().sort_values(["horizon","recorded_as_of_date"])

recon = pd.read_csv(EXP / "reconstructed_vs_log_v2.csv", parse_dates=["recorded_as_of_date"])
h5_v2_map = recon[(recon["horizon"]==5) & recon["pred_v2_reconstructed"].notna()].set_index("recorded_as_of_date")["pred_v2_reconstructed"]

# "base" prediction per horizon: use h5_v2 reconstructed pred for horizon 5 (fixed model), else the
# original logged prediction (h1-4,6,7 unaffected by the h5-specific bug).
log_c["base_pred"] = log_c["predicted_m3_per_day"]
mask5 = log_c["horizon"] == 5
log_c.loc[mask5, "base_pred"] = log_c.loc[mask5, "recorded_as_of_date"].map(h5_v2_map)
log_c = log_c.dropna(subset=["base_pred"])

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

FIT_FRAC = 0.65
rows_report = []
for h, g in log_c.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n*FIT_FRAC), 5)
    fit, hold = g.iloc[:cut], g.iloc[cut:]
    if len(hold) < 3:
        continue
    bias_fit = (fit["base_pred"] - fit["actual_m3_per_day"]).mean()

    # holdout metrics BEFORE correction
    mae_before = (hold["base_pred"] - hold["actual_m3_per_day"]).abs().mean()
    bias_before = (hold["base_pred"] - hold["actual_m3_per_day"]).mean()
    nse_before = nse(hold["actual_m3_per_day"], hold["base_pred"])

    # apply additive correction fit on FIT set, evaluate on HOLDOUT (honest out-of-sample)
    corrected = (hold["base_pred"] - bias_fit).clip(lower=0.0)
    mae_after = (corrected - hold["actual_m3_per_day"]).abs().mean()
    bias_after = (corrected - hold["actual_m3_per_day"]).mean()
    nse_after = nse(hold["actual_m3_per_day"], corrected)

    rows_report.append(dict(
        horizon=h, n_fit=len(fit), n_holdout=len(hold), bias_correction=bias_fit,
        mae_before=mae_before, mae_after=mae_after,
        bias_before=bias_before, bias_after=bias_after,
        nse_before=nse_before, nse_after=nse_after,
    ))

rep = pd.DataFrame(rows_report)
pd.set_option("display.width", 160)
print(rep.round(1).to_string(index=False))
rep.to_csv(EXP / "bias_recalibration_holdout_results.csv", index=False)
print("\nsaved bias_recalibration_holdout_results.csv")

# overall MAE improvement summary
total_mae_before = rep["mae_before"].mul(rep["n_holdout"]).sum() / rep["n_holdout"].sum()
total_mae_after = rep["mae_after"].mul(rep["n_holdout"]).sum() / rep["n_holdout"].sum()
print(f"\nWeighted-avg holdout MAE across horizons: before={total_mae_before:.0f}  after={total_mae_after:.0f}  "
      f"improvement={100*(1-total_mae_after/total_mae_before):.1f}%")
