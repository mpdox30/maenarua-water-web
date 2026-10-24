# -*- coding: utf-8 -*-
"""
score_active.py -- ติดตามความคืบหน้าการทดสอบ shadow 6 ชม. ก่อนตัดสินใจขึ้น production (เพิ่ม 2026-10-24)

ทำไมต้องมี: NSE รวมของ score_shadow.py ถูกดันด้วยความต่างระหว่างช่วงน้ำมาก/แห้ง (ช่วง 8-13 ต.ค. เหตุการณ์เดียว)
สคริปต์นี้จึงแยกให้ดู 3 อย่าง
  1) คะแนนเฉพาะช่วง "มีน้ำเข้าจริง" (ค่าจริง > ACTIVE_TH ม3/6ชม.) เทียบ persistence
  2) จำนวนเหตุการณ์น้ำเข้าที่ "เห็นช่วงเริ่มเพิ่ม (rising limb)" ภายในช่วงที่ log ครอบคลุม
  3) เช็กลิสต์เกณฑ์ตัดสินใจ (ผ่าน/ยังไม่ผ่าน)

ใช้:  python score_active.py            (ไม่แก้ shadow_predictions_log.csv ; เขียน shadow_active_report.csv + shadow_active_progress.txt)
ต้องรันในโฟลเดอร์นี้ (import shadow_predict แบบเดียวกับ score_shadow.py -> ดาวน์โหลด gdrive_log ใหม่ถ้าออนไลน์)

หมายเหตุการตีความ: การเลือก subset จากค่าจริง (obs > TH) ทำให้ NSE ต่ำกว่าปกติสำหรับทุกโมเดล
ใช้เทียบกับ persistence (subset เดียวกัน) ได้ แต่ไม่ใช่ความแม่นสัมบูรณ์
"""
import os
from datetime import datetime

import numpy as np
import pandas as pd

import shadow_predict as sp

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "shadow_predictions_log.csv")
OUT_CSV = os.path.join(HERE, "shadow_active_report.csv")
OUT_TXT = os.path.join(HERE, "shadow_active_progress.txt")

ACTIVE_TH = 10000          # ม3/6ชม. -- ถือว่า "มีน้ำเข้า"
EVENT_PEAK_TH = 30000      # ยอดของเหตุการณ์ต้องไม่ต่ำกว่านี้ จึงนับเป็นเหตุการณ์
DRY_LOOKBACK = 4           # ต้องแห้ง (<= ACTIVE_TH) ต่อเนื่อง 4 mark (24 ชม.) ก่อนเริ่ม จึงนับว่าเห็น rising limb
# เกณฑ์ตัดสินใจ (ข้อเสนอ 2026-10-24)
NEED_EVENTS = 3
NEED_ACTIVE_N = 30
NEED_N_ALL = 60


def nse(o, p):
    o, p = np.asarray(o, float), np.asarray(p, float)
    d = ((o - o.mean()) ** 2).sum()
    return float("nan") if (len(o) < 3 or d < 1e-9) else float(1 - ((o - p) ** 2).sum() / d)


def mae(o, p):
    return float(np.mean(np.abs(np.asarray(o, float) - np.asarray(p, float)))) if len(o) else float("nan")


def find_events(series):
    """series: Q_in รายmark (index = เวลา) -> รายการเหตุการณ์ (run ของ mark > ACTIVE_TH ที่เว้นช่องว่างได้ <=2 mark)"""
    s = series.sort_index()
    act = (s > ACTIVE_TH).values
    idx = s.index
    runs, i, n = [], 0, len(s)
    while i < n:
        if not act[i]:
            i += 1
            continue
        j, gap = i, 0
        k = i + 1
        while k < n and gap <= 2:
            if act[k]:
                j, gap = k, 0
            else:
                gap += 1
            k += 1
        runs.append((i, j))
        i = j + 1
    ev = []
    for a, b in runs:
        seg = s.iloc[a:b + 1]
        before = s.iloc[max(0, a - DRY_LOOKBACK):a]
        rising = (a >= DRY_LOOKBACK) and bool((before <= ACTIVE_TH).all())
        ev.append({"start": idx[a], "end": idx[b], "peak": float(seg.max()), "peak_at": seg.idxmax(),
                   "rising_limb_seen": rising, "counted": rising and float(seg.max()) >= EVENT_PEAK_TH})
    return ev


