/**
 * PRITHVI LANDSCAPE-CHANGE ATTRIBUTION — REGIONAL DISTURBANCE SUMMARY POC
 * ---------------------------------------------------------------------------
 * Oregon State University / NASA — Prithvi-Based Landscape Change Attribution
 * Service in Support of National Park Service and National Forest Monitoring
 * Needs (PI: Robert Kennedy).
 *
 * THIS SUPERSEDES prithvi_grid_summary_poc.js FOR THE REFERENCE-DATA
 * ASSESSMENT STAGE. The fixed 224/112/56-pixel chip grid is no longer the
 * analysis unit -- existing geographic regions are:
 *
 *   NCCN  -> individual NPS park boundaries
 *   GLKN  -> HUC boundaries (matching Al's attribution work)
 *   ADS   -> USFS Region 6 / Region 10 boundaries (TBD -- not hard-coded)
 *
 * PURPOSE
 *   attributed disturbance polygons
 *     -> existing region boundaries (park / HUC / USFS region)
 *     -> summarize disturbance distribution within each region
 *     -> one row per (region, year, change_class)
 *
 * WHY VECTOR INTERSECTION, NOT RASTERIZATION (see chat for full reasoning):
 *   The analysis unit is now an entire park/HUC/region, not a raster chip.
 *   Rasterizing whole regions at 30 m just to total area is expensive at
 *   national scale and adds a pixel-center sampling bias for no benefit --
 *   exact geometric area is a strictly better answer to "how much area of
 *   class X is in region Y". A separate, optional, NOT-invoked-by-default
 *   function (computeRegionPixelCounts, bottom of this file) is kept around
 *   for the different future question of "how many 30 m training pixels
 *   would this region contribute", which is a modeling-sample-budget
 *   question, not a reference-data-distribution question.
 *
 * OVERLAP HANDLING (important -- read before changing class-area logic):
 *   - Same-class self-overlaps (e.g. two fire polygons over the same ground)
 *     are dissolved via FeatureCollection.geometry(), which performs a true
 *     topological union, so a class's area is never inflated by duplicate/
 *     overlapping digitizations of the same event.
 *   - Cross-class overlaps (e.g. fire and insect claiming the same ground)
 *     are NOT resolved or hidden. They are surfaced as their own explicit
 *     row: change_class = 'multi_class_overlap', with
 *     area_m2 = sum(per-class areas) - area(union of all classes).
 *     No priority order or allocation rule is applied -- that is a decision
 *     to make later, informed by seeing how much overlap actually exists.
 *   - "unlabeled" (region area with no attributed polygon at all, for that
 *     year) is its own explicit row, change_class = 'unlabeled'. It is
 *     never conflated with an explicit no-change class, because the source
 *     databases are known to have false negatives / omitted disturbances.
 *
 * A polygon that straddles two adjacent regions (e.g. a fire crossing a
 * park boundary) will correctly appear, partially, in BOTH regions' rows.
 * Do not sum polygon_count or area_m2 across regions expecting a national
 * unique-event total -- that is intentional region-local reporting, not a
 * bug.
 */

// =============================================================================
// 1. PARAMETERS
// =============================================================================

// Fixed planar, equal-area CRS for ALL geometry operations (intersection,
// union/dissolve, area). Even with rasterization gone, an explicit CRS still
// matters: ee.Geometry.area() etc. default to geodesic (ellipsoidal)
// computation, which is fine on its own, but mixing geodesic geometries with
// planar union/intersection introduces vertex-densification and
// antimeridian edge cases that are hard to reproduce/debug. Reprojecting
// everything to one fixed planar CRS up front makes every geometry op
// deterministic and consistent, the same motivation as fixing
// ANALYSIS_PROJECTION in the old grid POC, just applied to vector ops now.
var AREA_CRS = 'EPSG:5070'; // NAD83 / Conus Albers, equal-area, CONUS-scale
var MAX_ERROR = 1;          // meters, tolerance for geometry ops

// Modular class vocabulary -- the one thing that will actually need editing
// per source (NCCN / GLKN / ADS use different native attribute codes; map
// them onto this shared vocabulary at ingestion, before calling
// computeRegionSummary).
var CLASSES = ['fire', 'insect', 'harvest'];
var CLASS_PROPERTY = 'change_class';

var YEAR = 2020;

// =============================================================================
// 2. SYNTHETIC INPUTS (stand-ins for real NCCN/GLKN/ADS + boundary data)
// =============================================================================

