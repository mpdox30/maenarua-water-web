"""
Final honest end-to-end comparison, on the SAME holdout rows (last 35% chronologically per horizon,
never used to fit either model's bias correction):
  - CURRENTLY DEPLOYED production formula: regularized_final candidate (+ rain-binary h3/6/7)
    + its existing bias correction (h3-h7 only, values from 2026-09-07 deploy)
  - SELECTIVE candidate: + range_24h/max_level_24h added to h2,h4,h5,h6,h7 (not h1,h3)
    + its own freshly re-fit bias correction (only applied where it demonstrably helps)
"""
import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()

# currently deployed bias correction (from 2026-09-07 deploy, data_pipeline.py)
DEPLOYED_BIAS = {3: 610.9, 4: 4241.9, 5: 2605.5, 6: 6583.5, 7: 13153.2}

# selective candidate's own bias correction (only where improve>0 from 07_selective_candidate_and_bias.py)
sel_bias_rep = pd.read_csv(EXP / "selective_bias_recalibration_results.csv")
SELECTIVE_BIAS = {int(r.horizon): r.bias_correction for r in sel_bias_rep.itertuples() if r.improve > 0}
print("Selective candidate bias correction applied to horizons:", SELECTIVE_BIAS)

sel = pd.read_csv(EXP / "selective_candidate_vs_log.csv", parse_dates=["recorded_as_of_date"])
sel = sel.dropna(subset=["pred_selective", "actual_m3_per_day"]).sort_values(["horizon", "recorded_as_of_date"])

# also need the deployed-model (no range) reconstruction on the SAME rows -- reuse final_candidate_vs_log.csv
# from the original regularized_final validation (has pred_final_candidate = deployed model, no bias yet)
REGEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_regularized_final_20260907")
dep = pd.read_csv(REGEXP / "final_candidate_vs_log.csv", parse_dates=["recorded_as_of_date"])
dep = dep[["recorded_as_of_date", "horizon", "pred_final_candidate"]]

FIT_FRAC = 0.65
rows = []
for h, g in sel.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n * FIT_FRAC), 5)
    hold = g.iloc[cut:].copy()
    if len(hold) < 3:
        continue
    hold = hold.merge(dep, on=["recorded_as_of_date", "horizon"], how="left")
    hold = hold.dropna(subset=["pred_final_candidate"])
    if hold.empty:
        continue

    # deployed production: apply its existing bias (h3-h7 only)
    dep_bias = DEPLOYED_BIAS.get(h, 0.0)
    hold["pred_deployed_final"] = (hold["pred_final_candidate"] - dep_bias).clip(lower=0.0)

    # selective candidate: apply its own freshly-fit bias (where it helps)
    sel_bias = SELECTIVE_BIAS.get(h, 0.0)
    hold["pred_selective_final"] = (hold["pred_selective"] - sel_bias).clip(lower=0.0)

    def nse(actual, pred):
        actual = np.asarray(actual, float); pred = np.asarray(pred, float)
        denom = np.sum((actual - actual.mean()) ** 2)
        return 1 - np.sum((actual - pred) ** 2) / denom if denom else np.nan

    mae_dep = (hold["pred_deployed_final"] - hold["actual_m3_per_day"]).abs().mean()
    mae_sel = (hold["pred_selective_final"] - hold["actual_m3_per_day"]).abs().mean()
    nse_dep = nse(hold["actual_m3_per_day"], hold["pred_deployed_final"])
    nse_sel = nse(hold["actual_m3_per_day"], hold["pred_selective_final"])
    imp = 100 * (1 - mae_sel / mae_dep) if mae_dep else np.nan
    rows.append(dict(horizon=h, n=len(hold), mae_deployed=mae_dep, mae_selective=mae_sel,
                      improvement_pct=imp, nse_deployed=nse_dep, nse_selective=nse_sel))

rep = pd.DataFrame(rows)
pd.set_option("display.width", 160)
print("\n=== FINAL: currently-deployed (regularized+rain+bias) vs SELECTIVE (+range h2,4,5,6,7 + re-fit bias) ===")
print(rep.round(3).to_string(index=False))
rep.to_csv(EXP / "final_end_to_end_selective_vs_deployed.csv", index=False)

w_dep = (rep.mae_deployed * rep.n).sum() / rep.n.sum()
w_sel = (rep.mae_selective * rep.n).sum() / rep.n.sum()
print(f"\nWeighted-avg MAE: deployed(now)={w_dep:.0f}  selective_candidate={w_sel:.0f}  "
      f"overall improvement={100*(1-w_sel/w_dep):.1f}%")
print(f"\nh1-h3 only: deployed={rep[rep.horizon<=3].mae_deployed.mean():.0f} avg, "
      f"selective={rep[rep.horizon<=3].mae_selective.mean():.0f} avg")
