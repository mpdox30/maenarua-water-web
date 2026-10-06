# -*- coding: utf-8 -*-
"""
How much would FUTURE-RAIN knowledge help the 6h model, and how good must the forecast be?
(motivation: 2026-10-06 -- user got access to Google WeatherNext; plan = bias-correct it and feed it in)

Oracle features per horizon h (using observed rain as a stand-in for a perfect forecast):
  rain_tgt = rain in the target window (t+6(h-1), t+6h]      rain_cum = rain in (t, t+6h]
Forecast-quality simulation applied to the TEST rows only (train on oracle unless noted):
  level 'oracle'  : exact observed rain
  level 'good'    : lognormal multiplicative error sigma=0.4, 10% of rain windows missed (set 0)
  level 'poor'    : sigma=0.8, 30% missed, 15% false alarms (calm window -> 5 mm)
Same blocked expanding-window CV as run_compare.py; base model = variant E (UNION feats, Qend target).
"""
import os, sys, warnings
import numpy as np, pandas as pd, lightgbm as lgb
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import run_compare as rc

rng = np.random.default_rng(7)
df = pd.read_csv(os.path.join(HERE, "Training_v2_6h.csv"), parse_dates=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
idx = df.set_index("Datetime")["rain_6h_end"]
from datetime import timedelta
for k in range(1, 13):
    df[f"rain6_f{k}"] = [idx.get(t + timedelta(hours=6 * k), np.nan) for t in df.Datetime]


def corrupt(x, level):
    x = np.asarray(x, float).copy()
    if level == "oracle":
        return x
    sig, miss, fa = {"good": (0.4, 0.10, 0.0), "poor": (0.8, 0.30, 0.15)}[level]
    wet = x > 0.5
    x[wet] = x[wet] * rng.lognormal(0, sig, wet.sum())
    x[wet & (rng.random(len(x)) < miss)] = 0.0
    calm = ~wet
    x[calm & (rng.random(len(x)) < fa)] = 5.0
    return x


def feats_for(df_, h, level="oracle"):
    out = df_.copy()
    tgt = out[f"rain6_f{h}"].to_numpy()
    cum = out[[f"rain6_f{k}" for k in range(1, h + 1)]].sum(axis=1, min_count=h).to_numpy()
    out["rain_tgt"] = corrupt(np.nan_to_num(tgt, nan=np.nan), level) if level != "oracle" else tgt
    out["rain_cum"] = corrupt(np.nan_to_num(cum, nan=np.nan), level) if level != "oracle" else cum
    out.loc[np.isnan(tgt), "rain_tgt"] = np.nan
    out.loc[np.isnan(cum), "rain_cum"] = np.nan
    return out


def run(df, levels=("none", "oracle", "good", "poor")):
    n = len(df); edges = [int(n * x) for x in (0.4, 0.55, 0.7, 0.85, 1.0)]
    base = rc.UNION; rows = []
    for h in range(1, 13):
        ycol = f"y{h}_end"
        preds = {lv: [] for lv in levels}
        for k in range(4):
            tr_raw, te_raw = df.iloc[: edges[k]], df.iloc[edges[k]: edges[k + 1]]
            tr = feats_for(tr_raw, h, "oracle")
            for lv in levels:
                feats = base if lv == "none" else base + ["rain_tgt", "rain_cum"]
                te = feats_for(te_raw, h, "oracle" if lv == "none" else lv)
                trn = tr.dropna(subset=feats + [ycol, "Qend"]); ten = te.dropna(subset=feats + ["Qend"])
                if len(trn) < 50 or ten.empty: continue
                p = rc.fit_predict(trn[feats], trn[ycol].to_numpy(), trn["Qend"].to_numpy(), ten[feats], ten["Qend"].to_numpy())
                preds[lv].append(pd.Series(p, index=ten.index))
        P = {lv: pd.concat(s) for lv, s in preds.items() if s}
        truth = df[ycol]; common = truth.dropna().index
        for lv in P: common = common.intersection(P[lv].index)
        on = common[(df.loc[common, "Qend"] < 10000) & (truth.loc[common] > 50000)]
        ev = common[truth.loc[common] > 20000]
        r = {"H": h, "n": len(common), "n_onset": len(on), "NSE_persist": rc.nse(truth.loc[common], df.loc[common, "Qend"])}
        for lv in P:
            r[f"NSE_{lv}"] = rc.nse(truth.loc[common], P[lv].loc[common])
            r[f"MAE_{lv}"] = float(np.mean(np.abs(truth.loc[common] - P[lv].loc[common])))
            if len(on):
                r[f"onsetMean_{lv}"] = float(P[lv].loc[on].mean()); r[f"onsetRecall_{lv}"] = float((P[lv].loc[on] > 20000).mean())
            r[f"evRecall_{lv}"] = float((P[lv].loc[ev] > 20000).mean())
        r["onsetTruthMean"] = float(truth.loc[on].mean()) if len(on) else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def clean(df):
    fl = pd.read_csv(os.path.join(HERE, "artifact_flags.csv"), parse_dates=["Datetime"]).set_index("Datetime")["artifact"]
    d = df.copy(); d["artifact"] = [fl.get(t, np.nan) for t in d.Datetime]
    for h in range(1, 13):
        tf = np.array([fl.get(t + timedelta(hours=6 * h), np.nan) for t in d.Datetime])
        d.loc[tf == 1.0, f"y{h}_end"] = np.nan
    return d[d.artifact != 1.0].reset_index(drop=True)


if __name__ == "__main__":
    CLEAN = "--clean" in sys.argv
    res = run(clean(df) if CLEAN else df)
    res.to_csv(os.path.join(HERE, "foresight_results_clean.csv" if CLEAN else "foresight_results.csv"), index=False)
    pd.set_option("display.width", 250)
    print(res[["H", "n", "NSE_persist", "NSE_none", "NSE_oracle", "NSE_good", "NSE_poor"]].round(3).to_string(index=False))
    print(res[["H", "MAE_none", "MAE_oracle", "MAE_good", "MAE_poor"]].round(0).to_string(index=False))
    print(res[["H", "n_onset", "onsetTruthMean", "onsetMean_none", "onsetMean_oracle", "onsetMean_good", "onsetMean_poor"]].round(0).to_string(index=False))
    print(res[["H", "evRecall_none", "evRecall_oracle", "evRecall_good", "evRecall_poor", "onsetRecall_none", "onsetRecall_oracle", "onsetRecall_good", "onsetRecall_poor"]].round(2).to_string(index=False))
