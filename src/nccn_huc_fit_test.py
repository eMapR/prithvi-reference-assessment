"""
Exploratory spatial-fit test: does the NCCN reference-data footprint appear
to have been organized around HUC watersheds?

This is diagnostic ONLY. It does not modify data/processed/nccn/, does not
create a study-area boundary product, and does not touch GLKN or ADS. It
reads the already-standardized NCCN reference data and both HUC boundary
exports (HUC10 and, as of 2026-09-23, HUC12), and writes QA reports to
outputs/qa/.

Inputs:
    data/processed/nccn/nccn_standardized.parquet   (read-only)
    data/raw/boundaries/nps/Prithvi_NCCN/NCCN_HUC10.shp   (read-only)
    data/raw/boundaries/nps/Prithvi_NCCN/NCCN_HUC12.shp   (read-only)

Method notes:
  - Working CRS: EPSG:26910 (same as the NCCN processing step), so area
    figures are directly comparable to outputs/qa/nccn_processing_report.md.
  - HUC10 and HUC12 are run through the exact same analysis function
    (analyze_park), parameterized only by which HUC layer and ID/name
    columns to use, so the two are directly comparable and the HUC10 logic
    is not duplicated.
  - "Edge alignment" test: a per-park diagnostic union of the reference
    polygons, buffered by a small tolerance and dissolved, is built ONLY to
    approximate the monitored footprint's outer edge for comparison against
    HUC boundary lines -- this buffered/dissolved shape is diagnostic only,
    held in memory, never written to disk, and is not a proposed
    study-area boundary. Buffer/dissolve distance and edge-coincidence
    tolerance are identical for HUC10 and HUC12 so the two scores are
    directly comparable, and are heuristic choices, not derived values.
  - Nesting check: each selected HUC12's parent HUC10 is derived from the
    standard USGS convention that a HUC12 code's first 10 digits are its
    parent HUC10 code -- verified directly against the HUC10 file (all 117
    HUC10s are represented as a parent of at least one of the 469 HUC12s;
    no orphans), not assumed.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
RAW = REPO_ROOT / "data" / "raw"
QA_DIR = REPO_ROOT / "outputs" / "qa"

WORKING_CRS = "EPSG:26910"
HUC_DIR = RAW / "boundaries" / "nps" / "Prithvi_NCCN"
HUC10_PATH = HUC_DIR / "NCCN_HUC10.shp"
HUC12_PATH = HUC_DIR / "NCCN_HUC12.shp"

# Diagnostic-only parameters (see module docstring). Identical for HUC10 and
# HUC12 so the two edge-alignment scores are directly comparable.
DISSOLVE_BUFFER_M = 250
EDGE_COINCIDENCE_TOL_M = 100
LOW_FILL_THRESHOLD_PCT = 1.0  # used for the "artificial boundary" diagnostic

PARKS = ["MORA", "NOCA", "OLYM", "LEWI"]


def log(msg=""):
    print(msg)


def load_reference():
    gdf = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")
    assert str(gdf.crs).upper().find("26910") >= 0
    return gdf


def load_huc(path, id_col):
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(WORKING_CRS)
    gdf[id_col] = gdf[id_col].astype(str)
    return gdf


def edge_alignment_fraction(ref_polys, huc_union_boundary):
    """Fraction of the (buffered/dissolved) reference-extent boundary length
    that falls within EDGE_COINCIDENCE_TOL_M of a HUC boundary line.
    Diagnostic only -- see module docstring. Same method for HUC10/HUC12."""
    if len(ref_polys) == 0:
        return None, 0.0
    dissolved = unary_union(ref_polys.buffer(DISSOLVE_BUFFER_M))
    ext_boundary = dissolved.boundary
    total_len = ext_boundary.length
    if total_len == 0:
        return dissolved, 0.0
    huc_boundary_buffer = huc_union_boundary.buffer(EDGE_COINCIDENCE_TOL_M)
    aligned_part = ext_boundary.intersection(huc_boundary_buffer)
    aligned_len = aligned_part.length
    return dissolved, (aligned_len / total_len) if total_len else 0.0


def analyze_park(park_code, ref_all, huc_gdf, id_col, name_col):
    """Generic per-park HUC fit analysis -- used identically for HUC10 and
    HUC12 (parameterized by which layer/columns), so the methodology is not
    duplicated between the two."""
    ref = ref_all[ref_all["park_code"] == park_code].copy()
    total_ref_area = float(ref.geometry.area.sum())

    intersecting_mask = huc_gdf.geometry.apply(lambda h: ref.geometry.intersects(h).any())
    selected = huc_gdf[intersecting_mask].copy()

    huc_union = unary_union(selected.geometry.values) if len(selected) else None

    rows = []
    for _, huc in selected.iterrows():
        inter_area = float(ref.geometry.intersection(huc.geometry).area.sum())
        rows.append({
            "huc_id": huc[id_col],
            "name": huc[name_col],
            "hutype": huc.get("hutype", None),
            "huc_area_m2": float(huc.geometry.area),
            "ref_area_within_huc_m2": inter_area,
            "pct_of_park_ref_area": round(100 * inter_area / total_ref_area, 2) if total_ref_area else 0.0,
            "pct_of_huc_filled": round(100 * inter_area / huc.geometry.area, 3) if huc.geometry.area else 0.0,
        })
    per_huc = pd.DataFrame(rows).sort_values("ref_area_within_huc_m2", ascending=False)

    area_within_selected = float(ref.geometry.intersection(huc_union).area.sum()) if huc_union is not None else 0.0
    area_outside_selected = total_ref_area - area_within_selected

    dissolved_ref, align_frac = edge_alignment_fraction(
        ref.geometry, huc_union.boundary if huc_union is not None else None
    )

    low_fill_count = int((per_huc["pct_of_huc_filled"] < LOW_FILL_THRESHOLD_PCT).sum()) if len(per_huc) else 0

    summary = {
        "park_code": park_code,
        "total_reference_polygons": len(ref),
        "total_reference_area_m2": total_ref_area,
        "n_huc_intersecting": len(selected),
        "area_within_selected_hucs_m2": area_within_selected,
        "area_outside_selected_hucs_m2": area_outside_selected,
        "pct_area_within_selected_hucs": round(100 * area_within_selected / total_ref_area, 2) if total_ref_area else 0.0,
        "pct_area_outside_selected_hucs": round(100 * area_outside_selected / total_ref_area, 2) if total_ref_area else 0.0,
        "edge_alignment_fraction": round(align_frac, 3) if align_frac is not None else None,
        "low_fill_huc_count": low_fill_count,
        "low_fill_huc_pct_of_selected": round(100 * low_fill_count / len(selected), 1) if len(selected) else 0.0,
    }
    return summary, per_huc


def nesting_check(park_code, huc12_per_huc, huc10_per_huc, huc10_all):
    """For this park's selected HUC12s, derive each one's parent HUC10 (first
    10 digits of the HUC12 code, the standard USGS nesting convention) and
    compare against the HUC10s independently found to intersect the same
    park's reference data. Reports whether HUC12 selection is a clean nested
    subset of the HUC10 selection, or whether it disagrees."""
    huc12_ids = huc12_per_huc["huc_id"].astype(str)
    parents = huc12_ids.str[:10]
    distinct_parents = sorted(parents.unique())

    huc10_selected_ids = set(huc10_per_huc["huc_id"].astype(str))
    parents_not_in_huc10_selection = sorted(set(distinct_parents) - huc10_selected_ids)
    huc10_selected_not_parent = sorted(huc10_selected_ids - set(distinct_parents))

    return {
        "park_code": park_code,
        "n_huc12_selected": len(huc12_ids),
        "n_distinct_huc10_parents_of_selected_huc12": len(distinct_parents),
        "n_huc10_selected_independently": len(huc10_selected_ids),
        "huc10_parents_not_independently_selected": parents_not_in_huc10_selection,
        "huc10_independently_selected_but_no_child_huc12_selected": huc10_selected_not_parent,
        "nesting_is_clean": len(parents_not_in_huc10_selection) == 0 and len(huc10_selected_not_parent) == 0,
    }


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 70)
    log("NCCN HUC SPATIAL-FIT TEST -- HUC10 and HUC12 (diagnostic only)")
    log("=" * 70)

    ref_all = load_reference()
    huc10 = load_huc(HUC10_PATH, "huc10")
    huc12 = load_huc(HUC12_PATH, "huc12")
    log(f"\nLoaded {len(ref_all)} standardized NCCN reference polygons.")
    log(f"Loaded {len(huc10)} HUC10 candidate watersheds.")
    log(f"Loaded {len(huc12)} HUC12 candidate watersheds.")

    all_summaries_10, all_summaries_12 = [], []
    all_per_huc_10, all_per_huc_12 = [], []
    all_nesting = []

    for park in PARKS:
        log("\n" + "-" * 70)
        log(f"{park}")
        log("-" * 70)

        s10, ph10 = analyze_park(park, ref_all, huc10, "huc10", "name")
        ph10.insert(0, "park_code", park)
        all_summaries_10.append(s10)
        all_per_huc_10.append(ph10)

        s12, ph12 = analyze_park(park, ref_all, huc12, "huc12", "name")
        ph12.insert(0, "park_code", park)
        all_summaries_12.append(s12)
        all_per_huc_12.append(ph12)

        log(f"  HUC10: n={s10['n_huc_intersecting']}  coverage={s10['pct_area_within_selected_hucs']}%  "
            f"edge_alignment={s10['edge_alignment_fraction']}  "
            f"low_fill(<{LOW_FILL_THRESHOLD_PCT}%)={s10['low_fill_huc_count']} ({s10['low_fill_huc_pct_of_selected']}%)")
        log(f"  HUC12: n={s12['n_huc_intersecting']}  coverage={s12['pct_area_within_selected_hucs']}%  "
            f"edge_alignment={s12['edge_alignment_fraction']}  "
            f"low_fill(<{LOW_FILL_THRESHOLD_PCT}%)={s12['low_fill_huc_count']} ({s12['low_fill_huc_pct_of_selected']}%)")

        nest = nesting_check(park, ph12, ph10, huc10)
        all_nesting.append(nest)
        log(f"  Nesting: {nest['n_huc12_selected']} selected HUC12s -> "
            f"{nest['n_distinct_huc10_parents_of_selected_huc12']} distinct HUC10 parents "
            f"(vs {nest['n_huc10_selected_independently']} HUC10s independently selected). "
            f"Clean nesting: {nest['nesting_is_clean']}")
        if not nest["nesting_is_clean"]:
            log(f"    HUC10 parents of selected HUC12 not independently selected: "
                f"{nest['huc10_parents_not_independently_selected']}")
            log(f"    HUC10 independently selected but no child HUC12 selected: "
                f"{nest['huc10_independently_selected_but_no_child_huc12_selected']}")

    pd.DataFrame(all_summaries_10).to_csv(QA_DIR / "nccn_huc10_fit_summary.csv", index=False)
    pd.concat(all_per_huc_10, ignore_index=True).to_csv(QA_DIR / "nccn_huc10_fit_per_huc.csv", index=False)
    pd.DataFrame(all_summaries_12).to_csv(QA_DIR / "nccn_huc12_fit_summary.csv", index=False)
    pd.concat(all_per_huc_12, ignore_index=True).to_csv(QA_DIR / "nccn_huc12_fit_per_huc.csv", index=False)

    nesting_df = pd.DataFrame(all_nesting)
    nesting_df["huc10_parents_not_independently_selected"] = nesting_df[
        "huc10_parents_not_independently_selected"].apply(lambda x: ";".join(x))
    nesting_df["huc10_independently_selected_but_no_child_huc12_selected"] = nesting_df[
        "huc10_independently_selected_but_no_child_huc12_selected"].apply(lambda x: ";".join(x))
    nesting_df.to_csv(QA_DIR / "nccn_huc10_huc12_nesting.csv", index=False)

    # Direct HUC10 vs HUC12 comparison table
    comp = pd.DataFrame(all_summaries_10).set_index("park_code")[
        ["n_huc_intersecting", "pct_area_within_selected_hucs", "edge_alignment_fraction", "low_fill_huc_pct_of_selected"]
    ].add_suffix("_huc10")
    comp12 = pd.DataFrame(all_summaries_12).set_index("park_code")[
        ["n_huc_intersecting", "pct_area_within_selected_hucs", "edge_alignment_fraction", "low_fill_huc_pct_of_selected"]
    ].add_suffix("_huc12")
    comparison = comp.join(comp12).reindex(PARKS)
    comparison.to_csv(QA_DIR / "nccn_huc10_vs_huc12_comparison.csv")

    log("\n" + "=" * 70)
    log("HUC10 vs HUC12 comparison")
    log("=" * 70)
    log(comparison.to_string())

    log("\n" + "=" * 70)
    log("DONE")
    log("=" * 70)

    return comparison, nesting_df


if __name__ == "__main__":
    main()
