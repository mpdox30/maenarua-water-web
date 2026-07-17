# Feature Schema — Water Demand Forecasting (Zone A/B)

เอกสารนี้สรุปจากการอ่านโค้ดจริงในไฟล์
`01_data/scripts and code/Water_demand/archive/combined_final_pipeline.py` (6,502 บรรทัด)
โดยคัดลอก logic การคำนวณ feature ต่างๆ มาแบบคำต่อคำ (verbatim) ไม่ตีความหรือย่อ
เพื่อให้ตรวจสอบความถูกต้องได้ก่อนนำไป implement ใน `pipeline/data_pipeline.py`

**หมายเหตุสำคัญเรื่องไฟล์ต้นทาง:** ไฟล์ `combined_final_pipeline.py` เป็นการรวม cell จาก
notebook หลายไฟล์/หลายรอบมาต่อกัน จึงมีการ `def get_feature_cols(...)` ซ้ำ 7 ครั้ง และ
`CLASSIFIER_FEATURES = [...]` ซ้ำ 4 ครั้ง (บรรทัด 2781, 2878, 3057, 3317, 3587, 3746, 3902
สำหรับ `get_feature_cols`, และ 4106, 4374, 5267, 5566 สำหรับ `CLASSIFIER_FEATURES`) — ทุกเวอร์ชัน
มี exclude-set และรายชื่อ feature **เหมือนกันทุกตัวอักษร** ไม่มีความขัดแย้งกัน เอกสารนี้อ้างอิง
เวอร์ชันสุดท้ายที่ใช้จริงใน production flow (Step 3e — two-stage combination, บรรทัด 4382–4532)
เป็นหลัก

---

## 1. รายชื่อโมเดลทั้งหมดและไฟล์ .pkl ที่เกี่ยวข้อง

| โมเดล | ไฟล์ | ใช้ทำอะไร |
|---|---|---|
| RF crop classifier (v3b) | `rf_model_v3b_final.pkl` + `rf_scaler_v3b_final.pkl` + `col_medians_v3b_final.pkl` | จำแนกชนิดพืชรายพิกเซลจากภาพ Sentinel-2 (dry season composite) + Sentinel-1 SAR (dry+wet weekly) — **ไม่ใช่โมเดลพยากรณ์ demand โดยตรง** เป็นโมเดลที่อยู่ *ต้นน้ำ* ของ pipeline (Phase 1) ใช้สร้าง crop map เพื่อคำนวณพื้นที่ปลูกพืชต่อ zone |
| Stage-1 classifier | `stage1_classifiers.pkl` + `stage1_thresholds.pkl` | LGBMClassifier ต่อ (zone, horizon) — ทำนายว่า demand ของสัปดาห์นั้นจะ > 0 หรือไม่ (regime detection) |
| Stage-2 regressor (CatBoost) | `catboost_models.pkl` | CatBoostRegressor ต่อ (zone, horizon) — ทำนาย magnitude ของ demand |
| Stage-2 regressor (LightGBM) | `lightgbm_models.pkl` | LGBMRegressor ต่อ (zone, horizon) — ทำนาย magnitude ของ demand (คู่ขนานกับ CatBoost) |
| Stacking weights | `stack_weights.pkl` | น้ำหนัก inverse-MAE ต่อ (zone, horizon) สำหรับรวม CatBoost + LightGBM |

**สำคัญ:** ไม่มีไฟล์โมเดล CatBoost/LightGBM สำหรับ **Reservoir Inflow** เก็บไว้ใน repo นี้เลย
(ตรวจสอบแล้วในงานก่อนหน้า) — โมเดล inflow ต้อง retrain ใหม่จาก
`01_data/scripts and code/Reservoir_inflow/active/inflow_forecasting_MULTIMODEL_stratified_split3.ipynb`
เอกสารนี้ครอบคลุมเฉพาะฝั่ง Water Demand เท่านั้นตามที่ไฟล์ต้นทางที่ขอให้อ่านระบุ

---

## 2. Target variable: NIR_A_m3 / GIR_B_m3 (ที่มาของ demand ดิบ)

ก่อนจะเข้าสู่ feature engineering, ต้องเข้าใจว่า target ที่โมเดลพยากรณ์ (`NIR_A_m3`, `GIR_B_m3`)
มาจากการคำนวณ (ไม่ใช่ข้อมูลวัดจริง) ด้วยสูตร FAO-56 Kc-ETo-Peff copy มาจากบรรทัด 2356–2418:

```python
for _, row in climate.iterrows():
    yr      = int(row['year'])
    wk      = int(row['week'])
    et0     = float(row['ET0_mm_week'])
    p_eff_a = float(row['P_eff_upland'])  # Zone A = rainfed → upland P_eff
    p_eff_b = float(row['P_eff_paddy'])   # Zone B = irrigated (rice-dominant)

    # --- Zone A: NIR (Net Irrigation Requirement) ---
    nir_a_total = 0.0
    etc_a_total = 0.0   # ETc = crop evapotranspiration (FAO-56 term) — ไม่เกี่ยวกับ crop class 'etc'
    for crop, area_m2 in AREA_ZONE_A.items():
        if area_m2 == 0:
            continue

        # (แก้ไข 2026-07-08) crop class 'etc' จาก RF classifier (v3b) เป็น catch-all ที่รวม
        # ยางพารา/ปาล์ม/พืชอื่นนอกเป้าหมาย — ไม่มี entry ตรงกันใน kc_weekly_lookup_all_crops.csv
        # เลย (Kc table มีแค่ rice/corn/cassava/longan/rubber ไม่มี 'etc') เดิมโค้ดปล่อยให้
        # lookup หาไม่เจอแล้ว fallback เป็น Kc=0 แบบเงียบๆ — เปลี่ยนเป็น explicit skip พร้อม log
        # เพื่อให้เห็นชัดว่าเป็นการออกแบบตั้งใจ ไม่ใช่บั๊ก/lookup miss โดยไม่ได้ตรวจสอบ
        if crop == 'etc':
            log.info(
                "Zone A: %.2f ha เป็น class 'etc' — ไม่คำนวณ water demand ตามการออกแบบ "
                "(ไม่ใช่พืชเป้าหมาย)", area_m2 / 10000,
            )
            continue  # ข้าม area นี้ไปเลย ไม่รวมเข้า NIR_A_m3

        # หา Kc สำหรับ crop นี้ที่ week นี้
        if 'year' in merge_keys:
            kc_val = kc_lookup[(kc_lookup['year']==yr) &
                               (kc_lookup['week']==wk) &
                               (kc_lookup['crop']==crop)]['Kc']
        else:
            kc_val = kc_lookup[(kc_lookup['week']==wk) &
                               (kc_lookup['crop']==crop)]['Kc']

        kc_val = float(kc_val.values[0]) if len(kc_val) > 0 else 0.0
        etc_mm = kc_val * et0                          # mm/week
        nir_mm = max(0.0, etc_mm - p_eff_a)            # mm/week
        nir_a_total += nir_mm * area_m2 / 1000         # m³/week
        etc_a_total += etc_mm * area_m2 / 1000

    # --- Zone B: GIR (Gross Irrigation Requirement) ---
    gir_b_total = 0.0
    etc_b_total = 0.0
    for crop, area_m2 in AREA_ZONE_B.items():
        if area_m2 == 0:
            continue

        # (แก้ไข 2026-07-08) เหตุผลเดียวกับ Zone A ด้านบน — ดูคอมเมนต์ที่นั่น
        if crop == 'etc':
            log.info(
                "Zone B: %.2f ha เป็น class 'etc' — ไม่คำนวณ water demand ตามการออกแบบ "
                "(ไม่ใช่พืชเป้าหมาย)", area_m2 / 10000,
            )
            continue  # ข้าม area นี้ไปเลย ไม่รวมเข้า GIR_B_m3

        if 'year' in merge_keys:
            kc_val = kc_lookup[(kc_lookup['year']==yr) &
                               (kc_lookup['week']==wk) &
                               (kc_lookup['crop']==crop)]['Kc']
        else:
            kc_val = kc_lookup[(kc_lookup['week']==wk) &
                               (kc_lookup['crop']==crop)]['Kc']

        kc_val = float(kc_val.values[0]) if len(kc_val) > 0 else 0.0
        etc_mm  = kc_val * et0
        nir_mm  = max(0.0, etc_mm - p_eff_b)
        gir_mm  = nir_mm / IE                          # หาร IE
        gir_b_total += gir_mm * area_m2 / 1000
        etc_b_total += etc_mm * area_m2 / 1000
```

โดยที่ `IE = 0.90` (Irrigation efficiency, FAO-56 surface irrigation, บรรทัด 2310 —
ปรับจากค่าเดิม 0.75 เป็น 0.90)

