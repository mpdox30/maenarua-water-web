// =============================================================================
// GEE — Sentinel-2 Dry Season Composite (พ.ย.–เม.ย., cloud < 10%)
// Mae Na Rua Sub-District, Phayao, Northern Thailand
// Source: reconstructed from 4_methodology_guide.docx (full code) and
// confirmed FINAL/done in 4_methodology_guide_updated_p12.docx (✅ เสร็จแล้ว).
//
// Confirmed final output per methodology_guide_updated_p12.docx:
//   Files : S2_drySeason_composite_20XX.tif  (2020–2023)
//   Bands : B02–B12 (20 m) + NDVI, NDWI, NDRE, SAVI  = 14 features total
//   Scale : 20 m | CRS: EPSG:32647 (UTM Zone 47N)
//
// ⚠️ NOTE: the "confirmed final" doc only gives a condensed summary, not the
// full literal script — this file is the fuller version from the original
// methodology guide, with variable names aligned to the confirmed final
// naming (aoiGeom). Band list/feature count (14) match between both docs,
// so this is very likely an accurate reconstruction, but it was NOT
// recoverable as one single verbatim source — verify against your own GEE
// script editor history/Drive exports before re-running.
// =============================================================================

// ── AOI — replace with your actual Mae Na Rua sub-district boundary asset ──
var aoiGeom = mae_na_rua_boundary; // <-- set this to your loaded boundary FeatureCollection/Geometry

// ── Sentinel-2 SR collection, dry season only (Nov–Apr), low cloud ─────────
var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoiGeom)
  .filter(ee.Filter.calendarRange(11, 4, 'month'))   // Nov–Apr
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
  .filterDate('2020-01-01', '2024-12-31');

// ── Median composite over the 10 optical/SWIR bands ────────────────────────
var composite = s2.median().select(
  ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']
);

// ── Spectral indices (4 extra features -> 14 total with the 10 bands) ─────
var ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI');
var ndwi = composite.normalizedDifference(['B3', 'B8']).rename('NDWI');
var ndre = composite.normalizedDifference(['B8A', 'B5']).rename('NDRE');
var savi = composite.expression('1.5*(NIR-RED)/(NIR+RED+0.5)', {
  NIR: composite.select('B8'),
  RED: composite.select('B4')
}).rename('SAVI');

var s2_final = composite.addBands([ndvi, ndwi, ndre, savi]);

// ── Export ──────────────────────────────────────────────────────────────
// Confirmed final naming: S2_drySeason_composite_YYYY.tif | scale=20 | EPSG:32647
Export.image.toDrive({
  image: s2_final,
  description: 'S2_drySeason_composite',   // rename per year when exporting each composite
  scale: 20,
  region: aoiGeom,
  crs: 'EPSG:32647',
  maxPixels: 1e13
});
