/**
 * PRITHVI LANDSCAPE-CHANGE ATTRIBUTION — GRID-SUMMARY METHODOLOGY POC
 * ---------------------------------------------------------------------------
 * Oregon State University / NASA — Prithvi-Based Landscape Change Attribution
 * Service in Support of National Park Service and National Forest Monitoring
 * Needs (PI: Robert Kennedy).
 *
 * PURPOSE
 *   This is a small, self-contained proof of concept for turning attributed
 *   landscape-change polygons (eventually: NCCN/NPS, Glicken/NPS, USFS ADS)
 *   into a deterministic, per-grid-cell reference-data summary table at a
 *   fixed 30 m analysis resolution.
 *
 *   It is NOT the national pipeline and NOT Prithvi model training. It exists
 *   to prove out and visually QA the methodology:
 *
 *     attributed polygons
 *       -> rasterize to a fixed 30 m analysis grid
 *       -> overlay a configurable chip/grid system
 *       -> count labeled pixels by class within each grid cell
 *       -> one row per grid cell
 *
 * KEY DESIGN DECISIONS (see accompanying explanation for full rationale):
 *   - A single fixed analysis projection (CRS + 30 m scale, native CRS
 *     origin) is defined ONCE and reused for every raster/reduce operation.
 *     Nothing is ever left to Earth Engine's default projection behavior.
 *   - Grid cell row/col indices are computed by floor-dividing projected
 *     coordinates by the cell size in meters, anchored at the CRS's native
 *     (0,0) origin — NOT at the AOI's bounding box. This makes grid_id
 *     deterministic and stable across runs/regions/exports.
 *   - Each change_class gets its own binary raster band. Classes are never
 *     merged with a "first wins" / "last wins" reducer, so multi-label
 *     pixels can be detected instead of silently overwritten.
 *   - "unlabeled" is used instead of "no_change" everywhere, because the
 *     source reference databases are known to have false negatives /
 *     omitted disturbances. Absence of a label is NOT evidence of no change.
 */

// =============================================================================
// 1. PARAMETERS  (keep everything configurable up here)
// =============================================================================

// --- Grid / pixel parameters -------------------------------------------------
var PIXEL_SIZE = 30;                 // analysis pixel size, meters (fixed)
var CHIP_PIXELS = 224;               // candidate: 224, 112, or 56 — NOT final
var CELL_SIZE_M = CHIP_PIXELS * PIXEL_SIZE; // grid cell edge length, meters

// --- Analysis projection ------------------------------------------------------
// EPSG:5070 = NAD83 / Conus Albers: equal-area, CONUS-appropriate, and its
// natural (0,0) origin sits near the projection center (~lon -96, lat 23),
// i.e. inside/near the analysis domain rather than off in the ocean somewhere.
// That matters: see explanation of why we anchor the grid to this origin
// rather than to the AOI bounding box.
var ANALYSIS_CRS = 'EPSG:5070';
var ANALYSIS_PROJECTION = ee.Projection(ANALYSIS_CRS).atScale(PIXEL_SIZE);

// --- Class list ---------------------------------------------------------------
// Modular on purpose: this list, and the property name it comes from, WILL
// change once real NCCN / Glicken / ADS schemas are in hand. Nothing below
// this point should need to change structurally when that happens — only
// this list and the ingestion/normalization step in Section 3.
var CLASSES = ['fire', 'insect', 'harvest'];
var CLASS_PROPERTY = 'change_class';

// --- Temporal parameter ---------------------------------------------------
// Real datasets are multi-year. The POC processes one year at a time by
// design (see computeGridSummary() below), but the whole pipeline is wrapped
// in a function keyed on year specifically so it can be mapped over a list
// of years later without restructuring anything.
var YEAR = 2020;

// --- AOI ------------------------------------------------------------------
// Small, arbitrary synthetic AOI (western Cascades, OR) sized to a handful
// of grid cells so the whole thing is easy to visually QA against basemap
// imagery. Not tied to any real reference dataset.
var AOI_CENTER_LONLAT = [-122.15, 44.35];
var GRID_COLS_RADIUS = 2;   // cells to each side of center column -> 5 cols
var GRID_ROWS_RADIUS = 1;   // cells to each side of center row    -> 3 rows
// 5 x 3 = 15 grid cells, within the requested 10-20 cell POC range.

// --- Export -----------------------------------------------------------------
var EXPORT_FOLDER = 'prithvi_poc_exports';
var EXPORT_DESCRIPTION = 'prithvi_grid_summary_poc_' + YEAR;

