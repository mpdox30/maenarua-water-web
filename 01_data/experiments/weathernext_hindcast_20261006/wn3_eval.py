# -*- coding: utf-8 -*-
"""
ประเมิน WeatherNext 3 (0.1deg) กับฝนเกจ RES002 และทดสอบเป็นฟีเจอร์ของโมเดล 6 ชม. (การทดลอง ไม่แตะ production)

กฎกันรั่ว (no leakage): ณ เวลาออกพยากรณ์ t (mark ตามเวลาไทย; UTC = t-7h, ออกจริง ~t+30 นาที)
ใช้ได้เฉพาะ init ที่ EE ปล่อยแล้วตามตาราง dissemination (init 6 ชม. +8h10m)
=> init ที่ใช้ = floor6h((t_utc+0.5h) - 8h10m) ซึ่งตกที่ t_utc-12h เสมอ  (forecast "แก่" 12 ชม. ตอนใช้)
ฟีเจอร์ของ window k (หน้าต่าง 6 ชม. ถัดจาก t ไปอีก k ก้าว) = ผลรวมฝน mean รายชั่วโมง lead 12+6(k-1)+1 .. 12+6k
"""
import os, sys, warnings
from datetime import timedelta
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
H = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(H, "..", "sixhourly_stormfix_20261006")
sys.path.insert(0, EXP)
import run_compare as rc
import run_foresight as rf

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--csv", default="wn3_hindcast_2026.csv")
_ap.add_argument("--offset", type=int, default=12)
_ap.add_argument("--tag", default="")
_ap.add_argument("--src", default="pt", choices=["pt", "bx", "bxmax"], help="pt=pixel เดียว, bx=เฉลี่ย 3x3, bxmax=สูงสุด 3x3")
_A = _ap.parse_args()
OFFSET = _A.offset
KMAX = 6
P = _A.src + "_total_precipitation_1hr_"
w = pd.read_csv(os.path.join(H, _A.csv), parse_dates=["init_utc"])
w["init_utc"] = w.init_utc.dt.tz_localize(None)
w = w.set_index(["init_utc", "lead_h"]).sort_index()
col = {"mean": P + "mean_mm", "p90": P + "p90_mm", "imerg": _A.src + "_imerg_tp_1hr_mean_mm"}
inits = set(w.index.get_level_values(0))

df = pd.read_csv(os.path.join(EXP, "Training_v2_6h.csv"), parse_dates=["Datetime"]).sort_values("Datetime").reset_index(drop=True)
df = df[df.Datetime >= "2026-01-02"].reset_index(drop=True)

def feats_row(t):
    tu = t - timedelta(hours=7)
    I = tu - timedelta(hours=OFFSET)
    if I not in inits:
        return {}
    d = w.loc[I]
    out = {}
    for k in range(1, KMAX + 1):
        lo, hi = OFFSET + 6 * (k - 1) + 1, OFFSET + 6 * k
        sub = d.loc[(d.index >= lo) & (d.index <= hi)]
        # แปลง lead (นับจาก init) -> ชั่วโมง; ต้องครบ 6 ชั่วโมงมิฉะนั้น NaN
        if len(sub) < 6:
            continue
        out[f"wn_mean_{k}"] = sub[col["mean"]].sum()
        out[f"wn_p90max_{k}"] = sub[col["p90"]].max()
        out[f"wn_imerg_{k}"] = sub[col["imerg"]].sum()
    return out

F = pd.DataFrame([feats_row(t) for t in df.Datetime])
df = pd.concat([df, F], axis=1)
# gauge rain in each future window (observed, for evaluation only)
idx = df.set_index("Datetime")["rain_6h_end"]
for k in range(1, KMAX + 1):
    df[f"gauge_{k}"] = [idx.get(t + timedelta(hours=6 * k), np.nan) for t in df.Datetime]

