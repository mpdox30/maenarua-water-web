# -*- coding: utf-8 -*-
"""Same comparison as run_compare.py, but with level-spike artifacts (artifact_check.py) removed:
rows flagged as artifact are dropped from training, and flagged TARGET windows are masked from truth
(both Qend truth and the old smoothed truth). Test rows are therefore 'clean' windows only."""
import os, sys, warnings
import numpy as np, pandas as pd
from datetime import timedelta
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import run_compare as rc

df = pd.read_csv(os.path.join(HERE, "Training_v2_6h.csv"), parse_dates=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
fl = pd.read_csv(os.path.join(HERE, "artifact_flags.csv"), parse_dates=["Datetime"]).set_index("Datetime")["artifact"]
df["artifact"] = [fl.get(t, np.nan) for t in df.Datetime]
for h in range(1, 13):
    tf = np.array([fl.get(t + timedelta(hours=6 * h), np.nan) for t in df.Datetime])
    for c in (f"y{h}_end", f"y{h}=Q_in_t+{h} (m3/6h)"):
        df.loc[tf == 1.0, c] = np.nan
df = df[df.artifact != 1.0].reset_index(drop=True)   # drop flagged rows (as feature rows / persistence)
res = rc.cv_eval(df)
res.to_csv(os.path.join(HERE, "cv_results_clean.csv"), index=False)
pd.set_option("display.width", 250)
print("rows used:", len(df))
print(res[["H", "n", "n_events(>20k)", "NSE_persist_Qend", "NSE_A_vsQend", "NSE_B_vsQend", "NSE_C_vsQend", "NSE_D_vsQend", "NSE_E_vsQend"]].round(3).to_string(index=False))
print(res[["H", "NSE_A_vsOwnTruth", "NSE_D_vsOwnTruth", "NSE_persist_smoothed_vsOwn"]].round(3).to_string(index=False))
print(res[["H", "evMAE_persist", "evMAE_A", "evMAE_B", "evMAE_C", "evMAE_E"]].round(0).to_string(index=False) if "evMAE_A" in res else "")
print(res[["H", "n_onset", "onset_meanPred_persist", "onset_meanTruth", "onset_meanPred_A", "onset_meanPred_C", "onset_meanPred_E"]].round(0).to_string(index=False))
