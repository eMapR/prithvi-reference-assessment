"""
QA: verify the authoritative-AOI <-> source-dataset generation mapping for NCCN,
per user instruction (2026-09-24 follow-up) -- do NOT assume Natasha's expected
mapping (MORA/NOCA/OLYM V2.1.1 -> Protected Areas; LEWI -> original 10-mile-buffer
AOI) is correct; verify it from the actual files.

For each of the 4 currently-used Task 1 source datasets, AND the 2 superseded
V2B/V2B-2 legacy datasets (loaded directly from data/raw/, not part of the
processed/standardized product), this script reports:
  - exact source file, feature count, area, temporal coverage
  - containment (% count, % area) against BOTH NCCN AOI generations
    (original 10-mile-buffer LPa01; later Protected Areas -- MORA/NOCA/OLYM only)
  - outside-AOI polygon detail: count not fully within, how many have a
    genuinely-outside centroid (vs. merely straddling the boundary), max % of
    a polygon's own area outside, and same-row attribute values
    (Event_type/In_Park/Dist_name/change_class) to flag any obvious explanation

Read-only assessment. Does not change subregion definitions, rerun
rasterization, or alter any pixel-summary table.
"""

import geopandas as gpd
import pandas as pd

from rasterize_common import REPO_ROOT, PROCESSED, QA_DIR

NCCN_AOI_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "nps" / "Prithvi_NCCN"
NCCN_RAW_DIR = REPO_ROOT / "data" / "raw" / "nccn"


def load_aois(target_crs):
    lpa01 = gpd.read_file(NCCN_AOI_DIR / "LPa01_LEWI_MORA_NOCA_OLYM.shp").to_crs(target_crs)
    lpa01_by_park = lpa01.dissolve(by="PARK_CODE").geometry  # LEWI: union of N+S

    protected = {}
    for p in ["MORA", "NOCA", "OLYM"]:
        g = gpd.read_file(NCCN_AOI_DIR / f"{p}_USFS_NPS_StudyArea.shp")
        g["geometry"] = g.geometry.buffer(0)
        protected[p] = g.to_crs(target_crs).geometry.union_all()

    return lpa01_by_park, protected


def outside_detail(sub, aoi_geom, label):
    """For polygons not fully within aoi_geom: what fraction of each polygon's OWN
    area sits outside (pct_own_area_outside), and whether its centroid is genuinely
    outside the AOI (centroid_dist_to_aoi_m > 0) vs. merely boundary-straddling.

    NOTE: an earlier version used hausdorff_distance(g.difference(aoi_geom), aoi_geom)
    as a "how far outside" metric and produced spurious tens-of-km values for
    polygons independently confirmed (direct centroid check) to be 0m outside --
    an artifact of GEOS Hausdorff distance on the difference() of complex
    multi-part (24-55 parcel) unioned geometries, not a real excursion. Do not
    reintroduce a Hausdorff-based distance here without re-verifying against a
    direct centroid-distance spot check first.
    """
    outside_mask = ~sub.geometry.within(aoi_geom)
    outside = sub[outside_mask].copy()
    if len(outside) == 0:
        return outside, "none"
    outside["own_area_m2"] = outside.geometry.area
    outside["pct_own_area_outside"] = 100 * outside.geometry.difference(aoi_geom).area / outside["own_area_m2"]
    outside["centroid_dist_to_aoi_m"] = outside.geometry.centroid.distance(aoi_geom)
    hint_cols = [c for c in ["Event_type", "In_Park", "Dist_name", "Chnge_type", "change_class"] if c in outside.columns]
    return outside, hint_cols


