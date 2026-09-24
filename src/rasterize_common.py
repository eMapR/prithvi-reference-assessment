"""
Shared rasterization helpers for the reference-data 30 m grid summaries.

IMPORTANT TERMINOLOGY: pixels produced here are "30 m reference-grid pixels"
-- a project-defined grid used ONLY to quantify the spatial amount and
distribution of attributed reference labels at a consistent Landsat-scale
resolution. They are NOT native Landsat pixels, NOT HLS pixels, and NOT
Prithvi model input pixels. No Prithvi/HLS imagery-ingestion grid convention
was found anywhere in this project's available materials (see the grid-
alignment investigation in the assessment notebook / conversation record).
Alignment against the actual HLS/Prithvi ingestion grid MUST be revisited
before these pixels are used to generate real model training/eval samples.

Grid convention (applies uniformly, same rule for every source):
  - resolution: 30 m
  - all_touched = False (pixel-CENTER inclusion only)
  - pixel edges anchored to exact 30 m multiples of each source's own
    processed CRS native (0, 0) origin -- never to an AOI/window bounding
    box -- so every rasterization within one source/CRS shares identical
    pixel boundaries regardless of which subregion/year/class window is
    being computed.
  - each native class is rasterized INDEPENDENTLY (no mutually-exclusive
    "winner" raster) -- a pixel may be positive for more than one class in
    the same year where the source attribution itself supports that.
  - unlabeled pixels are simply absent from the output tables -- never
    represented as an explicit "no_change"/background class.

Never writes to data/raw/. Reads only already-processed parquets.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
import shapely
from affine import Affine

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"
RASTER_RES = 30.0  # meters


def snap_transform(minx, miny, maxx, maxy, res=RASTER_RES, pad_pixels=1):
    """Return (transform, width, height) for a window covering
    [minx,maxx] x [miny,maxy], with pixel edges anchored to exact multiples
    of `res` from the CRS's native (0, 0) origin (NOT the window bounds).
    `pad_pixels` adds a small margin so polygons touching the raw bounds
    aren't clipped by floating-point edge effects.
    """
    col_min = int(np.floor(minx / res)) - pad_pixels
    col_max = int(np.floor(maxx / res)) + pad_pixels
    row_min = int(np.floor(miny / res)) - pad_pixels
    row_max = int(np.floor(maxy / res)) + pad_pixels

    x0 = col_min * res
    y1 = (row_max + 1) * res  # top edge (north)

    width = col_max - col_min + 1
    height = row_max - row_min + 1
    transform = Affine(res, 0, x0, 0, -res, y1)
    return transform, width, height


def rasterize_bool(geoms, transform, width, height, all_touched=False):
    """Boolean occupancy mask: True where a pixel CENTER (all_touched=False)
    falls inside any of `geoms`. Empty geoms -> all-False array of the
    requested shape (avoids rasterio's error on an empty shape list)."""
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms or width <= 0 or height <= 0:
        return np.zeros((max(height, 0), max(width, 0)), dtype=bool)
    arr = rasterio.features.rasterize(
        [(g, 1) for g in geoms],
        out_shape=(height, width),
        transform=transform,
        all_touched=all_touched,
        fill=0,
        dtype="uint8",
    )
    return arr.astype(bool)


def rasterize_ads_source(gdf, boundaries, boundary_id_col, boundary_name_col, id_col, year_col, class_col, label):
    """Shared ADS R6/R10 driver: boundary-based (NOT centroid-based) subregion
    pixel counting. For each subregion boundary polygon, finds candidate
    attributed polygons via a spatial-intersects filter, then for each
    (subregion, year) rasterizes each present native_class independently and
    ANDs it with that subregion's own boundary mask on the SAME local
    window -- so a polygon straddling two subregions correctly contributes
    pixels to both, split by actual pixel-center location, not by which
    subregion its centroid happened to fall in.

    Returns (long_df, multilabel_df, zero_pixel_summary_dict).
    """
    long_rows, multilabel_rows = [], []
    zero_pixel_total_checked = 0
    zero_pixel_total_zero = 0

    sindex = gdf.sindex
    for _, bnd_row in boundaries.iterrows():
        subregion_id = bnd_row[boundary_id_col]
        subregion_name = bnd_row[boundary_name_col]
        bnd_geom = bnd_row.geometry

        candidate_idx = list(sindex.query(bnd_geom, predicate="intersects"))
        if not candidate_idx:
            continue
        candidates = gdf.iloc[candidate_idx]
        n_groups = candidates.groupby(year_col).ngroups
        print(f"  [{label}] subregion {subregion_id} ({subregion_name}): {len(candidates):,} candidate polygons, {n_groups} years")

        for year, grp in candidates.groupby(year_col):
            classes_present = sorted(grp[class_col].dropna().unique())
            if not classes_present:
                continue
            minx, miny, maxx, maxy = grp.total_bounds
            transform, w, h = snap_transform(minx, miny, maxx, maxy)
            if w <= 0 or h <= 0:
                continue

            subregion_mask = rasterize_bool([bnd_geom], transform, w, h)
            if not subregion_mask.any():
                continue

            # Memory note: do NOT keep one boolean layer per class in memory
            # at once (n_classes x h x w) -- for large, widely-scattered
            # subregions (e.g. ADS R10's largest HUC6 basins) that stack can
            # reach tens of GB and gets OOM-killed. Instead keep a single
            # running per-pixel class-count array (uint8, plenty of headroom
            # for realistic class counts) and discard each class's boolean
            # layer immediately after counting it.
            class_count_per_pixel = np.zeros((h, w), dtype=np.uint8)
            for cls in classes_present:
                geoms = grp.loc[grp[class_col] == cls, "geometry"].values
                masked = rasterize_bool(geoms, transform, w, h) & subregion_mask
                pixel_count = int(masked.sum())
                if pixel_count == 0:
                    continue
                long_rows.append(dict(
                    subregion=subregion_id, subregion_name=subregion_name, year=int(year),
                    native_class=cls, pixel_count=pixel_count, area_ha=round(pixel_count * 0.09, 4),
                ))
                class_count_per_pixel += masked
                del masked

            attributed = int((class_count_per_pixel >= 1).sum())
            single = int((class_count_per_pixel == 1).sum())
            multi = int((class_count_per_pixel > 1).sum())
            multilabel_rows.append(dict(
                subregion=subregion_id, subregion_name=subregion_name, year=int(year),
                attributed_pixels=attributed, single_label_pixels=single,
                multi_label_pixels=multi,
                pct_multi_label=round(100 * multi / attributed, 4) if attributed else 0.0,
            ))

    return pd.DataFrame(long_rows), pd.DataFrame(multilabel_rows)


def find_zero_pixel_polygons(gdf, class_col, subregion_col, year_col, area_threshold_m2):
    small = gdf[gdf.geometry.area < area_threshold_m2].copy()
    if len(small) == 0:
        return small.assign(has_pixel=pd.Series(dtype=bool))
    results = []
    for geom in small.geometry.values:
        minx, miny, maxx, maxy = geom.bounds
        col_min, col_max = int(np.floor(minx / RASTER_RES)), int(np.floor(maxx / RASTER_RES))
        row_min, row_max = int(np.floor(miny / RASTER_RES)), int(np.floor(maxy / RASTER_RES))
        centers = [((c + 0.5) * RASTER_RES, (r + 0.5) * RASTER_RES)
                   for c in range(col_min, col_max + 1) for r in range(row_min, row_max + 1)]
        if not centers:
            results.append(False)
            continue
        pts = shapely.points(np.array(centers))
        results.append(bool(shapely.contains(geom, pts).any()))
    small["has_pixel"] = results
    return small


def grid_metadata(source, crs, subregion_field, year_field, class_field, notes=""):
    return {
        "source": source,
        "reference_grid_resolution_m": RASTER_RES,
        "all_touched": False,
        "pixel_inclusion_rule": "pixel-center (all_touched=False)",
        "grid_alignment": "anchored to exact 30 m multiples of the CRS's own native (0,0) origin, not per-window bounds",
        "crs": str(crs),
        "subregion_field": subregion_field,
        "year_field": year_field,
        "native_class_field": class_field,
        "overlap_treatment": "each native class rasterized independently; a pixel may be positive for >1 class in the same year",
        "unlabeled_treatment": "unlabeled pixels are absent from output tables, never represented as an explicit no-change/background class",
        "terminology_note": "these are project-defined '30 m reference-grid pixels' for reference-label characterization only -- NOT native Landsat/HLS/Prithvi pixels; alignment must be revisited against the actual HLS/Prithvi ingestion grid before use in model training/eval sample generation",
        "notes": notes,
    }