// =============================================================================
// 2. DETERMINISTIC GRID CONSTRUCTION
// =============================================================================
//
// WHY NOT JUST DRAW RECTANGLES OF ~THE RIGHT SIZE:
//   ee.Geometry.Rectangle() built from lon/lat degrees does NOT produce cells
//   that are exactly CELL_SIZE_M on a side, and does not guarantee cell edges
//   fall on 30 m pixel boundaries. Degrees are not a fixed distance, and
//   Earth Engine will happily let you build "grid" geometries that drift out
//   of alignment with your raster pixel grid, causing partial-pixel edge
//   effects and, worse, cells whose IDs are not reproducible if the AOI
//   shifts even slightly between runs.
//
//   Instead: everything below is built directly in the analysis projection's
//   own coordinate system (meters, in EPSG:5070), using integer row/col
//   indices multiplied by CELL_SIZE_M. Because CELL_SIZE_M is itself an
//   integer multiple of PIXEL_SIZE (30), and both the grid and the raster
//   share the exact same projection origin (ANALYSIS_PROJECTION's native
//   CRS origin, i.e. (0,0) in EPSG:5070 -- see atScale() below), grid cell
//   boundaries always land exactly on 30 m pixel boundaries. No fractional
//   pixel straddles a grid line.
//
// WHY ANCHOR AT THE CRS ORIGIN, NOT AT THE AOI BOUNDS:
//   ee.Projection(CRS).atScale(scale) keeps the CRS's own native transform
//   origin -- it does NOT recenter on whatever geometry you happen to be
//   looking at. If we instead computed the grid origin from AOI.bounds(),
//   two different runs with slightly different AOIs would produce two
//   different, incompatible grids (same physical pixel could be assigned to
//   different cells / different grid_ids in each run), which breaks
//   reproducibility and makes it impossible to later merge grid tables
//   produced from different regions or different processing runs.
//   Anchoring at the fixed CRS origin means row/col/grid_id for a given
//   patch of ground are the same no matter what AOI you happened to run.

// Center point, converted into the analysis projection so we can compute
// integer row/col indices directly in meters.
var centerPoint = ee.Geometry.Point(AOI_CENTER_LONLAT);
var centerProj = centerPoint.transform(ANALYSIS_PROJECTION, 1);
var centerCoords = ee.List(centerProj.coordinates());
var centerX = ee.Number(centerCoords.get(0));
var centerY = ee.Number(centerCoords.get(1));
var centerCol = centerX.divide(CELL_SIZE_M).floor();
var centerRow = centerY.divide(CELL_SIZE_M).floor();

var colStart = centerCol.subtract(GRID_COLS_RADIUS);
var colEnd = centerCol.add(GRID_COLS_RADIUS);
var rowStart = centerRow.subtract(GRID_ROWS_RADIUS);
var rowEnd = centerRow.add(GRID_ROWS_RADIUS);

var rows = ee.List.sequence(rowStart, rowEnd);
var cols = ee.List.sequence(colStart, colEnd);

function makeCell(row, col) {
  row = ee.Number(row);
  col = ee.Number(col);
  var xMin = col.multiply(CELL_SIZE_M);
  var xMax = xMin.add(CELL_SIZE_M);
  var yMin = row.multiply(CELL_SIZE_M);
  var yMax = yMin.add(CELL_SIZE_M);

  // Built directly IN the analysis projection -- these coordinates are
  // meters in EPSG:5070, not lon/lat, so there is no reprojection step
  // (and therefore no reprojection ambiguity) between "grid definition"
  // and "raster pixel grid".
  var geom = ee.Geometry.Rectangle(
    [xMin, yMin, xMax, yMax],
    ANALYSIS_PROJECTION,
    false // not geodesic: this is a planar rectangle in a projected CRS
  );

  // grid_id is a pure function of (row, col) in the fixed, anchored grid,
  // so it is stable across runs, AOIs, and export batches.
  var gridId = row.format('R%d').cat('_').cat(col.format('C%d'));

  return ee.Feature(geom, {
    grid_id: gridId,
    row: row,
    col: col
  });
}

var gridFeatures = rows.map(function(r) {
  return cols.map(function(c) {
    return makeCell(r, c);
  });
}).flatten();

var gridFC = ee.FeatureCollection(gridFeatures);

// =============================================================================
// 3. SYNTHETIC INPUT POLYGONS (stand-in for NCCN / Glicken / ADS)
// =============================================================================
//
// Schema kept deliberately minimal and generic: polygon_id, year,
// change_class. When real data arrives, this section is the ONLY place that
// should need real ingestion/normalization logic (e.g. mapping each source's
// native attribute codes onto the shared CLASSES vocabulary above).
//
// Two of these polygons (fire_002 / insect_001) intentionally overlap, to
// exercise multi-label pixel detection.

