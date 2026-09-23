"""
train_stage2_kc_plus_2025.py
=============================
2026-09-23 -- ข้อ 5+6 รวมกัน: retrain CatBoost+LightGBM stage2 ทั้ง 24 ชุด
ด้วย feature set เดิม + kc_target_h{h} (จาก add_kc_target_features.py เวอร์ชัน
ล่าสุดที่ regenerate ครอบคลุมถึงปี 2025 แล้ว) บน ml_features_phase4.csv ที่มี
ข้อมูลปี 2025 รวมอยู่แล้ว (จาก merge_2025_backfill.py)

Protocol: ใช้ protocol ที่แก้ leakage แล้ว (เหมือน train_stage2_extended_window.py
ฉบับตรวจสอบ apples-to-apples ล่าสุด) -- TRAIN/CALIB/TEST เป็นปีที่ไม่ซ้อนกันเลย:
  TRAIN_YEARS       = [2020, 2021, 2022]   (เท่าของเดิม -- ไม่ขยาย เพราะพิสูจน์
                       แล้วว่าขยาย TRAIN ไปปี 2023 ไม่ได้ช่วยอะไร (มีแต่แย่ลง
                       นิดหน่อยตอนลองแยกอิทธิพล) -- รอบนี้แยกเฉพาะอิทธิพลของ
                       Kc feature ล้วนๆ)
  WEIGHT_CALIB_YEAR = 2023  (เหมือนเดิม)
  TEST_YEARS        = [2024]  (เฉพาะปี 2024 ล้วนๆ -- ไม่ปนปี 2023 แบบ protocol
                       เดิมที่มีปัญหา calib/test ปีซ้อนกัน)

เทียบกับ baseline ที่ผ่านการตรวจ apples-to-apples แล้วจริงๆ บน TEST=[2024] เดียวกันเป๊ะ:
  zone_A = 69,651   zone_B = 23,054   (n_test=612 ทั้งคู่)

Output (ยังไม่ deploy ทับ production เอง):
  catboost_models_kc2025.pkl, lightgbm_models_kc2025.pkl, stack_weights_kc2025.pkl
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
TEST_YEARS = [2024]

# baseline apples-to-apples จริง (TRAIN=2020-22, CALIB=2023, TEST=2024 เท่านั้น, ไม่มี Kc)
BASELINE_MAE_A2A = {"zone_A": 69651, "zone_B": 23054}


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
    print(f"โหลด ml_features_phase4.csv+kc: {df.shape[0]} แถว, ปี {sorted(df['year'].unique())}")
    print(f"TRAIN={TRAIN_YEARS}  CALIB={WEIGHT_CALIB_YEAR}  TEST={TEST_YEARS}\n")

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
                "n_test": len(y_test), "n_train": len(y_train),
            })
            print(f"{zone} h{h:2d}: n_train={len(y_train):>4d}  n_test={len(y_test):>3d}  "
                  f"MAE_new={mae_new:>10,.0f}  RMSE_new={rmse_new:>10,.0f}  "
                  f"w_cat={w_cat:.2f} w_lgb={w_lgb:.2f}")

    joblib.dump(cat_models, ACTIVE_DIR / "catboost_models_kc2025.pkl")
    joblib.dump(lgb_models, ACTIVE_DIR / "lightgbm_models_kc2025.pkl")
    joblib.dump(weights, ACTIVE_DIR / "stack_weights_kc2025.pkl")

    edf = pd.DataFrame(eval_rows)
    print("\n" + "=" * 90)
    print("SUMMARY -- Kc feature model (TRAIN 2020-22, CALIB 2023, TEST 2024) vs apples-to-apples baseline")
    print("=" * 90)
    for zone in ZONES:
        sub = edf[edf["zone"] == zone]
        mae_new_overall = (sub["mae_new"] * sub["n_test"]).sum() / sub["n_test"].sum()
        n_test_total = sub["n_test"].sum()
        change = (mae_new_overall / BASELINE_MAE_A2A[zone] - 1) * 100
        print(f"{zone}: baseline(a2a) MAE={BASELINE_MAE_A2A[zone]:>10,.0f}   "
              f"new(Kc) MAE={mae_new_overall:>10,.0f}   change={change:+.1f}%   (n_test={n_test_total})")

    print("\nSaved: catboost_models_kc2025.pkl, lightgbm_models_kc2025.pkl, stack_weights_kc2025.pkl "
          "(ไฟล์แยกจาก production เดิม ยังไม่ deploy)")


if __name__ == "__main__":
    main()