// Two adjacent synthetic "regions" (stand-ins for two parks, two HUCs, etc).
// Field names (region_id/region_name) are deliberately generic -- real NPS
// boundary layers, HUC layers, and USFS region layers will each use their
// own native field names, which get passed into computeRegionSummary()
// below rather than assumed here.
var syntheticRegions = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Polygon([[
    [-122.30, 44.45], [-122.15, 44.45], [-122.15, 44.30], [-122.30, 44.30], [-122.30, 44.45]
  ]]), {region_id: 'PARKA', region_name: 'Synthetic Park A'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.15, 44.45], [-122.00, 44.45], [-122.00, 44.30], [-122.15, 44.30], [-122.15, 44.45]
  ]]), {region_id: 'PARKB', region_name: 'Synthetic Park B'})
]);

// Disturbance polygons, schema: polygon_id, year, change_class. Overlap
// cases built in on purpose:
//  - fire_001 / fire_003: same class, overlapping -> tests same-class
//    dissolve (must NOT double-count).
//  - fire_001 / insect_001: different classes, overlapping -> tests
//    multi_class_overlap detection.
//  - harvest_001: straddles the PARKA/PARKB boundary -> tests the
//    intentional dual-region-counting behavior documented above.
//  - harvest_002: a different year, to prove year filtering works.
var syntheticPolygons = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Polygon([[
    [-122.28, 44.40], [-122.20, 44.40], [-122.20, 44.34], [-122.28, 44.34], [-122.28, 44.40]
  ]]), {polygon_id: 'fire_001', year: 2020, change_class: 'fire'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.25, 44.42], [-122.19, 44.42], [-122.19, 44.37], [-122.25, 44.37], [-122.25, 44.42]
  ]]), {polygon_id: 'fire_003', year: 2020, change_class: 'fire'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.27, 44.38], [-122.22, 44.38], [-122.22, 44.33], [-122.27, 44.33], [-122.27, 44.38]
  ]]), {polygon_id: 'insect_001', year: 2020, change_class: 'insect'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.18, 44.36], [-122.12, 44.36], [-122.12, 44.32], [-122.18, 44.32], [-122.18, 44.36]
  ]]), {polygon_id: 'harvest_001', year: 2020, change_class: 'harvest'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.10, 44.42], [-122.05, 44.42], [-122.05, 44.38], [-122.10, 44.38], [-122.10, 44.42]
  ]]), {polygon_id: 'insect_002', year: 2020, change_class: 'insect'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.08, 44.36], [-122.03, 44.36], [-122.03, 44.33], [-122.08, 44.33], [-122.08, 44.36]
  ]]), {polygon_id: 'harvest_002', year: 2019, change_class: 'harvest'})
]);

// =============================================================================
// 3. CORE REGIONAL SUMMARY (the reusable piece: NCCN parks / GLKN HUCs /
//    ADS regions all call this same function with different inputs)
// =============================================================================
//
// Output schema (long format, one row per region x class, plus per-region
// 'unlabeled' and 'multi_class_overlap' rows):
//   region_id, region_name, region_type, source, year, change_class,
//   polygon_count, area_m2, area_ha, pct_attributed
//
// pct_attributed = area_m2 / region_area_m2 * 100 for EVERY row (including
// unlabeled and multi_class_overlap), so it is always interpretable on its
// own without joining back to a region total. Because per-class areas can
// overlap each other, the real class rows' pct_attributed values are NOT
// expected to sum to 100 -- that is expected, not an error, and is exactly
// what multi_class_overlap quantifies. What IS guaranteed to sum to 100 is:
//   unlabeled_pct + (area of the union of all classes / region_area * 100)

