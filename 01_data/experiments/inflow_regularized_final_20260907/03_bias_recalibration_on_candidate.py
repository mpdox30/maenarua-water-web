import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()
df = pd.read_csv(EXP / "final_candidate_vs_log.csv", parse_dates=["recorded_as_of_date"])
df = df.dropna(subset=["pred_final_candidate","actual_m3_per_day"]).sort_values(["horizon","recorded_as_of_date"])

def nse(actual, pred):
    actual=np.asarray(actual,float); pred=np.asarray(pred,float)
    denom = np.sum((actual-actual.mean())**2)
    return 1 - np.sum((actual-pred)**2)/denom if denom else np.nan

FIT_FRAC = 0.65
rows = []
for h, g in df.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n*FIT_FRAC), 5)
    fit, hold = g.iloc[:cut], g.iloc[cut:]
    if len(hold) < 3:
        continue
    bias_fit = (fit["pred_final_candidate"] - fit["actual_m3_per_day"]).mean()

    mae_before = (hold["pred_final_candidate"] - hold["actual_m3_per_day"]).abs().mean()
    nse_before = nse(hold["actual_m3_per_day"], hold["pred_final_candidate"])

    corrected = (hold["pred_final_candidate"] - bias_fit).clip(lower=0.0)
    mae_after = (corrected - hold["actual_m3_per_day"]).abs().mean()
    nse_after = nse(hold["actual_m3_per_day"], corrected)

    rows.append(dict(horizon=h, n_fit=len(fit), n_holdout=len(hold), bias_correction=bias_fit,
                      mae_before=mae_before, mae_after=mae_after,
                      nse_before=nse_before, nse_after=nse_after,
                      improve=mae_before - mae_after))

rep = pd.DataFrame(rows)
pd.set_option("display.width", 160)
print(rep.round(1).to_string(index=False))
rep.to_csv(EXP / "bias_recalibration_on_candidate_results.csv", index=False)

total_before = rep["mae_before"].mul(rep["n_holdout"]).sum() / rep["n_holdout"].sum()
total_after = rep["mae_after"].mul(rep["n_holdout"]).sum() / rep["n_holdout"].sum()
print(f"\nWeighted holdout MAE: before={total_before:.0f}  after={total_after:.0f}  "
      f"improvement={100*(1-total_after/total_before):.1f}%")
