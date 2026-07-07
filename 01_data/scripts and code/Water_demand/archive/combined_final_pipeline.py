"""
==============================================================================
COMBINED FINAL PIPELINE  (v2)
Weekly Agricultural Water Demand Forecasting — Mae Na Rua, Phayao, Thailand
Dual-zone (Zone A rainfed / Zone B irrigated), two-stage ML + Mondrian
conformal prediction (Variant D: Mondrian + Normalized — FINAL, confirmed
as the version used in the manuscript).
==============================================================================

Assembled from your uploaded notebooks/scripts + methodology guide docx files.
Each section below is reproduced VERBATIM from your files unless marked
"EDITED" or "GAP" in its header comment.

v2 changes vs. the first combined file:
  - PHASE 2 (DTW): fastdtw replaced with the pure-numpy dtw_distance()
    implementation, per your confirmation that this is the actual final
    method (fastdtw was not installable in the working environment).
  - GEE JavaScript (Sentinel-1/2 preprocessing) intentionally NOT included
    per your instruction — runs separately in the Earth Engine editor.
  - Step 5.3 spatial demand mapping (pixel-level, Kc-weighted) intentionally
    left as an open gap per your instruction — the only version found in
    the methodology guide is the abandoned zone-level GeoPackage plan, not
    the actual final pixel-level script, so it was not included.

This script is NOT meant to be run top-to-bottom in one go — each PHASE/Step
was originally a separate script/notebook cell with its own inputs/outputs
on disk (csv/pkl files). Run sections individually, in order, as you did
originally.
"""


# ##############################################################################
# # PHASE 1 — Crop Classification (Random Forest, FINAL model v3b)
# Source: `Retrain3.ipynb` (final, superseding the earlier `Training_Data.ipynb`
# draft which trained `rf_model_best.pkl` instead of the v3b model actually used
# in the paper). OA = 0.8362, 86 features, 6,347 training points.
# ##############################################################################

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

df = pd.read_csv('ข้อมูลเพาะปลูก.csv')


# ── 1. แปลงวันที่ integer → datetime ──────────────────────────
def parse_thaidate(val):
    try:
        s = str(int(val))
        if len(s) != 8:
            return pd.NaT
        yr = int(s[:4])
        # ถ้า year > 2500 = พ.ศ. → แปลงเป็น ค.ศ.
        if yr > 2500:
            yr -= 543
        return pd.Timestamp(f"{yr}-{s[4:6]}-{s[6:8]}")
    except:
        return pd.NaT

df['plant_date_dt']   = df['plant_date'].apply(parse_thaidate)
df['harvest_date_dt'] = df['produce_da'].apply(parse_thaidate)

# แปลง year_act (พ.ศ. → ค.ศ.)
df['year_ce'] = df['year_act'].apply(lambda y: y - 543 if y > 2500 else y)

# ── 2. คำนวณ growing duration (วัน) ──────────────────────────
df['growing_days'] = (df['harvest_date_dt'] - df['plant_date_dt']).dt.days

# กรอง perennial ที่มีวันที่ผิดปกติ
df['is_annual'] = df['detail_nam'].isin([
    'ข้าวเจ้า','ข้าวเหนียว',
    'ข้าวโพดเลี้ยงสัตว์','มันสำปะหลังโรงงาน'
])

print("Annual crops growing duration (days):")
print(df[df['is_annual']]['growing_days'].describe())

# ── 3. Reclassify crop classes ──────────────────────────────
# ปัญหา: tobacco = 2 แปลง, rubber = 30 แปลง
# แนวทาง: ปรับ class scheme ให้สมจริง

class_map = {
    'ข้าวเจ้า':              'rice',
    'ข้าวเหนียว':            'rice',
    'ลำไย':                  'longan',
    'ข้าวโพดเลี้ยงสัตว์':    'corn',
    'มันสำปะหลังโรงงาน':     'cassava',    # ← เพิ่มใหม่! มี 122 แปลง
    'ยางพารา':               'rubber',
    'ยาสูบ':                 'etc',         # ← รวมเข้า etc (2 แปลงเท่านั้น)
    'ปาล์มน้ำมัน':           'etc',
    'มะขาม':                 'etc',
    'หอมแบ่ง(ต้นหอม)':       'etc',
    'ยูคาลิปตัส':            'etc',
    'ฝรั่ง':                 'etc',
    'ฟักทอง':                'etc',
    'กระท่อม':               'etc',
    'มะม่วง':                'etc',
    'ส้มโอ':                 'etc',
    'ผักอื่นๆ':              'etc',
    'กระท้อน':               'etc',
    'ถั่วเขียวผิวมัน':       'etc',
}
df['crop_class'] = df['detail_nam'].map(class_map).fillna('etc')

print("\nRevised class distribution:")
print(df.groupby('crop_class')['act_rai_or'].agg(
    count='count',
    area_rai='sum'
).round(2).sort_values('count', ascending=False))

# ── 4. แปลงเป็น GeoDataFrame ─────────────────────────────────
df_clean = df.dropna(subset=['lat','lng'])
geometry = [Point(lng, lat) for lat, lng
            in zip(df_clean['lat'], df_clean['lng'])]
gdf = gpd.GeoDataFrame(df_clean, geometry=geometry, crs='EPSG:4326')
gdf = gdf.to_crs('EPSG:32647')  # UTM Zone 47N

print(f"\nGeoDataFrame ready: {len(gdf)} parcels")
print(f"CRS: {gdf.crs}")

# แก้ไข: กรองพิกัดที่ไม่ valid ออกก่อน
# ต.แม่นาเรือ อยู่ใน lat 18.9–19.3, lng 99.5–100.1
valid_mask = (
    df_clean['lat'].between(18.9, 19.3) &
    df_clean['lng'].between(99.5, 100.1)
)
gdf = gdf[valid_mask].copy()
print(f"แถวที่ valid หลังกรองพิกัด: {len(gdf)} (ลบออก {(~valid_mask).sum()} แถว)")

# ── 5. Export แยกตาม use case ─────────────────────────────────

# 5a. Training points สำหรับ Phase 1 (RF classification)
#     ใช้ปี 2021–2022 เป็น training | ปี 2023 เป็น validation
gdf_train = gdf[gdf['year_ce'].isin([2021, 2022])]
gdf_val   = gdf[gdf['year_ce'] == 2023]
gdf_train.to_file('training_parcels_2021_2022.shp')
gdf_val.to_file('validation_parcels_2023.shp')
print(f"\nTraining: {len(gdf_train)} | Validation: {len(gdf_val)}")

# 5b. Phenology calendar สำหรับ Phase 2 (DTW template)
#     เฉพาะ annual crops ที่มีวันที่น่าเชื่อถือ
pheno = gdf[gdf['is_annual'] & (gdf['growing_days'] > 30) & (gdf['growing_days'] < 365)]
pheno_cal = pheno.groupby(['crop_class','year_ce']).agg(
    mean_plant_doy  = ('plant_date_dt',   lambda x: x.dt.dayofyear.mean()),
    std_plant_doy   = ('plant_date_dt',   lambda x: x.dt.dayofyear.std()),
    mean_harvest_doy= ('harvest_date_dt', lambda x: x.dt.dayofyear.mean()),
    mean_duration   = ('growing_days',    'mean'),
    n_parcels       = ('act',             'count'),
    total_area_rai  = ('act_rai_or',      'sum'),
).round(1).reset_index()
pheno_cal.to_csv('phenology_calendar_by_crop_year.csv', index=False)
print("\nPhenology calendar (DOY = Day of Year):")
print(pheno_cal.to_string())

# 5c. Crop area per zone สำหรับ Phase 3 (demand estimation)
#     ต้องการ zone boundary ก่อน แต่ prepare ข้อมูลพร้อมไว้
area_summary = gdf.groupby(['year_ce','crop_class'])['act_rai_or'].sum()
area_summary_m2 = (area_summary * 1600).round(0)  # 1 ไร่ = 1,600 m²
area_summary_m2.to_csv('crop_area_m2_by_year.csv')
print("\nCrop area (m²) by year:")
print(area_summary_m2.unstack(fill_value=0))

import rasterio
import numpy as np
import geopandas as gpd
from rasterio.sample import sample_gen

# ── 1. เช็กว่า geometry เป็น Point หรือ Polygon ──────────────
gdf_in = gpd.read_file('training_parcels_2021_2022.shp')
gdf_in = gdf_in.to_crs('EPSG:32647')
print("Geometry type:", gdf_in.geometry.geom_type.value_counts().to_dict())

# ── 2. เช็ก nodata value ของ raster ─────────────────────────
with rasterio.open('S2_drySeason_composite_2022.tif') as src:
    print(f"\nS2 nodata value: {src.nodata}")
    print(f"S2 dtype       : {src.dtypes[0]}")
    # อ่าน band 1 และดูการกระจายของค่า
    band1 = src.read(1)
    print(f"S2 band1 - NaN count  : {np.isnan(band1).sum()}")
    print(f"S2 band1 - Zero count : {(band1==0).sum()}")
    print(f"S2 band1 - Valid count: {(band1>0).sum()}")
    total = band1.size
    valid_pct = (band1>0).sum() / total * 100
    print(f"S2 band1 - Valid %    : {valid_pct:.1f}%")

with rasterio.open('S1_fullYear_weekly_2022.tif') as src:
    print(f"\nS1 nodata value: {src.nodata}")
    print(f"S1 dtype       : {src.dtypes[0]}")
    band1 = src.read(1)  # VV week 1
    print(f"S1 VV band - NaN count   : {np.isnan(band1).sum()}")
    print(f"S1 VV band - Zero count  : {(band1==0).sum()}")
    valid_pct_s1 = (~np.isnan(band1) & (band1!=0)).sum() / band1.size * 100
    print(f"S1 VV band - Valid %     : {valid_pct_s1:.1f}%")

# ── 3. ทดสอบ extract ค่าที่จุดตรงกลาง raster ────────────────
with rasterio.open('S2_drySeason_composite_2022.tif') as src:
    cx = (src.bounds.left + src.bounds.right)  / 2
    cy = (src.bounds.bottom + src.bounds.top) / 2
    test_val = list(sample_gen(src, [(cx, cy)]))[0]
    print(f"\nS2 value at raster center {cx:.0f},{cy:.0f}:")
    print(f"  {test_val[:5]}  ← 0 หรือ NaN = masked")

"""
=============================================================
Phase 1 — Crop Classification v3b (FINAL)
Mae Na Rua Sub-District, Phayao, Northern Thailand
 
Changes from v3a:
  - ใช้ sample_points_inner_custom (erosion แยกตาม crop)
  - longan erosion 40m (จาก 20m) เพื่อลด mixed pixel กับ rice
  - ข้าม rice จาก LDD — ใช้ SHP เท่านั้น
  - เพิ่ม bootstrap CI สำหรับ minority classes
=============================================================
RESTART KERNEL ก่อนรัน
"""
 
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.sample import sample_gen
from shapely.geometry import Point
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score
from sklearn.utils import resample as sk_resample
import matplotlib.pyplot as plt
import joblib, json, warnings
warnings.filterwarnings('ignore')
 
class_labels = {'rice':0, 'corn':1, 'cassava':2, 'longan':3, 'etc':4}
 
# ══════════════════════════════════════════════════════════════
# STEP 0A — SHP training points (point geometry, ปี 2021–2022)
# ══════════════════════════════════════════════════════════════
gdf = gpd.read_file('training_parcels_2021_2022.shp').to_crs('EPSG:32647')
gdf['crop_class'] = gdf['crop_class'].replace('rubber', 'etc')
gdf['class_id']   = gdf['crop_class'].map(class_labels)
gdf = gdf.dropna(subset=['class_id'])
gdf['class_id']   = gdf['class_id'].astype(int)
 
with rasterio.open('S2_drySeason_composite_2022.tif') as src:
    rb = src.bounds
 
gdf = gdf[
    gdf.geometry.x.between(rb.left,  rb.right) &
    gdf.geometry.y.between(rb.bottom, rb.top)
].reset_index(drop=True)
 
coords_shp = list(zip(gdf.geometry.x, gdf.geometry.y))
labels_shp = gdf['class_id'].values
 
print(f"SHP points: {len(coords_shp)}")
print(gdf['crop_class'].value_counts())
 
# ══════════════════════════════════════════════════════════════
# STEP 0B — LDD polygon sampling (minority classes เท่านั้น)
# ══════════════════════════════════════════════════════════════
 
def sample_points_inner_custom(polygon, n_pts, erosion_m=20, seed=42):
    """
    Sample จากส่วนใน polygon หลัง erode erosion_m เมตร
    เพื่อหลีกเลี่ยง mixed pixel ที่ขอบแปลง
    """
    inner = polygon.buffer(-erosion_m)
    if inner.is_empty or inner.area < 1:
        inner = polygon.buffer(-10)   # fallback: erode น้อยลง
    if inner.is_empty or inner.area < 1:
        inner = polygon               # fallback: ใช้ทั้งหมด
 
    rng = np.random.default_rng(seed)
    minx, miny, maxx, maxy = inner.bounds
    pts, attempts = [], 0
    while len(pts) < n_pts and attempts < n_pts * 50:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if inner.contains(Point(x, y)):
            pts.append((x, y))
        attempts += 1
    return pts if pts else [(inner.centroid.x, inner.centroid.y)]
 
# Erosion ต่างกันตาม crop (เมตร)
EROSION_M = {
    'longan':  40,   # เพิ่มจาก 20 → 40 เพราะ adjacent กับ rice สูง
    'corn':    20,
    'cassava': 20,
    'etc':     20,
}
 
# จำนวนจุดต่อ polygon
POINTS_PER_CLASS = {
    'longan':   3,   # ลดลง — polygon longan มี mixed pixel สูง
    'corn':     8,
    'cassava': 15,
    'etc':      5,
}
 
# Map LDD → crop class
ldd_crop_map = {
    'Active paddy field':            'rice',
    'Abandoned paddy field':         'rice',
    'Active paddy field+Corn':       'rice',
    'Active paddy field+Truck crop': 'rice',
    'Corn':                          'corn',
    'Corn+Tobacco':                  'corn',
    'Corn(Shifting cultivation)':    'corn',
    'Corn/Tamarind':                 'corn',
    'Corn/Truck crop':               'corn',
    'Cassava':                       'cassava',
    'Longan':                        'longan',
    'Teak/Longan':                   'longan',
    'Tamarind/Longan':               'longan',
    'Mango/Longan':                  'longan',
    'Para rubber':                   'etc',
    'Truck crop':                    'etc',
    'Mixed orchard':                 'etc',
    'Mixed perennial':               'etc',
    'Tamarind':                      'etc',
    'Banana':                        'etc',
    'Abandoned field crop':          'etc',
    'Abandoned perenial':            'etc',
    'Abandoned orchard':             'etc',
}
 
# โหลด LDD + filter เฉพาะ agricultural
ldd = gpd.read_file('LDD_landuse.shp').to_crs('EPSG:32647')
ldd['crop_class'] = ldd['LU_DES_EN'].map(ldd_crop_map)
ldd_agri = ldd.dropna(subset=['crop_class']).copy()
ldd_agri['class_id'] = ldd_agri['crop_class'].map(class_labels)
ldd_agri = ldd_agri.dropna(subset=['class_id'])
 
# filter ให้อยู่ใน raster extent
ldd_agri['cx'] = ldd_agri.geometry.centroid.x
ldd_agri['cy'] = ldd_agri.geometry.centroid.y
ldd_agri = ldd_agri[
    ldd_agri['cx'].between(rb.left,  rb.right) &
    ldd_agri['cy'].between(rb.bottom, rb.top)
].reset_index(drop=True)
 
# Sample จุดจาก polygon พร้อม erosion แยกตาม crop
np.random.seed(42)
coords_ldd, labels_ldd = [], []
skipped = 0
 
for _, row in ldd_agri.iterrows():
    crop = row['crop_class']
 
    # ข้าม rice ทั้งหมด — SHP มี rice พอแล้ว และ pure กว่า
    if crop == 'rice':
        continue
 
    n_pts    = POINTS_PER_CLASS.get(crop, 3)
    erosion  = EROSION_M.get(crop, 20)
 
    pts = sample_points_inner_custom(        # ← ใช้ฟังก์ชันใหม่
        row.geometry, n_pts, erosion_m=erosion
    )
    if not pts:
        skipped += 1
        continue
 
    coords_ldd.extend(pts)
    labels_ldd.extend([int(row['class_id'])] * len(pts))
 
labels_ldd = np.array(labels_ldd)
print(f"\nLDD polygon points (erosion, no rice): {len(coords_ldd)}")
print(f"Skipped polygons: {skipped}")
for idx, name in {v:k for k,v in class_labels.items()}.items():
    print(f"  {name:10s}: {(labels_ldd==idx).sum()}")
 
# ══════════════════════════════════════════════════════════════
# STEP 0C — รวม SHP + LDD
# ══════════════════════════════════════════════════════════════
all_coords = coords_shp + coords_ldd
all_labels = np.concatenate([labels_shp, labels_ldd])
 
print(f"\nTotal points: {len(all_coords)}")
print("Final class distribution:")
for idx, name in {v:k for k,v in class_labels.items()}.items():
    print(f"  {name:10s}: {(all_labels==idx).sum()}")
 
# ══════════════════════════════════════════════════════════════
# STEP 1 — Extract features
# ══════════════════════════════════════════════════════════════
def extract(tif_path, coords, prefix, band_idx=None):
    with rasterio.open(tif_path) as src:
        arr = np.array(list(sample_gen(src, coords)), dtype=np.float32)
    if band_idx is not None:
        arr = arr[:, band_idx]
    return pd.DataFrame(arr, columns=[f"{prefix}_{i}" for i in range(arr.shape[1])])
 
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
y       = all_labels
 
print(f"\nX shape: {X.shape} | NaN: {X.isnull().sum().sum()}")

# ── 4. Train RF ───────────────────────────────────────────────
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, stratify=y, random_state=42)

param_grid = {
    'n_estimators':     [400,600,800],
    'max_depth':        [20, 10, 30],
    'min_samples_leaf': [2,3,4],
    'min_samples_split': [4,2,3],
    'criterion':        ['entropy'],
    'bootstrap':        [ True, False],
}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
gs = GridSearchCV(
    RandomForestClassifier(
        class_weight='balanced',
        n_jobs=-1, random_state=42
    ),
    param_grid, cv=cv, scoring='f1_macro', verbose=1
)
gs.fit(X_train, y_train)

# ══════════════════════════════════════════════════════════════
# STEP 3 — Evaluate
# ══════════════════════════════════════════════════════════════
y_pred = gs.best_estimator_.predict(X_test)
oa     = (y_pred == y_test).mean()
names  = list(class_labels.keys())
 
print(f"\n{'='*55}")
print(f"OA: {oa:.4f}")
print(f"  v2 (SAR wet, SHP only)     : 0.9329")
print(f"  v3a (LDD full, erosion 20m): 0.8299")
print(f"  งานเดิม Pinkaeo 2024       : 0.7365")
print(f"Best params: {gs.best_params_}")
print(f"{'='*55}")
print(classification_report(y_test, y_pred,
      target_names=names, zero_division=0))
 

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
fig, ax = plt.subplots(figsize=(7,6))
ConfusionMatrixDisplay(cm, display_labels=names).plot(
    ax=ax, cmap='Blues', colorbar=False)
ax.set_title(f'RF v3b — S2+SAR dry+wet + LDD erosion (OA={oa:.4f})', fontsize=11)
plt.tight_layout()
plt.savefig('confusion_matrix_v3b_final.png', dpi=300)
plt.show()

# Feature importance
fi = pd.Series(gs.best_estimator_.feature_importances_,
               index=X.columns).sort_values(ascending=False)
s2_imp  = fi[[c for c in fi.index if c.startswith('S2')]].sum()
s1d_imp = fi[[c for c in fi.index if c.startswith('S1d')]].sum()
s1w_imp = fi[[c for c in fi.index if c.startswith('S1w')]].sum()
 
print(f"\nFeature group importance:")
print(f"  S2  dry optical : {s2_imp*100:.1f}%")
print(f"  S1d SAR dry     : {s1d_imp*100:.1f}%")
print(f"  S1w SAR wet     : {s1w_imp*100:.1f}%")
print(f"\nTop 10 features:")
print(fi.head(10).round(4))

# Bootstrap CI
print("\n=== Bootstrap 95% CI (n=1000) ===")
f1_boot = {name:[] for name in names}
for i in range(1000):
    idx = sk_resample(range(len(y_test)), random_state=i)
    yt, yp = y_test[idx], y_pred[idx]
    for name, cid in class_labels.items():
        f1 = f1_score(yt, yp, labels=[cid],
                      average='macro', zero_division=0)
        f1_boot[name].append(f1)
 
for name, vals in f1_boot.items():
    ci  = np.percentile(vals, [2.5, 97.5])
    n   = (y_test == class_labels[name]).sum()
    print(f"  {name:10s}: F1={np.mean(vals):.3f} "
          f"95%CI [{ci[0]:.3f}–{ci[1]:.3f}]  n_test={n}")

# ══════════════════════════════════════════════════════════════
# STEP 4 — Save
# ══════════════════════════════════════════════════════════════
joblib.dump(gs.best_estimator_, 'rf_model_v3b_final.pkl')
joblib.dump(scaler,             'rf_scaler_v3b_final.pkl')
joblib.dump(medians,            'col_medians_v3b_final.pkl')
 
feature_info = {
    's2_cols':  s2_cols,
    's1d_cols': s1d_cols,
    's1w_cols': s1w_cols,
    'all_cols': all_cols,
    'dry_vv':   dry_vv,
    'dry_vh':   dry_vh,
    'wet_vv':   wet_vv,
    'wet_vh':   wet_vh,
    'n_feat':   N_FEAT,
}
with open('feature_info_v3b_final.json','w') as f:
    json.dump(feature_info, f)
with open('class_labels.json','w') as f:
    json.dump(class_labels, f)

"""
Table 1 — Classification Performance Summary (for paper)
Phase 1: RF Crop Classification, Mae Na Rua, Phayao
Final model: v3b only
"""
import pandas as pd
import numpy as np

# ── ข้อมูลจากผลการรัน ─────────────────────────────────────────
results = pd.DataFrame({
    'Class':        ['rice', 'corn', 'cassava', 'longan', 'etc', 'Overall (OA)'],

    # Pinkaeo et al. 2024 (งานเดิม — 6 class, S2 dry season only)
    'Pinkaeo_2024_F1': [0.81, 0.52, 'N/A', 0.72, 'N/A', '0.7365'],

    # v3b: S2 + SAR dry + wet, SHP + LDD erosion sampling
    'v3b_Precision': [0.94, 0.76, 1.00, 0.68, 0.81, '—'],
    'v3b_Recall':    [0.96, 0.87, 0.67, 0.62, 0.71, '—'],
    'v3b_F1':        [0.95, 0.81, 0.80, 0.65, 0.75, '0.8362'],
    'CI_95_low':     [0.935, 0.778, 0.708, 0.586, 0.706, '—'],
    'CI_95_high':    [0.962, 0.839, 0.871, 0.706, 0.800, '—'],
    'n_test':        [489, 336, 72, 163, 210, 1270],
    'vs_Pinkaeo':    ['+0.14', '+0.29', 'new', '−0.07', 'new', '+0.10 OA'],
})

print("="*100)
print("TABLE 1. RF Crop Classification Performance — Model v3b")
print("="*100)
print(results.to_string(index=False))

print("\n\n=== สำหรับใส่ใน paper ===")
print("""
Table 1. Classification accuracy of the RF crop mapping model (v3b).
Features: Sentinel-2 dry-season composite + Sentinel-1 SAR (dry: wk 1–16; wet: wk 17–36).
Training: field survey points (n=2,830) augmented with LDD polygon sampling
          using crop-specific interior erosion (longan: 40 m; others: 20 m).
95% CI estimated by bootstrap resampling (n=1,000).
N/A = class not included in Pinkaeo et al. (2024). OA = Overall Accuracy.

Class     Precision  Recall   F1     95% CI            n_test  vs. Pinkaeo (2024)
rice       0.94      0.96    0.95   [0.935–0.962]      489     +0.14
corn       0.76      0.87    0.81   [0.778–0.839]      336     +0.29
cassava    1.00      0.67    0.80   [0.708–0.871]       72     new class
longan     0.68      0.62    0.65   [0.586–0.706]      163     −0.07
etc        0.81      0.71    0.75   [0.706–0.800]      210     new class
─────────────────────────────────────────────────────────────────────
OA (macro) 0.84      0.77    0.79                     1270     +0.10 OA
                             0.8362 (weighted avg)
""")

print("=== Feature Importance ===")
fi = pd.DataFrame({
    'Feature group':   [
        'S2 dry optical (wk Nov–Apr)',
        'S1 SAR dry season (wk 1–16)',
        'S1 SAR wet season (wk 17–36)',
    ],
    'Importance (%)': [44.2, 19.8, 36.0],
    'Key features':   [
        'S2_12 (SWIR2), S2_11 (SWIR1), S2_13 (NDVI)',
        'VV/VH backscatter Jan–Apr',
        'S1w_33, S1w_37 (VH Aug–Sep = corn grain fill)',
    ],
})
print(fi.to_string(index=False))

print("""
Note: S1 wet season (36.0%) contributed more than S1 dry season (19.8%),
confirming the importance of cloud-agnostic SAR for corn phenology detection
during the monsoon growing period (June–October).
""")

print("=== Key Findings for Discussion ===")
print("""
1. corn F1: 0.52 (Pinkaeo 2024) → 0.81 (v3b)   +0.29
   → SAR wet season (wk 17–36) critical for corn detection
   → Peak features: wk 33–37 (Aug–Sep) = grain fill stage

2. cassava F1 = 0.80 [CI: 0.71–0.87] with n_test=72
   → Reliable estimate via LDD polygon augmentation
   → Previously untested in Pinkaeo 2024

3. longan F1: 0.72 (Pinkaeo 2024) → 0.65 (v3b)  −0.07
   → LDD longan polygons border adjacent rice fields
   → 40 m interior erosion insufficient for small parcels
   → Recommend field validation for longan area estimates

4. OA: 0.7365 → 0.8362  (+10.0 percentage points)
   → Improvement despite harder 5-class problem
   → Attributed to SAR wet season features + augmented training
""")

results.to_csv('table1_v3b_only.csv', index=False)
print("✅ Saved: table1_v3b_only.csv")

# รันหลัง Grid Search เสร็จและ save model แล้ว
import numpy as np, pandas as pd, geopandas as gpd
import rasterio, joblib, json, warnings
from rasterio.features import rasterize
from rasterio.enums import Resampling
warnings.filterwarnings('ignore')

rf      = joblib.load('rf_model_v3b_final.pkl')
scaler  = joblib.load('rf_scaler_v3b_final.pkl')
medians = joblib.load('col_medians_v3b_final.pkl')
with open('feature_info_v3b_final.json') as f: fi = json.load(f)
with open('class_labels.json') as f: class_labels = json.load(f)

all_cols    = fi['all_cols']
dry_vv,dry_vh = fi['dry_vv'], fi['dry_vh']
wet_vv,wet_vh = fi['wet_vv'], fi['wet_vh']
N_FEAT      = fi['n_feat']
class_names = {v:k for k,v in class_labels.items()}

# LDD mask
ldd = gpd.read_file('LDD_landuse.shp')
agri_l2 = [20,21,22,23,24,25,26,27,29,
           21222,21225,22124,22125,22222,22225,23124]
exclude_en = ['Teak','Fish farm','Cattle farm house',
              'Poultry  farm house','Swine farm house',
              'Bamboo','Rain tree','Bur-flower tree']
agri_ldd = ldd[
    ldd['LU_ID_L2'].isin(agri_l2) &
    ~ldd['LU_DES_EN'].isin(exclude_en)
].copy()

def generate_crop_map_v3b(year):
    with rasterio.open(f'S2_drySeason_composite_{year}.tif') as s:
        s2_data = s.read().astype(np.float32)
        profile = s.profile.copy()
        rows,cols = s.shape
        transform,crs = s.transform, s.crs

    with rasterio.open(f'S1_fullYear_weekly_{year}.tif') as s:
        s1_all = s.read(out_shape=(s.count,rows,cols),
                        resampling=Resampling.bilinear).astype(np.float32)

    s1_dry = s1_all[dry_vv+dry_vh]
    s1_wet = s1_all[wet_vv+wet_vh]

    # LDD mask
    agri_repr = agri_ldd.to_crs(crs)
    agri_mask = rasterize(
        [(g,1) for g in agri_repr.geometry if g and not g.is_empty],
        out_shape=(rows,cols), transform=transform,
        fill=0, dtype=np.uint8)

    stacked  = np.vstack([s2_data, s1_dry, s1_wet])
    X_raster = stacked.reshape(len(all_cols),-1).T
    df = pd.DataFrame(X_raster, columns=all_cols)
    df = df.fillna(medians).fillna(0)

    preds    = rf.predict(scaler.transform(df.values)).astype(np.uint8)
    crop_flat = np.full(rows*cols, 255, dtype=np.uint8)
    crop_flat[agri_mask.flatten().astype(bool)] = \
        preds[agri_mask.flatten().astype(bool)]
    crop_map = crop_flat.reshape(rows, cols)

    profile.update(count=1, dtype='uint8', nodata=255)
    with rasterio.open(f'crop_map_v3b_{year}.tif','w',**profile) as dst:
        dst.write(crop_map, 1)

    pixel_rai = abs(profile['transform'].a * profile['transform'].e)/1600
    ldd_ref   = {'rice':30535,'corn':7894,'longan':3473,'cassava':170,'etc':0}
    print(f"\n=== crop_map_v3b_{year}.tif ===")
    print(f"  {'Class':<12}{'ไร่':>8}  {'LDD ref':>8}  {'ratio':>6}")
    results = {}
    for cid,cname in class_names.items():
        n_px = int((crop_map==cid).sum())
        rai  = round(n_px*pixel_rai)
        ref  = ldd_ref.get(cname,0)
        ratio = f"{rai/ref:.2f}" if ref>0 else "—"
        results[cname] = {'rai':rai,'pixels':n_px,'m2':n_px*pixel_rai*1600}
        print(f"  {cname:<12}{rai:>8,}  {ref:>8,}  {ratio:>6}")
    return results

all_areas = {}
for year in [2020,2021,2022,2023]:
    all_areas[year] = generate_crop_map_v3b(year)
    print(f"✅ crop_map_v3b_{year}.tif saved")

rows_out = [{'year':yr,'crop':cn,'rai':v['rai'],'m2':v['m2']}
            for yr,a in all_areas.items()
            for cn,v in a.items()]
pd.DataFrame(rows_out).to_csv('crop_area_v3b_by_year.csv',index=False)
print("\n✅ crop_area_v3b_by_year.csv saved")


# ##############################################################################
# # PHASE 2 — SAR-Based Crop Phenology (DTW Templates)
# Source: `phase2_dtw_templates.py`, as uploaded, but EDITED per your
# confirmation: `4_methodology_guide_updated_p12.docx` states fastdtw
# was not installable in the working environment and was replaced with a
# pure-numpy DTW implementation for the actual final run. The fastdtw
# import is commented out (kept for provenance) and `classify_stage_dtw`
# now calls the pure-numpy `dtw_distance()` function (reproduced verbatim
# from the methodology guide) instead. No other logic changed.
# ##############################################################################

"""
=============================================================
Phase 2 — SAR-Based Crop Phenology Detection
DTW Templates derived from field data (2020–2023)
Mae Na Rua Sub-District, Phayao, Northern Thailand
=============================================================

Growing Stage Boundaries — from phenology_calendar_by_crop_year.csv
---------------------------------------------------------------------
RICE    : plant W26 (DOY 181±18) → harvest W47 (DOY 325) | ~20 weeks
CORN    : plant W25 (DOY 174±47) → harvest W39 (DOY 272) | ~17 weeks
CASSAVA : plant W17 (DOY 118±53) → harvest ~W07 next year | ~42 weeks
LONGAN  : perennial — stress phase W44–50 (Nov–Dec)
RUBBER  : perennial — defoliation W01–08 (Jan–Feb)

SAR Backscatter Templates (VH dB) — calibrated from literature
for tropical smallholder systems + adjusted to match field date ranges
---------------------------------------------------------------------
References:
  Nguyen et al. (2016) Remote Sens. — rice SAR phenology Mekong
  Torbick et al. (2017) Remote Sens. — SE Asia rice SAR
  Verhegghen et al. (2014) Remote Sens. — rubber SAR signature
  Longan: adapted from Kc dynamics (Menzel & Lüdders 2001)
=============================================================
"""

import numpy as np
import pandas as pd
# EDITED — see note above: fastdtw replaced with pure-numpy DTW
# (fastdtw import kept commented out for reference / provenance only)
# from fastdtw import fastdtw
# from scipy.spatial.distance import euclidean


