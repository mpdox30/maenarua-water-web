# -*- coding: utf-8 -*-
"""
Replay the 2026-10-05 storm: what would each system have said, mark by mark?
 - V1  = the FROZEN production-shadow models (shadow_models/), run through shadow_predict's own code
         on an hourly series extended past the store end (levels from inflow_6h_display.json, rain=0 after 16:00,
         both verified: display levels == store levels on 59 overlapping hours)
 - P2  = persistence of the end-of-window Qend (v2 definition, no ML)
 - C/E = v2 LightGBM variants trained on CLEAN rows through 2026-09-18 07:00 (same cut as the frozen models)
Truth printed both ways: Qend (physical window inflow) and v1-smoothed Q_in.
"""
import os, sys, warnings
from datetime import datetime, timedelta
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hourly_series as hs, build_v2_dataset as b2, run_compare as rc
sp = hs.sp

# ---- 1. augmented store for the frozen v1 pipeline -------------------------------------------------
hl, hr, ext = hs.load_hourly(extend_from_display_json=True)
store = pd.read_csv(os.path.join(hs.SRC, "shadow_gdrive_raw_store.csv"))
add = []
for t in sorted(ext):
    add.append(("RES002", t.strftime("%Y-%m-%d %H:%M:%S"), "water_level", hl[t]))
    add.append(("RES002", t.strftime("%Y-%m-%d %H:%M:%S"), "rainfall_1h", 0.0))
aug = pd.concat([store, pd.DataFrame(add, columns=["station", "dt", "dtype", "value"])], ignore_index=True)
sp.fetch_and_update_gdrive_store = lambda: aug
rows_v1 = sp.add_segment_lag_feats(sp.build_6hourly_rows())
v1 = pd.DataFrame(rows_v1).set_index("Datetime")
models = sp.load_all_frozen_models()

# ---- 2. v2 features on the same extended hourly series ---------------------------------------------
v2 = b2.compute_mark_rows(hl, hr).set_index("Datetime")

# ---- 3. v2 models trained on clean rows through the frozen-model cut ------------------------------
tr = pd.read_csv(os.path.join(HERE, "Training_v2_6h.csv"), parse_dates=["Datetime"]).sort_values("Datetime")
fl = pd.read_csv(os.path.join(HERE, "artifact_flags.csv"), parse_dates=["Datetime"]).set_index("Datetime")["artifact"]
tr["artifact"] = [fl.get(t, np.nan) for t in tr.Datetime]
tr = tr[(tr.artifact != 1.0) & (tr.Datetime <= datetime(2026, 9, 18, 7, 0))]
def train(var, h):
    cfg = rc.VARIANTS[var]; cols = cfg["feats"] + [cfg["ycol"](h), cfg["base"]]
    d = tr.dropna(subset=cols)
    import lightgbm as lgb
    return lgb.LGBMRegressor(**rc.PARAMS).fit(d[cfg["feats"]], d[cfg["ycol"](h)] - d[cfg["base"]])
M = {(v, h): train(v, h) for v in ("C", "E") for h in range(1, 13)}

# ---- 4. replay ---------------------------------------------------------------------------------------
marks = [datetime(2026, 10, 5, 7), datetime(2026, 10, 5, 13), datetime(2026, 10, 5, 19), datetime(2026, 10, 6, 1), datetime(2026, 10, 6, 7)]
smooth_truth = v1["Q_in_t (m3/6h)"]; end_truth = v2["Qend"]
print("== observed series (m3/6h) ==")
print(pd.DataFrame({"smoothed_Qin(v1)": smooth_truth, "Qend(v2)": end_truth, "rain6h": v2["rain_6h_end"], "L_end": v2["L_end"]}).loc[datetime(2026, 10, 4, 19):].round(1).to_string())
out = []
for t in marks:
    r1 = v1.loc[t]; r2 = v2.loc[t]
    comb = pd.concat([r1, r2[[c for c in v2.columns if c not in r1.index]]])
    for h in range(1, 7):
        tgt = t + timedelta(hours=6 * h)
        if tgt not in end_truth.index: continue
        rec = {"issued": t.strftime("%d %H:%M"), "H": h, "target_end": tgt.strftime("%d %H:%M"),
               "truth_Qend": end_truth[tgt], "truth_smoothed": smooth_truth.get(tgt, np.nan)}
        X1 = pd.DataFrame([{c: r1[c] for c in sp.FEATS}])
        _, rec["V1_frozen"] = sp.predict_for_horizon(models, h, X1, r1["Q_in_t (m3/6h)"])
        rec["P2_persist_Qend"] = r2["Qend"]
        for v in ("C", "E"):
            cfg = rc.VARIANTS[v]
            X = pd.DataFrame([{c: comb[c] for c in cfg["feats"]}])
            rec[f"{v}_lgbm"] = float(max(0.0, comb[cfg["base"]] + M[(v, h)].predict(X)[0]))
        out.append(rec)
res = pd.DataFrame(out)
pd.set_option("display.width", 250)
print("\n== replay (m3/6h) ==")
print(res.round(0).to_string(index=False))
res.to_csv(os.path.join(HERE, "storm_replay.csv"), index=False)
