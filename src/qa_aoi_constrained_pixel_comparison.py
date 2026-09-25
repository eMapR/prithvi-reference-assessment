"""
QA (2026-09-24 follow-up): quantify one methodological choice BEFORE changing
any authoritative Task 1 pixel totals -- for NCCN and GLKN, compare:

  (A) EXISTING source-assigned rasterized counts (already-authoritative
      outputs: outputs/qa/nccn_subregion_year_class_pixels.csv +
      nccn_multilabel_qa.csv; outputs/qa/glkn_subregion_year_class_pixels_primary.csv
      + glkn_multilabel_qa_primary.csv) -- pixel membership determined purely
      by which polygon a pixel center falls in, no AOI constraint.
  (B) AOI-CONSTRAINED counts -- the SAME polygons, SAME per-(subregion,year)
      window and grid, SAME pixel-center rule, but ANDed against a rasterized
      mask of the subregion's own authoritative study-area AOI (verified
      mapping from the prior QA pass, src/qa_nccn_aoi_generation_mapping.py):

        NCCN MORA/NOCA/OLYM (V2.1.1) -> {park} Protected Areas
        NCCN LEWI (1985-2011)        -> LPa01 LEWI (N+S union)
        GLKN (all 7 park_code)       -> matching GLKN_LandTrendr_AOIs feature

      NCCN V2B/V2B-2 (superseded) are excluded, per instruction -- they are
      not part of nccn_standardized.parquet in the first place.

This directly reuses the boundary-AND-mask pattern already established for
ADS R6/R10 (rasterize_common.rasterize_ads_source) -- same grid, same
pixel-center rule, only the membership mask differs. Does NOT touch or
overwrite any existing authoritative output; writes new, separate
"aoi_constrained" QA files and a diff/comparison table.

Also computes each authoritative AOI's own total 30 m reference-grid pixel
count/area (the study-area denominator) -- NOT used to redefine the existing
spatial-prevalence denominator, per instruction.
"""

import time

import geopandas as gpd
import numpy as np
import pandas as pd

from rasterize_common import PROCESSED, QA_DIR, REPO_ROOT, rasterize_bool, snap_transform

NCCN_AOI_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "nps" / "Prithvi_NCCN"
GLKN_AOI_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "glkn"

GLKN_PARKS = ["APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"]


def load_nccn_aois(target_crs):
    lpa01 = gpd.read_file(NCCN_AOI_DIR / "LPa01_LEWI_MORA_NOCA_OLYM.shp").to_crs(target_crs)
    lpa01_by_park = lpa01.dissolve(by="PARK_CODE").geometry
    aoi = {"LEWI": lpa01_by_park.loc["LEWI"]}
    for p in ["MORA", "NOCA", "OLYM"]:
        g = gpd.read_file(NCCN_AOI_DIR / f"{p}_USFS_NPS_StudyArea.shp")
        g["geometry"] = g.geometry.buffer(0)
        aoi[p] = g.to_crs(target_crs).geometry.union_all()
    return aoi


def load_glkn_aois(target_crs):
    g = gpd.read_file(GLKN_AOI_DIR / "GLKN_LandTrendr_AOIs.shp")
    g["park_upper"] = g["park"].str.upper()
    g["geometry"] = g.geometry.buffer(0)
    g = g.to_crs(target_crs)
    return {row.park_upper: row.geometry for row in g.itertuples() if row.park_upper in GLKN_PARKS}


