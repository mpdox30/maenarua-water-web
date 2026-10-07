"""
Build SELECTIVE candidate: signed-log(delta) transform only for h4,h5,h6,h7 (clear real-log gains:
+12% to +27%). h1,h2,h3 stay on the currently-deployed (no-transform) model -- h1,h2 were worse with
the transform on real log despite a promising CV signal (yet another CV-vs-real-log divergence this
session), h3 was only marginally different (+1.7%, within noise).

Then re-fit bias correction on the selective candidate (65/35 split, same as before), and produce
the final end-to-end comparison against currently-deployed production (with its existing bias).
"""
import json, joblib
import pandas as pd, numpy as np
from pathlib import Path

EXP = Path.cwd()
REGEXP = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/experiments/inflow_regularized_final_20260907")

LOGTRANSFORM_HORIZONS = {4, 5, 6, 7}
DEPLOYED_BIAS = {3: 610.9, 4: 4241.9, 5: 2605.5, 6: 6583.5, 7: 13153.2}

merged = pd.read_csv(EXP / "logtransform_vs_deployed_full_log.csv", parse_dates=["recorded_as_of_date"])
merged["pred_selective"] = np.where(merged["horizon"].isin(LOGTRANSFORM_HORIZONS),
                                     merged["pred_logtransform"], merged["pred_deployed"])

def nse(a, p):
    a = np.asarray(a, float); p = np.asarray(p, float)
    d = np.sum((a - a.mean()) ** 2)
    return 1 - np.sum((a - p) ** 2) / d if d else np.nan

df = merged.dropna(subset=["pred_selective", "actual_m3_per_day"]).sort_values(["horizon", "recorded_as_of_date"])
FIT_FRAC = 0.65
bias_rows = []
for h, g in df.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n * FIT_FRAC), 5)
    fit, hold = g.iloc[:cut], g.iloc[cut:]
    if len(hold) < 3:
        continue
    bias_fit = (fit["pred_selective"] - fit["actual_m3_per_day"]).mean()
    mae_before = (hold["pred_selective"] - hold["actual_m3_per_day"]).abs().mean()
    corrected = (hold["pred_selective"] - bias_fit).clip(lower=0.0)
    mae_after = (corrected - hold["actual_m3_per_day"]).abs().mean()
    bias_rows.append(dict(horizon=h, n_fit=len(fit), n_holdout=len(hold), bias_correction=bias_fit,
                           mae_before=mae_before, mae_after=mae_after, improve=mae_before - mae_after))
bias_rep = pd.DataFrame(bias_rows)
bias_rep.to_csv(EXP / "selective_bias_recalibration_results.csv", index=False)
print("=== bias recalibration on selective (h4-7 log-transform) candidate ===")
print(bias_rep.round(1).to_string(index=False))

SELECTIVE_BIAS = {int(r.horizon): r.bias_correction for r in bias_rep.itertuples() if r.improve > 0}
print("\nSelective candidate bias correction applied to:", SELECTIVE_BIAS)

# --- final comparison on the SAME held-out tail (last 35%), each side using its own bias policy ---
rows = []
for h, g in df.groupby("horizon"):
    g = g.sort_values("recorded_as_of_date").reset_index(drop=True)
    n = len(g)
    cut = max(int(n * FIT_FRAC), 5)
    hold = g.iloc[cut:].copy()
    if len(hold) < 3:
        continue
    dep_bias = DEPLOYED_BIAS.get(h, 0.0)
    hold["pred_deployed_final"] = (hold["pred_deployed"] - dep_bias).clip(lower=0.0)
    sel_bias = SELECTIVE_BIAS.get(h, 0.0)
    hold["pred_selective_final"] = (hold["pred_selective"] - sel_bias).clip(lower=0.0)
    mae_dep = (hold["pred_deployed_final"] - hold["actual_m3_per_day"]).abs().mean()
    mae_sel = (hold["pred_selective_final"] - hold["actual_m3_per_day"]).abs().mean()
    nse_dep = nse(hold["actual_m3_per_day"], hold["pred_deployed_final"])
    nse_sel = nse(hold["actual_m3_per_day"], hold["pred_selective_final"])
    imp = 100 * (1 - mae_sel / mae_dep) if mae_dep else np.nan
    rows.append(dict(horizon=h, n=len(hold), mae_deployed=mae_dep, mae_selective=mae_sel,
                      improvement_pct=imp, nse_deployed=nse_dep, nse_selective=nse_sel))

rep = pd.DataFrame(rows)
pd.set_option("display.width", 160)
print("\n=== FINAL: currently-deployed vs SELECTIVE (log-transform h4-7 + re-fit bias) ===")
print(rep.round(3).to_string(index=False))
rep.to_csv(EXP / "final_end_to_end_selective_vs_deployed.csv", index=False)
w_dep = (rep.mae_deployed * rep.n).sum() / rep.n.sum()
w_sel = (rep.mae_selective * rep.n).sum() / rep.n.sum()
print(f"\nWeighted MAE: deployed(now)={w_dep:.0f}  selective_candidate={w_sel:.0f}  "
      f"overall improvement={100*(1-w_sel/w_dep):.1f}%")
