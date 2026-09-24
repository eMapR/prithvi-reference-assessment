# Data Manifest

Authoritative list of every source package and its canonical path in this project, as of the 2026-09-22 reorganization. If you're looking for "where does the real copy of X live," this file is the answer — `docs/data_inventory.md` has the technical detail (fields, CRS, counts) and `docs/DATA_STATUS.md` has the acquisition/status tracker, but this file is the map from dataset name to filesystem path.

All paths are relative to the repository root (`prithvi-reference-assessment/`).

| Source | Dataset | Canonical raw location | Original format | Notes |
|---|---|---|---|---|
| NCCN | Mount Rainier (MORA), current | `data/raw/nccn/NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/MORA_1987_2017_V2_1_1_UTM.shp` | Shapefile | |
| NCCN | North Cascades (NOCA), current | `data/raw/nccn/NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/NOCA_1987_2017_V2_1_1_UTM.shp` | Shapefile | |
| NCCN | Olympic (OLYM), current | `data/raw/nccn/NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/OLYM_1987_2017_V2_1_1_UTM.shp` | Shapefile | |
| NCCN | North Cascades (NOCA), legacy | `data/raw/nccn/V2B/NOCA_1985_2009_V2B_UTM.shp` | Shapefile | Likely superseded by the current V2.1.1 file above — not confirmed |
| NCCN | Olympic (OLYM), legacy | `data/raw/nccn/V2B-2/OLYM_1985_2010_V2B_UTM.shp` | Shapefile | Likely superseded by the current V2.1.1 file above — not confirmed |
| NCCN | Lewis & Clark (LEWI) | `data/raw/nccn/NCCN_Landscape_Change_LPa01_LEWI_1985-2011_DISTRIBUTION/LEWI_1985_2011_Report_UTM.shp` | Shapefile | Only vintage available; no current-schema update exists |
| GLKN | LandTrendr disturbance polygons + schema tables | `data/raw/glkn/LandTrendr` | File Geodatabase (**directory name lacks the `.gdb` extension** — this is confirmed to be a real FileGDB by its internal structure; GDAL needs a `.gdb`-suffixed copy to auto-detect it, see note below) | 177,153 features (63,448 with change_occurred=true+HUC12 attribution, 113,704 without change) |
| GLKN | Stray non-data file | ~~`data/raw/glkn/LandTrendr.textClipping`~~ **(removed 2026-09-22)** | macOS clipping file | Inspected before removal: entire content was the plain text string "LandTrendr" (visible in both UTF-8 and UTF-16 form) — a drag-and-drop artifact, not part of the delivered dataset or any documentation. Confirmed, not just assumed, before deleting |
| ADS R6 | Damage areas | `data/raw/ads/r6/ADS_R6_Damage_allyears.shp` | Shapefile (exported from a GDB — field names truncated to 10 chars) | 913,165 features; `REGION_ID` contains a few stray non-R6 records |
| ADS R10 | Damage areas + damage points + surveyed extent | `data/raw/ads/r10/AK_Region10_AllYears.gdb.zip` | File Geodatabase, zipped | 3 layers, 162,628 features total. **Extracted 2026-09-23** to a persistent working copy at `data/processed/ads_r10/AK_Region10_AllYears.gdb` (raw ZIP itself untouched, preserved as the canonical source) |
| Boundaries — NPS | National Park Service unit boundaries (442 units nationwide) | `data/raw/boundaries/nps/National_Parks.zip` | Shapefile, zipped | Used by NCCN (park-level) and potentially GLKN; not yet extracted |
| Boundaries — ADS R6 | EPA-ecoregion-based candidate regions ("BugNet") | `data/raw/boundaries/ads_r6/BugNet_R6_Regions.shp` | Shapefile | Extracted from `data/raw/boundaries/other/drive-download-...zip` (see below); 19 features, EPSG:4326; not yet confirmed as the final intended boundary |
| Boundaries — ADS R10 | HUC6-based candidate regions ("BugNet") | `data/raw/boundaries/ads_r10/BugNet_R10_Regions.shp` | Shapefile | Extracted from the same ZIP; 20 features, exact subset of the full HUC6 catalog below |
| Boundaries — ADS R10 | Full Alaska HUC6 catalog (38 basins) | `data/raw/boundaries/ads_r10/AK_HUC6_boundaries/AK_HUC6_*.shp` | Shapefile, one file per basin | Extracted from the same ZIP; `BugNet_R10_Regions` is a confirmed 20-of-38 subset of this set |
| Boundaries — other | Original combined ZIP for the three items above | `data/raw/boundaries/other/drive-download-20260923T002841Z-1-001.zip` | ZIP (mixed contents: `BugNet_Regions/` + `AK_HUC6_boundaries/`) | **Kept intact as the canonical source package.** Its contents were extracted once and split into `boundaries/ads_r6/` and `boundaries/ads_r10/` above, per the project's boundary-vs-reference-data separation — see `data/README.md` "ZIP handling" |
| Docs — NCCN | Certification forms / reports (V2.1.1 ×3, LEWI report, V2B ×2) | `docs/source_docs/nccn/*.doc(x)` | Word .doc/.docx | 2 Word lock files (`~$...doc`) previously here were confirmed transient Office artifacts (not real documents) and removed 2026-09-22 |
| Docs — GLKN | Field-level FGDC metadata | `docs/source_docs/glkn/GLKN_metadata.rtf` | RTF | Authored by Al Kirschbaum; see `docs/data_inventory.md` §3.5 for full cross-check against the GDB |
| Docs — GLKN | Published SLBE landscape-dynamics report | `docs/source_docs/glkn/Kirschbaum_2025_SLBE-LandscapeDynamics_1990-2021_SR.pdf` | PDF (42 pp.) | Resolves the HUC10-vs-HUC12 analysis-unit question — see `docs/data_inventory.md` §3.6 |
| Docs — ADS | National IDS flat-file schema readme | `docs/source_docs/ads/IDS_FlatFiles_Readme.pdf` | PDF | Surfaced inside the R10 GDB ZIP on extraction (2026-09-23); relocated here from `data/processed/ads_r10/`. Official USDA documentation of the national IDS schema — applies to both R6 and R10 (same database). ADS R6's `.qmd` FGDC metadata is a separate shapefile sidecar and stays with the raw data, not here |