**หมายเหตุการแก้ไข 2026-07-08 — crop class `'etc'` ไม่ถูกนับเข้า NIR/GIR โดยตั้งใจ:**
class `'etc'` จาก RF classifier (v3b, catch-all ที่รวมยางพารา/ปาล์มน้ำมัน/ยาสูบ/มะขาม/พืชอื่นนอกเป้าหมาย
— ดูการ map ชื่อพืชจริงใน `Training Data.ipynb`) ไม่ถูกนับเข้าการคำนวณ NIR/GIR เพราะไม่ใช่พืชที่ต้อง
บริหารจัดการน้ำในระบบนี้ (ระบบออกแบบมาสำหรับ rice/corn/cassava/longan เท่านั้น ตรงกับ
`kc_weekly_lookup_all_crops.csv` ที่มี Kc เฉพาะ 4 พืชนี้ + rubber แยกต่างหาก — ไม่มี Kc สำหรับ `'etc'`)
พื้นที่ 156.68 ha (Zone A) + 57.88 ha (Zone B) จะ**ไม่ปรากฏ**ใน water demand forecast เลย ไม่ใช่บั๊ก
แต่เป็นขอบเขตของระบบที่ตั้งใจไว้ — ถ้าต้องการรวมยางพาราเข้ามาในอนาคต ควร map พื้นที่ class `'etc'`
ไปเป็น crop `'rubber'` แทน (มี Kc จริงอยู่แล้วใน `KC_FAO56['rubber']` ของ `combined_final_pipeline.py`
บรรทัด 917-921: GS_defoliation=0.60, GS_leaf_flush=0.80, GS_mature=1.00) ไม่ใช่ปล่อยให้ตรงกับ `'etc'`
ที่ไม่มี Kc นิยามไว้เลย

**⚠️ พื้นที่ปลูกพืชต่อ zone เป็นค่าคงที่ hardcode จากปี 2020 ไม่ใช่ค่าที่อัปเดตอัตโนมัติ**
copy มาจากบรรทัด 2294–2308:

```python
# crop area จาก Step 12 (m²) — แทนด้วยค่าจริง
AREA_ZONE_A = {
    'rice'   : 1510.72 * 10000,
    'corn'   : 621.36  * 10000,
    'longan' : 461.36  * 10000,
    'cassava': 0.16    * 10000,
    'etc'    : 156.68  * 10000,
}
AREA_ZONE_B = {
    'rice'   : 282.88  * 10000,
    'corn'   : 215.52  * 10000,
    'longan' : 170.64  * 10000,
    'cassava': 0.32    * 10000,
    'etc'    : 57.88   * 10000,
}
```

ค่าพื้นที่เหล่านี้ได้มาจากการรัน RF crop classifier (v3b) บนภาพปี 2020 เท่านั้น
(`crop_map_v3b_2020.tif` → `extract_crop_area()` → `crop_area_per_zone.csv`) แล้ว **hardcode**
กลับเข้ามาเป็นตัวเลขในสคริปต์ตัวถัดไป **ไม่มี logic ใดที่เชื่อมผลลัพธ์ crop classification
ใหม่ (จาก SAR image ใหม่ตาม Step 2 ของ pipeline) กลับเข้ามาอัปเดต `AREA_ZONE_A`/`AREA_ZONE_B`
โดยอัตโนมัติ** — นี่คือช่องว่างสำคัญที่ต้อง implement เพิ่มถ้าต้องการให้ `trigger_crop_classification()`
ใน `data_pipeline.py` ส่งผลไปถึง `NIR_A_m3`/`GIR_B_m3` จริง มิฉะนั้นพื้นที่พืชจะค้างอยู่ที่ปี 2020 ตลอดไป

---

## 3. Feature engineering หลัก (lag / rolling / seasonality)

Copy มาจากบรรทัด 2591–2728 (`build_feature_matrix()`):

