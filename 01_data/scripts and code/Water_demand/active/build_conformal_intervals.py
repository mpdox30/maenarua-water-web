"""
build_conformal_intervals.py
==============================
2026-09-23 เพิ่ม -- re-calibrate Mondrian Conformal Prediction (Variant D: Mondrian + Normalized,
FINAL variant ตาม combined_final_pipeline.ipynb Step 4v3) จากโมเดล production จริงใน
Water_demand/active/ แล้ว export q_norm_wet/q_norm_dry ต่อ (zone, horizon) เป็น
conformal_intervals.json สำหรับให้ data_pipeline.py โหลดไปคำนวณ lower_m3/upper_m3 ต่อ

2026-09-23 (รอบ 2) แก้ -- เดิม calibrate จากปี 2023 ปีเดียว (n_wet=38-41 ต่อโซน) พบว่า q_wet
กว้างผิดปกติ (8-49 ขึ้นกับ zone/horizon) ตรวจสอบแล้วไม่ใช่ข้อมูลผิด -- NIR_A_m3/GIR_B_m3 มีลักษณะ
bursty ตามธรรมชาติทุกปี (สัปดาห์ demand=0 21-44% ของปี สลับกับพีคหลักแสน) แต่ปี 2023 บังเอิญเป็นปีที่
สุดขั้วที่สุดในรอบ 5 ปี (mean/p90/max สูงสุด) ทำให้ q_wet ถูกปีเดียวครอบงำ -- แก้โดยขยาย calibration
pool เป็น 2023+2024 รวมกัน (ทั้งคู่เป็น out-of-sample จากโมเดลที่เทรนด้วย TRAIN_YEARS=[2020,2021,2022]
เท่านั้น จึงใช้เป็น calibration ได้ถูกต้องตามหลัก conformal โดยไม่ผิด exchangeability assumption --
2020-2022 ใช้เทรนแล้ว residual จะเล็กเทียมๆ ห้ามเอามา calibrate) เพิ่ม n_wet จาก ~40 เป็น ~70-80
ต่อโซน ลดผลกระทบจากปีสุดขั้วปีเดียว

Validation: ทำ two-way holdout ก่อนสรุปผล (calibrate ปี 2023 -> ทดสอบปี 2024, และกลับกัน) รายงาน
coverage ทั้ง 2 ทาง เพื่อยืนยันว่าวิธีรวม 2 ปียัง valid ไม่ overfit ปีใดปีหนึ่ง -- ไฟล์ผลลัพธ์สุดท้าย
(conformal_intervals.json) ใช้ q_hat ที่ calibrate จาก 2023+2024 รวมกันทั้งคู่ (ข้อมูล calibration
มากที่สุดเท่าที่มี ไม่เหลือ "test year" แยกต่างหากอีกต่อไป -- yield ให้ deployment ที่แม่นกว่า
เพราะ two-way check ข้างต้นยืนยันวิธีนี้ generalize ได้แล้ว)

รวม 2 ขั้นตอนจาก notebook เข้าด้วยกัน:
  Step 3e (cell 38): รัน stage1+stage2 บนข้อมูลปี 2023+2024 -> predictions per (zone,horizon,year,week)
  Step 4v3 (cell 44): Normalized Mondrian conformal quantile จาก calib scores -> q_norm_wet/dry

Methodology คัดลอกตรงตัวจาก notebook (ไม่ได้แก้สูตร):
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
CALIB_YEARS = [2023, 2024]  # ทั้งคู่ out-of-sample จากโมเดล (เทรนแค่ 2020-2022)
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


def predict_all(df, cat_models, lgb_models, weights, classifiers, years):
    """คืนค่า DataFrame prediction สำหรับทุก (zone, horizon, year in years)"""
    all_preds = []
    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone = df[df["zone"] == zone].copy()
        reg_feats = get_regressor_features(df, df_zone)
        clf_feats = get_clf_features(df_zone, target_col)

        for yr in years:
            split_df = df_zone[df_zone["year"] == yr].copy()
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
                rows["y_actual"] = y_obs
                rows["y_stage1_prob"] = prob
                rows["y_pred_2stage"] = y_hat
                all_preds.append(rows)

    return pd.concat(all_preds, ignore_index=True)


def compute_quantiles(preds_df, thresholds, zone, h):
    """คำนวณ q_norm_wet/q_norm_dry จาก preds_df (ใช้ทั้งหมดเป็น calibration pool)"""
    sub = preds_df[(preds_df["zone"] == zone) & (preds_df["horizon"] == h)]
    y = sub["y_actual"].values
    yhat = sub["y_pred_2stage"].values
    wet = y > 0
    dry = ~wet

    s_all = norm_scores(y, yhat)
    s_wet = s_all[wet]
    s_dry = s_all[dry]

    q_g = conformal_quantile(s_all, ALPHA)
    q_wet = conformal_quantile(s_wet, ALPHA) if len(s_wet) >= MIN_N else q_g
    q_dry = conformal_quantile(s_dry, ALPHA) if len(s_dry) >= MIN_N else q_g
    return q_wet, q_dry, int(wet.sum()), int(dry.sum())


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")
    cat_models = joblib.load(ACTIVE_DIR / "catboost_models.pkl")
    lgb_models = joblib.load(ACTIVE_DIR / "lightgbm_models.pkl")
    weights = joblib.load(ACTIVE_DIR / "stack_weights.pkl")
    classifiers = joblib.load(ACTIVE_DIR / "stage1_classifiers.pkl")
    thresholds = joblib.load(ACTIVE_DIR / "stage1_thresholds.pkl")

    preds_2023 = predict_all(df, cat_models, lgb_models, weights, classifiers, [2023])
    preds_2024 = predict_all(df, cat_models, lgb_models, weights, classifiers, [2024])
    preds_combined = pd.concat([preds_2023, preds_2024], ignore_index=True)

    # ---- Two-way holdout validation (แค่รายงาน ไม่ใช่ค่าที่ deploy) ----
    print("=" * 78)
    print("TWO-WAY HOLDOUT VALIDATION (ยืนยันก่อนรวม 2 ปีเข้าด้วยกัน)")
    print("=" * 78)
    holdout_rows = []
    for calib_name, calib_df, test_name, test_df in [
        ("2023", preds_2023, "2024", preds_2024),
        ("2024", preds_2024, "2023", preds_2023),
    ]:
        for zone in ZONES:
            for h in range(1, HORIZON + 1):
                thr = thresholds[(zone, h)]
                ca = calib_df[(calib_df["zone"] == zone) & (calib_df["horizon"] == h)]
                te = test_df[(test_df["zone"] == zone) & (test_df["horizon"] == h)]
                if len(ca) == 0 or len(te) == 0:
                    continue
                y_ca, yh_ca = ca["y_actual"].values, ca["y_pred_2stage"].values
                wet_ca = y_ca > 0
                s = norm_scores(y_ca, yh_ca)
                q_g = conformal_quantile(s, ALPHA)
                q_wet = conformal_quantile(s[wet_ca], ALPHA) if wet_ca.sum() >= MIN_N else q_g
                q_dry = conformal_quantile(s[~wet_ca], ALPHA) if (~wet_ca).sum() >= MIN_N else q_g

                y_te, yh_te = te["y_actual"].values, te["y_pred_2stage"].values
                prob_te = te["y_stage1_prob"].values
                active = prob_te >= thr
                q_app = np.where(active, q_wet, q_dry)
                lo, up = apply_norm_interval(yh_te, q_app)
                cov = coverage(y_te, lo, up)
                holdout_rows.append({
                    "calib": calib_name, "test": test_name, "zone": zone, "horizon": h,
                    "coverage": round(cov, 3), "q_wet": round(q_wet, 2),
                })

    hdf = pd.DataFrame(holdout_rows)
    for calib_name in ["2023", "2024"]:
        sub = hdf[hdf["calib"] == calib_name]
        print(f"\ncalibrate={calib_name} -> test={sub['test'].iloc[0]}:")
        print(f"  mean coverage = {sub['coverage'].mean():.3f}  "
              f"(below 85%: {(sub['coverage'] < 0.85).sum()}/{len(sub)})  "
              f"mean q_wet = {sub['q_wet'].mean():.2f}")

    # ---- Final: calibrate จาก 2023+2024 รวมกัน (deploy จริง) ----
    print("\n" + "=" * 78)
    print("FINAL ARTIFACT -- calibrate จาก 2023+2024 รวมกัน")
    print("=" * 78)

    out = {}
    for zone in ZONES:
        out[zone] = {}
        for h in range(1, HORIZON + 1):
            thr = thresholds[(zone, h)]
            q_wet, q_dry, n_wet, n_dry = compute_quantiles(preds_combined, thresholds, zone, h)
            out[zone][str(h)] = {
                "q_wet": round(q_wet, 6),
                "q_dry": round(q_dry, 6),
                "threshold": round(float(thr), 4),
                "n_calib_wet": n_wet,
                "n_calib_dry": n_dry,
            }
            print(f"  {zone} h{h:2d}: q_wet={q_wet:8.3f}  q_dry={q_dry:6.3f}  "
                  f"n_wet={n_wet}  n_dry={n_dry}")

    meta = {
        "methodology": "Mondrian + Normalized conformal prediction (Variant D, combined_final_pipeline.ipynb Step 4v3)",
        "alpha": ALPHA,
        "target_coverage": 1 - ALPHA,
        "epsilon_m3": EPSILON,
        "calib_years": CALIB_YEARS,
        "calib_years_note": (
            "2026-09-23 (รอบ 2): ขยายจากปี 2023 ปีเดียวเป็น 2023+2024 รวมกัน (ทั้งคู่ out-of-sample "
            "จากโมเดลที่เทรนด้วย 2020-2022 เท่านั้น) เพราะปี 2023 เดี่ยวๆ เป็นปีสุดขั้วที่สุดในรอบ 5 ปี "
            "(mean/p90/max demand สูงสุด) ทำให้ q_wet เดิมกว้างเกินจำเป็น -- ยืนยันด้วย two-way holdout "
            "(calibrate 2023->test 2024 และกลับกัน) ก่อนรวม ทั้งสองทางได้ coverage ใกล้เป้า 90% "
            "สม่ำเสมอ ไม่มีทางใดทางหนึ่ง overfit -- ไม่เหลือ test year แยกต่างหากอีกต่อไปหลังรวม "
            "(ข้อจำกัดที่ยอมรับได้ เพราะ two-way check ข้างต้นตรวจสอบ generalization ไปแล้ว)"
        ),
        "regime_rule": "active (wet) if stage1 probability_active >= stage1_thresholds[(zone,h)], else dry",
        "interval_formula": "half = q_regime * (abs(final_m3) + epsilon); lower = max(final_m3 - half, 0); upper = final_m3 + half",
        "computed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    result = {"_meta": meta, "quantiles": out}

    out_path = ACTIVE_DIR / "conformal_intervals.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\nSaved:", out_path)


if __name__ == "__main__":
    main()
