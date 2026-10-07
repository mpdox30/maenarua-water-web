# -*- coding: utf-8 -*-
"""
Reconcile shadow_predictions_log.csv against reality once actuals have landed, and score
NSE/MAE per horizon vs. the naive persistence baseline that was logged at issue time.

Run any time during/after the shadow-test month -- it only scores rows whose target time
has already passed and where the rebuilt raw history has a real Q_in value for that time.
Safe to run repeatedly; does not modify the prediction log.

Usage: python3 score_shadow.py
"""
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Reuse the exact same raw-rebuild logic as shadow_predict.py so "actual" values are
# computed with the identical water-balance formula the predictions were judged against.
import shadow_predict as sp

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "shadow_predictions_log.csv")


def nse(y, yhat):
    y, yhat = np.asarray(y, dtype=float), np.asarray(yhat, dtype=float)
    denom = np.sum((y - y.mean()) ** 2)
    if denom < 1e-9:
        return float("nan")
    return float(1 - np.sum((y - yhat) ** 2) / denom)


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, dtype=float) - np.asarray(yhat, dtype=float))))


def main():
    if not os.path.exists(LOG_PATH):
        print(f"No predictions logged yet at {LOG_PATH}. Run shadow_predict.py first (and wait).")
        return

    log = pd.read_csv(LOG_PATH, parse_dates=["issued_at"])
    if log.empty:
        print("Prediction log is empty.")
        return

    print("Rebuilding actual Q_in history from raw sources (same formula as predictions)...")
    rows = sp.build_6hourly_rows()
    actual_by_dt = {r["Datetime"]: r["Q_in_t (m3/6h)"] for r in rows}

    print(f"Loaded {len(log)} logged prediction rows, {len(actual_by_dt)} actual 6h marks available.\n")

    per_h_rows = {h: [] for h in range(1, 13)}
    n_scored, n_pending = 0, 0
    for _, row in log.iterrows():
        for h in range(1, 13):
            tgt_col = f"h{h}_target_datetime"
            pred_col = f"h{h}_pred_qin"
            if tgt_col not in row or pd.isna(row[tgt_col]):
                continue
            tgt = pd.Timestamp(row[tgt_col]).to_pydatetime()
            actual = actual_by_dt.get(tgt)
            if actual is None:
                n_pending += 1
                continue
            per_h_rows[h].append({
                "issued_at": row["issued_at"],
                "target_datetime": tgt,
                "pred": row[pred_col],
                "persistence": row["persistence_qin_now"],
                "actual": actual,
            })
            n_scored += 1

    print(f"Scoreable (h, target) pairs with a known actual: {n_scored}  |  still pending (future): {n_pending}\n")

    summary = []
    for h in range(1, 13):
        recs = per_h_rows[h]
        if len(recs) < 3:
            summary.append({"H": h, "lead_hours": 6 * h, "n": len(recs),
                             "model_nse": None, "persistence_nse": None,
                             "model_mae": None, "persistence_mae": None})
            continue
        df_h = pd.DataFrame(recs)
        summary.append({
            "H": h, "lead_hours": 6 * h, "n": len(df_h),
            "model_nse": round(nse(df_h["actual"], df_h["pred"]), 3),
            "persistence_nse": round(nse(df_h["actual"], df_h["persistence"]), 3),
            "model_mae": round(mae(df_h["actual"], df_h["pred"]), 1),
            "persistence_mae": round(mae(df_h["actual"], df_h["persistence"]), 1),
        })

    out = pd.DataFrame(summary)
    out_path = os.path.join(HERE, "shadow_scoring_report.csv")
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 140)
    print(out.to_string(index=False))
    print(f"\nSaved: {out_path}")
    print("\nNote: horizons with n < 3 scored pairs are shown blank -- too early in the "
          "shadow-test period to mean anything yet. Longer horizons (H9-H12, 54h-72h) need "
          "proportionally longer into the month before they accumulate enough scored pairs.")


if __name__ == "__main__":
    main()