function computeRegionSummary(params) {
  var regions = params.regions;
  var regionIdField = params.regionIdField;
  var regionNameField = params.regionNameField;
  var regionType = params.regionType;   // e.g. 'park', 'huc', 'usfs_region'
  var source = params.source;           // e.g. 'NCCN', 'GLKN', 'ADS_R6'
  var polygons = params.polygons;
  var year = params.year;

  var yearPolygons = polygons
    .filter(ee.Filter.eq('year', year))
    .map(function(f) { return f.transform(AREA_CRS, MAX_ERROR); });

  var regionsProj = regions.map(function(f) { return f.transform(AREA_CRS, MAX_ERROR); });
  var regionList = regionsProj.toList(regionsProj.size());

  var perRegionTables = regionList.map(function(regionFeature) {
    var region = ee.Feature(regionFeature);
    var regionGeom = region.geometry();
    var regionId = region.get(regionIdField);
    var regionName = region.get(regionNameField);
    var regionAreaM2 = regionGeom.area(MAX_ERROR);

    // Only polygons that actually touch this region. Note: a polygon
    // straddling two regions will pass this filter for both -- see header
    // comment. Area below is still exact because it's clipped per region.
    var polysInRegion = yearPolygons.filterBounds(regionGeom);

    var classRows = ee.FeatureCollection(CLASSES.map(function(cls) {
      var classPolys = polysInRegion.filter(ee.Filter.eq(CLASS_PROPERTY, cls));
      var polygonCount = classPolys.size();
      // .geometry() unions (dissolves) all features in the collection --
      // this is what prevents overlapping same-class polygons from
      // double-counting area.
      var classGeom = classPolys.geometry(MAX_ERROR);
      var clipped = classGeom.intersection(regionGeom, MAX_ERROR);
      var areaM2 = clipped.area(MAX_ERROR);
      return ee.Feature(null, {
        region_id: regionId,
        region_name: regionName,
        region_type: regionType,
        source: source,
        year: year,
        change_class: cls,
        polygon_count: polygonCount,
        area_m2: areaM2
      });
    }));

    // True attributed footprint: union of ALL classes together, so overlap
    // between classes is not double-counted here.
    var allAttributedGeom = polysInRegion.geometry(MAX_ERROR).intersection(regionGeom, MAX_ERROR);
    var totalAttributedAreaM2 = allAttributedGeom.area(MAX_ERROR);
    var unlabeledAreaM2 = regionAreaM2.subtract(totalAttributedAreaM2);

    var unlabeledRow = ee.Feature(null, {
      region_id: regionId, region_name: regionName, region_type: regionType,
      source: source, year: year, change_class: 'unlabeled',
      polygon_count: null, area_m2: unlabeledAreaM2
    });

    // Overlap magnitude, without picking a resolution rule: how much MORE
    // area the per-class totals claim than the true (deduplicated)
    // attributed footprint. Zero if no two classes overlap anywhere in
    // this region.
    var sumClassAreasM2 = ee.Number(classRows.aggregate_sum('area_m2'));
    var overlapAreaM2 = sumClassAreasM2.subtract(totalAttributedAreaM2);

    var overlapRow = ee.Feature(null, {
      region_id: regionId, region_name: regionName, region_type: regionType,
      source: source, year: year, change_class: 'multi_class_overlap',
      polygon_count: null, area_m2: overlapAreaM2
    });

    return classRows.merge(ee.FeatureCollection([unlabeledRow, overlapRow]))
      .map(function(f) {
        var areaM2 = ee.Number(f.get('area_m2'));
        return f
          .set('area_ha', areaM2.divide(10000))
          .set('pct_attributed', areaM2.divide(regionAreaM2).multiply(100));
      });
  });

  return ee.FeatureCollection(perRegionTables).flatten();
}

// Example call for NCCN-style parks. GLKN/ADS use the same function with
// different regions/fields/regionType/source -- no other code changes.
var regionSummary = computeRegionSummary({
  regions: syntheticRegions,
  regionIdField: 'region_id',
  regionNameField: 'region_name',
  regionType: 'park',
  source: 'NCCN_POC',
  polygons: syntheticPolygons,
  year: YEAR
});

// To run the same logic for GLKN HUCs or ADS regions once those boundary
// datasets are finalized:
//   var glknSummary = computeRegionSummary({
//     regions: hucBoundaries, regionIdField: 'huc8', regionNameField: 'name',
//     regionType: 'huc', source: 'GLKN', polygons: glknPolygons, year: YEAR
//   });
//   var adsSummary = computeRegionSummary({
//     regions: usfsRegionBoundaries, regionIdField: '<tbd>', regionNameField: '<tbd>',
//     regionType: 'usfs_region', source: 'ADS_R6', polygons: adsPolygons, year: YEAR
//   });
// and merge with regionSummary.merge(glknSummary).merge(adsSummary).