## Processed data (produced by us — not raw)

### NCCN

Produced by `src/process_nccn.py` (see `docs/data_inventory.md` §12 and `outputs/qa/nccn_processing_report.md` for full detail).

| Dataset | Canonical path | Format | Derived from | Notes |
|---|---|---|---|---|
| MORA, geometry-repaired | `data/processed/nccn/repaired/MORA_repaired.parquet` | GeoParquet | `data/raw/nccn/.../MORA_1987_2017_V2_1_1_UTM.shp` | `make_valid()` applied; original attributes otherwise unchanged |
| NOCA, geometry-repaired | `data/processed/nccn/repaired/NOCA_repaired.parquet` | GeoParquet | `data/raw/nccn/.../NOCA_1987_2017_V2_1_1_UTM.shp` (current, not V2B) | |
| OLYM, geometry-repaired | `data/processed/nccn/repaired/OLYM_repaired.parquet` | GeoParquet | `data/raw/nccn/.../OLYM_1987_2017_V2_1_1_UTM.shp` (current, not V2B) | |
| LEWI, geometry-repaired | `data/processed/nccn/repaired/LEWI_repaired.parquet` | GeoParquet | `data/raw/nccn/.../LEWI_1985_2011_Report_UTM.shp` | |
| NCCN standardized (all 4 parks) | `data/processed/nccn/nccn_standardized.parquet` | GeoParquet | the 4 repaired files above | 12,630 features, EPSG:26910; standardized `source`/`source_dataset`/`source_feature_id`/`park_code`/`year`/`change_class` fields added alongside all original attributes |
| NCCN park boundaries | `data/processed/boundaries/nccn_park_boundaries.parquet` | GeoParquet | `data/raw/boundaries/nps/National_Parks.zip`, filtered to `UNIT_CODE` in {MORA,NOCA,OLYM,LEWI} | Reprojected EPSG:3857 → EPSG:26910; no dissolve (each already 1 feature) |