var syntheticPolygons = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Polygon([[
    [-122.22, 44.38], [-122.16, 44.38], [-122.16, 44.34], [-122.22, 44.34], [-122.22, 44.38]
  ]]), {polygon_id: 'fire_001', year: 2020, change_class: 'fire'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.14, 44.37], [-122.09, 44.37], [-122.09, 44.33], [-122.14, 44.33], [-122.14, 44.37]
  ]]), {polygon_id: 'fire_002', year: 2020, change_class: 'fire'}),

  // Overlaps fire_002 -- deliberate conflict for multi-label testing.
  ee.Feature(ee.Geometry.Polygon([[
    [-122.13, 44.36], [-122.08, 44.36], [-122.08, 44.32], [-122.13, 44.32], [-122.13, 44.36]
  ]]), {polygon_id: 'insect_001', year: 2020, change_class: 'insect'}),

  ee.Feature(ee.Geometry.Polygon([[
    [-122.20, 44.33], [-122.16, 44.33], [-122.16, 44.30], [-122.20, 44.30], [-122.20, 44.33]
  ]]), {polygon_id: 'harvest_001', year: 2020, change_class: 'harvest'}),

  // A different year, included to prove year filtering actually excludes it.
  ee.Feature(ee.Geometry.Polygon([[
    [-122.10, 44.31], [-122.06, 44.31], [-122.06, 44.28], [-122.10, 44.28], [-122.10, 44.31]
  ]]), {polygon_id: 'harvest_002', year: 2019, change_class: 'harvest'})
]);

// =============================================================================
// 4. RASTERIZATION + PIXEL COUNTING  (wrapped per-year for future reuse)
// =============================================================================
//
// PROJECTION GOTCHA THIS SECTION EXISTS TO AVOID:
//   ee.Image().paint(...) produces an image with no inherent pixel grid --
//   it is scale/projection-free until something forces a grid onto it
//   (a reproject(), or an implicit default when it hits a reducer). If you
//   skip the explicit .reproject() below, reduceRegions() will silently fall
//   back to computing in EPSG:4326 at whatever scale it infers, which is
//   NOT our 30 m equal-area analysis grid, and will NOT agree pixel-for-
//   pixel with ANALYSIS_PROJECTION. That would break the entire premise that
//   "pixel counts" mean fixed 30 m analysis pixels. So: every class band is
//   explicitly reprojected to ANALYSIS_PROJECTION immediately after
//   rasterization, before any bands are combined or reduced.

function computeGridSummary(year) {
  var yearPolygons = syntheticPolygons.filter(ee.Filter.eq('year', year));

  // One binary band per class. Painted separately (not merged with a single
  // "burn all polygons, last one wins" pass) specifically so overlapping
  // classes remain visible instead of one silently overwriting another.
  var classBands = CLASSES.map(function(cls) {
    var subset = yearPolygons.filter(ee.Filter.eq(CLASS_PROPERTY, cls));
    var painted = ee.Image().byte().paint(subset, 1);
    return painted
      .unmask(0)                       // masked (outside polygon) -> 0
      .reproject(ANALYSIS_PROJECTION)  // force onto the fixed 30 m grid
      .rename(cls);
  });

  var classStack = ee.Image.cat(classBands);

  var classCount = classStack.reduce(ee.Reducer.sum()).rename('class_count');
  var labeledBand = classCount.gt(0).rename('labeled_pixels');
  var unlabeledBand = classCount.eq(0).rename('unlabeled_pixels');
  var multiLabelBand = classCount.gt(1).rename('multi_label_pixels');

  // Unmasked everywhere -> reduceRegions' count/sum of this band gives the
  // true number of 30 m analysis pixels overlapping each cell, including
  // partial edge cells at the AOI boundary.
  var totalBand = ee.Image.constant(1).toByte()
    .reproject(ANALYSIS_PROJECTION)
    .rename('total_pixels');

  var classPixelBands = ee.Image.cat(CLASSES.map(function(cls) {
    return classStack.select(cls).rename(cls + '_pixels');
  }));

  var analysisImage = totalBand
    .addBands(labeledBand)
    .addBands(unlabeledBand)
    .addBands(multiLabelBand)
    .addBands(classPixelBands);

  // reduceRegions with an explicit crs+scale that matches ANALYSIS_PROJECTION
  // exactly (same CRS, same native origin, same 30 m scale) so the reducer's
  // internal pixel grid is identical to the one the bands were built on --
  // not an independently-resampled approximation of it.
  var gridStats = analysisImage.reduceRegions({
    collection: gridFC,
    reducer: ee.Reducer.sum(), // each band is a 0/1 indicator -> sum = count
    scale: PIXEL_SIZE,
    crs: ANALYSIS_CRS
  });

  // Areas and percentages derived from pixel counts (the fundamental
  // measurement), not recomputed independently from geometry.
  gridStats = gridStats.map(function(f) {
    f = f.set('year', year);
    CLASSES.forEach(function(cls) {
      var pixelCount = ee.Number(f.get(cls + '_pixels'));
      f = f.set(cls + '_area_m2', pixelCount.multiply(PIXEL_SIZE * PIXEL_SIZE));
    });
    var total = ee.Number(f.get('total_pixels'));
    var labeled = ee.Number(f.get('labeled_pixels'));
    // NOTE: total.gt(0) is a server-side ee.Number, so a JS "? :" ternary on
    // it would always take the true branch (any ee object is truthy in JS).
    // ee.Algorithms.If evaluates the condition server-side instead.
    f = f.set('labeled_pct', ee.Algorithms.If(
      total.gt(0), labeled.divide(total).multiply(100), null
    ));
    return f;
  });

  return gridStats;
}

