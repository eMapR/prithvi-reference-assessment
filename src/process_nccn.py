"""
NCCN processing: preparation + QA only (Steps 1-6 of the NCCN processing
phase). This is NOT the final region-summary step -- it produces a clean,
standardized, geometry-repaired NCCN reference dataset and a matching
4-park NPS boundary dataset, plus QA reports on both the geometry repair
and the reference-polygon-to-park-boundary spatial relationship, so that
question can be answered with evidence before any clipping/summary logic
is written.

Scope: NCCN only. Does not touch GLKN, ADS R6, or ADS R10. Does not
harmonize change classes across sources. Does not compute final
region x year x class summary tables.

Inputs (raw, read-only -- see docs/DATA_MANIFEST.md):
    data/raw/nccn/NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION/
        MORA_1987_2017_V2_1_1_UTM.shp   (current schema)
        NOCA_1987_2017_V2_1_1_UTM.shp   (current schema)
        OLYM_1987_2017_V2_1_1_UTM.shp   (current schema)
    data/raw/nccn/NCCN_Landscape_Change_LPa01_LEWI_1985-2011_DISTRIBUTION/
        LEWI_1985_2011_Report_UTM.shp   (older/own schema vintage)
    data/raw/boundaries/nps/National_Parks.zip (national NPS unit boundaries)

NOT used for the primary processed product (deliberately excluded, per
instruction): data/raw/nccn/V2B/NOCA_1985_2009_V2B_UTM.shp and
data/raw/nccn/V2B-2/OLYM_1985_2010_V2B_UTM.shp -- these remain in raw,
untouched, as preserved legacy source data.

Working CRS: EPSG:26910 (NAD83 / UTM Zone 10N). This is the shared native
CRS of all NCCN source shapefiles (confirmed identical across all 6 NCCN
files during inspection), so using it introduces no reprojection distortion
for the reference data itself. All four target parks (MORA, NOCA, OLYM,
LEWI) sit close to its central meridian (-123 W), so UTM 10N's local area
distortion here is minimal -- comparable to or better than reprojecting to
a CONUS-wide equal-area CRS for this specific, geographically compact
study area. Only the NPS boundary layer (native EPSG:3857, not suitable
for area work at all) needs reprojecting, into this same CRS.

Geometry repair method: shapely/GEOS make_valid() (GeoSeries.make_valid()),
not the older buffer(0) trick -- make_valid() is GEOS's purpose-built,
topology-preserving repair algorithm and is considered the robust modern
standard for this. make_valid() can occasionally return a GeometryCollection
mixing polygonal and non-polygonal (line/point) components when a self-
intersection degenerates part of the geometry; when that happens here, only
the polygonal parts are kept (unioned back into a Polygon/MultiPolygon) and
the feature is flagged in the QA output -- this is a standard, documented
consequence of using make_valid() on polygon data, not a silent decision.

Writes:
    data/processed/nccn/repaired/{PARK}_repaired.parquet   (geometry-repaired,
        original attributes otherwise untouched -- Step 2 deliverable)
    data/processed/nccn/nccn_standardized.parquet            (Step 3 deliverable)
    data/processed/boundaries/nccn_park_boundaries.parquet    (Step 4 deliverable)
    outputs/qa/nccn_geometry_repair_qa.csv
    outputs/qa/nccn_geometry_repair_large_changes.csv
    outputs/qa/nccn_boundary_relationship_qa.csv
    outputs/qa/nccn_processing_report.md

Never writes to data/raw/.
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import get_parts
from shapely.geometry import MultiPolygon
from shapely.validation import explain_validity

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"

WORKING_CRS = "EPSG:26910"  # NAD83 / UTM Zone 10N -- see module docstring
NPS_ZIP = RAW / "boundaries" / "nps" / "National_Parks.zip"
NPS_LAYER_PATH = f"/vsizip/{NPS_ZIP.resolve()}/National_Parks.shp"

# --- Step 1: exact input selection -----------------------------------------
# Each entry documents the exact raw file, its schema family, and the field
# mapping used to populate the standardized columns in Step 3.
PARKS = {
    "MORA": {
        "path": RAW / "nccn" / "NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION"
                / "MORA_1987_2017_V2_1_1_UTM.shp",
        "schema": "v2_1_1",
    },
    "NOCA": {
        "path": RAW / "nccn" / "NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION"
                / "NOCA_1987_2017_V2_1_1_UTM.shp",
        "schema": "v2_1_1",
    },
    "OLYM": {
        "path": RAW / "nccn" / "NCCN_Landscape_Change_LPa01_1987-2017_V2_1_1_DISTRIBUTION"
                / "OLYM_1987_2017_V2_1_1_UTM.shp",
        "schema": "v2_1_1",
    },
    "LEWI": {
        "path": RAW / "nccn" / "NCCN_Landscape_Change_LPa01_LEWI_1985-2011_DISTRIBUTION"
                / "LEWI_1985_2011_Report_UTM.shp",
        "schema": "lewi",
    },
}

LARGE_CHANGE_REL_THRESHOLD = 0.05  # flag features whose area changed >5% under repair


def log(msg=""):
    print(msg)


# -----------------------------------------------------------------------------
# Step 1/2: load raw, report validity + area before repair
# -----------------------------------------------------------------------------

def load_raw(park_code):
    info = PARKS[park_code]
    gdf = gpd.read_file(info["path"])
    assert gdf.crs is not None and str(gdf.crs).upper().replace("EPSG:", "") == "26910", (
        f"{park_code}: unexpected CRS {gdf.crs}, expected EPSG:26910"
    )
    return gdf


def invalidity_reasons(gdf):
    invalid = gdf[~gdf.geometry.is_valid]
    if len(invalid) == 0:
        return pd.Series(dtype="int64")
    reasons = invalid.geometry.apply(explain_validity).str.extract(r"^(\D+?)\[")[0]
    reasons = reasons.fillna(invalid.geometry.apply(explain_validity))
    return reasons.value_counts()


def before_repair_report(park_code, gdf):
    n = len(gdf)
    valid_mask = gdf.geometry.is_valid
    n_valid = int(valid_mask.sum())
    n_invalid = n - n_valid
    total_area = float(gdf.geometry.area.sum())
    reasons = invalidity_reasons(gdf)
    return {
        "park_code": park_code,
        "source_dataset": PARKS[park_code]["path"].stem,
        "feature_count": n,
        "valid_count": n_valid,
        "invalid_count": n_invalid,
        "invalid_pct": round(100 * n_invalid / n, 2) if n else 0.0,
        "invalidity_reasons": {k: int(v) for k, v in reasons.items()} if len(reasons) else {},
        "total_area_m2_before": total_area,
    }


# -----------------------------------------------------------------------------
# Step 2: repair, compare before/after
# -----------------------------------------------------------------------------

def to_polygonal(geom):
    """Extract only polygonal parts from a geometry that make_valid() may have
    turned into a mixed-type GeometryCollection. Returns None if nothing
    polygonal survives (feature becomes empty -- flagged separately)."""
    if geom is None or geom.is_empty:
        return geom
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in get_parts(geom) if g.geom_type in ("Polygon", "MultiPolygon")]
        if not parts:
            return None
        flat = []
        for p in parts:
            if p.geom_type == "MultiPolygon":
                flat.extend(list(p.geoms))
            else:
                flat.append(p)
        return flat[0] if len(flat) == 1 else MultiPolygon(flat)
    return geom  # unexpected type -- left as-is, will show up as a type-change flag


def repair_geometries(park_code, gdf_raw):
    gdf = gdf_raw.copy()
    geom_type_before = gdf.geometry.geom_type.copy()
    area_before = gdf.geometry.area.copy()
    is_multipart_before = gdf.geometry.apply(
        lambda g: g.geom_type == "MultiPolygon" and len(g.geoms) > 1 if g is not None else False
    )

    repaired = gdf.geometry.make_valid()
    became_collection = repaired.geom_type == "GeometryCollection"
    repaired = repaired.apply(to_polygonal)

    gdf["geometry"] = repaired
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=WORKING_CRS)

    geom_type_after = gdf.geometry.geom_type
    area_after = gdf.geometry.area.fillna(0.0)
    is_multipart_after = gdf.geometry.apply(
        lambda g: g is not None and g.geom_type == "MultiPolygon" and len(g.geoms) > 1
    )
    n_empty_after = int(gdf.geometry.isna().sum() + gdf.geometry.is_empty.sum())

    type_changed = geom_type_before.fillna("None") != geom_type_after.fillna("None")

    rel_change = ((area_after - area_before).abs() / area_before.replace(0, pd.NA)).fillna(0.0)
    large_change_mask = rel_change > LARGE_CHANGE_REL_THRESHOLD

    comparison = {
        "park_code": park_code,
        "feature_count_before": len(gdf_raw),
        "feature_count_after": len(gdf),
        "geometry_type_changed_count": int(type_changed.sum()),
        "became_geometrycollection_count": int(became_collection.sum()),
        "empty_after_repair_count": n_empty_after,
        "multipart_before_count": int(is_multipart_before.sum()),
        "multipart_after_count": int(is_multipart_after.sum()),
        "total_area_m2_before": float(area_before.sum()),
        "total_area_m2_after": float(area_after.sum()),
        "area_diff_m2": float(area_after.sum() - area_before.sum()),
        "area_pct_diff": round(
            100 * (area_after.sum() - area_before.sum()) / area_before.sum(), 4
        ) if area_before.sum() else 0.0,
        "large_change_feature_count": int(large_change_mask.sum()),
        "large_change_threshold_pct": LARGE_CHANGE_REL_THRESHOLD * 100,
    }

    large_changes = pd.DataFrame({
        "park_code": park_code,
        "source_feature_id": _feature_id(gdf_raw, park_code)[large_change_mask].values,
        "area_before_m2": area_before[large_change_mask].values,
        "area_after_m2": area_after[large_change_mask].values,
        "rel_change_pct": (rel_change[large_change_mask] * 100).values,
        "geom_type_before": geom_type_before[large_change_mask].values,
        "geom_type_after": geom_type_after[large_change_mask].values,
    }).sort_values("rel_change_pct", ascending=False)

    return gdf, comparison, large_changes


def _feature_id(gdf, park_code):
    schema = PARKS[park_code]["schema"]
    if schema == "v2_1_1":
        return gdf["Patch_name"].astype(str)
    return gdf["PatchID"].astype(str)


# -----------------------------------------------------------------------------
# Step 3: standardize
# -----------------------------------------------------------------------------

def standardize(park_code, gdf_repaired):
    schema = PARKS[park_code]["schema"]
    out = gdf_repaired.copy()

    out["source"] = "NCCN"
    out["source_dataset"] = PARKS[park_code]["path"].stem
    out["park_code"] = park_code

    if schema == "v2_1_1":
        out["source_feature_id"] = out["Patch_name"].astype(str)
        out["change_class"] = out["ChangeType"]
        detect_yr = out["Detect_yr"]
        dist_yr = out["Dist_year"]
        is_fire_with_dist_year = (out["ChangeType"] == "Fire") & (dist_yr > 0)
        out["year"] = detect_yr.where(~is_fire_with_dist_year, dist_yr)
        out["year_source_field"] = pd.Series("Detect_yr", index=out.index).where(
            ~is_fire_with_dist_year, "Dist_year"
        )
    else:  # lewi
        out["source_feature_id"] = out["PatchID"].astype(str)
        out["change_class"] = out["Chnge_type"]
        out["year"] = out["AnalysisYr"]
        out["year_source_field"] = "AnalysisYr"

    standardized_cols = [
        "source", "source_dataset", "source_feature_id", "park_code",
        "year", "year_source_field", "change_class",
    ]
    original_cols = [c for c in gdf_repaired.columns if c != "geometry"]
    ordered = standardized_cols + [c for c in original_cols if c not in standardized_cols] + ["geometry"]
    return gpd.GeoDataFrame(out[ordered], geometry="geometry", crs=WORKING_CRS)


# -----------------------------------------------------------------------------
# Step 4: boundaries
# -----------------------------------------------------------------------------

def load_nps_boundaries():
    gdf = gpd.read_file(NPS_LAYER_PATH)
    target = gdf[gdf["UNIT_CODE"].isin(PARKS.keys())].copy()
    assert len(target) == 4, f"expected 4 matched parks, got {len(target)}"
    keep_cols = ["UNIT_CODE", "UNIT_NAME", "PARKNAME", "STATE", "REGION", "Status", "DATE_EDIT", "geometry"]
    target = target[keep_cols]
    target = target.to_crs(WORKING_CRS)
    return gpd.GeoDataFrame(target, geometry="geometry", crs=WORKING_CRS)


# -----------------------------------------------------------------------------
# Step 5: boundary relationship QA
# -----------------------------------------------------------------------------

def boundary_relationship_qa(park_code, gdf_repaired, park_boundary_geom):
    geoms = gdf_repaired.geometry
    total_area = float(geoms.area.sum())

    within_mask = geoms.within(park_boundary_geom)
    intersects_mask = geoms.intersects(park_boundary_geom)
    outside_mask = ~intersects_mask
    straddle_mask = intersects_mask & ~within_mask

    inside_area = float(geoms.intersection(park_boundary_geom).area.sum())
    outside_area = total_area - inside_area

    return {
        "park_code": park_code,
        "total_reference_polygons": len(gdf_repaired),
        "entirely_inside_count": int(within_mask.sum()),
        "straddling_boundary_count": int(straddle_mask.sum()),
        "entirely_outside_count": int(outside_mask.sum()),
        "total_reference_area_m2": total_area,
        "area_inside_park_m2": inside_area,
        "area_outside_park_m2": outside_area,
        "pct_area_inside": round(100 * inside_area / total_area, 2) if total_area else 0.0,
        "pct_area_outside": round(100 * outside_area / total_area, 2) if total_area else 0.0,
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    (PROCESSED / "nccn" / "repaired").mkdir(parents=True, exist_ok=True)
    (PROCESSED / "boundaries").mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 70)
    log("STEP 1: INPUT SELECTION")
    log("=" * 70)
    for code, info in PARKS.items():
        log(f"{code}: {info['path'].relative_to(REPO_ROOT)}  (schema: {info['schema']})")

    log()
    log("=" * 70)
    log("STEP 2: GEOMETRY VALIDITY (BEFORE REPAIR) + REPAIR COMPARISON")
    log("=" * 70)

    before_reports = []
    repair_comparisons = []
    all_large_changes = []
    repaired_gdfs = {}

    for code in PARKS:
        gdf_raw = load_raw(code)
        before = before_repair_report(code, gdf_raw)
        before_reports.append(before)
        log(f"\n--- {code} ({before['source_dataset']}) ---")
        log(f"  feature_count={before['feature_count']}  valid={before['valid_count']}  "
            f"invalid={before['invalid_count']} ({before['invalid_pct']}%)")
        log(f"  invalidity_reasons={before['invalidity_reasons']}")
        log(f"  total_area_m2_before={before['total_area_m2_before']:,.1f}")

        gdf_repaired, comparison, large_changes = repair_geometries(code, gdf_raw)
        repair_comparisons.append(comparison)
        all_large_changes.append(large_changes)
        repaired_gdfs[code] = gdf_repaired

        log(f"  AFTER REPAIR: type_changed={comparison['geometry_type_changed_count']}  "
            f"became_geometrycollection={comparison['became_geometrycollection_count']}  "
            f"empty_after={comparison['empty_after_repair_count']}")
        log(f"  multipart_before={comparison['multipart_before_count']}  "
            f"multipart_after={comparison['multipart_after_count']}")
        log(f"  total_area_m2_after={comparison['total_area_m2_after']:,.1f}  "
            f"area_diff_m2={comparison['area_diff_m2']:,.1f}  "
            f"area_pct_diff={comparison['area_pct_diff']}%")
        log(f"  large_change_features (>{comparison['large_change_threshold_pct']}% area change): "
            f"{comparison['large_change_feature_count']}")

        out_path = PROCESSED / "nccn" / "repaired" / f"{code}_repaired.parquet"
        gdf_repaired.to_parquet(out_path)
        log(f"  wrote {out_path.relative_to(REPO_ROOT)}")

    before_df = pd.DataFrame(before_reports)
    before_df["invalidity_reasons_json"] = before_df["invalidity_reasons"].apply(json.dumps)
    before_df = before_df.drop(columns=["invalidity_reasons"])
    before_df.to_csv(QA_DIR / "nccn_geometry_validity_before_repair.csv", index=False)

    repair_qa_df = pd.DataFrame(repair_comparisons)
    repair_qa_df.to_csv(QA_DIR / "nccn_geometry_repair_qa.csv", index=False)

    large_changes_df = pd.concat(all_large_changes, ignore_index=True) if all_large_changes else pd.DataFrame()
    large_changes_df.to_csv(QA_DIR / "nccn_geometry_repair_large_changes.csv", index=False)

    log()
    log("=" * 70)
    log("STEP 3: STANDARDIZE")
    log("=" * 70)
    standardized_parts = []
    for code in PARKS:
        std = standardize(code, repaired_gdfs[code])
        standardized_parts.append(std)
        log(f"{code}: {len(std)} features standardized "
            f"(change_class values: {sorted(std['change_class'].dropna().unique().tolist())})")

    nccn_standardized = gpd.GeoDataFrame(
        pd.concat(standardized_parts, ignore_index=True), geometry="geometry", crs=WORKING_CRS
    )
    std_path = PROCESSED / "nccn" / "nccn_standardized.parquet"
    nccn_standardized.to_parquet(std_path)
    log(f"\nwrote {std_path.relative_to(REPO_ROOT)} ({len(nccn_standardized)} total features)")

    log()
    log("=" * 70)
    log("STEP 4: NPS BOUNDARIES (MORA, NOCA, OLYM, LEWI)")
    log("=" * 70)
    boundaries = load_nps_boundaries()
    log(boundaries[["UNIT_CODE", "UNIT_NAME", "Status", "DATE_EDIT"]].to_string(index=False))
    bnd_path = PROCESSED / "boundaries" / "nccn_park_boundaries.parquet"
    boundaries.to_parquet(bnd_path)
    log(f"\nwrote {bnd_path.relative_to(REPO_ROOT)}")

    log()
    log("=" * 70)
    log("STEP 5: BOUNDARY RELATIONSHIP QA")
    log("=" * 70)
    relationship_rows = []
    for code in PARKS:
        park_geom = boundaries.loc[boundaries["UNIT_CODE"] == code, "geometry"].iloc[0]
        qa = boundary_relationship_qa(code, repaired_gdfs[code], park_geom)
        relationship_rows.append(qa)
        log(f"\n--- {code} ---")
        log(f"  total_reference_polygons={qa['total_reference_polygons']}")
        log(f"  entirely_inside={qa['entirely_inside_count']}  "
            f"straddling_boundary={qa['straddling_boundary_count']}  "
            f"entirely_outside={qa['entirely_outside_count']}")
        log(f"  total_reference_area_m2={qa['total_reference_area_m2']:,.1f}")
        log(f"  area_inside_park_m2={qa['area_inside_park_m2']:,.1f} ({qa['pct_area_inside']}%)")
        log(f"  area_outside_park_m2={qa['area_outside_park_m2']:,.1f} ({qa['pct_area_outside']}%)")

    relationship_df = pd.DataFrame(relationship_rows)
    relationship_df.to_csv(QA_DIR / "nccn_boundary_relationship_qa.csv", index=False)

    log()
    log("=" * 70)
    log("DONE")
    log("=" * 70)

    return {
        "before_reports": before_reports,
        "repair_comparisons": repair_comparisons,
        "large_changes": large_changes_df,
        "relationship": relationship_df,
    }


if __name__ == "__main__":
    main()
