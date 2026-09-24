# Prithvi Reference-Data Assessment

Reference-data assessment for "Prithvi-Based Landscape Change Attribution
Service in Support of National Park Service and National Forest Monitoring
Needs" (NASA-funded, PI Robert Kennedy, Oregon State University).

This repo covers the **reference-data assessment stage only**: characterizing
existing attributed landscape-change polygons (NCCN, GLKN, USFS ADS) against
existing geographic regions, before any Prithvi-EO-2.0 modeling work begins.

## Sources and their analysis regions (subregions)

| Source | Reference data | Subregions |
|---|---|---|
| NCCN (NPS) | Attributed disturbance polygons, North Coast and Cascades Network | The source's own `park_code` identity (MORA, NOCA, OLYM, LEWI) -- no complete, agreed containing boundary exists for every park, so subregion identity comes directly from the source attribute, not a spatial join against a boundary layer |
| GLKN (NPS) | Al's attributed disturbance data, Great Lakes Network | The source's own `park_code` identity (APIS, INDU, ISRO, MISS, SACN, SLBE, VOYA) -- HUC boundaries were investigated as a candidate but not adopted (HUC boundary *geometry* is missing for GLKN, and ISRO/VOYA data extend into Canada where no boundary exists in this project); same park_code-as-subregion approach as NCCN |
| USFS ADS Region 6 | Aerial Detection Survey polygons | The 7 dissolved EPA Level III ecoregions (`BugNet_R6` boundaries, actual boundary geometry, not centroid-assigned) |
| USFS ADS Region 10 | Aerial Detection Survey polygons | The 20 HUC6 watershed basins (`BugNet_R10` boundaries, actual boundary geometry, not centroid-assigned) |

Do not assume any of the above class schemas, field names, or region
boundary datasets match across sources. Each source gets inspected on its
own before any shared logic is written against it. **Native source
taxonomies (NCCN `change_class`, GLKN `agent_01`/`agent_02`/`agent_03`, ADS
`DCA_CODE`/`DAMAGE_TYPE`) are preserved as delivered and are not mapped onto
a shared/harmonized vocabulary at this stage** -- see `docs/data_inventory.md`
and the QA reports under `outputs/qa/` for the full per-source rationale.

## Processing environment

The authoritative pipeline runs **locally in Python** (GeoPandas / Shapely /
Fiona / Pyogrio / Pandas / Rasterio), not Google Earth Engine.

Reference-label characterization is now done at two levels: (1) vector-level
region/subregion summaries (record counts, attributed area, per-class
composition -- `src/process_*.py`, `src/*_regional_summary.py`), and (2) a
**30 m reference-grid rasterization** of each source's native classes,
independently per subregion x year (`src/rasterize_*.py`,
`src/build_pixel_summary_tables.py`). This 30 m grid is a *project-defined*
reference grid used only to quantify the spatial amount and distribution of
attributed labels at a consistent Landsat-scale resolution -- it is **not**
verified against the Prithvi model's actual HLS ingestion grid, and that
alignment must be revisited before these pixels are used to generate real
training/eval samples. See the metadata JSONs in `outputs/qa/` for the exact
CRS/resolution/alignment convention used per source.

`gee_exploratory/` holds two **retired** Earth Engine POCs (an arbitrary
224/112/56-pixel chip-grid approach, and an earlier region-summary sketch).
Both are superseded by the current local-Python design above (existing
source regions/subregions instead of an arbitrary chip grid, and the 30 m
reference-grid rasterization instead of GEE) -- kept only for historical
reference, not as active pipeline code.

## Directory structure