```python
HORIZON      = 12
LAG_WINDOWS  = [1, 2, 3, 4, 8, 12]
ROLL_WINDOWS = [4, 8]

ZONE_CONFIG = {
    "zone_A": {"target": "NIR_A_m3",  "p_eff_col": "P_eff_upland"},
    "zone_B": {"target": "GIR_B_m3",  "p_eff_col": "P_eff_paddy"},
}


def add_lag_features(df, col, lags):
    for lag in lags:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_rolling_features(df, col, windows):
    for w in windows:
        df[f"{col}_roll{w}_mean"] = df[col].shift(1).rolling(w).mean()
        df[f"{col}_roll{w}_std"]  = df[col].shift(1).rolling(w).std()
    return df


def build_feature_matrix():

    # ── Load ──────────────────────────────────────────────────────────────
    demand  = pd.read_csv("water_demand_weekly_dual_zone.csv")
    climate = pd.read_csv("climate_weekly_phayao_2020_2024.csv")
    mei     = pd.read_csv("mei_monthly.csv")

    # ── Date + month ──────────────────────────────────────────────────────
    demand["date"] = pd.to_datetime(
        demand["year"].astype(str) + "-W" +
        demand["week"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u"
    )
    demand["month"] = demand["date"].dt.month

    # ── Merge climate (drop duplicate columns already in demand) ──────────
    overlap = [c for c in climate.columns
               if c in demand.columns and c not in ["year", "week"]]
    demand_clean = demand.drop(columns=overlap, errors="ignore")

    df = demand_clean.merge(climate, on=["year", "week"], how="left")

    # ── Merge MEI ─────────────────────────────────────────────────────────
    df = df.merge(mei[["year", "month", "MEI"]], on=["year", "month"], how="left")
    df["MEI"] = df["MEI"].interpolate(method="linear").bfill().ffill()

    # ── Seasonality encoding ──────────────────────────────────────────────
    df["WoY_sin"] = np.sin(2 * np.pi * df["week"] / 52)
    df["WoY_cos"] = np.cos(2 * np.pi * df["week"] / 52)
    df["MoY_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["MoY_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # ── Season encode (ถ้ามี column season) ──────────────────────────────
    if "season" in df.columns:
        season_map = {"dry": 0, "wet": 1, "cool": 2,
                      "summer": 0, "rainy": 1, "winter": 2}
        df["season_enc"] = df["season"].map(season_map)
        if df["season_enc"].isna().any():
            df["season_enc"] = pd.factorize(df["season"])[0]

    # ── Per-zone feature matrices ─────────────────────────────────────────
    frames = []

    for zone_label, cfg in ZONE_CONFIG.items():
        target_col = cfg["target"]
        p_eff_col  = cfg["p_eff_col"]

        wanted = [
            "year", "week", "month", "date",
            "ET0_mm_week", "T_mean", "RH_pct", "VPD_kPa", "u2_ms", "Rn_MJ",
            "P_mm_week", p_eff_col,
            "SPI_4", "drought_flag", "AI_week",
            "MEI", "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
            target_col,
        ]
        if "season_enc" in df.columns:
            wanted.append("season_enc")

        cols = [c for c in wanted if c in df.columns]
        z = df[cols].copy().sort_values(["year", "week"]).reset_index(drop=True)

        z = z.rename(columns={p_eff_col: "P_eff_mm"})

        # ── Lag + rolling on target ───────────────────────────────────────
        z = add_lag_features(z, target_col, LAG_WINDOWS)
        z = add_rolling_features(z, target_col, ROLL_WINDOWS)

        # ── Lag on climate drivers ────────────────────────────────────────
        z = add_lag_features(z, "ET0_mm_week", [1, 2, 4])
        z = add_lag_features(z, "P_mm_week",   [1, 2, 4])
        z = add_lag_features(z, "VPD_kPa",     [1, 2])
        z = add_lag_features(z, "MEI",         [4, 8])

        # ── Direct horizon targets ────────────────────────────────────────
        for h in range(1, HORIZON + 1):
            z[f"y_h{h}"] = z[target_col].shift(-h)

        z["zone"]       = zone_label
        z["target_col"] = target_col
        frames.append(z)

    # ── Combine ───────────────────────────────────────────────────────────
    ml = pd.concat(frames, ignore_index=True)
    ml = ml.sort_values(["year", "week", "zone"]).reset_index(drop=True)

    horizon_cols = [f"y_h{h}" for h in range(1, HORIZON + 1)]
    ml = ml.dropna(subset=horizon_cols, how="all")

    ml.to_csv("ml_features_phase4.csv", index=False)
    return ml
```

**หมายเหตุ:** `HORIZON = 12` ในสคริปต์นี้ (ต่างจากที่หน้าเว็บ `inflow-forecast.html` แสดง horizon 1–7
ซึ่งเป็นของ Reservoir Inflow คนละโมเดลกัน — Water Demand พยากรณ์ล่วงหน้า 12 สัปดาห์)

### ที่มาของ climate driver ดิบ

| Column | มาจากไฟล์ | มาจาก source ข้อมูลอะไร |
|---|---|---|
| `ET0_mm_week`, `T_mean`, `RH_pct`, `VPD_kPa`, `u2_ms`, `Rn_MJ` | `ET0_weekly_phayao_2020_2024.csv` | ERA5 reanalysis (ดาวน์โหลดผ่านสคริปต์ `Phase3 step1 era5 download et0.ipynb`) — คำนวณ ET0 ด้วยสูตร Penman-Monteith รายสัปดาห์ |
| `P_mm_week`, `P_eff_paddy`, `P_eff_upland` | `CHIRPS_weekly_phayao_2020_2024.csv` | CHIRPS satellite rainfall estimate (สคริปต์ `Phase3 step2 chirps rainfall.ipynb`) |
| `MEI` | `mei_monthly.csv` | Multivariate ENSO Index รายเดือน (external climate index) — interpolate เป็นรายสัปดาห์ตอน merge |
| `WoY_sin/cos`, `MoY_sin/cos` | คำนวณจาก `week`/`month` โดยตรง | ไม่ต้องพึ่งข้อมูลภายนอก เป็น deterministic calendar encoding |
| `SPI_4`, `drought_flag`, `AI_week` | คำนวณต่อจาก `P_mm_week`/`ET0_mm_week` (ดูหัวข้อ 4) | derived จาก climate ข้างต้น |
| `NIR_A_m3` / `GIR_B_m3` (target, และ input ของ lag/roll) | คำนวณจาก crop area (static 2020) × Kc × ET0/P_eff (ดูหัวข้อ 2) | ผสมระหว่าง RF crop classification (ครั้งเดียว ปี 2020) + climate ปัจจุบัน |