def dtw_distance(s1, s2):
    """Pure numpy DTW distance -- no external library needed.

    Source: 4_methodology_guide_updated_p12.docx, Step 2.3 (confirmed FINAL
    approach — fastdtw was not installable in the working environment, this
    pure-numpy implementation was substituted and tested successfully).
    """
    n, m = len(s1), len(s2)
    dtw_mat = np.full((n + 1, m + 1), np.inf)
    dtw_mat[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(float(s1[i - 1]) - float(s2[j - 1]))
            dtw_mat[i, j] = cost + min(dtw_mat[i - 1, j],
                                        dtw_mat[i, j - 1],
                                        dtw_mat[i - 1, j - 1])
    return dtw_mat[n, m]


# ─────────────────────────────────────────────────────────────
# 1.  GROWING STAGE WEEK BOUNDARIES (from field data)
# ─────────────────────────────────────────────────────────────
# Each tuple = (week_start, week_end) inclusive, 1-indexed (1=Jan1)

STAGE_WEEKS = {

    'rice': {
        # Field data: plant DOY 181±18, harvest DOY 325, duration 144d
        'GS0': (24, 26),   # Land prep / paddock flooding  ← 2 wk before plant
        'GS1': (26, 30),   # Transplanting → early vegetative (4 wk)
        'GS2': (30, 38),   # Tillering → canopy closure     (8 wk)
        'GS3': (38, 45),   # Booting → grain filling        (7 wk)
        'GS4': (45, 49),   # Near-harvest → bare soil       (4 wk)
    },

    'corn': {
        # Field data: plant DOY 174±47, harvest DOY 272, duration 121d
        'GS0': (22, 25),   # Land preparation               (3 wk before plant)
        'GS1': (25, 28),   # Germination → early veg        (3 wk)
        'GS2': (28, 34),   # Rapid growth → canopy closure  (6 wk)
        'GS3': (34, 39),   # Tasseling → grain fill         (5 wk) ← brown/drying
        'GS4': (39, 42),   # Harvest → bare soil            (3 wk)
    },

    'cassava': {
        # Field data: plant DOY 118±53, duration ~298d (harvest next Feb)
        'GS0': (15, 17),   # Land preparation
        'GS1': (17, 23),   # Sprouting → early canopy       (6 wk)
        'GS2': (23, 36),   # Canopy development             (13 wk)
        'GS3': (36, 52),   # Storage root fill → maturation (16 wk, yr-end)
        'GS4': (1,  7),    # Harvest period (NEXT YEAR Jan–Feb)
    },

    'longan': {
        # Perennial — approximate seasonal cycles (literature-based)
        'GS1': (9,  16),   # Leaf flush / new growth        (Feb–Apr)
        'GS2': (16, 42),   # Active canopy growth           (Apr–Oct)
        'GS2_stress': (44, 50),  # WATER STRESS induction   (Nov–Dec) ← Kc=0
        'GS3': (50, 52),   # Flowering initiation           (Dec)
        'GS4': (1,  8),    # Fruit development (NEXT YEAR)
    },

    'rubber': {
        # Perennial — leaf phenology cycle
        'GS_defoliation': (1,  8),    # Leaf shedding (Jan–Feb)  ← SAR↑ bare soil
        'GS_leaf_flush':  (9,  16),   # New leaf sprouting       (Mar–Apr)
        'GS_mature':      (16, 52),   # Mature canopy (May–Dec)
    },
}


# ─────────────────────────────────────────────────────────────
# 2.  SAR VH BACKSCATTER TEMPLATES (dB)
#     คำอธิบาย: ค่า VH dB ทั่วไปของแต่ละ stage (4 สัปดาห์ต่อ window)
#     ต้อง calibrate กับข้อมูล SAR จริงจาก GEE ก่อน run DTW
# ─────────────────────────────────────────────────────────────

SAR_TEMPLATES_VH = {

    'rice': {
        # GS0: flooded/ploughed field → strong specular → VH ต่ำมาก
        # GS1: transplanted shoots   → backscatter เริ่มขึ้น
        # GS2: tillering/canopy      → VH สูงสุดช่วง canopy closure
        # GS3: grain fill → heading  → VH ลดลงเล็กน้อย (spike ช่วง heading)
        # GS4: harvest/senescence    → VH ลดลงเร็ว กลับเป็น bare soil
        'GS0': np.array([-20.0, -19.5, -19.0, -18.5]),
        'GS1': np.array([-18.0, -16.0, -14.0, -12.5]),
        'GS2': np.array([-11.5, -10.5, -10.0, -10.0]),
        'GS3': np.array([-10.5, -11.0, -12.0, -13.5]),
        'GS4': np.array([-15.0, -17.0, -18.5, -19.5]),
    },

    'corn': {
        # GS0: bare soil             → VH ต่ำ
        # GS1: germination           → เพิ่มขึ้นช้า
        # GS2: rapid growth          → VH สูงสุด (dense canopy)
        # GS3: tasseling/brown       → VH ลดฮวบ (leaves dry/brown) ← จุดที่งานเดิม classify ผิด
        # GS4: post-harvest          → กลับเป็น bare soil
        'GS0': np.array([-20.5, -20.0, -19.5, -18.5]),
        'GS1': np.array([-18.0, -16.5, -15.0, -13.5]),
        'GS2': np.array([-12.0, -11.0, -10.5, -10.5]),
        'GS3': np.array([-12.0, -14.0, -16.5, -18.5]),   # ← ลดเร็ว
        'GS4': np.array([-19.0, -19.5, -20.0, -20.0]),
    },

    'cassava': {
        # GS0: bare soil/ridge prep  → VH ต่ำ
        # GS1: sprouting             → เพิ่มช้า (sparse canopy)
        # GS2: canopy develop        → VH ขึ้นสูงปานกลาง (less dense than rice)
        # GS3: mature/root fill      → VH ค่อนข้างคงที่ (evergreen-like)
        # GS4: pre-harvest (next yr) → VH คงที่หรือลดเล็กน้อย
        'GS0': np.array([-20.0, -19.5, -19.0, -18.0]),
        'GS1': np.array([-17.5, -16.0, -14.5, -13.0]),
        'GS2': np.array([-12.0, -11.5, -11.0, -11.0]),
        'GS3': np.array([-11.0, -11.0, -11.0, -11.0]),   # ← คงที่
        'GS4': np.array([-11.5, -12.0, -13.5, -15.0]),
    },

    'longan': {
        # GS1: leaf flush            → VH ขึ้นเร็ว
        # GS2: mature canopy         → VH สูง คงที่ (dense evergreen)
        # GS2_stress: water stress   → เกษตรกรหยุดให้น้ำ, canopy ลดลงเล็กน้อย
        # GS3: flower initiation     → VH ต่ำลงเล็กน้อย
        # GS4: fruit dev (next year) → VH สูงขึ้นอีกครั้ง
        'GS1':       np.array([-13.0, -12.0, -11.0, -10.5]),
        'GS2':       np.array([-10.0, -10.0, -10.0, -10.0]),
        'GS2_stress':np.array([-11.0, -12.0, -12.5, -13.0]),  # ← signature สำคัญ
        'GS3':       np.array([-12.5, -12.0, -11.5, -11.0]),
        'GS4':       np.array([-10.5, -10.0,  -9.5,  -9.5]),
    },

    'rubber': {
        # GS_defoliation: Jan–Feb ← VH เหมือน bare soil, ทำให้ classify ผิดในงานเดิม
        # GS_leaf_flush: Mar–Apr   → VH ขึ้นเร็วมาก
        # GS_mature: May–Dec       → VH สูงคงที่ (dense canopy)
        'GS_defoliation': np.array([-18.5, -18.0, -17.5, -17.0]),  # ← งานเดิม confuse กับ bare soil
        'GS_leaf_flush':  np.array([-14.0, -12.0, -11.0, -10.5]),
        'GS_mature':      np.array([-10.0, -10.0, -10.0, -10.0]),
    },
}


# ─────────────────────────────────────────────────────────────
# 3.  FAO-56 Kc TABLE (Allen et al. 1998) + local adjustment
#     CF_local = 1.05 (humid subtropical, Phayao station)
#     → ต้อง recalculate จาก ERA5 actual RHmin, u2
# ─────────────────────────────────────────────────────────────

CF_LOCAL = 1.05

KC_FAO56 = {
    'rice':    {'GS0': 0.00, 'GS1': 1.15, 'GS2': 1.20, 'GS3': 1.05, 'GS4': 0.00},
    'corn':    {'GS0': 0.00, 'GS1': 0.30, 'GS2': 1.20, 'GS3': 0.35, 'GS4': 0.00},
    'cassava': {'GS0': 0.00, 'GS1': 0.30, 'GS2': 0.80, 'GS3': 1.10, 'GS4': 1.00},
    'longan':  {
        'GS1': 0.70, 'GS2': 0.85,
        'GS2_stress': 0.00,   # ← deliberate water stress = Kc 0
        'GS3': 0.90, 'GS4': 0.95,
    },
    'rubber':  {
        'GS_defoliation': 0.60,
        'GS_leaf_flush':  0.80,
        'GS_mature':      1.00,
    },
}


def get_kc(crop: str, stage: str, cf: float = CF_LOCAL) -> float:
    """Return Kc adjusted by local climate factor."""
    base = KC_FAO56.get(crop, {}).get(stage, 0.0)
    return round(base * cf, 3)


# ─────────────────────────────────────────────────────────────
# 4.  WEEK → STAGE LOOKUP TABLE (สร้าง look-up ทุกสัปดาห์ 1–52)
# ─────────────────────────────────────────────────────────────

def build_weekly_stage_lookup(stage_weeks: dict) -> pd.DataFrame:
    """
    Build a week→stage lookup for each crop.
    Returns DataFrame with columns: week, crop, stage, Kc
    """
    rows = []
    for crop, stages in stage_weeks.items():
        for week in range(1, 53):
            assigned = 'offseason'
            for stage, (ws, we) in stages.items():
                # Handle cassava GS4 that wraps to next year (we < ws)
                if ws <= we:
                    if ws <= week <= we:
                        assigned = stage
                        break
                else:   # wraps (e.g., GS4: week 1–7)
                    if week <= we or week >= ws:
                        assigned = stage
                        break
            rows.append({
                'crop': crop,
                'week': week,
                'stage': assigned,
                'Kc': get_kc(crop, assigned),
            })
    df = pd.DataFrame(rows)
    return df


weekly_kc = build_weekly_stage_lookup(STAGE_WEEKS)
pivot = weekly_kc.pivot_table(
    index='week', columns='crop', values='Kc', aggfunc='first'
)
print("=== WEEKLY Kc LOOKUP TABLE (sample weeks 1, 10, 20, 26, 30, 38, 45, 47, 50) ===")
sample_weeks = [1, 10, 17, 20, 26, 30, 34, 38, 42, 45, 47, 50, 52]
print(pivot.loc[pivot.index.isin(sample_weeks)].round(3).to_string())

weekly_kc.to_csv('kc_weekly_lookup_all_crops.csv', index=False)
print("\n✅ Saved: kc_weekly_lookup_all_crops.csv")


# ─────────────────────────────────────────────────────────────
# 5.  DTW CLASSIFICATION FUNCTION (ใช้กับ SAR time series จริง)
# ─────────────────────────────────────────────────────────────

def classify_stage_dtw(vh_window: np.ndarray,
                       crop: str,
                       templates: dict = SAR_TEMPLATES_VH) -> tuple:
    """
    Classify growing stage for a given crop using DTW.

    Parameters
    ----------
    vh_window : np.ndarray, shape (4,)
        VH backscatter (dB) for 4-week sliding window
    crop : str
        One of: 'rice', 'corn', 'cassava', 'longan', 'rubber'
    templates : dict
        SAR_TEMPLATES_VH

    Returns
    -------
    (best_stage: str, dtw_distance: float)
    """
    crop_templates = templates.get(crop, {})
    if not crop_templates:
        return 'unknown', float('inf')

    best_stage = None
    best_dist  = float('inf')
    for stage, template in crop_templates.items():
        # EDITED — was fastdtw(vh_window.reshape(-1,1), template.reshape(-1,1),
        #                      dist=euclidean); replaced with pure-numpy dtw_distance()
        dist = dtw_distance(vh_window, template)
        if dist < best_dist:
            best_dist  = dist
            best_stage = stage

    return best_stage, best_dist


# ─────────────────────────────────────────────────────────────
# 6.  APPLY TO SAR TIME SERIES (template — ใส่ path จริงของคุณ)
# ─────────────────────────────────────────────────────────────

def run_phenology_detection(sar_mean_vh_per_crop: dict,
                            window_size: int = 4) -> pd.DataFrame:
    """
    Apply DTW stage classification to SAR time series.

    Parameters
    ----------
    sar_mean_vh_per_crop : dict
        {crop: np.ndarray shape (n_weeks,)}
        Mean VH backscatter per crop per week
        (extracted from SAR stack masked by crop map)
    window_size : int
        Sliding window size (default 4 weeks)

    Returns
    -------
    DataFrame: week_idx, crop, stage, dtw_dist, Kc
    """
    results = []
    kc_lookup = weekly_kc.set_index(['crop','week'])['Kc'].to_dict()

    for crop, vh_series in sar_mean_vh_per_crop.items():
        n_weeks = len(vh_series)
        for i in range(n_weeks - window_size + 1):
            window = vh_series[i:i + window_size]
            if np.any(np.isnan(window)):          # skip empty weeks
                stage, dist = 'no_data', np.nan
            else:
                stage, dist = classify_stage_dtw(window, crop)

            week_1indexed = i + window_size        # centre of window
            kc_val = get_kc(crop, stage)

            results.append({
                'week_idx':    i,
                'week':        week_1indexed,
                'crop':        crop,
                'stage':       stage,
                'dtw_dist':    round(dist, 3) if not np.isnan(dist) else np.nan,
                'Kc':          kc_val,
            })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────
# 7.  DEMO — ทดสอบ DTW ด้วยข้อมูล synthetic ก่อน SAR จริงพร้อม
# ─────────────────────────────────────────────────────────────

print("\n=== DTW DEMO — synthetic rice time series (52 weeks) ===")

# สร้าง synthetic VH series สำหรับ rice ตาม stage boundaries
rice_synthetic_vh = np.array(
    [-19.0]*2 +          # GS0 wk 24–26
    [-17.0,-14.0,-13.0,-12.0]*1 +  # GS1 wk 26–30
    [-11.0,-10.5,-10.0,-10.0,-10.0,-10.0,-10.0,-10.0]*1 +  # GS2 wk 30–38
    [-10.5,-11.0,-12.0,-13.0,-13.5,-14.0,-14.0]*1 +        # GS3 wk 38–45
    [-15.0,-17.0,-18.5,-19.0]*1    # GS4 wk 45–49
)

demo_stages = []
for i in range(len(rice_synthetic_vh) - 3):
    window = rice_synthetic_vh[i:i+4]
    stage, dist = classify_stage_dtw(window, 'rice')
    demo_stages.append({'window_start': i, 'stage': stage, 'dtw_dist': round(dist,2)})

demo_df = pd.DataFrame(demo_stages)
print(demo_df.groupby('stage')['window_start'].agg(list).to_string())
print("\n✅ DTW classification working correctly")


# ─────────────────────────────────────────────────────────────
# 8.  PHENOLOGY SUMMARY TABLE (สำหรับ paper Table หรือ Figure 4)
# ─────────────────────────────────────────────────────────────

print("\n=== PHENOLOGY SUMMARY (for paper) ===")
summary_rows = []
for crop, stages in STAGE_WEEKS.items():
    for stage, (ws, we) in stages.items():
        kc = get_kc(crop, stage)
        # แปลง week กลับเป็น approximate month
        def wk_to_month(wk):
            months = ['Jan','Feb','Mar','Apr','May','Jun',
                      'Jul','Aug','Sep','Oct','Nov','Dec']
            return months[min(11, (wk-1)*7//30)]
        summary_rows.append({
            'Crop':          crop,
            'Stage':         stage,
            'Week start':    ws,
            'Week end':      we,
            'Approx. period':f"{wk_to_month(ws)}–{wk_to_month(we)}",
            'Kc (adjusted)': kc,
            'Data source':   'Field data' if crop in ['rice','corn','cassava']
                             else 'Literature',
        })

summary_df = pd.DataFrame(summary_rows)
print(summary_df.to_string(index=False))
summary_df.to_csv('phenology_stage_summary_for_paper.csv', index=False)
print("\n✅ Saved: phenology_stage_summary_for_paper.csv")
print("✅ Saved: kc_weekly_lookup_all_crops.csv")
print("\n📌 NEXT STEP: load SAR stack จริง → run run_phenology_detection()")


# ##############################################################################
# # PHASE 3.1 — ERA5-Land Download + FAO-56 Penman-Monteith ET0 (weekly)
# Source: `Phase3_step1_era5_download_et0.ipynb`
# ##############################################################################

"""
=============================================================
Phase 3 — Step 1: Download ERA5-Land + คำนวณ ET₀ รายสัปดาห์
Mae Na Rua Sub-District, Phayao (19.05°N, 99.80°E)
Period: 2020–2024
=============================================================
PREREQUISITES:
  pip install cdsapi xarray netCDF4 scipy pandas numpy

CDS API KEY SETUP (ทำครั้งเดียว):
  1. สร้างไฟล์ C:/Users/<username>/.cdsapirc  (Windows)
     หรือ ~/.cdsapirc  (Mac/Linux)
  2. ใส่เนื้อหา:
       url: https://cds.climate.copernicus.eu/api
       key: <your-api-key-here>
=============================================================
"""

# ── PART A: ตรวจสอบ API key ก่อน ─────────────────────────────
import cdsapi
import os

print("=== ตรวจสอบ CDS API ===")
try:
    c = cdsapi.Client()
    print("✅ CDS API พร้อมใช้งาน")
except Exception as e:
    print(f"❌ CDS API Error: {e}")
    print("""
แก้ไข:
1. สร้างไฟล์ C:/Users/<ชื่อผู้ใช้>/.cdsapirc
2. ใส่เนื้อหา (แทน YOUR_KEY ด้วย key จริง):
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_KEY
3. Restart kernel แล้วรันใหม่
    """)
    raise




import cdsapi
import zipfile
import os
import shutil

c = cdsapi.Client()

variables = [
    '2m_temperature', '2m_dewpoint_temperature',
    '10m_u_component_of_wind', '10m_v_component_of_wind',
    'surface_net_solar_radiation', 'surface_net_thermal_radiation',
    'total_precipitation',
]

DST_DIR = r'c:\Users\mpdox\Desktop\ETo'
os.makedirs(DST_DIR, exist_ok=True)

for year in [2020, 2021, 2022, 2023, 2024]:
    final_nc  = os.path.join(DST_DIR, f'era5_{year}.nc')
    temp_zip  = os.path.join(DST_DIR, f'era5_{year}_raw.zip')

    if os.path.exists(final_nc):
        size = os.path.getsize(final_nc)
        if size > 1_000_000:   # > 1 MB = สมบูรณ์
            print(f"⚡ {year}: มีอยู่แล้ว ({size/1e6:.1f} MB) — ข้าม")
            continue
        else:
            print(f"⚠️  {year}: ไฟล์เล็กเกินไป ({size:,} bytes) — re-download")
            os.remove(final_nc)

    print(f"\n📥 Downloading {year}...")
    c.retrieve(
        'reanalysis-era5-land',
        {
            'variable':     variables,
            'product_type': 'reanalysis',
            'year':         str(year),
            'month':        [str(m).zfill(2) for m in range(1, 13)],
            'day':          [str(d).zfill(2) for d in range(1, 32)],
            'time':         '12:00',
            'area':         [19.3, 99.5, 18.9, 100.1],
            'format':       'netcdf',
        },
        temp_zip   # ← บันทึกเป็น temp ก่อน
    )

    # ตรวจสอบว่าเป็น ZIP หรือ NC
    with open(temp_zip, 'rb') as f:
        header = f.read(4)

    if header[:2] == b'PK':   # ZIP
        print(f"  Unzip {year}...")
        with zipfile.ZipFile(temp_zip, 'r') as z:
            # extract data_0.nc แล้ว rename
            z.extract('data_0.nc', DST_DIR)
            os.rename(
                os.path.join(DST_DIR, 'data_0.nc'),
                final_nc
            )
        os.remove(temp_zip)
    else:
        # เป็น NC โดยตรง
        os.rename(temp_zip, final_nc)

    size = os.path.getsize(final_nc)
    print(f"  ✅ era5_{year}.nc saved ({size/1e6:.1f} MB)")



# ── ตรวจสอบทุกไฟล์ ────────────────────────────────────────────
DST_DIR = r'c:\Users\mpdox\Desktop\ETo'
os.makedirs(DST_DIR, exist_ok=True)

print("\n=== ไฟล์ที่ได้ ===")
for year in [2020, 2021, 2022, 2023, 2024]:
    path = os.path.join(DST_DIR, f'era5_{year}.nc')
    if os.path.exists(path):
        size = os.path.getsize(path)
        status = "✅" if size > 1_000_000 else "❌ เล็กเกินไป"
        print(f"  era5_{year}.nc : {size/1e6:.1f} MB  {status}")
    else:
        print(f"  era5_{year}.nc : ❌ ไม่พบ")

# ── ทดสอบเปิดไฟล์ ─────────────────────────────────────────────
print("\n=== ทดสอบเปิด era5_2020.nc ===")
import xarray as xr
ds = xr.open_dataset(
    os.path.join(DST_DIR, 'era5_2020.nc'),
    engine='netcdf4'
)
print("Variables :", list(ds.data_vars))
print("Time      :", str(ds.time.values[0])[:10],
      "→", str(ds.time.values[-1])[:10])
print("Lat       :", ds.latitude.values)
print("Lon       :", ds.longitude.values)
print("t2m sample:", float(ds['t2m'].isel(time=0).values.flat[0]), "K")
ds.close()
print("✅ ไฟล์ใช้งานได้")

import xarray as xr, os

DST_DIR = r'c:\Users\mpdox\Desktop\ETo'
os.makedirs(DST_DIR, exist_ok=True)

ds = xr.open_dataset(os.path.join(DST_DIR, 'era5_2020.nc'), engine='netcdf4')

print("Variables :", list(ds.data_vars))
print("Dimensions:", dict(ds.dims))
print("Coords    :", list(ds.coords))
print(ds)  # ดู full structure

import numpy as np
import xarray as xr
import pandas as pd
import os

# ── ค่าคงที่ ──────────────────────────────────────────────
ELEV_M   = 400.0   # ความสูงเฉลี่ยพื้นที่ศึกษา (เมตร) — ปรับตามจริง
ALPHA    = 0.23    # albedo (FAO-56 reference grass)
MJ_DAY   = 1e-6    # J → MJ

def kelvin_to_celsius(k):
    return k - 273.15

def saturation_vp(T_c):
    """es (kPa) จาก temperature (°C)"""
    return 0.6108 * np.exp(17.27 * T_c / (T_c + 237.3))

def slope_vp(T_c):
    """Δ (kPa/°C)"""
    return 4098 * saturation_vp(T_c) / (T_c + 237.3)**2

def psychrometric_const(elev_m):
    """γ (kPa/°C) จาก elevation"""
    P = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26  # kPa
    return 0.000665 * P

def wind_2m(u10, v10):
    """แปลง wind 10m → 2m (FAO-56 eq. 47)"""
    ws10 = np.sqrt(u10**2 + v10**2)
    return ws10 * (4.87 / np.log(67.8 * 10 - 5.42))

def compute_eto_daily(ds, elev_m=ELEV_M):
    """
    คำนวณ ETo (mm/day) จาก ERA5-Land dataset
    Input : xr.Dataset with valid_time, latitude, longitude
    Output: xr.DataArray ETo (mm/day)
    """
    # ── อุณหภูมิ ──────────────────────────────────────────
    T_c  = kelvin_to_celsius(ds['t2m'])          # °C
    Td_c = kelvin_to_celsius(ds['d2m'])          # °C dewpoint

    # ── Vapour pressure ───────────────────────────────────
    es = saturation_vp(T_c)                      # kPa
    ea = saturation_vp(Td_c)                     # kPa (actual)
    delta = slope_vp(T_c)                        # kPa/°C
    gamma = psychrometric_const(elev_m)          # kPa/°C (scalar)

    # ── Radiation → MJ/m²/day ─────────────────────────────
    Rs  =  ds['ssr'] * MJ_DAY                    # shortwave ↓
    Rnl = -ds['str'] * MJ_DAY                    # net longwave (ERA5 str เป็น negative → กลับเครื่องหมาย)
    Rns = (1 - ALPHA) * Rs                       # net shortwave
    Rn  = Rns - Rnl                              # net radiation
    G   = xr.zeros_like(Rn)                      # soil heat flux ≈ 0 (daily)

    # ── Wind 10m → 2m ─────────────────────────────────────
    u2 = wind_2m(ds['u10'], ds['v10'])

    # ── FAO-56 Penman-Monteith ────────────────────────────
    numerator   = (0.408 * delta * (Rn - G)
                   + gamma * (900 / (T_c + 273)) * u2 * (es - ea))
    denominator = delta + gamma * (1 + 0.34 * u2)
    ETo = numerator / denominator

    ETo = ETo.rename('ETo')
    ETo.attrs.update({'units': 'mm/day', 'long_name': 'Reference Evapotranspiration (FAO-56 PM)'})
    return ETo

# ── ทดสอบกับ 2020 ─────────────────────────────────────────
DST_DIR = r"c:\Users\mpdox\Desktop\ETo"   # ← แก้ path

ds2020 = xr.open_dataset(os.path.join(DST_DIR, 'era5_2020.nc'), engine='netcdf4')

ETo_2020 = compute_eto_daily(ds2020)
print(ETo_2020)
print("\nStats (spatial mean per day):")
print(ETo_2020.mean(['latitude','longitude']).to_series().describe().round(2))

import glob

YEARS = range(2020, 2024)

eto_list = []

for yr in YEARS:
    fpath = os.path.join(DST_DIR, f'era5_{yr}.nc')
    if not os.path.exists(fpath):
        print(f"⚠️  ไม่พบไฟล์: {fpath} — ข้าม")
        continue

    ds = xr.open_dataset(fpath, engine='netcdf4')
    eto = compute_eto_daily(ds)
    eto_list.append(eto)
    print(f"✅ {yr}  |  mean={float(eto.mean()):.2f}  min={float(eto.min()):.2f}  max={float(eto.max()):.2f}  mm/day")

# ── Concatenate ───────────────────────────────────────────
ETo_all = xr.concat(eto_list, dim='valid_time')
ETo_all = ETo_all.sortby('valid_time')

print(f"\nรวม : {len(ETo_all.valid_time)} days  "
      f"({str(ETo_all.valid_time.values[0])[:10]} → "
      f"{str(ETo_all.valid_time.values[-1])[:10]})")

# ── บันทึก ────────────────────────────────────────────────
out_path = os.path.join(DST_DIR, 'ETo_2020_2024.nc')
ETo_all.to_netcdf(out_path)
print(f"💾 บันทึกแล้ว: {out_path}")

import xarray as xr
import numpy as np
import pandas as pd
import os

# ════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════
DST_DIR  = r"c:\Users\mpdox\Desktop\ETo"   # ← แก้ path
YEARS    = range(2018, 2025)
ELEV_M   = 300.0
ALPHA    = 0.23
MJ_DAY   = 1e-6

# ════════════════════════════════════════════════════════════
# FUNCTIONS (เหมือนเดิม)
# ════════════════════════════════════════════════════════════
def kelvin_to_celsius(k):   return k - 273.15
def saturation_vp(T_c):     return 0.6108 * np.exp(17.27 * T_c / (T_c + 237.3))
def slope_vp(T_c):          return 4098 * saturation_vp(T_c) / (T_c + 237.3)**2
def psychrometric_const(e): P = 101.3*((293-0.0065*e)/293)**5.26; return 0.000665*P
def wind_2m(u10, v10):      return np.sqrt(u10**2+v10**2) * (4.87/np.log(67.8*10-5.42))

def compute_eto_daily(ds, elev_m=ELEV_M):
    T_c   = kelvin_to_celsius(ds['t2m'])
    Td_c  = kelvin_to_celsius(ds['d2m'])
    es    = saturation_vp(T_c)
    ea    = saturation_vp(Td_c)
    delta = slope_vp(T_c)
    gamma = psychrometric_const(elev_m)
    Rs    =  ds['ssr'] * MJ_DAY
    Rnl   = -ds['str'] * MJ_DAY
    Rn    = (1 - ALPHA) * Rs - Rnl
    u2    = wind_2m(ds['u10'], ds['v10'])
    ETo   = (0.408*delta*(Rn) + gamma*(900/(T_c+273))*u2*(es-ea)) / \
            (delta + gamma*(1+0.34*u2))
    return ETo, T_c, ea, es, u2, Rn

# ════════════════════════════════════════════════════════════
# STEP 1 — คำนวณ ETo ทุกปี → spatial mean → daily DataFrame
# ════════════════════════════════════════════════════════════
records = []

for yr in YEARS:
    fpath = os.path.join(DST_DIR, f'era5_{yr}.nc')
    if not os.path.exists(fpath):
        print(f"⚠️  ไม่พบ: {fpath}")
        continue

    ds = xr.open_dataset(fpath, engine='netcdf4')

    ETo, T_c, ea, es, u2, Rn = compute_eto_daily(ds)

    # spatial mean ทั้ง grid (5×7 points)
    sp = dict(latitude=ds.latitude, longitude=ds.longitude)
    def smean(da): return float(da.mean(['latitude','longitude']))

    for i, t in enumerate(ds['valid_time'].values):
        date = pd.Timestamp(t)
        T_i  = float(T_c.isel(valid_time=i).mean(['latitude','longitude']))
        ea_i = float(ea.isel(valid_time=i).mean(['latitude','longitude']))
        es_i = float(es.isel(valid_time=i).mean(['latitude','longitude']))
        u2_i = float(u2.isel(valid_time=i).mean(['latitude','longitude']))
        Rn_i = float(Rn.isel(valid_time=i).mean(['latitude','longitude']))
        et_i = float(ETo.isel(valid_time=i).mean(['latitude','longitude']))
        RH_i = min(100.0, (ea_i / es_i) * 100)
        VPD_i = max(0.0, es_i - ea_i)

        records.append({
            'date'      : date.date(),
            'year'      : date.year,
            'doy'       : date.day_of_year,
            'T_mean'    : round(T_i,   2),
            'RH_pct'    : round(RH_i,  1),
            'VPD_kPa'   : round(VPD_i, 4),
            'u2_ms'     : round(u2_i,  3),
            'Rn_MJ'     : round(Rn_i,  4),
            'ETo_mm_day': round(et_i,  3),
        })

    ds.close()
    print(f"✅ {yr}  ETo mean={np.mean([r['ETo_mm_day'] for r in records if r['year']==yr]):.2f} mm/day")

df_daily = pd.DataFrame(records)
df_daily['date'] = pd.to_datetime(df_daily['date'])

# ════════════════════════════════════════════════════════════
# STEP 2 — Aggregate รายสัปดาห์ (ISO week)
# ════════════════════════════════════════════════════════════
df_daily['week']     = df_daily['date'].dt.isocalendar().week.astype(int)
df_daily['iso_year'] = df_daily['date'].dt.isocalendar().year.astype(int)

# ใช้ iso_year แทน year เพื่อป้องกัน week 52/53 ข้ามปี
ET0_weekly = (
    df_daily
    .groupby(['iso_year', 'week'])
    .agg(
        ET0_mm_week = ('ETo_mm_day', 'sum'),
        T_mean      = ('T_mean',     'mean'),
        RH_pct      = ('RH_pct',     'mean'),
        VPD_kPa     = ('VPD_kPa',    'mean'),
        u2_ms       = ('u2_ms',      'mean'),
        Rn_MJ       = ('Rn_MJ',      'mean'),
        n_days      = ('ETo_mm_day', 'count'),
    )
    .reset_index()
    .rename(columns={'iso_year': 'year'})
    .round({'ET0_mm_week':2, 'T_mean':2, 'RH_pct':1,
            'VPD_kPa':4, 'u2_ms':3, 'Rn_MJ':4})
)

# กรองเฉพาะ week ที่มีข้อมูลครบ 7 วัน (ป้องกัน partial week ต้น/ท้ายปี)
ET0_weekly = ET0_weekly[ET0_weekly['n_days'] == 7].reset_index(drop=True)

# ════════════════════════════════════════════════════════════
# STEP 3 — Sanity Check
# ════════════════════════════════════════════════════════════
print("\n" + "═"*55)
print("SANITY CHECK — ETo Weekly")
print("═"*55)
print(f"ช่วงเวลา   : {ET0_weekly['year'].min()} W{ET0_weekly['week'].min():02d}"
      f" → {ET0_weekly['year'].max()} W{ET0_weekly['week'].max():02d}")
print(f"จำนวน weeks: {len(ET0_weekly)}")
print(f"\n{'Metric':<15} {'mm/week':>10} {'หมายเหตุ'}")
print("-"*55)
print(f"{'Mean':<15} {ET0_weekly['ET0_mm_week'].mean():>10.2f}  ควรอยู่ ~20–28 mm/week")
print(f"{'Std':<15} {ET0_weekly['ET0_mm_week'].std():>10.2f}")
print(f"{'Min':<15} {ET0_weekly['ET0_mm_week'].min():>10.2f}  wet season (ฝนตก)")
print(f"{'Max':<15} {ET0_weekly['ET0_mm_week'].max():>10.2f}  ควร < 50 mm/week")
print(f"{'Missing weeks':<15} {(ET0_weekly['n_days']<7).sum():>10}  ควร = 0")

# ตรวจ negative / outlier
neg = (ET0_weekly['ET0_mm_week'] < 0).sum()
ext = (ET0_weekly['ET0_mm_week'] > 55).sum()
print(f"{'Negative':<15} {neg:>10}  ควร = 0")
print(f"{'Extreme >55':<15} {ext:>10}  ควร = 0")

# Seasonal pattern check
ET0_weekly['season'] = ET0_weekly['week'].apply(
    lambda w: 'Dry(hot)' if 10<=w<=18 else ('Wet' if 22<=w<=40 else 'Dry(cool)'))
print("\nค่าเฉลี่ยตามฤดูกาล:")
print(ET0_weekly.groupby('season')['ET0_mm_week']
      .agg(['mean','min','max']).round(2).to_string())

# ════════════════════════════════════════════════════════════
# STEP 4 — ตรวจ gap (สัปดาห์ขาดหาย)
# ════════════════════════════════════════════════════════════
all_weeks = set()
for yr in ET0_weekly['year'].unique():
    for wk in range(1, 53):
        all_weeks.add((yr, wk))
existing = set(zip(ET0_weekly['year'], ET0_weekly['week']))
missing  = sorted(all_weeks - existing)
if missing:
    print(f"\n⚠️  Weeks ที่ขาดหาย ({len(missing)} weeks):")
    for y, w in missing[:10]: print(f"   {y} W{w:02d}")
else:
    print("\n✅ ไม่มี week ขาดหาย")

# ════════════════════════════════════════════════════════════
# STEP 5 — Export
# ════════════════════════════════════════════════════════════
df_daily.to_csv('ET0_daily_phayao_2018_2024.csv', index=False)
ET0_weekly[['year','week','ET0_mm_week','T_mean','RH_pct',
            'VPD_kPa','u2_ms','Rn_MJ','n_days']].to_csv(
    'ET0_weekly_phayao_2018_2024.csv', index=False)

print("\n✅ Saved: ET0_daily_phayao_2018_2024.csv")
print("✅ Saved: ET0_weekly_phayao_2018_2024.csv")
print(f"\nตัวอย่างข้อมูล (week 26–30 ปี 2022 = wet season peak):")
sample = ET0_weekly[(ET0_weekly['year']==2022) &
                    (ET0_weekly['week'].between(26,30))]
print(sample[['year','week','ET0_mm_week','T_mean',
              'RH_pct','VPD_kPa']].to_string(index=False))

print("\n📌 NEXT: รัน phase3_step2_chirps_rainfall.py")


# ##############################################################################
# # PHASE 3.2 — CHIRPS Rainfall Download + Effective Precipitation
# Source: `Phase3_step2_chirps_rainfall.ipynb`
# NOTE: This script's own internal 'PART C: merge ET0+Rainfall' section at the
# end is SUPERSEDED by the dedicated Step 2C (FINAL) merge script below
# (that final version adds year-boundary-week imputation this one lacks).
# Kept here verbatim for the CHIRPS-download + P_eff portion.
# ##############################################################################

"""
=============================================================
Phase 3 — Step 2: Download CHIRPS Rainfall + คำนวณ P_eff
Mae Na Rua Sub-District, Phayao (19.05°N, 99.80°E)
Period: 2020–2024
=============================================================
PREREQUISITES:
  pip install requests pandas numpy

CHIRPS: Climate Hazards Group InfraRed Precipitation with Station data
  - Resolution: 0.05° (~5.5 km)
  - Free, no API key required
  - URL: https://data.chc.ucsb.edu/products/CHIRPS-2.0/
=============================================================
"""

import requests
import numpy as np
import pandas as pd
from pathlib import Path
import os

# ── พิกัด ต.แม่นาเรือ ─────────────────────────────────────────
TARGET_LAT = 19.05
TARGET_LON = 99.80

# ── Download CHIRPS daily (ปี 2020–2024) ─────────────────────
# CHIRPS ใช้ GeoTIFF รายวัน → extract ค่าที่พิกัดด้วย rasterio

print("=== Download CHIRPS Rainfall ===")
print("Method: GEE export (แนะนำ) หรือ rasterio extract จาก GeoTIFF")

# ── วิธีที่ 1: ใช้ข้อมูลจาก GEE ที่ export ไว้แล้ว ────────────
# ถ้ามีไฟล์ CHIRPS_daily_maenaerua.csv จาก GEE แล้ว ใช้ทางนี้

CHIRPS_FROM_GEE = 'CHIRPS_daily_maenaerua.csv'

if os.path.exists(CHIRPS_FROM_GEE):
    print(f"✅ พบไฟล์ GEE: {CHIRPS_FROM_GEE}")
    rain = pd.read_csv(CHIRPS_FROM_GEE)
    print(f"Columns: {rain.columns.tolist()}")
    print(rain.head(3))

else:
    print(f"ไม่พบ {CHIRPS_FROM_GEE} — ใช้ CHIRPS API แทน")

    # ── วิธีที่ 2: Download CHIRPS ผ่าน UCSB server ────────────
    print("\nDownloading CHIRPS daily GeoTIFF...")

    try:
        import rasterio
        from rasterio.crs import CRS
        import io

        records = []

        for year in range(2020, 2025):
            print(f"  Year {year}...", end='', flush=True)
            for month in range(1, 13):
                # จำนวนวันในเดือน
                import calendar
                n_days = calendar.monthrange(year, month)[1]

                for day in range(1, n_days+1):
                    date_str = f"{year}.{month:02d}.{day:02d}"
                    url = (
                        f"https://data.chc.ucsb.edu/products/CHIRPS-2.0/"
                        f"global_daily/tifs/p05/{year}/"
                        f"chirps-v2.0.{date_str}.tif.gz"
                    )

                    try:
                        resp = requests.get(url, timeout=30)
                        if resp.status_code == 200:
                            import gzip
                            with gzip.open(io.BytesIO(resp.content)) as gz:
                                data = gz.read()
                            with rasterio.open(io.BytesIO(data)) as src:
                                val = list(src.sample([(TARGET_LON, TARGET_LAT)]))[0][0]
                            val = max(0, float(val)) if val != -9999 else 0.0
                        else:
                            val = np.nan
                    except:
                        val = np.nan

                    records.append({
                        'date': f"{year}-{month:02d}-{day:02d}",
                        'precipitation': val
                    })

            print(" done")

        rain = pd.DataFrame(records)
        rain.to_csv('CHIRPS_daily_raw.csv', index=False)
        print("✅ Saved: CHIRPS_daily_raw.csv")

    except ImportError:
        print("❌ ต้องติดตั้ง rasterio: pip install rasterio")
        raise


# ── แปลง format ให้ตรงกัน ─────────────────────────────────────
if 'date' not in rain.columns:
    # GEE export อาจมีชื่อ column ต่างกัน
    print("\nColumns ที่มี:", rain.columns.tolist())
    # ปรับตาม column จริง
    date_col  = [c for c in rain.columns if 'date' in c.lower()][0]
    rain_col  = [c for c in rain.columns if any(
                 x in c.lower() for x in ['rain','prec','chirps','total'])][0]
    rain = rain.rename(columns={date_col:'date', rain_col:'precipitation'})

rain['date']          = pd.to_datetime(rain['date'])
rain['precipitation'] = pd.to_numeric(rain['precipitation'], errors='coerce').fillna(0)
rain['precipitation'] = rain['precipitation'].clip(lower=0)

print(f"\nRainfall daily stats (mm/day):")
print(rain['precipitation'].describe().round(2))

# ── คำนวณ P_eff (USDA SCS Method) ────────────────────────────
# P_eff = 0.8 × P_week  (สำหรับ paddy field)
# สำหรับ upland crops: P_eff = max(0, P_week - 5) * 0.85

rain['year'] = rain['date'].dt.year
rain['week'] = rain['date'].dt.isocalendar().week.astype(int)

P_weekly = rain.groupby(['year','week']).agg(
    P_mm_week = ('precipitation', 'sum'),
    n_days    = ('precipitation', 'count'),
).reset_index()

# คำนวณ P_eff สองวิธี
P_weekly['P_eff_paddy']  = P_weekly['P_mm_week'] * 0.8   # paddy/rice
P_weekly['P_eff_upland'] = (                               # upland crops
    np.maximum(0, P_weekly['P_mm_week'] - 5) * 0.85
)

print(f"\nWeekly rainfall stats:")
print(P_weekly['P_mm_week'].describe().round(2))

# ── Sanity check ──────────────────────────────────────────────
print("\n=== Sanity Check ===")
annual_rain = P_weekly.groupby('year')['P_mm_week'].sum()
print("ปริมาณฝนรายปี (mm/year) — คาดหวัง 1,000–1,400 mm สำหรับพะเยา:")
print(annual_rain.round(0).to_string())

wet_dry = P_weekly.groupby(
    P_weekly['week'].apply(lambda w:
        'Wet (wk 18–44)' if 18<=w<=44 else 'Dry (wk 1–17, 45–52)')
)['P_mm_week'].mean()
print("\nค่าเฉลี่ยฝนต่อสัปดาห์ แยก season:")
print(wet_dry.round(1).to_string())

# ── Export ────────────────────────────────────────────────────
P_weekly.to_csv('CHIRPS_weekly_phayao_2020_2024.csv', index=False)
print("\n✅ Saved: CHIRPS_weekly_phayao_2020_2024.csv")
print(f"   Columns: {P_weekly.columns.tolist()}")


# ── PART C: รวม ET₀ + Rainfall เป็น climate_weekly ───────────
print("\n=== รวม ET₀ + Rainfall ===")

ET0_file = 'ET0_weekly_phayao_2020_2024.csv'
if os.path.exists(ET0_file):
    ET0 = pd.read_csv(ET0_file)
    climate = ET0.merge(P_weekly, on=['year','week'], how='left')
    climate['P_mm_week'] = climate['P_mm_week'].fillna(0)

    # คำนวณ deficit (ET₀ - P) — ค่าบวก = ต้องการน้ำเพิ่ม
    climate['deficit_mm'] = climate['ET0_mm_week'] - climate['P_eff_paddy']

    # SPI-4 (4-week Standardized Precipitation Index)
    climate = climate.sort_values(['year','week']).reset_index(drop=True)
    climate['P_4week'] = climate['P_mm_week'].rolling(4, min_periods=4).sum()
    from scipy.stats import zscore
    climate['SPI_4'] = climate.groupby('week')['P_4week'].transform(
        lambda x: zscore(x, ddof=1) if len(x)>1 else 0
    )

    climate.to_csv('climate_weekly_phayao_2020_2024.csv', index=False)
    print("✅ Saved: climate_weekly_phayao_2020_2024.csv")
    print(f"   Rows: {len(climate)} | Columns: {climate.columns.tolist()}")

    print("\nSample (week 26–30, 2022 = wet season peak):")
    sample = climate[(climate['year']==2022) & (climate['week'].between(26,30))]
    print(sample[['year','week','ET0_mm_week','P_mm_week',
                  'P_eff_paddy','deficit_mm']].to_string(index=False))
else:
    print(f"⚠️ ไม่พบ {ET0_file} — รัน phase3_step1_era5_download_ET0.py ก่อน")

print("\n📌 NEXT STEP: zone delineation → คำนวณ NIR_A และ GID_B")


# ##############################################################################
# # PHASE 3.3 — Step 2C (FINAL): Merge ET0 + CHIRPS -> climate_weekly_phayao_2020_2024.csv
# Source: `Phase_3_-_Merge_ET0___CHIRPS_-_climate_weekly.ipynb`
# This is the authoritative merge step (supersedes the merge inside the CHIRPS
# script above). Produces SPI-4, drought_flag, aridity index, and imputes 5
# year-boundary CHIRPS weeks via week-level medians.
# ##############################################################################

# ════════════════════════════════════════════════════════════
# Phase 3 — Step 2C (FINAL): Merge ET₀ + CHIRPS → climate_weekly
# Mae Na Rua Sub-District, Phayao | Period: 2020–2024
# ════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from scipy.stats import zscore

# ════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════
ET0_FILE    = r'ET0_weekly_phayao_2020_2024.csv'
CHIRPS_FILE = r'CHIRPS_weekly_phayao_2020_2024.csv'
OUT_FILE    = r'climate_weekly_phayao_2020_2024.csv'

# ════════════════════════════════════════════════════════════
# STEP 1 — โหลดและกรอง partial weeks
# ════════════════════════════════════════════════════════════
print("="*55)
print("STEP 1 — โหลดข้อมูล")
print("="*55)

ET0 = pd.read_csv(ET0_FILE)
P   = pd.read_csv(CHIRPS_FILE)

ET0 = ET0[ET0['n_days'] == 7].reset_index(drop=True)
P   = P  [P  ['n_days'] == 7].reset_index(drop=True)

print(f"ET₀   : {len(ET0)} weeks  {ET0.columns.tolist()}")
print(f"CHIRPS: {len(P)} weeks  {P.columns.tolist()}")

# ════════════════════════════════════════════════════════════
# STEP 2 — ตรวจและ impute weeks ที่ CHIRPS ขาดหาย
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 2 — ตรวจ + Impute CHIRPS weeks ที่ขาด")
print("="*55)

et0_keys = set(zip(ET0['year'], ET0['week']))
p_keys   = set(zip(P['year'],   P['week']))
missing  = sorted(et0_keys - p_keys)

print(f"ET₀ weeks   : {len(et0_keys)}")
print(f"CHIRPS weeks: {len(p_keys)}")
print(f"ขาด {len(missing)} weeks:")

# week-level median จากข้อมูลที่มี
P_median = (P.groupby('week')[['P_mm_week','P_eff_paddy','P_eff_upland']]
             .median().reset_index())

imputed_rows = []
for y, w in missing:
    med = P_median[P_median['week'] == w]
    if len(med) > 0:
        row = {
            'year'        : y,
            'week'        : w,
            'P_mm_week'   : round(float(med['P_mm_week'].values[0]),   3),
            'P_eff_paddy' : round(float(med['P_eff_paddy'].values[0]), 3),
            'P_eff_upland': round(float(med['P_eff_upland'].values[0]),3),
            'n_days'      : 7,
            'imputed'     : 1,
        }
    else:
        row = {'year':y, 'week':w, 'P_mm_week':0.0,
               'P_eff_paddy':0.0, 'P_eff_upland':0.0,
               'n_days':7, 'imputed':1}
    imputed_rows.append(row)
    print(f"  Imputed {y} W{w:02d} → P = {row['P_mm_week']:.1f} mm (week median)")

P['imputed'] = 0
P_full = (pd.concat([P, pd.DataFrame(imputed_rows)], ignore_index=True)
           .sort_values(['year','week'])
           .reset_index(drop=True))

# ════════════════════════════════════════════════════════════
# STEP 3 — Merge
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 3 — Merge ET₀ + Rainfall")
print("="*55)

climate = ET0.merge(
    P_full[['year','week','P_mm_week','P_eff_paddy',
            'P_eff_upland','imputed']],
    on=['year','week'],
    how='inner'
).sort_values(['year','week']).reset_index(drop=True)

print(f"หลัง merge: {len(climate)} weeks  "
      f"({climate['year'].min()} W{climate['week'].min():02d} "
      f"→ {climate['year'].max()} W{climate['week'].max():02d})")

# ════════════════════════════════════════════════════════════
# STEP 4 — Derived Variables
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 4 — Derived Variables")
print("="*55)

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

print("Variables ที่คำนวณ:")
print(climate[['deficit_paddy_mm','deficit_upland_mm',
               'P_4week','SPI_4','drought_flag','AI_week']]
      .describe().round(2).to_string())

# ════════════════════════════════════════════════════════════
# STEP 5 — Sanity Check
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 5 — Sanity Check")
print("="*55)

checks = {
    'ET₀ < 0'         : (climate['ET0_mm_week'] < 0).sum(),
    'P < 0'           : (climate['P_mm_week'] < 0).sum(),
    'P_eff > P'       : (climate['P_eff_paddy'] > climate['P_mm_week']+0.01).sum(),
    'AI_week > 10'    : (climate['AI_week'] > 10).sum(),
    'SPI_4 NaN'       : climate['SPI_4'].isna().sum(),
    'deficit NaN'     : climate['deficit_paddy_mm'].isna().sum(),
    'imputed rows'    : int(climate['imputed'].sum()),
    'total weeks'     : len(climate),
}
all_pass = True
for k, v in checks.items():
    if k == 'imputed rows':
        flag = '📌'
    elif k == 'total weeks':
        flag = '📊'
    else:
        flag = '✅' if v == 0 else '❌'
        if v != 0 and k not in ('imputed rows','total weeks'):
            all_pass = False
    print(f"  {flag}  {k:<22}: {v}")

print(f"\n{'✅ All checks passed!' if all_pass else '❌ มี issue — ตรวจสอบก่อนเดินหน้า'}")

# Seasonal pattern
climate['season'] = climate['week'].apply(
    lambda w: 'Dry-hot(W10-18)' if 10<=w<=18
    else ('Wet(W19-44)' if 19<=w<=44 else 'Dry-cool'))

print("\nค่าเฉลี่ยตามฤดูกาล:")
print(climate.groupby('season')[
    ['ET0_mm_week','P_mm_week','deficit_paddy_mm','AI_week']
].mean().round(2).to_string())

# Annual balance
print("\nAnnual water balance:")
ann = climate.groupby('year')[['ET0_mm_week','P_mm_week']].sum().round(0)
ann['status'] = (ann['ET0_mm_week'] > ann['P_mm_week']).map(
    {True:'⚠️  drought', False:'✅ sufficient'})
print(ann.to_string())

# Drought summary
n_dr = climate['drought_flag'].sum()
print(f"\nDrought weeks (SPI-4 < −1): {n_dr} / {len(climate)} "
      f"({n_dr/len(climate)*100:.1f}%)")

# ════════════════════════════════════════════════════════════
# STEP 6 — Export
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 6 — Export")
print("="*55)

out_cols = [
    'year','week',
    'ET0_mm_week','T_mean','RH_pct','VPD_kPa','u2_ms','Rn_MJ',
    'P_mm_week','P_eff_paddy','P_eff_upland',
    'deficit_paddy_mm','deficit_upland_mm',
    'P_4week','SPI_4','drought_flag','AI_week',
    'imputed','n_days'
]
climate[out_cols].to_csv(OUT_FILE, index=False)

print(f"✅ Saved : {OUT_FILE}")
print(f"   Rows  : {len(climate)} | Columns: {len(out_cols)}")
print(f"   Columns: {out_cols}")

# ════════════════════════════════════════════════════════════
# STEP 7 — Sample output
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 7 — Sample Output")
print("="*55)

view_cols = ['year','week','ET0_mm_week','P_mm_week',
             'P_eff_paddy','deficit_paddy_mm','SPI_4',
             'drought_flag','AI_week','imputed']

print("\nWet season peak (W26–30, 2022):")
s1 = climate[(climate['year']==2022) & (climate['week'].between(26,30))]
print(s1[view_cols].to_string(index=False))

print("\nDry season (W10–14, 2023 — drought year):")
s2 = climate[(climate['year']==2023) & (climate['week'].between(10,14))]
print(s2[view_cols].to_string(index=False))

print("\nImputed rows:")
imp = climate[climate['imputed']==1]
print(imp[view_cols].to_string(index=False))

print("\n📌 NEXT: zone delineation → คำนวณ NIR_A และ GIR_B")

import pandas as pd
import numpy as np
from scipy.stats import zscore

ET0_FILE    = r'ET0_weekly_phayao_2020_2024.csv'
CHIRPS_FILE = r'CHIRPS_weekly_phayao_2020_2024.csv'
OUT_FILE    = r'climate_weekly_phayao_2020_2024.csv'

ET0 = pd.read_csv(ET0_FILE)
P   = pd.read_csv(CHIRPS_FILE)

ET0 = ET0[ET0['n_days'] == 7].reset_index(drop=True)
P   = P  [P  ['n_days'] == 7].reset_index(drop=True)

# ════════════════════════════════════════════════════════════
# FIX 1 — ตรวจหา weeks ที่ CHIRPS ขาดหาย
# ════════════════════════════════════════════════════════════
print("="*55)
print("FIX 1 — ตรวจ weeks ที่ขาดหาย")
print("="*55)

et0_keys = set(zip(ET0['year'], ET0['week']))
p_keys   = set(zip(P['year'],   P['week']))
missing  = sorted(et0_keys - p_keys)

print(f"ET₀ weeks : {len(et0_keys)}")
print(f"CHIRPS weeks: {len(p_keys)}")
print(f"CHIRPS ขาด {len(missing)} weeks:")
for y, w in missing:
    print(f"  {y} W{w:02d}")

# ════════════════════════════════════════════════════════════
# FIX 2 — Impute weeks ที่ขาด ด้วย median ของ week เดียวกัน
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("FIX 2 — Impute CHIRPS ที่ขาด")
print("="*55)

# สร้าง week-level median จากข้อมูลที่มี
P_median = (P.groupby('week')[['P_mm_week','P_eff_paddy','P_eff_upland']]
             .median().reset_index())

imputed_rows = []
for y, w in missing:
    med = P_median[P_median['week'] == w]
    if len(med) > 0:
        row = {
            'year'        : y,
            'week'        : w,
            'P_mm_week'   : round(float(med['P_mm_week'].values[0]),   3),
            'P_eff_paddy' : round(float(med['P_eff_paddy'].values[0]), 3),
            'P_eff_upland': round(float(med['P_eff_upland'].values[0]),3),
            'n_days'      : 7,
            'imputed'     : 1,
        }
    else:
        row = {'year':y,'week':w,'P_mm_week':0,'P_eff_paddy':0,
               'P_eff_upland':0,'n_days':7,'imputed':1}
    imputed_rows.append(row)
    print(f"  Imputed {y} W{w:02d} → P={row['P_mm_week']:.1f} mm")

P['imputed'] = 0
P_full = pd.concat([P, pd.DataFrame(imputed_rows)], ignore_index=True)
P_full = P_full.sort_values(['year','week']).reset_index(drop=True)

# ════════════════════════════════════════════════════════════
# MERGE
# ════════════════════════════════════════════════════════════
climate = ET0.merge(
    P_full[['year','week','P_mm_week','P_eff_paddy',
            'P_eff_upland','imputed']],
    on=['year','week'], how='inner'
).sort_values(['year','week']).reset_index(drop=True)

print(f"\nหลัง impute + merge: {len(climate)} weeks")

# ════════════════════════════════════════════════════════════
# DERIVED VARIABLES (แก้ AI_week)
# ════════════════════════════════════════════════════════════
climate['deficit_paddy_mm']  = (climate['ET0_mm_week']
                                 - climate['P_eff_paddy']).round(2)
climate['deficit_upland_mm'] = (climate['ET0_mm_week']
                                 - climate['P_eff_upland']).round(2)

climate['P_4week'] = climate['P_mm_week'].rolling(4, min_periods=4).sum()

climate['SPI_4'] = (
    climate.groupby('week')['P_4week']
    .transform(lambda x: zscore(x, ddof=1) if len(x) > 1 else 0.0)
    .round(3)
)

climate['drought_flag'] = (climate['SPI_4'] < -1.0).astype(int)

# FIX: AI_week — cap ที่ 10 (ค่า > 10 หมายถึง extreme dry แล้ว)
climate['AI_week'] = (
    climate['ET0_mm_week'] / (climate['P_mm_week'] + 0.001)
).clip(upper=10).round(3)

# ════════════════════════════════════════════════════════════
# SANITY CHECK
# ════════════════════════════════════════════════════════════
print("\n" + "="*55)
print("SANITY CHECK (final)")
print("="*55)

checks = {
    'ET₀ < 0'       : (climate['ET0_mm_week'] < 0).sum(),
    'P < 0'         : (climate['P_mm_week'] < 0).sum(),
    'P_eff > P'     : (climate['P_eff_paddy'] > climate['P_mm_week']+0.01).sum(),
    'AI_week > 10'  : (climate['AI_week'] > 10).sum(),
    'SPI_4 NaN'     : climate['SPI_4'].isna().sum(),
    'imputed rows'  : climate['imputed'].sum(),
}
for k, v in checks.items():
    flag = '✅' if v == 0 else '⚠️'
    print(f"  {flag}  {k:<20}: {v}")

print("\nSeasonal means:")
climate['season'] = climate['week'].apply(
    lambda w: 'Dry-hot(10-18)' if 10<=w<=18
    else ('Wet(19-44)' if 19<=w<=44 else 'Dry-cool'))
print(climate.groupby('season')[
    ['ET0_mm_week','P_mm_week','deficit_paddy_mm','AI_week']
].mean().round(2).to_string())

print("\nAnnual balance:")
ann = climate.groupby('year')[['ET0_mm_week','P_mm_week']].sum().round(0)
ann['status'] = (ann['ET0_mm_week'] > ann['P_mm_week']).map(
    {True:'⚠️ drought', False:'✅ sufficient'})
print(ann.to_string())

# ════════════════════════════════════════════════════════════
# EXPORT
# ════════════════════════════════════════════════════════════
out_cols = [
    'year','week',
    'ET0_mm_week','T_mean','RH_pct','VPD_kPa','u2_ms','Rn_MJ',
    'P_mm_week','P_eff_paddy','P_eff_upland',
    'deficit_paddy_mm','deficit_upland_mm',
    'P_4week','SPI_4','drought_flag','AI_week',
    'imputed','n_days'
]
climate[out_cols].to_csv(OUT_FILE, index=False)
print(f"\n✅ Saved: {OUT_FILE}")
print(f"   Rows: {len(climate)} | Columns: {len(out_cols)}")

print("\n📌 NEXT: zone delineation → คำนวณ NIR_A และ GIR_B")


# ##############################################################################
# # PHASE 3.4 — Zone Crop-Area Extraction + Weekly Water Demand (NIR_A / GIR_B)
# Source: `crop_area_per_zone.ipynb`
# Produces `crop_area_per_zone.csv` then `water_demand_weekly_dual_zone.csv`
# (the Phase 4 modeling target), using static 2020 RF crop map v3b + Kc lookup,
# IE = 0.75.
# ##############################################################################

import rasterio
import numpy as np
import geopandas as gpd
import pandas as pd
from rasterio.mask import mask
from shapely.geometry import mapping
import os

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════
CROP_MAP_FILE = r'D:\University of Phayao\เอกสารการเรียน\Paper 2\Revise\ML\crop_map_v3b_2020.tif' 
ZONE_A_FILE   = r'D:\University of Phayao\เอกสารการเรียน\Paper 2\Revise\ML\zone_a_rainfed.shp'
ZONE_B_FILE   = r'D:\University of Phayao\เอกสารการเรียน\Paper 2\Revise\ML\zone_b_irrigated.shp'
OUT_DIR       = r'D:\University of Phayao\เอกสารการเรียน\Paper 2\Revise\ML\output'

CLASS_LABELS  = {0:'rice', 1:'corn', 2:'cassava', 3:'longan', 4:'etc'}
NODATA_VAL    = 255   # จาก inspect เดิม

# ════════════════════════════════════════════════════════
# STEP 1 — โหลด zones
# ════════════════════════════════════════════════════════
zone_a = gpd.read_file(ZONE_A_FILE)
zone_b = gpd.read_file(ZONE_B_FILE)

with rasterio.open(CROP_MAP_FILE) as src:
    crop_crs = src.crs
    pixel_area_m2 = abs(src.res[0] * src.res[1])  # 20×20 = 400 m²

print(f"Pixel area: {pixel_area_m2} m² ({pixel_area_m2/10000:.4f} ha)")

# Reproject zones ให้ตรงกับ crop map (ควรเป็น EPSG:32647 เหมือนกัน)
zone_a = zone_a.to_crs(crop_crs)
zone_b = zone_b.to_crs(crop_crs)

# ════════════════════════════════════════════════════════
# STEP 2 — Extract crop pixels ต่อ zone
# ════════════════════════════════════════════════════════
def extract_crop_area(zone_gdf, zone_name, crop_tif, class_labels, nodata=255):
    """Mask raster ด้วย zone polygon → นับ pixels ต่อ class"""
    geoms = [mapping(g) for g in zone_gdf.geometry if g is not None]

    with rasterio.open(crop_tif) as src:
        masked, _ = mask(src, geoms, crop=True, filled=True,
                         nodata=nodata, all_touched=False)
        data = masked[0]

    total_valid = np.sum(data != nodata)
    rows = []
    for val, name in class_labels.items():
        n_px   = int(np.sum(data == val))
        area_m2 = n_px * pixel_area_m2
        rows.append({
            'zone'      : zone_name,
            'crop_id'   : val,
            'crop'      : name,
            'n_pixels'  : n_px,
            'area_m2'   : area_m2,
            'area_ha'   : round(area_m2 / 10000, 2),
            'area_km2'  : round(area_m2 / 1e6,   4),
            'pct_zone'  : round(n_px / total_valid * 100, 1) if total_valid > 0 else 0,
        })
    return pd.DataFrame(rows), total_valid

print("\n=== STEP 2 — Extract crop area per zone ===")
df_a, valid_a = extract_crop_area(zone_a, 'A', CROP_MAP_FILE, CLASS_LABELS)
df_b, valid_b = extract_crop_area(zone_b, 'B', CROP_MAP_FILE, CLASS_LABELS)

crop_area = pd.concat([df_a, df_b], ignore_index=True)

# ════════════════════════════════════════════════════════
# STEP 3 — Sanity Check
# ════════════════════════════════════════════════════════
print("\n=== STEP 3 — Sanity Check ===")
print("\nCrop area per zone (ha):")
pivot = crop_area.pivot_table(
    index='crop', columns='zone',
    values=['area_ha','pct_zone'], aggfunc='sum'
).round(2)
print(pivot.to_string())

# ตรวจ total area สมเหตุสมผลไหม
total_a_ha = df_a['area_ha'].sum()
total_b_ha = df_b['area_ha'].sum()
print(f"\nZone A valid crop pixels: {valid_a:,} → {total_a_ha:.1f} ha")
print(f"Zone B valid crop pixels: {valid_b:,} → {total_b_ha:.1f} ha")
print(f"Zone A from shapefile   : {zone_a.geometry.area.sum()/10000:.1f} ha")
print(f"Zone B from shapefile   : {zone_b.geometry.area.sum()/10000:.1f} ha")

# ตรวจ dominant crop ต่อ zone (ควรสมเหตุสมผลตามภูมิศาสตร์)
print("\nDominant crop per zone:")
for zn, grp in crop_area.groupby('zone'):
    top = grp.nlargest(1, 'area_ha').iloc[0]
    print(f"  Zone {zn}: {top['crop']} ({top['area_ha']:.1f} ha, {top['pct_zone']:.1f}%)")

# ════════════════════════════════════════════════════════
# STEP 4 — สร้าง area_dict สำหรับใช้ใน demand calculation
# ════════════════════════════════════════════════════════
# Format ที่ Step 13 ต้องการ: {'rice': m², 'corn': m², ...}
area_zone_a = dict(zip(df_a['crop'], df_a['area_m2']))
area_zone_b = dict(zip(df_b['crop'], df_b['area_m2']))

print("\narea_zone_a (m²):")
for k, v in area_zone_a.items():
    print(f"  '{k}': {v:,.0f}")

print("\narea_zone_b (m²):")
for k, v in area_zone_b.items():
    print(f"  '{k}': {v:,.0f}")

# ════════════════════════════════════════════════════════
# STEP 5 — Export
# ════════════════════════════════════════════════════════
crop_area.to_csv(os.path.join(OUT_DIR, 'crop_area_per_zone.csv'), index=False)
print(f"\n✅ Saved: crop_area_per_zone.csv")
print(f"   Rows: {len(crop_area)} | Columns: {crop_area.columns.tolist()}")
print("\n📌 NEXT: Step 13 → คำนวณ NIR_A และ GIR_B รายสัปดาห์")

import pandas as pd
import numpy as np
import os

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════
CLIMATE_FILE  = r'climate_weekly_phayao_2020_2024.csv'
KC_FILE       = r'kc_weekly_lookup_all_crops.csv'
OUT_DIR       = r'D:\University of Phayao\เอกสารการเรียน\Paper 2\Revise\ML\output'

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

IE = 0.90   # Irrigation efficiency (FAO-56 surface irrigation)

# ════════════════════════════════════════════════════════
# STEP 1 — โหลดข้อมูล
# ════════════════════════════════════════════════════════
print("="*55)
print("STEP 1 — โหลดข้อมูล")
print("="*55)

climate = pd.read_csv(CLIMATE_FILE)
kc      = pd.read_csv(KC_FILE)

print(f"climate: {len(climate)} weeks | cols: {climate.columns.tolist()}")
print(f"kc     : {len(kc)} rows     | cols: {kc.columns.tolist()}")
print(f"kc crops: {kc['crop'].unique()}")

# ════════════════════════════════════════════════════════
# STEP 2 — สร้าง Kc lookup (year, week, crop)
# ════════════════════════════════════════════════════════
# Kc อาจมีแค่ crop+week (ไม่มี year) → ใช้ mean ข้ามปี
# หรือมี year ด้วย → merge ตรง
kc_cols = kc.columns.tolist()
print(f"\nKc columns: {kc_cols}")

if 'year' in kc_cols:
    kc_lookup = kc[['year','week','crop','Kc']].copy()
    merge_keys = ['year','week','crop']
else:
    # ใช้ค่า Kc เฉลี่ยต่อ week ข้ามปี
    kc_lookup = kc.groupby(['week','crop'])['Kc'].mean().reset_index()
    merge_keys = ['week','crop']

print(f"Kc lookup shape: {kc_lookup.shape}")
print(f"Sample Kc values:")
print(kc_lookup.head(8).to_string(index=False))


# ════════════════════════════════════════════════════════
# STEP 3 — คำนวณ NIR_A และ GIR_B รายสัปดาห์
# ════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 3 — คำนวณ NIR_A / GIR_B")
print("="*55)

results = []

for _, row in climate.iterrows():
    yr      = int(row['year'])
    wk      = int(row['week'])
    et0     = float(row['ET0_mm_week'])
    p_eff_a = float(row['P_eff_upland'])  # Zone A = rainfed → upland P_eff
    p_eff_b = float(row['P_eff_paddy'])   # Zone B = irrigated (rice-dominant)

    # --- Zone A: NIR (Net Irrigation Requirement) ---
    nir_a_total = 0.0
    etc_a_total = 0.0
    for crop, area_m2 in AREA_ZONE_A.items():
        if area_m2 == 0:
            continue
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

    results.append({
        'year'         : yr,
        'week'         : wk,
        'ET0_mm_week'  : round(et0, 3),
        'P_eff_upland' : round(p_eff_a, 3),
        'P_eff_paddy'  : round(p_eff_b, 3),
        'ETc_A_m3'     : round(etc_a_total, 1),
        'NIR_A_m3'     : round(nir_a_total, 1),
        'ETc_B_m3'     : round(etc_b_total, 1),
        'GIR_B_m3'     : round(gir_b_total, 1),
        'D_total_m3'   : round(nir_a_total + gir_b_total, 1),
        'SPI_4'        : float(row['SPI_4']),
        'drought_flag' : int(row['drought_flag']),
    })

demand = pd.DataFrame(results)

# ════════════════════════════════════════════════════════
# STEP 4 — Sanity Check
# ════════════════════════════════════════════════════════
print("\n" + "="*55)
print("STEP 4 — Sanity Check")
print("="*55)

print(f"Total weeks: {len(demand)}")
print(f"\nStats (m³/week):")
print(demand[['NIR_A_m3','GIR_B_m3','D_total_m3']].describe().round(0).to_string())

# ตรวจ negative
neg = (demand['D_total_m3'] < 0).sum()
print(f"\nNegative D_total: {neg}  (ควร = 0)")

# Seasonal pattern
demand['season'] = demand['week'].apply(
    lambda w: 'Dry-hot(10-18)' if 10<=w<=18
    else ('Wet(19-44)' if 19<=w<=44 else 'Dry-cool'))
print("\nค่าเฉลี่ยตามฤดูกาล (m³/week):")
print(demand.groupby('season')[['NIR_A_m3','GIR_B_m3','D_total_m3']]
      .mean().round(0).to_string())

# Annual demand
print("\nAnnual demand (m³/year):")
print(demand.groupby('year')['D_total_m3'].sum()
      .apply(lambda x: f"{x/1e6:.3f} Mm³").to_string())

# Sample
print("\nตัวอย่าง wet season (W26-30, 2022):")
s = demand[(demand['year']==2022) & (demand['week'].between(26,30))]
print(s[['year','week','ET0_mm_week','NIR_A_m3',
         'GIR_B_m3','D_total_m3','SPI_4']].to_string(index=False))

print("\nตัวอย่าง dry season (W10-14, 2023):")
s2 = demand[(demand['year']==2023) & (demand['week'].between(10,14))]
print(s2[['year','week','ET0_mm_week','NIR_A_m3',
          'GIR_B_m3','D_total_m3','SPI_4']].to_string(index=False))


# ════════════════════════════════════════════════════════
# STEP 5 — Export
# ════════════════════════════════════════════════════════
out_path = os.path.join(OUT_DIR, 'water_demand_weekly_dual_zone.csv')
demand.to_csv(out_path, index=False)
print(f"\n✅ Saved: water_demand_weekly_dual_zone.csv")
print(f"   Rows: {len(demand)} | Columns: {demand.columns.tolist()}")
print("\n📌 NEXT: Phase 4 — Feature engineering → ML model")


# ##############################################################################
# # PHASE 4 — ML Demand Forecasting + Conformal Prediction
# Source: `Phase_4_ML_Demand_Forecasting_and_Conformal_Prediction.ipynb`
# Header cell from the original notebook (context only).
# ##############################################################################

#"""
#Phase 4: ML Demand Forecasting + Conformal Prediction
#======================================================
#Study area : ต.แม่นาเรือ (Mae Na Rua), Phayao
#Targets    : NIR_A_m3 (Zone A rainfed), GID_B_m3 (Zone B irrigated)
#Strategy   : Direct multi-step, H = 12 weeks
#Stack      : CatBoost + LightGBM → Ridge meta-learner
#Uncertainty: Conformal Prediction (split conformal, α = 0.10)
#Split      : Train 2020-2022 | Calib 2023 | Test 2024
 
#Run order  :
  #Step 1 → step1_download_mei.py   (download NOAA MEI index)
  #Step 2 → step2_feature_engineering.py
  #Step 3 → step3_train_direct.py
  #Step 4 → step4_conformal.py
  #Step 5 → step5_metrics_shap.py
#"""


# ##############################################################################
# ## Step 1 — Download NOAA MEI v2 (ENSO) Index
# ##############################################################################

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — Download NOAA MEI v2 Index
# ─────────────────────────────────────────────────────────────────────────────
# Save as: step1_download_mei.py
 
import requests
import pandas as pd
import numpy as np
from io import StringIO
 
def download_mei():
    """
    Download MEI v2 (Multivariate ENSO Index) from NOAA PSL.
    Source: https://psl.noaa.gov/enso/mei/
    Format: wide table — rows = years, columns = bimonthly periods
    Returns: long-format DataFrame with columns [year, month, MEI]
    """
    url = "https://psl.noaa.gov/enso/mei/data/meiv2.data"
    print(f"Downloading MEI v2 from {url} ...")
 
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
 
    lines = resp.text.strip().split("\n")
 
    # Find header line (first line with year range)
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("MEI"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0].isdigit():
            data_lines.append(parts)
 
    # Column names: DJ, JF, FM, MA, AM, MJ, JJ, JA, AS, SO, ON, ND
    # These bimonthly values map to the SECOND month in the pair
    bimonth_labels = ["DJ","JF","FM","MA","AM","MJ","JJ","JA","AS","SO","ON","ND"]
    # Month of the second element in each pair (1-indexed)
    second_month   = [  1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12]
 
    records = []
    for parts in data_lines:
        year = int(parts[0])
        values = parts[1:]
        for i, val_str in enumerate(values[:12]):
            try:
                mei_val = float(val_str)
                if mei_val == -999.0:
                    mei_val = np.nan
            except ValueError:
                mei_val = np.nan
            records.append({
                "year":  year,
                "month": second_month[i],
                "MEI":   mei_val,
            })
 
    df = pd.DataFrame(records)
    df = df[(df["year"] >= 2018) & (df["year"] <= 2024)].copy()
    df.sort_values(["year","month"], inplace=True)
    df.reset_index(drop=True, inplace=True)
 
    df.to_csv("mei_monthly.csv", index=False)
    print(f"Saved mei_monthly.csv — {len(df)} rows")
    print(df.tail())
    return df
 
 
if __name__ == "__main__":
    download_mei()


# ##############################################################################
# ## Step 2 — Feature Engineering (v3, final: single climate file)
# ##############################################################################

"""
Step 2 — Feature Engineering  (v3 — single climate file)
==========================================================
Input  : water_demand_weekly_dual_zone.csv
         climate_weekly_phayao_2020_2024.csv  ← รวม ERA5 + CHIRPS ไว้แล้ว
         mei_monthly.csv
Output : ml_features_phase4.csv

ไม่ต้องใช้ :
  ET0_weekly_phayao_2020_2024.csv   (ซ้ำกับ climate file)
  CHIRPS_weekly_phayao_2020_2024.csv (ซ้ำกับ climate file)
"""

import pandas as pd
import numpy as np

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

    print(f"Merged: {df.shape[0]} rows x {df.shape[1]} cols")
    nan_counts = df.isna().sum()
    if nan_counts.any():
        print(f"NaN columns:\n{nan_counts[nan_counts > 0]}\n")

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

    # ── Summary ───────────────────────────────────────────────────────────
    meta_cols = {"year","week","month","date","zone","target_col",
                 "NIR_A_m3","GIR_B_m3","P_4week"}
    feature_cols = [c for c in ml.columns
                    if c not in meta_cols and not c.startswith("y_h")]

    print(f"\n{'='*55}")
    print(f"Output   : ml_features_phase4.csv")
    print(f"Shape    : {ml.shape[0]} rows x {ml.shape[1]} cols")
    print(f"Zones    : {list(ml['zone'].unique())}")
    print(f"Years    : {sorted(ml['year'].unique())}")
    print(f"Features ({len(feature_cols)}):")
    for i, f in enumerate(feature_cols, 1):
        print(f"  {i:2d}. {f}")
    print(f"Targets  : y_h1 ... y_h{HORIZON}")
    print(f"{'='*55}")
    return ml


if __name__ == "__main__":
    build_feature_matrix()


# ##############################################################################
# ## Step 3a — CatBoost Training + Optuna Tuning
# *** GAP: NOT FOUND IN YOUR UPLOADS ***
# Your uploaded notebook only contains the ROUND-3 RERUN of this step (next
# cell below), which expects an existing `catboost_models.pkl` from round 2 as
# input ('overwrite เฉพาะ 3 keys'). The original round-1/round-2 training
# script that PRODUCES the initial `catboost_models.pkl` was not among your
# uploaded files. I located a partial fragment of it in an earlier chat
# (saved at the time to /mnt/user-data/outputs/step3a_catboost.py), reproduced
# below AS FAR AS THE SEARCH SNIPPET WENT -- it cuts off inside tune_catboost().
# Please check your local machine/downloads for the complete
# `step3a_catboost.py` file from that session and paste it in; I do not want
# to guess/fabricate the rest of the Optuna search space and risk it not
# matching what you actually ran and reported in the manuscript.
# ##############################################################################

"""
Step 3a — CatBoost Training + Optuna Tuning
============================================
Input  : ml_features_phase4.csv
Output : catboost_models.pkl
         catboost_tuning_log.csv   (best params + calib MAE per zone x horizon)

Run    : python step3a_catboost.py
"""

import pandas as pd
import numpy as np
import optuna
import joblib
import warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error

# -- Config --------------------------------------------------------------
HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
N_TRIALS    = 80        # increase to 150+ for final run
EARLY_STOP  = 50


def get_feature_cols(df: pd.DataFrame) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GID_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    return [c for c in df.columns if c not in exclude]


def tune_catboost(X_train, y_train, X_calib, y_calib) -> tuple:
    """
    Bayesian search over CatBoost hyperparameters.
    Returns (best_model, best_params, best_mae).
    """
    # <<< TRUNCATED IN SOURCE RECOVERY -- see note above. Body of this
    #     function (Optuna objective, search space, study.optimize call,
    #     and the main()/save block) was not recoverable via chat search
    #     and is NOT reproduced here to avoid fabricating your actual
    #     hyperparameter search space. >>>
    raise NotImplementedError("Paste your original step3a_catboost.py body here")


# ##############################################################################
# ## Step 3a — CatBoost Rerun Round 3 (FINAL patch, zone A h=2,7,8 only)
# Merges into the `catboost_models.pkl` produced by the (missing) round-1/2
# script above.
# ##############################################################################

"""
Step 3a — CatBoost Rerun รอบ 3 (zone A h=2, 7, 8 เท่านั้น)
=============================================================
Input  : ml_features_phase4.csv
         catboost_models.pkl        ← รอบ 2 (จะ overwrite เฉพาะ 3 keys)
Output : catboost_models.pkl        ← merged (รอบ 2 + รอบ 3)
         catboost_tuning_log_r3.csv

เปลี่ยนจากรอบ 2:
  - warmstart จาก best params รอบ 2 (trial แรกเริ่มจากจุดที่รู้แล้ว)
  - depth min → 6  (ตัด depth=5 ออกสำหรับ zone A)
  - learning_rate min → 0.15  (ตัด lr ต่ำที่ทำให้ h=2 แย่)
  - l2_leaf_reg max → 6.0  (เข้มกว่ารอบ 2)
  - N_TRIALS → 120
  - EARLY_STOP → 80
"""

import pandas as pd
import numpy as np
import optuna
import joblib
import warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
TEST_YEAR   = 2024
N_TRIALS    = 120
EARLY_STOP  = 80

# rerun เฉพาะ zone A horizons เหล่านี้
RERUN = [("zone_A", 2), ("zone_A", 7), ("zone_A", 8)]

# best params จากรอบ 2 — เป็น starting point ของ trial แรก
WARMSTART = {
    ("zone_A", 2): {
        "iterations":        1372,
        "depth":             7,
        "learning_rate":     0.1229,
        "l2_leaf_reg":       3.366,
        "subsample":         0.912,
        "colsample_bylevel": 0.691,
        "min_data_in_leaf":  15,
    },
    ("zone_A", 7): {
        "iterations":        867,
        "depth":             8,
        "learning_rate":     0.2379,
        "l2_leaf_reg":       6.0,    # clamp ให้อยู่ใน range ใหม่
        "subsample":         0.914,
        "colsample_bylevel": 0.513,
        "min_data_in_leaf":  11,
    },
    ("zone_A", 8): {
        "iterations":        1392,
        "depth":             6,      # เพิ่มจาก 5 → 6 (min ใหม่)
        "learning_rate":     0.1544,
        "l2_leaf_reg":       1.004,
        "subsample":         0.865,
        "colsample_bylevel": 0.615,
        "min_data_in_leaf":  6,
    },
}


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def tune_catboost(X_train, y_train, X_calib, y_calib,
                  warmstart_params: dict = None) -> tuple:
    def objective(trial):
        params = {
            "iterations":        trial.suggest_int("iterations", 700, 2000),
            "depth":             trial.suggest_int("depth", 6, 10),
            "learning_rate":     trial.suggest_float("learning_rate", 0.15, 0.30, log=True),
            "l2_leaf_reg":       trial.suggest_float("l2_leaf_reg", 1.0, 6.0),
            "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.5, 1.0),
            "min_data_in_leaf":  trial.suggest_int("min_data_in_leaf", 2, 20),
            "verbose":      False,
            "random_seed":  42,
        }
        m = CatBoostRegressor(**params)
        m.fit(X_train, y_train,
              eval_set=(X_calib, y_calib),
              early_stopping_rounds=EARLY_STOP)
        return mean_absolute_error(y_calib, m.predict(X_calib))

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    if warmstart_params is not None:
        # clamp warmstart values ให้อยู่ใน range ใหม่ก่อน enqueue
        ws = dict(warmstart_params)
        ws["depth"]         = max(6,    min(10,  ws["depth"]))
        ws["learning_rate"] = max(0.15, min(0.30, ws["learning_rate"]))
        ws["l2_leaf_reg"]   = max(1.0,  min(6.0,  ws["l2_leaf_reg"]))
        study.enqueue_trial(ws)

    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    best_params = study.best_params
    best_model  = CatBoostRegressor(**best_params, verbose=False, random_seed=42)
    best_model.fit(X_train, y_train)
    best_mae = mean_absolute_error(y_calib, best_model.predict(X_calib))

    return best_model, best_params, best_mae


def main():
    df = pd.read_csv("ml_features_phase4.csv")

    # MAE รอบ 2 สำหรับ compare
    r2_mae = {
        ("zone_A", 2): 93966.80,
        ("zone_A", 7): 84138.09,
        ("zone_A", 8): 85954.44,
    }

    # โหลด models รอบ 2
    try:
        all_models = joblib.load("catboost_models.pkl")
        print(f"Loaded catboost_models.pkl ({len(all_models)} models)")
    except FileNotFoundError:
        print("catboost_models.pkl not found — starting fresh dict")
        all_models = {}

    new_models = {}
    log_rows   = []

    for zone, h in RERUN:
        df_zone      = df[df["zone"] == zone].copy()
        feature_cols = get_feature_cols(df, df_zone)

        target = f"y_h{h}"
        valid  = df_zone.dropna(subset=feature_cols + [target])

        train = valid[valid["year"].isin(TRAIN_YEARS)]
        calib = valid[valid["year"] == CALIB_YEAR]

        X_train = train[feature_cols].values
        y_train = train[target].values
        X_calib = calib[feature_cols].values
        y_calib = calib[target].values

        print(f"\n{'='*60}")
        print(f"[{zone}] h={h:02d}  |  train={len(X_train)}  calib={len(X_calib)}")
        print(f"  รอบ 2 MAE = {r2_mae[(zone,h)]:,.0f} m³  ← target to beat")
        print(f"{'='*60}")

        ws    = WARMSTART.get((zone, h))
        model, params, mae = tune_catboost(
            X_train, y_train, X_calib, y_calib,
            warmstart_params=ws,
        )
        new_models[(zone, h)] = model

        r2     = r2_mae[(zone, h)]
        delta  = mae - r2
        symbol = "✅" if delta < 0 else "❌"
        print(f"\n  {symbol} รอบ 3 MAE = {mae:,.2f}  |  delta = {delta:+,.0f} m³")
        print(f"  best params: {params}")

        log_rows.append({
            "zone":             zone,
            "horizon":          h,
            "calib_mae_r2":     r2,
            "calib_mae_r3":     round(mae, 2),
            "delta":            round(delta, 2),
            **{f"cat_{k}": v for k, v in params.items()},
        })

    # ── Merge: overwrite เฉพาะ 3 keys ────────────────────────────────────
    for key, model in new_models.items():
        # เก็บเฉพาะถ้า MAE รอบ 3 ดีกว่ารอบ 2
        zone, h = key
        r3_mae = log_rows[[r["horizon"] == h and r["zone"] == zone
                            for r in log_rows].index(True)]["calib_mae_r3"]
        if r3_mae < r2_mae[key]:
            all_models[key] = model
            print(f"\n[merge] ({zone}, h={h}) → replaced (MAE {r2_mae[key]:,.0f} → {r3_mae:,.0f})")
        else:
            print(f"\n[merge] ({zone}, h={h}) → kept รอบ 2 (รอบ 3 ไม่ดีกว่า)")

    joblib.dump(all_models, "catboost_models.pkl")
    print(f"\nSaved catboost_models.pkl ({len(all_models)} models)")

    # ── Summary ───────────────────────────────────────────────────────────
    log_df = pd.DataFrame(log_rows)
    log_df.to_csv("catboost_tuning_log_r3.csv", index=False)

    print("\n" + "="*55)
    print("Round 3 summary")
    print("="*55)
    print(log_df[["zone","horizon","calib_mae_r2","calib_mae_r3","delta"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 3b — LightGBM Training + Optuna Tuning (Round 1)
# ##############################################################################

"""
Step 3b — LightGBM Training + Optuna Tuning
============================================
Input  : ml_features_phase4.csv
Output : lightgbm_models.pkl
         lightgbm_tuning_log.csv

Run    : python step3b_lightgbm.py
"""

import pandas as pd
import numpy as np
import optuna
import joblib
import warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

import lightgbm as lgb
from sklearn.metrics import mean_absolute_error

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
N_TRIALS    = 80        # เพิ่มเป็น 150+ สำหรับ final run
EARLY_STOP  = 50


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GID_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def tune_lightgbm(X_train, y_train, X_calib, y_calib) -> tuple:
    """
    Bayesian search over LightGBM hyperparameters.
    Returns (best_model, best_params, best_mae).
    """
    def objective(trial):
        params = {
            "objective":        "regression",
            "metric":           "mae",
            "verbosity":        -1,
            "boosting_type":    "gbdt",
            "n_estimators":     trial.suggest_int("n_estimators", 600, 2000),
            "learning_rate":    trial.suggest_float("learning_rate", 0.1, 0.3, log=True),
            "num_leaves":       trial.suggest_int("num_leaves", 20, 120),
            "max_depth":        trial.suggest_int("max_depth", 4, 12),
            "min_child_samples":trial.suggest_int("min_child_samples", 5, 35),
            "subsample":        trial.suggest_float("subsample", 0.5, 1.0),
            "subsample_freq":   1,
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
            "reg_alpha":        trial.suggest_float("reg_alpha", 1e-4, 3.0, log=True),
            "reg_lambda":       trial.suggest_float("reg_lambda", 1e-4, 3.0, log=True),
        }
        m = lgb.LGBMRegressor(**params)
        m.fit(
            X_train, y_train,
            eval_set=[(X_calib, y_calib)],
            callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)],
        )
        return mean_absolute_error(y_calib, m.predict(X_calib))

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    best_params = {
        "objective": "regression", "metric": "mae",
        "verbosity": -1, **study.best_params,
    }
    best_model = lgb.LGBMRegressor(**best_params)
    best_model.fit(
        X_train, y_train,
        eval_set=[(X_calib, y_calib)],
        callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)],
    )
    best_mae = mean_absolute_error(y_calib, best_model.predict(X_calib))

    return best_model, study.best_params, best_mae


def main():
    df = pd.read_csv("ml_features_phase4.csv")

    lgb_models = {}   # key: (zone, h)  value: fitted LGBMRegressor
    log_rows   = []

    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        feature_cols = get_feature_cols(df, df_zone)
        print(f"\n{'='*60}")
        print(f"Zone: {zone}")
        print(f"{'='*60}")

        for h in range(1, HORIZON + 1):
            target = f"y_h{h}"
            valid  = df_zone.dropna(subset=feature_cols + [target])

            train = valid[valid["year"].isin(TRAIN_YEARS)]
            calib = valid[valid["year"] == CALIB_YEAR]

            X_train = train[feature_cols].values
            y_train = train[target].values
            X_calib = calib[feature_cols].values
            y_calib = calib[target].values

            print(f"\n  h={h:02d} | train={len(X_train)} calib={len(X_calib)}")

            model, params, mae = tune_lightgbm(X_train, y_train, X_calib, y_calib)
            lgb_models[(zone, h)] = model

            log_rows.append({
                "zone": zone, "horizon": h, "calib_mae": round(mae, 2),
                **{f"lgb_{k}": v for k, v in params.items()},
            })
            print(f"  → Best MAE = {mae:.2f} m³  |  params: {params}")

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(lgb_models, "lightgbm_models.pkl")
    pd.DataFrame(log_rows).to_csv("lightgbm_tuning_log.csv", index=False)
    print(f"\nSaved lightgbm_models.pkl  ({len(lgb_models)} models)")
    print("Saved lightgbm_tuning_log.csv")


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 3b — LightGBM Rerun Round 2
# *** GAP: NOT FOUND IN YOUR UPLOADS ***
# The Round-3 rerun below explicitly says its input is
# `lightgbm_models.pkl <- รอบ 2`, i.e. a Round-2 rerun script must exist
# between Round 1 (above) and Round 3 (below). I could not find this Round-2
# script anywhere in your uploads or in chat search results. Please locate it
# locally and insert it here; leaving this gap means Round 3 cannot be run
# standalone from Round 1's output alone.
# ##############################################################################

# <<< MISSING: Step 3b Round 2 rerun script -- see note above >>>


# ##############################################################################
# ## Step 3b — LightGBM Rerun Round 3 (FINAL patch)
# ##############################################################################

"""
Step 3b — LightGBM Rerun รอบ 3
================================
Zone A  : rerun h=2,5,6,8,11,12  (horizons ที่แย่ลงในรอบ 2)
Zone B  : rerun ทั้ง 12 horizons  (8/12 แย่ลง → คืน search space กว้าง)

Search space แยกต่าม zone:
  Zone A : lr 0.10–0.30, depth 4–12, reg 1e-4–3.0
  Zone B : lr 0.05–0.30, depth 3–12, reg_alpha 1e-4–8.0, reg_lambda 1e-4–5.0

Warmstart: best params จากรอบที่ดีที่สุด (round 1 หรือ 2) ต่อ horizon
Merge    : auto-keep ผลที่ดีที่สุดจากทุก round ก่อน save

Input  : ml_features_phase4.csv
         lightgbm_models.pkl   ← รอบ 2
Output : lightgbm_models.pkl   ← merged best
         lightgbm_tuning_log_r3.csv
"""

import pandas as pd
import numpy as np
import optuna
import joblib
import warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

import lightgbm as lgb
from sklearn.metrics import mean_absolute_error

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
N_TRIALS    = 120
EARLY_STOP  = 80

# Zone A: rerun horizons ที่แย่ลงในรอบ 2
RERUN_A = [2, 5, 6, 8, 11, 12]
# Zone B: rerun ทั้งหมด (search space รอบ 2 ทำให้แย่ลง 8/12)
RERUN_B = list(range(1, 13))

# Search space แยก zone
SEARCH_SPACE = {
    "zone_A": dict(
        lr_min=0.10,  lr_max=0.30,
        depth_min=4,  depth_max=12,
        alpha_min=1e-4, alpha_max=3.0,
        lambda_min=1e-4, lambda_max=3.0,
    ),
    "zone_B": dict(
        lr_min=0.05,  lr_max=0.30,   # คืน lr ต่ำ
        depth_min=3,  depth_max=12,  # คืน depth=3
        alpha_min=1e-4, alpha_max=8.0,  # zone B ใช้ alpha สูงได้
        lambda_min=1e-4, lambda_max=5.0,
    ),
}

# ── Warmstart: best params จาก round ที่ดีกว่า ───────────────────────────────
# Zone A — warmstart จากรอบ 1 สำหรับ horizon ที่รอบ 1 ดีกว่า
# Zone B — warmstart จากรอบ 1 (ดีกว่ารอบ 2 ใน 8/12 horizons)

WARMSTART = {
    # Zone A — ใช้ round 1 params สำหรับ h ที่ round 1 ดีกว่า
    ("zone_A", 2):  {"n_estimators":613,  "learning_rate":0.2908, "num_leaves":133,
                     "max_depth":6,  "min_child_samples":6,  "subsample":0.6447,
                     "colsample_bytree":0.5710, "reg_alpha":0.0137, "reg_lambda":0.3997},
    ("zone_A", 5):  {"n_estimators":987,  "learning_rate":0.2537, "num_leaves":65,
                     "max_depth":6,  "min_child_samples":10, "subsample":0.5510,
                     "colsample_bytree":0.7389, "reg_alpha":0.0003, "reg_lambda":1.5321},
    ("zone_A", 6):  {"n_estimators":1460, "learning_rate":0.0561, "num_leaves":20,
                     "max_depth":8,  "min_child_samples":5,  "subsample":0.5338,
                     "colsample_bytree":0.8334, "reg_alpha":0.0038, "reg_lambda":9.984},
    ("zone_A", 8):  {"n_estimators":1850, "learning_rate":0.1372, "num_leaves":125,
                     "max_depth":10, "min_child_samples":18, "subsample":0.9707,
                     "colsample_bytree":0.7645, "reg_alpha":0.0001, "reg_lambda":0.0002},
    ("zone_A", 11): {"n_estimators":937,  "learning_rate":0.2452, "num_leaves":115,
                     "max_depth":8,  "min_child_samples":12, "subsample":0.5780,
                     "colsample_bytree":0.4349, "reg_alpha":2.1423, "reg_lambda":0.1013},
    ("zone_A", 12): {"n_estimators":1014, "learning_rate":0.2605, "num_leaves":120,
                     "max_depth":10, "min_child_samples":10, "subsample":0.5020,
                     "colsample_bytree":0.4536, "reg_alpha":0.0176, "reg_lambda":0.2303},
    # Zone B — warmstart จาก round 1 ทุก horizon
    ("zone_B", 1):  {"n_estimators":593,  "learning_rate":0.1944, "num_leaves":137,
                     "max_depth":11, "min_child_samples":15, "subsample":0.5750,
                     "colsample_bytree":0.5244, "reg_alpha":1.7348, "reg_lambda":0.0016},
    ("zone_B", 2):  {"n_estimators":1403, "learning_rate":0.0911, "num_leaves":51,
                     "max_depth":10, "min_child_samples":14, "subsample":0.5042,
                     "colsample_bytree":0.9660, "reg_alpha":0.1845, "reg_lambda":1.4534},
    ("zone_B", 3):  {"n_estimators":724,  "learning_rate":0.1457, "num_leaves":94,
                     "max_depth":11, "min_child_samples":8,  "subsample":0.5824,
                     "colsample_bytree":0.5041, "reg_alpha":0.0089, "reg_lambda":0.0006},
    ("zone_B", 4):  {"n_estimators":1670, "learning_rate":0.0525, "num_leaves":110,
                     "max_depth":12, "min_child_samples":17, "subsample":0.9754,
                     "colsample_bytree":0.9753, "reg_alpha":6.7842, "reg_lambda":0.0172},
    ("zone_B", 5):  {"n_estimators":1030, "learning_rate":0.1644, "num_leaves":23,
                     "max_depth":3,  "min_child_samples":12, "subsample":0.6699,
                     "colsample_bytree":0.9891, "reg_alpha":0.0013, "reg_lambda":2.3709},
    ("zone_B", 6):  {"n_estimators":508,  "learning_rate":0.2167, "num_leaves":76,
                     "max_depth":9,  "min_child_samples":22, "subsample":0.5649,
                     "colsample_bytree":0.5238, "reg_alpha":1.9599, "reg_lambda":0.9322},
    ("zone_B", 7):  {"n_estimators":1501, "learning_rate":0.2966, "num_leaves":30,
                     "max_depth":9,  "min_child_samples":45, "subsample":0.9567,
                     "colsample_bytree":0.7354, "reg_alpha":0.0008, "reg_lambda":0.0085},
    ("zone_B", 8):  {"n_estimators":1992, "learning_rate":0.1216, "num_leaves":46,
                     "max_depth":12, "min_child_samples":8,  "subsample":0.9992,
                     "colsample_bytree":0.8432, "reg_alpha":0.0154, "reg_lambda":0.1665},
    ("zone_B", 9):  {"n_estimators":1444, "learning_rate":0.1406, "num_leaves":114,
                     "max_depth":6,  "min_child_samples":15, "subsample":0.8574,
                     "colsample_bytree":0.8103, "reg_alpha":0.0455, "reg_lambda":0.0196},
    ("zone_B", 10): {"n_estimators":1025, "learning_rate":0.2855, "num_leaves":150,
                     "max_depth":9,  "min_child_samples":7,  "subsample":0.9562,
                     "colsample_bytree":0.5453, "reg_alpha":0.0039, "reg_lambda":0.0048},
    ("zone_B", 11): {"n_estimators":872,  "learning_rate":0.2981, "num_leaves":61,
                     "max_depth":3,  "min_child_samples":6,  "subsample":0.6941,
                     "colsample_bytree":0.8206, "reg_alpha":0.0047, "reg_lambda":4.9100},
    ("zone_B", 12): {"n_estimators":1054, "learning_rate":0.2669, "num_leaves":47,
                     "max_depth":12, "min_child_samples":15, "subsample":0.5788,
                     "colsample_bytree":0.5464, "reg_alpha":9.6406, "reg_lambda":6.2304},
}

# MAE ที่ดีที่สุดในปัจจุบัน (best of round 1 & 2) — สำหรับ merge check
BEST_MAE = {
    ("zone_A", 1):  81333.74, ("zone_A", 2):  86248.04, ("zone_A", 3):  79964.46,
    ("zone_A", 4):  82513.25, ("zone_A", 5):  81620.34, ("zone_A", 6):  77579.03,
    ("zone_A", 7):  81611.10, ("zone_A", 8):  81030.43, ("zone_A", 9):  75281.45,
    ("zone_A", 10): 80494.66, ("zone_A", 11): 82826.25, ("zone_A", 12): 76874.42,
    ("zone_B", 1):  27175.79, ("zone_B", 2):  29004.31, ("zone_B", 3):  26252.54,
    ("zone_B", 4):  26199.50, ("zone_B", 5):  26861.40, ("zone_B", 6):  25082.02,
    ("zone_B", 7):  26549.14, ("zone_B", 8):  26310.01, ("zone_B", 9):  28117.68,
    ("zone_B", 10): 24883.06, ("zone_B", 11): 29121.29, ("zone_B", 12): 26924.27,
}


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def tune_lightgbm(X_train, y_train, X_calib, y_calib,
                  zone: str, warmstart_params: dict = None) -> tuple:
    sp = SEARCH_SPACE[zone]

    def objective(trial):
        params = {
            "objective":         "regression",
            "metric":            "mae",
            "verbosity":         -1,
            "boosting_type":     "gbdt",
            "n_estimators":      trial.suggest_int("n_estimators", 600, 2000),
            "learning_rate":     trial.suggest_float("learning_rate",
                                     sp["lr_min"], sp["lr_max"], log=True),
            "num_leaves":        trial.suggest_int("num_leaves", 20, 120),
            "max_depth":         trial.suggest_int("max_depth",
                                     sp["depth_min"], sp["depth_max"]),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 35),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "subsample_freq":    1,
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.45, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha",
                                     sp["alpha_min"], sp["alpha_max"], log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda",
                                     sp["lambda_min"], sp["lambda_max"], log=True),
        }
        m = lgb.LGBMRegressor(**params)
        m.fit(X_train, y_train,
              eval_set=[(X_calib, y_calib)],
              callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)])
        return mean_absolute_error(y_calib, m.predict(X_calib))

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    if warmstart_params is not None:
        # clamp warmstart ให้อยู่ใน range ใหม่
        ws = dict(warmstart_params)
        ws["learning_rate"]  = max(sp["lr_min"],    min(sp["lr_max"],    ws["learning_rate"]))
        ws["max_depth"]      = max(sp["depth_min"], min(sp["depth_max"], ws["max_depth"]))
        ws["reg_alpha"]      = max(sp["alpha_min"], min(sp["alpha_max"], ws["reg_alpha"]))
        ws["reg_lambda"]     = max(sp["lambda_min"],min(sp["lambda_max"],ws["reg_lambda"]))
        ws["num_leaves"]     = max(20, min(120, ws["num_leaves"]))
        ws["n_estimators"]   = max(600, min(2000, ws["n_estimators"]))
        ws["min_child_samples"] = max(5, min(35, ws["min_child_samples"]))
        study.enqueue_trial(ws)

    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    best_params = {
        "objective": "regression", "metric": "mae",
        "verbosity": -1, **study.best_params,
    }
    best_model = lgb.LGBMRegressor(**best_params)
    best_model.fit(X_train, y_train,
                   eval_set=[(X_calib, y_calib)],
                   callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)])
    best_mae = mean_absolute_error(y_calib, best_model.predict(X_calib))

    return best_model, study.best_params, best_mae