def main():
    if not os.path.exists(LOG_PATH):
        print("ยังไม่มี shadow_predictions_log.csv")
        return
    log = pd.read_csv(LOG_PATH, parse_dates=["issued_at"])
    rows = sp.build_6hourly_rows()
    act = pd.Series({r["Datetime"]: r["Q_in_t (m3/6h)"] for r in rows}).sort_index()
    act.index = pd.to_datetime(act.index)

    out = []
    for h in range(1, 13):
        rec = []
        for _, r in log.iterrows():
            o = act.get(pd.Timestamp(r[f"h{h}_target_datetime"]))
            if o is None or pd.isna(o):
                continue
            rec.append((o, r[f"h{h}_pred_qin"], r["persistence_qin_now"]))
        d = pd.DataFrame(rec, columns=["o", "p", "q"])
        a = d[d.o > ACTIVE_TH]
        dry = d[d.o <= ACTIVE_TH]
        out.append({
            "H": h, "lead_hours": 6 * h, "n_all": len(d),
            "nse_model_all": round(nse(d.o, d.p), 3), "nse_persist_all": round(nse(d.o, d.q), 3),
            "n_active": len(a),
            "nse_model_active": round(nse(a.o, a.p), 3), "nse_persist_active": round(nse(a.o, a.q), 3),
            "mae_model_active": round(mae(a.o, a.p), 0), "mae_persist_active": round(mae(a.o, a.q), 0),
            "n_dry": len(dry), "mae_model_dry": round(mae(dry.o, dry.p), 0), "mae_persist_dry": round(mae(dry.o, dry.q), 0),
        })
    rep = pd.DataFrame(out)
    rep.to_csv(OUT_CSV, index=False)

    # เหตุการณ์ในช่วงที่ log ครอบคลุม (นับจาก issued แรก)
    t0 = log.issued_at.min()
    win = act[act.index >= t0 - pd.Timedelta(hours=6 * DRY_LOOKBACK)]
    ev = [e for e in find_events(win) if e["end"] >= t0]
    n_counted = sum(1 for e in ev if e["counted"])

    lines = []
    P = lines.append
    P(f"shadow 6h -- ความคืบหน้า ณ {datetime.now():%Y-%m-%d %H:%M}")
    P(f"log: {len(log)} แถว  issued {log.issued_at.min():%Y-%m-%d %H:%M} -> {log.issued_at.max():%Y-%m-%d %H:%M}")
    P("")
    P("เหตุการณ์น้ำเข้าในช่วงทดสอบ (ACTIVE>%d, ยอด>=%d ม3/6ชม.):" % (ACTIVE_TH, EVENT_PEAK_TH))
    if not ev:
        P("  (ยังไม่มี)")
    for e in ev:
        tag = "นับได้ (เห็นช่วงเริ่มเพิ่ม)" if e["counted"] else ("ไม่นับ: เริ่มก่อนช่วงทดสอบ/ไม่เห็นช่วงเริ่มเพิ่ม" if not e["rising_limb_seen"] else "ไม่นับ: ยอดต่ำกว่าเกณฑ์")
        P(f"  {e['start']:%m-%d %H:%M} -> {e['end']:%m-%d %H:%M}  ยอด {e['peak']:,.0f} @ {e['peak_at']:%m-%d %H:%M}  [{tag}]")
    P("")
    P("เช็กลิสต์เกณฑ์ตัดสินใจ:")
    n_all_min = int(rep.n_all.min())
    n_act_min = int(rep.n_active.min())
    ok1, ok2, ok3 = n_counted >= NEED_EVENTS, n_act_min >= NEED_ACTIVE_N, n_all_min >= NEED_N_ALL
    P(f"  [{'x' if ok1 else ' '}] เหตุการณ์ที่เห็นช่วงเริ่มเพิ่ม >= {NEED_EVENTS}   (ตอนนี้ {n_counted})")
    P(f"  [{'x' if ok2 else ' '}] mark ช่วงมีน้ำเข้าต่อ horizon >= {NEED_ACTIVE_N}   (ต่ำสุดตอนนี้ {n_act_min}; H1={int(rep.n_active.iloc[0])})")
    P(f"  [{'x' if ok3 else ' '}] n รวมต่อ horizon >= {NEED_N_ALL}   (ต่ำสุดตอนนี้ {n_all_min})")
    P("  สถานะ: " + ("พร้อมพิจารณา" if (ok1 and ok2 and ok3) else "ยังไม่พร้อม -- สะสมต่อ"))
    P("")
    P("คะแนนช่วงมีน้ำเข้า (โมเดล vs persistence, NSE):")
    P(rep[["H", "lead_hours", "n_active", "nse_model_active", "nse_persist_active", "mae_model_active", "mae_persist_active"]].to_string(index=False))
    P("")
    P("คะแนนรวม (เทียบ score_shadow.py):")
    P(rep[["H", "n_all", "nse_model_all", "nse_persist_all"]].to_string(index=False))
    txt = "\n".join(lines)
    print(txt)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(f"\nบันทึก {OUT_CSV}\nบันทึก {OUT_TXT}")


if __name__ == "__main__":
    main()