### สูตร SPI-4 / drought_flag / AI_week (copy จากบรรทัด 1876–1901)

```python
# 4.1 Water deficit (mm/week)
climate['deficit_paddy_mm']  = (climate['ET0_mm_week']
                                 - climate['P_eff_paddy']).round(2)
climate['deficit_upland_mm'] = (climate['ET0_mm_week']
                                 - climate['P_eff_upland']).round(2)

# 4.2 Rolling 4-week rainfall
climate['P_4week'] = (climate['P_mm_week']
                      .rolling(4, min_periods=4)
                      .sum())

# 4.3 SPI-4 (z-score ภายใน week เดียวกันข้ามปี)
climate['SPI_4'] = (
    climate.groupby('week')['P_4week']
    .transform(lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0)
    .fillna(0.0)   # ← rolling warmup weeks → 0 (climatological normal)
    .round(3)
)

# 4.4 Drought flag (SPI-4 < -1.0 = moderately dry)
climate['drought_flag'] = (climate['SPI_4'] < -1.0).astype(int)

# 4.5 Aridity Index รายสัปดาห์ (cap ที่ 10 ป้องกัน div-by-zero)
climate['AI_week'] = (
    climate['ET0_mm_week'] / (climate['P_mm_week'] + 0.001)
).clip(upper=10).round(3)
```

**ข้อสังเกต:** `SPI_4` คำนวณด้วย z-score เทียบกับ **สัปดาห์เดียวกันข้ามปีทั้งหมด** (`groupby('week')`)
แปลว่าเวลาคำนวณ SPI_4 ของสัปดาห์ปัจจุบัน (real-time inference) ต้องมีข้อมูล `P_4week` ของสัปดาห์
เดียวกันจากปีก่อนๆ ครบ ไม่ใช่แค่คำนวณจากข้อมูลปีเดียวได้ — ต้องเก็บ climate history ย้อนหลังไว้เสมอ

---

## 4. Feature list ที่โมเดล regressor (CatBoost/LightGBM) ต้องการ

Copy `get_feature_cols` / `get_regressor_features` เวอร์ชันสุดท้าย (บรรทัด 3902–3909 และ
5574–5579 — เหมือนกันทุกตัวอักษร):

```python
def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols
```

กล่าวคือ **feature ของ regressor = ทุก column ใน `ml_features_phase4.csv` ยกเว้น**
`year, week, month, date, zone, target_col, NIR_A_m3, GIR_B_m3, P_4week, y_h1...y_h12`

จากโครงสร้างที่ `build_feature_matrix()` สร้างไว้ (หัวข้อ 3) รายชื่อ feature ที่เหลือจริงคือ
(นับได้ 36 ตัว บวก `season_enc` ถ้ามี column `season` = รวม **37 ตัว** ตรงกับ comment
`"✅ Feature counts verified (all 37)"` ในบรรทัด 3951 ของโค้ดต้นฉบับ):

**Climate/seasonality (16 ตัว, ค่าปัจจุบันของสัปดาห์นั้น ไม่ lag):**
`ET0_mm_week`, `T_mean`, `RH_pct`, `VPD_kPa`, `u2_ms`, `Rn_MJ`,
`P_mm_week`, `P_eff_mm` (=`P_eff_upland` สำหรับ zone_A หรือ `P_eff_paddy` สำหรับ zone_B, rename แล้ว),
`SPI_4`, `drought_flag`, `AI_week`, `MEI`,
`WoY_sin`, `WoY_cos`, `MoY_sin`, `MoY_cos`

**Target lag/rolling (10 ตัว, ของ `NIR_A_m3` หรือ `GIR_B_m3` ตาม zone):**
`{target}_lag1`, `{target}_lag2`, `{target}_lag3`, `{target}_lag4`, `{target}_lag8`, `{target}_lag12`,
`{target}_roll4_mean`, `{target}_roll4_std`, `{target}_roll8_mean`, `{target}_roll8_std`

