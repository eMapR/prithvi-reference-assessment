# Data Directory

## `raw/`

**Original data exactly as received.** Nothing in `raw/` is ever modified, renamed, converted, repaired, or reprojected in place. If a file arrived zipped, the ZIP itself is kept as the canonical source package (see "ZIP handling" below). If a file arrived as a File Geodatabase, it stays a File Geodatabase.

If you ever need to change something about a raw file — fix a geometry, reproject it, rename a field, even just unzip it for convenience — copy or derive it into `processed/` instead. `raw/` should always be re-creatable from the original delivery (email attachment, download link, shared drive), and should always match what the data provider actually sent.

Layout:

```
raw/
    nccn/           NCCN attributed landscape-change shapefiles (multiple parks, multiple schema versions)
    glkn/           GLKN File Geodatabase (LandTrendr disturbance polygons + schema tables)
    ads/
        r6/         USFS ADS Region 6 attributed damage shapefile
        r10/        USFS ADS Region 10 File Geodatabase (zipped)
    boundaries/     Region/boundary datasets -- kept separate from reference data (see below)
        nps/        National Park Service unit boundaries (used by both NCCN and, potentially, GLKN)
        ads_r6/     Candidate ADS Region 6 analysis regions (EPA-ecoregion-based)
        ads_r10/    Candidate ADS Region 10 analysis regions (HUC6-based) + the full Alaska HUC6 catalog
        other/      Source packages that don't map to one boundary category alone (see manifest)
```

## `processed/`

**Anything we create.** Repaired geometries, standardized/GeoParquet exports, filtered subsets (e.g. ADS rows actually in Region 6), reprojected boundaries, dissolved multi-part features — all of it goes here, mirroring the same source-based subfolder layout as `raw/` (`nccn/`, `glkn/`, `ads_r6/`, `ads_r10/`, `boundaries/`). Nothing has been written here yet as of this reorganization — no geometry repair, standardization, or conversion has happened.

Every file in `processed/` should be traceable back to a specific file (or files) in `raw/` — prefer a comment/README in the relevant `processed/` subfolder, or a note in `docs/DATA_MANIFEST.md`, over leaving that relationship implicit.

## Boundaries live separately from reference/change data

A boundary dataset (e.g. NPS park boundaries) is not "NCCN data" or "GLKN data" just because NCCN or GLKN happens to use it — the same NPS boundary file is relevant to both. Boundaries get their own `raw/boundaries/` (and `processed/boundaries/`) tree instead of being nested inside a source's own folder.

## Source documentation lives in `docs/source_docs/`, not here

Reports, FGDC/RTF metadata, certification forms, and other documents that describe a dataset (rather than being the geospatial data itself) live under `docs/source_docs/<source>/` — e.g. `docs/source_docs/glkn/GLKN_metadata.rtf`. A shapefile's own *sidecar* files (`.prj`, `.cpg`, `.shp.xml`, `.qmd` — anything sharing the shapefile's basename and shipped alongside it as part of the same delivery) stay bundled with the shapefile in `raw/`, since those are part of the dataset itself, not separate documentation.

## `outputs/` is downstream of all of this

Summary tables, spatial products, maps, and QA reports produced by our own processing go in the top-level `outputs/` directory (`tables/`, `spatial/`, `maps/`, `qa/`), not under `data/`. `data/processed/` is for reusable intermediate data products; `outputs/` is for analytical results meant to be read/shared.

## ZIP handling

When a source delivered a ZIP archive, the ZIP itself is preserved in `raw/` as the canonical package — it is not deleted after extraction. If an extracted copy is needed for actual processing (some tools can't read directly out of a ZIP), that extracted copy belongs in `processed/`, and its provenance (which ZIP it came from) should be documented rather than left implicit. See `docs/DATA_MANIFEST.md` for the current, specific ZIP/extraction relationships in this project — some source ZIPs bundle content that belongs in more than one `raw/boundaries/` subfolder; in that case the original ZIP is kept intact in `boundaries/other/`, and the split, extracted contents live in the folders they actually belong to.

## Basic provenance rules

1. Never overwrite a file in `raw/`. If you're unsure whether a change belongs in `raw/` or `processed/`, it belongs in `processed/`.
2. Every dataset should be traceable to a source and an acquisition context — check `docs/DATA_MANIFEST.md` and `docs/data_inventory.md` before assuming a file's meaning; both are the persistent record of what's actually been inspected.
3. If a `raw/` file's correct destination subfolder is genuinely unclear (e.g. it doesn't cleanly belong to one source or one boundary category), leave it where it is and flag it — don't guess.
