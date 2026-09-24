"""
ADS Region 6 processing: preparation + QA only, using the simplified
"ecoregions as landscape containers" approach (not a NCCN/GLKN-style
geometry-repair-and-standardize pipeline, per instruction -- this is
deliberately leaner).

Purpose: not to reconstruct ADS's historical analysis boundaries, but to
answer "where do we have useful concentrations of attributed change labels,
what types are present, and over what years" -- using the existing BugNet R6
EPA ecoregion boundaries as candidate analysis regions (already sensible,
large landscape units; dissolved to one polygon per ecoregion, not per
state-fragment).

Scope: ADS R6 only. Does not touch NCCN, GLKN, or ADS R10. Does not
harmonize the native ADS taxonomy (DCA_CODE/DAMAGE_TYP) with NCCN's or
GLKN's class vocabularies.

Steps:
    1. Filter raw ADS R6 to REGION_ID == 6 (the file also contains a few
       stray Region 1/5 records -- verified again here, not assumed).
    2. Inspect BugNet R6 ecoregion boundaries; dissolve the 19 state-
       fragmented rows down to one polygon per distinct EPA Level III
       ecoregion (us_l3code), so "Coast Range" (OR + WA) is one region,
       not two.
    3. Light geometry validity fix (make_valid()) on the ADS polygons
       before overlay -- ADS R6 was already found to be ~99.994% valid in
       the original inspection, so this is a light touch, not a full QA
       campaign like NCCN/GLKN got.
    4. Overlay: how much ADS R6 area/how many polygons fall inside the
       union of the 7 dissolved ecoregions vs. outside.
    5. Report capture stats per ecoregion (area captured, region's own
       total area, "fill fraction" -- how much of the ecoregion's own
       area is actually attributed damage, for landscape-coherence context).
    6. Characterize by ecoregion x year, ecoregion x DCA_CODE, ecoregion x
       DAMAGE_TYP -- native taxonomy preserved, not harmonized.

Never writes to data/raw/.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"

ADS_R6_PATH = RAW / "ads" / "r6" / "ADS_R6_Damage_allyears.shp"
BUGNET_R6_PATH = RAW / "boundaries" / "ads_r6" / "BugNet_R6_Regions.shp"


def log(msg=""):
    print(msg)


# -----------------------------------------------------------------------------
# Step 1: filter to REGION_ID == 6
# -----------------------------------------------------------------------------

def step1_filter_region6():
    log("=" * 70)
    log("STEP 1: FILTER ADS R6 TO REGION_ID == 6")
    log("=" * 70)

    gdf = gpd.read_file(ADS_R6_PATH)
    log(f"Raw feature count: {len(gdf)}")
    log(f"CRS: {gdf.crs}")

    vc = gdf["REGION_ID"].value_counts().sort_index()
    log(f"REGION_ID value counts (before filter): {dict(vc)}")

    filter_qa = vc.reset_index()
    filter_qa.columns = ["REGION_ID", "feature_count"]
    filter_qa["pct"] = round(100 * filter_qa["feature_count"] / len(gdf), 4)
    filter_qa.to_csv(QA_DIR / "ads_r6_region_filter_qa.csv", index=False)

    r6 = gdf[gdf["REGION_ID"] == 6].copy()
    log(f"After filtering to REGION_ID==6: {len(r6)} of {len(gdf)} "
        f"({100*len(r6)/len(gdf):.3f}%) retained; "
        f"{len(gdf)-len(r6)} stray non-R6 records dropped from this analysis "
        f"(NOT removed from raw data).")

    return r6


# -----------------------------------------------------------------------------
# Step 2: inspect + dissolve BugNet R6 ecoregions
# -----------------------------------------------------------------------------

def step2_dissolve_ecoregions(working_crs):
    log("\n" + "=" * 70)
    log("STEP 2: BUGNET R6 ECOREGIONS -- INSPECT + DISSOLVE")
    log("=" * 70)

    gdf = gpd.read_file(BUGNET_R6_PATH)
    log(f"Raw feature count: {len(gdf)}, CRS: {gdf.crs}")
    log(f"Distinct us_l3code values (true ecoregion identity, state-independent): "
        f"{gdf['us_l3code'].nunique()}")
    log(gdf[["us_l3code", "us_l3name", "STATE"]].to_string())

    gdf = gdf.to_crs(working_crs)
    dissolved = gdf.dissolve(by="us_l3code", aggfunc={"us_l3name": "first", "na_l1name": "first"}).reset_index()
    dissolved["region_area_m2"] = dissolved.geometry.area
    dissolved["n_parts"] = dissolved.geometry.apply(
        lambda g: len(g.geoms) if g.geom_type == "MultiPolygon" else 1
    )

    log(f"\nDissolved to {len(dissolved)} regions (one per EPA Level III ecoregion, "
        f"state fragmentation removed):")
    log(dissolved[["us_l3code", "us_l3name", "n_parts", "region_area_m2"]].to_string())

    out_path = PROCESSED / "boundaries" / "ads_r6_ecoregions.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dissolved.to_parquet(out_path)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)}")

    return dissolved


# -----------------------------------------------------------------------------
# Step 3: light geometry fix before overlay
# -----------------------------------------------------------------------------

def step3_light_geometry_fix(r6):
    log("\n" + "=" * 70)
    log("STEP 3: LIGHT GEOMETRY VALIDITY CHECK (ADS R6 -- already ~99.994% valid)")
    log("=" * 70)

    n_invalid = int((~r6.geometry.is_valid).sum())
    log(f"Invalid geometries: {n_invalid} of {len(r6)} ({100*n_invalid/len(r6):.4f}%)")

    if n_invalid > 0:
        r6 = r6.copy()
        r6["geometry"] = r6.geometry.make_valid()
        n_still_invalid = int((~r6.geometry.is_valid).sum())
        log(f"After make_valid(): {n_still_invalid} still invalid")
    else:
        log("Nothing to fix.")

    return r6


# -----------------------------------------------------------------------------
# Step 4/5: overlay + capture stats
# -----------------------------------------------------------------------------

def step4_5_overlay(r6, ecoregions):
    import shapely
    import numpy as np
    import time

    log("\n" + "=" * 70)
    log("STEP 4/5: OVERLAY -- HOW MUCH ADS R6 DATA DO THE ECOREGIONS CAPTURE?")
    log("=" * 70)

    total_area = float(r6.geometry.area.sum())
    total_count = len(r6)
    log(f"Total ADS R6 (REGION_ID==6) polygons: {total_count:,}, total area: {total_area:,.0f} m2 "
        f"({total_area/1e4:,.0f} ha)")

    # Performance note: a naive `r6.geometry.intersection(ecoregion_union).area`
    # over ~912k rows against one large, highly-detailed dissolved ecoregion
    # union took >12 minutes and was killed. Fixed with a three-tier strategy
    # using an explicitly prepared geometry (shapely.prepare -- built for
    # exactly this "test many geometries against one fixed complex geometry"
    # pattern) and boolean predicates (which can short-circuit) instead of
    # full intersection construction for the vast majority of rows:
    #   1. within(union)     -> full polygon area counts, no intersection needed
    #   2. not intersects    -> zero area, no intersection needed
    #   3. intersects but not within (boundary-straddlers only, expected to be
    #      a small minority) -> exact intersection().area computed just for these
    t0 = time.time()
    ecoregion_union = ecoregions.geometry.union_all()
    shapely.prepare(ecoregion_union)

    r6 = r6.copy()
    geoms = r6.geometry.values
    r6["area_m2"] = r6.geometry.area

    is_within = shapely.within(geoms, ecoregion_union)
    is_intersecting = shapely.intersects(geoms, ecoregion_union)
    straddling = is_intersecting & ~is_within
    n_straddling = int(straddling.sum())
    log(f"within={int(is_within.sum()):,}  intersects_but_not_within(straddling)={n_straddling:,}  "
        f"no_intersect={int((~is_intersecting).sum()):,}  (prepared-geometry predicates, {time.time()-t0:.1f}s)")

    area_in = np.where(is_within, r6["area_m2"].values, 0.0)
    if n_straddling:
        t1 = time.time()
        straddle_area = shapely.area(shapely.intersection(geoms[straddling], ecoregion_union))
        area_in[straddling] = straddle_area
        log(f"Exact intersection area computed for {n_straddling:,} straddling polygons only ({time.time()-t1:.1f}s)")

    r6["area_in_ecoregions_m2"] = area_in
    r6["area_outside_ecoregions_m2"] = r6["area_m2"] - r6["area_in_ecoregions_m2"]
    log(f"Total overlay time: {time.time()-t0:.1f}s")

    captured_area = float(r6["area_in_ecoregions_m2"].sum())
    uncaptured_area = total_area - captured_area
    log(f"\nArea captured by union of 7 ecoregions: {captured_area:,.0f} m2 "
        f"({100*captured_area/total_area:.3f}%)")
    log(f"Area OUTSIDE all 7 ecoregions: {uncaptured_area:,.0f} m2 "
        f"({100*uncaptured_area/total_area:.3f}%)")

    outside_mask = r6["area_outside_ecoregions_m2"] > (0.5 * r6["area_m2"])  # majority-outside polygons
    n_outside = int(outside_mask.sum())
    log(f"Polygons with >50% of their own area outside all ecoregions: {n_outside:,} "
        f"({100*n_outside/total_count:.3f}%)")

    # Assign each polygon to its primary ecoregion via centroid (fast, and
    # adequate for landscape-level *characterization* -- Section 6 grouping).
    centroids = gpd.GeoDataFrame(geometry=r6.geometry.centroid, crs=r6.crs)
    joined = gpd.sjoin(centroids, ecoregions[["us_l3code", "us_l3name", "geometry"]],
                        how="left", predicate="within")
    r6["us_l3code"] = joined["us_l3code"].values
    r6["us_l3name"] = joined["us_l3name"].values

    # IMPORTANT: for the per-ecoregion *area* table, crediting a centroid-
    # assigned polygon's full raw area (or its area-within-the-whole-union)
    # to one ecoregion can exceed that ecoregion's own area whenever a
    # polygon straddles the boundary *between two individual ecoregions*
    # (common along long shared forest boundaries) while still being fully
    # within the 7-ecoregion union overall -- caught during this run (fill
    # fractions >100%). Fixed by intersecting each polygon against its own
    # *assigned* ecoregion specifically (not the union), using the same
    # prepared-geometry within-first shortcut, per ecoregion group.
    r6["area_in_own_ecoregion_m2"] = np.nan
    eco_geom = dict(zip(ecoregions["us_l3code"], ecoregions.geometry))
    for code, geom in eco_geom.items():
        shapely.prepare(geom)
        mask = (r6["us_l3code"] == code).values
        sub_geoms = r6.geometry.values[mask]
        sub_within = shapely.within(sub_geoms, geom)
        sub_area_full = r6["area_m2"].values[mask]
        sub_area_out = np.where(sub_within, sub_area_full, 0.0)
        sub_straddle = ~sub_within
        if sub_straddle.sum():
            sub_area_out[sub_straddle] = shapely.area(shapely.intersection(sub_geoms[sub_straddle], geom))
        r6.loc[mask, "area_in_own_ecoregion_m2"] = sub_area_out

    per_ecoregion = r6.groupby(["us_l3code", "us_l3name"], dropna=False).agg(
        polygon_count=("OBJECTID", "count"),
        attributed_area_m2=("area_in_own_ecoregion_m2", "sum"),
    ).reset_index()
    per_ecoregion = per_ecoregion.merge(
        ecoregions[["us_l3code", "region_area_m2"]], on="us_l3code", how="left"
    )
    per_ecoregion["fill_fraction_pct"] = round(
        100 * per_ecoregion["attributed_area_m2"] / per_ecoregion["region_area_m2"], 4
    )
    per_ecoregion = per_ecoregion.sort_values("attributed_area_m2", ascending=False)
    # NOTE: fill_fraction_pct CAN legitimately exceed 100%. area_in_own_ecoregion_m2
    # sums each polygon's own intersection with its assigned ecoregion (so any
    # single polygon's contribution is capped at its own area, verified during
    # development), but ADS_R6_Damage_allyears.shp is a repeated ANNUAL survey
    # (SURVEY_YEA spans 1997-2025, up to 29 distinct years in one ecoregion here)
    # -- the same ground can be legitimately re-attributed with damage in
    # multiple different years, so cumulative attributed area across all years
    # can exceed the ecoregion's one-time land area. This is real multi-year
    # richness, not double-counting error -- confirmed by checking DAMAGE_ARE
    # repeat rates (~1.06x, i.e. NOT the dominant driver) vs. distinct
    # SURVEY_YEA count (up to 29) for the highest-fill-fraction ecoregion.
    n_over_100 = int((per_ecoregion["fill_fraction_pct"] > 100).sum())
    if n_over_100:
        log(f"\nNOTE: {n_over_100} ecoregion(s) show fill_fraction_pct > 100% -- expected for a "
            f"repeated multi-year annual survey (same ground re-attributed across different years), "
            f"not a computation error. See module docstring / QA report for the verification.")

    log("\nPer-ecoregion capture summary (centroid-assigned; NaN us_l3code = centroid fell outside all 7):")
    log(per_ecoregion.to_string(index=False))

    out_path = QA_DIR / "ads_r6_ecoregion_capture.csv"
    per_ecoregion.to_csv(out_path, index=False)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)}")

    return r6, per_ecoregion


# -----------------------------------------------------------------------------
# Step 6: characterize by ecoregion x year x DCA_CODE x DAMAGE_TYP
# -----------------------------------------------------------------------------

def step6_characterize(r6):
    log("\n" + "=" * 70)
    log("STEP 6: CHARACTERIZE BY ECOREGION x YEAR x DCA_CODE x DAMAGE_TYP")
    log("=" * 70)
    log("(native ADS taxonomy preserved verbatim -- no harmonization with NCCN/GLKN)")

    by_year = r6.groupby(["us_l3code", "SURVEY_YEA"]).agg(
        polygon_count=("OBJECTID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_year.to_csv(QA_DIR / "ads_r6_by_ecoregion_year.csv", index=False)
    log(f"\nWrote outputs/qa/ads_r6_by_ecoregion_year.csv ({len(by_year)} rows)")

    by_dca = r6.groupby(["us_l3code", "DCA_CODE", "DCA_COMMON"]).agg(
        polygon_count=("OBJECTID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_dca.to_csv(QA_DIR / "ads_r6_by_ecoregion_dca.csv", index=False)
    log(f"Wrote outputs/qa/ads_r6_by_ecoregion_dca.csv ({len(by_dca)} rows)")

    by_damage_typ = r6.groupby(["us_l3code", "DAMAGE_TYP", "DAMAGE_T_1"]).agg(
        polygon_count=("OBJECTID", "count"), area_m2=("area_m2", "sum")
    ).reset_index()
    by_damage_typ.to_csv(QA_DIR / "ads_r6_by_ecoregion_damage_type.csv", index=False)
    log(f"Wrote outputs/qa/ads_r6_by_ecoregion_damage_type.csv ({len(by_damage_typ)} rows)")

    log("\nTop 5 DCA_COMMON per ecoregion (by area):")
    for code, grp in by_dca.groupby("us_l3code"):
        top5 = grp.sort_values("area_m2", ascending=False).head(5)
        log(f"  {code}: " + "; ".join(f"{r.DCA_COMMON} ({r.area_m2/1e4:,.0f} ha)" for r in top5.itertuples()))

    return by_year, by_dca, by_damage_typ


def main():
    (PROCESSED / "ads_r6").mkdir(parents=True, exist_ok=True)
    (PROCESSED / "boundaries").mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    r6 = step1_filter_region6()
    ecoregions = step2_dissolve_ecoregions(r6.crs)
    r6 = step3_light_geometry_fix(r6)
    r6, per_ecoregion = step4_5_overlay(r6, ecoregions)
    step6_characterize(r6)

    out_path = PROCESSED / "ads_r6" / "ads_r6_region6_with_ecoregion.parquet"
    r6.to_parquet(out_path)
    log(f"\nWrote {out_path.relative_to(REPO_ROOT)} ({len(r6)} features)")

    log("\n" + "=" * 70)
    log("DONE")
    log("=" * 70)


if __name__ == "__main__":
    main()
