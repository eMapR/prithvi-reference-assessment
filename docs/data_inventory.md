# Data Inventory & Schema Notes

**Last updated:** 2026-09-22 (third pass — project reorganization). All raw data and source documentation was moved from a sibling directory one level above this repo into the canonical structure below. Nothing was renamed, converted, repaired, or otherwise modified in the move — only relocated. Every previously-inventoried dataset was independently re-verified as readable at its new location. See `docs/DATA_MANIFEST.md` for the exact canonical path of every source package.

This file is the persistent technical record. See `docs/DATA_STATUS.md` for the quick human-readable tracker table and `docs/DATA_MANIFEST.md` for exact file paths. Update all three in place as new data arrives — don't let them drift from what `src/inspect_dataset.py` actually reports.

> **`docs/DATA_MANIFEST.md` is the authoritative source for current canonical file paths, full stop.** This document was written across several inspection passes, before and after the 2026-09-22 reorganization, and intentionally was **not** mechanically rewritten path-by-path afterward — many path references below still show pre-reorganization bare filenames (e.g. `GLKN/LandTrendr`, `ADS_R6/ADS_R6_Damage_allyears.shp`, `National_Parks.zip`, `drive-download-...zip`) rather than their current `data/raw/...` location. Treat every such mention here as a **dataset identifier**, not a literal path — always look it up in `docs/DATA_MANIFEST.md` before acting on it (e.g. before writing a script that opens a file). The technical content in this document (fields, CRS, counts, cross-checks against documentation) remains accurate regardless of path staleness.

## 0. Where things actually are

All raw data now lives under `data/raw/` in this repository, organized by source: `data/raw/nccn/`, `data/raw/glkn/`, `data/raw/ads/{r6,r10}/`, and `data/raw/boundaries/{nps,ads_r6,ads_r10,other}/`. Source documentation (reports, metadata, certification forms) lives separately under `docs/source_docs/{nccn,glkn,ads}/`. See `docs/DATA_MANIFEST.md` for the exact path of every individual package, and `data/README.md` for the rules governing this structure (raw vs. processed, boundaries kept separate from reference data, ZIP-handling policy).

`data/raw/glkn/LandTrendr` is preserved with its **original name** (no `.gdb` extension), exactly as received — it is confirmed to be a real File Geodatabase by its internal file structure (`a00000001.gdbtable`, etc.), not by its name. GDAL/OGR needs a `.gdb`-suffixed copy to auto-detect it; this has been done repeatedly during inspection via temporary copies, never modifying the original (see `docs/DATA_MANIFEST.md` "GDB extension note").

The two boundary-candidate ZIPs (`National_Parks.zip`, and the combined `drive-download-...zip` covering both ADS R6 and R10 boundary candidates) are preserved intact in `data/raw/boundaries/`. The combined ZIP's contents were extracted once and split into `boundaries/ads_r6/` and `boundaries/ads_r10/` per the project's boundary-organization scheme (boundaries separated from reference data, and by which ADS region they apply to) — the original ZIP remains in `boundaries/other/` as the canonical source package; see `docs/DATA_MANIFEST.md` for the full relationship.

## 1. Status at a glance

See `docs/DATA_STATUS.md` for the full table. Summary: NCCN (6 shapefiles, all inspected), GLKN (1 real GDB with 177,153 features, inspected), ADS R6 (1 shapefile, 913,165 features, inspected — likely missing sibling layers), ADS R10 (1 zipped GDB, 3 layers, 162,628 total features, inspected), boundary candidates for ADS R6/R10 (received, inspected), national NPS park boundaries (received, inspected, all 11 NCCN+GLKN target parks matched — see §5.3). Still missing: GLKN HUC12 boundary polygons.

## 2. NCCN

*(Unchanged from the first inspection pass — see below. Still accurate.)*

### 2.0 Protocol history (source-provided, added 2026-09-23)

The following is reproduced from NCCN, not paraphrased, and is now also in `notebooks/reference_data_assessment.ipynb` (NCCN §1) alongside a QA check against the processed data:

> - NCCN developed the landscape-change protocol as part of NPS Vital Signs Monitoring.
> - Initial implementations were NOCA (2012), MORA (2013), and OLYM (2014), using OSU/eMapR LandTrendr.
> - The supplied dataset was generated from LandTrendr for 1987–2017.
> - Disturbance pixels for each year were aggregated into patches using adjacency rules and a minimum mapping unit of 0.8 ha (2 acres).
> - Those candidate disturbance patches were subsequently human reviewed and labeled.
> - MORA and NOCA use eight change categories: Avalanche, Blowdown, Clearing, Defoliation, Development, Fire, Mass Movement, and Riparian Change.
> - OLYM additionally includes Ice Damage and Coastal Change.