def main():
    df = pd.read_csv("ml_features_phase4.csv")

    try:
        all_models = joblib.load("lightgbm_models.pkl")
        print(f"Loaded lightgbm_models.pkl ({len(all_models)} models)")
    except FileNotFoundError:
        print("lightgbm_models.pkl not found — starting fresh dict")
        all_models = {}

    rerun_list = (
        [("zone_A", h) for h in RERUN_A] +
        [("zone_B", h) for h in RERUN_B]
    )
    print(f"\nTotal rerun: {len(rerun_list)} models")

    log_rows   = []
    new_models = {}

    for zone, h in rerun_list:
        df_zone      = df[df["zone"] == zone].copy()
        feature_cols = get_feature_cols(df, df_zone)

        target = f"y_h{h}"
        valid  = df_zone.dropna(subset=feature_cols + [target])

        train = valid[valid["year"].isin(TRAIN_YEARS)]
        calib = valid[valid["year"] == CALIB_YEAR]

        X_train = train[feature_cols].values;  y_train = train[target].values
        X_calib = calib[feature_cols].values;  y_calib = calib[target].values

        prev_best = BEST_MAE[(zone, h)]
        print(f"\n{'='*60}")
        print(f"[{zone}] h={h:02d}  best so far = {prev_best:,.0f} m³")
        print(f"{'='*60}")

        ws = WARMSTART.get((zone, h))
        model, params, mae = tune_lightgbm(
            X_train, y_train, X_calib, y_calib,
            zone=zone, warmstart_params=ws,
        )
        new_models[(zone, h)] = (model, mae)

        delta  = mae - prev_best
        symbol = "✅" if delta < 0 else "❌"
        print(f"  {symbol}  รอบ 3 MAE = {mae:,.2f}  |  delta = {delta:+,.0f} m³")

        log_rows.append({
            "zone": zone, "horizon": h,
            "best_prev":    round(prev_best, 2),
            "calib_mae_r3": round(mae, 2),
            "delta":        round(delta, 2),
            **{f"lgb_{k}": v for k, v in params.items()},
        })

    # ── Merge: เก็บดีที่สุดจากทุก round ──────────────────────────────────
    print(f"\n{'='*60}")
    print("Merging results...")
    replaced = 0
    for (zone, h), (model, mae) in new_models.items():
        if mae < BEST_MAE[(zone, h)]:
            all_models[(zone, h)] = model
            replaced += 1
            print(f"  ✅ ({zone}, h={h:2d}) replaced  "
                  f"{BEST_MAE[(zone,h)]:,.0f} → {mae:,.0f}  "
                  f"(Δ={mae-BEST_MAE[(zone,h)]:+,.0f})")
        else:
            print(f"  ⏸  ({zone}, h={h:2d}) kept prev  "
                  f"({BEST_MAE[(zone,h)]:,.0f} ≤ {mae:,.0f})")

    joblib.dump(all_models, "lightgbm_models.pkl")
    print(f"\nSaved lightgbm_models.pkl ({len(all_models)} models)")
    print(f"Replaced: {replaced} / {len(rerun_list)}")

    # ── Summary table ─────────────────────────────────────────────────────
    log_df = pd.DataFrame(log_rows)
    log_df.to_csv("lightgbm_tuning_log_r3.csv", index=False)

    print(f"\n{'='*55}")
    print("Round 3 summary")
    print("="*55)
    for zone in ["zone_A", "zone_B"]:
        sub = log_df[log_df["zone"] == zone][
            ["zone","horizon","best_prev","calib_mae_r3","delta"]]
        imp = (sub["delta"] < 0).sum()
        print(f"\n{zone}  ({imp}/{len(sub)} improved)")
        print(sub.to_string(index=False))


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Fix — Zone B CatBoost + LightGBM retrain to 37 features (feature-count mismatch fix)
# ##############################################################################

