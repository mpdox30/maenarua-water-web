"""
train_stage2_extended_window.py
================================
2026-09-23 -- ข้อ 6 ส่วนที่ 3: ทดลองใช้ประโยชน์จากข้อมูลปี 2025 แบบ "ขยายปีที่ train
จริง" ไม่ใช่แค่แก้ evaluation ให้ครบ (train_stage2_baseline_2025.py ทำไปแล้ว
พบว่า -3.9%/-4.4% ที่ได้เป็นผลจาก test set ครบขึ้น ไม่ใช่โมเดลเก่งขึ้นจริง)

Protocol ใหม่ (เลื่อนหน้าต่างไปข้างหน้า 1 ปี เทียบกับเดิม):
  TRAIN_YEARS       = [2020, 2021, 2022, 2023]   (เพิ่มปี 2023 เข้า train ได้
                       จริง เพราะตอนนี้ label ของช่วงรอยต่อ 2023->2024 สมบูรณ์
                       แล้วจากการ merge 2025 -- เดิม 2023 ก็ label ครบอยู่แล้ว
                       จริงๆ (อยู่กลางช่วง 2020-2024) แต่เดิมถูกกันไว้ทำ
                       WEIGHT_CALIB_YEAR เท่านั้น ไม่เคย train ด้วย)
  WEIGHT_CALIB_YEAR = 2025 (partial year, 51 สัปดาห์)  <-- จุดสำคัญ: ใช้ปี 2025
                       เป็น calibration set แทนที่จะใช้ปีเดียวกับ TEST ซ้ำ
                       (protocol เดิมมีจุดอ่อนแอบแฝง: WEIGHT_CALIB_YEAR=2023
                       ซ้อนทับกับ TEST_YEARS=[2023,2024] -- แปลว่า inverse-MAE
                       stack weight ถูก fit บนข้อมูลปีเดียวกับที่เอาไป "ทดสอบ"
                       บางส่วน เป็นการรั่วไหลเล็กน้อย (leakage) -- รอบนี้แก้ให้
                       CALIB/TRAIN/TEST เป็นปีที่ไม่ซ้อนกันเลยทั้ง 3 ชุด)
  TEST_YEARS        = [2024]   (out-of-sample ล้วนๆ ไม่ถูกใช้ทั้ง train และ calib)

Hyperparameters เดิมทุกตัว, ไม่มี kc_target feature (เก็บไว้ตามที่ตัดสินใจ)

Output (ยังไม่ deploy ทับ production เอง):
  catboost_models_extwin.pkl, lightgbm_models_extwin.pkl, stack_weights_extwin.pkl
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
TRAIN_YEARS = [2020, 2021, 2022, 2023]
WEIGHT_CALIB_YEAR = 2025
TEST_YEARS = [2024]

# baseline เดิม (protocol เดิม: TRAIN=[2020-22], CALIB=2023, TEST=[2023,2024])
BASELINE_MAE_OLD = {"zone_A": 79135, "zone_B": 26466}
# ผลจาก train_stage2_baseline_2025.py (protocol เดิมเป๊ะ แต่ TEST set ครบขึ้นจาก 2025 merge)
BASELINE_MAE_COMPLETED_TEST = {"zone_A": 76047, "zone_B": 25296}


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
    print(f"TRAIN={TRAIN_YEARS}  CALIB={WEIGHT_CALIB_YEAR}  TEST={TEST_YEARS}  (ไม่ซ้อนกันเลยทั้ง 3 ชุด)\n")

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

            if len(X_calib) == 0:
                print(f"[WARN] {zone} h{h}: calib set ว่าง (ปี {WEIGHT_CALIB_YEAR} ไม่มีแถวที่ label ครบสำหรับ horizon นี้) -- ใช้ weight 0.5/0.5")
                w_cat, w_lgb = 0.5, 0.5
            else:
                pass

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

            if len(X_calib) > 0:
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
                "n_test": len(y_test), "n_train": len(y_train), "n_calib": len(X_calib),
            })
            print(f"{zone} h{h:2d}: n_train={len(y_train):>4d}  n_calib={len(X_calib):>3d}  n_test={len(y_test):>3d}  "
                  f"MAE_new={mae_new:>10,.0f}  RMSE_new={rmse_new:>10,.0f}  "
                  f"w_cat={w_cat:.2f} w_lgb={w_lgb:.2f}")

    joblib.dump(cat_models, ACTIVE_DIR / "catboost_models_extwin.pkl")
    joblib.dump(lgb_models, ACTIVE_DIR / "lightgbm_models_extwin.pkl")
    joblib.dump(weights, ACTIVE_DIR / "stack_weights_extwin.pkl")

    edf = pd.DataFrame(eval_rows)
    print("\n" + "=" * 90)
    print("SUMMARY -- extended-window model (TRAIN 2020-2023, CALIB 2025, TEST 2024) vs baselines")
    print("=" * 90)
    for zone in ZONES:
        sub = edf[edf["zone"] == zone]
        mae_new_overall = (sub["mae_new"] * sub["n_test"]).sum() / sub["n_test"].sum()
        n_test_total = sub["n_test"].sum()
        chg_orig = (mae_new_overall / BASELINE_MAE_OLD[zone] - 1) * 100
        chg_completed = (mae_new_overall / BASELINE_MAE_COMPLETED_TEST[zone] - 1) * 100
        print(f"{zone}:")
        print(f"  vs protocol เดิม (2020-2024 data)         : {BASELINE_MAE_OLD[zone]:>10,.0f} -> {mae_new_overall:>10,.0f}  ({chg_orig:+.1f}%)")
        print(f"  vs protocol เดิม+test ครบ (2020-2025 data) : {BASELINE_MAE_COMPLETED_TEST[zone]:>10,.0f} -> {mae_new_overall:>10,.0f}  ({chg_completed:+.1f}%)")
        print(f"  (n_test={n_test_total}, n_train เฉลี่ย={sub['n_train'].mean():.0f}, n_calib เฉลี่ย={sub['n_calib'].mean():.0f})")

    print("\nหมายเหตุ: TEST_YEARS=[2024] รอบนี้ไม่ใช่ชุดเดียวกับ TEST=[2023,2024] ของ baseline เดิม")
    print("เทียบ MAE ข้าม test-set ที่ไม่เหมือนกันเป๊ะได้แค่ระดับ 'แนวโน้ม' ไม่ใช่ apples-to-apples 100%")
    print("\nSaved: catboost_models_extwin.pkl, lightgbm_models_extwin.pkl, stack_weights_extwin.pkl "
          "(ไฟล์แยกจาก production เดิม ยังไม่ deploy)")


if __name__ == "__main__":
    main()