This describes how the patches were generated and classified — it does **not** define the outer monitoring/study-area boundary (see §12.1 / the notebook's Section 7 for that separate, unresolved question; nothing about the boundary should be inferred from this description). **These are human-interpreted LandTrendr disturbance patches, not a wall-to-wall land-cover map** — absence of a patch is not evidence of confirmed no-change.

This description covers MORA/NOCA/OLYM only (the "initial implementations," all current V2.1.1 schema). **LEWI is a separate dataset with its own earlier implementation and schema vintage, not covered by this description.**

**QA check against the processed data** (`data/processed/nccn/nccn_standardized.parquet`): MORA, NOCA, and OLYM match exactly — year range 1987–2017 with zero rows outside it, and zero unexpected or missing classes relative to the two category lists above, for all three parks. LEWI's data (1985–2011) falls partly outside 1987–2017, as expected given it's a separate dataset — flagged, not silently reconciled.

### 2.1 Files present

| File | Park | Years | Records | Schema family |
|---|---|---|---|---|
| `NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/MORA_1987_2017_V2_1_1_UTM.shp` | Mount Rainier (MORA) | 1987–2017 | 2,234 | **V2.1.1 (current)** |
| `.../NOCA_1987_2017_V2_1_1_UTM.shp` | North Cascades (NOCA) | 1987–2017 | 5,547 | **V2.1.1 (current)** |
| `.../OLYM_1987_2017_V2_1_1_UTM.shp` | Olympic (OLYM) | 1987–2017 | 2,043 | **V2.1.1 (current)** |
| `V2B/NOCA_1985_2009_V2B_UTM.shp` | North Cascades | 1985–2009 | 9,980 | Legacy (superseded by V2.1.1 above) |
| `V2B-2/OLYM_1985_2010_V2B_UTM.shp` | Olympic | 1985–2010 | 22,553 | Legacy (superseded by V2.1.1 above) |
| `NCCN_Landscape_Change_LPa01_LEWI_1985-2011_DISTRIBUTION/LEWI_1985_2011_Report_UTM.shp` | Lewis & Clark (LEWI) | 1985–2011 | 2,806 | Own vintage ("V2A"); no current-schema version exists yet |

All six share CRS `NAD_1983_UTM_Zone_10N` (EPSG:26910).

### 2.2 Two schema families

**V2.1.1 (MORA, NOCA-new, OLYM-new) — 15 fields:** `Event_type, ChangeType, Confidence, Alt_type, In_Park, Dist_year, Dist_name, Park_code, Detect_yr, Patch_name, Perim_m, Area_m, UTME, UTMN, DPL`

**Legacy (NOCA-V2B, OLYM-V2B) — 12 fields:** `PatchID, In_Park, AnalysisYr, Area_m, Perim_m, Chnge_type, Source, UTME, UTMN, Park_code, Confidence, Alt_type`

**LEWI (its own vintage) — 13 fields:** `AnalysisYr, Confidence, Alt_agent, Star_2km, State, PatchID, In_Park, Area_m, Perim_m, Chnge_type, Source, UTME, UTMN` (no `Park_code` field — only `In_Park` + `State`)

Documented rename mapping (from the MORA certification form): `Progressive Defoliation → Defoliation`, `Tree Toppling → Blowdown`, `Riparian → Riparian Change`.

### 2.3 Field meanings (from FGDC metadata + certification forms)

- **`ChangeType`/`Chnge_type`** — primary disturbance class. Maps to `change_class`.
- **`Alt_type`/`Alt_agent`** — secondary label, populated when `Confidence` is 1–2 or a patch mixes two types. Contains values *excluded from the primary field by design*: `Annual Variability` (transient spectral noise, not of interest to NCCN), `Unknown`, (LEWI only) `Agricultural`. These appear as *primary* values only in the older V2B legacy files.
- **`Confidence`** (1–3): subjective office-assigned confidence.
- **`Dist_year`** (V2.1.1 only): actual disturbance year, populated **only for `ChangeType=='Fire'`**; `0` is a sentinel, not a missing value.
- **`Detect_yr`** (V2.1.1 only): Landsat detection year, populated for every record (1987–2018). General-purpose year field; prefer `Dist_year` for Fire specifically.
- **`AnalysisYr`** (legacy/LEWI): single year field, no fire-specific split.
- **`In_Park`** (Y/N): the source's own precomputed spatial join — but against a "Protected Areas" study area that extends into surrounding USFS Wilderness, not the park boundary alone. MORA has 31 2017-fire patches deliberately **not clipped** to the study area at all.
- **`Park_code`**: MORA/NOCA/OLYM. Absent in LEWI.
- **`Area_m`/`Perim_m`**: precomputed by the source (m²/m) — cross-check against our own geometry-based calculations.
- **`Patch_name`(V2.1.1)/`PatchID`(legacy/LEWI)**: unique ID, verified unique both by source QA and empirically here (0 duplicates in every file).
- **`Event_type`(V2.1.1)/`Source`(legacy/LEWI)**: **not a disturbance class** — records *how* the label was assigned (`Office`/`Field`/legacy-only `Model`). V2.1.1 has no `Model` value at all.
- **`DPL`**: Data Processing Level (`Accepted`/`Updated`).
- Minimum mapped unit ~2 acres (0.81 ha), with small documented exceptions.
- Source explicitly states **polygon_count ≠ disturbance-event count** — one event can be multiple polygons.

### 2.4 Data-quality issues found

| File | Invalid geoms | % | Cause (via `explain_validity`) |
|---|---|---|---|
| MORA (V2.1.1) | 1,793 / 2,234 | 80% | Ring self-intersection |
| NOCA (V2.1.1) | 3,929 / 5,547 | 71% | Ring self-intersection |
| OLYM (V2.1.1) | 56 / 2,043 | 2.7% | Ring self-intersection |
| LEWI | 13 / 2,806 | 0.5% | Ring self-intersection |
| NOCA (V2B legacy) | 13 / 9,980 | 0.1% | Ring self-intersection |
| OLYM (V2B legacy) | 49 / 22,553 | 0.2% | Ring self-intersection |

Invalidity is **not** cleanly explained by `In_Park` status (checked directly). Root cause undocumented; **ring self-intersections also showed up independently in GLKN's data** (§3.4) — both are LandTrendr-derived patch products, so this may be a systematic artifact of the LandTrendr vectorization pipeline itself, not a one-off error in a single park. Worth asking the NCCN/GLKN data stewards. Must be repaired (`make_valid()`) in `data/processed/`, never in raw data.

### 2.5 Unexplained — flagged, not guessed

- LEWI's `Star_2km` field (Y/N).
- Why V2.1.1 dropped `Model` from `Event_type`.

## 3. GLKN — corrected: real data, not empty

**Previous inventory incorrectly reported GLKN as having "nothing but a stray file."** That was based only on what `find` showed by file extension. `GLKN/LandTrendr` is a directory whose internal file signatures (`a00000001.gdbtable`/`.gdbtablx`/`.gdbindexes`, `.freelist`, `.spx`, `.horizon`, `.atx` index files) are unambiguously an ESRI File Geodatabase — just missing the `.gdb` extension GDAL's driver normally keys off of. Copied (not moved) to a scratch path with a `.gdb` suffix to open it; confirmed via `fiona.listlayers()`.

### 3.1 Layers

| Layer | Type | Rows | Role |
|---|---|---|---|
| `LandTrendr_disturbance_polygons` | Spatial (MultiPolygon) | 177,153 | Reference data |
| `SCH_DATASET` | Non-spatial | 0 | Schema/admin table |
| `SCH_RELEASE` | Non-spatial | 1 | Schema/admin table |
| `SCH_UNIQUEID` | Non-spatial | 11 | Schema/admin table |

CRS: ESRI:102039 (same defining parameters as EPSG:5070). 49 fields on the main layer.

### 3.2 This dataset is structurally different from NCCN and ADS

GLKN's product is a **land-cover-transition** dataset with *optional* disturbance-agent attribution layered on top, not a pure disturbance-agent labeling scheme:

- **`change_occurred`**: `false` for 123,488 rows, `true` for 53,665 rows. This is a **genuine, explicit no-change/stable class** — the one case so far where "unlabeled" and "no change" are legitimately the same thing, because the source says so explicitly (per the original project instructions: treat as no-change *only* when the source contains an explicit stable/no-change label — this is that case). This count matches `agent_01`'s null count exactly (123,488).
- **`agent_01`/`agent_02`/`agent_03`** (+ `_perc`, `_cov_remain` per slot): up to **three concurrent causal agents per polygon**, each with % of polygon affected and % canopy cover remaining. `agent_01` values (of the 53,665 `change_occurred=='true'` rows): `harvest` (23,249), `insect_disease_defo` (14,141), `development` (12,545), `beaver` (1,793), `agriculture` (731), `blowdown` (456), `unknown` (286), `fire` (246), `insect_disease_mort` (163), `flooding` (55). Note **fire is a small category here** — a real contrast with NCCN (PNW, fire-dominated in some parks) and useful cross-source context.
- **`start_class_01/02/03`** and **`end_class_01/02/03`** (+ `_perc` per slot): pre- and post-disturbance **land-cover class** (not agent) — `forest_closed`, `forest_open`, `forest_semi_closed`, `herbaceous`, `shrub`, `water`, `pervious`, `impervious`, `impervious_vegetated`. This before/after land-cover dimension has no equivalent in NCCN or ADS — worth preserving as extra context, not forcing into `change_class`.
- **`park`**: `sacn`, `apis`, `isro`, `voya`, `slbe`, `miss`, `indu` — 7 real GLKN member parks, **populated for every single row** (0 missing) — unlike `agent_01`, region assignment here is not ambiguous.
- **`HUC_12`**: populated on only 63,448 of 177,153 rows (113,704 true null, 1 empty string) — **not populated for every row**, unlike `park`. Population rate and scheme both **vary sharply by park** (do not assume one watershed scheme applies GLKN-wide):

  | Park | Null | Standard numeric code | Non-standard (island-style) code |
  |---|---|---|---|
  | apis | 65% | 35% | 0% |
  | indu | 87% | 13% | ~0% (1 row) |
  | miss | 35% | 65% | 0% |
  | sacn | 77% | 23% | 0% |
  | slbe | 80% | 20% | 0% |
  | isro | 47% | 0.1% | **99.9%** |
  | voya | 72% | 21% | 7% |

  **Is the "standard numeric" code actually HUC12, HUC10, or a mixture? Checked directly, because GLKN documentation for at least Sleeping Bear Dunes (slbe) states its analysis used HUC10 units, despite the field being named `HUC_12`.** Test: if the field really held a HUC10 code zero-padded to 12 digits, every code sharing a 10-digit prefix would collapse to exactly one 12-digit value per prefix, always ending in `00`. Instead, **every park using the numeric scheme — including slbe — shows multiple distinct 12-digit codes per 10-digit prefix** (ratios of 3.1–7.6 distinct codes per prefix) **with varied, non-`00` two-digit suffixes** (`01`,`02`,`03`,`04`,`06`,`07`,...). That is the structural signature of genuine HUC12 subwatershed codes, not a repeated/padded HUC10. Specifically for slbe: 25 distinct 12-digit codes across only 7 distinct HUC10 parents, non-zero suffixes throughout. **The simple "field is mislabeled, really contains HUC10" hypothesis is not supported by the numeric pattern, even for slbe** — this is a genuine, unresolved tension between the documented analysis unit and the stored attribute, not something to silently resolve. Two non-exclusive possibilities, neither confirmed here: (1) polygons are tagged with real HUC12 codes via a later, uniform spatial join against the national WBD, while the SBD report separately aggregated/presented results at HUC10; or (2) the original sampling/stratification design used HUC10 while this attribute was populated independently. **Needs Al's clarification, not an inferred answer.**

  Of the 247 distinct non-blank values overall: 230 are standard 12-digit numeric codes (per above, these look like genuine HUC12s in every park that uses them); 17 are non-standard (`2AA-01`, `2AB-08`, `5PB-20`-style), overwhelmingly on Isle Royale (`isro`: 16,025 rows) plus a little on Voyageurs (`voya`: 926) and Indiana Dunes (`indu`: 1) — an island/park-specific micro-watershed scheme, not USGS WBD format, won't resolve against the national WBD. Three further values are placeholder-like: `isro: 040203000000` (19 rows — isro's *only* "standard" code) and `slbe: 040602000000` (9 rows, 0.2% of slbe's populated codes) both end in eight zeros (HUC8-level, nothing resolved below it — likely a failed/default join, not real geography); `voya: 090300012400` (329 rows) only has its last pair as `00`, a different and less clear-cut case, possibly a legitimately but unusually numbered subwatershed. Full itemized list (with the standard/non-standard split) saved to `docs/glkn_huc12_codes.txt`. This is only the *attribute* — no boundary geometry for any HUC exists anywhere in this GDB (confirmed via both `fiona.listlayers()` and `ogrinfo`: exactly 4 layers total, none a boundary layer — see §3.1).

  **Practical implication for slbe specifically**: there may be two legitimate boundary choices — join at the 25 HUC12s actually stored in the attribute (matches the data exactly), or dissolve up to the 7 HUC10 parents (matches the documented analysis level in the report you found). Don't pick one silently; confirm with Al which one the report's numbers actually correspond to.
- **`owner_type1`/`owner_name1`**: land ownership (`Private`, `Federal`, `State`, `Native American`, `County`, plus Canadian categories `Crown Land Unpatented/Patent/Freehold Disposition` — this dataset extends across the Canadian border in places, e.g. near Voyageurs/Isle Royale).
- **`UNIQUE`**: confirmed unique (0 duplicates) — the true row-level ID, despite the more ID-sounding `uniqID` actually repeating up to 6× (tracks the same physical patch across repeated annual assessments) and `index` being a spectral-index label (`ENC`/`nbr`/`nbr_band5`), not an ID at all, despite the name.
- **`analysis_yrs`** (string, e.g. `"1990_2020"`): the overall multi-decade study window used for that park's LandTrendr run — **not** a per-polygon disturbance year. The per-polygon year is the separate `year` field (1986–2021, fully populated).
- **`interp_date`/`cert_date`**: real datetime columns (2009–2024 / 2014–2024) — GDAL/pyogrio already parses these as proper datetimes; a first pass of `inspect_dataset.py` mishandled real datetime columns by coercing them to numbers, producing nonsense ranges — **fixed** in the script (now reports native datetime min/max directly).
- **`LT_version`**: `LTGEE.2019`–`LTGEE.2023` for most parks, but `2.1` and `0.423` for others — different parks were processed with different LandTrendr software versions.
- **`protocol_version`**: `1.0` for 107,727 rows, missing for 69,426 (39%) — a real completeness gap, not investigated further yet.
- **`field_valid_candid`**/**`cross_valid`**: small field-validation/cross-validation flag columns (34 and 1,483 populated rows respectively) — a small accuracy-assessment subsample exists.

### 3.3 IDs

Use **`UNIQUE`** as the true unique key (0 duplicates, verified). Do not use `uniqID` (repeats) or `index` (a spectral-index label, not an ID) despite their names.

### 3.4 Data-quality issues found

- Geometry invalidity: 1,122 / 177,153 (0.63%), all **ring self-intersections** (same failure mode as NCCN — see §2.4).
- `pyogrio` warns during read that some polygons have "more than 100 parts" (`organizePolygons()` performance warning) — some GLKN multipolygons are extremely complex; not necessarily invalid, but worth knowing before running anything expensive on the whole layer.

### 3.5 Documentation cross-check: `GLKN_metadata.rtf` and the Kirschbaum 2025 SLBE report

Two documentation files were received and inspected against the GDB inventoried above: `GLKN_metadata.rtf` (FGDC-style metadata authored by Al Kirschbaum, NPS GLKN, last updated 2024-11-05) and `Kirschbaum_2025_SLBE-LandscapeDynamics_1990-2021_SR.pdf` (the published Sleeping Bear Dunes report, 42 pages). Neither was modified; both were read via read-only conversion/extraction. Findings below are explicitly labeled **[DOCUMENTED]** (stated directly in one of the two sources, quoted or closely paraphrased), **[GDB-CONFIRMED]** (verified empirically against the actual GDB in this session), or **[UNRESOLVED]** (neither source addresses it, or the sources conflict).

**1–2. What area was analyzed, and how were analysis units defined?**
**[DOCUMENTED]** For SLBE specifically, the report states plainly: *"The analysis was conducted inside and adjacent to Sleeping Bear Dunes National Lakeshore... The analysis area extended into seven watersheds that could potentially influence the park... Watersheds were defined by level-10 delineations of the National Hydrography Dataset's Hydrologic Unit Code (HUC)."* Exact figures given: **215,844 ha monitored total, of which 23,879 ha is inside SLBE itself** — i.e., ~89% of the monitored area is outside the park boundary, in the surrounding watersheds. The GLKN metadata's dataset title independently confirms the same "in and around" framing network-wide: *"Landscape disturbances delineated and validated in and around nine national parks within the Great Lakes network."* This exactly parallels NCCN's "Protected Areas study area" extending beyond the park (§2.3) — a consistent pattern across both networks: **park boundary ≠ monitoring/analysis landscape.**

**3. What does `HUC_12` specifically represent?**
**[DOCUMENTED]** — and this directly resolves the tension flagged in the prior inventory pass. The SLBE report's Appendix A states explicitly: *"Watershed identifier: During validation we add the unique 12-digit watershed identifier, referred to as the Hydrologic Unit Code 12 (HUC12) from the USGS database."* This is an **unambiguous, written confirmation that the per-polygon attribute is a genuine HUC12 code**, not a mislabeled HUC10 — consistent with (and now confirming) the numeric-structure analysis from the previous session (multiple distinct 12-digit codes per 10-digit parent, varied non-`00` suffixes, even for slbe).

The HUC10-vs-HUC12 apparent conflict is fully explained: **these are two different, both-legitimate things.** The report's own Figure 2 / Tables 5–6 / Figure 9 aggregate and present results **by the 7 HUC10 watersheds** shown in Figure 2 — that is a deliberate reporting/presentation choice made *on top of* the finer per-polygon HUC12 attribute, not evidence that the attribute itself is actually HUC10. **[GDB-CONFIRMED]**: this reporting-level HUC10 grouping is consistent with the 7-parents-to-25-children ratio found for slbe in the prior session.

**4. Why is `HUC_12` populated for only part of the dataset?**
**[GDB-CONFIRMED — this is a new, cleaner answer, superseding the prior session's "may reflect a sampling design" speculation.]** The metadata states `HUC_12` is added *"during validation"* — the same validation step that also fills in `agent_01` etc., which the metadata explicitly restricts to confirmed disturbances (*"If disturbance was determined to be 'true'..."*). Tested this directly against the GDB:

| Park | `HUC_12` populated when `change_occurred=='true'` | `HUC_12` populated when `change_occurred=='false'` |
|---|---|---|
| apis | 100.0% (11,951/11,951) | 0.03% |
| indu | 100.0% (362/362) | 0.0% |
| isro | 100.0% (16,042/16,042) | 0.01% |
| sacn | 100.0% (10,013/10,013) | 0.01% |
| slbe | 100.0% (4,422/4,422) | 0.03% |
| voya | 100.0% (6,252/6,252) | 0.71% |
| **miss** | 100.0% (4,623/4,623) | **56.2% (9,651/17,184)** |

`HUC_12` is populated in **exactly 100.0% of `change_occurred=='true'` rows, in every one of the 7 parks, with zero exceptions** — population is driven by confirmed-disturbance status, not by a park-specific watershed scheme as previously speculated. The apparent "differs sharply by park" pattern from the prior session is now understood to be driven mostly by each park's differing overall confirmed-disturbance rate. **One genuine anomaly remains unexplained: `miss` has HUC_12 populated for 56% of its *false* (non-disturbance) rows too, unlike every other park (≤0.7%).** Neither document explains this. **[UNRESOLVED — flag for Al.]**

**5. What do the Isle Royale-style codes (`2AA-01`, etc.) represent?**
**[UNRESOLVED]** — searched both documents in full; neither mentions these codes, Isle Royale-specific watershed handling, or any custom/non-USGS coding scheme. Not documented anywhere received so far.

**6. How were candidate/reference polygons generated?**
**[DOCUMENTED]** LandTrendr (automated per-pixel, 30 m Landsat time-series segmentation) flags candidate disturbance patches; adjacent same-year-disturbance pixels are grouped via 8-neighbor adjacency into patches; patches ≤10 pixels (~1 ha / 2.5 ac) are dropped as unverifiable. Every remaining LandTrendr-generated polygon is then manually reviewed by an interpreter using high-resolution imagery (often NAIP, ~1 m) plus the full Landsat time series, who determines whether a real disturbance occurred and, if so, its agent(s).

**7. What does `change_occurred=='true'/'false'` mean?**
**[DOCUMENTED]**, verbatim from the metadata: *"After interpretation, did a disturbance actually occur at this location. True=disturbance occurred, False=disturbance did NOT occur."*

**8. Were `false`/no-change polygons deliberately retained as reference samples?**
**[DOCUMENTED — and this changes the prior session's framing.]** The SLBE report states: *"a total of 22,329 LandTrendr-delineated disturbance polygons were validated, **removing all false positive (commission) polygons from the summary analysis**."* **[GDB-CONFIRMED]**: 22,329 is exactly SLBE's total row count in the GDB (17,907 false + 4,422 true) — confirming the report's "validated" figure is the *entire* candidate pool, before the false positives are excluded from further analysis.

This means: `change_occurred=='false'` rows are **retained in the raw GDB** (confirmed structurally, unchanged from the prior session), but the source's own stated practice is to treat them as **discarded commission errors**, not as a first-class "confirmed no-change" analytical product — they receive essentially no further attribution (per the HUC_12/agent_01 finding above, in 6 of 7 parks). **This is a meaningful correction to the prior session's framing**, which treated `change_occurred=='false'` more like a validated stable-reference class. The more accurate characterization: these are *automated-candidate locations that a human reviewer determined were false alarms*, kept in the data as a record of what was checked and rejected, not curated as representative "no-change" ecological samples. Whether to use them as weak evidence of no-change anyway is a project decision, not something either source recommends.

**9. How should `agent_01/02/03` and their percentages be interpreted?**
**[DOCUMENTED]** Up to 3 agents per polygon, drawn from a fixed 9-value vocabulary (`agriculture, beaver, blowdown, development, fire, unknown, forest harvest, insect/disease (mortality), insect/disease (defoliation)`) — confirms the vocabulary inferred empirically last session maps exactly onto this controlled list. `agent_0N_perc` (valid range 10–100) is *"the percent of the [polygon] area affected by [that] disturbance agent"* — **not necessarily mutually exclusive shares that sum to 100% across agents**, since co-located/overlapping agent footprints within one polygon are possible. `agent_0N_cov_remain` (0–90) applies **only when the agent is forest harvest** — an estimate of overstory cover remaining, in 10% increments — not a general severity field for all agents, as the prior session's wording implied. A separate field, `perc_poly_affect` (10–100, not previously called out individually), records the overall percent of the polygon affected by *any* disturbance — worth using for area-weighting if not 100%. Report Table 3 also shows the 9-agent vocabulary gets **further collapsed to 6 groups for presentation** in the SLBE report itself (`forest harvest` light/moderate/heavy → one "Forest harvest" group; both insect/disease types → "Forest pathogen"; agriculture+development → "Development") — a third, coarser vocabulary layer worth knowing about if comparing our future crosswalk against how GLKN's own reports group agents.

**10. How was disturbance year assigned?**
**[DOCUMENTED]** `year` is *"automatically generated by LandTrendr during processing"* — i.e., an algorithmic detection year, analogous to NCCN's `Detect_yr`. **Unlike NCCN, GLKN documents no separate manually-verified "actual disturbance year" override field** (NCCN has `Dist_year` for fire specifically) — `year` is the only year field, and per the metadata it is not manually corrected.

**11. Were boundary-crossing polygons clipped, or assigned by majority area?**
**[DOCUMENTED]**, directly answers this: *"If a polygon spanned boundaries (watershed, ownership), the attribute with the majority of the polygon represented was chosen."* **Polygons are not clipped at watershed/ownership boundaries — they are assigned a single attribute value by majority-area rule.** This matters directly for our region-summary methodology: a GLKN polygon's `HUC_12` (or `owner_type1`) reflects whichever watershed/owner covers the *majority* of that polygon, not necessarily its full extent — a polygon straddling two HUC12s will show only one of them, with some of its true area effectively misattributed to whichever HUC12 has the plurality. This is a real, documented source of boundary-area error to account for, not guess around, if we later do our own independent spatial join against HUC boundaries instead of trusting the stored attribute.

**12. Do the reports distinguish the park boundary from a larger monitoring/analysis landscape?**
**[DOCUMENTED]** Yes, explicitly and by design (see §1–2 above) — Figure 1's caption in the SLBE report: *"Green indicates area monitored outside the park in additional watersheds."* The `loc_01` field (metadata: *"Location of polygon, inside or outside the park"*, values like `slbe`/`non_slbe`) is the per-polygon mechanism for this — **not yet empirically checked against the GDB this session** (flagged as a follow-up, not run out of scope for this task).

**13. Does a sampling/stratification design explain the differing `HUC_12` population rates by park?**
**[GDB-CONFIRMED, see Q4]** No formal stratification or sampling design is documented in either source — LandTrendr is run wall-to-wall (every pixel), not on a spatial sample. The population-rate differences are now explained by the `change_occurred`-driven pattern in Q4, not by a per-park watershed-scheme choice.

**14. Any definitions resolving fields that were ambiguous during the GDB inspection?**
Resolved: `index` = *"Landsat band or index used to produce this polygon"* (confirms it's not an ID); `cross_valid` = *"If polygon was cross-validated by someone else in the lab this field would equal 1"*; `analysis_yrs` = explicitly marked *"Internal use only"* by the source itself — do not treat as a reportable field; `uniqID` = *"simplified form of UNIQUE"* (confirms `UNIQUE`, not `uniqID`, is the real key, matching the empirical finding). **Still not resolved**: `field_valid_candid`'s own metadata description is just the word *"comments"* copy-pasted from the `comments` field's description — the source documentation itself is imprecise here, not just our reading of it.

**Discrepancies found between the documentation and the actual GDB (flagging, not resolving):**
- The metadata states the dataset contains **114,049** `LandTrendr_disturbance_polygons` records; the live GDB has **177,153**. Given the metadata records "In work" / "Annually" updated status, this is most likely a stale count from an earlier snapshot the metadata document wasn't regenerated for — but this is inferred, not confirmed.
- The metadata's top-level scope statement and its own `park` field valid-value list disagree with each other **and** with the actual data: the metadata's abstract/keywords name **nine** parks (`PIRO, APIS, VOYA, GRPO, SLBE, INDU, ISRO, MISS, SACN`); the `park` field's own documented valid-value list names **eight** (omits `GRPO`); the GDB itself contains only **seven** (`sacn, apis, isro, voya, slbe, miss, indu` — omits both `PIRO` and `GRPO`). Not resolved here — worth asking whether PIRO (Pictured Rocks) and GRPO (Grand Portage) data exists elsewhere and simply isn't in this GDB snapshot.
- Documented valid range for `year` is 1990–2023; empirically the GDB has one single row at `year=1986` (otherwise consistent) — a minor, single-row discrepancy.
- Documented valid range for `interp_date` is 2017–2024; empirically the GDB's minimum is **2009-06-16** — an 8-year gap below the documented lower bound, larger and less easily dismissed than the `year` discrepancy. Not resolved.

### 3.6 Answer to the boundary question (A–E)

**The documentation supports (E): there are multiple legitimate geographic summaries, serving different purposes — not one correct answer to pick.** Specifically, for GLKN:

- **HUC12** is the real, per-polygon, USGS-sourced attribute actually stored in the GDB (confirmed in writing, §3.5 Q3) — the finest-grained, most literal join key, available (with the caveats in Q4 and Q11) for confirmed disturbances.
- **HUC10** is the unit GLKN's own published analysis and reporting (at least for SLBE) is built around — Figure 2, Tables 5–6, and Figure 9 in the SLBE report all present results by the 7 HUC10 watersheds, not by HUC12. **If the goal is to reproduce or compare against GLKN's own published numbers, HUC10 is the unit that matches those tables — not HUC12.**
- **NPS park boundary (A)** is explicitly documented as *not* the analysis unit on its own — both sources describe monitoring "in and around" parks, with the large majority of SLBE's monitored area (89%) outside the park. Using the park boundary alone would exclude most of what GLKN itself analyzed.
- **Park-specific/custom boundaries (D)**: no evidence of a boundary beyond HUC10/HUC12 in either document (the Isle Royale-style codes remain unexplained, §3.5 Q5, but nothing suggests they define a boundary rather than just a non-standard ID scheme).

**Practical implication**: which of HUC10 or HUC12 (or both) to use depends on the actual goal — matching GLKN's own published, human-reviewed numbers argues for HUC10; preserving full attribute fidelity and finer spatial resolution argues for HUC12. This should be a deliberate choice once we get to the actual region-summary step, not defaulted to whichever is easier to implement.

### 3.7 Does this change how the 177,153 polygons or the no-change records should be interpreted?

Yes, in two ways:
1. **The `false` rows (123,488 of 177,153) should be understood as reviewed-and-rejected LandTrendr candidates that GLKN's own workflow discards before analysis, not as a curated "confirmed stable" reference class** (§3.5 Q8). This doesn't mean they're useless to us, but treating them as directly equivalent to a deliberate no-change sample would overstate what the source data actually represents.
2. **The differing `HUC_12` population rates by park are not evidence of different watershed schemes per park** (as the prior inventory pass speculated) — they're explained by each park's confirmed-disturbance rate, with one unexplained exception (`miss`).

Everything else from the prior inventory pass (agent vocabulary, land-cover transition fields, `UNIQUE` as the real ID, geometry invalidity rate, etc.) stands as previously documented — nothing here contradicts it.

## 4. USFS ADS

### 4.1 Region 6 (previously inspected)

`ADS_R6/ADS_R6_Damage_allyears.shp` — 913,165 features, `Polygon`/`MultiPolygon`, ESRI:102039 (~EPSG:5070). Field names are **truncated to 10 characters** (`DAMAGE_ARE`, `DCA_COMMON`, `DAMAGE_TYP`, `DAMAGE_T_1`, `HOST_GRO_1`, ...) — a shapefile fingerprint, confirmed by comparing against R10 below, which has the same fields **un-truncated** (`DAMAGE_AREA_ID`, `DCA_COMMON_NAME`, `DAMAGE_TYPE_CODE`, ...) because it was inspected straight from a File Geodatabase. This strongly suggests the R6 file we have is a shapefile *export* of a richer source GDB, and that the export dropped the field-name precision the GDB would have preserved.

`REGION_ID` has 3 distinct values (`6`: 911,911; `5`: 1,157; `1`: 97) despite the filename — **must filter `REGION_ID==6` explicitly.**

Two classification axes: `DCA_CODE`/`DCA_COMMON` (103 species/agent-level codes — causal agent) and `DAMAGE_TYP`/`DAMAGE_T_1` (16 values — impact/severity type, e.g. Mortality dominates at 802,387). See prior inventory pass for the full breakdown; unchanged.

`OBJECTID` confirmed fully unique (913,165/913,165); `DAMAGE_ARE` (truncated `DAMAGE_AREA_ID`) is **not** unique (879,907 distinct, up to 4× repeats) — by design, per the FGDC "Flat Decode" description (multiple agent/host rows can share one spatial damage area).

Geometry invalidity: 53/913,165 (0.006%) — negligible.

**What we likely don't have for R6**: only the polygon "damage areas" layer was provided. R10 (below) shows the source GDB likely also includes a points layer and a surveyed-extent layer — worth requesting the equivalent for R6.

### 4.2 Region 10 — newly found, was zipped and unreported

`AK_Region10_AllYears.gdb.zip` (96 MB, top-level of the project directory) is a zipped File Geodatabase — **this is the ADS R10 data**, previously reported as "not received" because it hadn't been opened. Inspected directly via GDAL's `/vsizip/` virtual filesystem, without extracting.

| Layer | Geometry | Features | CRS | Role |
|---|---|---|---|---|
| `DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10` | MultiPolygon | 151,309 | EPSG:3338 (Alaska Albers) | Reference data — same structure as R6's damage-areas layer, full untruncated field names |
| `DAMAGE_POINTS_FLAT_Allyears_AK_Rgn10` | **Point** | 5,066 | EPSG:3338 | Reference data — point-based damage observations (no polygon area); we have no R6 equivalent |
| `SURVEYED_AREAS_FLAT_AllYears_AK_Rgn10` | MultiPolygon | 6,253 | EPSG:3338 | **Survey extent/coverage** — where surveys actually flew, independent of whether damage was found |

**`SURVEYED_AREAS_FLAT` is a significant find.** It's exactly the kind of layer needed to properly resolve "unlabeled ≠ no change" for ADS: it lets us distinguish "not surveyed this year" from "surveyed, no damage recorded" — something we cannot do for NCCN or for ADS R6 (no equivalent layer received for either). Recommend requesting the equivalent for R6 specifically because of this.

Note: R10 uses **EPSG:3338 (Alaska Albers)**, not the CONUS Albers (~EPSG:5070) that R6 and GLKN use — expected, since it's the appropriate equal-area CRS for Alaska specifically, but means R6 and R10 cannot be directly compared/combined without a reprojection step; each should stay in its own native equal-area CRS for area math within its own region.

Data-quality notes:
- Geometry invalidity: 101/151,309 (0.07%) damage areas, 0/5,066 points, 5/6,253 (0.08%) surveyed areas — all low, consistent with R6.
- `SURVEYED_AREAS_FLAT`'s `START_DATE`/`END_DATE` contain `1899-12-30` as a minimum value for some rows — this is the classic OLE-Automation/Excel epoch-zero artifact for a null date, **not a real 1899 survey**. Treat as a null sentinel.
- `REV_DATE` is entirely empty (6,253/6,253 missing) — a dead column in this export.
- `LEGACY_SURVEY_ID` uses `-1` as a "no legacy ID" sentinel, similar in spirit to NCCN's `Dist_year=0` sentinel.

## 5. Boundary / region datasets (newly inventoried)

Found inside `drive-download-20260923T002841Z-1-001.zip` (23 MB, top-level of the project directory) — unzipped to a scratch location only, for inspection; nothing written into the project tree.

### 5.1 `BugNet_Regions/` — candidate ADS analysis regions, already prepared

Two shapefiles, **not the same kind of boundary** despite the parallel naming:

- **`BugNet_R6_Regions.shp`** — 19 features, EPSG:4326. Fields are **EPA ecoregion** codes/names at Levels I–III (`na_l1name`, `na_l2name`, `na_l3name`, `us_l3code`, ...) plus `STATE` (`OR`/`WA` only — matches ADS Region 6 exactly). This is an actual, already-prepared **ecoregion boundary set for Region 6** — resolves the earlier open question of whether EPA ecoregions would be used for ADS. Ecoregions appear as **repeated multi-part fragments** (e.g. "Coast Range" appears 3× for WA) — would need dissolving by ecoregion code to get one row per ecoregion before using as summarization regions.
- **`BugNet_R10_Regions.shp`** — 20 features, EPSG:4326. Fields are standard USGS Watershed Boundary Dataset attributes (`huc6`, `name`, `areasqkm`, `states`, `tnmid`, `gnis_id`, ...) — this is **HUC6-based**, not ecoregion-based. Confirmed by exact code match to be a **20-of-38 subset** of the full Alaska HUC6 catalog below (0 codes outside that set).

**Takeaway: the intended ADS analysis-region strategy already differs by region** — ecoregions for R6, HUC6 watersheds for R10 — which is a reasonable, defensible split (matches how these two forest-health programs are actually organized), but should be explicitly confirmed with you/Peter/Robert before treating it as final, since neither file's provenance/authorship is documented in the ZIP itself.

### 5.2 `AK_HUC6_boundaries/` — full Alaska HUC6 catalog

38 shapefiles, one feature each, one per named Alaska HUC6 basin (e.g. `AK_HUC6_Tanana_River.shp`, `AK_HUC6_Prince_William_Sound.shp`). CRS: **EPSG:3338** (Alaska Albers — already equal-area, matches ADS R10's native CRS, no reprojection needed for area work if used directly). Same field schema across all 38 files (`huc6`, `name`, `areaacres`, `areasqkm`, `states`, `tnmid`, `gnis_id`, `sourcedata`, `loaddate`, ...). Confirmed to be the superset `BugNet_R10_Regions` was drawn from (§5.1).

### 5.3 `National_Parks.zip` — national NPS unit boundaries (received)

Top-level of the project directory, 26.5 MB, zipped shapefile (`National_Parks.shp` + sidecars, including an FGDC-style `.xml`). Inspected directly from inside the ZIP via GDAL's `/vsizip/` virtual filesystem — not extracted into the project tree, original untouched.

- **Format**: Shapefile (single layer `National_Parks`).
- **CRS**: **EPSG:3857 (Web Mercator)** — a web-display projection, **not equal-area**; must be reprojected before any area calculation (consistent with the CRS discipline established for every other source in this project).
- **Feature count**: 442.
- **Geometry type**: `Polygon`/`MultiPolygon`.
- **Fields (15)**: `OBJECTID, UNIT_CODE, UNIT_NAME, DATE_EDIT, STATE, REGION, UNIT_TYPE, METADATA, PARKNAME, GlobalID, AreaID, IRMARefere, Status, Shape__Are, Shape__Len`.
- **Park/unit name field**: `UNIT_NAME` (full name, e.g. "Mount Rainier National Park") and `PARKNAME` (abbreviated/display form, e.g. "MT RAINIER NP") — both present, redundant, worth keeping both since one may be more convenient for reporting than the other.
- **Park/unit code field**: `UNIT_CODE` — the standard 4-letter NPS code, matches the code convention used directly by NCCN (`Park_code`) and GLKN (`park`, lowercased).
- **Other identifiers**: `OBJECTID` and `GlobalID` are both confirmed **globally unique** (442/442). `AreaID` is present but **not** globally unique. `IRMARefere` (likely "IRMA Reference") points to an NPS IRMA catalog record — not yet followed up. `UNIT_TYPE` (22 distinct values: National Parks, National Historic Sites, National Lakeshores, National Rivers, ...) and `REGION` (NPS administrative region, e.g. `PWR` = Pacific West Region, `MWR` = Midwest Region) are useful cross-checks, not needed as join keys. `Status` is `Official` for 425 rows and **`Legacy` for 17** — see below, one of our target parks is in the Legacy set.
- **`UNIT_CODE` is not globally unique across the whole file**: 429 distinct codes across 442 rows. Nine codes repeat as multiple separate rows/features — `BOST` (6 rows), `GRSA`, `ANIA`, `DENA`, `GAAR`, `GLBA`, `KATM`, `LACL`, `WRST` (2 rows each) — **none of these are our target parks.**

#### 5.3.1 Match results

**All 11 target codes matched, 100%, each as exactly one row** — no code, name, or missing-unit discrepancies found:

| Code | Network | `UNIT_NAME` | `Status` | `DATE_EDIT` | Geometry parts (MultiPolygon) |
|---|---|---|---|---|---|
| MORA | NCCN | Mount Rainier National Park | Official | 2015-11-17 | 6 |
| NOCA | NCCN | North Cascades National Park | Official | 2026-06-05 | 2 |
| OLYM | NCCN | Olympic National Park | Official | 2024-12-17 | **287** |
| LEWI | NCCN | Lewis and Clark National Historical Park | **Legacy** | **2019-09-10** | 7 |
| APIS | GLKN | Apostle Islands National Lakeshore | Official | 2024-10-17 | 22 |
| INDU | GLKN | Indiana Dunes National Park | Official | 2025-06-12 | 24 |
| MISS | GLKN | Mississippi National River and Recreation Area | Official | 2024-12-16 | 1 (simple `Polygon`) |
| SACN | GLKN | Saint Croix National Scenic Riverway | Official | 2025-02-20 | 1 (simple `Polygon`) |
| SLBE | GLKN | Sleeping Bear Dunes National Lakeshore | Official | 2025-06-12 | 6 |
| ISRO | GLKN | Isle Royale National Park | Official | 2023-09-21 | 4 |
| VOYA | GLKN | Voyageurs National Park | Official | 2025-02-04 | 11 |

**Flag: `LEWI` is the one discrepancy worth surfacing.** It's the only one of our 11 target parks marked `Status='Legacy'` rather than `'Official'`, and its `DATE_EDIT` (2019) is markedly older than every other target park's (2023–2026). This doesn't block using it, but the boundary may be out of date relative to the current administrative boundary — worth confirming rather than assuming it's current, especially since LEWI is already the odd one out in the reference data (its own schema vintage, no `Park_code` field, no current-schema NCCN update — see §2).

#### 5.3.2 Multi-row vs. multi-part — what would (not) need to happen before using these as analysis boundaries

**No dissolve across rows is needed for any of the 11 target parks** — each is already exactly one feature/row in this dataset (dissolve would only matter for non-target parks like `BOST`, which aren't in scope here).

However, **every target park's single row is internally a `MultiPolygon`**, and the part count varies enormously — from a simple single `Polygon` (MISS, SACN) up to **287 disjoint parts for OLYM** (Olympic's boundary includes many separate coastal-strip/river-corridor exclaves, consistent with its well-known fragmented shape) and 22–24 parts for the two Great Lakes island/dunes parks (APIS, INDU). This doesn't require a dissolve step (`unary_union`/`.area`/`.intersection` all handle multi-part geometries correctly and automatically sum/operate across all parts of one feature), but it's worth flagging because:
- A 287-part geometry is a reasonable candidate to watch for intersection performance/precision issues once we do the actual region-summary step.
- If any of these "parts" turn out to be genuinely disconnected administrative sub-units rather than just disjoint polygon fragments of one park (e.g., a detached corridor vs. a separate administrative area), that distinction matters for interpretation later — not checked here, flagged for when we actually build the summary.

No intersections or regional summaries were run — this was inspection and identifier-matching only, as requested.

### 5.4 Still missing

- **GLKN HUC12 boundary polygons** — the `HUC_12` attribute exists on 63,448 of 177,153 GLKN disturbance polygons (§3.2), but no boundary geometry for any HUC exists in the GDB. 230 of the 247 distinct codes are standard USGS WBD HUC12 format and can be pulled from the national WBD directly (list in `docs/glkn_huc12_codes.txt`); 17 (mostly Isle Royale) are a non-standard scheme and will need a different source or clarification from Al.

## 6. Cross-source comparison

| Dimension | NCCN | GLKN | ADS R6 | ADS R10 |
|---|---|---|---|---|
| Unique ID | `Patch_name`/`PatchID`, verified unique | `UNIQUE` (verified unique; `uniqID`/`index` are traps) | `OBJECTID` unique; `DAMAGE_ARE` not unique (by design) | `DAMAGE_AREA_ID`/`DAMAGE_POINT_ID`/`SURVEYED_AREA_ID` per layer (uniqueness not yet spot-checked) |
| Region identifier | `Park_code` + `In_Park` (self-declared, vs. study area) | `park` (populated 100%) + `HUC_12` (populated on only 36% of rows; 230/247 codes are standard WBD format, 17 are not; no boundary geometry exists) | `REGION_ID` (self-declared; filename ≠ actual content) | `REGION_ID` (not yet spot-checked for R10; watch for the same pattern seen in R6) |
| Year | `Detect_yr`/`Dist_year` split (V2.1.1) or `AnalysisYr` (legacy) | `year` (1986–2021, fully populated); `analysis_yrs` is a study-period range, not a per-row year | `SURVEY_YEA` (1997–2025) | `SURVEY_YEAR` (1997–2025 areas; 2016–2025 points) |
| Disturbance class | `ChangeType`/`Chnge_type`, ~8–10 categories | `agent_01/02/03`, 10 categories, **only present for 30% of rows** (rest are explicit no-change) | `DCA_CODE`, 103 species/agent codes, + separate `DAMAGE_TYP` axis | Same schema as R6 (untruncated field names) |
| Explicit no-change class? | No | **Yes** — `change_occurred=='false'` | No | Not yet checked for `SURVEYED_AREAS_FLAT` vs. damage areas relationship |
| Extra dimensions | Confidence (1–3) | Land-cover class transition (`start_class_*`/`end_class_*`), land ownership | `PERCENT_*` fields (not yet inspected in detail) | Same as R6 |
| Geometry quality | 0.1–80% invalid (ring self-intersections) | 0.6% invalid (same failure mode) | 0.006% invalid | 0.006–0.08% invalid |
| Scale | Hundreds–~22k features per file | 177k features, 7 parks | 913k features, 1 region | 151k polygons + 5k points + 6k survey-extent, 1 region |
| Native CRS | NAD83 UTM Zone 10N (EPSG:26910) | ESRI:102039 (~EPSG:5070) | ESRI:102039 (~EPSG:5070) | **EPSG:3338** (Alaska Albers — different from R6) |
| Survey-extent layer available? | No | No (but has explicit `change_occurred` instead) | No | **Yes** (`SURVEYED_AREAS_FLAT`) |

**Takeaway:** four sources, four different design philosophies — NCCN labels disturbances only (silence = unlabeled), GLKN labels a sampled set of change candidates as changed-or-not (silence outside the polygon set is still unlabeled, but *within* the polygon set there's a real no-change class), and ADS labels damage only but R10 additionally tracks where surveys actually looked. A shared schema is still realistic, but "unlabeled" needs a source-specific definition, not one blanket rule.

## 7. Missing / ambiguous — needs a decision, not a guess

- Whether NCCN's V2.1.1 supersedes V2B for NOCA/OLYM (strong signal yes; unconfirmed).
- Which NCCN study-area definition (park boundary vs. broader "Protected Areas" area) is the intended summarization unit. **Update 2026-09-24: both candidate AOIs are now in hand and assessed — see §18. Still an open decision, not yet resolved.**
- LEWI's `Star_2km`; why V2.1.1 dropped `Model` from `Event_type`.
- Whether the 30%-populated GLKN `agent_01` (vs. 70% explicit no-change) reflects a systematic sampling design (e.g., a fixed grid of candidate points, only some of which changed) — worth confirming with Al, since it changes how "reference data availability" should be interpreted for GLKN specifically.
- Whether `BugNet_R6_Regions`/`BugNet_R10_Regions` are in fact the intended final ADS analysis regions, or provisional/example files — not documented in the ZIP itself.
- Whether ADS's `DAMAGE_TYP`/GLKN's land-cover-transition fields belong in the common schema as a second dimension, or are out of scope.
- Whether the full ADS R6 GDB (with points/surveyed-extent layers, matching R10) exists and can be obtained.

## 8. Data-quality issues worth investigating further

- NCCN geometry invalidity (up to 80%) and GLKN's smaller but same-shaped invalidity (0.6%) — both ring self-intersections; possibly a shared LandTrendr-pipeline artifact worth asking about once, not per-source.
- ADS `REGION_ID` stray records outside the named region in R6; check the same for R10.
- ADS `DAMAGE_ARE`/`DAMAGE_AREA_ID` non-uniqueness (by design).
- ADS R10 `START_DATE`/`END_DATE` `1899-12-30` null-date artifacts — must be treated as missing, not a real date, in any date-based filtering.
- `BugNet_R6_Regions`' repeated multi-part ecoregion fragments — needs dissolving before use as one-row-per-region boundaries.

## 9. Recommended processed format

Unchanged: **GeoParquet** for anything we produce, **GeoPackage** as a secondary single-file option for QGIS/ArcGIS sharing. The R6-vs-R10 field-name-truncation comparison in §4.1 is now a concrete, in-hand example of exactly the problem shapefile export causes — further reason to avoid it for our own outputs.

## 10. Proposed common schema (draft — still not applied to any raw data)

Same shape as before, now informed by four sources instead of two:

| Common field | NCCN | GLKN | ADS R6/R10 |
|---|---|---|---|
| `source` | `'NCCN'` | `'GLKN'` | `'ADS_R6'`/`'ADS_R10'` |
| `source_feature_id` | `Patch_name`/`PatchID` | `UNIQUE` | `OBJECTID`/`DAMAGE_AREA_ID` |
| `region_id` | `Park_code` (boundary TBD) | `park` (HUC12 boundary TBD) | `REGION_ID`, validated against filename; final boundary TBD (ecoregion for R6, HUC6 for R10, per §5.1) |
| `year` | `Detect_yr`/`Dist_year` (V2.1.1) or `AnalysisYr` (legacy) | `year` | `SURVEY_YEA(R)` |
| `change_class` | mapped from `ChangeType`/`Chnge_type` via documented rename table | mapped from `agent_01` (and possibly `agent_02`/`agent_03` for multi-agent rows) | mapped from `DCA_CODE` via a new crosswalk (TBD) |
| `change_class_original` | raw `ChangeType`/`Chnge_type` | raw `agent_01`/`02`/`03` | raw `DCA_CODE`+`DCA_COMMON` |
| `no_change_flag` | not available (silence = unlabeled) | **`change_occurred=='false'`** — a real field | not available for damage areas; possibly derivable from `SURVEYED_AREAS_FLAT` minus damage areas for R10 |
| confidence/severity | `Confidence` (1–3) | none direct (agent `_perc`/`_cov_remain` come closest) | `DAMAGE_TYP`/`PERCENT_*` |
| geometry | as provided, reproject before area math | as provided (already equal-area) | as provided (already equal-area; R6 and R10 use *different* equal-area CRSs) |

Still explicitly unresolved: how `Alt_type`/`Alt_agent` (NCCN), the multi-agent slots (GLKN), and `DAMAGE_TYP`/land-cover-transition fields fit into or alongside the common schema.

## 11. Suggested next small tasks

1. Confirm whether `BugNet_R6_Regions`/`BugNet_R10_Regions` are the intended final ADS boundaries.
2. Get GLKN HUC12 boundary polygons (NPS park boundaries now received — see §5.3).
3. Ask whether a full ADS R6 GDB (with points/surveyed-extent layers) exists, matching what R10 provided.
4. Confirm with GLKN/Al whether the `agent_01` 30%-populated pattern reflects a systematic sampling design.
5. Confirm with NCCN whether the V2.1.1 files supersede the V2B legacy files.
6. ~~Once one NCCN park + its boundary... are both in hand, build the single real end-to-end POC~~ — **done, see §12 below.**

## 12. NCCN processing (Step 1 of the processing phase — preparation + QA only)

Full detail, per-park numbers, and the exact standardization/repair rules are in `outputs/qa/nccn_processing_report.md`, produced by `src/process_nccn.py`. This section is a pointer + the headline results; do not duplicate the numbers here as they may drift — the QA report and the script are the source of truth.

**Scope:** NCCN only (MORA, NOCA, OLYM current V2.1.1 + LEWI). GLKN and ADS were not touched. This step produced a geometry-repaired, standardized NCCN dataset and a matching 4-park NPS boundary dataset — it explicitly does **not** harmonize classes across sources or compute a final region×year×class summary table.

**Geometry repair verdict:** clean and trustworthy. `make_valid()` applied to all four parks; total area change was floating-point noise (~10⁻⁷ m²) in every case, zero features collapsed into mixed-type geometry, zero empty results, zero individual features exceeded a 5% area-change threshold (12,630 features checked). No stop condition was triggered.

**Boundary-relationship finding (the important one):** the NPS park boundary alone would exclude the large majority of NCCN's own reference data for 3 of 4 parks — **95.5% of MORA's, 89.6% of NOCA's, and 99.1% of LEWI's total attributed area falls outside the park boundary** (only OLYM is mostly inside, at 86.4%). This is a direct, measured confirmation of what §2.3 already documented from the certification forms (monitoring covers the park "and surrounding" USFS Wilderness/study area) — not a new surprise, but now quantified per park rather than described qualitatively. **This means the strict NPS park boundary should not be used as the sole NCCN summarization geography without an explicit decision about the excluded area** — see the QA report's Verdict section for the two options considered (broader documented study-area boundary, not yet acquired; vs. reporting inside/outside separately rather than discarding).

**Outputs**: `data/processed/nccn/repaired/*.parquet`, `data/processed/nccn/nccn_standardized.parquet` (12,630 features), `data/processed/boundaries/nccn_park_boundaries.parquet` (4 features), plus 3 QA CSVs and the full markdown report under `outputs/qa/`. All paths current in `docs/DATA_MANIFEST.md`.

### 12.1 Follow-up: does the reference-data footprint follow HUC watershed boundaries?

Exploratory test, `src/nccn_huc_fit_test.py`, full report `outputs/qa/nccn_huc_fit_test.md`. Both a HUC10 selection (117 features) and, as of 2026-09-23, a HUC12 selection (469 features — arrived zipped, extracted into the same `Prithvi_NCCN/` folder as HUC10, original ZIP preserved) were compared against the standardized reference polygons per park, using the identical method at both resolutions so the results are directly comparable.

**Result: no, at either resolution.** Despite the reference data being ~93–100% areally contained within the union of intersecting HUCs at both HUC10 and HUC12, the footprint's actual edge shows essentially zero alignment with HUC boundary lines — HUC10: 0.000–0.021; **HUC12: 0.001–0.021, i.e. no meaningful improvement over HUC10.** Going to four times the spatial resolution did not reveal a boundary pattern HUC10 was too coarse to show. High coverage was explicitly not treated as sufficient evidence, per the instruction that prompted this test — watersheds tile all land exhaustively, so near-total coverage of any compact area is close to inevitable regardless of how its true boundary was drawn. This is consistent with the certification-form evidence (§2.3) that the monitored extent is an administrative "Protected Areas" study area, not a hydrological one.

**Nesting check** (new): each park's selected HUC12s' implied parent HUC10s (via the standard 10-digit-prefix convention) exactly match that park's independently-selected HUC10 set, for all four parks — the two HUC layers are internally consistent with each other, though this doesn't itself support the watershed hypothesis.

**Possible artificial-selection effect** (cautious interpretation, not a measured fact): going from HUC10 to HUC12, the number of intersecting units roughly triples-to-quadruples per park (e.g. NOCA 27→106) while the aggregate fraction of the selected HUC area that's actually reference data stays low (1.2%–9.1% at HUC12, only modestly higher than HUC10's 0.9%–6.5%, an increase attributable to smaller unit size rather than better fit). This is consistent with, though not proof of, "select by intersection" tracking scattered disturbance locations rather than a real finer-grained boundary.

**Data-quality flag**: NOCA's HUC12 coverage (93.13%) is measurably lower than its HUC10 coverage (99.86%) for the same reference data — unexpected, since HUC12s should tile all land as exhaustively as HUC10. Flagged as a possible gap in the HUC12 export for NOCA specifically, not a finding about the monitoring geography — see the QA report for detail, not resolved here.

## 13. Suggested next small tasks (updated)

**NCCN status (2026-09-23): blocked, waiting on Natasha for the original "Protected Areas" study-area boundary (§12.1/§12 Section 7.2 classification C/D). No further NCCN work planned until that's resolved.** **Update 2026-09-24: received — see §18.** Still not adopted as the analysis subregion pending a decision.

1. Confirm whether `BugNet_R6_Regions`/`BugNet_R10_Regions` are the intended final ADS boundaries.
2. Get GLKN HUC12 boundary polygons (geometry, not just the attribute — needed for any future GLKN HUC10-level map/summary; see §14.4).
3. Ask whether a full ADS R6 GDB (with points/surveyed-extent layers) exists, matching what R10 provided.
4. Confirm with GLKN/Al whether the `agent_01` 30%-populated pattern reflects a systematic sampling design (largely superseded by §14.1's confirmed-vs-rejected explanation, but still worth confirming operationally).
5. Confirm with NCCN whether the V2.1.1 files supersede the V2B legacy files (still pending, independent of the Natasha boundary question).
6. **Resolve the Isle Royale/Voyageurs non-standard HUC12 code scheme** (§14.4) before attempting any HUC10-based GLKN summary — currently excludes 99.9% of ISRO's confirmed disturbance data.

## 14. GLKN processing (preparation + QA only)

Full detail, per-park numbers, and exact standardization/repair rules are in `outputs/qa/glkn_processing_report.md`, produced by `src/process_glkn.py`. This section is a pointer + headline results — see the QA report for the source of truth, not this summary.

**Scope:** GLKN only (all 7 parks). NCCN, ADS R6, ADS R10 not touched. Does not harmonize `change_class` with NCCN's vocabulary, does not compute a final region×year×class summary table, and deliberately does not collapse GLKN's native 9-agent vocabulary into the SLBE report's 6 presentation groups.

### 14.1 Input re-verification (not assumed)

Re-read the GLKN GDB fresh from `data/processed/glkn/LandTrendr.gdb` (a content-identical, `.gdb`-suffixed working copy of the raw file — see `docs/DATA_MANIFEST.md`) and checked every headline number against the prior inventory: total rows (177,153), `true`/`false` counts (53,665 / 123,488), and the 7-park set all matched exactly — no drift since the original inspection. **One real bug was caught in this process**: `change_occurred` is stored as the literal string `"true"`/`"false"`, not a Python boolean — an initial `== True` filter silently returned zero rows before being caught and fixed. A concrete example of why "verify, don't assume" matters even for code you just wrote.

### 14.2 Geometry repair: clean, no stop condition

Same `make_valid()` method as NCCN, applied to the 53,665 **confirmed** (`change_occurred=='true'`) polygons only. Pre-repair invalidity ranged from 0.27% (SLBE) to 4.43% (VOYA) — all ring self-intersections, all well below NCCN's worst rates (up to 80%). Area change after repair: 0.0% across all 7 parks (floating-point noise), zero empty geometries, zero features exceeding a 5% individual-area-change threshold. No stop condition triggered.

### 14.3 Standardized product

`data/processed/glkn/glkn_confirmed_standardized.parquet` — 53,665 features, standardized `source`/`source_dataset`/`source_feature_id` (`UNIQUE`, verified globally unique)/`park_code`/`year`/`change_class` (= native `agent_01`, unharmonized) fields added alongside every original attribute (agent 02/03 + percentages, start/end class fields, `HUC_12`, `uniqID`, ownership, etc.).

### 14.4 HUC geography: a major, quantified gap

**35.78% of confirmed disturbance area (31.58% of polygons) cannot be assigned to a standard-format HUC10**, derived from the first 10 digits of a standard 12-digit `HUC_12` value. This is overwhelmingly concentrated in one park: **99.9% of ISRO's own confirmed rows (16,023 of 16,042) use the non-standard Isle Royale code scheme (`2AA-01` style) and cannot be assigned a HUC10 at all** without separately resolving that scheme — no HUC10 was invented for them. VOYA is affected to a smaller degree (14.8% of its rows, via the Canada-adjacent portion of its footprint). **Practical implication: a naive HUC10-level GLKN summary would silently drop virtually all of Isle Royale's data** unless this is addressed first. Full per-polygon detail: `outputs/qa/glkn_huc10_unassigned.csv`.

### 14.5 Step 6 QA answers (see `outputs/qa/glkn_processing_report.md` for full detail)

- **1.43%** of confirmed rows (769 of 53,665) have more than one agent populated.
- `uniqID` (not the row-level key) repeats: only 46,446 distinct values across 53,665 confirmed rows — **raw polygon counts overstate distinct physical patches by ~15.6%**. Per instruction, polygon counts are not called "event counts" anywhere in this documentation.
- Only 2 of 53,665 confirmed rows share an exact duplicate geometry — negligible double-counting risk.
- The MISS `false`-row `HUC_12` anomaly found in the earlier documentation cross-check **does not affect this product** — 0 of MISS's 4,623 confirmed rows have missing `HUC_12` (checked directly, not assumed).

### 14.6 Not yet done (by design, per instruction)

- No inside/outside-park-boundary analysis (NCCN's Step 5 equivalent) — `data/processed/boundaries/glkn_park_boundaries.parquet` (7 features) was produced for map context only.
- No region×year×class summary table.
- No cross-source class harmonization.

### 14.7 Isle Royale / Voyageurs non-standard HUC codes — investigated, then paused (2026-09-23)

Checked `GLKN_metadata.rtf`, the Kirschbaum SLBE report, and the GDB's `SCH_DATASET`/`SCH_RELEASE`/`SCH_UNIQUEID` tables (confirmed these are pure ESRI internal schema/version-tracking tables — `SCH_DATASET` is empty, `SCH_RELEASE` just records geodatabase version 1.0.0, `SCH_UNIQUEID` holds only null placeholder rows; no code definitions anywhere). None explain the non-standard codes.

**One clean, decisive finding from existing project data (not spatial inference):** every non-standard-code confirmed row, in both ISRO (16,023/16,023) and VOYA (926/926), has `loc_02=='canada'` — a 100% correlation with zero exceptions in either direction; all standard-code rows are `loc_02=='usa'`. `owner_type1` on the non-standard rows is dominated by "Crown Land Unpatented/Patent" (Canadian land-tenure terminology). **This establishes *why* no standard code exists — the USGS Watershed Boundary Dataset (source of the standard 12-digit codes) does not cover Canadian territory — but not what the non-standard codes themselves specifically denote.**

Investigation paused here per instruction, before completing spatial-coherence/hierarchy analysis or attempting to source a Canadian boundary/code dataset — reverse-engineering the exact code semantics is not worth further time right now.

**FINAL ANALYSIS BOUNDARY PENDING: standard US HUC boundaries alone are insufficient for ISRO/VOYA, because attributed data for those two parks extend into Canada**, where no standard-format HUC code (and no HUC boundary geometry, US or Canadian, currently in this project) exists. Any future GLKN analysis-region work for ISRO/VOYA must account for this gap explicitly rather than silently excluding the Canadian portion. **Update 2026-09-24: the newly-received `GLKN_LandTrendr_AOIs` per-park AOI (§18) contains 99.99%/100% of ISRO's and VOYA's existing attributed area respectively**, including their Canadian-portion records — this AOI appears to already have been drawn to include whatever generated the non-standard-HUC rows, without requiring us to source or reconstruct a Canadian boundary ourselves. **Decided 2026-09-24 (§18.4): documented as study-area context, not adopted as a pixel-clipping boundary** — `park_code` remains the subregion identity and Task 1's pixel counts are not AOI-constrained.

## 15. ADS Region 6 processing (simplified approach — ecoregions as landscape containers)

Full detail: `outputs/qa/ads_r6_processing_report.md`, produced by `src/process_ads_r6.py`. Deliberately simpler than the NCCN/GLKN pipelines, per instruction: the existing `BugNet_R6` EPA ecoregion boundaries are used directly as candidate analysis regions (large, already-sensible landscape units), not reconstructed ADS analysis boundaries. **Accepted as-is (97.0% capture), not further optimized.** Goal: identify where useful concentrations of attributed change labels exist, not reproduce ADS's historical study design.

**Primary metrics for ADS (post-review framing, applies to R6 and R10): polygon/record count, attributed area, attributed area by year, years represented, `DCA_CODE` composition, `DAMAGE_TYP` composition, spatial concentration.** Cumulative "fill fraction" (attributed area ÷ static region area) is kept as QA/context only — it can exceed 100% for reasons unrelated to data quality, since ADS spans many years and the same ground can legitimately be attributed in different years.

**Step 1 — Region filter (re-verified):** `REGION_ID` value counts re-confirmed exactly as previously inventoried — 6: 911,911 (99.863%), 5: 1,157, 1: 97. Filtered to `REGION_ID==6` only.

**Step 2 — Ecoregion dissolve:** 19 raw `BugNet_R6` features (state-fragmented) dissolve cleanly by `us_l3code` to **7 EPA Level III ecoregions** (Coast Range, Blue Mountains, Northern Rockies, Cascades, North Cascades, Klamath Mountains/California High North Coast Range, Eastern Cascades Slopes and Foothills).

**Step 3:** light `make_valid()` pass — 53 of 911,911 invalid (0.0058%), all resolved. Not a full QA campaign (not requested, and the rate doesn't warrant one).

**Step 4/5 — Overlay, with two things worth flagging explicitly:**
1. **Performance**: a naive full-geometry intersection over 911,911 rows against the dissolved ecoregion union took >12 minutes and was killed; replaced with a prepared-geometry (`shapely.prepare()`) within/intersects short-circuit strategy — 316 seconds for the full pass, 57 seconds for a corrected per-ecoregion pass (see next point). Documented in the script for future reuse at this data scale.
2. **A real bug caught and fixed**: an initial per-ecoregion area table (crediting each polygon's full area, or its area-within-the-whole-union, to its centroid-assigned ecoregion) produced fill fractions **above 100%** — geometrically impossible if computed correctly against one ecoregion's own area. Root cause: polygons straddling the boundary *between two individual ecoregions* (not the outer union boundary) were having their full area credited to just one. Fixed by intersecting each polygon against its own specifically-assigned ecoregion.

**Result: 97.0% of ADS R6's total area is captured by the union of the 7 ecoregions**; 3.0% falls outside all of them. **Two ecoregions still legitimately exceed 100% fill fraction after the fix** (Eastern Cascades Slopes and Foothills: 117.6%; North Cascades: 109.1%) — verified, not a remaining bug: `SURVEY_YEA` spans 1997–2025 (up to 29 distinct years in one ecoregion), and the same ground can be re-attributed with damage in different years as genuinely separate records. The `DAMAGE_ARE` repeat rate there is only ~1.06× (not the driver); the 29-year cumulative span is. This is real multi-year richness, not double-counting.

**Step 6 — Characterization**, native taxonomy preserved (no harmonization with NCCN/GLKN): causal-agent (`DCA_CODE`/`DCA_COMMON`) and damage-type (`DAMAGE_TYP`/`DAMAGE_T_1`) composition both vary meaningfully across the 7 ecoregions and across years — full tables in `outputs/qa/ads_r6_by_ecoregion_*.csv`.

**Not done, by design:** no cross-source class harmonization, no reconstruction of ADS's historical analysis boundaries, no final reference-data summary statistics.

## 16. ADS Region 10 processing (HUC6 basins as landscape containers)

Full detail: `outputs/qa/ads_r10_processing_report.md`, produced by `src/process_ads_r10.py`. Same simplified approach as R6 (§15), applied to Alaska: the existing `BugNet_R10` HUC6 watershed boundaries are used directly as candidate analysis regions, not reconstructed ADS analysis boundaries. Source is the same national IDS database as R6, this time distributed as a zipped File Geodatabase (`AK_Region10_AllYears.gdb.zip`), extracted to a persistent working copy at `data/processed/ads_r10/AK_Region10_AllYears.gdb` (raw ZIP untouched, mirroring the GLKN `LandTrendr.gdb` precedent). The extraction also surfaced official USDA schema documentation, relocated to `docs/source_docs/ads/IDS_FlatFiles_Readme.pdf`, which confirmed the correct layer (`DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10`) and explained the "pancake" (overlapping-observation) pattern referenced below.

**Primary metrics follow the same post-review framing as R6 (§15): count, area, area-by-year, years, `DCA_CODE`/`DAMAGE_TYPE` composition, spatial concentration — fill fraction is QA/context only, applied here from the start rather than corrected after the fact.**

**Step 1 — Load and verify:** 151,309 features, CRS EPSG:3338. `REGION_ID` is 100% ==10 — no filter step needed (unlike R6's 1,254 stray records). Years: 1997–2025 (29 distinct, matching R6 exactly). Pancake QA: 6,949 rows flagged `OBSERVATION_COUNT=='MULTIPLE'`; 147,821 distinct `DAMAGE_AREA_ID` footprints vs. 151,309 total rows (3,488 "extra" rows) — confirmed as legitimate distinct co-located observations per the official readme, not duplicates. Note: this GDB export has no `OBJECTID` column; `DAMAGE_AREA_ID` is used as the row identifier throughout (an initial script draft assumed `OBJECTID` existed and failed — caught and fixed by direct column inspection).

**Step 2 — HUC6 regions:** 20 raw `BugNet_R10_Regions` features, already one row per HUC6 — **no dissolve needed** (unlike R6's state-fragmented ecoregions). Several basins span Alaska and Canada (Yukon/Tanana/Copper watersheds); not investigated further, consistent with the instruction not to chase boundary reconstruction.

**Step 3:** light `make_valid()` pass — 101 of 151,309 invalid (0.0668%), all resolved.

**Step 4/5 — Overlay:** same prepared-geometry performance pattern as R6, with the per-own-HUC6 area-assignment fix applied from the start (not re-derived). **Result: 90.549% of ADS R10's total area is captured by the union of the 20 HUC6 regions** — lower than R6's 97.0%, with a larger uncaptured share (9.451%, ~7,300 records with zero attributed area inside any region). Reported as-is, not investigated further, per instruction. **No HUC6 exceeds 100% fill fraction** (max: Kenai Peninsula, 31.4%) — unlike R6, where two ecoregions legitimately exceeded 100%; consistent with HUC6 basins being larger watershed-scale units than R6's ecoregions relative to attributed-damage density here.

**Step 6 — Characterization**, native taxonomy preserved (no harmonization with NCCN/GLKN/ADS R6): causal-agent (`DCA_CODE`/`DCA_COMMON_NAME`) and damage-type composition vary strongly across the 20 HUC6 basins, with a clear geographic split — bark beetles (spruce beetle, etc.) dominate the southern/coastal HUC6s (Kenai Peninsula, Susitna River, Copper River), while defoliators/leafminers (aspen leafminer, willow leaf blotchminer, birch leafroller) dominate the northern/interior HUC6s (Tanana River, Porcupine River, Beaver Creek). Full tables in `outputs/qa/ads_r10_by_huc6_*.csv`.

**Not done, by design:** no cross-source class harmonization, no reconstruction of ADS's historical analysis boundaries, no final reference-data summary statistics.

### 16.1 Native DCA class-count reconciliation (2026-09-24) — 71 vs. 68 vs. 67

While preparing polished-report assets, three different "how many native DCA classes does R10 have" numbers turned up across different parts of this project. Reconciled directly from the files, not assumed:

- **71** = `r10["DCA_CODE"].nunique()` on the raw vector data. `DCA_CODE` is the internal numeric code field — **not** the taxonomy field this project reports as `native_class` anywhere else. Checking `(DCA_CODE, DCA_COMMON_NAME)` pairs shows a clean 1:1 mapping except 3 name values that each have 2 codes (`large-spored spruce-Labrador tea rust`: 25013/26017; `spruce broom rust`: 27001/26029; `yellow-cedar decline`: 24001/29001) — almost certainly a mid-survey code renumbering for the same real causal agent, not 3 genuinely distinct classes. **71 should not be used as "the number of native classes" anywhere.**
- **68** = `r10["DCA_COMMON_NAME"].nunique()` on the raw vector data. `DCA_COMMON_NAME` is the correct taxonomy field (matches what `native_class` is built from throughout `src/rasterize_ads_r10.py` and `src/build_pixel_summary_tables.py`). This is the real diversity of the *source* dataset.
- **67** = `ads_r10_dca_subregion_class_summary.csv["native_class"].nunique()` — the rasterized, subregion-assigned Part B universe (what the B.4/B.5 figures already say, e.g. "top 20 of 67 DCA codes"). One class, **"Rhizosphaera needle disease of fir"** (exactly 2 polygons, `huc6_code` null for both — i.e. entirely outside all 20 HUC6 subregions, confirmed **not** a small-polygon pixel-dropout case since both polygons are 5.2 km² and 9.0 km², far above the dropout-check threshold), never appears in any subregion and so has zero rows in the subregion-level summary.

**Which number belongs where:** 68 (`DCA_COMMON_NAME`) is correct when characterizing the raw source dataset's native diversity (Part A). 67 is correct when describing what's actually characterized in this report's quantitative (rasterized, per-subregion) assessment (Part B) — and for report-wide consistency, the compact A.2-style summary table also reports 67, so a reader never sees two different "native class count" numbers for the same source. See `src/export_report_assets.py` for the reconciliation code (asserted at export time, not hand-typed).

## 17. Suggested next small tasks (updated 2026-09-23)

1. ~~Review ADS R6 findings (§15) before deciding on ADS R10.~~ — **done; R10 complete, see §16.**
2. Look more closely at the 3.0% of ADS R6 area (§15) and 9.45% of ADS R10 area (§16) falling outside their respective candidate regions before treating any one region's numbers as complete.
3. GLKN per-park HUC-based analysis boundaries remain deferred (§14.7) — not blocking.
4. NCCN remains blocked on Natasha for the "Protected Areas" boundary (§13) — **received and assessed 2026-09-24, see §18.**
5. Confirm whether `BugNet_R6_Regions`/`BugNet_R10_Regions` are the intended final ADS boundaries — now more load-bearing given both are in active use.
6. **Next major step (per instruction): zoom out and review NCCN + GLKN + ADS R6 + ADS R10 together to decide what cross-source tables/figures are needed for the Objective 1 assessment.** No further source-specific investigation until that review happens. *(This was subsequently completed — see the Objective 1 Task 1 reference-data assessment report, `notebooks/reference_data_assessment.ipynb`.)*
7. **Decide whether to adopt either NCCN AOI generation or the GLKN LandTrendr AOI as the analysis subregion definition** (§18) — assessed but explicitly not yet decided; Objective 1 Task 1's report currently still uses `park_code` for both NCCN and GLKN.

## 18. Natasha's NCCN study-area AOIs + GLKN LandTrendr AOI — received and assessed (2026-09-24)

Two independent authoritative-boundary gaps that were open throughout §12-§14 (NCCN: no agreed containing boundary for every park; GLKN: HUC boundaries investigated but rejected, no boundary geometry for the Canadian portion of ISRO/VOYA) are both addressed by new data received this session. **This section is characterization only — no subregion definition, rasterization, or pixel-summary methodology has been changed as a result.** Full containment numbers: `outputs/qa/nccn_natasha_aoi_containment_qa.csv`, `outputs/qa/glkn_landtrendr_aoi_containment_qa.csv` (produced by `src/qa_new_aoi_containment.py`).

### 18.1 NCCN — two study-area generations, both supplied

Natasha Antonova (`CREATED_BY`/`SOURCE` attributes confirm authorship) supplied both generations of NCCN's original study-area boundary, matching the two-era history already documented in §2.0:

- **Original analysis (1985-2009/10/11): 10-mile buffer.** `LPa01_LEWI_MORA_NOCA_OLYM.shp`, one dissolved polygon per park (LEWI split into north/south units, `PARK_CODE`/`FULL_NAME`/`AREA_SQKM`/`SOURCE`/`CREATED_BY`/`DATE_AOA` fields, "NCCN Landscape Dynamics Monitoring Protocol" as source). Areas are 3-40x each park's core NPS unit size, consistent with a ~10-mile (16.1 km) buffer around park boundaries (LEWI's small, scattered historic-site units show the largest multiple, as expected).
- **Later analysis (1987-2017): "Protected Areas."** `{MORA,NOCA,OLYM}_USFS_NPS_StudyArea.shp` — parcel-level (24-55 features per park), attributed by `Agency`/`Owner`/`Manager` (National Park Service, U.S. Forest Service, and for NOCA also British Columbia and "National Recreation Area" parcels, reflecting the North Cascades complex's Ross Lake/Lake Chelan NRAs and Canadian border). **No LEWI file exists in this set**, consistent with Natasha's description that the later, narrower extent excluded areas NPS did not intend to track private-property change on — LEWI's small, scattered, non-wilderness-adjacent units apparently never received a "Protected Areas" study-area redefinition.

**Which generation our currently-used reference data corresponds to (confirmed from `source_dataset`, not assumed):** MORA/NOCA/OLYM's currently-used files are the `*_1987_2017_V2_1_1_UTM` vintage (later/"Protected Areas" generation); **LEWI's currently-used file is `LEWI_1985_2011_Report_UTM` — the original/10-mile-buffer generation**, matching the absence of a LEWI Protected Areas file. LEWI is on a different generation than the other three parks, not an oversight — the raw data itself has no later-vintage LEWI file to use instead (§2.1/§7).

**Containment (`outputs/qa/nccn_natasha_aoi_containment_qa.csv`):**

| Park | Attributed area (ha) | % area in LPa01 (10-mi buffer) | % area in Protected Areas |
|---|---|---|---|
| MORA | 23,549.5 | 99.54% | 88.22% |
| NOCA | 48,536.2 | 88.24% | 98.12% |
| OLYM | 7,923.3 | 100.00% | 97.81% |
| LEWI | 23,360.4 | 99.94% | n/a (no file) |

Polygon-count intersection is 100% for every park against both AOIs except NOCA-vs-LPa01 (91.74%). MORA and OLYM fit their generation's AOI closely (area-in-matching-AOI ≥97.8%, with the small remainder plausibly attributable to the 2017-fire patches the documentation says are "deliberately not clipped to the study area," §2.3/§data_inventory.md line 74). **NOCA is the one anomaly**: its area-in-LPa01 (88.24%) is measurably *lower* than its area-in-Protected-Areas (98.12%) — i.e. the narrower, later-era boundary contains NOCA's data better than the wider, earlier-era buffer does. **Resolved in §18.3**: this is a cross-generation comparison artifact (476 of 518 non-contained polygons are genuinely, not just marginally, outside LPa01 by up to 13.5 km) caused by NOCA's Protected Areas AOI being only 96.34% nested inside its LPa01 AOI (vs. 100% for MORA/OLYM) — not a data-quality problem, and it disappears when NOCA V2.1.1 is checked only against its own proper-generation AOI.

Both AOI shapefiles have one ring-self-intersection geometry each (NOCA's "Glacier Peak Wilderness" USFS Wilderness parcel; trivially fixed with `buffer(0)` for the containment check, raw file itself untouched).

### 18.2 GLKN — LandTrendr per-park analysis-area AOI

`GLKN_LandTrendr_AOIs.shp`: 9 features (`park`, `Shape_Leng`, `Shape_Area`, `acres`), one per GLKN network unit — the 7 `park_code` values already used in this project (APIS, INDU, ISRO, MISS, SACN, SLBE, VOYA), plus **PIRO (Pictured Rocks National Lakeshore) and GRPO (Grand Portage National Monument)**, which have no reference disturbance data in `glkn_confirmed_standardized.parquet` (i.e. GLKN monitors 9 units; our reference dataset only has confirmed disturbance rows for 7 of them). Areas are 1.9-330x each park's core NPS unit size — this is not a park-boundary layer.

**This is confirmed authoritative, not inferred from area alone.** The shapefile's embedded FGDC/Esri lineage records its build history directly: individual `{PARK}_LandTrendr_analysis_area` shapefiles created/appended 2011 (APIS) through 2022 (SACN), progressively merged into `LandTrendr_analysis_areas_by_park`, exported to the delivered file 2026-04-22. This is literally the AOI the GLKN LandTrendr change-detection analysis was run within per park — i.e., the boundary that generated the reference disturbance dataset in the first place, not a boundary being tested as a candidate summarization unit after the fact.

**Containment (`outputs/qa/glkn_landtrendr_aoi_containment_qa.csv`): 99.99-100% of existing attributed area and 100% of polygon count falls inside the matching park's AOI, for all 7 parks with reference data** — including ISRO (99.99% area) and VOYA (100% area), the two parks whose non-standard-HUC-code Canadian-portion records (§14.7) could not be assigned any HUC boundary at all. This AOI appears to already encompass whatever generated those Canadian-portion rows, without our needing to source or reconstruct a Canadian boundary dataset ourselves. One ring-self-intersection (ISRO's 588-part multipolygon) was trivially fixed with `buffer(0)` for the check; raw file untouched. `apis`/`sacn` touch at a shared vertex (0 area); `miss`/`sacn` have a small (~140 ha) real overlap — negligible relative to either park's total attributed area, not investigated further.

### 18.3 Verified per-dataset generation mapping (2026-09-24 follow-up)

Natasha's expected mapping (MORA/NOCA/OLYM V2.1.1 -> Protected Areas; LEWI's older dataset -> the original 10-mile-buffer AOI) was **verified directly from the files, not assumed** — `src/qa_nccn_aoi_generation_mapping.py`, `outputs/qa/nccn_aoi_generation_mapping_qa.csv` (per-dataset summary) and `outputs/qa/nccn_aoi_generation_mapping_outside_polygons.csv` (every not-fully-contained polygon, with a corrected metric — see caveat below).

**Confirmed correct for all 4 currently-used Task 1 datasets**, each checked only against its own proper-generation AOI:

| Dataset (source_dataset) | Park | Years | Generation | Proper AOI | % area in AOI | % count in AOI | Polygons not fully within | ...with a genuinely-outside centroid |
|---|---|---|---|---|---|---|---|---|
| `MORA_1987_2017_V2_1_1_UTM` | MORA | 1987-2017 | later (Protected Areas) | MORA Protected Areas | 88.22% | 100.00% | 145 | **0** |
| `NOCA_1987_2017_V2_1_1_UTM` | NOCA | 1987-2017 | later (Protected Areas) | NOCA Protected Areas | 98.12% | 100.00% | 223 | **1** (4.2 m) |
| `OLYM_1987_2017_V2_1_1_UTM` | OLYM | 1987-2017 | later (Protected Areas) | OLYM Protected Areas | 97.81% | 100.00% | 73 | **0** |
| `LEWI_1985_2011_Report_UTM` | LEWI | 1985-2011 | original (10-mi buffer) | LPa01 (LEWI N+S union) | 99.94% | 100.00% | 120 | **1** (19.4 m) |

Every "not fully within" polygon above is a **boundary-straddling event polygon** (a fire, defoliation, or riparian-change patch whose footprint legitimately crosses a parcel/buffer edge — dominant `change_class` values are Defoliation/Fire/Riparian Change/Clearing, exactly the classes expected not to respect ownership boundaries), not evidence of a wrong-generation pairing: centroids sit inside the AOI in 900 of 902 cases, and the 2 exceptions are 4.2 m and 19.4 m outside — floating-point/digitizing-precision scale, not real displacement.

**The NOCA anomaly is resolved, and disappears once the proper generation pairing is used.** The earlier (§18.1) cross-generation check — comparing NOCA V2.1.1 against the *wrong*-generation LPa01 AOI — showed only 88.24% area containment with **476 of 518 non-contained polygons having a genuinely-outside centroid, up to 13.5 km away**: a real, substantial mismatch, not a rounding artifact. That mismatch vanishes (down to the single 4.2 m case above) once NOCA V2.1.1 is checked against its own proper AOI (Protected Areas, 98.12% area, 1 negligible outlier). Root cause: Protected Areas is only 96.34% geometrically nested inside LPa01 for NOCA specifically (100% nested for MORA and OLYM) — North Cascades' more spatially complex protected-lands footprint (Ross Lake/Lake Chelan NRA parcels, adjacency to the Canadian border) extends beyond the 2013-drawn 10-mile buffer in places that MORA's and OLYM's simpler, more compact footprints don't. The anomaly was a cross-generation comparison artifact, not a NCCN data-quality problem.

**Where the superseded V2B/V2B-2 legacy datasets fit** (loaded directly from `data/raw/nccn/`, excluded from Task 1 per instruction): checked against both AOIs for confirmation —

| Dataset | Years | % area in LPa01 (proper) | % area in Protected Areas (wrong) | Genuinely-outside centroids vs. Protected Areas |
|---|---|---|---|---|
| `NOCA_1985_2009_V2B_UTM` | 1985-2009 | **100.00%** | 35.17% | 6,508 of 9,980 (up to 39.1 km) |
| `OLYM_1985_2010_V2B_UTM` | 1985-2010 | **100.00%** | 2.78% | 20,877 of 22,553 (up to 29.0 km) |

Both legacy files fit their proper (original/10-mile-buffer) generation at essentially 100% area with zero genuine outliers, and are overwhelmingly, genuinely outside Protected Areas — an unambiguous confirmation that V2B/V2B-2 belong to the original generation, not the one MORA/NOCA/OLYM's current V2.1.1 files use. This corroborates the V2.1.1-supersedes-V2B hypothesis from §7/§12 from a completely independent angle (AOI generation, not just file-naming/date evidence) and reconfirms they should stay excluded from Task 1's quantitative results.

**Caveat on method:** an initial pass used Hausdorff distance between each polygon's outside-portion and the AOI as a "how far outside" metric, and produced spurious tens-of-km values for polygons a direct centroid check confirmed were 0 m outside — a GEOS artifact on the difference() of complex multi-part (24-55 parcel) unioned geometries, not a real excursion. The corrected metric (used throughout this section) is centroid-distance-to-AOI plus % of each polygon's own area outside; see the docstring in `src/qa_nccn_aoi_generation_mapping.py` for detail. Don't reintroduce a Hausdorff-based distance for this kind of check without re-verifying against a direct centroid spot check first.

### 18.4 What is and isn't resolved

**Resolved (verified from the actual files, not assumed):**
- What generation each currently-used NCCN reference dataset belongs to, and which AOI it should be checked against — confirmed exactly as Natasha described (§18.3).
- Whether the GLKN LandTrendr AOI is genuinely authoritative (yes, confirmed by embedded lineage) and whether it represents all 7 in-use `park_code` values (yes) plus 2 more with no reference data (PIRO, GRPO).
- Whether NCCN/GLKN attributed polygons fall well inside their respective new, PROPERLY-PAIRED AOIs (yes: 88-100% area for NCCN's 4 current datasets, each against its own generation; 99.99-100% for GLKN).
- The NOCA LPa01-vs-Protected-Areas anomaly — resolved; it was a cross-generation comparison artifact (§18.3), not a data problem, and disappears under proper pairing.
- Where the superseded V2B/V2B-2 datasets fit (original generation, confirmed independently via AOI containment) — correctly excluded from Task 1.
- **Whether to AOI-clip Task 1's pixel counts — decided 2026-09-24: no.** Before deciding, the methodological choice was quantified: an AOI-constrained rasterization (same grid, same pixel-center rule, `src/qa_aoi_constrained_pixel_comparison.py`) was compared against the existing source-assigned counts for every NCCN/GLKN subregion (`outputs/qa/nccn_glkn_aoi_constraint_comparison_subregion.csv`, `..._class.csv`). GLKN is negligible either way (≤0.01% at the subregion level). NCCN's one meaningful case, MORA (-11.79% attributed pixel-years if AOI-clipped), is dominated by a single, already-documented, deliberate exception (the 2017 fire event, -14.4% of MORA's Fire-class pixels specifically) that NCCN's own methodology intentionally did not clip to the study boundary. **Decision: Task 1 retains the complete published attributed-polygon geometry for both sources; the AOIs are documented as study-area/provenance context (notebook Part B.1, Appendix A.6/B.6), not used to constrain pixel membership.** Each AOI's own 30 m reference-grid pixel count/area is also now documented (`outputs/qa/nccn_glkn_aoi_total_pixel_counts.csv`) as a study-area denominator for context only — it is not used as the spatial-prevalence denominator, and unlabeled AOI pixels are not interpreted as no-change.
- Whether adopting either boundary would change any Part B (30 m reference-grid) rasterization, spatial-prevalence, or pixel-summary result currently in the Objective 1 Task 1 report — **tested and decided against**: see the AOI-clipping comparison above. The existing spatial-prevalence calculation (annual: unique attributed pixels; all-years: attributed pixel-years) is unchanged.

**Not resolved / explicitly out of scope:**
- No cross-source class harmonization, no diversity scoring, no subregion ranking or focal-area selection — unaffected by this AOI work, per standing instruction.
