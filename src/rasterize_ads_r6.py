"""
ADS Region 6 30 m reference-grid pixel summaries.

subregion = the 7 dissolved EPA Level III ecoregions (BOUNDARY GEOMETRY, not
the earlier centroid-based assignment -- per instruction, a polygon crossing
an ecoregion boundary must have its pixels split by actual pixel-center
location between both ecoregions, not assigned wholesale to whichever
ecoregion its centroid happened to fall in).

Two SEPARATE, independent products (not combined):
  PRIMARY:   subregion x year x DCA_COMMON  (causal agent)
  SECONDARY: subregion x year x DAMAGE_T_1  (damage type)

Same-year overlap handling: each native class rasterized independently (see
src/rasterize_common.py) -- a pixel may be positive for >1 DCA/damage-type
in the same year, consistent with the same-year overlap investigation
(97% of R6 same-year overlap is the documented "pancake" pattern: multiple
legitimate attributions at the same footprint).

Outputs (outputs/qa/):
  ads_r6_subregion_year_dca_pixels.csv            -- A (primary)
  ads_r6_subregion_dca_pixels_allyears.csv        -- B (primary)
  ads_r6_subregion_year_pixels_summary_dca.csv    -- C (primary)
  ads_r6_multilabel_qa_dca.csv                    -- D (primary)
  ads_r6_subregion_year_damagetype_pixels.csv     -- A (secondary)
  ads_r6_subregion_damagetype_pixels_allyears.csv -- B (secondary)
  ads_r6_subregion_year_pixels_summary_damagetype.csv -- C (secondary)
  ads_r6_multilabel_qa_damagetype.csv             -- D (secondary)
  ads_r6_zero_pixel_polygons.csv
  ads_r6_rasterize_metadata.json
"""

import json
import time

import geopandas as gpd
import pandas as pd

from rasterize_common import (
    PROCESSED, QA_DIR, RASTER_RES, find_zero_pixel_polygons,
    grid_metadata, rasterize_ads_source,
)

SOURCE = "ADS R6"
PARQUET = PROCESSED / "ads_r6" / "ads_r6_region6_with_ecoregion.parquet"
BOUNDARY_PARQUET = PROCESSED / "boundaries" / "ads_r6_ecoregions.parquet"
YEAR_COL = "SURVEY_YEA"
DCA_COL = "DCA_COMMON"
DAMAGE_COL = "DAMAGE_T_1"

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
    print(f"Loaded {len(boundaries)} ecoregion boundaries, CRS={boundaries.crs.to_epsg() or boundaries.crs.srs}")
    if str(gdf.crs) != str(boundaries.crs):
        print("  Reprojecting boundaries to match reference-data CRS...")
        boundaries = boundaries.to_crs(gdf.crs)

    print("\nPRIMARY (DCA_COMMON):")
    long_dca, ml_dca = rasterize_ads_source(
        gdf, boundaries, "us_l3code", "us_l3name", None, YEAR_COL, DCA_COL, "R6-DCA"
    )
    write_products(long_dca, ml_dca, "ads_r6_subregion_year_dca")

    print("\nSECONDARY (DAMAGE_T_1):")
    long_dmg, ml_dmg = rasterize_ads_source(
        gdf, boundaries, "us_l3code", "us_l3name", None, YEAR_COL, DAMAGE_COL, "R6-DamageType"
    )
    write_products(long_dmg, ml_dmg, "ads_r6_subregion_year_damagetype")

    print("\nZero-pixel polygon check (polygons < 4-pixel area threshold, DCA classing)...")
    zero_check = find_zero_pixel_polygons(gdf, DCA_COL, "us_l3code", YEAR_COL, ZERO_PIXEL_AREA_THRESHOLD_M2)
    n_small = len(zero_check)
    n_zero = int((~zero_check["has_pixel"]).sum()) if n_small else 0
    if n_small:
        zero_check[~zero_check["has_pixel"]][["us_l3code", YEAR_COL, DCA_COL]].assign(
            area_m2=zero_check.loc[~zero_check["has_pixel"], "geometry"].area
        ).to_csv(QA_DIR / "ads_r6_zero_pixel_polygons.csv", index=False)
    print(f"  {n_small:,} polygons under {ZERO_PIXEL_AREA_THRESHOLD_M2:.0f} m2; {n_zero:,} contribute zero pixels")

    meta = grid_metadata(SOURCE, gdf.crs, "us_l3code (dissolved EPA Level III ecoregion)", YEAR_COL,
                          "DCA_COMMON (primary) / DAMAGE_T_1 (secondary, separate product)",
                          notes="Subregion membership determined by ACTUAL BOUNDARY GEOMETRY (pixel-center-in-subregion-polygon), "
                                "not by the earlier centroid-based vector-stage assignment. A polygon straddling two ecoregions "
                                "contributes pixels to both, split by pixel location.")
    with open(QA_DIR / "ads_r6_rasterize_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote ads_r6_rasterize_metadata.json")

    print(f"\nElapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
