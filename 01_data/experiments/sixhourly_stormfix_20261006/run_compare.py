# -*- coding: utf-8 -*-
"""
Compare 6h-model variants on the SAME rows (no production/shadow files are touched):
  A = old features + old (smoothed) target          -> what the frozen shadow models learn
  B = old features + end-of-window target (Qend)    -> ablation: target definition only
  C = NEW issue-time features + Qend target         -> proposed
  P = persistence of Qend_t (and of smoothed Q_in_t for A's own truth)
Evaluation 1: blocked expanding-window CV (train on first 40% of time, test on remaining 4 blocks).
Evaluation 2: forward test -- train through 2026-09-18 07:00 (same cut as the frozen shadow models),
              test on later marks built from the local store (+ display-json tail for 5-6 Oct).
All models: LightGBM, delta-from-current baseline (same design as production shadow), clipped >= 0.
Truth for A/B/C comparison = Qend (physical inflow of the window); A is also scored on its own truth.
"""
import os, sys, warnings
import numpy as np, pandas as pd
import lightgbm as lgb
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_v2_dataset as b2

OLD = ["Q_in_t (m3/6h)", "Water_Level_t (m)", "Storage_S_t (m3)", "DeltaS_t (m3/6h)", "%Full_t",
       "Rain_obs_t (mm)", "API_t (mm)", "Qin_lag1 (m3/6h)", "Qin_lag2 (m3/6h)",
       "Rain_lag1 (mm)", "Rain_lag2 (mm)", "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)"]
NEW = ["Qend", "Qend_lag1", "Qend_lag2", "L_end", "S_end", "pctfull_end", "dL_1h", "dL_3h", "dL_6h",
       "head_end", "rain_h1", "rain_h2", "rain_h3", "rain_max1h", "rain_6h_end", "rain6_lag1", "rain6_lag2",
       "API_t (mm)", "Rain_roll3 (mm)", "Rain_roll5 (mm)", "Rain_roll7 (mm)"]
PARAMS = dict(n_estimators=250, learning_rate=0.04, num_leaves=12, min_child_samples=12, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=2.0, random_state=42, verbose=-1)
H = range(1, 13)


def nse(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / d) if d > 1e-9 else float("nan")


def fit_predict(Xtr, ytr, base_tr, Xte, base_te):
    m = lgb.LGBMRegressor(**PARAMS).fit(Xtr, ytr - base_tr)
    return np.clip(base_te + m.predict(Xte), 0, None)


UNION = OLD + [c for c in NEW if c not in OLD]
VARIANTS = {
    "A": dict(feats=OLD, ycol=lambda h: f"y{h}=Q_in_t+{h} (m3/6h)", base="Q_in_t (m3/6h)"),
    "B": dict(feats=OLD, ycol=lambda h: f"y{h}_end", base="Qend"),
    "C": dict(feats=NEW, ycol=lambda h: f"y{h}_end", base="Qend"),
    "D": dict(feats=UNION, ycol=lambda h: f"y{h}=Q_in_t+{h} (m3/6h)", base="Q_in_t (m3/6h)"),
    "E": dict(feats=UNION, ycol=lambda h: f"y{h}_end", base="Qend"),
}


def run_split(df_tr, df_te, h):
    """returns dict variant -> preds aligned to df_te rows that have all needed values (index of df_te)"""
    out = {}
    for v, cfg in VARIANTS.items():
        cols = cfg["feats"] + [cfg["ycol"](h), cfg["base"]]
        tr = df_tr.dropna(subset=cols)
        te = df_te.dropna(subset=cfg["feats"] + [cfg["base"]])
        if len(tr) < 50 or te.empty:
            continue
        p = fit_predict(tr[cfg["feats"]], tr[cfg["ycol"](h)].to_numpy(), tr[cfg["base"]].to_numpy(),
                        te[cfg["feats"]], te[cfg["base"]].to_numpy())
        out[v] = pd.Series(p, index=te.index)
    return out


def cv_eval(df):
    n = len(df); edges = [int(n * x) for x in (0.4, 0.55, 0.7, 0.85, 1.0)]
    rows = []
    for h in H:
        preds = {v: [] for v in VARIANTS}
        for k in range(4):
            tr, te = df.iloc[: edges[k]], df.iloc[edges[k]: edges[k + 1]]
            for v, s in run_split(tr, te, h).items():
                preds[v].append(s)
        P = {v: pd.concat(s) for v, s in preds.items() if s}
        truth_end = df[f"y{h}_end"]; truth_old = df[f"y{h}=Q_in_t+{h} (m3/6h)"]
        common = truth_end.dropna().index
        for v in P: common = common.intersection(P[v].index)
        common = common.intersection(truth_old.dropna().index)
        ev = common[truth_end.loc[common] > 20000]
        r = {"H": h, "n": len(common), "n_events(>20k)": len(ev)}
        pers_end = df.loc[common, "Qend"]
        r["NSE_persist_Qend"] = nse(truth_end.loc[common], pers_end)
        for v in P:
            r[f"NSE_{v}_vsQend"] = nse(truth_end.loc[common], P[v].loc[common])
            r[f"MAE_{v}_vsQend"] = float(np.mean(np.abs(truth_end.loc[common] - P[v].loc[common])))
            if len(ev):
                r[f"evMAE_{v}"] = float(np.mean(np.abs(truth_end.loc[ev] - P[v].loc[ev])))
                r[f"evRecall_{v}"] = float(np.mean(P[v].loc[ev] > 20000))
        if len(ev):
            r["evMAE_persist"] = float(np.mean(np.abs(truth_end.loc[ev] - pers_end.loc[ev])))
            r["evRecall_persist"] = float(np.mean(pers_end.loc[ev] > 20000))
        r["NSE_A_vsOwnTruth"] = nse(truth_old.loc[common], P["A"].loc[common]) if "A" in P else np.nan
        r["NSE_persist_smoothed_vsOwn"] = nse(truth_old.loc[common], df.loc[common, "Q_in_t (m3/6h)"])
        # surge-onset rows: calm now (Qend_t<10k) but window t+h is a flood (>50k) -- the storm scenario
        on = common[(df.loc[common, "Qend"] < 10000) & (truth_end.loc[common] > 50000)]
        r["n_onset"] = len(on)
        if len(on):
            r["onset_meanPred_persist"] = float(df.loc[on, "Qend"].mean())
            r["onset_meanTruth"] = float(truth_end.loc[on].mean())
            for v in P:
                r[f"onset_meanPred_{v}"] = float(P[v].loc[on].mean())
                r[f"onset_recall20k_{v}"] = float((P[v].loc[on] > 20000).mean())
        for v in ("D",):
            if v in P:
                r["NSE_D_vsOwnTruth"] = nse(truth_old.loc[common], P["D"].loc[common])
        rows.append(r)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(HERE, "Training_v2_6h.csv"), parse_dates=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
    res = cv_eval(df)
    res.to_csv(os.path.join(HERE, "cv_results.csv"), index=False)
    pd.set_option("display.width", 250)
    cols = ["H", "n", "n_events(>20k)", "NSE_persist_Qend", "NSE_A_vsQend", "NSE_B_vsQend", "NSE_C_vsQend", "NSE_D_vsQend", "NSE_E_vsQend"]
    print(res[cols].round(3).to_string(index=False))
    print(res[["H", "NSE_A_vsOwnTruth", "NSE_D_vsOwnTruth", "NSE_persist_smoothed_vsOwn"]].round(3).to_string(index=False))
    oc = [c for c in res.columns if c.startswith("onset") or c == "n_onset" or c == "H"]
    print(res[oc].round(2).to_string(index=False))

