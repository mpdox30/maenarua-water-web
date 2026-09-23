"""
train_stage2_baseline_2025.py
==============================
2026-09-23 เพิ่ม -- ข้อ 6 ส่วนที่ 2: retrain CatBoost+LightGBM stage2 ทั้ง 24 ชุด
(2 โซน x 12 horizon) ด้วย feature set เดิมของ production (ไม่มี Kc) แต่ใช้
ml_features_phase4.csv เวอร์ชันใหม่ที่ merge ข้อมูลปี 2025 เข้าไปแล้ว
(merge_2025_backfill.py) -- เทียบ MAE กับ baseline เดิมที่บันทึกไว้ตอน
train_stage2_with_kc.py (zone_A=79,135, zone_B=26,466)

Protocol เหมือนเดิมทุกประการ (เพื่อแยกผลของ "มีข้อมูลปี 2025 เติมเต็ม
y_h1..h12 ของปลายปี 2024" ออกจากตัวแปรอื่น):
  - TRAIN_YEARS      = [2020, 2021, 2022]   (ไม่รวม 2025 เป็น training ตรงๆ
    -- 2025 มีหน้าที่แค่เติม target label ของปลายปี 2024 ที่ shift(-h) ไปเจอ
    NaN ตอนไม่มีปี 2025 ให้ shift)
  - WEIGHT_CALIB_YEAR = 2023
  - TEST_YEARS        = [2023, 2024]        (เหมือนเดิม -- แต่ตอนนี้ TEST SET
    ที่ dropna แล้วจะมีแถวมากขึ้นกว่าเดิม เพราะปลายปี 2024 เดิม y_h ยาวๆ เป็น
    NaN ถูก dropna(subset=...) ตัดออกไปจาก TEST ทั้งที่ควรทดสอบได้ -- ตอนนี้
    มีค่าจริงแล้วจึงเข้า TEST ได้ครบมากขึ้น)
  - Hyperparameters เดิมทุกตัว (CatBoost/LightGBM) ตาม train_stage2_with_kc.py

**ไม่มี kc_target feature ในรอบนี้** -- เก็บ Kc ไว้เป็นการทดลองแยกตามที่
ตัดสินใจไว้ (ดู #52-54 ในบันทึก)

Output (ยังไม่ deploy ทับ production เอง):
  catboost_models_2025.pkl, lightgbm_models_2025.pkl, stack_weights_2025.pkl
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

BASELINE_MAE_OLD = {"zone_A": 79135, "zone_B": 26466}  # จาก error_breakdown.py / train_stage2_with_kc.py


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
    print(f"โหลด ml_features_phase4.csv: {df.shape[0]} แถว, ปี {sorted(df['year'].unique())}")

    cat_models, lgb_models, weights = {}, {}, {}
    eval_rows = []

    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        reg_feats = get_regressor_features(df, df_zone)

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"

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
                "n_test": len(y_test), "n_train": len(y_train),
            })
            print(f"{zone} h{h:2d}: n_train={len(y_train):>4d}  n_test={len(y_test):>3d}  "
                  f"MAE_new={mae_new:>10,.0f}  RMSE_new={rmse_new:>10,.0f}  "
                  f"w_cat={w_cat:.2f} w_lgb={w_lgb:.2f}")

    joblib.dump(cat_models, ACTIVE_DIR / "catboost_models_2025.pkl")
    joblib.dump(lgb_models, ACTIVE_DIR / "lightgbm_models_2025.pkl")
    joblib.dump(weights, ACTIVE_DIR / "stack_weights_2025.pkl")

    edf = pd.DataFrame(eval_rows)
    print("\n" + "=" * 78)
    print("SUMMARY -- new model (baseline features + 2020-2025 data) vs OLD production baseline")
    print("=" * 78)
    for zone in ZONES:
        sub = edf[edf["zone"] == zone]
        mae_new_overall = (sub["mae_new"] * sub["n_test"]).sum() / sub["n_test"].sum()
        n_test_total = sub["n_test"].sum()
        change = (mae_new_overall / BASELINE_MAE_OLD[zone] - 1) * 100
        print(f"{zone}: old baseline MAE={BASELINE_MAE_OLD[zone]:>10,.0f}   "
              f"new MAE={mae_new_overall:>10,.0f}   change={change:+.1f}%   "
              f"(n_test รวม={n_test_total}, ตัว train เฉลี่ย={sub['n_train'].mean():.0f} แถว/horizon)")

    print("\nSaved: catboost_models_2025.pkl, lightgbm_models_2025.pkl, stack_weights_2025.pkl "
          "(ไฟล์แยกจาก production เดิม ยังไม่ deploy)")


if __name__ == "__main__":
    main()
