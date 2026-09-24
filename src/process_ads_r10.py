"""
ADS Region 10 (Alaska) processing: preparation + QA only, mirroring the
simplified ADS R6 approach (src/process_ads_r6.py) -- existing BugNet R10
HUC6 boundaries used directly as candidate analysis regions, not a
reconstruction of ADS's historical analysis boundaries.

Purpose: characterize where useful concentrations of attributed change
labels exist, what types they contain, and over what years -- to help
identify focal landscapes for the later Prithvi work. Not a final summary.

Scope: ADS R10 only. Does not touch NCCN, GLKN, or ADS R6. Does not
harmonize the native ADS taxonomy (DCA_CODE/DAMAGE_TYPE) with any other
source's class vocabulary.

Primary metrics (per the R6 methodological review): attributed
record/polygon count, attributed area, attributed area by year, years
represented, DCA_CODE composition, DAMAGE_TYPE composition, spatial
concentration. Cumulative "fill fraction" (area / region area) is computed
only as QA/context, not emphasized, since ADS spans many years and the same
ground can be legitimately re-attributed across different years.

Source layer: `DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10` -- confirmed the right
choice per the official USDA "IDS_FlatFiles_Readme.pdf" found alongside the
raw R10 GDB and relocated to docs/source_docs/ads/ (this documentation also
retroactively explains ADS R6's structure, since both come from the same
national IDS database). That readme explicitly documents "pancake" features:
overlapping observations at one location get identical geometry but
different OBSERVATION_ID/OBJECTID, flagged via OBSERVATION_COUNT=='MULTIPLE'
-- "care must be taken to account for the possibility of multiple counting
during any data summarizing." Checked directly below, reported as QA, not
silently ignored or "fixed" (they're legitimate distinct observations, not
duplicates to drop).

Input (raw, read-only): data/raw/ads/r10/AK_Region10_AllYears.gdb.zip. A
persistent extracted working copy (pure unzip, zero content change) lives at
data/processed/ads_r10/AK_Region10_AllYears.gdb for this and future R10
processing to read from (documented in docs/DATA_MANIFEST.md).

Never writes to data/raw/.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"

GDB_PATH = PROCESSED / "ads_r10" / "AK_Region10_AllYears.gdb"
LAYER = "DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10"
BUGNET_R10_PATH = RAW / "boundaries" / "ads_r10" / "BugNet_R10_Regions.shp"


def log(msg=""):
    print(msg)


# -----------------------------------------------------------------------------
# Step 1: load + verify REGION_ID + pancake/multiple-observation QA
# -----------------------------------------------------------------------------

def step1_load_and_verify():
    log("=" * 70)
    log("STEP 1: LOAD DAMAGE_AREAS_FLAT_AllYears_AK_Rgn10 + VERIFY")
    log("=" * 70)

    gdf = gpd.read_file(GDB_PATH, layer=LAYER)
    log(f"Feature count: {len(gdf)}")
    log(f"CRS: {gdf.crs}")

    vc = gdf["REGION_ID"].value_counts()
    log(f"REGION_ID value counts: {dict(vc)}")
    if set(vc.index) == {10}:
        log("100% REGION_ID==10 -- no filtering needed (unlike R6, which had stray non-6 records).")
    else:
        n_before = len(gdf)
        gdf = gdf[gdf["REGION_ID"] == 10].copy()
        log(f"Filtered to REGION_ID==10: {len(gdf)} of {n_before} retained.")

    log(f"\nAREA_TYPE value counts: {dict(gdf['AREA_TYPE'].value_counts(dropna=False))}")
    log(f"Years represented: {int(gdf['SURVEY_YEAR'].min())}-{int(gdf['SURVEY_YEAR'].max())} "
        f"({gdf['SURVEY_YEAR'].nunique()} distinct years)")

    # Pancake / multiple-observation QA, per the official readme's explicit warning.
    obs_count_vc = gdf["OBSERVATION_COUNT"].value_counts(dropna=False)
    log(f"\nOBSERVATION_COUNT value counts: {dict(obs_count_vc)}")
    n_multi = int(obs_count_vc.get("MULTIPLE", 0))
    n_distinct_footprint = gdf["DAMAGE_AREA_ID"].nunique()
    log(f"Distinct DAMAGE_AREA_ID (footprint) values: {n_distinct_footprint} of {len(gdf)} rows")
    log(f"-> {len(gdf) - n_distinct_footprint} 'extra' rows beyond one-per-footprint, consistent with "
        f"{n_multi} rows flagged OBSERVATION_COUNT=='MULTIPLE' (overlapping observations at the same "
        f"footprint, confirmed by the official readme -- NOT duplicate/erroneous records; each is a "
        f"distinct observation, e.g. a different host/agent at the same location. Retained as-is; "
        f"flagged here so downstream area/count sums are interpreted correctly.)")

    return gdf


# -----------------------------------------------------------------------------
# Step 2: inspect BugNet R10 HUC6 regions (no dissolve needed -- verified)
# -----------------------------------------------------------------------------

def step2_huc6_regions(working_crs):
    log("\n" + "=" * 70)
    log("STEP 2: BUGNET R10 HUC6 REGIONS")
    log("=" * 70)

    gdf = gpd.read_file(BUGNET_R10_PATH)
    log(f"Raw feature count: {len(gdf)}, CRS: {gdf.crs}")
    log(f"Distinct huc6 values: {gdf['huc6'].nunique()}")

    if len(gdf) == gdf["huc6"].nunique():
        log("Already one row per HUC6 -- no dissolve needed (unlike R6's state-fragmented ecoregions).")
    else:
        log(f"WARNING: {len(gdf)} rows but only {gdf['huc6'].nunique()} distinct huc6 -- dissolving.")
        gdf = gdf.dissolve(by="huc6", aggfunc={"name": "first", "states": "first"}).reset_index()

    log(gdf[["huc6", "name", "states"]].to_string())

    gdf = gdf.to_crs(working_crs)
    gdf["region_area_m2"] = gdf.geometry.area
    gdf["n_parts"] = gdf.geometry.apply(lambda g: len(g.geoms) if g.geom_type == "MultiPolygon" else 1)

    out_path = PROCESSED / "boundaries" / "ads_r10_huc6.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out_path)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)}")

    return gdf


# -----------------------------------------------------------------------------
# Step 3: light geometry fix
# -----------------------------------------------------------------------------

def step3_light_geometry_fix(gdf):
    log("\n" + "=" * 70)
    log("STEP 3: LIGHT GEOMETRY VALIDITY CHECK")
    log("=" * 70)

    n_invalid = int((~gdf.geometry.is_valid).sum())
    log(f"Invalid geometries: {n_invalid} of {len(gdf)} ({100*n_invalid/len(gdf):.4f}%)")
    if n_invalid > 0:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.make_valid()
        log(f"After make_valid(): {int((~gdf.geometry.is_valid).sum())} still invalid")
    else:
        log("Nothing to fix.")
    return gdf


# -----------------------------------------------------------------------------
# Step 4/5: overlay -- capture stats + per-HUC6 area (own-region intersection,
# not union -- avoids the >100%-fill-fraction bug found and fixed for R6)
# -----------------------------------------------------------------------------

def step4_5_overlay(gdf, huc6):
    log("\n" + "=" * 70)
    log("STEP 4/5: OVERLAY -- CAPTURE STATS + PER-HUC6 ASSIGNMENT")
    log("=" * 70)

    gdf = gdf.copy()
    gdf["area_m2"] = gdf.geometry.area
    total_area = float(gdf["area_m2"].sum())
    total_count = len(gdf)
    log(f"Total ADS R10 records: {total_count:,}, total area: {total_area:,.0f} m2 ({total_area/1e4:,.0f} ha)")

    huc6_union = huc6.geometry.union_all()
    shapely.prepare(huc6_union)
    geoms = gdf.geometry.values
    is_within = shapely.within(geoms, huc6_union)
    is_intersecting = shapely.intersects(geoms, huc6_union)
    straddling = is_intersecting & ~is_within

    area_in = np.where(is_within, gdf["area_m2"].values, 0.0)
    if straddling.sum():
        area_in[straddling] = shapely.area(shapely.intersection(geoms[straddling], huc6_union))
    gdf["area_in_huc6_union_m2"] = area_in

    captured_area = float(gdf["area_in_huc6_union_m2"].sum())
    log(f"within={int(is_within.sum()):,}  straddling={int(straddling.sum()):,}  "
        f"no_intersect={int((~is_intersecting).sum()):,}")
    log(f"Area captured by union of 20 HUC6 regions: {captured_area:,.0f} m2 "
        f"({100*captured_area/total_area:.3f}%)")
    log(f"Area outside all 20 HUC6 regions: {total_area-captured_area:,.0f} m2 "
        f"({100*(total_area-captured_area)/total_area:.3f}%)")

    # Assign each record to its primary HUC6 via centroid (for characterization),
    # then compute the precise per-own-HUC6 intersection area (not union area --
    # avoids the R6 >100%-fill-fraction bug).
    centroids = gpd.GeoDataFrame(geometry=gdf.geometry.centroid, crs=gdf.crs)
    joined = gpd.sjoin(centroids, huc6[["huc6", "name", "geometry"]], how="left", predicate="within")
    gdf["huc6_code"] = joined["huc6"].values
    gdf["huc6_name"] = joined["name"].values

    gdf["area_in_own_huc6_m2"] = np.nan
    huc_geom = dict(zip(huc6["huc6"], huc6.geometry))
    for code, geom in huc_geom.items():
        shapely.prepare(geom)
        mask = (gdf["huc6_code"] == code).values
        if not mask.any():
            continue
        sub_geoms = gdf.geometry.values[mask]
        sub_within = shapely.within(sub_geoms, geom)
        sub_area = np.where(sub_within, gdf["area_m2"].values[mask], 0.0)
        sub_straddle = ~sub_within
        if sub_straddle.sum():
            sub_area[sub_straddle] = shapely.area(shapely.intersection(sub_geoms[sub_straddle], geom))
        gdf.loc[mask, "area_in_own_huc6_m2"] = sub_area

    per_huc = gdf.groupby(["huc6_code", "huc6_name"], dropna=False).agg(
        record_count=("DAMAGE_AREA_ID", "count"),
        attributed_area_m2=("area_in_own_huc6_m2", "sum"),
    ).reset_index()
    per_huc = per_huc.merge(huc6[["huc6", "region_area_m2"]], left_on="huc6_code", right_on="huc6", how="left")
    per_huc["fill_fraction_pct"] = round(100 * per_huc["attributed_area_m2"] / per_huc["region_area_m2"], 4)
    per_huc = per_huc.sort_values("attributed_area_m2", ascending=False)

    log("\nPer-HUC6 capture summary (record count + area are the primary metrics; "
        "fill_fraction_pct is QA/context only -- see module docstring):")
    log(per_huc[["huc6_code", "huc6_name", "record_count", "attributed_area_m2", "fill_fraction_pct"]].to_string(index=False))

    out_path = QA_DIR / "ads_r10_huc6_capture.csv"
    per_huc.to_csv(out_path, index=False)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)}")

    return gdf, per_huc


# -----------------------------------------------------------------------------
# Step 6: characterize by HUC6 x year x DCA_CODE x DAMAGE_TYPE
# -----------------------------------------------------------------------------

def step6_characterize(gdf):
    log("\n" + "=" * 70)
    log("STEP 6: CHARACTERIZE BY HUC6 x YEAR x DCA_CODE x DAMAGE_TYPE")
    log("=" * 70)
    log("(native ADS taxonomy preserved verbatim -- no harmonization with NCCN/GLKN/ADS R6)")

    by_year = gdf.groupby(["huc6_code", "SURVEY_YEAR"]).agg(
        record_count=("DAMAGE_AREA_ID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_year.to_csv(QA_DIR / "ads_r10_by_huc6_year.csv", index=False)
    log(f"\nWrote outputs/qa/ads_r10_by_huc6_year.csv ({len(by_year)} rows)")

    by_dca = gdf.groupby(["huc6_code", "DCA_CODE", "DCA_COMMON_NAME"]).agg(
        record_count=("DAMAGE_AREA_ID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_dca.to_csv(QA_DIR / "ads_r10_by_huc6_dca.csv", index=False)
    log(f"Wrote outputs/qa/ads_r10_by_huc6_dca.csv ({len(by_dca)} rows)")

    by_damage_typ = gdf.groupby(["huc6_code", "DAMAGE_TYPE_CODE", "DAMAGE_TYPE"]).agg(
        record_count=("DAMAGE_AREA_ID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_damage_typ.to_csv(QA_DIR / "ads_r10_by_huc6_damage_type.csv", index=False)
    log(f"Wrote outputs/qa/ads_r10_by_huc6_damage_type.csv ({len(by_damage_typ)} rows)")

    log("\nTop 5 DCA_COMMON_NAME per HUC6 (by area):")
    for code, grp in by_dca.groupby("huc6_code"):
        top5 = grp.sort_values("area_m2", ascending=False).head(5)
        log(f"  {code}: " + "; ".join(f"{r.DCA_COMMON_NAME} ({r.area_m2/1e4:,.0f} ha)" for r in top5.itertuples()))

    return by_year, by_dca, by_damage_typ


def main():
    (PROCESSED / "ads_r10").mkdir(parents=True, exist_ok=True)
    (PROCESSED / "boundaries").mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    gdf = step1_load_and_verify()
    huc6 = step2_huc6_regions(gdf.crs)
    gdf = step3_light_geometry_fix(gdf)
    gdf, per_huc = step4_5_overlay(gdf, huc6)
    step6_characterize(gdf)

    out_path = PROCESSED / "ads_r10" / "ads_r10_with_huc6.parquet"
    gdf.to_parquet(out_path)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)} ({len(gdf)} features)")

    log("\n" + "=" * 70)
    log("DONE")
    log("=" * 70)


if __name__ == "__main__":
    main()