def rasterize_constrained(gdf, subregion_col, year_col, class_col, aoi_by_subregion, label):
    """Same structure as rasterize_common.rasterize_ads_source, but the mask
    is a fixed per-subregion AOI (not a spatially-joined boundary set) --
    subregion identity here is already an attribute (park_code), matching
    how rasterize_nccn.py / rasterize_glkn.py originally grouped."""
    long_rows, multilabel_rows = [], []
    for (subregion, year), grp in gdf.groupby([subregion_col, year_col]):
        if subregion not in aoi_by_subregion:
            continue
        classes_present = sorted(grp[class_col].dropna().unique())
        if not classes_present:
            continue
        minx, miny, maxx, maxy = grp.total_bounds
        transform, w, h = snap_transform(minx, miny, maxx, maxy)
        if w <= 0 or h <= 0:
            continue

        aoi_mask = rasterize_bool([aoi_by_subregion[subregion]], transform, w, h)

        class_count_per_pixel = np.zeros((h, w), dtype=np.uint8)
        for cls in classes_present:
            geoms = grp.loc[grp[class_col] == cls, "geometry"].values
            masked = rasterize_bool(geoms, transform, w, h) & aoi_mask
            pixel_count = int(masked.sum())
            if pixel_count == 0:
                continue
            long_rows.append(dict(
                subregion=subregion, year=int(year), native_class=cls,
                pixel_count=pixel_count, area_ha=round(pixel_count * 0.09, 4),
            ))
            class_count_per_pixel += masked
            del masked

        attributed = int((class_count_per_pixel >= 1).sum())
        single = int((class_count_per_pixel == 1).sum())
        multi = int((class_count_per_pixel > 1).sum())
        multilabel_rows.append(dict(
            subregion=subregion, year=int(year),
            attributed_pixels=attributed, single_label_pixels=single,
            multi_label_pixels=multi,
            pct_multi_label=round(100 * multi / attributed, 4) if attributed else 0.0,
        ))
    print(f"  [{label}] done: {len(long_rows)} class rows, {len(multilabel_rows)} subregion-year rows")
    return pd.DataFrame(long_rows), pd.DataFrame(multilabel_rows)


def aoi_own_pixel_counts(aoi_by_subregion, label):
    rows = []
    for subregion, geom in aoi_by_subregion.items():
        minx, miny, maxx, maxy = geom.bounds
        transform, w, h = snap_transform(minx, miny, maxx, maxy)
        mask = rasterize_bool([geom], transform, w, h)
        n = int(mask.sum())
        rows.append(dict(source=label, subregion=subregion, aoi_pixel_count=n, aoi_area_ha=round(n * 0.09, 1)))
    return pd.DataFrame(rows)


def compare(existing_long, existing_ml, constrained_long, constrained_ml, subregions, label):
    # --- subregion-level: attributed pixel-years (sum over years) ---
    ex_py = existing_ml[existing_ml.subregion.isin(subregions)].groupby("subregion")["attributed_pixels"].sum()
    co_py = constrained_ml.groupby("subregion")["attributed_pixels"].sum() if len(constrained_ml) else pd.Series(dtype=int)
    py_rows = []
    for sub in subregions:
        ex = int(ex_py.get(sub, 0))
        co = int(co_py.get(sub, 0))
        diff = co - ex
        py_rows.append(dict(
            source=label, subregion=sub,
            existing_attributed_pixel_years=ex, aoi_constrained_attributed_pixel_years=co,
            abs_diff=diff, pct_diff=round(100 * diff / ex, 3) if ex else None,
        ))
    py_df = pd.DataFrame(py_rows)

    # --- subregion x class: all-years pixel_count ---
    ex_cls = existing_long[existing_long.subregion.isin(subregions)].groupby(
        ["subregion", "native_class"])["pixel_count"].sum().rename("existing_pixel_count")
    co_cls = (constrained_long.groupby(["subregion", "native_class"])["pixel_count"].sum().rename("aoi_constrained_pixel_count")
              if len(constrained_long) else pd.Series(dtype=int, name="aoi_constrained_pixel_count"))
    cls_df = pd.concat([ex_cls, co_cls], axis=1).fillna(0).astype(int).reset_index()
    cls_df["abs_diff"] = cls_df["aoi_constrained_pixel_count"] - cls_df["existing_pixel_count"]
    cls_df["pct_diff"] = cls_df.apply(
        lambda r: round(100 * r["abs_diff"] / r["existing_pixel_count"], 3) if r["existing_pixel_count"] else None, axis=1)
    cls_df.insert(0, "source", label)

    return py_df, cls_df