def summarize(sub, park, dataset_label, lpa_geom, prot_geom, year_col):
    total_area = sub.geometry.area.sum()
    total_count = len(sub)
    years = sub[year_col].dropna()
    year_range = f"{int(years.min())}-{int(years.max())}" if len(years) else "n/a"

    row = dict(
        dataset=dataset_label, park=park, feature_count=total_count,
        total_area_ha=round(total_area / 1e4, 1), year_range=year_range,
    )

    for aoi_name, aoi_geom in [("lpa01_10mi_buffer", lpa_geom), ("protected_areas", prot_geom)]:
        if aoi_geom is None:
            row[f"pct_count_in_{aoi_name}"] = None
            row[f"pct_area_in_{aoi_name}"] = None
            row[f"n_outside_{aoi_name}"] = None
            row[f"n_centroid_outside_{aoi_name}"] = None
            row[f"max_centroid_dist_outside_m_{aoi_name}"] = None
            row[f"max_pct_own_area_outside_{aoi_name}"] = None
            continue
        area_in = sub.geometry.intersection(aoi_geom).area.sum()
        count_in = sub.geometry.intersects(aoi_geom).sum()
        row[f"pct_area_in_{aoi_name}"] = round(100 * area_in / total_area, 2)
        row[f"pct_count_in_{aoi_name}"] = round(100 * count_in / total_count, 2)

        outside, hint_cols = outside_detail(sub, aoi_geom, aoi_name)
        row[f"n_outside_{aoi_name}"] = len(outside)
        if len(outside):
            n_centroid_out = int((outside["centroid_dist_to_aoi_m"] > 0).sum())
            row[f"n_centroid_outside_{aoi_name}"] = n_centroid_out
            row[f"max_centroid_dist_outside_m_{aoi_name}"] = round(outside["centroid_dist_to_aoi_m"].max(), 1)
            row[f"max_pct_own_area_outside_{aoi_name}"] = round(outside["pct_own_area_outside"].max(), 1)
        else:
            row[f"n_centroid_outside_{aoi_name}"] = 0
            row[f"max_centroid_dist_outside_m_{aoi_name}"] = 0.0
            row[f"max_pct_own_area_outside_{aoi_name}"] = 0.0

    return row


def main():
    nccn = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")
    nccn["geometry"] = nccn.geometry.buffer(0)

    lpa01_by_park, protected = load_aois(nccn.crs)

    rows = []
    outside_rows = []

    # --- currently-used Task 1 datasets ---
    for park, ds_label in [
        ("MORA", "MORA_1987_2017_V2_1_1_UTM"),
        ("NOCA", "NOCA_1987_2017_V2_1_1_UTM"),
        ("OLYM", "OLYM_1987_2017_V2_1_1_UTM"),
        ("LEWI", "LEWI_1985_2011_Report_UTM"),
    ]:
        sub = nccn[(nccn.park_code == park) & (nccn.source_dataset == ds_label)].copy()
        assert len(sub) > 0, f"no rows for {ds_label}"
        lpa_geom = lpa01_by_park.loc[park]
        prot_geom = protected.get(park)
        row = summarize(sub, park, ds_label, lpa_geom, prot_geom, "year")
        row["generation"] = "later (Protected Areas)" if park != "LEWI" else "original (10-mi buffer)"
        row["used_in_task1"] = True
        rows.append(row)

        for aoi_name, aoi_geom in [("lpa01_10mi_buffer", lpa_geom), ("protected_areas", prot_geom)]:
            if aoi_geom is None:
                continue
            outside, hint_cols = outside_detail(sub, aoi_geom, aoi_name)
            if len(outside) == 0:
                continue
            keep_cols = ["year", "change_class"] + [c for c in hint_cols if c not in ("change_class",)]
            keep_cols = [c for c in keep_cols if c in outside.columns]
            od = outside[keep_cols + ["pct_own_area_outside", "centroid_dist_to_aoi_m"]].copy()
            od.insert(0, "aoi", aoi_name)
            od.insert(0, "dataset", ds_label)
            outside_rows.append(od)

    # --- superseded V2B legacy datasets (raw, not in processed product) ---
    v2b_noca = gpd.read_file(NCCN_RAW_DIR / "V2B" / "NOCA_1985_2009_V2B_UTM.shp")
    v2b_olym = gpd.read_file(NCCN_RAW_DIR / "V2B-2" / "OLYM_1985_2010_V2B_UTM.shp")
    for park, gdf, ds_label in [("NOCA", v2b_noca, "NOCA_1985_2009_V2B_UTM (legacy, superseded)"),
                                 ("OLYM", v2b_olym, "OLYM_1985_2010_V2B_UTM (legacy, superseded)")]:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.buffer(0)
        lpa_geom = lpa01_by_park.loc[park]
        prot_geom = protected.get(park)
        row = summarize(gdf, park, ds_label, lpa_geom, prot_geom, "AnalysisYr")
        row["generation"] = "original (10-mi buffer) -- legacy vintage"
        row["used_in_task1"] = False
        rows.append(row)

    df = pd.DataFrame(rows)
    out = QA_DIR / "nccn_aoi_generation_mapping_qa.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.name}")
    print(df.to_string())

    if outside_rows:
        outside_df = pd.concat(outside_rows, ignore_index=True)
        out2 = QA_DIR / "nccn_aoi_generation_mapping_outside_polygons.csv"
        outside_df.to_csv(out2, index=False)
        print(f"\nWrote {out2.name} ({len(outside_df)} rows)")


if __name__ == "__main__":
    main()
