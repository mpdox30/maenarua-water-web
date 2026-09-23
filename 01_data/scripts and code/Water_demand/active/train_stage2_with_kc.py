"""
train_stage2_with_kc.py
=========================
2026-09-23 เพิ่ม -- ข้อ 5 (ปรับปรุงโมเดล magnitude regressor) ส่วนที่ 2: retrain CatBoost+LightGBM
stage2 ทั้ง 24 ชุด (2 โซน x 12 horizon) โดยเพิ่ม feature ใหม่ kc_target_h{h} (จาก
add_kc_target_features.py) เข้าไปใน reg_feats เดิม แล้วเทียบ MAE/RMSE กับโมเดล production
ปัจจุบัน (catboost_models.pkl/lightgbm_models.pkl เดิม) บนชุดทดสอบเดียวกัน (2023+2024,
out-of-sample จาก TRAIN_YEARS=[2020,2021,2022]) ก่อนตัดสินใจ deploy จริง

Protocol เดียวกับโมเดลเดิมทุกประการ (ดู feature_schema.md หัวข้อ 7):
  - Train CatBoost/LightGBM บน TRAIN_YEARS=[2020,2021,2022]
  - คำนวณ stack weight (inverse-MAE) จาก calibration ปี 2023 (WEIGHT_CALIB_YEAR)
  - ประเมินผลสุดท้าย (compare กับ baseline) บน 2023+2024 รวมกัน -- ชุดเดียวกับที่ error_breakdown.py
    ใช้ประเมิน baseline (MAE zone_A=79,135, zone_B=26,466) เพื่อเทียบตรงๆ ได้

**สิ่งที่เปลี่ยนจากเดิม**: reg_feats = get_regressor_features (37 เดิม) + ["kc_target_h{h}"]
(feature ใหม่ 1 ตัว เฉพาะของ horizon นั้นๆ -- ดู add_kc_target_features.py ว่าทำไมต้องแยกไฟล์/
แยกต่อ horizon) -- ไม่แตะ clf_feats/stage1 classifier ในรอบนี้ (โฟกัสแก้ magnitude regressor
ก่อนตามที่วิเคราะห์พบว่าเป็นจุดอ่อนหลัก)

Output (ถ้าผลดีขึ้นจริง คนจะตัดสินใจ deploy เอง ไม่ auto-overwrite .pkl เดิม):
  catboost_models_kc.pkl, lightgbm_models_kc.pkl, stack_weights_kc.pkl
  (ตั้งชื่อแยกจาก production เดิมโดยตั้งใจ -- ปลอดภัย ไม่เสี่ยงเผลอ overwrite ของที่ deploy อยู่)
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor

ACTIVE_DIR = Path(__file__).resolve().parent
HORIZON = 12
ZONES = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
WEIGHT_CALIB_YEAR = 2023
TEST_YEARS = [2023, 2024]


def get_regressor_features(df, df_zone):
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def inverse_mae_weights(mae_cat, mae_lgb):
    w_cat = (1 / mae_cat) / (1 / mae_cat + 1 / mae_lgb)
    w_lgb = 1 - w_cat
    return round(w_cat, 4), round(w_lgb, 4)


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")
    kc = pd.read_csv(ACTIVE_DIR / "kc_target_features.csv")
    df = df.merge(kc, on=["zone", "year", "week"], how="left")

    cat_models, lgb_models, weights = {}, {}, {}
    eval_rows = []

    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        base_reg_feats = get_regressor_features(df, df_zone)

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"
            kc_col = f"kc_target_h{h}"
            reg_feats = base_reg_feats + [kc_col]

            train_df = df_zone[df_zone["year"].isin(TRAIN_YEARS)].dropna(subset=reg_feats + [target_h])
            calib_df = df_zone[df_zone["year"] == WEIGHT_CALIB_YEAR].dropna(subset=reg_feats + [target_h])
            test_df = df_zone[df_zone["year"].isin(TEST_YEARS)].dropna(subset=reg_feats + [target_h])

            X_train, y_train = train_df[reg_feats].values, train_df[target_h].values
            X_calib, y_calib = calib_df[reg_feats].values, calib_df[target_h].values
            X_test, y_test = test_df[reg_feats].values, test_df[target_h].values

            cat_m = CatBoostRegressor(
                iterations=300, depth=4, learning_rate=0.05,
                loss_function="MAE", verbose=False, random_seed=42,
            )
            cat_m.fit(X_train, y_train)

            lgb_m = LGBMRegressor(
                n_estimators=300, max_depth=4, num_leaves=15,
                learning_rate=0.05, min_child_samples=5,
                objective="regression_l1", verbosity=-1, random_state=42,
            )
            lgb_m.fit(X_train, y_train)

            mae_cat = np.mean(np.abs(cat_m.predict(X_calib) - y_calib))
            mae_lgb = np.mean(np.abs(lgb_m.predict(X_calib) - y_calib))
            w_cat, w_lgb = inverse_mae_weights(max(mae_cat, 1e-6), max(mae_lgb, 1e-6))

            key = (zone, h)
            cat_models[key] = cat_m
            lgb_models[key] = lgb_m
            weights[key] = {"w_cat": w_cat, "w_lgb": w_lgb}

            pred = w_cat * cat_m.predict(X_test) + w_lgb * lgb_m.predict(X_test)
            pred = np.maximum(pred, 0)
            mae_new = np.mean(np.abs(pred - y_test))
            rmse_new = np.sqrt(np.mean((pred - y_test) ** 2))
            eval_rows.append({
                "zone": zone, "h": h, "mae_new": mae_new, "rmse_new": rmse_new,
                "n_test": len(y_test),
            })
            print(f"{zone} h{h:2d}: MAE_new={mae_new:>10,.0f}  RMSE_new={rmse_new:>10,.0f}  "
                  f"w_cat={w_cat:.2f} w_lgb={w_lgb:.2f}")

    joblib.dump(cat_models, ACTIVE_DIR / "catboost_models_kc.pkl")
    joblib.dump(lgb_models, ACTIVE_DIR / "lightgbm_models_kc.pkl")
    joblib.dump(weights, ACTIVE_DIR / "stack_weights_kc.pkl")

    edf = pd.DataFrame(eval_rows)
    print("\n" + "=" * 78)
    print("SUMMARY -- new model (with kc_target feature) vs baseline production model")
    print("=" * 78)
    baseline_mae = {"zone_A": 79135, "zone_B": 26466}  # จาก error_breakdown.py (baseline ปัจจุบัน)
    for zone in ZONES:
        sub = edf[edf["zone"] == zone]
        mae_new_overall = (sub["mae_new"] * sub["n_test"]).sum() / sub["n_test"].sum()
        change = (mae_new_overall / baseline_mae[zone] - 1) * 100
        print(f"{zone}: baseline MAE={baseline_mae[zone]:>10,.0f}   new MAE={mae_new_overall:>10,.0f}   "
              f"change={change:+.1f}%")

    print("\nSaved: catboost_models_kc.pkl, lightgbm_models_kc.pkl, stack_weights_kc.pkl "
          "(ไฟล์แยกจาก production เดิม ยังไม่ deploy)")


if __name__ == "__main__":
    main()
