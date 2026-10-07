import joblib, json, pandas as pd, numpy as np
from pathlib import Path

ACTIVE = Path("/sessions/busy-awesome-cerf/mnt/maenaruea-water-web/01_data/scripts and code/Reservoir_inflow/active")

FEATS = ['Q_in_t (m3/day)', 'Water_Level_t (m)', 'Storage_S_t (m3)', 'DeltaS_t (m3/day)',
         '%Full_t', 'Rain_obs_t (mm)', 'API_t (mm)', 'Qin_lag1 (m3/day)', 'Qin_lag2 (m3/day)',
         'Rain_roll3 (mm)', 'Rain_roll5 (mm)', 'Rain_roll7 (mm)']

df = pd.read_csv(ACTIVE / "Training_Values_Nofct_7day_Extended_lagfeat.csv", parse_dates=["Date"])
regressors = joblib.load(ACTIVE / "deployment_regressors_no_stage1.pkl")

def nse(actual, pred):
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    denom = np.sum((actual - actual.mean())**2)
    if denom == 0:
        return np.nan
    return 1 - np.sum((actual - pred)**2) / denom

print(f"{'h':>2} {'n':>4} {'mean_delta':>12} {'max_delta':>12} {'mean|delta|':>12} {'MAE':>12} {'Bias':>12} {'NSE_in':>8}")
results = {}
for h in range(1, 8):
    m = regressors[h]
    sub = df.dropna(subset=FEATS + [f"y{h}=Q_in_t+{h} (m3/day)"]).copy()
    X = sub[FEATS].values
    delta = m.predict(X)
    current_qin = sub["Q_in_t (m3/day)"].values
    pred = np.maximum(current_qin + delta, 0.0)
    actual = sub[f"y{h}=Q_in_t+{h} (m3/day)"].values
    mae = np.mean(np.abs(pred - actual))
    bias = np.mean(pred - actual)
    n = nse(actual, pred)
    results[h] = dict(n=len(sub), mean_delta=delta.mean(), max_delta=delta.max(), mean_abs_delta=np.abs(delta).mean(),
                       mae=mae, bias=bias, nse=n)
    print(f"{h:>2} {len(sub):>4} {delta.mean():>12.1f} {delta.max():>12.1f} {np.abs(delta).mean():>12.1f} {mae:>12.1f} {bias:>12.1f} {n:>8.3f}")

# Save
import pickle
with open("insample_results.json", "w") as f:
    json.dump({str(k): {kk: float(vv) for kk, vv in v.items()} for k, v in results.items()}, f, indent=2)