# ---------- 1) WN3 vs gauge ----------
print("rows:", len(df), "| มี WN feature:", int(df.wn_mean_1.notna().sum()))
rows = []
for k in range(1, KMAX + 1):
    d = df[[f"wn_mean_{k}", f"wn_p90max_{k}", f"gauge_{k}"]].dropna()
    g = d[f"gauge_{k}"]; m = d[f"wn_mean_{k}"]; p = d[f"wn_p90max_{k}"]
    ev = g >= 20
    rows.append(dict(window=k, lead_start_h=OFFSET + 6 * (k - 1), n=len(d),
        corr_mean=np.corrcoef(g, m)[0, 1], rank_corr=g.corr(m, method="spearman"),
        gauge_mean=g.mean(), wn_mean=m.mean(), bias_ratio=m.sum() / max(g.sum(), 1e-9),
        n_events20=int(ev.sum()), wn_mean_on_events=m[ev].mean() if ev.any() else np.nan,
        gauge_mean_on_events=g[ev].mean() if ev.any() else np.nan,
        hit_mean_ge5=(m[ev] >= 5).mean() if ev.any() else np.nan,
        hit_p90_ge10=(p[ev] >= 10).mean() if ev.any() else np.nan,
        false_alarm_p90_ge10=(p[~ev] >= 10).mean()))
cmp_ = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(cmp_.round(2).to_string(index=False))
cmp_.to_csv(os.path.join(H, f"wn3_vs_gauge{_A.tag}.csv"), index=False)

# ---------- 2) เป็นฟีเจอร์ของโมเดล ----------
def clean(d):
    fl = pd.read_csv(os.path.join(EXP, "artifact_flags.csv"), parse_dates=["Datetime"]).set_index("Datetime")["artifact"]
    d = d.copy(); d["artifact"] = [fl.get(t, np.nan) for t in d.Datetime]
    for h in range(1, 13):
        tf = np.array([fl.get(t + timedelta(hours=6 * h), np.nan) for t in d.Datetime])
        d.loc[tf == 1.0, f"y{h}_end"] = np.nan
    return d[d.artifact != 1.0].reset_index(drop=True)

df = clean(df)
base = rc.UNION
n = len(df); edges = [int(n * x) for x in (0.4, 0.55, 0.7, 0.85, 1.0)]
res = []
for h in range(1, KMAX + 1):
    ycol = f"y{h}_end"
    df[f"wn_tgt"] = df[f"wn_mean_{h}"]
    df["wn_cum"] = df[[f"wn_mean_{k}" for k in range(1, h + 1)]].sum(axis=1, min_count=h)
    df["wn_p90_tgt"] = df[f"wn_p90max_{h}"]
    df["rain_tgt"] = df[f"gauge_{h}"]
    df["rain_cum"] = df[[f"gauge_{k}" for k in range(1, h + 1)]].sum(axis=1, min_count=h)
    sets = {"none": base, "wn3": base + ["wn_tgt", "wn_cum", "wn_p90_tgt"], "oracle": base + ["rain_tgt", "rain_cum"]}
    need = sum(sets.values(), []) + [ycol, "Qend"]
    preds = {k: [] for k in sets}
    for b in range(4):
        tr, te = df.iloc[: edges[b]], df.iloc[edges[b]: edges[b + 1]]
        trn = tr.dropna(subset=list(set(need))); ten = te.dropna(subset=list(set(need) - {ycol}))
        if len(trn) < 50 or ten.empty: continue
        for nm, fs in sets.items():
            p = rc.fit_predict(trn[fs], trn[ycol].to_numpy(), trn["Qend"].to_numpy(), ten[fs], ten["Qend"].to_numpy())
            preds[nm].append(pd.Series(p, index=ten.index))
    P_ = {k: pd.concat(v) for k, v in preds.items() if v}
    truth = df[ycol]; common = truth.dropna().index
    for k in P_: common = common.intersection(P_[k].index)
    ev = common[truth.loc[common] > 20000]
    r = {"H": h, "n": len(common), "n_ev": len(ev), "NSE_persist": rc.nse(truth.loc[common], df.loc[common, "Qend"])}
    for k in P_:
        r[f"NSE_{k}"] = rc.nse(truth.loc[common], P_[k].loc[common])
        r[f"MAE_{k}"] = float(np.mean(np.abs(truth.loc[common] - P_[k].loc[common])))
        r[f"evRecall_{k}"] = float((P_[k].loc[ev] > 20000).mean()) if len(ev) else np.nan
    res.append(r)
R = pd.DataFrame(res)
print(R.round(3).to_string(index=False))
R.to_csv(os.path.join(H, f"wn3_cv_results{_A.tag}.csv"), index=False)
