# Prithvi Reference-Data Assessment

NASA-funded project: *A Prithvi-based landscape change attribution service in
support of National Park Service and National Forest monitoring needs* (PI
Robert Kennedy, Oregon State University).

This repository contains the completed **Objective 1, Task 1 — Reference
Data Assessment**. Task 1 characterizes the existing landscape-change
reference data available from four sources (NCCN, GLKN, USFS ADS Region 6,
USFS ADS Region 10) before the project's focal sub-domains are selected and
subsequent Prithvi-EO-2.0 experimental design begins. **It does not select
or rank focal regions** — that is later project work, informed by these
results.

## Start here

**[Read the Task 1 Reference Data Assessment](report/task1_reference_data_assessment.md)**

Principal Task 1 products:

| Product | What it is |
|---|---|
| [`report/task1_reference_data_assessment.md`](report/task1_reference_data_assessment.md) | Human-readable Task 1 report — start here |
| [`outputs/report/task1_master_pixel_summary.csv`](outputs/report/task1_master_pixel_summary.csv) | Principal machine-readable all-years subregion × native-class summary |
| [`notebooks/reference_data_assessment.ipynb`](notebooks/reference_data_assessment.ipynb) | Detailed, reproducible analysis (the analytical source of truth) |
| [`outputs/qa/`](outputs/qa/) | Source-specific quantitative summaries and QA products underlying the report |

A DOCX build of the report has intentionally been removed while the report
content is under revision; it is not a current deliverable.

## What was assessed

Four existing reference-data sources, each kept in its own native
attribution system (no cross-source harmonization at this stage):

| Source | Subregions | Primary attribution view | Native classes |
|---|---|---|---|
| NCCN (NPS) | 4 parks (MORA, NOCA, OLYM, LEWI) | Native landscape-change class | 16 |
| GLKN (NPS) | 7 parks (APIS, INDU, ISRO, MISS, SACN, SLBE, VOYA) | Primary attributed agent (`agent_01`); secondary/tertiary agents retained separately | 10 |
| USFS ADS Region 6 | 7 EPA Level III ecoregions | Damage Causal Agent (DCA) | 91 |
| USFS ADS Region 10 | 20 HUC6 watershed basins | Damage Causal Agent (DCA) | 67 |

NCCN and GLKN each have an **authoritative study-area AOI** documented as
spatial/provenance context — it is not used to clip the published attributed
polygons. The ADS Region 6 ecoregions and Region 10 HUC6 basins are
**project-defined analysis subregions** (adopted from the existing BugNet
framework), not historical ADS survey-area boundaries.

## Task 1 methodology

```
published attributed polygons
  -> project-defined 30 m reference grid
  -> subregion x year x native class
  -> pixel counts / pixel-derived area / spatial prevalence
```

- The 30 m grid is a **Task 1 characterization grid**, not a verified
  HLS/Prithvi training-sampling grid; that alignment is a subsequent design
  decision.
- **Unlabeled ≠ no-change.** Absence of an attributed polygon is never
  interpreted as a stable/no-change observation.
- Native attribution taxonomies are **preserved, not harmonized**, across
  sources.
- Valid same-year multiple attributions are **retained**, not collapsed to
  one class.
- All-years totals are **attributed pixel-years** (a location attributed in
  more than one year contributes once per year), not unique physical area.
- Because of multi-label attribution, native-class spatial prevalence can
  **sum above 100%** within a subregion/year.

## Master pixel-summary table

[`outputs/report/task1_master_pixel_summary.csv`](outputs/report/task1_master_pixel_summary.csv)
combines the four primary all-years quantitative views (NCCN; GLKN primary
agent; ADS R6 DCA; ADS R10 DCA) into one table, without harmonizing native
classes across sources. Built reproducibly by
[`src/build_master_pixel_summary.py`](src/build_master_pixel_summary.py)
from the underlying per-source summary CSVs in `outputs/qa/`.

Schema: `source | subregion | subregion_name | native_class | pixel_count | area_ha | spatial_prevalence_pct`

## Repository structure

