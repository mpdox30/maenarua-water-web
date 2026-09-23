"""
build_mondrian_cqr_intervals.py
==================================
2026-09-23 เพิ่ม -- ขั้นถัดไปจาก CQR (build_cqr_intervals.py): แทนที่จะใช้ q_hat ตัวเดียว
รวมทุกสัปดาห์ (ทั้ง wet และ dry) มาแบ่ง q_hat ตาม regime แบบเดียวกับที่ Mondrian+Normalized
ทำไว้เดิม (build_conformal_intervals.py) -- คือ q_hat_wet (จากสัปดาห์ที่ y_actual > 0) และ
q_hat_dry (จากสัปดาห์ที่ y_actual == 0) แยกกัน

เหตุผล: สัปดาห์ dry (demand=0) เป็น 21-44% ของทุกปี และโมเดล quantile ทำนาย q_lo/q_hi แคบ
พอสมควรสำหรับสัปดาห์เหล่านี้อยู่แล้ว (ทำนายง่ายกว่า) แต่การรวม conformity score จากทุกสัปดาห์
เข้าด้วยกันแบบ global (ทำใน build_cqr_intervals.py เดิม) ทำให้ q_hat ถูกดึงกว้างขึ้นจากสัปดาห์ wet
ที่มี error สูงกว่ามาก -- ผลคือช่วงของสัปดาห์ dry กว้างเกินจำเป็นทั้งที่โมเดลมั่นใจว่าจะเป็น 0

วิธีนี้ (Mondrian-CQR): ใช้โมเดล quantile regression ตัวเดิมจาก build_cqr_intervals.py
(cqr_quantile_models.pkl, ไม่ต้อง retrain) แต่แยกคำนวณ conformal quantile ของ conformity
score E = max(q_lo - y, y - q_hi) ตาม regime ของ calibration set (wet: y_actual > 0,
dry: y_actual == 0) เช่นเดียวกับที่ Mondrian ทำกับ normalized score เดิม

ตอนใช้งานจริง (inference): regime เลือกจาก stage1 classifier -- active (wet) ถ้า
probability_active >= stage1_thresholds[(zone,h)] เหมือน Mondrian เดิมทุกประการ (ความสอดคล้อง
กับของเดิม)

Output: mondrian_cqr_intervals.json (q_hat_wet, q_hat_dry ต่อ zone/horizon + metadata)
ไม่แตะ/ไม่แทนที่ cqr_intervals.json หรือ cqr_quantile_models.pkl เดิม -- ใช้โมเดล quantile
ตัวเดิมร่วมกัน (reuse) เพราะการเทรนควอนไทล์แยก regime ไม่จำเป็น (regime แยกแค่ตอน
conformalize ไม่ใช่ตอนเทรนโมเดล q_lo/q_hi)
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ACTIVE_DIR = Path(__file__).resolve().parent
HORIZON = 12
ZONES = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEARS = [2023, 2024]
ALPHA = 0.10
Q_LO = ALPHA / 2
Q_HI = 1 - ALPHA / 2
MIN_N = 5

CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
TARGET_LAGS = [1, 2, 3, 4]


def get_regressor_features(df, df_zone):
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def get_clf_features(df_zone, target_col):
    lag_cols = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted = CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted if c in df_zone.columns and not df_zone[c].isna().all()]


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    if n == 0:
        return float("inf")
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


def predict_bounds_with_prob(cqr_models, classifiers, df, df_zone, reg_feats, clf_feats,
                              split_df, target_h, zone, h):
    valid = split_df.dropna(subset=reg_feats + clf_feats + [target_h])
    if len(valid) == 0:
        return None
    X_reg = valid[reg_feats].values
    X_clf = valid[clf_feats].values
    y = valid[target_h].values
    q_lo = np.maximum(cqr_models[(zone, h, "lo")].predict(X_reg), 0)
    q_hi = np.maximum(cqr_models[(zone, h, "hi")].predict(X_reg), q_lo)
    prob = classifiers[(zone, h)].predict_proba(X_clf)[:, 1]
    out = valid[["year", "week"]].copy()
    out["y_actual"] = y
    out["q_lo"] = q_lo
    out["q_hi"] = q_hi
    out["prob_active"] = prob
    return out


def coverage(y, lo, hi):
    return float(((y >= lo) & (y <= hi)).mean())


def compute_regime_qhat(sub):
    """sub: DataFrame with y_actual, q_lo, q_hi -- แยก regime ตาม y_actual (calibration only)"""
    y = sub["y_actual"].values
    q_lo = sub["q_lo"].values
    q_hi = sub["q_hi"].values
    e_all = np.maximum(q_lo - y, y - q_hi)
    wet = y > 0
    dry = ~wet
    q_g = conformal_quantile(e_all, ALPHA)
    q_wet = conformal_quantile(e_all[wet], ALPHA) if wet.sum() >= MIN_N else q_g
    q_dry = conformal_quantile(e_all[dry], ALPHA) if dry.sum() >= MIN_N else q_g
    return q_wet, q_dry, int(wet.sum()), int(dry.sum())


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")
    cqr_models = joblib.load(ACTIVE_DIR / "cqr_quantile_models.pkl")
    classifiers = joblib.load(ACTIVE_DIR / "stage1_classifiers.pkl")
    thresholds = joblib.load(ACTIVE_DIR / "stage1_thresholds.pkl")

    preds_2023, preds_2024 = [], []

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone = df[df["zone"] == zone].copy()
        reg_feats = get_regressor_features(df, df_zone)
        clf_feats = get_clf_features(df_zone, target_col)

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"
            for yr, bucket in [(2023, preds_2023), (2024, preds_2024)]:
                split_df = df_zone[df_zone["year"] == yr]
                p = predict_bounds_with_prob(cqr_models, classifiers, df, df_zone,
                                              reg_feats, clf_feats, split_df, target_h,
                                              zone, h)
                if p is not None:
                    p["zone"] = zone
                    p["horizon"] = h
                    bucket.append(p)

    preds_2023 = pd.concat(preds_2023, ignore_index=True)
    preds_2024 = pd.concat(preds_2024, ignore_index=True)
    preds_combined = pd.concat([preds_2023, preds_2024], ignore_index=True)

    # ---- Two-way holdout validation ----
    print("=" * 78)
    print("TWO-WAY HOLDOUT VALIDATION (Mondrian-CQR: q_hat แยก wet/dry)")
    print("=" * 78)
    for calib_name, calib_df, test_name, test_df in [
        ("2023", preds_2023, "2024", preds_2024),
        ("2024", preds_2024, "2023", preds_2023),
    ]:
        rows = []
        for zone in ZONES:
            for h in range(1, HORIZON + 1):
                thr = thresholds[(zone, h)]
                ca = calib_df[(calib_df["zone"] == zone) & (calib_df["horizon"] == h)]
                te = test_df[(test_df["zone"] == zone) & (test_df["horizon"] == h)]
                if len(ca) == 0 or len(te) == 0:
                    continue
                q_wet, q_dry, n_wet, n_dry = compute_regime_qhat(ca)

                y_te = te["y_actual"].values
                q_lo_te = te["q_lo"].values
                q_hi_te = te["q_hi"].values
                active_te = te["prob_active"].values >= thr
                q_hat_te = np.where(active_te, q_wet, q_dry)
                lo = np.maximum(q_lo_te - q_hat_te, 0)
                hi = q_hi_te + q_hat_te
                cov = coverage(y_te, lo, hi)
                iw = (hi - lo).mean()
                rows.append({"zone": zone, "horizon": h, "coverage": cov, "IW": iw})
        rdf = pd.DataFrame(rows)
        print(f"\ncalibrate={calib_name} -> test={test_name}:")
        for zone in ZONES:
            sub = rdf[rdf["zone"] == zone]
            print(f"  {zone}: mean coverage={sub['coverage'].mean():.3f}  "
                  f"mean IW={sub['IW'].mean():,.0f} m3  "
                  f"(below 85%: {(sub['coverage'] < 0.85).sum()}/{len(sub)})")

    # ---- Final: pooled 2023+2024 calibration ----
    print("\n" + "=" * 78)
    print("FINAL ARTIFACT -- Mondrian-CQR calibrated on 2023+2024 pooled")
    print("=" * 78)
    out = {}
    compare_rows = []
    for zone in ZONES:
        out[zone] = {}
        for h in range(1, HORIZON + 1):
            thr = thresholds[(zone, h)]
            sub = preds_combined[(preds_combined["zone"] == zone) & (preds_combined["horizon"] == h)]
            q_wet, q_dry, n_wet, n_dry = compute_regime_qhat(sub)
            # global q_hat (จาก build_cqr_intervals.py เดิม) สำหรับเทียบ
            e_all = np.maximum(sub["q_lo"] - sub["y_actual"], sub["y_actual"] - sub["q_hi"])
            q_global = conformal_quantile(e_all.values, ALPHA)

            out[zone][str(h)] = {
                "q_hat_wet": round(q_wet, 2),
                "q_hat_dry": round(q_dry, 2),
                "threshold": round(float(thr), 4),
                "n_calib_wet": n_wet,
                "n_calib_dry": n_dry,
            }
            compare_rows.append({
                "zone": zone, "h": h, "q_global": q_global,
                "q_wet": q_wet, "q_dry": q_dry,
            })
            print(f"  {zone} h{h:2d}: q_global={q_global:>10,.0f}  "
                  f"q_wet={q_wet:>10,.0f} (n={n_wet})  q_dry={q_dry:>10,.0f} (n={n_dry})")

    cdf = pd.DataFrame(compare_rows)
    print("\n--- dry-week interval width reduction vs global q_hat (2*q) ---")
    for zone in ZONES:
        sub = cdf[cdf["zone"] == zone]
        reduction = 1 - (sub["q_dry"].sum() / sub["q_global"].sum())
        print(f"  {zone}: dry q_hat sum {sub['q_global'].sum():,.0f} -> {sub['q_dry'].sum():,.0f}  "
              f"(-{reduction:.1%})")

    meta = {
        "methodology": (
            "Mondrian-CQR -- ใช้โมเดล quantile regression เดิมจาก build_cqr_intervals.py "
            "(cqr_quantile_models.pkl, ไม่ retrain) แต่แยกคำนวณ conformal quantile ของ "
            "conformity score E=max(q_lo-y, y-q_hi) ตาม regime wet(y_calib>0)/dry(y_calib==0) "
            "แทนที่จะรวมเป็น q_hat เดียว (global) แบบ build_cqr_intervals.py เดิม"
        ),
        "alpha": ALPHA,
        "quantile_lo": Q_LO,
        "quantile_hi": Q_HI,
        "target_coverage": 1 - ALPHA,
        "train_years": TRAIN_YEARS,
        "calib_years": CALIB_YEARS,
        "regime_rule": "active (wet) if stage1 probability_active >= stage1_thresholds[(zone,h)], else dry",
        "interval_formula": (
            "q_hat = q_hat_wet if active else q_hat_dry; "
            "lower = max(q_lo(x) - q_hat, 0); upper = q_hi(x) + q_hat"
        ),
        "uses_quantile_models_from": "cqr_quantile_models.pkl (shared, ไม่ได้ retrain)",
        "computed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    result = {"_meta": meta, "quantiles": out}
    with open(ACTIVE_DIR / "mondrian_cqr_intervals.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\nSaved mondrian_cqr_intervals.json")


if __name__ == "__main__":
    main()
