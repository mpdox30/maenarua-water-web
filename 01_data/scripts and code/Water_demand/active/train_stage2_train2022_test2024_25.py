"""
train_stage2_train2022_test2024_25.py
=======================================
2026-09-23 -- ทดลองตามคำขอ: TRAIN=[2020,2021,2022], CALIB=2023,
TEST=[2024,2025] รวมกัน (ปีทั้งสามชุดแยกจากกันสนิท ไม่ overlap)

เทรน 2 โมเดลด้วย protocol เดียวกันทุกประการ (ต่างกันแค่มี/ไม่มี kc_target_h{h}
feature) เพื่อเทียบ apples-to-apples ตรงๆในรอบเดียว:
  1) baseline  -- feature set เดิมของ production (ไม่มี Kc)
  2) +Kc       -- เพิ่ม kc_target_h{h} ต่อ horizon (จาก kc_target_features.csv)

Output (ไฟล์อ้างอิง ยังไม่ deploy):
  catboost/lightgbm/stack_weights_train22test2425_{baseline,kc}.pkl
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
TEST_YEARS = [2024, 2025]


def get_regressor_features(df, df_zone, extra_cols=None):
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    feats = [c for c in cols if not df_zone[c].isna().all()]
    if extra_cols:
        feats = feats + extra_cols
    return feats


def inverse_mae_weights(mae_cat, mae_lgb):
    w_cat = (1 / mae_cat) / (1 / mae_cat + 1 / mae_lgb)
    w_lgb = 1 - w_cat
    return round(w_cat, 4), round(w_lgb, 4)


def train_one(df, kc_df, use_kc: bool, tag: str):
    cat_models, lgb_models, weights = {}, {}, {}
    eval_rows = []

    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        if use_kc:
            df_zone = df_zone.merge(
                kc_df[kc_df["zone"] == zone], on=["zone", "year", "week"], how="left"
            )

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"
            extra = [f"kc_target_h{h}"] if use_kc else None
            reg_feats = get_regressor_features(df, df_zone, extra_cols=extra)

            train_df = df_zone[df_zone["year"].isin(TRAIN_YEARS)].dropna(subset=reg_feats + [target_h])
            calib_df = df_zone[df_zone["year"] == WEIGHT_CALIB_YEAR].dropna(subset=reg_feats + [target_h])
            test_df = df_zone[df_zone["year"].isin(TEST_YEARS)].dropna(subset=reg_feats + [target_h])

            X_train, y_train = train_df[reg_feats].values, train_df[target_h].values
            X_calib, y_calib = calib_df[reg_feats].values, calib_df[target_h].values
            X_test, y_test = test_df[reg_feats].values, test_df[target_h].values

            if len(X_train) == 0 or len(X_test) == 0:
                print(f"[skip] {tag} {zone} h{h}: n_train={len(X_train)} n_test={len(X_test)}")
                continue

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
            else:
                w_cat, w_lgb = 0.5, 0.5

            key = (zone, h)
            cat_models[key] = cat_m
            lgb_models[key] = lgb_m
            weights[key] = {"w_cat": w_cat, "w_lgb": w_lgb}

            pred = w_cat * cat_m.predict(X_test) + w_lgb * lgb_m.predict(X_test)
            pred = np.maximum(pred, 0)
            mae_new = np.mean(np.abs(pred - y_test))
            rmse_new = np.sqrt(np.mean((pred - y_test) ** 2))
            eval_rows.append({
                "zone": zone, "h": h, "mae": mae_new, "rmse": rmse_new,
                "n_test": len(y_test), "n_train": len(y_train), "n_calib": len(X_calib),
            })
            print(f"[{tag}] {zone} h{h:2d}: n_train={len(y_train):>4d} n_calib={len(X_calib):>3d} n_test={len(y_test):>3d}  "
                  f"MAE={mae_new:>10,.0f}  RMSE={rmse_new:>10,.0f}  w_cat={w_cat:.2f} w_lgb={w_lgb:.2f}")

    joblib.dump(cat_models, ACTIVE_DIR / f"catboost_models_train22test2425_{tag}.pkl")
    joblib.dump(lgb_models, ACTIVE_DIR / f"lightgbm_models_train22test2425_{tag}.pkl")
    joblib.dump(weights, ACTIVE_DIR / f"stack_weights_train22test2425_{tag}.pkl")

    return pd.DataFrame(eval_rows)


def main():
    df = pd.read_csv(ACTIVE_DIR / "ml_features_phase4.csv")
    kc_df = pd.read_csv(ACTIVE_DIR / "kc_target_features.csv")
    print(f"โหลด ml_features_phase4.csv: {df.shape[0]} แถว, ปี {sorted(df['year'].unique())}")
    print(f"TRAIN_YEARS={TRAIN_YEARS}  CALIB={WEIGHT_CALIB_YEAR}  TEST_YEARS={TEST_YEARS}\n")

    edf_base = train_one(df, kc_df, use_kc=False, tag="baseline")
    print()
    edf_kc = train_one(df, kc_df, use_kc=True, tag="kc")

    print("\n" + "=" * 90)
    print("SUMMARY -- TRAIN=2020-2022, CALIB=2023, TEST=2024+2025 -- baseline vs +Kc (apples-to-apples)")
    print("=" * 90)
    for zone in ZONES:
        b = edf_base[edf_base["zone"] == zone]
        k = edf_kc[edf_kc["zone"] == zone]
        common_h = sorted(set(b["h"]) & set(k["h"]))
        b2 = b[b["h"].isin(common_h)]
        k2 = k[k["h"].isin(common_h)]
        mae_b = (b2["mae"] * b2["n_test"]).sum() / b2["n_test"].sum()
        mae_k = (k2["mae"] * k2["n_test"]).sum() / k2["n_test"].sum()
        n_test_b = b2["n_test"].sum()
        n_test_k = k2["n_test"].sum()
        same_n = "n_test เท่ากันทุก horizon: " + ("ใช่" if (b2.set_index("h")["n_test"] == k2.set_index("h")["n_test"]).all() else "ไม่ -- ระวัง!")
        change = (mae_k / mae_b - 1) * 100
        print(f"{zone}: baseline MAE={mae_b:>10,.0f} (n={n_test_b})   +Kc MAE={mae_k:>10,.0f} (n={n_test_k})   "
              f"change={change:+.1f}%   {same_n}")

    # แยกดูตามปีด้วย (2024 vs 2025 อาจให้ภาพต่างกัน)
    print("\n--- แยกตามปี (เพื่อดูว่าผลรวมถูกปีไหนดึง) ---")
    for zone in ZONES:
        for yr_label, yr_val in [("2024", 2024), ("2025", 2025)]:
            b = edf_base[edf_base["zone"] == zone]
            k = edf_kc[edf_kc["zone"] == zone]
            print(f"  ({zone}, TEST รวม 2024+2025 -- ตัวเลขนี้คือรวม ไม่ได้แยกจริง เพราะ eval ทำรวมปีในลูปเดียว)")
            break
        break
    print("  หมายเหตุ: MAE ด้านบนคำนวณจาก TEST_YEARS=[2024,2025] รวมกันในการ dropna/predict ครั้งเดียว")
    print("  ถ้าต้องการแยก MAE ปี 2024 vs 2025 ต่างหาก แจ้งเพิ่มได้")

    print("\nSaved: catboost/lightgbm/stack_weights_train22test2425_{baseline,kc}.pkl (ไฟล์อ้างอิง ยังไม่ deploy)")


if __name__ == "__main__":
    main()