var gridSummary = computeGridSummary(YEAR);

// To later iterate across years without restructuring anything above:
//   var allYears = ee.List([2018, 2019, 2020]);
//   var multiYear = ee.FeatureCollection(allYears.map(function(y) {
//     return computeGridSummary(y);
//   })).flatten();
// Each output feature already carries 'year', so grid_id x year x class
// stays queryable directly from a flattened multi-year table.

// =============================================================================
// 5. VISUAL QA
// =============================================================================

Map.setOptions('SATELLITE');
Map.centerObject(gridFC, 13);

// Layer 1: original polygons, colored by class, outlined so overlap is
// visible as a filled region under two outlines.
var classColors = {fire: 'FF3B30', insect: 'FFCC00', harvest: '34C759'};
CLASSES.forEach(function(cls) {
  var subset = syntheticPolygons.filter(ee.Filter.and(
    ee.Filter.eq('year', YEAR),
    ee.Filter.eq(CLASS_PROPERTY, cls)
  ));
  Map.addLayer(
    subset.style({color: classColors[cls], fillColor: classColors[cls] + '55', width: 2}),
    {},
    '1. Polygons - ' + cls
  );
});

// Layer 2: rasterized 30 m labels, RGB = fire/insect/harvest indicator bands.
// Overlapping classes show up as a blended/brighter color -- a direct visual
// proxy for multi_label_pixels, at the actual 30 m pixel grid (not the
// original polygon boundaries).
var yearPolygonsForViz = syntheticPolygons.filter(ee.Filter.eq('year', YEAR));
var classBandsViz = ee.Image.cat(CLASSES.map(function(cls) {
  var subset = yearPolygonsForViz.filter(ee.Filter.eq(CLASS_PROPERTY, cls));
  return ee.Image().byte().paint(subset, 1).unmask(0)
    .reproject(ANALYSIS_PROJECTION).rename(cls);
}));
Map.addLayer(
  classBandsViz.updateMask(classBandsViz.reduce(ee.Reducer.sum()).gt(0)),
  {bands: CLASSES, min: 0, max: 1},
  '2. Rasterized 30m labels (R=fire G=insect B=harvest)'
);

// Layer 3: grid/chip boundaries with grid_id visible via Inspector click.
Map.addLayer(
  gridFC.style({color: 'FFFFFF', fillColor: '00000000', width: 2}),
  {},
  '3. Grid cells (' + CHIP_PIXELS + 'px @ ' + PIXEL_SIZE + 'm = ' + CELL_SIZE_M + 'm)'
);

// Console inspection: compare these numbers against what Layers 1-3 show
// for a given cell (click a cell with the Inspector tool to read its
// grid_id, then find that row below).
print('Grid summary (' + YEAR + '), one row per grid cell:', gridSummary);
print('Grid cell count (should be ' + ((2 * GRID_COLS_RADIUS + 1) * (2 * GRID_ROWS_RADIUS + 1)) + '):', gridFC.size());
print('Analysis projection:', ANALYSIS_PROJECTION);

// =============================================================================
// 6. EXPORT
// =============================================================================

Export.table.toDrive({
  collection: gridSummary,
  description: EXPORT_DESCRIPTION,
  folder: EXPORT_FOLDER,
  fileNamePrefix: EXPORT_DESCRIPTION,
  fileFormat: 'CSV',
  selectors: [
    'grid_id', 'row', 'col', 'year',
    'total_pixels', 'labeled_pixels', 'unlabeled_pixels', 'multi_label_pixels',
    'labeled_pct'
  ].concat(CLASSES.map(function(c) { return c + '_pixels'; }))
   .concat(CLASSES.map(function(c) { return c + '_area_m2'; }))
});