"""
Fix: Zone B CatBoost + LightGBM → 37 features
================================================
ปัญหา : Zone B models ทั้ง 2 ถูก train ด้วย 38 features (GIR_B_m3 หลุดเข้าไป)
         แต่ step3c ต้องการ 37 features → mismatch

วิธีแก้: retrain ด้วย best params เดิม แต่ใช้ 37-feature set (GIR_B_m3 excluded)
         ไม่ต้อง Optuna ใหม่ — ใช้ params จาก tuning log ที่บันทึกไว้

Input  : ml_features_phase4.csv
         catboost_models.pkl
         lightgbm_models.pkl
Output : catboost_models.pkl  ← Zone B fixed (37 features)
         lightgbm_models.pkl  ← Zone B fixed (37 features, ยกเว้น h=9 ที่ OK อยู่แล้ว)
         fix_feature_log.csv
"""

import pandas as pd
import numpy as np
import joblib
import warnings
warnings.filterwarnings("ignore")

from catboost import CatBoostRegressor
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error

HORIZON     = 12
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023

# ── Best params Zone B ─────────────────────────────────────────────────────
# คัดจาก tuning log — round ที่ให้ calib_mae ต่ำสุดต่อ horizon

CAT_B_PARAMS = {
    1:  {"iterations":1361, "depth":8,  "learning_rate":0.1099, "l2_leaf_reg":1.886,
         "subsample":0.632, "colsample_bylevel":0.676, "min_data_in_leaf":16},
    2:  {"iterations":1311, "depth":10, "learning_rate":0.2788, "l2_leaf_reg":3.136,
         "subsample":0.754, "colsample_bylevel":0.658, "min_data_in_leaf":14},
    3:  {"iterations":1634, "depth":6,  "learning_rate":0.2015, "l2_leaf_reg":2.342,
         "subsample":0.826, "colsample_bylevel":0.765, "min_data_in_leaf":16},
    4:  {"iterations": 881, "depth":6,  "learning_rate":0.1496, "l2_leaf_reg":4.192,
         "subsample":0.914, "colsample_bylevel":0.600, "min_data_in_leaf":11},
    5:  {"iterations":1350, "depth":5,  "learning_rate":0.2496, "l2_leaf_reg":2.047,
         "subsample":0.934, "colsample_bylevel":0.673, "min_data_in_leaf": 5},
    6:  {"iterations":1615, "depth":6,  "learning_rate":0.1047, "l2_leaf_reg":2.910,
         "subsample":0.783, "colsample_bylevel":0.779, "min_data_in_leaf":15},
    7:  {"iterations":1229, "depth":5,  "learning_rate":0.2287, "l2_leaf_reg":7.985,
         "subsample":0.675, "colsample_bylevel":0.816, "min_data_in_leaf":20},
    8:  {"iterations": 907, "depth":5,  "learning_rate":0.2148, "l2_leaf_reg":5.882,
         "subsample":0.971, "colsample_bylevel":0.521, "min_data_in_leaf":19},
    9:  {"iterations":1645, "depth":5,  "learning_rate":0.2090, "l2_leaf_reg":7.545,
         "subsample":0.603, "colsample_bylevel":0.707, "min_data_in_leaf":12},
    10: {"iterations":1388, "depth":5,  "learning_rate":0.1961, "l2_leaf_reg":1.075,
         "subsample":0.719, "colsample_bylevel":0.996, "min_data_in_leaf": 6},
    11: {"iterations":1960, "depth":5,  "learning_rate":0.2885, "l2_leaf_reg":3.642,
         "subsample":0.772, "colsample_bylevel":0.903, "min_data_in_leaf": 5},
    12: {"iterations":1623, "depth":6,  "learning_rate":0.2086, "l2_leaf_reg":1.061,
         "subsample":0.870, "colsample_bylevel":0.724, "min_data_in_leaf":13},
}

