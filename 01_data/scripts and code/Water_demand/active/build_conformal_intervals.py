"""
build_conformal_intervals.py
==============================
2026-09-23 เพิ่ม -- re-calibrate Mondrian Conformal Prediction (Variant D: Mondrian + Normalized,
FINAL variant ตาม combined_final_pipeline.ipynb Step 4v3) จากโมเดล production จริงใน
Water_demand/active/ (ไม่ใช่โมเดลจำลอง) แล้ว export q_norm_wet/q_norm_dry ต่อ (zone, horizon)
เป็น conformal_intervals.json สำหรับให้ data_pipeline.py โหลดไปคำนวณ lower_m3/upper_m3 ต่อ

รวม 2 ขั้นตอนจาก notebook เข้าด้วยกัน:
  Step 3e (cell 38): รัน stage1+stage2 บนข้อมูล calib(2023)/test(2024) -> final_predictions_2stage
  Step 4v3 (cell 44): Normalized Mondrian conformal quantile จาก calib scores -> q_norm_wet/dry
                       ต่อ (zone, horizon) แล้ว apply ชุด test(2024) ตรวจสอบ coverage จริง

Methodology คัดลอกตรงตัวจาก notebook (ไม่ได้แก้สูตร) เพื่อให้ผลตรงกับที่ manuscript รายงานไว้:
  score = |y - yhat| / (|yhat| + epsilon), epsilon = 1000 m3
  q_hat = conformal_quantile(scores, alpha=0.10)  -- finite-sample corrected quantile
  แยก q_hat ตาม regime: wet (y_calib > 0) / dry (y_calib == 0) -- Mondrian
  interval = yhat +/- q_hat_regime * (|yhat| + epsilon), clip lower >= 0
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
CALIB_YEAR = 2023
TEST_YEAR = 2024
ALPHA = 0.10
MIN_N = 5
EPSILON = 1_000

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


def norm_scores(y, yhat, eps=EPSILON):
    return np.abs(y - yhat) / (np.abs(yhat) + eps)


def apply_norm_interval(yhat, q_norm, eps=EPSILON):
    half = q_norm * (np.abs(yhat) + eps)
    lower = np.maximum(yhat - half, 0)
    upper = yhat + half
    return lower, upper


def coverage(y, lower, upper):
    covered = (y >= lower) & (y <= upper)
    return float(covered.mean())


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")
    cat_models = joblib.load(ACTIVE_DIR / "catboost_models.pkl")
    lgb_models = joblib.load(ACTIVE_DIR / "lightgbm_models.pkl")
    weights = joblib.load(ACTIVE_DIR / "stack_weights.pkl")
    classifiers = joblib.load(ACTIVE_DIR / "stage1_classifiers.pkl")
    thresholds = joblib.load(ACTIVE_DIR / "stage1_thresholds.pkl")

    # ---- Step 3e: predict calib(2023) + test(2024) สำหรับทุก (zone, horizon) ----
    all_preds = []
    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone = df[df["zone"] == zone].copy()
        reg_feats = get_regressor_features(df, df_zone)
        clf_feats = get_clf_features(df_zone, target_col)

        for split_year, split_name in [(CALIB_YEAR, "calib"), (TEST_YEAR, "test")]:
            split_df = df_zone[df_zone["year"] == split_year].copy()
            for h in range(1, HORIZON + 1):
                target_h = f"y_h{h}"
                valid = split_df.dropna(subset=reg_feats + clf_feats + [target_h])
                if len(valid) == 0:
                    continue
                X_reg = valid[reg_feats].values
                X_clf = valid[clf_feats].values
                y_obs = valid[target_h].values

                key = (zone, h)
                prob = classifiers[key].predict_proba(X_clf)[:, 1]
                w = weights[key]
                mag = (w["w_cat"] * cat_models[key].predict(X_reg) +
                       w["w_lgb"] * lgb_models[key].predict(X_reg))
                mag = np.maximum(mag, 0)
                y_hat = prob * mag

                rows = valid[["year", "week"]].copy()
                rows["zone"] = zone
                rows["horizon"] = h
                rows["split"] = split_name
                rows["y_actual"] = y_obs
                rows["y_stage1_prob"] = prob
                rows["y_pred_2stage"] = y_hat
                all_preds.append(rows)

    preds_df = pd.concat(all_preds, ignore_index=True)

    # ---- Step 4v3: Normalized Mondrian conformal (Variant D) ----
    out = {}
    coverage_rows = []
    for zone in ZONES:
        z = preds_df[preds_df["zone"] == zone]
        calib_df = z[z["split"] == "calib"]
        test_df = z[z["split"] == "test"]
        out[zone] = {}

        for h in range(1, HORIZON + 1):
            thr = thresholds[(zone, h)]
            ca_h = calib_df[calib_df["horizon"] == h]
            te_h = test_df[test_df["horizon"] == h]

            y_ca = ca_h["y_actual"].values
            yh_ca = ca_h["y_pred_2stage"].values
            wet_ca = y_ca > 0
            dry_ca = ~wet_ca

            s_nrm_all = norm_scores(y_ca, yh_ca)
            s_nrm_wet = s_nrm_all[wet_ca]
            s_nrm_dry = s_nrm_all[dry_ca]

            q_nrm_g = conformal_quantile(s_nrm_all, ALPHA)
            q_nrm_wet = (conformal_quantile(s_nrm_wet, ALPHA)
                         if len(s_nrm_wet) >= MIN_N else q_nrm_g)
            q_nrm_dry = (conformal_quantile(s_nrm_dry, ALPHA)
                         if len(s_nrm_dry) >= MIN_N else q_nrm_g)

            out[zone][str(h)] = {
                "q_wet": round(float(q_nrm_wet), 6),
                "q_dry": round(float(q_nrm_dry), 6),
                "threshold": round(float(thr), 4),
                "n_calib_wet": int(wet_ca.sum()),
                "n_calib_dry": int(dry_ca.sum()),
            }

            # ---- ตรวจสอบ coverage จริงบน test(2024) เพื่อ sanity check ----
            if len(te_h) > 0:
                y_te = te_h["y_actual"].values
                yh_te = te_h["y_pred_2stage"].values
                prob_te = te_h["y_stage1_prob"].values
                active = prob_te >= thr
                q_applied = np.where(active, q_nrm_wet, q_nrm_dry)
                lo, up = apply_norm_interval(yh_te, q_applied)
                cov = coverage(y_te, lo, up)
                coverage_rows.append({"zone": zone, "horizon": h, "coverage": round(cov, 3),
                                       "n_test": len(y_te)})

    meta = {
        "methodology": "Mondrian + Normalized conformal prediction (Variant D, combined_final_pipeline.ipynb Step 4v3)",
        "alpha": ALPHA,
        "target_coverage": 1 - ALPHA,
        "epsilon_m3": EPSILON,
        "calib_year": CALIB_YEAR,
        "test_year_for_validation": TEST_YEAR,
        "regime_rule": "active (wet) if stage1 probability_active >= stage1_thresholds[(zone,h)], else dry",
        "interval_formula": "half = q_regime * (abs(final_m3) + epsilon); lower = max(final_m3 - half, 0); upper = final_m3 + half",
        "computed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "note": "q_wet/q_dry recomputed 2026-09-23 -- ไม่เคยมี artifact ก่อนหน้านี้ notebook ต้นทางไม่มี saved cell outputs",
    }

    result = {"_meta": meta, "quantiles": out}

    out_path = ACTIVE_DIR / "conformal_intervals.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    cov_df = pd.DataFrame(coverage_rows)
    print("Saved:", out_path)
    print("\n=== Coverage on test(2024), target = 90% ===")
    print(cov_df.to_string(index=False))
    print("\nBelow-target horizons:", (cov_df["coverage"] < 0.85).sum(), "/", len(cov_df))
    print("\nOverall mean coverage by zone:")
    print(cov_df.groupby("zone")["coverage"].mean())


if __name__ == "__main__":
    main()