QA outputs: `outputs/qa/nccn_geometry_repair_qa.csv`, `outputs/qa/nccn_geometry_repair_large_changes.csv` (empty — none found), `outputs/qa/nccn_boundary_relationship_qa.csv`, `outputs/qa/nccn_huc10_fit_*.csv`, `outputs/qa/nccn_huc12_fit_*.csv`, `outputs/qa/nccn_huc10_vs_huc12_comparison.csv`, `outputs/qa/nccn_processing_report.md`, `outputs/qa/nccn_huc_fit_test.md`.

### GLKN

Produced by `src/process_glkn.py` (see `docs/data_inventory.md` §14 and `outputs/qa/glkn_processing_report.md` for full detail).

| Dataset | Canonical path | Format | Derived from | Notes |
|---|---|---|---|---|
| GLKN GDB, working copy | `data/processed/glkn/LandTrendr.gdb` | File Geodatabase | `data/raw/glkn/LandTrendr` | **Pure rename, zero content change** — GDAL needs the `.gdb` extension; the original raw file has no extension by design (see "GDB extension note" below) |
| GLKN confirmed, geometry-repaired | `data/processed/glkn/glkn_confirmed_repaired.parquet` | GeoParquet | `LandTrendr_disturbance_polygons` layer, filtered to `change_occurred=='true'` | `make_valid()` applied; original attributes otherwise unchanged. `change_occurred=='false'` rows are excluded from this product entirely (retained only in raw) |
| GLKN confirmed, standardized | `data/processed/glkn/glkn_confirmed_standardized.parquet` | GeoParquet | the repaired file above | 53,665 features, native CRS (ESRI:102039 ≈ EPSG:5070); standardized fields added, `change_class`=native `agent_01` (unharmonized); all native fields preserved |
| GLKN park boundaries | `data/processed/boundaries/glkn_park_boundaries.parquet` | GeoParquet | `data/raw/boundaries/nps/National_Parks.zip`, filtered to `UNIT_CODE` in the 7 GLKN parks | Context only — **not assumed to be the GLKN analysis extent** |

QA outputs: `outputs/qa/glkn_schema_qa.md`, `outputs/qa/glkn_geometry_validity_before_repair.csv`, `outputs/qa/glkn_geometry_repair_qa.csv`, `outputs/qa/glkn_geometry_repair_large_changes.csv` (empty — none found), `outputs/qa/glkn_huc_geography.csv`, `outputs/qa/glkn_huc10_unassigned.csv`, `outputs/qa/glkn_processing_report.md`.

### ADS R6

Produced by `src/process_ads_r6.py` (see `docs/data_inventory.md` §15 and `outputs/qa/ads_r6_processing_report.md` for full detail). Simplified approach — EPA ecoregions used directly as analysis regions, not a reconstructed ADS boundary.

| Dataset | Canonical path | Format | Derived from | Notes |
|---|---|---|---|---|
| ADS R6 ecoregions, dissolved | `data/processed/boundaries/ads_r6_ecoregions.parquet` | GeoParquet | `data/raw/boundaries/ads_r6/BugNet_R6_Regions.shp`, dissolved by `us_l3code` | 19 state-fragmented raw features → 7 clean EPA Level III ecoregions |
| ADS R6 (Region 6 only), with ecoregion assignment | `data/processed/ads_r6/ads_r6_region6_with_ecoregion.parquet` | GeoParquet | `data/raw/ads/r6/ADS_R6_Damage_allyears.shp`, filtered to `REGION_ID==6` | 911,911 features, native CRS (ESRI:102039); `area_in_own_ecoregion_m2` is the authoritative per-polygon area figure (see processing report for why two earlier area computations were wrong before this one) |

QA outputs: `outputs/qa/ads_r6_region_filter_qa.csv`, `outputs/qa/ads_r6_ecoregion_capture.csv`, `outputs/qa/ads_r6_by_ecoregion_year.csv`, `outputs/qa/ads_r6_by_ecoregion_dca.csv`, `outputs/qa/ads_r6_by_ecoregion_damage_type.csv`, `outputs/qa/ads_r6_processing_report.md`.

### ADS R10