# h=9 ข้ามเพราะ LGB Zone B h=9 มี 37 features อยู่แล้ว (R3)
LGB_B_PARAMS = {
    1:  {"n_estimators":1519, "learning_rate":0.1842, "num_leaves": 94, "max_depth": 5,
         "min_child_samples":16, "subsample":0.637, "colsample_bytree":0.499,
         "reg_alpha":2.223,  "reg_lambda":0.000},
    2:  {"n_estimators":1641, "learning_rate":0.1108, "num_leaves":115, "max_depth":11,
         "min_child_samples":12, "subsample":0.618, "colsample_bytree":0.490,
         "reg_alpha":0.002,  "reg_lambda":0.017},
    3:  {"n_estimators": 724, "learning_rate":0.1457, "num_leaves": 94, "max_depth":11,
         "min_child_samples": 8, "subsample":0.582, "colsample_bytree":0.504,
         "reg_alpha":0.009,  "reg_lambda":0.001},
    4:  {"n_estimators":1670, "learning_rate":0.0525, "num_leaves":110, "max_depth":12,
         "min_child_samples":17, "subsample":0.975, "colsample_bytree":0.975,
         "reg_alpha":6.784,  "reg_lambda":0.017},
    5:  {"n_estimators":1030, "learning_rate":0.1644, "num_leaves": 23, "max_depth": 3,
         "min_child_samples":12, "subsample":0.670, "colsample_bytree":0.989,
         "reg_alpha":0.001,  "reg_lambda":2.371},
    6:  {"n_estimators":1229, "learning_rate":0.2612, "num_leaves": 46, "max_depth": 7,
         "min_child_samples": 8, "subsample":0.692, "colsample_bytree":0.423,
         "reg_alpha":0.000,  "reg_lambda":1.161},
    7:  {"n_estimators":1501, "learning_rate":0.2966, "num_leaves": 30, "max_depth": 9,
         "min_child_samples":45, "subsample":0.957, "colsample_bytree":0.735,
         "reg_alpha":0.001,  "reg_lambda":0.008},
    8:  {"n_estimators":1992, "learning_rate":0.1216, "num_leaves": 46, "max_depth":12,
         "min_child_samples": 8, "subsample":0.999, "colsample_bytree":0.843,
         "reg_alpha":0.015,  "reg_lambda":0.167},
    # h=9 skip — already 37 features (R3)
    10: {"n_estimators":1025, "learning_rate":0.2855, "num_leaves":150, "max_depth": 9,
         "min_child_samples": 7, "subsample":0.956, "colsample_bytree":0.545,
         "reg_alpha":0.004,  "reg_lambda":0.005},
    11: {"n_estimators": 872, "learning_rate":0.2981, "num_leaves": 61, "max_depth": 3,
         "min_child_samples": 6, "subsample":0.694, "colsample_bytree":0.821,
         "reg_alpha":0.005,  "reg_lambda":4.910},
    12: {"n_estimators": 724, "learning_rate":0.1610, "num_leaves": 84, "max_depth":10,
         "min_child_samples":20, "subsample":0.737, "colsample_bytree":0.708,
         "reg_alpha":0.007,  "reg_lambda":0.074},
}


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    """37-feature version — GIR_B_m3 correctly excluded."""
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def fix_catboost_zone_b(df, df_zone, feat_cols, all_models):
    print("\n" + "="*55)
    print("Fixing CatBoost Zone B (38 → 37 features)")
    print("="*55)
    log = []
    for h in range(1, HORIZON + 1):
        target = f"y_h{h}"
        valid  = df_zone.dropna(subset=feat_cols + [target])
        train  = valid[valid["year"].isin(TRAIN_YEARS)]
        calib  = valid[valid["year"] == CALIB_YEAR]
        X_tr, y_tr = train[feat_cols].values, train[target].values
        X_ca, y_ca = calib[feat_cols].values, calib[target].values

        params = {**CAT_B_PARAMS[h], "verbose": False, "random_seed": 42}
        model  = CatBoostRegressor(**params)
        model.fit(X_tr, y_tr)
        n = len(model.feature_importances_)
        mae = mean_absolute_error(y_ca, model.predict(X_ca))

        all_models[("zone_B", h)] = model
        log.append({"model":"CatBoost","zone":"zone_B","horizon":h,
                    "n_features":n, "calib_mae":round(mae, 2)})
        print(f"  h={h:02d} | features={n} | MAE={mae:,.2f}")
    return log


def fix_lgb_zone_b(df, df_zone, feat_cols, all_models):
    print("\n" + "="*55)
    print("Fixing LightGBM Zone B (38 → 37 features, skip h=9)")
    print("="*55)
    log = []
    for h in range(1, HORIZON + 1):
        if h == 9:
            n = all_models[("zone_B", 9)].n_features_in_
            print(f"  h=09 | features={n} ✓ skipped (already 37)")
            log.append({"model":"LightGBM","zone":"zone_B","horizon":9,
                        "n_features":n, "calib_mae":"kept"})
            continue

        target = f"y_h{h}"
        valid  = df_zone.dropna(subset=feat_cols + [target])
        train  = valid[valid["year"].isin(TRAIN_YEARS)]
        calib  = valid[valid["year"] == CALIB_YEAR]
        X_tr, y_tr = train[feat_cols].values, train[target].values
        X_ca, y_ca = calib[feat_cols].values, calib[target].values

        params = {
            "objective": "regression", "metric": "mae",
            "verbosity": -1, **LGB_B_PARAMS[h],
        }
        model = lgb.LGBMRegressor(**params)
        model.fit(X_tr, y_tr,
                  eval_set=[(X_ca, y_ca)],
                  callbacks=[lgb.early_stopping(50), lgb.log_evaluation(-1)])
        n   = model.n_features_in_
        mae = mean_absolute_error(y_ca, model.predict(X_ca))

        all_models[("zone_B", h)] = model
        log.append({"model":"LightGBM","zone":"zone_B","horizon":h,
                    "n_features":n, "calib_mae":round(mae, 2)})
        print(f"  h={h:02d} | features={n} | MAE={mae:,.2f}")
    return log


def verify(cat_models, lgb_models):
    print("\n" + "="*55)
    print("Verification — feature counts")
    print("="*55)
    ok = True
    for zone in ["zone_A", "zone_B"]:
        for h in range(1, HORIZON + 1):
            nc = len(cat_models[(zone, h)].feature_importances_)
            nl = lgb_models[(zone, h)].n_features_in_
            status = "✅" if nc == 37 and nl == 37 else "❌"
            if nc != 37 or nl != 37:
                ok = False
            print(f"  {status} ({zone}, h={h:2d}) Cat={nc}  LGB={nl}")
    print()
    print("All 37 ✅" if ok else "⚠️  Still mismatched — check above")


def main():
    df        = pd.read_csv("ml_features_phase4.csv")
    cat_all   = joblib.load("catboost_models.pkl")
    lgb_all   = joblib.load("lightgbm_models.pkl")

    zone    = "zone_B"
    df_zone = df[df["zone"] == zone].copy()
    feat_cols = get_feature_cols(df, df_zone)
    print(f"Feature cols: {len(feat_cols)}  (expect 37)")

    log  = fix_catboost_zone_b(df, df_zone, feat_cols, cat_all)
    log += fix_lgb_zone_b(df, df_zone, feat_cols, lgb_all)

    # Save
    joblib.dump(cat_all, "catboost_models.pkl")
    joblib.dump(lgb_all, "lightgbm_models.pkl")
    print("\n✅ Saved catboost_models.pkl")
    print("✅ Saved lightgbm_models.pkl")

    pd.DataFrame(log).to_csv("fix_feature_log.csv", index=False)
    print("✅ Saved fix_feature_log.csv")

    verify(cat_all, lgb_all)


if __name__ == "__main__":
    main()


# ##############################################################################
# ## [SUPERSEDED — kept for reference only, NOT part of final pipeline]
# Step 3c — Ridge Meta-Learner (Stacking)
# Failed due to in-sample data leakage in the meta-learner (negative weights,
# stack won only 1/24 models). Replaced by Step 3c v2 (Inverse-MAE) below.
# ##############################################################################

"""
Step 3c — Ridge Meta-Learner (Stacking)
========================================
Input  : ml_features_phase4.csv
         catboost_models.pkl     ← จาก step3a
         lightgbm_models.pkl     ← จาก step3b
Output : ridge_meta_models.pkl
         stacking_summary.csv    (calib + test MAE per zone × horizon)

Run AFTER step3a และ step3b เสร็จแล้ว:
    python step3c_ridge_meta.py
"""

import pandas as pd
import numpy as np
import joblib

from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
TEST_YEAR   = 2024

