"""
GLKN processing: preparation + QA only (Steps 1-4 of the GLKN processing
phase, mirroring src/process_nccn.py's NCCN methodology). This is NOT the
final region-summary step -- it re-verifies the GLKN schema fresh against
the prior inventory, geometry-repairs and standardizes the CONFIRMED
disturbance polygons only, and reports HUC12/HUC10 geography QA.

Scope: GLKN only. Does not touch NCCN, ADS R6, or ADS R10. Does not
harmonize change classes across sources. Does not compute final
region x year x class summary tables.

Established interpretation (from docs/data_inventory.md SS3, the GLKN
metadata, and the Kirschbaum SLBE report -- not re-derived here, applied):
    - change_occurred == 'true'  -> confirmed/interpreted disturbance.
    - change_occurred == 'false' -> rejected/false-positive candidate,
      retained in raw data, EXCLUDED from the primary confirmed-disturbance
      processed product (not treated as a curated no-change class).
    - year is the per-polygon disturbance year (not analysis_yrs).
    - UNIQUE is the unique row-level identifier (not uniqID, which repeats
      across repeated assessments of the same physical patch).
    - HUC_12 is populated for 100% of confirmed rows (verified again below,
      not assumed).

Input (raw, read-only): data/raw/glkn/LandTrendr (no .gdb extension --
preserved exactly as received; GDAL needs a .gdb-suffixed copy to open it).
A persistent renamed COPY (not raw data, a pure rename with zero content
change) lives at data/processed/glkn/LandTrendr.gdb for this and future
GLKN processing to read from, per the plan already documented in
docs/DATA_MANIFEST.md ("GDB extension note").

Writes:
    data/processed/glkn/glkn_confirmed_repaired.parquet   (geometry-repaired
        confirmed disturbance polygons, otherwise-original attributes)
    data/processed/glkn/glkn_confirmed_standardized.parquet (Step 3 product)
    outputs/qa/glkn_schema_qa.md
    outputs/qa/glkn_geometry_repair_qa.csv
    outputs/qa/glkn_geometry_repair_large_changes.csv
    outputs/qa/glkn_huc_geography.csv
    outputs/qa/glkn_huc10_unassigned.csv

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

GDB_PATH = PROCESSED / "glkn" / "LandTrendr.gdb"
LAYER = "LandTrendr_disturbance_polygons"

PARKS = ["apis", "indu", "isro", "miss", "sacn", "slbe", "voya"]
LARGE_CHANGE_REL_THRESHOLD = 0.05

# Previously documented figures (docs/data_inventory.md SS3), re-verified
# below rather than assumed.
PRIOR_TOTAL_ROWS = 177153
PRIOR_TRUE_COUNT = 53665
PRIOR_FALSE_COUNT = 123488
PRIOR_PARKS = set(PARKS)


def log(msg=""):
    print(msg)


# -----------------------------------------------------------------------------
# Step 1: input / schema QA
# -----------------------------------------------------------------------------

def step1_schema_qa():
    log("=" * 70)
    log("STEP 1: INPUT / SCHEMA QA")
    log("=" * 70)

    gdf = gpd.read_file(GDB_PATH, layer=LAYER)
    report_lines = []

    def rlog(msg):
        log(msg)
        report_lines.append(msg)

    rlog(f"Source (working copy of raw): {GDB_PATH.relative_to(REPO_ROOT)}, layer={LAYER}")
    rlog(f"CRS: {gdf.crs}")
    rlog(f"Total rows: {len(gdf)}")

    # --- verify against prior inventory, don't assume ---
    rlog("\n--- Verification against prior inventory (docs/data_inventory.md SS3) ---")
    match_total = len(gdf) == PRIOR_TOTAL_ROWS
    rlog(f"Total rows match prior ({PRIOR_TOTAL_ROWS}): {match_total}" +
         ("" if match_total else f"  <-- MISMATCH, now {len(gdf)}"))

    vc_occurred = gdf["change_occurred"].value_counts(dropna=False)
    n_true = int(vc_occurred.get(True, vc_occurred.get("true", 0)))
    n_false = int(vc_occurred.get(False, vc_occurred.get("false", 0)))
    rlog(f"change_occurred value counts: {dict(vc_occurred)}")
    match_true = n_true == PRIOR_TRUE_COUNT
    match_false = n_false == PRIOR_FALSE_COUNT
    rlog(f"True count matches prior ({PRIOR_TRUE_COUNT}): {match_true}" +
         ("" if match_true else f"  <-- MISMATCH, now {n_true}"))
    rlog(f"False count matches prior ({PRIOR_FALSE_COUNT}): {match_false}" +
         ("" if match_false else f"  <-- MISMATCH, now {n_false}"))

    found_parks = set(gdf["park"].dropna().unique())
    rlog(f"Parks found: {sorted(found_parks)}")
    rlog(f"Parks match prior 7-park set: {found_parks == PRIOR_PARKS}" +
         ("" if found_parks == PRIOR_PARKS else f"  <-- MISMATCH: {found_parks.symmetric_difference(PRIOR_PARKS)}"))

    # --- confirmed rows by park ---
    rlog("\n--- Confirmed (change_occurred==True) rows by park ---")
    # change_occurred is stored as the literal string "true"/"false" in this
    # GDB, not a Python bool -- verified directly (see value_counts above),
    # not assumed.
    confirmed = gdf[gdf["change_occurred"].astype(str).str.lower() == "true"].copy()
    by_park = confirmed.groupby("park").size().reindex(PARKS)
    rlog(by_park.to_string())
    rlog(f"Total confirmed: {len(confirmed)}")

    # --- year range by park (all rows, and confirmed-only) ---
    rlog("\n--- Year range by park (ALL rows) ---")
    rlog(gdf.groupby("park")["year"].agg(["min", "max", "count"]).reindex(PARKS).to_string())
    rlog("\n--- Year range by park (CONFIRMED rows only -- year is the per-polygon disturbance year) ---")
    rlog(confirmed.groupby("park")["year"].agg(["min", "max", "count"]).reindex(PARKS).to_string())

    # --- agent vocabulary (confirmed rows) ---
    rlog("\n--- Agent vocabulary (agent_01/02/03 combined, confirmed rows) ---")
    agent_vals = pd.concat([confirmed["agent_01"], confirmed["agent_02"], confirmed["agent_03"]]).dropna()
    rlog(agent_vals.value_counts().to_string())

    # --- geometry validity by park: ALL rows, and confirmed-only ---
    rlog("\n--- Geometry validity by park (ALL rows) ---")
    gdf["_valid"] = gdf.geometry.is_valid
    rlog(gdf.groupby("park")["_valid"].agg(["sum", "count"]).rename(
        columns={"sum": "valid_count", "count": "total"}).reindex(PARKS).to_string())

    rlog("\n--- Geometry validity by park (CONFIRMED rows only) ---")
    confirmed["_valid"] = confirmed.geometry.is_valid
    rlog(confirmed.groupby("park")["_valid"].agg(["sum", "count"]).rename(
        columns={"sum": "valid_count", "count": "total"}).reindex(PARKS).to_string())

    # --- missingness in important fields ---
    rlog("\n--- Missingness in important fields (ALL rows, n=%d) ---" % len(gdf))
    important = ["UNIQUE", "uniqID", "year", "change_occurred", "agent_01", "HUC_12",
                 "park", "start_class_01", "end_class_01", "owner_type1", "loc_01", "loc_02"]
    for col in important:
        n_null = int(gdf[col].isna().sum())
        n_empty = int((gdf[col].astype(str) == "").sum()) if gdf[col].dtype == object else 0
        rlog(f"  {col}: {n_null} null ({100*n_null/len(gdf):.1f}%), {n_empty} empty string")

    rlog("\n--- Missingness in important fields (CONFIRMED rows only, n=%d) ---" % len(confirmed))
    for col in important:
        n_null = int(confirmed[col].isna().sum())
        rlog(f"  {col}: {n_null} null ({100*n_null/len(confirmed):.1f}%)")

    (QA_DIR).mkdir(parents=True, exist_ok=True)
    (QA_DIR / "glkn_schema_qa.md").write_text(
        "# GLKN Schema / Input QA\n\n```\n" + "\n".join(report_lines) + "\n```\n"
    )

    return gdf, confirmed


# -----------------------------------------------------------------------------
# Step 2: geometry repair QA (confirmed rows only)
# -----------------------------------------------------------------------------

def to_polygonal(geom):
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
    return geom


def invalidity_reasons(gdf):
    invalid = gdf[~gdf.geometry.is_valid]
    if len(invalid) == 0:
        return pd.Series(dtype="int64")
    reasons = invalid.geometry.apply(explain_validity).str.extract(r"^(\D+?)\[")[0]
    reasons = reasons.fillna(invalid.geometry.apply(explain_validity))
    return reasons.value_counts()


def repair_park(park_code, gdf_park):
    n = len(gdf_park)
    valid_mask = gdf_park.geometry.is_valid
    n_valid = int(valid_mask.sum())
    n_invalid = n - n_valid
    reasons = invalidity_reasons(gdf_park)
    area_before_total = float(gdf_park.geometry.area.sum())

    geom_type_before = gdf_park.geometry.geom_type.copy()
    area_before = gdf_park.geometry.area.copy()

    repaired = gdf_park.geometry.make_valid()
    became_collection = repaired.geom_type == "GeometryCollection"
    repaired = repaired.apply(to_polygonal)

    out = gdf_park.copy()
    out["geometry"] = repaired
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=gdf_park.crs)

    geom_type_after = out.geometry.geom_type
    area_after = out.geometry.area.fillna(0.0)
    n_empty_after = int(out.geometry.isna().sum() + out.geometry.is_empty.sum())
    type_changed = geom_type_before.fillna("None") != geom_type_after.fillna("None")

    rel_change = ((area_after - area_before).abs() / area_before.replace(0, pd.NA)).fillna(0.0)
    large_change_mask = rel_change > LARGE_CHANGE_REL_THRESHOLD

    before_report = {
        "park_code": park_code, "feature_count": n, "valid_count": n_valid,
        "invalid_count": n_invalid, "invalid_pct": round(100 * n_invalid / n, 2) if n else 0.0,
        "invalidity_reasons_json": json.dumps({k: int(v) for k, v in reasons.items()}),
        "total_area_m2_before": area_before_total,
    }

    comparison = {
        "park_code": park_code,
        "feature_count_before": n, "feature_count_after": len(out),
        "geometry_type_changed_count": int(type_changed.sum()),
        "became_geometrycollection_count": int(became_collection.sum()),
        "empty_after_repair_count": n_empty_after,
        "total_area_m2_before": float(area_before.sum()),
        "total_area_m2_after": float(area_after.sum()),
        "area_diff_m2": float(area_after.sum() - area_before.sum()),
        "area_pct_diff": round(100 * (area_after.sum() - area_before.sum()) / area_before.sum(), 4)
        if area_before.sum() else 0.0,
        "large_change_feature_count": int(large_change_mask.sum()),
        "large_change_threshold_pct": LARGE_CHANGE_REL_THRESHOLD * 100,
    }

    large_changes = pd.DataFrame({
        "park_code": park_code,
        "source_feature_id": gdf_park["UNIQUE"].astype(str)[large_change_mask].values,
        "area_before_m2": area_before[large_change_mask].values,
        "area_after_m2": area_after[large_change_mask].values,
        "rel_change_pct": (rel_change[large_change_mask] * 100).values,
    })

    return out, before_report, comparison, large_changes


def step2_geometry_repair(confirmed):
    log("\n" + "=" * 70)
    log("STEP 2: GEOMETRY REPAIR QA (confirmed rows only)")
    log("=" * 70)

    before_reports, comparisons, all_large_changes = [], [], []
    repaired_parts = []

    for park in PARKS:
        sub = confirmed[confirmed["park"] == park].reset_index(drop=True)
        out, before_report, comparison, large_changes = repair_park(park, sub)
        before_reports.append(before_report)
        comparisons.append(comparison)
        all_large_changes.append(large_changes)
        repaired_parts.append(out)

        log(f"\n--- {park} ---")
        log(f"  feature_count={before_report['feature_count']}  valid={before_report['valid_count']}  "
            f"invalid={before_report['invalid_count']} ({before_report['invalid_pct']}%)")
        log(f"  invalidity_reasons={before_report['invalidity_reasons_json']}")
        log(f"  area_before_m2={before_report['total_area_m2_before']:,.1f}")
        log(f"  AFTER REPAIR: type_changed={comparison['geometry_type_changed_count']}  "
            f"became_geometrycollection={comparison['became_geometrycollection_count']}  "
            f"empty_after={comparison['empty_after_repair_count']}")
        log(f"  area_after_m2={comparison['total_area_m2_after']:,.1f}  "
            f"area_pct_diff={comparison['area_pct_diff']}%  "
            f"large_change_features(>{comparison['large_change_threshold_pct']}%)={comparison['large_change_feature_count']}")

    before_df = pd.DataFrame(before_reports)
    before_df.to_csv(QA_DIR / "glkn_geometry_validity_before_repair.csv", index=False)

    comp_df = pd.DataFrame(comparisons)
    comp_df.to_csv(QA_DIR / "glkn_geometry_repair_qa.csv", index=False)

    large_df = pd.concat(all_large_changes, ignore_index=True) if all_large_changes else pd.DataFrame()
    large_df.to_csv(QA_DIR / "glkn_geometry_repair_large_changes.csv", index=False)

    repaired = gpd.GeoDataFrame(pd.concat(repaired_parts, ignore_index=True), geometry="geometry", crs=confirmed.crs)

    max_abs_pct_diff = comp_df["area_pct_diff"].abs().max()
    log(f"\nMax |area % diff| across all 7 parks: {max_abs_pct_diff}")
    total_large_changes = int(comp_df["large_change_feature_count"].sum())
    log(f"Total large-change features (>{LARGE_CHANGE_REL_THRESHOLD*100}%) across all parks: {total_large_changes}")

    stop = max_abs_pct_diff > 1.0 or total_large_changes > 0.02 * len(repaired)
    if stop:
        log("\n*** STOP CONDITION TRIGGERED -- repair caused meaningful/unexpected area changes. ***")
        log("*** Halting before Step 3. Review outputs/qa/glkn_geometry_repair_qa.csv. ***")
    else:
        log("\nRepair looks clean and defensible -- proceeding to Step 3.")

    out_path = PROCESSED / "glkn" / "glkn_confirmed_repaired.parquet"
    repaired.to_parquet(out_path)
    log(f"Wrote {out_path.relative_to(REPO_ROOT)}")

    return repaired, stop


# -----------------------------------------------------------------------------
# Step 3: standardize
# -----------------------------------------------------------------------------

def step3_standardize(repaired):
    log("\n" + "=" * 70)
    log("STEP 3: STANDARDIZED GLKN PRODUCT (confirmed disturbances only)")
    log("=" * 70)

    out = repaired.copy()
    out["source"] = "GLKN"
    out["source_dataset"] = LAYER
    out["source_feature_id"] = out["UNIQUE"].astype(str)
    out["park_code"] = out["park"].str.upper()
    out["year"] = out["year"]
    out["change_class"] = out["agent_01"]  # native primary causal attribution, no harmonization

    standardized_cols = ["source", "source_dataset", "source_feature_id", "park_code", "year", "change_class"]
    original_cols = [c for c in repaired.columns if c not in ("geometry", "_valid")]
    ordered = standardized_cols + [c for c in original_cols if c not in standardized_cols] + ["geometry"]
    out = gpd.GeoDataFrame(out[ordered], geometry="geometry", crs=repaired.crs)

    out_path = PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet"
    out.to_parquet(out_path)
    log(f"Wrote {out_path.relative_to(REPO_ROOT)} ({len(out)} features, {len(out.columns)} columns)")
    log(f"Missing year: {out['year'].isna().sum()}, missing change_class: {out['change_class'].isna().sum()}, "
        f"missing source_feature_id: {out['source_feature_id'].isna().sum()}")
    log(f"source_feature_id globally unique: {out['source_feature_id'].is_unique}")

    return out


# -----------------------------------------------------------------------------
# Step 4: HUC geography
# -----------------------------------------------------------------------------

def step4_huc_geography(standardized):
    import re
    log("\n" + "=" * 70)
    log("STEP 4: HUC GEOGRAPHY (confirmed disturbances)")
    log("=" * 70)

    df = standardized.copy()
    huc12 = df["HUC_12"].fillna("")
    is_standard = huc12.str.fullmatch(r"\d{12}")
    is_blank = huc12 == ""
    is_nonstandard = (~is_standard) & (~is_blank)

    df["huc12_class"] = "standard"
    df.loc[is_blank, "huc12_class"] = "missing"
    df.loc[is_nonstandard, "huc12_class"] = "nonstandard"

    df["huc10_derived"] = pd.NA
    df.loc[is_standard, "huc10_derived"] = huc12[is_standard].str[:10]

    log("HUC_12 classification (confirmed rows):")
    log(df["huc12_class"].value_counts().to_string())

    log("\nBy park:")
    log(pd.crosstab(df["park_code"], df["huc12_class"]).to_string())

    # area/count by park x HUC12 x derived HUC10
    geog = df.groupby(["park_code", "HUC_12", "huc10_derived", "huc12_class"], dropna=False).agg(
        polygon_count=("source_feature_id", "count"),
        area_m2=("geometry", lambda g: g.area.sum()),
    ).reset_index()
    geog.to_csv(QA_DIR / "glkn_huc_geography.csv", index=False)
    log(f"\nWrote outputs/qa/glkn_huc_geography.csv ({len(geog)} rows)")

    # how much confirmed area/count cannot be assigned to a standard HUC10
    total_area = float(df.geometry.area.sum())
    total_count = len(df)
    unassigned = df[df["huc12_class"] != "standard"]
    unassigned_area = float(unassigned.geometry.area.sum())
    log(f"\nConfirmed disturbances NOT assignable to a standard HUC10: "
        f"{len(unassigned)} of {total_count} polygons ({100*len(unassigned)/total_count:.2f}%), "
        f"{unassigned_area:,.0f} of {total_area:,.0f} m2 ({100*unassigned_area/total_area:.2f}% of area)")

    log("\nBy park, nonstandard/missing polygon count and area:")
    by_park_unassigned = unassigned.groupby("park_code").agg(
        polygon_count=("source_feature_id", "count"),
        area_m2=("geometry", lambda g: g.area.sum()),
    )
    log(by_park_unassigned.to_string())

    unassigned[["park_code", "source_feature_id", "HUC_12", "huc12_class", "year", "change_class"]].to_csv(
        QA_DIR / "glkn_huc10_unassigned.csv", index=False
    )
    log(f"\nWrote outputs/qa/glkn_huc10_unassigned.csv ({len(unassigned)} rows)")

    return df


# -----------------------------------------------------------------------------
# Supporting: GLKN park boundaries (mirrors src/process_nccn.py's
# load_nps_boundaries, same source, different park codes/CRS). Formal NPS
# boundaries are NOT assumed to be the GLKN analysis extent -- this is for
# map context only, same as NCCN's park-boundary comparison.
# -----------------------------------------------------------------------------

GLKN_UNIT_CODES = {"APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"}


def step_boundaries(working_crs):
    import geopandas as gpd
    log("\n" + "=" * 70)
    log("SUPPORTING: GLKN PARK BOUNDARIES (context only, not assumed to be the analysis extent)")
    log("=" * 70)

    nps_zip = RAW / "boundaries" / "nps" / "National_Parks.zip"
    nps_path = f"/vsizip/{nps_zip.resolve()}/National_Parks.shp"
    gdf = gpd.read_file(nps_path)
    target = gdf[gdf["UNIT_CODE"].isin(GLKN_UNIT_CODES)].copy()
    log(f"Matched {len(target)} of {len(GLKN_UNIT_CODES)} target GLKN unit codes: "
        f"{sorted(target['UNIT_CODE'].tolist())}")
    missing_codes = GLKN_UNIT_CODES - set(target["UNIT_CODE"])
    if missing_codes:
        log(f"  <-- MISSING codes (not found in National_Parks.shp): {sorted(missing_codes)}")

    keep_cols = ["UNIT_CODE", "UNIT_NAME", "PARKNAME", "STATE", "REGION", "Status", "DATE_EDIT", "geometry"]
    target = target[keep_cols].to_crs(working_crs)
    target = gpd.GeoDataFrame(target, geometry="geometry", crs=working_crs)

    out_path = PROCESSED / "boundaries" / "glkn_park_boundaries.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    target.to_parquet(out_path)
    log(f"Wrote {out_path.relative_to(REPO_ROOT)}")
    return target


def main():
    (PROCESSED / "glkn").mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    gdf, confirmed = step1_schema_qa()
    repaired, stop = step2_geometry_repair(confirmed)
    if stop:
        log("\nStopping before Step 3/4 per stop condition. Not writing standardized product.")
        return
    standardized = step3_standardize(repaired)
    geog = step4_huc_geography(standardized)
    boundaries = step_boundaries(standardized.crs)

    log("\n" + "=" * 70)
    log("DONE")
    log("=" * 70)


if __name__ == "__main__":
    main()