def main():
    t0 = time.time()

    # ---------------- NCCN ----------------
    print("=== NCCN ===")
    nccn = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")
    nccn["geometry"] = nccn.geometry.buffer(0)
    nccn_aois = load_nccn_aois(nccn.crs)

    nccn_constrained_long, nccn_constrained_ml = rasterize_constrained(
        nccn, "park_code", "year", "change_class", nccn_aois, "NCCN")
    nccn_constrained_long.to_csv(QA_DIR / "nccn_aoi_constrained_subregion_year_class_pixels.csv", index=False)
    nccn_constrained_ml.to_csv(QA_DIR / "nccn_aoi_constrained_multilabel_qa.csv", index=False)

    nccn_existing_long = pd.read_csv(QA_DIR / "nccn_subregion_year_class_pixels.csv")
    nccn_existing_ml = pd.read_csv(QA_DIR / "nccn_multilabel_qa.csv")
    nccn_py, nccn_cls = compare(nccn_existing_long, nccn_existing_ml, nccn_constrained_long, nccn_constrained_ml,
                                 ["MORA", "NOCA", "OLYM", "LEWI"], "NCCN")

    nccn_aoi_totals = aoi_own_pixel_counts(nccn_aois, "NCCN")

    # ---------------- GLKN ----------------
    print("\n=== GLKN ===")
    glkn = gpd.read_parquet(PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet")
    glkn["geometry"] = glkn.geometry.buffer(0)
    glkn_aois = load_glkn_aois(glkn.crs)
    glkn_primary = glkn[glkn["park_code"].isin(GLKN_PARKS)]  # agent_01 == change_class already, primary product

    glkn_constrained_long, glkn_constrained_ml = rasterize_constrained(
        glkn_primary, "park_code", "year", "change_class", glkn_aois, "GLKN-primary")
    glkn_constrained_long.to_csv(QA_DIR / "glkn_aoi_constrained_subregion_year_class_pixels_primary.csv", index=False)
    glkn_constrained_ml.to_csv(QA_DIR / "glkn_aoi_constrained_multilabel_qa_primary.csv", index=False)

    glkn_existing_long = pd.read_csv(QA_DIR / "glkn_subregion_year_class_pixels_primary.csv")
    glkn_existing_ml = pd.read_csv(QA_DIR / "glkn_multilabel_qa_primary.csv")
    glkn_py, glkn_cls = compare(glkn_existing_long, glkn_existing_ml, glkn_constrained_long, glkn_constrained_ml,
                                 GLKN_PARKS, "GLKN-primary")

    glkn_aoi_totals = aoi_own_pixel_counts(glkn_aois, "GLKN")

    # ---------------- combine + write ----------------
    py_all = pd.concat([nccn_py, glkn_py], ignore_index=True)
    cls_all = pd.concat([nccn_cls, glkn_cls], ignore_index=True)
    aoi_totals_all = pd.concat([nccn_aoi_totals, glkn_aoi_totals], ignore_index=True)

    py_all.to_csv(QA_DIR / "nccn_glkn_aoi_constraint_comparison_subregion.csv", index=False)
    cls_all.to_csv(QA_DIR / "nccn_glkn_aoi_constraint_comparison_class.csv", index=False)
    aoi_totals_all.to_csv(QA_DIR / "nccn_glkn_aoi_total_pixel_counts.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n--- Subregion-level: existing vs AOI-constrained attributed pixel-years ---")
    print(py_all.to_string(index=False))
    print("\n--- AOI's own total 30 m reference-grid pixel count/area (study-area denominator) ---")
    print(aoi_totals_all.to_string(index=False))
    print(f"\nWrote nccn_glkn_aoi_constraint_comparison_subregion.csv, "
          f"nccn_glkn_aoi_constraint_comparison_class.csv ({len(cls_all)} rows), "
          f"nccn_glkn_aoi_total_pixel_counts.csv")
    print(f"Elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
