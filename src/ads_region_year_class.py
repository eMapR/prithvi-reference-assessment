"""
ADS R6 / R10 region x year x native-DCA-class tables -- the detailed "stack"
behind the regional summaries (ads_r6_ecoregion_capture.csv /
ads_r10_huc6_capture.csv) and the existing by-year / by-DCA tables, which
each only break out one dimension at a time. Built entirely from the
already-processed, already-overlaid parquets produced by
src/process_ads_r6.py and src/process_ads_r10.py -- no new raw-data
processing, no new overlay/geometry work.

Scope: ADS R6 and ADS R10 only. Does not harmonize DCA_CODE/DCA_COMMON(_NAME)
across R6/R10 or with NCCN/GLKN. Native taxonomy preserved verbatim.

Never writes to data/raw/.
"""

from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # ADS R6: ecoregion x SURVEY_YEA x DCA_CODE/DCA_COMMON
    # -------------------------------------------------------------------
    r6 = gpd.read_parquet(PROCESSED / "ads_r6" / "ads_r6_region6_with_ecoregion.parquet")
    print(f"Loaded {len(r6):,} ADS R6 features")

    r6_stack = r6.dropna(subset=["us_l3code"]).groupby(
        ["us_l3code", "us_l3name", "SURVEY_YEA", "DCA_CODE", "DCA_COMMON"]
    ).agg(
        record_count=("OBJECTID", "count"),
        area_m2=("area_in_own_ecoregion_m2", "sum"),
    ).reset_index()
    r6_path = QA_DIR / "ads_r6_by_ecoregion_year_dca.csv"
    r6_stack.to_csv(r6_path, index=False)
    print(f"Wrote {r6_path.relative_to(REPO_ROOT)} ({len(r6_stack)} rows)")

    # -------------------------------------------------------------------
    # ADS R10: huc6 x SURVEY_YEAR x DCA_CODE/DCA_COMMON_NAME
    # -------------------------------------------------------------------
    r10 = gpd.read_parquet(PROCESSED / "ads_r10" / "ads_r10_with_huc6.parquet")
    print(f"\nLoaded {len(r10):,} ADS R10 features")

    r10_stack = r10.dropna(subset=["huc6_code"]).groupby(
        ["huc6_code", "huc6_name", "SURVEY_YEAR", "DCA_CODE", "DCA_COMMON_NAME"]
    ).agg(
        record_count=("DAMAGE_AREA_ID", "count"),
        area_m2=("area_in_own_huc6_m2", "sum"),
    ).reset_index()
    r10_path = QA_DIR / "ads_r10_by_huc6_year_dca.csv"
    r10_stack.to_csv(r10_path, index=False)
    print(f"Wrote {r10_path.relative_to(REPO_ROOT)} ({len(r10_stack)} rows)")


if __name__ == "__main__":
    main()