# RidgeCV — ค้นหา alpha อัตโนมัติจาก list นี้
RIDGE_ALPHAS = [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def get_meta_features(cat_models, lgb_models, zone, h, X):
    """Stack predictions from CatBoost + LightGBM as meta-features."""
    cat_pred = cat_models[(zone, h)].predict(X)
    lgb_pred = lgb_models[(zone, h)].predict(X)
    return np.column_stack([cat_pred, lgb_pred])


def main():
    df         = pd.read_csv("ml_features_phase4.csv")
    cat_models = joblib.load("catboost_models.pkl")
    lgb_models = joblib.load("lightgbm_models.pkl")


    meta_models = {}   # key: (zone, h)  value: fitted RidgeCV
    log_rows    = []

    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        feature_cols = get_feature_cols(df, df_zone)
        print(f"\n{'='*60}")
        print(f"Zone: {zone}")
        print(f"{'='*60}")

        for h in range(1, HORIZON + 1):
            target = f"y_h{h}"
            valid  = df_zone.dropna(subset=feature_cols + [target])

            train = valid[valid["year"].isin(TRAIN_YEARS)]
            calib = valid[valid["year"] == CALIB_YEAR]
            test  = valid[valid["year"] == TEST_YEAR]

            X_train = train[feature_cols].values
            y_train = train[target].values
            X_calib = calib[feature_cols].values
            y_calib = calib[target].values
            X_test  = test[feature_cols].values
            y_test  = test[target].values

            # ── Build meta-feature matrices ───────────────────────────────
            # Train meta on train + calib combined
            # (base models were fit on train only, so calib is out-of-fold)
            meta_train = get_meta_features(cat_models, lgb_models, zone, h, X_train)
            meta_calib = get_meta_features(cat_models, lgb_models, zone, h, X_calib)
            meta_test  = get_meta_features(cat_models, lgb_models, zone, h, X_test)

            meta_X_fit = np.vstack([meta_train, meta_calib])
            meta_y_fit = np.concatenate([y_train, y_calib])

            # ── RidgeCV (finds best alpha via leave-one-out CV) ───────────
            ridge = RidgeCV(alphas=RIDGE_ALPHAS, cv=5)
            ridge.fit(meta_X_fit, meta_y_fit)
            meta_models[(zone, h)] = ridge

            # ── Evaluate ─────────────────────────────────────────────────
            pred_calib_stack = ridge.predict(meta_calib)
            pred_test_stack  = ridge.predict(meta_test)
            mae_calib = mean_absolute_error(y_calib, pred_calib_stack)
            mae_test  = mean_absolute_error(y_test,  pred_test_stack)

            # Individual model MAE on test (for comparison)
            mae_cat  = mean_absolute_error(y_test, cat_models[(zone, h)].predict(X_test))
            mae_lgb  = mean_absolute_error(y_test, lgb_models[(zone, h)].predict(X_test))

            log_rows.append({
                "zone":         zone,
                "horizon":      h,
                "ridge_alpha":  ridge.alpha_,
                "mae_calib_stack": round(mae_calib, 2),
                "mae_test_cat":    round(mae_cat, 2),
                "mae_test_lgb":    round(mae_lgb, 2),
                "mae_test_stack":  round(mae_test, 2),
                "ridge_coef_cat":  round(ridge.coef_[0], 4),
                "ridge_coef_lgb":  round(ridge.coef_[1], 4),
            })

            print(f"  h={h:02d} | alpha={ridge.alpha_:.2f} "
                  f"| MAE calib={mae_calib:.1f} "
                  f"| MAE test → CatBoost={mae_cat:.1f} "
                  f"LGB={mae_lgb:.1f} "
                  f"Stack={mae_test:.1f} m³")

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(meta_models, "ridge_meta_models.pkl")
    summary = pd.DataFrame(log_rows)
    summary.to_csv("stacking_summary.csv", index=False)

    print(f"\nSaved ridge_meta_models.pkl  ({len(meta_models)} models)")
    print("Saved stacking_summary.csv\n")

    # ── Print pivot table: Stack MAE by zone × horizon ────────────────────
    for zone in ZONES:
        sub = summary[summary["zone"] == zone]
        print(f"\nTest MAE comparison — {zone}  (m³/week)")
        print(sub[["horizon","mae_test_cat","mae_test_lgb","mae_test_stack"]]
              .rename(columns={"mae_test_cat":"CatBoost",
                               "mae_test_lgb":"LightGBM",
                               "mae_test_stack":"Stack"})
              .to_string(index=False))


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 3c v2 — Inverse-MAE Weighted Averaging (FINAL ensemble method)
# ##############################################################################

"""
Step 3c v2 — Inverse-MAE Weighted Averaging
=============================================
แทนที่ Ridge Stacking ด้วย Inverse-MAE Weighted Average

เหตุผล: Ridge Stacking ล้มเหลวเพราะ meta-learner เทรนบน in-sample
predictions ของ base models → data leakage → negative weights →
test MAE แย่กว่า base models ทั้ง 2 (Stack wins แค่ 1/24)

วิธีใหม่:
  w_cat  = (1 / mae_calib_cat) / (1/mae_calib_cat + 1/mae_calib_lgb)
  w_lgb  = 1 - w_cat
  ŷ_stack = w_cat * ŷ_cat + w_lgb * ŷ_lgb

ข้อดี:
  - ไม่มี data leakage (ใช้แค่ calib set ซึ่งเป็น out-of-training)
  - interpretable ทุก weight เป็นบวก และรวมกันได้ 1
  - robust กับ dataset ขนาดเล็ก (52 calib weeks)

Input  : ml_features_phase4.csv
         catboost_models.pkl
         lightgbm_models.pkl
Output : stack_weights.pkl        ← (w_cat, w_lgb) per (zone, h)
         stacking_summary_v2.csv
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error

HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
TEST_YEAR   = 2024


def get_feature_cols(df: pd.DataFrame, df_zone: pd.DataFrame = None) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    if df_zone is not None:
        cols = [c for c in cols if not df_zone[c].isna().all()]
    return cols


def inverse_mae_weights(mae_cat: float, mae_lgb: float) -> tuple:
    """คำนวณน้ำหนัก inverse-MAE ที่รวมกันได้ 1."""
    w_cat = (1 / mae_cat) / (1 / mae_cat + 1 / mae_lgb)
    w_lgb = 1 - w_cat
    return round(w_cat, 4), round(w_lgb, 4)


def nse(y_obs, y_pred):
    return 1 - np.sum((y_obs - y_pred)**2) / np.sum((y_obs - np.mean(y_obs))**2)


def kge(y_obs, y_pred):
    r     = np.corrcoef(y_obs, y_pred)[0, 1]
    alpha = np.std(y_pred) / np.std(y_obs)
    beta  = np.mean(y_pred) / np.mean(y_obs)
    return 1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)


def main():
    df         = pd.read_csv("ml_features_phase4.csv")
    cat_models = joblib.load("catboost_models.pkl")
    lgb_models = joblib.load("lightgbm_models.pkl")

    # verify feature counts สม่ำเสมอ
    feat_issues = []
    for zone in ZONES:
        df_zone = df[df["zone"] == zone].copy()
        fc = get_feature_cols(df, df_zone)
        for h in range(1, HORIZON + 1):
            nc = len(cat_models[(zone, h)].feature_importances_)
            nl = lgb_models[(zone, h)].n_features_in_
            exp = len(fc)
            if nc != exp or nl != exp:
                feat_issues.append(f"({zone},h={h}): cat={nc} lgb={nl} expected={exp}")
    if feat_issues:
        print("⚠️  Feature mismatch detected — run fix_zone_b_features.py first:")
        for x in feat_issues:
            print(f"   {x}")
        return
    print("✅ Feature counts verified (all 37)")

    stack_weights = {}   # key: (zone, h) → {"w_cat": .., "w_lgb": ..}
    log_rows      = []

    for zone in ZONES:
        df_zone      = df[df["zone"] == zone].copy()
        feature_cols = get_feature_cols(df, df_zone)

        print(f"\n{'='*60}")
        print(f"Zone: {zone}")
        print(f"{'='*60}")

        for h in range(1, HORIZON + 1):
            target = f"y_h{h}"
            valid  = df_zone.dropna(subset=feature_cols + [target])

            calib = valid[valid["year"] == CALIB_YEAR]
            test  = valid[valid["year"] == TEST_YEAR]

            X_calib = calib[feature_cols].values;  y_calib = calib[target].values
            X_test  = test[feature_cols].values;   y_test  = test[target].values

            # ── Calib predictions ─────────────────────────────────────────
            cat_pred_calib = cat_models[(zone, h)].predict(X_calib)
            lgb_pred_calib = lgb_models[(zone, h)].predict(X_calib)

            mae_cat_calib = mean_absolute_error(y_calib, cat_pred_calib)
            mae_lgb_calib = mean_absolute_error(y_calib, lgb_pred_calib)

            # ── Compute weights ───────────────────────────────────────────
            w_cat, w_lgb = inverse_mae_weights(mae_cat_calib, mae_lgb_calib)
            stack_weights[(zone, h)] = {"w_cat": w_cat, "w_lgb": w_lgb}

            # ── Test predictions ──────────────────────────────────────────
            cat_pred_test = cat_models[(zone, h)].predict(X_test)
            lgb_pred_test = lgb_models[(zone, h)].predict(X_test)
            stk_pred_test = w_cat * cat_pred_test + w_lgb * lgb_pred_test
            stk_pred_test = np.maximum(stk_pred_test, 0)   # demand ≥ 0

            mae_cat  = mean_absolute_error(y_test, cat_pred_test)
            mae_lgb  = mean_absolute_error(y_test, lgb_pred_test)
            mae_stk  = mean_absolute_error(y_test, stk_pred_test)
            nse_stk  = nse(y_test, stk_pred_test)
            kge_stk  = kge(y_test, stk_pred_test)

            winner = "Cat" if mae_cat <= min(mae_lgb, mae_stk) else \
                     "LGB" if mae_lgb <= mae_stk else "Stack"

            print(f"  h={h:02d} | w=[{w_cat:.3f},{w_lgb:.3f}] "
                  f"| test MAE: Cat={mae_cat:.0f}  LGB={mae_lgb:.0f}  "
                  f"Stack={mae_stk:.0f}  [best: {winner}]")

            log_rows.append({
                "zone": zone, "horizon": h,
                "w_cat": w_cat, "w_lgb": w_lgb,
                "mae_calib_cat": round(mae_cat_calib, 2),
                "mae_calib_lgb": round(mae_lgb_calib, 2),
                "mae_test_cat":  round(mae_cat,  2),
                "mae_test_lgb":  round(mae_lgb,  2),
                "mae_test_stack":round(mae_stk,  2),
                "nse_test_stack":round(nse_stk,  4),
                "kge_test_stack":round(kge_stk,  4),
                "best_model": winner,
            })

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(stack_weights, "stack_weights.pkl")
    summary = pd.DataFrame(log_rows)
    summary.to_csv("stacking_summary_v2.csv", index=False)

    print(f"\nSaved stack_weights.pkl  ({len(stack_weights)} entries)")
    print("Saved stacking_summary_v2.csv\n")

    # ── Summary ───────────────────────────────────────────────────────────
    for zone in ZONES:
        sub = summary[summary["zone"] == zone]
        avg_cat = sub.mae_test_cat.mean()
        avg_lgb = sub.mae_test_lgb.mean()
        avg_stk = sub.mae_test_stack.mean()
        stk_wins = (sub.mae_test_stack == sub[["mae_test_cat",
                    "mae_test_lgb","mae_test_stack"]].min(axis=1)).sum()
        print(f"{zone}:")
        print(f"  avg test MAE — Cat={avg_cat:,.0f}  LGB={avg_lgb:,.0f}  "
              f"Stack={avg_stk:,.0f}")
        print(f"  Stack wins: {stk_wins}/12  "
              f"beats Cat: {(sub.mae_test_stack<sub.mae_test_cat).sum()}/12  "
              f"beats LGB: {(sub.mae_test_stack<sub.mae_test_lgb).sum()}/12")
        print(f"  avg NSE={sub.nse_test_stack.mean():.4f}  "
              f"avg KGE={sub.kge_test_stack.mean():.4f}")
        print()

    print("─"*55)
    print("Best model count across all 24 models:")
    print(summary.best_model.value_counts().to_string())


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 3d — Stage 1: Binary Classifier (regime detection, two-stage framework)
# ##############################################################################

"""
Step 3d — Stage 1: Binary Classifier (Two-stage Framework)
===========================================================
ทำนายว่าสัปดาห์ h สัปดาห์ข้างหน้าจะมี demand > 0 หรือไม่

Two-stage final prediction:
  ŷ_final = P(demand > 0) × ŷ_magnitude
  → ถ้า P ต่ำ: prediction ถูก pull toward 0 อัตโนมัติ
  → ถ้า P สูง: ใช้ magnitude จาก CatBoost+LGB stack เดิม

Input  : ml_features_phase4.csv
Output : stage1_classifiers.pkl    ← LGBMClassifier per (zone, h)
         stage1_thresholds.pkl     ← optimal threshold per (zone, h)
         stage1_report.csv         ← F1, precision, recall, AUC per model

Design:
  - LightGBM classifier + Optuna tuning
  - class_weight='balanced' (training zeros 37-44%)
  - Threshold tuning บน calib 2023 (maximize F1)
  - Evaluate บน test 2024: precision, recall, F1, AUC

Run: python step3d_stage1_classifier.py
"""

import pandas as pd
import numpy as np
import optuna
import joblib
import warnings
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

import lightgbm as lgb
from sklearn.metrics import (f1_score, precision_score, recall_score,
                             roc_auc_score, classification_report,
                             confusion_matrix)

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
TEST_YEAR   = 2024
N_TRIALS    = 80
EARLY_STOP  = 60


# ── Classifier feature set (subset ที่เหมาะกับ regime detection) ─────────────
# ใช้ seasonality + recent demand pattern + drought indicators
# ไม่ใช้ rolling std หรือ climate lag ที่ noisy เกินไป
CLASSIFIER_FEATURES = [
    # Seasonality — สำคัญที่สุดสำหรับ regime detection
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    # Recent demand (จะเป็น 0 ถ้าอยู่ในช่วงแล้ง)
    # ชื่อจะถูก resolve ตาม zone (NIR_A หรือ GIR_B)
    # → ดูใน get_clf_features()
    # Climate drivers
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag",
    # ENSO
    "MEI",
    # AI
    "AI_week",
]

# lag columns ของ target (zone-specific) — เพิ่มใน get_clf_features()
TARGET_LAGS = [1, 2, 3, 4]     # สัปดาห์ล่าสุด 4 สัปดาห์


def get_clf_features(df_zone: pd.DataFrame, target_col: str) -> list:
    """
    คืน feature list สำหรับ classifier
    รวม CLASSIFIER_FEATURES + lag columns ของ target zone นั้น
    กรอง all-NaN columns ออก
    """
    lag_cols = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean",
                 f"{target_col}_roll8_mean"]

    wanted = CLASSIFIER_FEATURES + lag_cols + roll_cols

    # กรองเฉพาะที่มีอยู่จริงและไม่ all-NaN
    cols = [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]
    return cols


def make_binary_target(series: pd.Series) -> pd.Series:
    """demand > 0 → 1 (active), demand = 0 → 0 (inactive)"""
    return (series > 0).astype(int)


def tune_classifier(X_train, y_train, X_calib, y_calib,
                    class_ratio: float) -> tuple:
    """
    Optuna tuning สำหรับ LGBMClassifier
    class_ratio = n_negative / n_positive (สำหรับ scale_pos_weight)
    Returns (best_model, best_params, best_threshold, best_f1_calib)
    """
    def objective(trial):
        params = {
            "objective":         "binary",
            "metric":            "binary_logloss",
            "verbosity":         -1,
            "n_estimators":      trial.suggest_int("n_estimators", 200, 1500),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves":        trial.suggest_int("num_leaves", 15, 80),
            "max_depth":         trial.suggest_int("max_depth", 3, 10),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 30),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 5.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-4, 5.0, log=True),
            "scale_pos_weight":  class_ratio,   # handle class imbalance
        }
        m = lgb.LGBMClassifier(**params)
        m.fit(X_train, y_train,
              eval_set=[(X_calib, y_calib)],
              callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)])
        # Optimize F1 on calib (better than logloss for imbalanced data)
        prob = m.predict_proba(X_calib)[:, 1]
        # Find best threshold
        thresholds = np.arange(0.2, 0.8, 0.05)
        best_f1 = max(f1_score(y_calib, (prob >= t).astype(int), zero_division=0)
                      for t in thresholds)
        return -best_f1   # minimize negative F1

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    # Train best model
    best_params = {
        "objective": "binary", "metric": "binary_logloss",
        "verbosity": -1, "scale_pos_weight": class_ratio,
        **study.best_params,
    }
    best_model = lgb.LGBMClassifier(**best_params)
    best_model.fit(X_train, y_train,
                   eval_set=[(X_calib, y_calib)],
                   callbacks=[lgb.early_stopping(EARLY_STOP), lgb.log_evaluation(-1)])

    # Tune threshold on calib
    prob_calib = best_model.predict_proba(X_calib)[:, 1]
    thresholds  = np.arange(0.15, 0.85, 0.025)
    best_thr, best_f1 = 0.5, 0.0
    for t in thresholds:
        f1 = f1_score(y_calib, (prob_calib >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_thr = f1, t

    return best_model, study.best_params, round(best_thr, 3), round(best_f1, 4)


def main():
    df = pd.read_csv("ml_features_phase4.csv")

    classifiers = {}    # key: (zone, h) → LGBMClassifier
    thresholds  = {}    # key: (zone, h) → float
    log_rows    = []

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone    = df[df["zone"] == zone].copy()
        clf_feats  = get_clf_features(df_zone, target_col)

        print(f"\n{'='*60}")
        print(f"Zone: {zone}  |  target: {target_col}")
        print(f"Classifier features ({len(clf_feats)}): {clf_feats}")
        print(f"{'='*60}")

        # Class distribution per year
        for yr in TRAIN_YEARS + [CALIB_YEAR, TEST_YEAR]:
            yr_data = df_zone[df_zone["year"] == yr][target_col].dropna()
            zeros   = (yr_data == 0).sum()
            print(f"  {yr}: {zeros}/{len(yr_data)} zeros "
                  f"({zeros/len(yr_data)*100:.0f}%)")
        print()

        for h in range(1, HORIZON + 1):
            target_h = f"y_h{h}"

            valid = df_zone.dropna(subset=clf_feats + [target_h])
            train = valid[valid["year"].isin(TRAIN_YEARS)]
            calib = valid[valid["year"] == CALIB_YEAR]
            test  = valid[valid["year"] == TEST_YEAR]

            # Binary labels
            y_tr = make_binary_target(train[target_h])
            y_ca = make_binary_target(calib[target_h])
            y_te = make_binary_target(test[target_h])

            X_tr  = train[clf_feats].values
            X_ca  = calib[clf_feats].values
            X_te  = test[clf_feats].values

            # Class ratio for scale_pos_weight
            n_neg  = (y_tr == 0).sum()
            n_pos  = (y_tr == 1).sum()
            ratio  = n_neg / max(n_pos, 1)

            print(f"  h={h:02d} | train: {n_pos}pos/{n_neg}neg  "
                  f"calib: {y_ca.sum()}/{len(y_ca)}pos  "
                  f"test: {y_te.sum()}/{len(y_te)}pos")

            model, params, thr, f1_calib = tune_classifier(
                X_tr, y_tr, X_ca, y_ca, class_ratio=ratio
            )
            classifiers[(zone, h)] = model
            thresholds[(zone, h)]  = thr

            # Evaluate on TEST set
            prob_te  = model.predict_proba(X_te)[:, 1]
            pred_te  = (prob_te >= thr).astype(int)
            f1_te    = f1_score(y_te, pred_te, zero_division=0)
            prec_te  = precision_score(y_te, pred_te, zero_division=0)
            rec_te   = recall_score(y_te, pred_te, zero_division=0)
            auc_te   = roc_auc_score(y_te, prob_te) if y_te.nunique() > 1 else np.nan
            # Zero-hit: correctly predict inactive (y=0 → pred=0)
            zero_hit = (pred_te[y_te == 0] == 0).mean() * 100 if (y_te==0).sum()>0 else np.nan

            print(f"       threshold={thr:.3f} | calib F1={f1_calib:.3f} "
                  f"| test F1={f1_te:.3f} prec={prec_te:.3f} rec={rec_te:.3f} "
                  f"AUC={auc_te:.3f} zero-hit={zero_hit:.0f}%")

            cm = confusion_matrix(y_te, pred_te)
            print(f"       confusion (test): TN={cm[0,0]} FP={cm[0,1]} "
                  f"FN={cm[1,0]} TP={cm[1,1]}")

            log_rows.append({
                "zone": zone, "horizon": h,
                "threshold":   thr,
                "f1_calib":    round(f1_calib, 4),
                "f1_test":     round(f1_te,    4),
                "precision":   round(prec_te,  4),
                "recall":      round(rec_te,   4),
                "auc":         round(auc_te,   4) if not np.isnan(auc_te) else np.nan,
                "zero_hit_pct": round(zero_hit, 1) if not np.isnan(zero_hit) else np.nan,
                "n_train_pos": int(n_pos), "n_train_neg": int(n_neg),
            })

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(classifiers, "stage1_classifiers.pkl")
    joblib.dump(thresholds,  "stage1_thresholds.pkl")

    report = pd.DataFrame(log_rows)
    report.to_csv("stage1_report.csv", index=False)

    print(f"\n{'='*60}")
    print(f"Saved stage1_classifiers.pkl ({len(classifiers)} models)")
    print(f"Saved stage1_thresholds.pkl")
    print(f"Saved stage1_report.csv")
    print(f"{'='*60}")

    # ── Summary ───────────────────────────────────────────────────────────
    for zone in ZONES:
        sub = report[report["zone"] == zone]
        print(f"\n{zone}:")
        print(f"  avg F1 (test)   = {sub.f1_test.mean():.3f}")
        print(f"  avg precision   = {sub.precision.mean():.3f}")
        print(f"  avg recall      = {sub.recall.mean():.3f}")
        print(f"  avg AUC         = {sub.auc.mean():.3f}")
        print(f"  avg zero-hit    = {sub.zero_hit_pct.mean():.1f}%")
        print(f"  avg threshold   = {sub.threshold.mean():.3f}")
        print()
        print(sub[["horizon","threshold","f1_test","precision",
                   "recall","auc","zero_hit_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 3e — Two-stage Final Predictions (P(demand>0) x magnitude)
# ##############################################################################

"""
Step 3e — Two-stage Final Predictions
======================================
รวม Stage 1 (classifier) + Stage 2 (magnitude ensemble) เข้าด้วยกัน

Final prediction formula:
  prob     = P(demand > 0)  ← จาก Stage 1 classifier
  magnitude = ŷ_cat*w_cat + ŷ_lgb*w_lgb  ← Stage 2 stack (เดิม)
  ŷ_final  = prob × magnitude

ข้อดีของ soft combination (prob × magnitude) เทียบกับ hard threshold:
  - Conformal prediction intervals จะสะท้อน regime uncertainty ด้วย
  - ไม่มี discontinuity ที่ threshold → smooth predictions
  - ถ้า prob=0.3 และ magnitude=100,000 → final=30,000 (reasonable)

Input  : ml_features_phase4.csv
         catboost_models.pkl
         lightgbm_models.pkl
         stack_weights.pkl
         stage1_classifiers.pkl
         stage1_thresholds.pkl
Output : final_predictions_2stage.csv   ← พร้อมส่งต่อ Step 4 (Conformal)
         twostage_metrics.csv           ← MAE, NSE, KGE, zero-hit per (zone, h)
"""

import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import mean_absolute_error, f1_score

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON     = 12
ZONES       = ["zone_A", "zone_B"]
TRAIN_YEARS = [2020, 2021, 2022]
CALIB_YEAR  = 2023
TEST_YEAR   = 2024
ZERO_THRESH = 5000   # m³ — ต่ำกว่านี้นับว่า "predict zero"

CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
TARGET_LAGS = [1, 2, 3, 4]


def get_regressor_features(df: pd.DataFrame, df_zone: pd.DataFrame) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def get_clf_features(df_zone: pd.DataFrame, target_col: str) -> list:
    lag_cols  = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted    = CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]


def nse(y_obs, y_pred):
    denom = np.sum((y_obs - np.mean(y_obs))**2)
    return 1 - np.sum((y_obs - y_pred)**2) / denom if denom > 1e-6 else np.nan


def kge(y_obs, y_pred):
    r     = np.corrcoef(y_obs, y_pred)[0, 1] if len(y_obs) > 1 else np.nan
    alpha = np.std(y_pred) / np.std(y_obs) if np.std(y_obs) > 0 else np.nan
    beta  = np.mean(y_pred) / np.mean(y_obs) if np.mean(y_obs) > 0 else np.nan
    return 1 - np.sqrt((r-1)**2 + (alpha-1)**2 + (beta-1)**2)


def main():
    df          = pd.read_csv("ml_features_phase4.csv")
    cat_models  = joblib.load("catboost_models.pkl")
    lgb_models  = joblib.load("lightgbm_models.pkl")
    weights     = joblib.load("stack_weights.pkl")
    classifiers = joblib.load("stage1_classifiers.pkl")
    thresholds  = joblib.load("stage1_thresholds.pkl")

    all_preds = []
    metrics   = []

    for zone in ZONES:
        target_col  = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone     = df[df["zone"] == zone].copy()
        reg_feats   = get_regressor_features(df, df_zone)
        clf_feats   = get_clf_features(df_zone, target_col)

        print(f"\n{'='*60}")
        print(f"Zone: {zone}")
        print(f"{'='*60}")

        # ── ทำนายทั้ง calib + test (เพื่อส่งต่อ conformal prediction) ────
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

                rows = valid[["year","week","month"]].copy()
                rows["zone"]      = zone
                rows["horizon"]   = h
                rows["split"]     = split_name
                rows["y_actual"]  = y_obs
                rows["y_stage1_prob"]   = prob.round(4)
                rows["y_stage2_mag"]    = mag.round(2)
                rows["y_pred_2stage"]   = y_hat.round(2)
                all_preds.append(rows)

                # Metrics for test set
                if split_name == "test":
                    mae_val   = mean_absolute_error(y_obs, y_hat)
                    nse_val   = nse(y_obs, y_hat)
                    kge_val   = kge(y_obs, y_hat)
                    # Wet season only
                    wet       = y_obs > 0
                    dry       = ~wet
                    mae_wet   = mean_absolute_error(y_obs[wet], y_hat[wet]) if wet.sum()>0 else np.nan
                    nse_wet   = nse(y_obs[wet], y_hat[wet]) if wet.sum()>1 else np.nan
                    mape_wet  = (np.abs((y_obs[wet]-y_hat[wet])/y_obs[wet]).mean()*100
                                 if wet.sum()>0 else np.nan)
                    zero_hit  = (y_hat[dry] < ZERO_THRESH).mean()*100 if dry.sum()>0 else np.nan
                    # F1 for binary regime
                    thr       = thresholds[(zone, h)]
                    y_bin_obs = (y_obs > 0).astype(int)
                    y_bin_hat = (y_hat > ZERO_THRESH).astype(int)
                    f1_val    = f1_score(y_bin_obs, y_bin_hat, zero_division=0)

                    metrics.append({
                        "zone": zone, "horizon": h,
                        "mae_overall":  round(mae_val,  2),
                        "nse_overall":  round(nse_val,  4),
                        "kge_overall":  round(kge_val,  4),
                        "mae_wet":      round(mae_wet,  2) if not np.isnan(mae_wet) else np.nan,
                        "nse_wet":      round(nse_wet,  4) if not np.isnan(nse_wet) else np.nan,
                        "mape_wet_pct": round(mape_wet, 1) if not np.isnan(mape_wet) else np.nan,
                        "zero_hit_pct": round(zero_hit, 1) if not np.isnan(zero_hit) else np.nan,
                        "f1_regime":    round(f1_val,   4),
                        "n_wet":        int(wet.sum()),
                        "n_dry":        int(dry.sum()),
                    })

                    print(f"  h={h:02d} | MAE={mae_val:,.0f}  NSE={nse_val:.3f}  "
                          f"NSE_wet={nse_wet:.3f}  MAPE_wet={mape_wet:.0f}%  "
                          f"zero-hit={zero_hit:.0f}%  F1={f1_val:.3f}")

    # ── Save ──────────────────────────────────────────────────────────────
    preds_df = pd.concat(all_preds, ignore_index=True)
    preds_df.to_csv("final_predictions_2stage.csv", index=False)

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv("twostage_metrics.csv", index=False)

    print(f"\n{'='*60}")
    print(f"Saved final_predictions_2stage.csv ({len(preds_df)} rows)")
    print(f"Saved twostage_metrics.csv")
    print(f"{'='*60}")

    # ── Summary ───────────────────────────────────────────────────────────
    for zone in ZONES:
        sub = metrics_df[metrics_df["zone"] == zone]
        print(f"\n{zone} — test 2024 summary:")
        print(f"  avg MAE (overall) = {sub.mae_overall.mean():,.0f} m³")
        print(f"  avg NSE (overall) = {sub.nse_overall.mean():.3f}")
        print(f"  avg NSE (wet)     = {sub.nse_wet.mean():.3f}")
        print(f"  avg MAPE (wet)    = {sub.mape_wet_pct.mean():.1f}%")
        print(f"  avg zero-hit      = {sub.zero_hit_pct.mean():.1f}%")
        print(f"  avg F1 (regime)   = {sub.f1_regime.mean():.3f}")

    return preds_df, metrics_df


if __name__ == "__main__":
    main()


# ##############################################################################
# ## [SUPERSEDED — kept for reference only, NOT part of final pipeline]
# Step 4 — Conformal Prediction Intervals, Variant A (Global + Absolute baseline)
# ##############################################################################

"""
Step 4 — Conformal Prediction Intervals (Two-stage version)
============================================================
ปรับจาก step4_conformal.py เดิมให้รองรับ two-stage predictions

สิ่งที่เปลี่ยน vs เดิม:
  - ไม่ใช้ direct_models_all.pkl (ไม่มีแล้ว)
  - โหลด predictions จาก final_predictions_2stage.csv โดยตรง
    (calib 2023 + test 2024 อยู่ในไฟล์เดียวกันแล้ว)
  - nonconformity score = |y_actual - y_pred_2stage|
  - ที่เหลือ (q_hat, interval, coverage) เหมือนเดิม

Input  : final_predictions_2stage.csv   ← จาก step3e
Output : forecast_conformal_2stage.csv
         conformal_coverage_summary.csv

Run    : python step4_conformal_2stage.py
"""

import pandas as pd
import numpy as np

HORIZON    = 12
ZONES      = ["zone_A", "zone_B"]
ALPHA      = 0.10        # target coverage = 90%
CALIB_YEAR = 2023
TEST_YEAR  = 2024


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """
    Finite-sample corrected conformal quantile.
    q̂ = quantile(scores, ceil((n+1)(1-α)) / n)
    """
    n       = len(scores)
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


def main():
    preds = pd.read_csv("final_predictions_2stage.csv")

    # ── ตรวจ columns ──────────────────────────────────────────────────────
    required = {"year", "week", "zone", "horizon", "split",
                "y_actual", "y_pred_2stage"}
    missing  = required - set(preds.columns)
    if missing:
        raise KeyError(f"Missing columns in final_predictions_2stage.csv: {missing}")

    all_results    = []
    coverage_table = {}

    for zone in ZONES:
        z_preds = preds[preds["zone"] == zone].copy()

        calib_df = z_preds[z_preds["split"] == "calib"]
        test_df  = z_preds[z_preds["split"] == "test"]

        print(f"\n{'='*55}")
        print(f"Zone: {zone}  |  "
              f"calib={len(calib_df)} rows  test={len(test_df)} rows")
        print(f"{'='*55}")

        for h in range(1, HORIZON + 1):
            # ── Calibration nonconformity scores (2023) ───────────────────
            calib_h = calib_df[calib_df["horizon"] == h].dropna(
                subset=["y_actual", "y_pred_2stage"])
            y_ca    = calib_h["y_actual"].values
            yhat_ca = calib_h["y_pred_2stage"].values
            scores  = np.abs(y_ca - yhat_ca)

            if len(scores) == 0:
                print(f"  h={h:02d} | ⚠ no calibration rows — skipped")
                continue

            q_hat = conformal_quantile(scores, ALPHA)

            # ── Test predictions + intervals (2024) ───────────────────────
            test_h  = test_df[test_df["horizon"] == h].dropna(
                subset=["y_actual", "y_pred_2stage"])
            y_te    = test_h["y_actual"].values
            yhat_te = test_h["y_pred_2stage"].values

            lower = np.maximum(yhat_te - q_hat, 0)   # demand ≥ 0
            upper = yhat_te + q_hat

            # ── Coverage & interval width ─────────────────────────────────
            covered  = (y_te >= lower) & (y_te <= upper)
            coverage = covered.mean()
            iw_mean  = (upper - lower).mean()
            iw_med   = np.median(upper - lower)

            # Conditional coverage: wet vs dry
            wet      = y_te > 0
            dry      = ~wet
            cov_wet  = covered[wet].mean()  if wet.sum()  > 0 else np.nan
            cov_dry  = covered[dry].mean()  if dry.sum()  > 0 else np.nan

            coverage_table[(zone, h)] = {
                "coverage":    coverage,
                "cov_wet":     cov_wet,
                "cov_dry":     cov_dry,
                "q_hat":       q_hat,
                "IW_mean":     iw_mean,
                "IW_median":   iw_med,
                "n_calib":     len(scores),
                "n_test":      len(y_te),
            }

            print(f"  h={h:02d} | q̂={q_hat:>9,.0f} m³ | "
                  f"coverage={coverage:.3f} "
                  f"(wet={cov_wet:.2f} dry={cov_dry:.2f}) | "
                  f"IW={iw_mean:,.0f} m³")

            # ── Collect rows ──────────────────────────────────────────────
            out = test_h[["year","week","zone","horizon",
                           "y_actual","y_stage1_prob",
                           "y_stage2_mag","y_pred_2stage"]].copy()
            out["lower_90"] = lower
            out["upper_90"] = upper
            out["q_hat"]    = q_hat
            out["covered"]  = covered.astype(int)
            all_results.append(out)

    # ── Save predictions ──────────────────────────────────────────────────
    forecast_df = pd.concat(all_results, ignore_index=True)
    forecast_df.to_csv("forecast_conformal_2stage.csv", index=False)
    print(f"\nSaved forecast_conformal_2stage.csv — {len(forecast_df)} rows")

    # ── Coverage summary ──────────────────────────────────────────────────
    cov_rows = [{"zone": z, "horizon": h, **stats}
                for (z, h), stats in coverage_table.items()]
    cov_df = pd.DataFrame(cov_rows)
    cov_df.to_csv("conformal_coverage_summary.csv", index=False)
    print("Saved conformal_coverage_summary.csv")

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"Coverage (target: {1-ALPHA:.0%})  — below {1-ALPHA:.0%} = under-covered")
    print(f"{'='*55}")
    piv_cov = cov_df.pivot(index="horizon", columns="zone",
                            values="coverage").round(3)
    piv_wet = cov_df.pivot(index="horizon", columns="zone",
                            values="cov_wet").round(3)
    piv_dry = cov_df.pivot(index="horizon", columns="zone",
                            values="cov_dry").round(3)
    piv_iw  = cov_df.pivot(index="horizon", columns="zone",
                            values="IW_mean").round(0)
    piv_qh  = cov_df.pivot(index="horizon", columns="zone",
                            values="q_hat").round(0)

    print("\nOverall coverage:")
    print(piv_cov.to_string())
    print("\nWet-season coverage (demand > 0):")
    print(piv_wet.to_string())
    print("\nDry-season coverage (demand = 0):")
    print(piv_dry.to_string())
    print("\nMean Interval Width (m³/week):")
    print(piv_iw.to_string())
    print("\nq̂ (nonconformity quantile, m³):")
    print(piv_qh.to_string())

    # ── Aggregate ─────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("Aggregate summary")
    print(f"{'='*55}")
    for zone in ZONES:
        sub = cov_df[cov_df["zone"] == zone]
        below = (sub["coverage"] < (1 - ALPHA)).sum()
        print(f"\n{zone}:")
        print(f"  avg coverage = {sub['coverage'].mean():.3f}  "
              f"(target {1-ALPHA:.0%})")
        print(f"  below target = {below}/12 horizons")
        print(f"  avg IW       = {sub['IW_mean'].mean():,.0f} m³/week")
        print(f"  avg q̂       = {sub['q_hat'].mean():,.0f} m³")

    return forecast_df, cov_df


if __name__ == "__main__":
    main()


# ##############################################################################
# ## [SUPERSEDED — kept for reference only, NOT part of final pipeline]
# Step 4v2 — Mondrian Conformal Prediction, Variant B (Mondrian + Absolute)
# ##############################################################################

"""
Step 4v2 — Mondrian Conformal Prediction (Regime-conditional)
=============================================================
แทนที่ global q̂ ด้วย regime-specific q̂:

  q̂_wet  = conformal_quantile(scores[y_calib > 0],  α)
  q̂_dry  = conformal_quantile(scores[y_calib == 0], α)

Apply ตาม Stage 1 probability:
  prob >= threshold → apply q̂_wet  (active regime)
  prob <  threshold → apply q̂_dry  (inactive regime)

ข้อดีทางทฤษฎี (Venn–Mondrian conformal):
  - valid marginal coverage ภายใต้ exchangeability ต่อ regime
  - narrower intervals เพราะ calibrate เฉพาะ within-regime residuals
  - ไม่มี dry-season transition outliers ดึง q̂_wet ขึ้น

Input  : final_predictions_2stage.csv
         stage1_thresholds.pkl
Output : forecast_mondrian.csv
         mondrian_coverage_summary.csv

Run: python step4v2_mondrian_conformal.py
"""

import pandas as pd
import numpy as np
import joblib

HORIZON    = 12
ZONES      = ["zone_A", "zone_B"]
ALPHA      = 0.10           # target coverage = 90%
CALIB_YEAR = 2023
TEST_YEAR  = 2024
MIN_REGIME_N = 5            # ถ้า regime มีน้อยกว่านี้ → fallback to global q̂


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Finite-sample corrected conformal quantile."""
    n = len(scores)
    if n == 0:
        return np.inf
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


def main():
    preds      = pd.read_csv("final_predictions_2stage.csv")
    thresholds = joblib.load("stage1_thresholds.pkl")

    all_results    = []
    coverage_table = {}

    for zone in ZONES:
        z = preds[preds["zone"] == zone].copy()
        calib_df = z[z["split"] == "calib"]
        test_df  = z[z["split"] == "test"]

        print(f"\n{'='*60}")
        print(f"Zone: {zone}  |  calib={len(calib_df)}  test={len(test_df)}")
        print(f"{'='*60}")

        for h in range(1, HORIZON + 1):
            thr = thresholds[(zone, h)]

            # ── Calibration split by regime ───────────────────────────────
            ca_h = calib_df[calib_df["horizon"] == h].dropna(
                subset=["y_actual", "y_pred_2stage", "y_stage1_prob"])

            wet_mask_ca = ca_h["y_actual"] > 0
            dry_mask_ca = ~wet_mask_ca

            scores_all = np.abs(ca_h["y_actual"] - ca_h["y_pred_2stage"])
            scores_wet = scores_all[wet_mask_ca].values
            scores_dry = scores_all[dry_mask_ca].values

            n_wet_ca = len(scores_wet)
            n_dry_ca = len(scores_dry)

            # Compute regime-specific q̂ (fallback to global if too few)
            q_hat_global = conformal_quantile(scores_all.values, ALPHA)
            q_hat_wet    = (conformal_quantile(scores_wet, ALPHA)
                            if n_wet_ca >= MIN_REGIME_N else q_hat_global)
            q_hat_dry    = (conformal_quantile(scores_dry, ALPHA)
                            if n_dry_ca >= MIN_REGIME_N else q_hat_global)

            # ── Test predictions ──────────────────────────────────────────
            te_h = test_df[test_df["horizon"] == h].dropna(
                subset=["y_actual", "y_pred_2stage", "y_stage1_prob"])

            y_te    = te_h["y_actual"].values
            yhat_te = te_h["y_pred_2stage"].values
            prob_te = te_h["y_stage1_prob"].values

            # Assign q̂ per row based on Stage 1 classification
            active_mask = prob_te >= thr
            q_applied   = np.where(active_mask, q_hat_wet, q_hat_dry)

            lower = np.maximum(yhat_te - q_applied, 0)
            upper = yhat_te + q_applied

            # ── Coverage metrics ──────────────────────────────────────────
            covered  = (y_te >= lower) & (y_te <= upper)
            coverage = covered.mean()
            iw       = (upper - lower).mean()
            iw_med   = np.median(upper - lower)

            wet_te   = y_te > 0
            dry_te   = ~wet_te
            cov_wet  = covered[wet_te].mean() if wet_te.sum() > 0 else np.nan
            cov_dry  = covered[dry_te].mean() if dry_te.sum() > 0 else np.nan

            # vs global (reference)
            lower_g  = np.maximum(yhat_te - q_hat_global, 0)
            upper_g  = yhat_te + q_hat_global
            cov_g    = ((y_te >= lower_g) & (y_te <= upper_g)).mean()
            iw_g     = (upper_g - lower_g).mean()

            coverage_table[(zone, h)] = {
                "coverage":     coverage,
                "cov_wet":      cov_wet,
                "cov_dry":      cov_dry,
                "cov_global":   cov_g,
                "q_hat_wet":    q_hat_wet,
                "q_hat_dry":    q_hat_dry,
                "q_hat_global": q_hat_global,
                "IW_mondrian":  iw,
                "IW_global":    iw_g,
                "IW_median":    iw_med,
                "n_calib_wet":  n_wet_ca,
                "n_calib_dry":  n_dry_ca,
                "n_test":       len(y_te),
                "threshold":    thr,
            }

            delta_iw  = iw - iw_g
            delta_cov = coverage - cov_g
            print(f"  h={h:02d} | q̂_wet={q_hat_wet:>8,.0f}  "
                  f"q̂_dry={q_hat_dry:>8,.0f}  "
                  f"cov={coverage:.3f} (wet={cov_wet:.2f} dry={cov_dry:.2f})  "
                  f"IW={iw:,.0f}  "
                  f"Δcov={delta_cov:+.3f}  ΔIW={delta_iw:+,.0f}")

            # ── Collect output rows ───────────────────────────────────────
            out = te_h[["year","week","zone","horizon",
                         "y_actual","y_stage1_prob",
                         "y_stage2_mag","y_pred_2stage"]].copy()
            out["lower_90_mondrian"] = lower
            out["upper_90_mondrian"] = upper
            out["lower_90_global"]   = lower_g
            out["upper_90_global"]   = upper_g
            out["q_hat_applied"]     = q_applied
            out["q_hat_wet"]         = q_hat_wet
            out["q_hat_dry"]         = q_hat_dry
            out["regime_active"]     = active_mask.astype(int)
            out["covered_mondrian"]  = covered.astype(int)
            out["covered_global"]    = ((y_te >= lower_g) &
                                        (y_te <= upper_g)).astype(int)
            all_results.append(out)

    # ── Save ──────────────────────────────────────────────────────────────
    forecast_df = pd.concat(all_results, ignore_index=True)
    forecast_df.to_csv("forecast_mondrian.csv", index=False)

    cov_rows = [{"zone": z, "horizon": h, **stats}
                for (z, h), stats in coverage_table.items()]
    cov_df = pd.DataFrame(cov_rows)
    cov_df.to_csv("mondrian_coverage_summary.csv", index=False)

    print(f"\nSaved forecast_mondrian.csv — {len(forecast_df)} rows")
    print("Saved mondrian_coverage_summary.csv")

    # ── Summary tables ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Mondrian vs Global — coverage (target {1-ALPHA:.0%})")
    print(f"{'='*60}")
    piv_mon  = cov_df.pivot(index="horizon", columns="zone", values="coverage").round(3)
    piv_glo  = cov_df.pivot(index="horizon", columns="zone", values="cov_global").round(3)
    piv_wet  = cov_df.pivot(index="horizon", columns="zone", values="cov_wet").round(3)
    piv_iw_m = cov_df.pivot(index="horizon", columns="zone", values="IW_mondrian").round(0)
    piv_iw_g = cov_df.pivot(index="horizon", columns="zone", values="IW_global").round(0)

    print("\nOverall coverage — Mondrian:")
    print(piv_mon.to_string())
    print("\nOverall coverage — Global (reference):")
    print(piv_glo.to_string())
    print("\nWet-season coverage — Mondrian:")
    print(piv_wet.to_string())
    print("\nMean IW — Mondrian (m³):")
    print(piv_iw_m.to_string())
    print("\nMean IW — Global (m³):")
    print(piv_iw_g.to_string())

    # ── Aggregate ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("Aggregate comparison: Mondrian vs Global")
    print(f"{'='*60}")
    for zone in ZONES:
        mean_demand = 85810 if zone == "zone_A" else 30187
        sub = cov_df[cov_df["zone"] == zone]
        print(f"\n{zone}:")
        print(f"  coverage  Mon={sub.coverage.mean():.3f}  "
              f"Glo={sub.cov_global.mean():.3f}  "
              f"Δ={sub.coverage.mean()-sub.cov_global.mean():+.3f}")
        print(f"  below 90% Mon={( sub.coverage<0.9).sum()}/12  "
              f"Glo={(sub.cov_global<0.9).sum()}/12")
        print(f"  IW_mean   Mon={sub.IW_mondrian.mean():,.0f}  "
              f"Glo={sub.IW_global.mean():,.0f}  "
              f"Δ={sub.IW_mondrian.mean()-sub.IW_global.mean():+,.0f} m³")
        print(f"  IW/demand Mon={sub.IW_mondrian.mean()/mean_demand:.2f}×  "
              f"Glo={sub.IW_global.mean()/mean_demand:.2f}×")
        print(f"  q̂_wet avg={sub.q_hat_wet.mean():,.0f}  "
              f"q̂_dry avg={sub.q_hat_dry.mean():,.0f}  "
              f"q̂_global={sub.q_hat_global.mean():,.0f}")

    return forecast_df, cov_df


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 4v3 — Normalized Mondrian Conformal Prediction (FINAL, Variant D:
# Mondrian + Normalized -- confirmed as the variant used in the manuscript,
# Table 4 / Fig. 5). Computes and compares all 4 variants (A/B/C/D) in one run;
# D is saved as the primary columns (`lower_90`, `upper_90`, `covered_D`) in
# `forecast_normalized_mondrian.csv`.
# ##############################################################################

"""
Step 4v3 — Normalized Mondrian Conformal Prediction
=====================================================
Combined approach:
  1. Normalized score  : s = |y − ŷ| / (|ŷ| + ε)
  2. Mondrian          : แยก q̂ ตาม regime (wet / dry)

Interval:  ŷ ± q̂_norm × (|ŷ| + ε)
  → กว้างเมื่อ prediction สูง  (wet season peaks)
  → แคบเมื่อ prediction ต่ำ   (dry season / transitions)
  → IW ปรับตาม magnitude อัตโนมัติ

Compare 4 variants ใน run เดียว:
  A. Global   + Absolute   (baseline — step4 เดิม)
  B. Mondrian + Absolute   (step4v2)
  C. Global   + Normalized (ใหม่)
  D. Mondrian + Normalized (ใหม่ — strongest)

Input  : final_predictions_2stage.csv
         stage1_thresholds.pkl
Output : forecast_normalized_mondrian.csv
         normalized_mondrian_summary.csv  (4-variant comparison)

Run: python step4v3_normalized_mondrian.py
"""

import pandas as pd
import numpy as np
import joblib

HORIZON      = 12
ZONES        = ["zone_A", "zone_B"]
ALPHA        = 0.10        # target coverage = 90%
CALIB_YEAR   = 2023
TEST_YEAR    = 2024
MIN_N        = 5           # min regime samples สำหรับ Mondrian
EPSILON      = 1_000       # m³ — ป้องกัน div/0 เมื่อ ŷ ≈ 0


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    if n == 0:
        return np.inf
    q_level = min(np.ceil((n + 1) * (1 - alpha)) / n, 1.0)
    return float(np.quantile(scores, q_level))


def abs_scores(y, yhat):
    return np.abs(y - yhat)


def norm_scores(y, yhat, eps=EPSILON):
    return np.abs(y - yhat) / (np.abs(yhat) + eps)


def apply_abs_interval(yhat, q):
    lower = np.maximum(yhat - q, 0)
    upper = yhat + q
    return lower, upper


def apply_norm_interval(yhat, q_norm, eps=EPSILON):
    half  = q_norm * (np.abs(yhat) + eps)
    lower = np.maximum(yhat - half, 0)
    upper = yhat + half
    return lower, upper


def coverage_stats(y, lower, upper):
    covered  = (y >= lower) & (y <= upper)
    wet      = y > 0
    dry      = ~wet
    return {
        "coverage":  covered.mean(),
        "cov_wet":   covered[wet].mean() if wet.sum() > 0 else np.nan,
        "cov_dry":   covered[dry].mean() if dry.sum() > 0 else np.nan,
        "IW_mean":   (upper - lower).mean(),
        "IW_median": np.median(upper - lower),
        "IW_wet":    (upper - lower)[wet].mean() if wet.sum() > 0 else np.nan,
    }


def main():
    preds      = pd.read_csv("final_predictions_2stage.csv")
    thresholds = joblib.load("stage1_thresholds.pkl")

    all_rows  = []
    log_rows  = []

    for zone in ZONES:
        mean_demand = 85_810 if zone == "zone_A" else 30_187
        z        = preds[preds["zone"] == zone].copy()
        calib_df = z[z["split"] == "calib"]
        test_df  = z[z["split"] == "test"]

        print(f"\n{'='*65}")
        print(f"Zone: {zone}  |  mean demand ≈ {mean_demand:,.0f} m³")
        print(f"{'='*65}")
        print(f"{'h':>3} | {'q̂abs_g':>10} {'q̂abs_wet':>10} {'q̂nrm_g':>8} {'q̂nrm_wet':>9} "
              f"| {'covA':>5} {'covB':>5} {'covC':>5} {'covD':>5} "
              f"| {'IW_A':>8} {'IW_D':>8} {'ratio':>5}")
        print("-"*100)

        for h in range(1, HORIZON + 1):
            thr   = thresholds[(zone, h)]
            ca_h  = calib_df[calib_df["horizon"] == h].dropna(
                        subset=["y_actual","y_pred_2stage","y_stage1_prob"])
            te_h  = test_df[test_df["horizon"] == h].dropna(
                        subset=["y_actual","y_pred_2stage","y_stage1_prob"])

            y_ca   = ca_h["y_actual"].values
            yh_ca  = ca_h["y_pred_2stage"].values
            y_te   = te_h["y_actual"].values
            yh_te  = te_h["y_pred_2stage"].values
            prob   = te_h["y_stage1_prob"].values
            active = prob >= thr

            wet_ca = y_ca > 0
            dry_ca = ~wet_ca

            # ── Calibration scores ────────────────────────────────────────
            s_abs_all  = abs_scores(y_ca, yh_ca)
            s_abs_wet  = s_abs_all[wet_ca]
            s_abs_dry  = s_abs_all[dry_ca]

            s_nrm_all  = norm_scores(y_ca, yh_ca)
            s_nrm_wet  = s_nrm_all[wet_ca]
            s_nrm_dry  = s_nrm_all[dry_ca]

            # ── q̂ per variant ─────────────────────────────────────────────
            q_abs_g   = conformal_quantile(s_abs_all, ALPHA)
            q_abs_wet = (conformal_quantile(s_abs_wet, ALPHA)
                         if len(s_abs_wet) >= MIN_N else q_abs_g)
            q_abs_dry = (conformal_quantile(s_abs_dry, ALPHA)
                         if len(s_abs_dry) >= MIN_N else q_abs_g)

            q_nrm_g   = conformal_quantile(s_nrm_all, ALPHA)
            q_nrm_wet = (conformal_quantile(s_nrm_wet, ALPHA)
                         if len(s_nrm_wet) >= MIN_N else q_nrm_g)
            q_nrm_dry = (conformal_quantile(s_nrm_dry, ALPHA)
                         if len(s_nrm_dry) >= MIN_N else q_nrm_g)

            # ── Test intervals ────────────────────────────────────────────
            # A: Global + Absolute
            lo_A, up_A = apply_abs_interval(yh_te, q_abs_g)
            # B: Mondrian + Absolute
            q_abs_app  = np.where(active, q_abs_wet, q_abs_dry)
            lo_B, up_B = apply_abs_interval(yh_te, q_abs_app)
            # C: Global + Normalized
            lo_C, up_C = apply_norm_interval(yh_te, q_nrm_g)
            # D: Mondrian + Normalized  ← primary output
            q_nrm_app  = np.where(active, q_nrm_wet, q_nrm_dry)
            lo_D, up_D = apply_norm_interval(yh_te, q_nrm_app)

            # ── Coverage & IW ─────────────────────────────────────────────
            covA = coverage_stats(y_te, lo_A, up_A)
            covB = coverage_stats(y_te, lo_B, up_B)
            covC = coverage_stats(y_te, lo_C, up_C)
            covD = coverage_stats(y_te, lo_D, up_D)

            iw_ratio = covD["IW_mean"] / mean_demand

            print(f"  {h:2d} | "
                  f"{q_abs_g:>10,.0f} {q_abs_wet:>10,.0f} "
                  f"{q_nrm_g:>8.3f} {q_nrm_wet:>9.3f} | "
                  f"{covA['coverage']:>5.3f} {covB['coverage']:>5.3f} "
                  f"{covC['coverage']:>5.3f} {covD['coverage']:>5.3f} | "
                  f"{covA['IW_mean']:>8,.0f} {covD['IW_mean']:>8,.0f} "
                  f"{iw_ratio:>5.2f}×")

            log_rows.append({
                "zone": zone, "horizon": h,
                "threshold": thr,
                # q̂ values
                "q_abs_global":   round(q_abs_g,   2),
                "q_abs_wet":      round(q_abs_wet,  2),
                "q_abs_dry":      round(q_abs_dry,  2),
                "q_norm_global":  round(q_nrm_g,    6),
                "q_norm_wet":     round(q_nrm_wet,  6),
                "q_norm_dry":     round(q_nrm_dry,  6),
                # Coverage — A
                "cov_A":     round(covA["coverage"], 4),
                "cov_wet_A": round(covA["cov_wet"],  4) if not np.isnan(covA["cov_wet"]) else np.nan,
                "IW_A":      round(covA["IW_mean"],  2),
                # Coverage — B
                "cov_B":     round(covB["coverage"], 4),
                "cov_wet_B": round(covB["cov_wet"],  4) if not np.isnan(covB["cov_wet"]) else np.nan,
                "IW_B":      round(covB["IW_mean"],  2),
                # Coverage — C
                "cov_C":     round(covC["coverage"], 4),
                "cov_wet_C": round(covC["cov_wet"],  4) if not np.isnan(covC["cov_wet"]) else np.nan,
                "IW_C":      round(covC["IW_mean"],  2),
                # Coverage — D (primary)
                "cov_D":        round(covD["coverage"], 4),
                "cov_wet_D":    round(covD["cov_wet"],  4) if not np.isnan(covD["cov_wet"]) else np.nan,
                "cov_dry_D":    round(covD["cov_dry"],  4) if not np.isnan(covD["cov_dry"]) else np.nan,
                "IW_D":         round(covD["IW_mean"],  2),
                "IW_wet_D":     round(covD["IW_wet"],   2) if not np.isnan(covD["IW_wet"]) else np.nan,
                "IW_ratio_D":   round(iw_ratio, 3),
                "n_calib_wet":  int(wet_ca.sum()),
                "n_calib_dry":  int(dry_ca.sum()),
                "n_test":       len(y_te),
            })

            # ── Collect test rows (variant D as primary) ──────────────────
            out = te_h[["year","week","zone","horizon",
                         "y_actual","y_stage1_prob",
                         "y_stage2_mag","y_pred_2stage"]].copy()
            out["lower_90"]       = lo_D
            out["upper_90"]       = up_D
            out["lower_90_A"]     = lo_A
            out["upper_90_A"]     = up_A
            out["q_norm_applied"] = q_nrm_app
            out["regime_active"]  = active.astype(int)
            out["covered_D"]      = ((y_te >= lo_D) & (y_te <= up_D)).astype(int)
            out["covered_A"]      = ((y_te >= lo_A) & (y_te <= up_A)).astype(int)
            all_rows.append(out)

    # ── Save ──────────────────────────────────────────────────────────────
    forecast_df = pd.concat(all_rows, ignore_index=True)
    forecast_df.to_csv("forecast_normalized_mondrian.csv", index=False)

    summary = pd.DataFrame(log_rows)
    summary.to_csv("normalized_mondrian_summary.csv", index=False)

    print(f"\nSaved forecast_normalized_mondrian.csv — {len(forecast_df)} rows")
    print("Saved normalized_mondrian_summary.csv")

    # ── Aggregate comparison ──────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("AGGREGATE COMPARISON — 4 variants (target coverage 90%)")
    print(f"{'='*65}")
    print(f"{'':8} {'A:Glo+Abs':>12} {'B:Mon+Abs':>12} "
          f"{'C:Glo+Nrm':>12} {'D:Mon+Nrm':>12}")
    print("-"*60)

    for zone in ZONES:
        mean_dem = 85_810 if zone == "zone_A" else 30_187
        sub = summary[summary["zone"] == zone]
        for metric, cols, fmt in [
            ("coverage",  ["cov_A","cov_B","cov_C","cov_D"],  ".3f"),
            ("below 90%", None, None),
            ("IW_mean",   ["IW_A","IW_B","IW_C","IW_D"],      ",.0f"),
            ("IW/demand", None, None),
        ]:
            if metric == "below 90%":
                vals = [f"{(sub[c]<0.9).sum()}/12" for c in ["cov_A","cov_B","cov_C","cov_D"]]
                print(f"  {zone[:6]:8} {metric:10} "+" ".join(f"{v:>12}" for v in vals))
            elif metric == "IW/demand":
                vals = [f"{sub[c].mean()/mean_dem:.2f}×" for c in ["IW_A","IW_B","IW_C","IW_D"]]
                print(f"  {'':8} {'IW/demand':10} "+" ".join(f"{v:>12}" for v in vals))
                print()
            else:
                vals = [f"{sub[c].mean():{fmt}}" for c in cols]
                print(f"  {zone[:6]:8} {metric:10} "+" ".join(f"{v:>12}" for v in vals))


if __name__ == "__main__":
    main()


# ##############################################################################
# ## Step 5 — Performance Metrics + SHAP Analysis
# *** EDITED vs. your original file ***
# Your uploaded script's docstring and `pd.read_csv(...)` call pointed at
# `forecast_mondrian.csv`, which is the Step 4v2 / Variant B output. Since you
# confirmed Variant D (Step 4v3, Mondrian+Normalized) is the version actually
# used in the manuscript, I changed the input filename below to
# `forecast_normalized_mondrian.csv`. No other logic was changed — the metrics
# code only uses `y_actual`/`y_pred_2stage`, both of which exist unchanged in
# the Variant D output file, so this is a safe, minimal edit.
# ##############################################################################

"""
Step 5 — Performance Metrics + SHAP Analysis (Two-stage version)
=================================================================
ปรับจาก step5_metrics_shap.py เดิม:
  - ไม่ใช้ direct_models_all.pkl (ไม่มีแล้ว)
  - โหลด catboost_models.pkl / lightgbm_models.pkl / stack_weights.pkl
  - metrics จาก forecast_normalized_mondrian.csv (Variant D — FINAL, EDITED from original Variant B reference)
  - เพิ่ม Stage 1 classifier SHAP
  - แก้ persistence baseline: GID_B_m3 → GIR_B_m3
  - เพิ่ม wet/dry season metrics breakdown

Input  : ml_features_phase4.csv
         forecast_normalized_mondrian.csv  ← Step 4v3 output (Variant D)
         catboost_models.pkl
         stage1_classifiers.pkl
Output : performance_metrics_all.csv
         shap_beeswarm_zone_A/B.png
         shap_importance_zone_A/B.csv
         shap_by_horizon_zone_A/B.csv
         shap_stage1_zone_A/B.png      ← classifier SHAP (ใหม่)
"""

import pandas as pd
import numpy as np
import joblib
import shap
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

HORIZON   = 12
ZONES     = ["zone_A", "zone_B"]
TEST_YEAR = 2024

CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
TARGET_LAGS = [1, 2, 3, 4]


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def get_regressor_features(df: pd.DataFrame,
                            df_zone: pd.DataFrame) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def get_clf_features(df_zone: pd.DataFrame, target_col: str) -> list:
    lag_cols  = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted    = CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]


def calc_metrics(y_obs: np.ndarray, y_sim: np.ndarray,
                 label: str = "Model") -> dict:
    eps  = 1e-6
    mae  = np.mean(np.abs(y_obs - y_sim))
    rmse = np.sqrt(np.mean((y_obs - y_sim) ** 2))
    # MAPE nonzero only (avoid astronomical values from near-zero weeks)
    nz   = y_obs > 0
    mape = (np.mean(np.abs((y_obs[nz] - y_sim[nz]) / y_obs[nz])) * 100
            if nz.sum() > 0 else np.nan)
    sst  = np.sum((y_obs - np.mean(y_obs)) ** 2) + eps
    nse  = 1 - np.sum((y_obs - y_sim) ** 2) / sst
    if len(y_obs) > 1 and np.std(y_obs) > 0 and np.std(y_sim) > 0:
        r     = np.corrcoef(y_obs, y_sim)[0, 1]
        alpha = np.std(y_sim) / np.std(y_obs)
        beta  = np.mean(y_sim) / (np.mean(y_obs) + eps)
        kge   = 1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)
    else:
        kge = np.nan
    return {"Model": label, "MAE": mae, "RMSE": rmse,
            "MAPE_nonzero(%)": mape, "NSE": nse, "KGE": kge}


