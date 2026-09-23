"""
build_cqr_intervals.py
========================
2026-09-23 เพิ่ม -- Conformalized Quantile Regression (CQR) สำหรับ Water Demand เป็นทางเลือกแทน
Mondrian+Normalized conformal (build_conformal_intervals.py) โดยเฉพาะ Zone A ที่ยังกว้างอยู่แม้ขยาย
calibration เป็น 2 ปีแล้ว (ดู commit ก่อนหน้า) -- สาเหตุคือ Zone A มีสัปดาห์พีค pulse-irrigation
เกิดขึ้นซ้ำทุกปี ทำให้ normalized-residual รอบ point-estimate เดียว (final_m3 = prob*magnitude)
กว้างเกินจำเป็นเมื่อโมเดลจุดพลาดเป้าหนักในสัปดาห์เหล่านั้น

CQR ต่างจาก Mondrian+Normalized ตรงที่ไม่ใช้ residual รอบ point estimate เดียว แต่เทรนโมเดล
quantile regression 2 ตัวแยกกันต่อ (zone, horizon): q_lo (5th percentile) และ q_hi (95th
percentile) ที่ปรับ shape ตาม feature ได้เอง (รวมถึงจับ skew/bursty ของข้อมูลได้เป็นธรรมชาติ
มากกว่า) แล้วค่อย conformalize ช่องว่างระหว่าง q_lo/q_hi ด้วย conformity score:
    E_i = max(q_lo(x_i) - y_i, y_i - q_hi(x_i))
    q_hat = conformal_quantile(E, alpha)
    interval = [max(q_lo(x) - q_hat, 0), q_hi(x) + q_hat]

Training: LightGBM quantile regression, TRAIN_YEARS=[2020,2021,2022] (เดียวกับที่ใช้เทรน
stage2 magnitude regressor เดิม) -- calibration/validation: 2023+2024 (two-way holdout ก่อน
แล้วค่อย pool รวมกันสำหรับ artifact สุดท้าย เหมือน build_conformal_intervals.py รอบ 2)

หมายเหตุสำคัญ: CQR bound ตรงนี้เป็นการ bound ค่า y_h{h} (raw target) ตรงๆ ไม่ได้ผูกกับ
final_m3 (prob_active * magnitude) แบบ Mondrian+Normalized เดิม -- final_m3 ยังใช้เป็นค่า
พยากรณ์หลัก (point estimate) เหมือนเดิมทุกจุด เปลี่ยนแค่วิธีคำนวณ lower_m3/upper_m3

Output: cqr_quantile_models.pkl  (dict {(zone,h,'lo'|'hi'): LGBMRegressor})
        cqr_intervals.json       (q_hat + metadata ต่อ zone/horizon)
"""
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

ACTIVE_DIR = Path(__file__).resolve().parent
HORIZON = 12
ZONES = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEARS = [2023, 2024]
ALPHA = 0.10  # target coverage 90% -> quantile levels 0.05 / 0.95
Q_LO = ALPHA / 2
Q_HI = 1 - ALPHA / 2
MIN_N = 5


def get_regressor_features(df, df_zone):
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    if n == 0:
        return float("inf")
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


def train_quantile_models(df, df_zone, reg_feats, target_h, train_df):
    valid = train_df.dropna(subset=reg_feats + [target_h])
    X = valid[reg_feats].values
    y = valid[target_h].values

    models = {}
    for q, tag in [(Q_LO, "lo"), (Q_HI, "hi")]:
        m = lgb.LGBMRegressor(
            objective="quantile", alpha=q,
            n_estimators=150, max_depth=4, num_leaves=15,
            learning_rate=0.05, min_child_samples=5,
            verbosity=-1,
        )
        m.fit(X, y)
        models[tag] = m
    return models


def predict_bounds(models, df_zone, reg_feats, split_df, target_h):
    valid = split_df.dropna(subset=reg_feats + [target_h])
    if len(valid) == 0:
        return None
    X = valid[reg_feats].values
    y = valid[target_h].values
    q_lo = np.maximum(models["lo"].predict(X), 0)
    q_hi = np.maximum(models["hi"].predict(X), q_lo)
    return valid[["year", "week"]].assign(y_actual=y, q_lo=q_lo, q_hi=q_hi)


