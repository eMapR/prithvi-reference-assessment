"""
NCCN 30 m reference-grid pixel summaries.

subregion = park_code (attribute, not a boundary -- per instruction, NCCN has
no complete agreed containing boundary, so subregion identity comes directly
from the source's own park_code field, same as the existing vector analysis).
year = year. native_class = change_class.

See src/rasterize_common.py for the shared grid convention (30 m,
all_touched=False, anchored to the CRS's native (0,0) origin, classes
rasterized independently, unlabeled pixels never represented).

Outputs (outputs/qa/):
  nccn_subregion_year_class_pixels.csv   -- A: long-form authoritative table
  nccn_subregion_class_pixels_allyears.csv -- B: all-years summary
  nccn_subregion_year_pixels_summary.csv -- C: subregion x year summary
  nccn_multilabel_qa.csv                 -- D: multi-label QA
  nccn_zero_pixel_polygons.csv           -- validation: small/narrow polygons contributing 0 pixels
  nccn_rasterize_metadata.json           -- grid/metadata record
"""

import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from rasterize_common import PROCESSED, QA_DIR, RASTER_RES, grid_metadata, rasterize_bool, snap_transform

SOURCE = "NCCN"
PARQUET = PROCESSED / "nccn" / "nccn_standardized.parquet"
SUBREGION_COL = "park_code"
YEAR_COL = "year"
CLASS_COL = "change_class"

ZERO_PIXEL_AREA_THRESHOLD_M2 = 4 * RASTER_RES * RASTER_RES  # 4 pixels' worth


def find_zero_pixel_polygons(gdf):
    """Vectorized check (no per-polygon rasterize call): for polygons under
    the area threshold, test whether ANY 30 m grid-pixel center (on the
    shared, origin-anchored grid) falls inside the polygon. Larger polygons
    are assumed to contain a center (spot-checked separately)."""
    small = gdf[gdf.geometry.area < ZERO_PIXEL_AREA_THRESHOLD_M2].copy()
    if len(small) == 0:
        return small.assign(has_pixel=pd.Series(dtype=bool))

    results = []
    for geom in small.geometry.values:
        minx, miny, maxx, maxy = geom.bounds
        col_min = int(np.floor(minx / RASTER_RES))
        col_max = int(np.floor(maxx / RASTER_RES))
        row_min = int(np.floor(miny / RASTER_RES))
        row_max = int(np.floor(maxy / RASTER_RES))
        centers = []
        for c in range(col_min, col_max + 1):
            for r in range(row_min, row_max + 1):
                cx = (c + 0.5) * RASTER_RES
                cy = (r + 0.5) * RASTER_RES
                centers.append((cx, cy))
        if not centers:
            results.append(False)
            continue
        pts = shapely.points(np.array(centers))
        results.append(bool(shapely.contains(geom, pts).any()))
    small["has_pixel"] = results
    return small