```
data/
    raw/                 Original source data, exactly as received. Never modified.
        nccn/
        glkn/
        ads/
            r6/
            r10/
        boundaries/      Region boundary datasets -- kept separate from reference
                         data even where one source (e.g. NCCN) is its main user.
            nps/
            ads_r6/
            ads_r10/
            other/       Source packages that don't map to one boundary category alone.
    processed/            Anything WE create: repaired geometry, standardized
                         GeoParquet, filtered subsets, reprojected boundaries.
                         Mirrors data/raw/'s source-based layout. Nothing here yet.
    README.md             Full explanation of the raw/processed/boundaries distinction.
docs/
    data_inventory.md      Full technical inventory (fields, CRS, counts, cross-checks).
    DATA_STATUS.md         Quick human-readable acquisition/status tracker.
    DATA_MANIFEST.md       Flat source-to-canonical-path lookup.
    source_docs/            Documentation that came with the source datasets
                         (reports, FGDC/RTF metadata, certification forms) --
                         not the geospatial data itself.
        nccn/  glkn/  ads/
outputs/
    tables/         Long-format region summary CSVs.
    spatial/        Spatial analytical products (e.g. dissolved/derived geometries).
    maps/           QA maps/figures.
    qa/             QA reports (see below).
src/                 Processing, inspection, and 30 m reference-grid rasterization scripts.
gee_exploratory/      Retired GEE POCs, superseded by the local-Python design above.
```

Raw and processed data, and generated outputs, are gitignored (structure is
tracked via `.gitkeep`; contents are not committed to git). See `data/README.md`
for the full rules governing this structure, and `docs/DATA_MANIFEST.md` for
the exact canonical path of every source package received so far.

## Design principles

- **Preserve originals.** Raw geodatabases/shapefiles/GeoPackages are never
  modified in place. Read `.gdb` directly where possible rather than
  converting everything to shapefile; prefer GeoPackage or GeoParquet for
  any processed/intermediate vector product.
- **Unlabeled ≠ no change.** Region area with no attributed polygon is
  reported as `unlabeled`, never as `no_change`, unless a source contains an
  explicit stable/no-change class. Existing attribution databases are known
  to omit real disturbance.
- **Overlaps are surfaced, not resolved.** Same-class overlapping polygons
  are dissolved before computing area (so duplicate/overlapping
  digitizations of one event don't double-count). Cross-class overlaps
  (and, once relevant, cross-year and cross-source overlaps) are reported
  as their own explicit quantity, not silently allowed to overwrite one
  another or resolved by an arbitrary priority rule, until we've actually
  looked at how much overlap exists and what it represents.
- **CRS is never assumed.** Every source's native CRS is inspected before
  any area is calculated. Area is always computed in an explicit, documented,
  appropriate projected/equal-area CRS — never directly from geographic
  (lat/lon) coordinates.
- **Every run produces QA output**, not just a CSV: input feature/area
  counts, regions and years covered, area assigned vs. unassigned to a
  region, potential overlap area, and any invalid geometries encountered.

## Workflow for a new dataset

1. Run `src/inspect_dataset.py` against the raw file first (read-only —
   never modifies the source). It reports layers, geometry types, CRS,
   feature counts, fields, heuristic guesses at ID/class/year/region
   fields, unique categorical values, year ranges, geometry validity, and
   an approximate self-overlap signal.
2. Look at the output by eye. Confirm or correct the field guesses.
3. Decide which subregion identity (a source attribute, e.g. `park_code`,
   or a boundary dataset, e.g. dissolved ecoregions/HUCs) summarizes it.
   Native class taxonomies are preserved as-is at this stage -- no mapping
   onto a shared/harmonized vocabulary is done here.
4. Build/extend the region-summary logic in `src/` against that one
   dataset + its subregion definition as a single end-to-end check before
   generalizing to the next source.

## Setup

```
conda env create -f environment.yml
conda activate prithvi-ref-assessment
```

or, if not using conda (GDAL-linked packages are more reliably installed via
conda-forge than pip):

```
pip install -r requirements.txt
```

## Usage

```
python src/inspect_dataset.py data/raw/ads/r6/ADS_R6_Damage_allyears.shp
python src/inspect_dataset.py data/raw/nccn/NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/MORA_1987_2017_V2_1_1_UTM.shp --save
python src/inspect_dataset.py /vsizip/$(pwd)/data/raw/ads/r10/AK_Region10_AllYears.gdb.zip   # zipped GDB, no extraction needed
```

`data/raw/glkn/LandTrendr` is a real File Geodatabase without a `.gdb`
extension (preserved exactly as received — see `docs/DATA_MANIFEST.md` "GDB
extension note"); GDAL needs a `.gdb`-suffixed copy to open it, e.g.
`cp -R data/raw/glkn/LandTrendr /tmp/LandTrendr.gdb` before inspecting.