```
report/                        Task 1 deliverables
    task1_reference_data_assessment.md   Human-readable report
    figures/                    Report figure assets
outputs/
    report/                     Principal Task 1 outputs
        task1_master_pixel_summary.csv   Master pixel-summary table
        assets/                 Source figure exports used to build the report
    qa/                         Per-source quantitative summaries and QA products
    tables/  spatial/  maps/    Reserved subdirectories, currently empty
notebooks/
    reference_data_assessment.ipynb   Detailed reproducible analysis
src/                            Processing, rasterization, and summary-table scripts
docs/
    data_inventory.md           Full technical inventory (fields, CRS, counts, cross-checks)
    DATA_STATUS.md               Acquisition/status tracker
    DATA_MANIFEST.md             Source-to-canonical-path lookup
    source_docs/                 Documentation shipped with the source datasets
data/
    raw/                        Original source data, exactly as received. Never modified.
    processed/                   Repaired/standardized geometry derived from raw data
                                 (NCCN, GLKN, ADS R6/R10, boundaries)
gee_exploratory/                Retired Earth Engine proof-of-concept (historical only, see below)
```

Raw data, processed data, and generated `outputs/` contents are gitignored
(directory structure is tracked via `.gitkeep`; the master pixel-summary CSV
is a deliberate, explicit exception — see `.gitignore`). See `data/README.md`
for the full raw/processed rules and `docs/DATA_MANIFEST.md` for the
canonical path of every source package received.

## Reproducing the analysis

### Setup

```
conda env create -f environment.yml
conda activate prithvi-ref-assessment
```

or, if not using conda (GDAL-linked packages are more reliably installed via
conda-forge than pip):

```
pip install -r requirements.txt
```

### Key scripts

Reference-label characterization runs at two levels:

1. **Vector-level summaries** — record counts, attributed area, per-class
   composition (`src/process_*.py`, `src/*_regional_summary.py`).
2. **30 m reference-grid rasterization** of each source's native classes,
   independently per subregion x year:
   - [`src/rasterize_common.py`](src/rasterize_common.py) — shared grid/rasterization logic
   - `src/rasterize_nccn.py`, `src/rasterize_glkn.py`, `src/rasterize_ads_r6.py`, `src/rasterize_ads_r10.py` — per-source rasterization
   - [`src/build_pixel_summary_tables.py`](src/build_pixel_summary_tables.py) — per-source subregion x year x class summary tables
   - [`src/build_master_pixel_summary.py`](src/build_master_pixel_summary.py) — combines the four primary summaries into the master table above

See the metadata JSONs in `outputs/qa/` for the exact CRS/resolution/
alignment convention used per source.

To inspect a new/raw dataset (read-only, never modifies the source):

```
python src/inspect_dataset.py data/raw/ads/r6/ADS_R6_Damage_allyears.shp
python src/inspect_dataset.py /vsizip/$(pwd)/data/raw/ads/r10/AK_Region10_AllYears.gdb.zip   # zipped GDB, no extraction needed
```

`data/raw/glkn/LandTrendr` is a real File Geodatabase without a `.gdb`
extension (preserved exactly as received — see `docs/DATA_MANIFEST.md` "GDB
extension note"); GDAL needs a `.gdb`-suffixed copy to open it.

### Design principles

- **Preserve originals.** Raw geodatabases/shapefiles/GeoPackages are never
  modified in place.
- **Unlabeled ≠ no change.** Absence of an attributed polygon is never
  treated as a stable/no-change observation.
- **Overlaps are surfaced, not resolved.** Same-class overlapping polygons
  are dissolved before computing area; cross-class/cross-year overlaps are
  reported as their own explicit quantity rather than resolved by an
  arbitrary priority rule.
- **CRS is never assumed.** Every source's native CRS is inspected before
  any area is calculated, in an explicit, documented, appropriate
  projected/equal-area CRS.
- **Every run produces QA output** — input feature/area counts, regions and
  years covered, and any invalid geometries encountered — not just a
  results CSV.

### Historical context: `gee_exploratory/`

`gee_exploratory/` holds two **retired** Earth Engine proof-of-concept
scripts (an arbitrary 224/112/56-pixel chip-grid approach, and an earlier
region-summary sketch) from before the project moved to the local-Python,
existing-source-region design used throughout this repository. Kept for
historical reference only — not active pipeline code.

## Current boundary and next step

Task 1 is **descriptive**. It characterizes the amount, composition, spatial
distribution, and temporal distribution of the reference information
currently available from each source. It does not rank subregions, score
their diversity, or select a focal region. These results are intended to
support the project's subsequent focal-domain selection and experimental-
design work.