def spot_check_large_polygons(gdf, n=200, seed=42):
    """Confirm the area-threshold assumption: a random sample of polygons
    ABOVE the zero-pixel-check threshold should essentially always contain
    at least one pixel center."""
    large = gdf[gdf.geometry.area >= ZERO_PIXEL_AREA_THRESHOLD_M2]
    if len(large) == 0:
        return 0, 0
    sample = large.sample(n=min(n, len(large)), random_state=seed)
    zero = 0
    for geom in sample.geometry.values:
        minx, miny, maxx, maxy = geom.bounds
        transform, w, h = snap_transform(minx, miny, maxx, maxy)
        mask = rasterize_bool([geom], transform, w, h)
        if not mask.any():
            zero += 1
    return zero, len(sample)


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    gdf = gpd.read_parquet(PARQUET)
    print(f"Loaded {len(gdf):,} {SOURCE} features, CRS={gdf.crs}")

    long_rows = []
    multilabel_rows = []

    n_groups = gdf.groupby([SUBREGION_COL, YEAR_COL]).ngroups
    print(f"Processing {n_groups} (subregion, year) groups...")

    for (subregion, year), grp in gdf.groupby([SUBREGION_COL, YEAR_COL]):
        classes_present = sorted(grp[CLASS_COL].dropna().unique())
        if not classes_present:
            continue
        minx, miny, maxx, maxy = grp.total_bounds
        transform, w, h = snap_transform(minx, miny, maxx, maxy)
        if w * h > 200_000_000:
            print(f"  WARNING: huge window for {subregion}/{year}: {w}x{h}")

        stack = np.zeros((len(classes_present), h, w), dtype=bool)
        for ci, cls in enumerate(classes_present):
            geoms = grp.loc[grp[CLASS_COL] == cls, "geometry"].values
            mask = rasterize_bool(geoms, transform, w, h)
            stack[ci] = mask
            pixel_count = int(mask.sum())
            long_rows.append(dict(
                subregion=subregion, year=int(year), native_class=cls,
                pixel_count=pixel_count, area_ha=round(pixel_count * 0.09, 4),
            ))

        class_count_per_pixel = stack.sum(axis=0)
        attributed = int((class_count_per_pixel >= 1).sum())
        single = int((class_count_per_pixel == 1).sum())
        multi = int((class_count_per_pixel > 1).sum())
        multilabel_rows.append(dict(
            subregion=subregion, year=int(year),
            attributed_pixels=attributed, single_label_pixels=single,
            multi_label_pixels=multi,
            pct_multi_label=round(100 * multi / attributed, 4) if attributed else 0.0,
        ))

    long_df = pd.DataFrame(long_rows)
    long_df.to_csv(QA_DIR / "nccn_subregion_year_class_pixels.csv", index=False)
    print(f"Wrote nccn_subregion_year_class_pixels.csv ({len(long_df)} rows)")

    allyears = long_df.groupby(["subregion", "native_class"]).agg(
        pixel_count=("pixel_count", "sum")
    ).reset_index()
    allyears["area_ha"] = (allyears["pixel_count"] * 0.09).round(4)
    allyears.to_csv(QA_DIR / "nccn_subregion_class_pixels_allyears.csv", index=False)
    print(f"Wrote nccn_subregion_class_pixels_allyears.csv ({len(allyears)} rows)")

    subyear = long_df.groupby(["subregion", "year"]).agg(
        total_pixel_count=("pixel_count", "sum")
    ).reset_index()
    subyear["total_area_ha"] = (subyear["total_pixel_count"] * 0.09).round(4)
    subyear.to_csv(QA_DIR / "nccn_subregion_year_pixels_summary.csv", index=False)
    print(f"Wrote nccn_subregion_year_pixels_summary.csv ({len(subyear)} rows)")

    ml_df = pd.DataFrame(multilabel_rows)
    ml_df.to_csv(QA_DIR / "nccn_multilabel_qa.csv", index=False)
    print(f"Wrote nccn_multilabel_qa.csv ({len(ml_df)} rows)")

    print("\nZero-pixel polygon check (polygons < 4-pixel area threshold)...")
    zero_check = find_zero_pixel_polygons(gdf)
    n_small = len(zero_check)
    n_zero = int((~zero_check["has_pixel"]).sum()) if n_small else 0
    zero_check[~zero_check["has_pixel"]][[SUBREGION_COL, YEAR_COL, CLASS_COL]].assign(
        area_m2=zero_check.loc[~zero_check["has_pixel"], "geometry"].area
    ).to_csv(QA_DIR / "nccn_zero_pixel_polygons.csv", index=False)
    print(f"  {n_small} polygons under {ZERO_PIXEL_AREA_THRESHOLD_M2:.0f} m2; {n_zero} contribute zero pixels")
    spot_zero, spot_n = spot_check_large_polygons(gdf)
    print(f"  Spot check of {spot_n} larger polygons: {spot_zero} contributed zero pixels (should be ~0)")

    total_pixels = int(long_df.groupby(["subregion", "year"])["pixel_count"].sum().sum())
    # NOTE: this sums pixel_count across classes too, so it OVER-counts multi-label
    # pixels (a multi-label pixel is counted once per class it belongs to). See
    # the multilabel QA table for the true union pixel count per subregion-year.
    print(f"\nTotal pixel_count summed across all rows (double-counts multi-label pixels by design of the long table): {total_pixels:,}")
    total_attributed_union = int(ml_df["attributed_pixels"].sum())
    print(f"Total attributed (union, no double count) pixel-years: {total_attributed_union:,}")

    meta = grid_metadata(SOURCE, gdf.crs, SUBREGION_COL, YEAR_COL, CLASS_COL,
                          notes="subregion is the park_code attribute; no boundary geometry used for subregion membership")
    with open(QA_DIR / "nccn_rasterize_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote nccn_rasterize_metadata.json")

    print(f"\nElapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