def coverage(y, lo, hi):
    return float(((y >= lo) & (y <= hi)).mean())


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")

    all_models = {}
    preds_2023, preds_2024 = [], []

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone = df[df["zone"] == zone].copy()
        reg_feats = get_regressor_features(df, df_zone)
        train_df = df_zone[df_zone["year"].isin(TRAIN_YEARS)]

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"
            models = train_quantile_models(df, df_zone, reg_feats, target_h, train_df)
            all_models[(zone, h, "lo")] = models["lo"]
            all_models[(zone, h, "hi")] = models["hi"]

            for yr, bucket in [(2023, preds_2023), (2024, preds_2024)]:
                split_df = df_zone[df_zone["year"] == yr]
                p = predict_bounds(models, df_zone, reg_feats, split_df, target_h)
                if p is not None:
                    p["zone"] = zone
                    p["horizon"] = h
                    bucket.append(p)

    preds_2023 = pd.concat(preds_2023, ignore_index=True)
    preds_2024 = pd.concat(preds_2024, ignore_index=True)
    preds_combined = pd.concat([preds_2023, preds_2024], ignore_index=True)

    # ---- Two-way holdout validation ----
    print("=" * 78)
    print("TWO-WAY HOLDOUT VALIDATION (CQR)")
    print("=" * 78)
    for calib_name, calib_df, test_name, test_df in [
        ("2023", preds_2023, "2024", preds_2024),
        ("2024", preds_2024, "2023", preds_2023),
    ]:
        rows = []
        for zone in ZONES:
            for h in range(1, HORIZON + 1):
                ca = calib_df[(calib_df["zone"] == zone) & (calib_df["horizon"] == h)]
                te = test_df[(test_df["zone"] == zone) & (test_df["horizon"] == h)]
                if len(ca) == 0 or len(te) == 0:
                    continue
                e = np.maximum(ca["q_lo"] - ca["y_actual"], ca["y_actual"] - ca["q_hi"])
                q_hat = conformal_quantile(e.values, ALPHA)
                lo = np.maximum(te["q_lo"] - q_hat, 0)
                hi = te["q_hi"] + q_hat
                cov = coverage(te["y_actual"].values, lo.values, hi.values)
                iw = (hi - lo).mean()
                rows.append({"zone": zone, "horizon": h, "coverage": cov, "IW": iw})
        rdf = pd.DataFrame(rows)
        print(f"\ncalibrate={calib_name} -> test={test_name}:")
        for zone in ZONES:
            sub = rdf[rdf["zone"] == zone]
            print(f"  {zone}: mean coverage={sub['coverage'].mean():.3f}  "
                  f"mean IW={sub['IW'].mean():,.0f} m3  "
                  f"(below 85%: {(sub['coverage'] < 0.85).sum()}/{len(sub)})")

    # ---- Final: calibrate on 2023+2024 pooled ----
    print("\n" + "=" * 78)
    print("FINAL ARTIFACT -- CQR calibrated on 2023+2024 pooled")
    print("=" * 78)
    out = {}
    for zone in ZONES:
        out[zone] = {}
        for h in range(1, HORIZON + 1):
            sub = preds_combined[(preds_combined["zone"] == zone) & (preds_combined["horizon"] == h)]
            e = np.maximum(sub["q_lo"] - sub["y_actual"], sub["y_actual"] - sub["q_hi"])
            q_hat = conformal_quantile(e.values, ALPHA)
            out[zone][str(h)] = {"q_hat": round(float(q_hat), 2), "n_calib": len(sub)}
            iw_mean = (sub["q_hi"] - sub["q_lo"] + 2 * q_hat).mean()
            print(f"  {zone} h{h:2d}: q_hat={q_hat:>10,.0f}  mean_IW={iw_mean:>10,.0f} m3  n={len(sub)}")

    joblib.dump(all_models, ACTIVE_DIR / "cqr_quantile_models.pkl")

    meta = {
        "methodology": "Conformalized Quantile Regression (CQR) -- LightGBM quantile regression + split conformal",
        "alpha": ALPHA,
        "quantile_lo": Q_LO,
        "quantile_hi": Q_HI,
        "target_coverage": 1 - ALPHA,
        "train_years": TRAIN_YEARS,
        "calib_years": CALIB_YEARS,
        "interval_formula": "lower = max(q_lo(x) - q_hat, 0); upper = q_hi(x) + q_hat",
        "note": (
            "Bound ค่า y_h{h} (raw target) ตรงๆ ไม่ผูกกับ final_m3 (prob*magnitude) แบบ "
            "Mondrian+Normalized เดิม -- ใช้เป็นทางเลือกเปรียบเทียบสำหรับ Zone A โดยเฉพาะ "
            "ที่ยังกว้างอยู่หลังขยาย calibration เป็น 2 ปี"
        ),
        "computed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    result = {"_meta": meta, "quantiles": out}
    with open(ACTIVE_DIR / "cqr_intervals.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\nSaved cqr_quantile_models.pkl + cqr_intervals.json")


if __name__ == "__main__":
    main()
