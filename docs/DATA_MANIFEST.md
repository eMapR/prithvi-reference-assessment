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
| ADS R10 | Damage areas + damage points + surveyed extent | `data/raw/ads/r10/AK_Region10_AllYears.gdb.zip` | File Geodatabase, zipped | 3 layers, 162,628 features total; not yet extracted — read directly via GDAL `/vsizip/` when needed |
| Boundaries — NPS | National Park Service unit boundaries (442 units nationwide) | `data/raw/boundaries/nps/National_Parks.zip` | Shapefile, zipped | Used by NCCN (park-level) and potentially GLKN; not yet extracted |
| Boundaries — ADS R6 | EPA-ecoregion-based candidate regions ("BugNet") | `data/raw/boundaries/ads_r6/BugNet_R6_Regions.shp` | Shapefile | Extracted from `data/raw/boundaries/other/drive-download-...zip` (see below); 19 features, EPSG:4326; not yet confirmed as the final intended boundary |
| Boundaries — ADS R10 | HUC6-based candidate regions ("BugNet") | `data/raw/boundaries/ads_r10/BugNet_R10_Regions.shp` | Shapefile | Extracted from the same ZIP; 20 features, exact subset of the full HUC6 catalog below |
| Boundaries — ADS R10 | Full Alaska HUC6 catalog (38 basins) | `data/raw/boundaries/ads_r10/AK_HUC6_boundaries/AK_HUC6_*.shp` | Shapefile, one file per basin | Extracted from the same ZIP; `BugNet_R10_Regions` is a confirmed 20-of-38 subset of this set |
| Boundaries — other | Original combined ZIP for the three items above | `data/raw/boundaries/other/drive-download-20260923T002841Z-1-001.zip` | ZIP (mixed contents: `BugNet_Regions/` + `AK_HUC6_boundaries/`) | **Kept intact as the canonical source package.** Its contents were extracted once and split into `boundaries/ads_r6/` and `boundaries/ads_r10/` above, per the project's boundary-vs-reference-data separation — see `data/README.md` "ZIP handling" |
| Docs — NCCN | Certification forms / reports (V2.1.1 ×3, LEWI report, V2B ×2) | `docs/source_docs/nccn/*.doc(x)` | Word .doc/.docx | 2 Word lock files (`~$...doc`) previously here were confirmed transient Office artifacts (not real documents) and removed 2026-09-22 |
| Docs — GLKN | Field-level FGDC metadata | `docs/source_docs/glkn/GLKN_metadata.rtf` | RTF | Authored by Al Kirschbaum; see `docs/data_inventory.md` §3.5 for full cross-check against the GDB |
| Docs — GLKN | Published SLBE landscape-dynamics report | `docs/source_docs/glkn/Kirschbaum_2025_SLBE-LandscapeDynamics_1990-2021_SR.pdf` | PDF (42 pp.) | Resolves the HUC10-vs-HUC12 analysis-unit question — see `docs/data_inventory.md` §3.6 |
| Docs — ADS | — | `docs/source_docs/ads/` | — | Empty — no standalone ADS documentation file received yet (ADS R6's `.qmd` FGDC metadata is a shapefile sidecar and stays with the raw data, not here) |

## GDB extension note

`data/raw/glkn/LandTrendr` is preserved with its **original name**, exactly as received — it has no `.gdb` extension even though it is one. GDAL/OGR generally needs the `.gdb` extension to auto-detect a File Geodatabase directory; to actually read this dataset, copy it to a scratch/processed location with a `.gdb` suffix first (e.g. `cp -R data/raw/glkn/LandTrendr /tmp/LandTrendr.gdb`), or pass the driver explicitly. This has been done repeatedly during inspection without ever modifying the original — the same approach should be used for any future processing step, with the renamed working copy living in `data/processed/glkn/`, not `data/raw/`.

## Not yet acquired (no manifest entry because nothing exists yet)

- GLKN HUC12 boundary polygons (the `HUC_12` attribute exists per-polygon; boundary geometry does not — 230 of 247 distinct codes are standard USGS WBD format and can be pulled directly, see `docs/glkn_huc12_codes.txt`).
- USFS ADS Region 10 documentation (if any exists, parallel to the R6 `.qmd`).
- Confirmation of whether an ADS R6 File Geodatabase (with points/surveyed-extent layers, matching R10) exists beyond the shapefile export we have.
