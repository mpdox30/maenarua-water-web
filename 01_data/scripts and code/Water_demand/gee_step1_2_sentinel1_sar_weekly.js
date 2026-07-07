// =============================================================================
// GEE — Sentinel-1 SAR Full-Year Weekly Composite
// Mae Na Rua Sub-District, Phayao, Northern Thailand
// Source: reconstructed from 4_methodology_guide.docx (full code) and
// confirmed FINAL/done in 4_methodology_guide_updated_p12.docx (✅ เสร็จแล้ว).
//
// Confirmed final output per methodology_guide_updated_p12.docx:
//   Files    : S1_fullYear_weekly_20XX.tif  (2020–2023)
//   Orbit    : IW mode, VV+VH, DESCENDING only (locked — important for
//              time-series consistency across weeks/years)
//   Features : VV, VH, VH-VV_dB, VH/VV_linear, VH_contrast, VH_homogeneity
//              (6 bands per week, all weeks of the year, not just wet season)
//   Scale    : 10 m | CRS: EPSG:32647 | ~312 bands/year (52 weeks x 6 features)
//   Known issue: GEE exports as a ZIP, not directly a plain .tif — unzip
//   before use.
//
// ⚠️ NOTE: this reconstruction merges two source docs that do not fully
// agree with each other:
//   - The original full script (below) only computed ONE ratio-type band
//     (VH minus VV, in dB — labelled VH_VV_ratio) plus GLCM contrast/
//     homogeneity = 4 derived bands, i.e. VV+VH+4 = 6 bands total.
//   - The "confirmed final" doc lists SIX feature names explicitly:
//     VV, VH, VH-VV_dB, VH/VV_linear, VH_contrast, VH_homogeneity.
//     That is the SAME dB-difference band (VH-VV_dB = the original
//     VH_VV_ratio) PLUS an additional VH/VV_linear (ratio in linear power,
//     not dB) that does not appear in the original script.
//   - The original script also does not explicitly filter to DESCENDING
//     orbit only; the confirmed-final doc says this was "locked".
// I have ADDED the DESCENDING-orbit filter and the VH/VV_linear band below
// (clearly marked "ADDED") to match the confirmed-final feature list, since
// leaving them out would silently under-deliver what you documented as
// final. Please double check these two additions against your actual GEE
// script history/Drive exports before re-running — they were not
// recoverable verbatim from any single source.
// =============================================================================

var aoiGeom = mae_na_rua_boundary; // <-- set this to your loaded boundary FeatureCollection/Geometry

// ── Sentinel-1 GRD, IW mode, VV+VH, DESCENDING orbit only ──────────────────
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoiGeom)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))  // <-- ADDED, see note above
  .filterDate('2020-01-01', '2024-12-31')
  .select(['VV', 'VH']);

// ── Weekly composite (mean per week), full year, 52 weeks x N years ───────
var weeks = ee.List.sequence(0, 260); // 52 weeks x 5 years

var weekly_s1 = weeks.map(function (w) {
  var start = ee.Date('2020-01-01').advance(ee.Number(w).multiply(7), 'day');
  var end   = start.advance(7, 'day');
  var img   = s1.filterDate(start, end).mean();

  // VH - VV in dB (additive difference) — this is "VH_VV_ratio" /
  // "VH-VV_dB" in the two source docs
  var ratio_db = img.select('VH').subtract(img.select('VV')).rename('VH_VV_ratio');

  // ADDED — VH/VV in linear power scale (multiplicative ratio), to match
  // the confirmed-final feature list's separate "VH/VV_linear" entry.
  // Converts dB->linear (10^(dB/10)) before dividing.
  var vv_lin = ee.Image(10).pow(img.select('VV').divide(10));
  var vh_lin = ee.Image(10).pow(img.select('VH').divide(10));
  var ratio_linear = vh_lin.divide(vv_lin).rename('VH_VV_linear');

  // GLCM texture (contrast + homogeneity) on VH
  var glcm = img.select('VH').glcmTexture({ size: 3 })
    .select(['VH_contrast', 'VH_homogeneity']);

  return img.addBands([ratio_db, ratio_linear, glcm])
    .set('week', w)
    .set('date', start);
});

// ── Export as multiband GeoTIFF stack ──────────────────────────────────────
// Confirmed final naming: S1_fullYear_weekly_YYYY.tif | scale=10 | EPSG:32647
// NOTE: GEE will export this as a ZIP archive — unzip before downstream use
// (this matches the "known issue" already noted in your methodology guide).
Export.image.toDrive({
  image: ee.ImageCollection(weekly_s1).toBands(),
  description: 'S1_fullYear_weekly',   // rename per year when exporting each stack
  scale: 10,
  region: aoiGeom,
  crs: 'EPSG:32647',
  maxPixels: 1e13
});
