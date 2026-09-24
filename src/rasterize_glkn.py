"""
GLKN 30 m reference-grid pixel summaries.

subregion = park_code (attribute). year = year.

Two parallel products, per instruction -- do not collapse the distinction:
  PRIMARY:      agent_01 only (= change_class, the existing standardized field)
  ALL-ATTRIBUTED: agent_01 + agent_02 + agent_03 (where populated), each
                  contributing the SAME polygon geometry to its own class
                  layer independently (agent multiplicity affects 1.43% of
                  confirmed polygons -- see outputs/qa/glkn_processing_report.md)

See src/rasterize_common.py for the shared grid convention.

Outputs (outputs/qa/), each produced twice (suffix _primary / _allagents):
  glkn_subregion_year_class_pixels_{suffix}.csv   -- A
  glkn_subregion_class_pixels_allyears_{suffix}.csv -- B
  glkn_subregion_year_pixels_summary_{suffix}.csv -- C
  glkn_multilabel_qa_{suffix}.csv                 -- D
  glkn_zero_pixel_polygons.csv                    -- validation (primary geometry set)
  glkn_rasterize_metadata.json
"""

import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from rasterize_common import PROCESSED, QA_DIR, RASTER_RES, grid_metadata, rasterize_bool, snap_transform

SOURCE = "GLKN"
PARQUET = PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet"
SUBREGION_COL = "park_code"
YEAR_COL = "year"

ZERO_PIXEL_AREA_THRESHOLD_M2 = 4 * RASTER_RES * RASTER_RES


def build_attribution_long(gdf, agent_cols=("agent_01", "agent_02", "agent_03")):
    """One row per (polygon, populated agent field). Keeps geometry, year,
    park_code, the class value, and which field it came from."""
    frames = []
    for col in agent_cols:
        sub = gdf[gdf[col].notna()][[SUBREGION_COL, YEAR_COL, "geometry", col]].copy()
        sub = sub.rename(columns={col: "native_class"})
        sub["attribution_field"] = col
        frames.append(sub)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=gdf.crs)


def rasterize_long_table(long_gdf, label):
    long_rows, multilabel_rows = [], []
    n_groups = long_gdf.groupby([SUBREGION_COL, YEAR_COL]).ngroups
    print(f"  [{label}] Processing {n_groups} (subregion, year) groups...")
    for (subregion, year), grp in long_gdf.groupby([SUBREGION_COL, YEAR_COL]):
        classes_present = sorted(grp["native_class"].dropna().unique())
        if not classes_present:
            continue
        minx, miny, maxx, maxy = grp.total_bounds
        transform, w, h = snap_transform(minx, miny, maxx, maxy)

        stack = np.zeros((len(classes_present), h, w), dtype=bool)
        for ci, cls in enumerate(classes_present):
            geoms = grp.loc[grp["native_class"] == cls, "geometry"].values
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
    return pd.DataFrame(long_rows), pd.DataFrame(multilabel_rows)


def write_products(long_df, ml_df, suffix):
    long_df.to_csv(QA_DIR / f"glkn_subregion_year_class_pixels_{suffix}.csv", index=False)
    allyears = long_df.groupby(["subregion", "native_class"]).agg(pixel_count=("pixel_count", "sum")).reset_index()
    allyears["area_ha"] = (allyears["pixel_count"] * 0.09).round(4)
    allyears.to_csv(QA_DIR / f"glkn_subregion_class_pixels_allyears_{suffix}.csv", index=False)
    subyear = long_df.groupby(["subregion", "year"]).agg(total_pixel_count=("pixel_count", "sum")).reset_index()
    subyear["total_area_ha"] = (subyear["total_pixel_count"] * 0.09).round(4)
    subyear.to_csv(QA_DIR / f"glkn_subregion_year_pixels_summary_{suffix}.csv", index=False)
    ml_df.to_csv(QA_DIR / f"glkn_multilabel_qa_{suffix}.csv", index=False)
    print(f"  [{suffix}] wrote A ({len(long_df)} rows), B ({len(allyears)} rows), C ({len(subyear)} rows), D ({len(ml_df)} rows)")


def find_zero_pixel_polygons(gdf):
    small = gdf[gdf.geometry.area < ZERO_PIXEL_AREA_THRESHOLD_M2].copy()
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


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    gdf = gpd.read_parquet(PARQUET)
    print(f"Loaded {len(gdf):,} {SOURCE} confirmed features, CRS={gdf.crs.to_epsg() or gdf.crs.srs}")

    long_gdf = build_attribution_long(gdf)
    n_primary = (long_gdf["attribution_field"] == "agent_01").sum()
    n_extra = len(long_gdf) - n_primary
    print(f"Exploded attribution rows: {len(long_gdf):,} ({n_primary:,} agent_01, {n_extra:,} additional agent_02/03)")

    print("\nPRIMARY (agent_01 only):")
    primary_long = long_gdf[long_gdf["attribution_field"] == "agent_01"]
    long_df_p, ml_df_p = rasterize_long_table(primary_long, "primary")
    write_products(long_df_p, ml_df_p, "primary")

    print("\nALL-ATTRIBUTED-AGENTS (agent_01 + agent_02 + agent_03):")
    long_df_a, ml_df_a = rasterize_long_table(long_gdf, "allagents")
    write_products(long_df_a, ml_df_a, "allagents")

    print("\nZero-pixel polygon check (primary geometry set, polygons < 4-pixel area threshold)...")
    zero_check = find_zero_pixel_polygons(gdf)
    n_small = len(zero_check)
    n_zero = int((~zero_check["has_pixel"]).sum()) if n_small else 0
    if n_small:
        zero_check[~zero_check["has_pixel"]][[SUBREGION_COL, YEAR_COL, "change_class"]].assign(
            area_m2=zero_check.loc[~zero_check["has_pixel"], "geometry"].area
        ).to_csv(QA_DIR / "glkn_zero_pixel_polygons.csv", index=False)
    print(f"  {n_small} polygons under {ZERO_PIXEL_AREA_THRESHOLD_M2:.0f} m2; {n_zero} contribute zero pixels")

    meta = grid_metadata(SOURCE, gdf.crs, SUBREGION_COL, YEAR_COL, "agent_01 (primary) / agent_01+02+03 (all-attributed)",
                          notes="subregion is the park_code attribute; no boundary geometry used for subregion membership. "
                                "Two parallel products distinguish primary (agent_01) vs all-attributed-agent (agent_01+02+03) "
                                "distributions -- agent multiplicity affects 1.43% of confirmed polygons.")
    with open(QA_DIR / "glkn_rasterize_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote glkn_rasterize_metadata.json")

    print(f"\nElapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