**Climate driver lag (10 ตัว):**
`ET0_mm_week_lag1`, `ET0_mm_week_lag2`, `ET0_mm_week_lag4`,
`P_mm_week_lag1`, `P_mm_week_lag2`, `P_mm_week_lag4`,
`VPD_kPa_lag1`, `VPD_kPa_lag2`,
`MEI_lag4`, `MEI_lag8`

**Optional (1 ตัว ถ้ามี column `season` ในข้อมูลต้นทาง):**
`season_enc`

รวม = 16 + 10 + 10 (+1 ถ้ามี season_enc) = 36 หรือ 37 ตัว — โมเดล CatBoost/LightGBM ทั้งสองตัว
train ด้วย feature set ชุดเดียวกันนี้ (คนละ zone คนละ horizon มี model instance แยกกัน
เก็บเป็น dict key `(zone, h)` ใน `.pkl`)

---

## 5. Feature list ที่ Stage-1 classifier ต้องการ

Copy `CLASSIFIER_FEATURES` และ `get_clf_features` เวอร์ชันสุดท้าย (บรรทัด 5566–5587):

```python
CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
TARGET_LAGS = [1, 2, 3, 4]


def get_clf_features(df_zone: pd.DataFrame, target_col: str) -> list:
    lag_cols  = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted    = CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]
```

รวม Stage-1 classifier ใช้สูงสุด **17 features**: 11 ตัวจาก `CLASSIFIER_FEATURES`
(seasonality 4 + climate 5 + ENSO 1 + aridity 1) + `{target}_lag1..lag4` (4 ตัว)
+ `{target}_roll4_mean`, `{target}_roll8_mean` (2 ตัว) — เป็น **subset** ของ feature ที่ regressor ใช้
(ไม่มี `T_mean`, `RH_pct`, `u2_ms`, `Rn_MJ`, ไม่มี lag8/lag12 ของ target, ไม่มี roll_std,
ไม่มี lag ของ climate driver ตัวอื่นนอกจาก target)

Comment ในโค้ดต้นฉบับ (บรรทัด 4103–4105) อธิบายเหตุผลการเลือก subset นี้:

```python
# ── Classifier feature set (subset ที่เหมาะกับ regime detection) ─────────────
# ใช้ seasonality + recent demand pattern + drought indicators
# ไม่ใช้ rolling std หรือ climate lag ที่ noisy เกินไป
```

---

## 6. Feature ที่ RF crop classifier (v3b) ต้องการ (คนละชุดกับด้านบนทั้งหมด)

RF classifier **ไม่ได้ใช้ feature แบบตาราง (tabular)** เหมือนโมเดล demand — มันทำนายจาก
ค่าพิกเซลของภาพถ่ายดาวเทียมโดยตรง copy จากบรรทัด 387–413:

```python
N_FEAT  = 6
dry_vv  = [w*N_FEAT+0 for w in range(16)]
dry_vh  = [w*N_FEAT+1 for w in range(16)]
wet_vv  = [w*N_FEAT+0 for w in range(16, 36)]
wet_vh  = [w*N_FEAT+1 for w in range(16, 36)]

s2      = extract('S2_drySeason_composite_2022.tif', all_coords, 'S2')
s1_dry  = extract('S1_fullYear_weekly_2022.tif', all_coords, 'S1d',
                   band_idx=dry_vv+dry_vh)
s1_wet  = extract('S1_fullYear_weekly_2022.tif', all_coords, 'S1w',
                   band_idx=wet_vv+wet_vh)

s2_cols  = s2.columns.tolist()
s1d_cols = s1_dry.columns.tolist()
s1w_cols = s1_wet.columns.tolist()
all_cols = s2_cols + s1d_cols + s1w_cols

X_raw   = pd.concat([s2, s1_dry, s1_wet], axis=1)
medians = X_raw.median()
X       = X_raw.fillna(medians).fillna(0)
```

Input ดิบ: แถบ (band) ของ Sentinel-2 dry-season composite (`S2_*`) + Sentinel-1 SAR
รายสัปดาห์ทั้งฤดูแล้ง (`S1d_*`, สัปดาห์ 1–16) และฤดูฝน (`S1w_*`, สัปดาห์ 17–36)
ค่า missing ถูกเติมด้วย median ของแต่ละ band (เก็บไว้ใน `col_medians_v3b_final.pkl`)
ก่อน scale ด้วย `MinMaxScaler` (เก็บไว้ใน `rf_scaler_v3b_final.pkl`) แล้วจึงเข้าโมเดล

ผลลัพธ์การจำแนก (`crop_map_v3b_{year}.tif`) ถูกนำไป mask ด้วยขอบเขต zone A/B แล้วนับพื้นที่
เป็น `crop_area_per_zone.csv` → hardcode กลับเป็น `AREA_ZONE_A`/`AREA_ZONE_B` (ดูหัวข้อ 2)
**นี่คือจุดเชื่อมต่อเดียวระหว่าง RF crop classifier กับโมเดล demand — ปัจจุบันเป็นการเชื่อมต่อ
แบบ manual/one-time ไม่ใช่ automated pipeline**