# ─────────────────────────────────────────────────────────────────────────────
#  Step 5A — Metrics
# ─────────────────────────────────────────────────────────────────────────────
def run_metrics():
    df       = pd.read_csv("ml_features_phase4.csv")
    forecast = pd.read_csv("forecast_normalized_mondrian.csv")   # Variant D output (EDITED — see note above)

    # ตรวจว่ามี column ที่ต้องการ
    pred_col = ("y_pred_2stage" if "y_pred_2stage" in forecast.columns
                else "y_pred")

    metrics_rows = []

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone    = df[df["zone"] == zone]

        for h in range(1, HORIZON + 1):
            sub = forecast[(forecast["zone"]    == zone) &
                           (forecast["horizon"] == h)].dropna(
                               subset=["y_actual", pred_col])
            y_obs  = sub["y_actual"].values
            y_pred = sub[pred_col].values

            # ── Two-stage model ───────────────────────────────────────────
            metrics_rows.append({
                **calc_metrics(y_obs, y_pred, "TwoStage"),
                "zone": zone, "horizon": h,
            })

            # ── Wet-season only ───────────────────────────────────────────
            wet = y_obs > 0
            if wet.sum() > 1:
                metrics_rows.append({
                    **calc_metrics(y_obs[wet], y_pred[wet], "TwoStage_wet"),
                    "zone": zone, "horizon": h,
                })

            # ── Persistence baseline (nearest available lag to h) ────────
            AVAIL_LAGS = [1, 2, 3, 4, 8, 12]
            best_lag   = min(AVAIL_LAGS, key=lambda x: abs(x - h))
            lag_col    = f"{target_col}_lag{best_lag}"
            test_z     = df_zone[df_zone["year"] == TEST_YEAR].dropna(
                             subset=[f"y_h{h}", lag_col])
            if len(test_z) > 0:
                y_p  = test_z[f"y_h{h}"].values
                y_lg = test_z[lag_col].values
                n    = min(len(y_p), len(y_lg))
                metrics_rows.append({
                    **calc_metrics(y_p[:n], y_lg[:n], "Persistence"),
                    "zone": zone, "horizon": h,
                })

            # ── Climatology baseline (mean of training demand) ────────────
            train_mean = (df_zone[df_zone["year"].isin([2020, 2021, 2022])]
                          [target_col].mean())
            clim_pred  = np.full_like(y_obs, train_mean, dtype=float)
            metrics_rows.append({
                **calc_metrics(y_obs, clim_pred, "Climatology"),
                "zone": zone, "horizon": h,
            })

    metrics_df = pd.DataFrame(metrics_rows).round(4)
    metrics_df.to_csv("performance_metrics_all.csv", index=False)
    print("Saved performance_metrics_all.csv")

    # Print summary for key horizons
    for zone in ZONES:
        print(f"\n{'─'*75}")
        print(f"Zone: {zone}")
        sub = metrics_df[
            (metrics_df["zone"] == zone) &
            (metrics_df["horizon"].isin([1, 4, 8, 12]))
        ]
        print(sub[["Model","horizon","MAE","NSE","KGE","MAPE_nonzero(%)"]].
              to_string(index=False))

    return metrics_df


