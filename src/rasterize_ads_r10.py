"""
ADS Region 10 30 m reference-grid pixel summaries.

subregion = the 20 HUC6 basins (BOUNDARY GEOMETRY, not the earlier
centroid-based assignment -- see src/rasterize_ads_r6.py for the shared
rationale, identical here).

Two SEPARATE, independent products:
  PRIMARY:   subregion x year x DCA_COMMON_NAME  (causal agent)
  SECONDARY: subregion x year x DAMAGE_TYPE      (damage type)

Outputs (outputs/qa/) -- names as actually written by write_products() below,
prefix is "ads_r10_subregion_year_dca" (primary) / "ads_r10_subregion_year_damagetype" (secondary):
  ads_r10_subregion_year_dca_pixels.csv                 -- A (primary)
  ads_r10_subregion_year_dca_pixels_allyears.csv        -- B (primary)
  ads_r10_subregion_year_dca_pixels_summary.csv         -- C (primary)
  ads_r10_subregion_year_dca_multilabel_qa.csv          -- D (primary)
  ads_r10_subregion_year_damagetype_pixels.csv          -- A (secondary)
  ads_r10_subregion_year_damagetype_pixels_allyears.csv -- B (secondary)
  ads_r10_subregion_year_damagetype_pixels_summary.csv  -- C (secondary)
  ads_r10_subregion_year_damagetype_multilabel_qa.csv   -- D (secondary)
  ads_r10_zero_pixel_polygons.csv
  ads_r10_rasterize_metadata.json

(The further-reshaped whiteboard-style spatial-prevalence summary tables --
ads_r10_dca_subregion_class_summary.csv,
ads_r10_dca_subregion_year_class_summary.csv, and the damagetype equivalents
-- are produced separately by src/build_pixel_summary_tables.py, not here.)
"""

import json
import time

import geopandas as gpd
import pandas as pd

from rasterize_common import (
    PROCESSED, QA_DIR, RASTER_RES, find_zero_pixel_polygons,
    grid_metadata, rasterize_ads_source,
)

SOURCE = "ADS R10"
PARQUET = PROCESSED / "ads_r10" / "ads_r10_with_huc6.parquet"
BOUNDARY_PARQUET = PROCESSED / "boundaries" / "ads_r10_huc6.parquet"
YEAR_COL = "SURVEY_YEAR"
DCA_COL = "DCA_COMMON_NAME"
DAMAGE_COL = "DAMAGE_TYPE"

ZERO_PIXEL_AREA_THRESHOLD_M2 = 4 * RASTER_RES * RASTER_RES


def write_products(long_df, ml_df, prefix):
    long_df.to_csv(QA_DIR / f"{prefix}_pixels.csv", index=False)
    allyears = long_df.groupby(["subregion", "subregion_name", "native_class"]).agg(
        pixel_count=("pixel_count", "sum")
    ).reset_index()
    allyears["area_ha"] = (allyears["pixel_count"] * 0.09).round(4)
    allyears.to_csv(QA_DIR / f"{prefix}_pixels_allyears.csv", index=False)
    subyear = long_df.groupby(["subregion", "subregion_name", "year"]).agg(
        total_pixel_count=("pixel_count", "sum")
    ).reset_index()
    subyear["total_area_ha"] = (subyear["total_pixel_count"] * 0.09).round(4)
    subyear.to_csv(QA_DIR / f"{prefix}_pixels_summary.csv", index=False)
    ml_df.to_csv(QA_DIR / f"{prefix}_multilabel_qa.csv", index=False)
    print(f"  wrote A ({len(long_df)} rows), B ({len(allyears)} rows), C ({len(subyear)} rows), D ({len(ml_df)} rows) for {prefix}")


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    gdf = gpd.read_parquet(PARQUET)
    boundaries = gpd.read_parquet(BOUNDARY_PARQUET)
    print(f"Loaded {len(gdf):,} {SOURCE} features, CRS={gdf.crs.to_epsg() or gdf.crs.srs}")
    print(f"Loaded {len(boundaries)} HUC6 boundaries, CRS={boundaries.crs.to_epsg() or boundaries.crs.srs}")
    if str(gdf.crs) != str(boundaries.crs):
        print("  Reprojecting boundaries to match reference-data CRS...")
        boundaries = boundaries.to_crs(gdf.crs)

    print("\nPRIMARY (DCA_COMMON_NAME):")
    long_dca, ml_dca = rasterize_ads_source(
        gdf, boundaries, "huc6", "name", None, YEAR_COL, DCA_COL, "R10-DCA"
    )
    write_products(long_dca, ml_dca, "ads_r10_subregion_year_dca")

    print("\nSECONDARY (DAMAGE_TYPE):")
    long_dmg, ml_dmg = rasterize_ads_source(
        gdf, boundaries, "huc6", "name", None, YEAR_COL, DAMAGE_COL, "R10-DamageType"
    )
    write_products(long_dmg, ml_dmg, "ads_r10_subregion_year_damagetype")

    print("\nZero-pixel polygon check (polygons < 4-pixel area threshold, DCA classing)...")
    zero_check = find_zero_pixel_polygons(gdf, DCA_COL, "huc6_code", YEAR_COL, ZERO_PIXEL_AREA_THRESHOLD_M2)
    n_small = len(zero_check)
    n_zero = int((~zero_check["has_pixel"]).sum()) if n_small else 0
    if n_small:
        zero_check[~zero_check["has_pixel"]][["huc6_code", YEAR_COL, DCA_COL]].assign(
            area_m2=zero_check.loc[~zero_check["has_pixel"], "geometry"].area
        ).to_csv(QA_DIR / "ads_r10_zero_pixel_polygons.csv", index=False)
    print(f"  {n_small:,} polygons under {ZERO_PIXEL_AREA_THRESHOLD_M2:.0f} m2; {n_zero:,} contribute zero pixels")

    meta = grid_metadata(SOURCE, gdf.crs, "huc6 (HUC6 basin boundary)", YEAR_COL,
                          "DCA_COMMON_NAME (primary) / DAMAGE_TYPE (secondary, separate product)",
                          notes="Subregion membership determined by ACTUAL BOUNDARY GEOMETRY (pixel-center-in-subregion-polygon), "
                                "not by the earlier centroid-based vector-stage assignment. A polygon straddling two HUC6s "
                                "contributes pixels to both, split by pixel location.")
    with open(QA_DIR / "ads_r10_rasterize_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote ads_r10_rasterize_metadata.json")

    print(f"\nElapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