---

## 7. ลำดับขั้นตอน Two-stage (Stage1 classifier → Stage2 regression)

Copy สูตรรวมผลสุดท้ายจากบรรทัด 4335–4348 และ 4441–4465:

```
prob      = P(demand > 0)               ← จาก Stage 1 classifier
magnitude = ŷ_cat*w_cat + ŷ_lgb*w_lgb   ← Stage 2 stack (CatBoost + LightGBM ถ่วงน้ำหนัก)
ŷ_final   = prob × magnitude
```

โค้ดจริง (บรรทัด 4441–4456):

```python
X_reg = valid[reg_feats].values
X_clf = valid[clf_feats].values
y_obs = valid[target_h].values

# Stage 1: probability of demand > 0
clf   = classifiers[(zone, h)]
prob  = clf.predict_proba(X_clf)[:, 1]

# Stage 2: magnitude
w     = weights[(zone, h)]
mag   = (w["w_cat"] * cat_models[(zone,h)].predict(X_reg) +
         w["w_lgb"] * lgb_models[(zone,h)].predict(X_reg))
mag   = np.maximum(mag, 0)

# Final: soft combination
y_hat = prob * mag
```

**น้ำหนัก stacking** (`w_cat`, `w_lgb`) คำนวณจาก inverse-MAE บน calibration set (ปี 2023)
copy จากบรรทัด 3912–3916:

```python
def inverse_mae_weights(mae_cat: float, mae_lgb: float) -> tuple:
    """คำนวณน้ำหนัก inverse-MAE ที่รวมกันได้ 1."""
    w_cat = (1 / mae_cat) / (1 / mae_cat + 1 / mae_lgb)
    w_lgb = 1 - w_cat
    return round(w_cat, 4), round(w_lgb, 4)
```

น้ำหนักเหล่านี้คำนวณไว้ล่วงหน้าตอน train (เก็บใน `stack_weights.pkl`) ไม่ต้องคำนวณใหม่ตอน inference
— ตอน inference จริงแค่โหลด `stack_weights.pkl` มาใช้ตรงๆ

**เหตุผลของการออกแบบ two-stage** (comment ต้นฉบับ บรรทัด 4345–4348):

```
ข้อดีของ soft combination (prob × magnitude) เทียบกับ hard threshold:
  - Conformal prediction intervals จะสะท้อน regime uncertainty ด้วย
  - ไม่มี discontinuity ที่ threshold → smooth predictions
  - ถ้า prob=0.3 และ magnitude=100,000 → final=30,000 (reasonable)
```

**ขั้นตอนแบบเรียงลำดับ (สำหรับ inference จริงต่อ 1 zone, 1 horizon):**

1. เตรียม `X_clf` (17 features สูงสุด, หัวข้อ 5) และ `X_reg` (36-37 features, หัวข้อ 4) จากข้อมูลล่าสุด
2. โหลด `stage1_classifiers.pkl[(zone, h)]` → เรียก `.predict_proba(X_clf)[:, 1]` ได้ `prob`
3. โหลด `catboost_models.pkl[(zone, h)]` และ `lightgbm_models.pkl[(zone, h)]` → เรียก `.predict(X_reg)` ทั้งคู่
4. โหลด `stack_weights.pkl[(zone, h)]` (`w_cat`, `w_lgb`) → รวมเป็น `magnitude = w_cat*cat_pred + w_lgb*lgb_pred` แล้ว clip ที่ 0 (`np.maximum(mag, 0)`)
5. `y_final = prob * magnitude`
6. ทำซ้ำข้อ 1–5 สำหรับ h = 1 ถึง 12 และสำหรับทั้ง zone_A, zone_B (รวม 24 ชุดโมเดลต่อรอบ)

**หมายเหตุ threshold:** `stage1_thresholds.pkl` เก็บ threshold ที่ optimize ไว้สำหรับแปลง `prob`
เป็น binary label (ใช้ตอน evaluate/report F1 เท่านั้น) **ไม่ได้ใช้ในสูตร final prediction**
(สูตร final ใช้ `prob` แบบต่อเนื่อง คูณตรงๆ ไม่ผ่าน threshold)

---

## 8. ช่องว่าง/ข้อมูลที่ยังขาด (สำหรับ implement `build_feature_vector()`/`run_prediction()` จริง)