# ─────────────────────────────────────────────────────────────────────────────
#  Step 5B — SHAP (Regressor: CatBoost)
# ─────────────────────────────────────────────────────────────────────────────
def run_shap_regressor():
    df         = pd.read_csv("ml_features_phase4.csv")
    cat_models = joblib.load("catboost_models.pkl")

    for zone in ZONES:
        df_zone   = df[df["zone"] == zone].copy()
        feat_cols = get_regressor_features(df, df_zone)
        test_df   = df_zone[df_zone["year"] == TEST_YEAR].dropna(
                        subset=feat_cols)
        X_test    = test_df[feat_cols].values

        cat_h1    = cat_models[(zone, 1)]
        explainer = shap.TreeExplainer(cat_h1)
        shap_vals = explainer(X_test)

        # ── 1. Beeswarm ───────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 7))
        shap.plots.beeswarm(shap_vals, max_display=15,
                            show=False, plot_size=(10, 7))
        plt.title(f"SHAP — Regressor (CatBoost) {zone}, h=1", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"shap_beeswarm_{zone}.png", dpi=300, bbox_inches="tight")
        plt.close()
        print(f"Saved shap_beeswarm_{zone}.png")

        # ── 2. Mean |SHAP| table ─────────────────────────────────────────
        imp = pd.DataFrame({
            "feature":       feat_cols,
            "mean_abs_shap": np.abs(shap_vals.values).mean(axis=0),
        }).sort_values("mean_abs_shap", ascending=False)
        imp.to_csv(f"shap_importance_{zone}.csv", index=False)
        print(f"\nTop-10 features for {zone}:")
        print(imp.head(10).to_string(index=False))

        # ── 3. SHAP across horizons (h=1,4,8,12) ─────────────────────────
        horizon_shap = {}
        for h in [1, 4, 8, 12]:
            cat_h  = cat_models[(zone, h)]
            exp_h  = shap.TreeExplainer(cat_h)
            sv_h   = exp_h(X_test)
            horizon_shap[f"h{h}"] = np.abs(sv_h.values).mean(axis=0)

        shap_by_h = pd.DataFrame(horizon_shap, index=feat_cols)
        shap_by_h.to_csv(f"shap_by_horizon_{zone}.csv")
        print(f"Saved shap_by_horizon_{zone}.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  Step 5C — SHAP (Stage 1: LightGBM Classifier)
# ─────────────────────────────────────────────────────────────────────────────
def run_shap_classifier():
    df          = pd.read_csv("ml_features_phase4.csv")
    classifiers = joblib.load("stage1_classifiers.pkl")

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone    = df[df["zone"] == zone].copy()
        clf_feats  = get_clf_features(df_zone, target_col)

        test_df   = df_zone[df_zone["year"] == TEST_YEAR].dropna(
                        subset=clf_feats)
        X_test    = test_df[clf_feats].values

        clf_h1    = classifiers[(zone, 1)]
        explainer = shap.TreeExplainer(clf_h1)
        shap_vals = explainer(X_test)

        # ── Beeswarm ──────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(9, 6))
        shap.plots.beeswarm(shap_vals, max_display=12,
                            show=False, plot_size=(9, 6))
        plt.title(f"SHAP — Stage 1 Classifier {zone}, h=1", fontsize=12)
        plt.tight_layout()
        plt.savefig(f"shap_stage1_{zone}.png", dpi=300, bbox_inches="tight")
        plt.close()
        print(f"Saved shap_stage1_{zone}.png")

        # ── Mean |SHAP| for classifier ───────────────────────────────────
        clf_imp = pd.DataFrame({
            "feature":       clf_feats,
            "mean_abs_shap": np.abs(shap_vals.values).mean(axis=0),
        }).sort_values("mean_abs_shap", ascending=False)
        clf_imp.to_csv(f"shap_stage1_importance_{zone}.csv", index=False)
        print(f"\nTop classifier features for {zone}:")
        print(clf_imp.to_string(index=False))

        # ── SHAP across horizons (h=1,4,8,12) — classifier ───────────────
        horizon_clf_shap = {}
        for h in [1, 4, 8, 12]:
            clf_h = classifiers[(zone, h)]
            exp_h = shap.TreeExplainer(clf_h)
            sv_h  = exp_h(X_test)
            horizon_clf_shap[f"h{h}"] = np.abs(sv_h.values).mean(axis=0)

        shap_clf_by_h = pd.DataFrame(horizon_clf_shap, index=clf_feats)
        shap_clf_by_h.to_csv(f"shap_stage1_by_horizon_{zone}.csv")
        print(f"Saved shap_stage1_by_horizon_{zone}.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Step 5A — Performance Metrics")
    print("=" * 60)
    metrics = run_metrics()

    print("\n" + "=" * 60)
    print("Step 5B — SHAP: Regressor (CatBoost)")
    print("=" * 60)
    run_shap_regressor()

    print("\n" + "=" * 60)
    print("Step 5C — SHAP: Stage 1 Classifier (LightGBM)")
    print("=" * 60)
    run_shap_classifier()

    print("\nPhase 4 complete ✅")
    print("\nOutputs:")
    print("  performance_metrics_all.csv")
    print("  shap_beeswarm_zone_A/B.png")
    print("  shap_importance_zone_A/B.csv")
    print("  shap_by_horizon_zone_A/B.csv")
    print("  shap_stage1_zone_A/B.png")
    print("  shap_stage1_importance_zone_A/B.csv")
    print("  shap_stage1_by_horizon_zone_A/B.csv")


# ##############################################################################
# ## SHAP Analysis — standalone alternate version (Zone A vs Zone B)
# NOTE: this appears to be a near-duplicate/alternate of the SHAP portion
# already inside Step 5 above (same CLASSIFIER_FEATURES, same helper function
# names). Kept here verbatim since it was in your notebook as its own cell;
# you likely only need to run one of the two SHAP implementations.
# ##############################################################################

"""
SHAP Analysis — Two-stage Model (Zone A vs Zone B)
===================================================
ปรับจาก code ต้นฉบับให้สอดคล้องกับ two-stage setup:
  - โหลด catboost_models.pkl แยก (ไม่ใช่ direct_models_all.pkl)
  - วิเคราะห์แยก Zone A / Zone B (ไม่ใช่ mask จาก combined set)
  - เพิ่ม SHAP across horizons (h=1,4,8,12)
  - เพิ่ม Stage 1 classifier SHAP
  - feature_cols ดึงจาก get_regressor_features / get_clf_features

Run: python shap_analysis.py
"""

import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────────
HORIZON   = 12
ZONES     = ["zone_A", "zone_B"]
TEST_YEAR = 2024
MAX_DISPLAY = 14       # จำนวน features ใน beeswarm

CLASSIFIER_FEATURES = [
    "WoY_sin", "WoY_cos", "MoY_sin", "MoY_cos",
    "ET0_mm_week", "P_mm_week", "P_eff_mm",
    "SPI_4", "drought_flag", "MEI", "AI_week",
]
TARGET_LAGS = [1, 2, 3, 4]


def get_regressor_features(df: pd.DataFrame, df_zone: pd.DataFrame) -> list:
    exclude = {"year", "week", "month", "date", "zone", "target_col",
               "NIR_A_m3", "GIR_B_m3", "P_4week"}
    exclude |= {f"y_h{h}" for h in range(1, HORIZON + 1)}
    cols = [c for c in df.columns if c not in exclude]
    return [c for c in cols if not df_zone[c].isna().all()]


def get_clf_features(df_zone: pd.DataFrame, target_col: str) -> list:
    lag_cols  = [f"{target_col}_lag{k}" for k in TARGET_LAGS]
    roll_cols = [f"{target_col}_roll4_mean", f"{target_col}_roll8_mean"]
    wanted    = CLASSIFIER_FEATURES + lag_cols + roll_cols
    return [c for c in wanted
            if c in df_zone.columns and not df_zone[c].isna().all()]


def shap_beeswarm(shap_explanation, title: str, outpath: str,
                  max_display: int = MAX_DISPLAY):
    """Save beeswarm plot."""
    plt.figure(figsize=(10, max(6, max_display * 0.45)))
    shap.plots.beeswarm(shap_explanation, max_display=max_display, show=False)
    plt.title(title, fontsize=12, pad=10)
    plt.tight_layout()
    plt.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved {outpath}")


def shap_bar(shap_explanation, title: str, outpath: str,
             max_display: int = MAX_DISPLAY):
    """Save bar plot (mean |SHAP|)."""
    plt.figure(figsize=(9, max(5, max_display * 0.35)))
    shap.plots.bar(shap_explanation, max_display=max_display, show=False)
    plt.title(title, fontsize=12, pad=10)
    plt.tight_layout()
    plt.savefig(outpath, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved {outpath}")


# ─────────────────────────────────────────────────────────────────────────────
#  Part 1 — Regressor SHAP (CatBoost)
# ─────────────────────────────────────────────────────────────────────────────
def run_regressor_shap():
    print("\n" + "="*60)
    print("Part 1: Regressor SHAP (CatBoost h=1)")
    print("="*60)

    df         = pd.read_csv("ml_features_phase4.csv")
    cat_models = joblib.load("catboost_models.pkl")

    all_importance = []   # รวมทั้ง 2 zones สำหรับ comparison

    for zone in ZONES:
        target_col  = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone     = df[df["zone"] == zone].copy()
        feature_cols = get_regressor_features(df, df_zone)

        test_df = df_zone[df_zone["year"] == TEST_YEAR].dropna(
                      subset=feature_cols)
        X_test  = test_df[feature_cols].values

        cat_h1    = cat_models[(zone, 1)]
        explainer = shap.TreeExplainer(cat_h1)
        # Pass feature_names so beeswarm shows real names (not 'Feature N')
        shap_vals = explainer(X_test)
        shap_vals.feature_names = feature_cols

        print(f"\n[{zone}]  n_test={len(X_test)}  n_features={len(feature_cols)}")

        # ── 1a. Beeswarm ──────────────────────────────────────────────────
        shap_beeswarm(
            shap_vals,
            title=f"SHAP Beeswarm — Demand Magnitude ({zone}, h=1)",
            outpath=f"shap_beeswarm_{zone}_h1.png",
        )

        # ── 1b. Bar plot ──────────────────────────────────────────────────
        shap_bar(
            shap_vals,
            title=f"Mean |SHAP| — {zone} (h=1)",
            outpath=f"shap_bar_{zone}_h1.png",
        )

        # ── 1c. Mean |SHAP| table ─────────────────────────────────────────
        mean_abs = np.abs(shap_vals.values).mean(axis=0)
        imp = pd.DataFrame({
            "feature":       feature_cols,
            "mean_abs_shap": mean_abs,
            "zone":          zone,
        }).sort_values("mean_abs_shap", ascending=False)
        imp.to_csv(f"shap_importance_{zone}_h1.csv", index=False)
        print(f"  Top-10 features:")
        print(imp.head(10)[["feature","mean_abs_shap"]].to_string(index=False))
        all_importance.append(imp)

        # ── 1d. SHAP across horizons (h=1, 4, 8, 12) ─────────────────────
        horizon_shap = {}
        for h in range(1, HORIZON + 1):
            cat_h  = cat_models[(zone, h)]
            exp_h  = shap.TreeExplainer(cat_h)
            sv_h   = exp_h(X_test)
            sv_h.feature_names = feature_cols
            horizon_shap[f"h{h}"] = np.abs(sv_h.values).mean(axis=0)

        df_by_h = pd.DataFrame(horizon_shap, index=feature_cols)
        df_by_h.to_csv(f"shap_by_horizon_{zone}.csv")
        print(f"  Saved shap_by_horizon_{zone}.csv")

        # ── 1e. Horizon horizon heatmap ───────────────────────────────────
        top_feats = imp.head(10)["feature"].tolist()
        fig, ax   = plt.subplots(figsize=(8, 5))
        data      = df_by_h.loc[top_feats].T
        im        = ax.imshow(data.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(top_feats)))
        ax.set_xticklabels(top_feats, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(data.index)))
        ax.set_yticklabels(data.index, fontsize=9)
        plt.colorbar(im, ax=ax, label="Mean |SHAP|")
        ax.set_title(f"SHAP Horizon Heatmap — {zone} (top-10 features)", fontsize=11)
        plt.tight_layout()
        hmap_path = f"shap_horizon_heatmap_{zone}.png"
        plt.savefig(hmap_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  Saved {hmap_path}")

    # ── 1f. Cross-zone comparison table ──────────────────────────────────
    za = all_importance[0].set_index("feature")["mean_abs_shap"].rename("SHAP_ZoneA")
    zb = all_importance[1].set_index("feature")["mean_abs_shap"].rename("SHAP_ZoneB")
    cross = pd.concat([za, zb], axis=1).fillna(0)
    cross["rank_A"] = cross["SHAP_ZoneA"].rank(ascending=False).astype(int)
    cross["rank_B"] = cross["SHAP_ZoneB"].rank(ascending=False).astype(int)
    cross = cross.sort_values("SHAP_ZoneA", ascending=False)
    cross.to_csv("shap_importance_by_zone.csv")
    print(f"\nCross-zone comparison (sorted by Zone A):")
    print(cross.head(15).round(2).to_string())
    print("Saved shap_importance_by_zone.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  Part 2 — Stage 1 Classifier SHAP (LightGBM)
# ─────────────────────────────────────────────────────────────────────────────
def run_classifier_shap():
    print("\n" + "="*60)
    print("Part 2: Stage 1 Classifier SHAP (LightGBM h=1)")
    print("="*60)

    df          = pd.read_csv("ml_features_phase4.csv")
    classifiers = joblib.load("stage1_classifiers.pkl")

    for zone in ZONES:
        target_col = "NIR_A_m3" if zone == "zone_A" else "GIR_B_m3"
        df_zone    = df[df["zone"] == zone].copy()
        clf_feats  = get_clf_features(df_zone, target_col)

        test_df = df_zone[df_zone["year"] == TEST_YEAR].dropna(subset=clf_feats)
        # LightGBM TreeExplainer ต้องการ DataFrame (ไม่ใช่ ndarray)
        X_test  = test_df[clf_feats]

        clf_h1    = classifiers[(zone, 1)]
        explainer = shap.TreeExplainer(clf_h1)
        shap_vals = explainer(X_test)

        print(f"\n[{zone}]  n_test={len(X_test)}  clf_features={len(clf_feats)}")

        # ── 2a. Beeswarm ──────────────────────────────────────────────────
        shap_beeswarm(
            shap_vals,
            title=f"SHAP Beeswarm — Regime Classifier ({zone}, h=1)",
            outpath=f"shap_stage1_beeswarm_{zone}.png",
        )

        # ── 2b. Mean |SHAP| ───────────────────────────────────────────────
        mean_abs = np.abs(shap_vals.values).mean(axis=0)
        clf_imp  = pd.DataFrame({
            "feature":       clf_feats,
            "mean_abs_shap": mean_abs,
        }).sort_values("mean_abs_shap", ascending=False)
        clf_imp.to_csv(f"shap_stage1_importance_{zone}.csv", index=False)
        print(f"  Classifier top features:")
        print(clf_imp.to_string(index=False))

        # ── 2c. SHAP across horizons — classifier ─────────────────────────
        clf_by_h = {}
        for h in range(1, HORIZON + 1):
            clf_h  = classifiers[(zone, h)]
            exp_h  = shap.TreeExplainer(clf_h)
            sv_h   = exp_h(X_test)
            clf_by_h[f"h{h}"] = np.abs(sv_h.values).mean(axis=0)

        pd.DataFrame(clf_by_h, index=clf_feats).to_csv(
            f"shap_stage1_by_horizon_{zone}.csv")
        print(f"  Saved shap_stage1_by_horizon_{zone}.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_regressor_shap()
    run_classifier_shap()

    print("\n" + "="*60)
    print("SHAP Analysis Complete")
    print("="*60)
    print("Outputs:")
    print("  shap_beeswarm_zone_A/B_h1.png      ← Figure: demand drivers")
    print("  shap_bar_zone_A/B_h1.png           ← Figure: ranked importance")
    print("  shap_horizon_heatmap_zone_A/B.png  ← Figure: drivers vs horizon")
    print("  shap_importance_zone_A/B_h1.csv")
    print("  shap_importance_by_zone.csv        ← cross-zone comparison")
    print("  shap_by_horizon_zone_A/B.csv")
    print("  shap_stage1_beeswarm_zone_A/B.png  ← Figure: regime drivers")
    print("  shap_stage1_importance_zone_A/B.csv")
    print("  shap_stage1_by_horizon_zone_A/B.csv")


# ##############################################################################
# ## Fig. 5 — Forecast vs Actual with Conformal Intervals (2024)
# *** EDITED vs. your original file ***
# Same Variant B -> Variant D fix as Step 5: input filename changed to
# `forecast_normalized_mondrian.csv`, and column names
# `lower_90_mondrian`/`upper_90_mondrian`/`covered_mondrian` changed to the
# Variant D output's actual column names `lower_90`/`upper_90`/`covered_D`
# (confirmed from the Step 4v3 script's own `out[...]=` assignments). All
# plotting/styling logic is untouched.
# ##############################################################################

"""
Fig 5 — Forecast vs Actual with Mondrian Conformal Intervals (2024)
====================================================================
Layout: 2 rows × 2 columns
  Row 1: Zone A — h=1 (left) and h=4 (right)
  Row 2: Zone B — h=1 (left) and h=4 (right)

Each panel shows:
  - Actual demand (black line)
  - Point forecast ŷ (coloured line)
  - 90% Mondrian conformal interval (shaded band)
  - Dry/zero-demand weeks shaded lightly
  - Conformal coverage annotated

Input  : forecast_normalized_mondrian.csv  (from step4v3, Variant D — EDITED)
         Columns needed: year, week, zone, horizon,
                         y_actual, y_pred_2stage,
                         lower_90, upper_90, covered_D

Output : fig5_forecast_intervals.pdf
         fig5_forecast_intervals.png

Run    : python fig5_forecast_intervals.py
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

# ── Load ───────────────────────────────────────────────────────────────────────
df = pd.read_csv("forecast_normalized_mondrian.csv")  # EDITED — Variant D, see note above

# Build week-of-year date for x-axis
df["date"] = pd.to_datetime(
    df["year"].astype(str) + "-W" +
    df["week"].astype(str).str.zfill(2) + "-1",
    format="%G-W%V-%u"
)
# Scale to k m³
for col in ["y_actual", "y_pred_2stage",
            "lower_90", "upper_90"]:
    df[col + "_k"] = df[col] / 1e3

# ── Palette ────────────────────────────────────────────────────────────────────
C_ACT    = "#222222"   # actual — near black
C_A      = "#4477AA"   # Zone A forecast — blue
C_B      = "#332288"   # Zone B forecast — indigo
C_CI_A   = "#4477AA30" # Zone A interval fill
C_CI_B   = "#33228830" # Zone B interval fill
C_MISS   = "#EE667740" # missed coverage — light red shading
C_DRY    = "#F5F5F080" # dry week shading
C_SPINE  = "#444444"

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        8,
    "axes.linewidth":   0.6,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.major.width":0.6,
    "ytick.major.width":0.6,
    "xtick.direction":  "out",
    "ytick.direction":  "out",
    "pdf.fonttype":     42,
    "ps.fonttype":      42,
})

# ── Panel config ───────────────────────────────────────────────────────────────
PANELS = [
    ("zone_A", 1,  "a", C_A,  C_CI_A),
    ("zone_A", 4,  "b", C_A,  C_CI_A),
    ("zone_B", 1,  "c", C_B,  C_CI_B),
    ("zone_B", 4,  "d", C_B,  C_CI_B),
]

# ── Figure ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    2, 2, figsize=(7.2, 5.4),
    gridspec_kw={"hspace": 0.44, "wspace": 0.32}
)
ax_list = [axes[0,0], axes[0,1], axes[1,0], axes[1,1]]


def get_zone_label(zone):
    return "Zone A — rainfed (NIR)" if zone == "zone_A" \
           else "Zone B — irrigated (GIR)"


for (zone, h, plabel, c_fc, c_ci), ax in zip(PANELS, ax_list):

    sub = (df[(df.zone == zone) & (df.horizon == h)]
             .sort_values("date")
             .dropna(subset=["y_actual_k","y_pred_2stage_k",
                             "lower_90_k","upper_90_k"]))

    if len(sub) == 0:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                ha="center", va="center", color="#999")
        continue

    x      = sub["date"].values
    y_act  = sub["y_actual_k"].values
    y_pred = sub["y_pred_2stage_k"].values
    lo     = sub["lower_90_k"].values
    hi     = sub["upper_90_k"].values
    cov    = sub["covered_D"].values if "covered_D" in sub else None

    # ── Dry-week background shading ───────────────────────────────────────────
    dry = y_act < 1     # k m³; essentially zero
    for i, is_dry in enumerate(dry):
        if is_dry:
            x_left  = x[i] - np.timedelta64(3, "D")
            x_right = x[i] + np.timedelta64(4, "D")
            ax.axvspan(x_left, x_right,
                       color=C_DRY, linewidth=0, zorder=1)

    # ── Missed coverage shading ───────────────────────────────────────────────
    if cov is not None:
        for i, (hit, xa) in enumerate(zip(cov, x)):
            if hit == 0:
                xl = xa - np.timedelta64(3, "D")
                xr = xa + np.timedelta64(4, "D")
                ax.axvspan(xl, xr, color=C_MISS, linewidth=0, zorder=2)

    # ── Conformal interval ────────────────────────────────────────────────────
    ax.fill_between(x, lo, hi, color=c_ci, linewidth=0, zorder=3,
                    label="90% conformal interval")

    # ── Interval bounds (thin lines) ─────────────────────────────────────────
    ax.plot(x, lo, color=c_fc, linewidth=0.4, linestyle="-",
            alpha=0.5, zorder=4)
    ax.plot(x, hi, color=c_fc, linewidth=0.4, linestyle="-",
            alpha=0.5, zorder=4)

    # ── Forecast line ─────────────────────────────────────────────────────────
    ax.plot(x, y_pred, color=c_fc, linewidth=1.1,
            zorder=5, label=f"Forecast (h={h})")

    # ── Actual line ───────────────────────────────────────────────────────────
    ax.plot(x, y_act, color=C_ACT, linewidth=0.8,
            zorder=6, alpha=0.85, label="Observed")

    # ── Coverage annotation ───────────────────────────────────────────────────
    if cov is not None:
        emp_cov = cov.mean() * 100
        ax.text(0.97, 0.97,
                f"Coverage: {emp_cov:.1f}%\n(target 90%)",
                transform=ax.transAxes, fontsize=6.5,
                ha="right", va="top",
                color=("#2CA02C" if emp_cov >= 90 else "#D62728"))

    # ── Formatting ────────────────────────────────────────────────────────────
    zone_lbl = get_zone_label(zone)
    ax.set_title(f"{zone_lbl}, h = {h} week{'s' if h > 1 else ''}",
                 fontsize=8, pad=4, loc="left")
    ax.set_ylabel("Water demand\n(×10³ m³ week⁻¹)", fontsize=7.5)

    # x-axis: month ticks
    ax.xaxis.set_major_locator(
        matplotlib.dates.MonthLocator(bymonth=[1,4,7,10]))
    ax.xaxis.set_major_formatter(
        matplotlib.dates.DateFormatter("%b"))
    ax.xaxis.set_minor_locator(matplotlib.dates.MonthLocator())
    ax.tick_params(axis="x", which="major", labelsize=7)

    ax.yaxis.grid(True, linewidth=0.3, color="#E8E8E8", zorder=0)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:.0f}"))

    # y-axis: start at 0
    ax.set_ylim(bottom=0)

    # Panel label
    ax.text(-0.15, 1.02, plabel, transform=ax.transAxes,
            fontsize=9, fontweight="bold", va="bottom")

    for sp in ax.spines.values():
        sp.set_color(C_SPINE)


# ── Shared legend ──────────────────────────────────────────────────────────────
legend_elements = [
    Line2D([0],[0], color=C_ACT, linewidth=0.9, label="Observed"),
    Line2D([0],[0], color=C_A,   linewidth=1.1, label="Forecast (Zone A)"),
    Line2D([0],[0], color=C_B,   linewidth=1.1, label="Forecast (Zone B)"),
    mpatches.Patch(facecolor="#88AABB50", edgecolor="#4477AA70",
                   linewidth=0.5, label="90% conformal interval"),
    mpatches.Patch(facecolor=C_MISS, edgecolor="none",
                   label="Interval miss"),
    mpatches.Patch(facecolor=C_DRY, edgecolor="none",
                   label="Zero-demand week"),
]
fig.legend(handles=legend_elements,
           loc="lower center", ncol=3, fontsize=6.5,
           frameon=True, framealpha=0.9,
           edgecolor="#CCCCCC", handlelength=1.5,
           handletextpad=0.5, borderpad=0.5,
           columnspacing=1.0,
           bbox_to_anchor=(0.5, -0.04))

# ── Super title ────────────────────────────────────────────────────────────────
fig.text(
    0.5, 1.002,
    "Fig. 5 | Two-stage forecast with Mondrian conformal intervals, 2024",
    ha="center", va="bottom", fontsize=8, color=C_SPINE
)

# ── Save ───────────────────────────────────────────────────────────────────────
plt.savefig("fig5_forecast_intervals.pdf",
            bbox_inches="tight", dpi=300)
plt.savefig("fig5_forecast_intervals.png",
            bbox_inches="tight", dpi=300)
plt.close()

print("Saved: fig5_forecast_intervals.pdf")
print("Saved: fig5_forecast_intervals.png")

print("""
=== Figure caption (draft) ===
Fig. 5 | Two-stage forecast with Mondrian conformal prediction intervals,
2024 test period. Panels show observed demand (black), point forecast (colour),
and 90% Mondrian conformal interval (shaded band) for one-week-ahead (h = 1)
and four-week-ahead (h = 4) forecasts for Zone A (a, b) and Zone B (c, d).
Pink shading indicates weeks where the actual demand falls outside the interval;
light grey background denotes zero-demand (dry-season) weeks. Empirical
coverage meets or exceeds the 90% target in all panels, validating the
finite-sample guarantee of split conformal prediction under a monsoon-climate
intermittent demand setting.
""")


# ##############################################################################
# # PHASE 4 ADDENDUM — MODIS ET Cross-Validation + Bootstrap CI
# Source: `Modis_Validation.ipynb`
# MODIS ET validation for Zone A (rainfed) and bootstrap 95% CI for the
# MAE-improvement-over-persistence headline numbers.
# ##############################################################################

"""
MODIS ET Validation v3 — Zone A rainfed, 2020–2024
=====================================================
Input  : MODIS_ET_cropland_weekly_MaeNaRua_v6.csv
         climate_weekly_phayao_2020_2024.csv
Output : modis_validation_results_v3.csv
         fig_modis_validation_v3.pdf / .png

Bugs fixed vs v1:
  BUG 1: ใช้ไฟล์ v6 (Collection 006/061 merged, cropland mask)
  BUG 2: filter ทั้ง NaN และ -9999 ออก (dropna จับแค่ NaN)
  BUG 3: merge key ผิด — MODIS ใช้ sequential week (1-261),
          climate ใช้ ISO week per year (1-52)
          → แก้โดยแปลง date_start เป็น iso_year + iso_week แล้ว merge

Conceptual fix:
  ET₀ กับ MODIS ETa วิ่ง anti-phase ตามฤดูกาล (ET₀ สูง dry season,
  ETa สูง wet season) → r รวมเป็นลบ ไม่สะท้อน model quality
  → validation ที่ถูกต้องคือ Kc_proxy = ETa/ET₀ เทียบกับ Kc_expected
    ซึ่งยืนยัน seasonal dynamics ของ FAO-56 dual-Kc framework
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

# ── Load ──────────────────────────────────────────────────────────────────────
modis = pd.read_csv("MODIS_ET_weekly_MaeNaRua_2020_2024.csv",
                    parse_dates=["date_start"])
clim  = pd.read_csv("climate_weekly_phayao_2020_2024.csv")

# ── Prep MODIS Zone A ─────────────────────────────────────────────────────────
modis_a = modis[modis["zone"] == "zone_A"][
    ["date_start", "ET_mm_week"]
].copy().rename(columns={"ET_mm_week": "ET_modis"})

# BUG 2 FIX: filter ทั้ง NaN และ -9999
modis_a = modis_a[modis_a["ET_modis"].notna() & (modis_a["ET_modis"] > 0)]
n_valid   = len(modis_a)
n_dropped = 261 - n_valid
print(f"MODIS valid rows: {n_valid}  (dropped {n_dropped})")

# BUG 3 FIX: แปลง date_start → ISO year + week
ic = modis_a["date_start"].dt.isocalendar()
modis_a["iso_year"] = ic["year"].astype(int)
modis_a["iso_week"] = ic["week"].astype(int)

# ── Merge ─────────────────────────────────────────────────────────────────────
# climate.week = ISO week per year → merge on [iso_year, iso_week]
df = clim[["year", "week", "ET0_mm_week"]].merge(
    modis_a[["date_start", "ET_modis", "iso_year", "iso_week"]],
    left_on=["year", "week"],
    right_on=["iso_year", "iso_week"],
    how="inner"
)
df["month"]  = df["date_start"].dt.month
df["season"] = df["month"].map({
    12:"cool", 1:"cool", 2:"cool",
    3:"dry",   4:"dry",  5:"dry",
    6:"wet",   7:"wet",  8:"wet", 9:"wet", 10:"wet", 11:"wet"
})

print(f"Merged rows: {len(df)}  |  "
      f"ET₀ mean={df.ET0_mm_week.mean():.2f}  "
      f"ETa mean={df.ET_modis.mean():.2f}")

assert df.ET_modis.min() > 0,   "พบค่าลบใน MODIS"
assert df.ET_modis.max() < 50,  "พบค่าสูงผิดปกติ"
assert df.ET0_mm_week.min() > 0,"พบค่าลบใน ET₀"

# ── Metric A: Kc_proxy = ETa / ET₀ ──────────────────────────────────────────
# เปรียบ seasonal shape ของ ETa/ET₀ กับ Kc_expected จาก FAO-56 literature
# (rice + upland mix ภาคเหนือไทย ปรับจาก Allen et al. 1998)
KC_TABLE = {1:0.55, 2:0.45, 3:0.35, 4:0.45, 5:0.65,
            6:0.90, 7:1.00, 8:1.05, 9:1.10, 10:1.05, 11:0.85, 12:0.70}
df["Kc_proxy"]    = df["ET_modis"] / df["ET0_mm_week"]
df["Kc_expected"] = df["month"].map(KC_TABLE)

r_kc, p_kc  = stats.pearsonr(df["Kc_proxy"], df["Kc_expected"])
bias_kc     = (df["Kc_proxy"] - df["Kc_expected"]).mean()
rmse_kc     = np.sqrt(((df["Kc_proxy"] - df["Kc_expected"]) ** 2).mean())
slope_kc, intercept_kc, _, _, _ = stats.linregress(
    df["Kc_expected"], df["Kc_proxy"])

# ── Metric B: ET₀ vs ETa ตาม season ─────────────────────────────────────────
print(f"\n{'':=<60}")
print(f"Kc_proxy vs Kc_expected  (n={len(df)})")
print(f"  r = {r_kc:.3f}  (p={p_kc:.2e})")
print(f"  bias Kc = {bias_kc:+.3f}")
print(f"  RMSE Kc = {rmse_kc:.3f}")

print(f"\nSeasonal breakdown (ET₀ vs ETa):")
for s, label in [("dry","Dry (Mar–May)"),
                  ("wet","Wet (Jun–Nov)"),
                  ("cool","Cool (Dec–Feb)")]:
    sub = df[df["season"] == s]
    if len(sub) < 3: continue
    b   = (sub["ET0_mm_week"] - sub["ET_modis"]).mean()
    rs, ps = stats.pearsonr(sub["ET0_mm_week"], sub["ET_modis"])
    print(f"  {label:20s}: n={len(sub):3d}  r={rs:+.3f}  bias={b:+.2f}")

# ── Save CSV ──────────────────────────────────────────────────────────────────
results = pd.DataFrame({
    "metric": ["n_pairs", "r_Kc_proxy_vs_expected", "p_value",
               "bias_Kc", "rmse_Kc",
               "ET0_mean", "ETa_mean", "Kc_proxy_mean"],
    "value":  [len(df), round(r_kc, 4), round(p_kc, 6),
               round(bias_kc, 4), round(rmse_kc, 4),
               round(df["ET0_mm_week"].mean(), 3),
               round(df["ET_modis"].mean(), 3),
               round(df["Kc_proxy"].mean(), 3)]
})
results.to_csv("modis_validation_results_v3.csv", index=False)

# ── Plot ──────────────────────────────────────────────────────────────────────
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8,
                     "pdf.fonttype":42,"ps.fonttype":42})
S_COLOR = {"dry":"#EF9F27","wet":"#378ADD","cool":"#7F77DD"}

fig, axes = plt.subplots(1, 3, figsize=(12, 4))

# ── Panel a: Kc_proxy vs Kc_expected scatter ─────────────────────────────────
ax = axes[0]
c_pts = df["season"].map(S_COLOR)
ax.scatter(df["Kc_expected"], df["Kc_proxy"],
           c=c_pts, alpha=0.5, s=16, edgecolors="none")

lim = [0, 1.5]
ax.plot(lim, lim, color="#888", linewidth=0.8, linestyle="--", label="1:1")
x_line = np.linspace(lim[0], lim[1], 100)
ax.plot(x_line, slope_kc * x_line + intercept_kc,
        color="#1D9E75", linewidth=1.4,
        label=f"OLS (r={r_kc:.3f})")
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel("K$_c$ expected (FAO-56, seasonal)", fontsize=8)
ax.set_ylabel("K$_c$ proxy (MODIS ETa / ERA5 ET₀)", fontsize=8)
ax.set_title("a  K$_c$ proxy vs K$_c$ expected", fontsize=8, loc="left")
ax.text(0.05, 0.95,
        f"n = {len(df)}\nr = {r_kc:.3f}  (p < 0.001)\nbias = {bias_kc:+.3f}",
        transform=ax.transAxes, fontsize=7, va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7, lw=0))
ax.legend(fontsize=7, frameon=False)
ax.spines[["top","right"]].set_visible(False)

# ── Panel b: Kc seasonal climatology ─────────────────────────────────────────
ax2 = axes[1]
mon_kc = df.groupby("month")["Kc_proxy"].agg(["mean","std"]).reset_index()
mon_exp = pd.DataFrame({"month": range(1,13),
                         "Kc_exp": [KC_TABLE[m] for m in range(1,13)]})
x = mon_kc["month"]
ax2.fill_between(x,
                 mon_kc["mean"] - mon_kc["std"],
                 mon_kc["mean"] + mon_kc["std"],
                 alpha=0.2, color="#1D9E75", label="±1 SD")
ax2.plot(x, mon_kc["mean"], color="#1D9E75", linewidth=1.4,
         marker="o", markersize=4, label="K$_c$ proxy (MODIS/ET₀)")
ax2.plot(mon_exp["month"], mon_exp["Kc_exp"], color="#888",
         linewidth=1.0, linestyle="--", marker="s", markersize=3,
         label="K$_c$ expected (FAO-56)")
ax2.axhline(1.0, color="#CCCCCC", linewidth=0.5)
ax2.set_xlabel("Month", fontsize=8)
ax2.set_ylabel("K$_c$ (dimensionless)", fontsize=8)
ax2.set_title("b  Seasonal K$_c$ climatology", fontsize=8, loc="left")
ax2.set_xticks(range(1,13))
ax2.set_xticklabels(["J","F","M","A","M","J","J","A","S","O","N","D"], fontsize=7)
ax2.legend(fontsize=7, frameon=False)
ax2.spines[["top","right"]].set_visible(False)

# ── Panel c: ET time series ───────────────────────────────────────────────────
ax3 = axes[2]
df_plot = df.sort_values("date_start").reset_index(drop=True)
x3 = np.arange(len(df_plot))
ax3.plot(x3, df_plot["ET0_mm_week"], color="#EF9F27", linewidth=0.9,
         label="ERA5 ET₀", alpha=0.9)
ax3.plot(x3, df_plot["ET_modis"], color="#1D9E75", linewidth=0.9,
         linestyle="--", label="MODIS ETa", alpha=0.9)
for yr in [2021,2022,2023,2024]:
    idx = df_plot[df_plot["date_start"].dt.year == yr].index
    if len(idx):
        ax3.axvline(idx[0], color="#CCCCCC", linewidth=0.5)
        ax3.text(idx[0]+1, ax3.get_ylim()[1]*0.97, str(yr),
                 fontsize=6, color="#888")
ax3.set_xlabel("Week index (2020–2024)", fontsize=8)
ax3.set_ylabel("ET (mm week⁻¹)", fontsize=8)
ax3.set_title("c  Time series: ET₀ vs ETa", fontsize=8, loc="left")
ax3.legend(fontsize=7, frameon=False)
ax3.spines[["top","right"]].set_visible(False)

# ── legend shared ─────────────────────────────────────────────────────────────
patches = [mpatches.Patch(color=v, label=k)
           for k, v in {"Dry":"#EF9F27","Wet":"#378ADD","Cool":"#7F77DD"}.items()]
axes[0].legend(handles=patches + [
    plt.Line2D([0],[0],color="#888",linestyle="--",lw=0.8,label="1:1"),
    plt.Line2D([0],[0],color="#1D9E75",lw=1.4,label=f"OLS r={r_kc:.3f}")
], fontsize=6, frameon=False)

plt.tight_layout()
plt.savefig("fig_modis_validation_v3.pdf", dpi=300, bbox_inches="tight")
plt.savefig("fig_modis_validation_v3.png", dpi=300, bbox_inches="tight")
plt.close()
print("\nSaved: modis_validation_results_v3.csv")
print("Saved: fig_modis_validation_v3.pdf / .png")

print(f"""
=== Methods text (Section 2.6.3) ===
MODIS MOD16A2 (Collection 6/6.1, 500 m, 8-day; n = {len(df)} valid
weekly observations after excluding {n_dropped} cloud-affected weeks) was used
to cross-validate the seasonal dynamics of the FAO-56 dual-coefficient
framework. Because ET₀ (reference surface) and ETa (actual cropland) are
anti-phased across the annual cycle — ET₀ peaks during the pre-monsoon dry
season whereas ETa peaks during the monsoon when crop Kc approaches unity —
direct ET₀–ETa correlation is not an appropriate validation target. Instead,
the crop coefficient proxy Kc_proxy = ETa / ET₀ was compared against the
FAO-56 seasonal Kc curve expected for the dominant crop calendar of the study
area. Agreement was strong (Pearson r = {r_kc:.3f}, p < 0.001; bias Kc =
{bias_kc:+.3f}; RMSE Kc = {rmse_kc:.3f}), confirming that MODIS-derived ETa and
ERA5-based ET₀ jointly reproduce the expected seasonal partitioning of
reference and actual evapotranspiration consistent with FAO-56 theory
(Allen et al., 1998).
""")

"""
Bootstrap Confidence Intervals — MAE improvement over persistence
=================================================================
คำนวณ 95% CI สำหรับ MAE improvement (%) ของ two-stage vs persistence
โดยใช้ paired bootstrap resampling

Input  : performance_metrics_all.csv
         forecast_mondrian.csv  (optional — สำหรับ week-level errors)
Output : bootstrap_ci_results.csv
         print summary สำหรับ Methods/Results text

Run    : python bootstrap_ci_mae.py
"""

import pandas as pd
import numpy as np

N_BOOT   = 10_000
ALPHA    = 0.05
SEED     = 42
rng      = np.random.default_rng(SEED)
KEY_H    = [1, 4, 8, 12]
ZONES    = ["zone_A", "zone_B"]

# ── Option A: Bootstrap จาก horizon-level MAE ──────────────
# (ถ้าไม่มี forecast_mondrian.csv)
# ใช้ MAE ทั้ง 12 horizons เป็น sample (n=12 per zone)
# แล้ว bootstrap paired difference

def bootstrap_improvement_from_metrics(df_metrics):
    """
    Paired bootstrap ของ MAE improvement (%)
    sample unit = horizon (n=12)
    """
    results = []
    for zone in ZONES:
        ts = (df_metrics[(df_metrics.zone==zone) &
                         (df_metrics.Model=="TwoStage")]
              .sort_values("horizon")["MAE"].values)
        pe = (df_metrics[(df_metrics.zone==zone) &
                         (df_metrics.Model=="Persistence")]
              .sort_values("horizon")["MAE"].values)

        n = len(ts)
        # Point estimate
        point = (pe - ts) / pe * 100

        # Bootstrap
        boot_mean = np.empty(N_BOOT)
        for b in range(N_BOOT):
            idx = rng.integers(0, n, size=n)
            boot_mean[b] = ((pe[idx] - ts[idx]) / pe[idx] * 100).mean()

        ci_lo = np.percentile(boot_mean, ALPHA/2 * 100)
        ci_hi = np.percentile(boot_mean, (1 - ALPHA/2) * 100)

        results.append({
            "zone"       : zone,
            "horizon"    : "all",
            "n_sample"   : n,
            "method"     : "horizon-level MAE (n=12)",
            "point_est"  : round(point.mean(), 2),
            "ci_lo_95"   : round(ci_lo, 2),
            "ci_hi_95"   : round(ci_hi, 2),
            "sig_pos"    : ci_lo > 0,
        })

        # Per key horizon (n=1 → use cross-horizon SD as proxy)
        for h in KEY_H:
            idx_h = h - 1
            p_h   = float((pe[idx_h] - ts[idx_h]) / pe[idx_h] * 100)
            results.append({
                "zone"       : zone,
                "horizon"    : h,
                "n_sample"   : 1,
                "method"     : "single horizon (point only)",
                "point_est"  : round(p_h, 2),
                "ci_lo_95"   : None,
                "ci_hi_95"   : None,
                "sig_pos"    : None,
            })

    return pd.DataFrame(results)


# ── Option B: Bootstrap จาก week-level errors ──────────────
# (ถ้ามี forecast_mondrian.csv — recommended, n=51 per zone-horizon)

def bootstrap_improvement_from_forecasts(df_forecast):
    """
    Paired bootstrap ของ MAE improvement (%)
    sample unit = week (n ≈ 51 per zone-horizon)
    ต้องการ columns: zone, horizon, y_actual, y_pred_2stage
    และ persistence prediction (y_persist = y actual shifted by h)
    """
    results = []
    for zone in ZONES:
        zf = df_forecast[df_forecast.zone == zone]

        for h in range(1, 13):
            sub = zf[zf.horizon == h].dropna(
                subset=["y_actual","y_pred_2stage"]).copy()

            if len(sub) < 5:
                continue

            # Two-stage absolute errors
            err_ts = np.abs(sub["y_actual"] - sub["y_pred_2stage"]).values

            # Persistence: ใช้ lag-h column ถ้ามี
            if "y_persist" in sub.columns:
                err_pe = np.abs(sub["y_actual"] - sub["y_persist"]).values
            else:
                # fallback: skip (ต้องการ lag data)
                continue

            n = len(err_ts)

            # Point estimate
            mae_ts = err_ts.mean()
            mae_pe = err_pe.mean()
            point  = (mae_pe - mae_ts) / mae_pe * 100

            # Paired bootstrap
            boot_mean = np.empty(N_BOOT)
            for b in range(N_BOOT):
                idx = rng.integers(0, n, size=n)
                bts = err_ts[idx].mean()
                bpe = err_pe[idx].mean()
                boot_mean[b] = (bpe - bts) / bpe * 100

            ci_lo = np.percentile(boot_mean, ALPHA/2 * 100)
            ci_hi = np.percentile(boot_mean, (1 - ALPHA/2) * 100)

            results.append({
                "zone"       : zone,
                "horizon"    : h,
                "n_sample"   : n,
                "method"     : "week-level errors",
                "point_est"  : round(point, 2),
                "ci_lo_95"   : round(ci_lo, 2),
                "ci_hi_95"   : round(ci_hi, 2),
                "sig_pos"    : bool(ci_lo > 0),
            })

    return pd.DataFrame(results)


# ── Main ──────────────────────────────────────────────────────
import os

df_metrics = pd.read_csv("performance_metrics_all.csv")

if os.path.exists("forecast_mondrian.csv"):
    print("Using week-level bootstrap (forecast_mondrian.csv found)")
    df_fc  = pd.read_csv("forecast_mondrian.csv")
    ci_df  = bootstrap_improvement_from_forecasts(df_fc)
    method = "week-level"
else:
    print("Using horizon-level bootstrap (forecast_mondrian.csv not found)")
    ci_df  = bootstrap_improvement_from_metrics(df_metrics)
    method = "horizon-level"

ci_df.to_csv("bootstrap_ci_results.csv", index=False)
print("Saved bootstrap_ci_results.csv")

# ── Print summary ─────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"Bootstrap 95% CI — MAE improvement over persistence")
print(f"n_boot = {N_BOOT:,}  |  method: {method}")
print(f"{'='*65}")

# --- aggregate summary ---
print(f"ci_df shape: {ci_df.shape}")
print(f"ci_df columns: {ci_df.columns.tolist()}")
if ci_df.empty or "zone" not in ci_df.columns:
    print("WARNING: ci_df is empty or missing 'zone' column")
    print("Falling back to horizon-level bootstrap...")
    ci_df = bootstrap_improvement_from_metrics(df_metrics)
    ci_df.to_csv("bootstrap_ci_results.csv", index=False)
    method = "horizon-level"
for zone in ZONES:
    sub = ci_df[ci_df["zone"] == zone].copy()
    # horizon-level method stores "all" as string; week-level stores ints
    all_rows = sub[sub["horizon"].astype(str) == "all"]
    h_rows   = sub[sub["horizon"].astype(str) != "all"]

    print(f"\n{zone}:")

    if len(all_rows) > 0:
        r = all_rows.iloc[0]
        lo = r["ci_lo_95"]; hi = r["ci_hi_95"]
        sig = bool(r["sig_pos"])
        print(f"  Avg improvement  = {r['point_est']:.1f}%"
              f"  95% CI [{lo:.1f}%, {hi:.1f}%]"
              f"  {chr(9989)+' sig' if sig else chr(10060)+' not sig'}")
    else:
        avg_pt = h_rows["point_est"].mean()
        avg_lo = h_rows["ci_lo_95"].dropna().mean()
        avg_hi = h_rows["ci_hi_95"].dropna().mean()
        sig_all = h_rows["sig_pos"].dropna().all()
        ci_str = f"[{avg_lo:.1f}%, {avg_hi:.1f}%]" if not pd.isna(avg_lo) else "—"
        print(f"  Avg improvement  = {avg_pt:.1f}%  avg CI {ci_str}"
              f"  {chr(9989)+' all sig' if sig_all else '—'}")

    # Key horizons
    for h in KEY_H:
        row = sub[sub.horizon == h]
        if len(row) == 0:
            continue
        r = row.iloc[0]
        ci_str = (f"[{r.ci_lo_95:.1f}%, {r.ci_hi_95:.1f}%]"
                  if r.ci_lo_95 is not None else "—")
        sig_str = ("✅" if r.sig_pos else
                   "❌" if r.sig_pos == False else "—")
        print(f"  h={h:2d}  {r.point_est:>6.1f}%  CI {ci_str}  {sig_str}")

# ── Draft sentence for Results ────────────────────────────────
print(f"""
{'='*65}
Draft sentence for Results §3.3 (fill CI values):

Zone A: "The two-stage model reduced MAE relative to persistence by
  an average of [X]% across all 12 horizons (95% bootstrap CI
  [lo%, hi%]; n_boot = 10,000), with improvements ranging from
  [min]% at h = 1 to [max]% at h = 11."

Zone B: analogous sentence with Zone B values.
{'='*65}
""")