Produced by `src/process_ads_r10.py` (see `docs/data_inventory.md` §16 and `outputs/qa/ads_r10_processing_report.md` for full detail). Same simplified approach as R6 — HUC6 watershed boundaries used directly as analysis regions, not a reconstructed ADS boundary.

| Dataset | Canonical path | Format | Derived from | Notes |
|---|---|---|---|---|
| ADS R10 GDB, working copy | `data/processed/ads_r10/AK_Region10_AllYears.gdb` | File Geodatabase | `data/raw/ads/r10/AK_Region10_AllYears.gdb.zip` | **Pure extraction, zero content change** — mirrors the GLKN `LandTrendr.gdb` precedent |
| ADS R10 HUC6 regions | `data/processed/boundaries/ads_r10_huc6.parquet` | GeoParquet | `data/raw/boundaries/ads_r10/BugNet_R10_Regions.shp` | 20 features — already one row per HUC6, no dissolve needed (unlike R6's ecoregions) |
| ADS R10, with HUC6 assignment | `data/processed/ads_r10/ads_r10_with_huc6.parquet` | GeoParquet | `data/processed/ads_r10/AK_Region10_AllYears.gdb` layer `DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10` (all rows — 100% `REGION_ID`==10, no filter needed) | 151,309 features, EPSG:3338; per-own-HUC6 area assignment applied from the start (avoiding the R6 area-crediting bug rather than re-deriving the fix) |

QA outputs: `outputs/qa/ads_r10_huc6_capture.csv`, `outputs/qa/ads_r10_by_huc6_year.csv`, `outputs/qa/ads_r10_by_huc6_dca.csv`, `outputs/qa/ads_r10_by_huc6_damage_type.csv`, `outputs/qa/ads_r10_processing_report.md`.

## GDB extension note

`data/raw/glkn/LandTrendr` is preserved with its **original name**, exactly as received — it has no `.gdb` extension even though it is one. GDAL/OGR generally needs the `.gdb` extension to auto-detect a File Geodatabase directory. As of the GLKN processing pass (2026-09-23), a **persistent, content-identical, renamed copy** now lives at `data/processed/glkn/LandTrendr.gdb` (see "Processed data" → GLKN above) — `src/process_glkn.py` and any future GLKN work should read from that copy rather than re-creating a temporary one. It is a pure rename (verified: same file count/sizes as the raw original), not a raw-data modification.

## NCCN HUC boundary export (exploratory input, not a processed product)

| Dataset | Canonical path | Format | Notes |
|---|---|---|---|
| NCCN-area HUC10 watersheds | `data/raw/boundaries/nps/Prithvi_NCCN/NCCN_HUC10.shp` | Shapefile | 117 features, EPSG:4326. User-exported selection around MORA/NOCA/OLYM/LEWI. Used in the exploratory spatial-fit test, `outputs/qa/nccn_huc_fit_test.md` |
| NCCN-area HUC12 watersheds | `data/raw/boundaries/nps/Prithvi_NCCN/NCCN_HUC12.shp` (+ original ZIP `NCCN_HUC12-20260923T164821Z-1-001.zip` preserved alongside) | Shapefile | 469 features, EPSG:4326. Added 2026-09-23 — arrived zipped directly in `data/raw/boundaries/nps/`, moved into `Prithvi_NCCN/` alongside HUC10 and extracted there; original ZIP kept. **Result (same test, both HUC10 and HUC12): reference-data footprint does not appear organized around either HUC resolution** — edge alignment stays essentially zero (0.001–0.021) at HUC12 despite ~93–100% areal coverage; see `outputs/qa/nccn_huc_fit_test.md` for the full HUC10-vs-HUC12 comparison, including a flagged coverage gap for NOCA's HUC12 selection specifically |

## Not yet acquired (no manifest entry because nothing exists yet)

- GLKN HUC12 boundary polygons (the `HUC_12` attribute exists per-polygon; boundary geometry does not — 230 of 247 distinct codes are standard USGS WBD format and can be pulled directly, see `docs/glkn_huc12_codes.txt`).
- Confirmation of whether an ADS R6 File Geodatabase (with points/surveyed-extent layers, matching R10) exists beyond the shapefile export we have.