1. **ไม่มีไฟล์โมเดล Reservoir Inflow** เก็บไว้เลย (ดูหัวข้อ 1) — นอกขอบเขตเอกสารนี้แต่เป็น blocker ที่ต้องแก้ก่อน
2. **สคริปต์ training จริงของ Step 3a (CatBoost + Optuna hyperparameter search) ไม่สมบูรณ์**
   ในไฟล์ต้นฉบับมี comment เตือนไว้เองที่บรรทัด 2737–2749:
   ```
   *** GAP: NOT FOUND IN YOUR UPLOADS ***
   Your uploaded notebook only contains the ROUND-3 RERUN of this step (next
   cell below), which expects an existing `catboost_models.pkl` from round 2 as
   input ('overwrite เฉพาะ 3 keys'). The original round-1/round-2 training
   script that PRODUCES the initial `catboost_models.pkl` was not among your
   uploaded files.
   ```
   หมายความว่าถ้าต้อง **retrain** โมเดล CatBoost ใหม่ทั้งหมด (ไม่ใช่แค่โหลด `.pkl` มา predict)
   ต้องหา hyperparameter search space ต้นฉบับเพิ่มเติม เอกสารนี้ครอบคลุมเฉพาะ **การ predict
   ด้วยโมเดลที่ train ไว้แล้ว** ซึ่งไม่ต้องพึ่งส่วนที่ขาดหายนี้
3. **พื้นที่ปลูกพืชต่อ zone เป็นค่าคงที่จากปี 2020** (หัวข้อ 2 และ 6) — ถ้า
   `trigger_crop_classification()` ใน `data_pipeline.py` รันแล้วได้ crop map ใหม่ ยังไม่มี logic
   แปลงผลนั้นเป็น `AREA_ZONE_A`/`AREA_ZONE_B` ใหม่โดยอัตโนมัติ ต้องเขียนเพิ่ม
4. **`SPI_4` ต้องใช้ climate history ย้อนหลังหลายปี** (z-score ข้ามปีของสัปดาห์เดียวกัน) —
   `build_feature_vector()` เวอร์ชัน production ต้องเก็บ/query climate time series สะสมไว้
   ไม่ใช่แค่ค่าของสัปดาห์ปัจจุบันอย่างเดียว เช่นเดียวกับ lag/rolling features ทั้งหมด (ต้องมี
   ประวัติ demand/climate ย้อนหลังอย่างน้อย 12 สัปดาห์สำหรับ lag12 และมากกว่านั้นสำหรับ SPI_4)
5. **`mei_monthly.csv`** (Multivariate ENSO Index) เป็น external data source ที่ไม่มีอยู่ใน repo
   ปัจจุบัน (ไม่พบไฟล์นี้ในการสำรวจ `01_data/` ก่อนหน้า) — ต้องหาแหล่งอัปเดตรายเดือนสำหรับใช้งานจริง
   (เช่น NOAA PSL MEI.v2 index)
6. **`kc_weekly_lookup_all_crops.csv`** (Kc lookup ที่หัวข้อ 4/7 ใช้) **หาไม่พบในโปรเจกต์นี้เลย**
   (path เดิมใน config ชี้ไป `D:\University of Phayao\...` คนละเครื่อง/โฟลเดอร์กับ repo ปัจจุบัน)
   — **แต่พบ generator script ต้นฉบับครบถ้วนแล้ว** ใน `archive/combined_final_pipeline.py`
   บรรทัด 786–973 (สำรวจเมื่อ 2026-07-08): มี `STAGE_WEEKS` (ช่วงสัปดาห์ growth stage ต่อพืช,
   5 พืช: rice/corn/cassava/longan/rubber), `KC_FAO56` (ค่า Kc ตาม Allen et al. 1998 ต่อ
   crop+stage พร้อม `CF_LOCAL = 1.05` ปรับค่าตามภูมิอากาศท้องถิ่นสถานีพะเยา), ฟังก์ชัน `get_kc()`
   และ `build_weekly_stage_lookup()` ที่ expand เป็น week 1–52 แล้ว `.to_csv('kc_weekly_lookup_all_crops.csv')`
   ตรงบรรทัด 972 — **นี่คือโค้ดต้นฉบับที่สร้างไฟล์ที่หายไปจริง ไม่ใช่แค่ต้องเดาค่า FAO-56 มาใหม่**
   รันซ้ำได้ทันทีเพื่อ regenerate ไฟล์ (ไม่มี `'etc'` เป็น key ใน `KC_FAO56` เลย — ยืนยันตรงกับ
   หัวข้อ 2 ว่า class `'etc'` ไม่เคยถูกออกแบบให้มี Kc ตั้งแต่ต้น)

---

*เอกสารนี้เป็นการสำรวจ/รวบรวม logic เท่านั้น ยังไม่ได้แก้ไข `pipeline/data_pipeline.py`
ตามที่ระบุไว้ในคำขอ*