// =============================================================================
// 4. OPTIONAL: 30 m PIXEL COUNTS PER REGION (NOT invoked by default)
// =============================================================================
//
// Kept for later, for a DIFFERENT question than area distribution: roughly
// how many 30 m training pixels of each class a region would contribute to
// a Prithvi sample. Not part of the reference-data distribution assessment
// above -- call it explicitly and only when that question is actually
// needed, since reduceRegions over full park/HUC/region extents is far more
// expensive than the vector approach above.

var PIXEL_SIZE = 30;
var PIXEL_CRS = 'EPSG:5070';
var PIXEL_PROJECTION = ee.Projection(PIXEL_CRS).atScale(PIXEL_SIZE);

function computeRegionPixelCounts(params) {
  var regions = params.regions;
  var regionIdField = params.regionIdField;
  var polygons = params.polygons.filter(ee.Filter.eq('year', params.year));

  var classBands = ee.Image.cat(CLASSES.map(function(cls) {
    var subset = polygons.filter(ee.Filter.eq(CLASS_PROPERTY, cls));
    return ee.Image().byte().paint(subset, 1).unmask(0)
      .reproject(PIXEL_PROJECTION).rename(cls + '_pixels');
  }));

  return classBands.reduceRegions({
    collection: regions,
    reducer: ee.Reducer.sum(),
    scale: PIXEL_SIZE,
    crs: PIXEL_CRS
  }).select(
    CLASSES.map(function(c) { return c + '_pixels'; }).concat([regionIdField]),
    null, false
  );
}

// Example (not run): var pixelCounts = computeRegionPixelCounts({
//   regions: syntheticRegions, regionIdField: 'region_id',
//   polygons: syntheticPolygons, year: YEAR
// });

// =============================================================================
// 5. VISUAL QA
// =============================================================================

Map.setOptions('SATELLITE');
Map.centerObject(syntheticRegions, 12);

// Layer 1: region boundaries.
Map.addLayer(
  syntheticRegions.style({color: 'FFFFFF', fillColor: '00000000', width: 3}),
  {}, '1. Region boundaries'
);

// Layer 2: disturbance polygons, colored by class.
var classColors = {fire: 'FF3B30', insect: 'FFCC00', harvest: '34C759'};
var yearPolygonsForViz = syntheticPolygons.filter(ee.Filter.eq('year', YEAR));
CLASSES.forEach(function(cls) {
  var subset = yearPolygonsForViz.filter(ee.Filter.eq(CLASS_PROPERTY, cls));
  Map.addLayer(
    subset.style({color: classColors[cls], fillColor: classColors[cls] + '55', width: 2}),
    {}, '2. Polygons - ' + cls
  );
});

// Layer 3: multi-class overlap footprint (global, not clipped per region --
// a direct visual check against the multi_class_overlap table rows: any
// area shown here inside a region should match that region's
// multi_class_overlap area_m2).
function classGeomFor(cls) {
  return yearPolygonsForViz.filter(ee.Filter.eq(CLASS_PROPERTY, cls))
    .map(function(f) { return f.transform(AREA_CRS, MAX_ERROR); })
    .geometry(MAX_ERROR);
}
var overlapGeoms = [];
for (var i = 0; i < CLASSES.length; i++) {
  for (var j = i + 1; j < CLASSES.length; j++) {
    overlapGeoms.push(classGeomFor(CLASSES[i]).intersection(classGeomFor(CLASSES[j]), MAX_ERROR));
  }
}
var overlapFeature = ee.Feature(
  overlapGeoms.length ? ee.Geometry(overlapGeoms.reduce(function(a, b) { return ee.Geometry(a).union(b, MAX_ERROR); })) : null
);
Map.addLayer(
  ee.FeatureCollection([overlapFeature]).style({color: 'FFFFFF00', fillColor: 'FF00FFAA'}),
  {}, '3. Multi-class overlap footprint (QA)'
);

print('Regional disturbance summary (' + YEAR + '), long format:', regionSummary);
print('Rows (regions x (classes + unlabeled + overlap)):', regionSummary.size());

// =============================================================================
// 6. EXPORT
// =============================================================================

Export.table.toDrive({
  collection: regionSummary,
  description: 'prithvi_region_summary_poc_' + YEAR,
  folder: 'prithvi_poc_exports',
  fileNamePrefix: 'region_summary_' + YEAR,
  fileFormat: 'CSV',
  selectors: [
    'region_id', 'region_name', 'region_type', 'source', 'year',
    'change_class', 'polygon_count', 'area_m2', 'area_ha', 'pct_attributed'
  ]
});
