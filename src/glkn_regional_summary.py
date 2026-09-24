"""
GLKN regional summary tables (by park) -- descriptive only, no new raw
processing. Reads the already-produced
data/processed/glkn/glkn_confirmed_standardized.parquet (see
docs/data_inventory.md §14, outputs/qa/glkn_processing_report.md) and adds
the same level of by-region breakdown already produced for ADS R6/R10: a
count+area+year-range summary per park, count+area by park x year, and
count+area by park x native agent_01 class.

Scope: GLKN only. Does not touch NCCN/ADS R6/ADS R10, and does not
harmonize GLKN's native 9-value agent_01 vocabulary with any other source's,
and does not collapse it to the SLBE report's 6 presentation groups. Does
not attempt to resolve the GLKN HUC/Canada boundary gap (§14.4/§14.7) --
"park" here means each park's own confirmed-disturbance footprint.

Never writes to data/raw/.
"""

from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"

GLKN_PARKS = ["APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"]


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)

    glkn = gpd.read_parquet(PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet")
    glkn = glkn.copy()
    glkn["area_m2"] = glkn.geometry.area

    print(f"Loaded {len(glkn):,} GLKN confirmed standardized features, CRS={glkn.crs}")

    # -------------------------------------------------------------------
    # Per-park summary
    # -------------------------------------------------------------------
    summary = glkn.groupby("park_code").agg(
        record_count=("year", "count"),
        attributed_area_m2=("area_m2", "sum"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        years_represented=("year", "nunique"),
        native_class_count=("change_class", "nunique"),
    ).reindex(GLKN_PARKS).reset_index()
    summary_path = QA_DIR / "glkn_by_park_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\nWrote {summary_path.relative_to(REPO_ROOT)}")
    print(summary.to_string(index=False))

    # -------------------------------------------------------------------
    # Per-park x year
    # -------------------------------------------------------------------
    by_year = glkn.groupby(["park_code", "year"]).agg(
        record_count=("change_class", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_year_path = QA_DIR / "glkn_by_park_year.csv"
    by_year.to_csv(by_year_path, index=False)
    print(f"\nWrote {by_year_path.relative_to(REPO_ROOT)} ({len(by_year)} rows)")

    # -------------------------------------------------------------------
    # Per-park x native agent_01 class (change_class = agent_01, preserved
    # verbatim -- native 9-value vocabulary, no harmonization)
    # -------------------------------------------------------------------
    by_class = glkn.groupby(["park_code", "change_class"]).agg(
        record_count=("year", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_class_path = QA_DIR / "glkn_by_park_class.csv"
    by_class.to_csv(by_class_path, index=False)
    print(f"Wrote {by_class_path.relative_to(REPO_ROOT)} ({len(by_class)} rows)")

    # -------------------------------------------------------------------
    # Per-park x year x native agent_01 class -- the detailed "stack"
    # behind the regional summary and the by-year/by-class tables above.
    # Built from the already-standardized parquet, not new raw processing.
    # -------------------------------------------------------------------
    by_year_class = glkn.groupby(["park_code", "year", "change_class"]).agg(
        record_count=("area_m2", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_year_class_path = QA_DIR / "glkn_by_park_year_class.csv"
    by_year_class.to_csv(by_year_class_path, index=False)
    print(f"Wrote {by_year_class_path.relative_to(REPO_ROOT)} ({len(by_year_class)} rows)")

    print("\nTop 3 native agent_01 classes by area, per park:")
    for park, grp in by_class.groupby("park_code"):
        top3 = grp.sort_values("area_m2", ascending=False).head(3)
        print(f"  {park}: " + "; ".join(
            f"{r.change_class} ({r.area_m2/1e4:,.0f} ha)" for r in top3.itertuples()
        ))


if __name__ == "__main__":
    main()
