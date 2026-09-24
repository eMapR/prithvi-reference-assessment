"""
NCCN regional summary tables (by park) -- descriptive only, no new raw
processing. Reads the already-produced data/processed/nccn/nccn_standardized.parquet
(see docs/data_inventory.md §12, outputs/qa/nccn_processing_report.md) and adds
the same level of by-region breakdown already produced for ADS R6/R10: a
count+area+year-range summary per park, count+area by park x year, and
count+area by park x native change_class.

Scope: NCCN only. Does not touch GLKN/ADS R6/ADS R10, and does not
harmonize NCCN's change_class vocabulary with any other source's. Does not
attempt to resolve the NCCN park-boundary question (§12/§13) -- "park" here
means each park's own attributed-data footprint, the same framing the rest
of this notebook already uses, not an independently drawn analysis boundary.

Never writes to data/raw/.
"""

from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
QA_DIR = REPO_ROOT / "outputs" / "qa"

PARKS = ["MORA", "NOCA", "OLYM", "LEWI"]


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)

    nccn = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")
    nccn = nccn.copy()
    nccn["area_m2"] = nccn.geometry.area

    print(f"Loaded {len(nccn):,} NCCN standardized features, CRS={nccn.crs.to_epsg()}")

    # -------------------------------------------------------------------
    # Per-park summary
    # -------------------------------------------------------------------
    summary = nccn.groupby("park_code").agg(
        record_count=("year", "count"),
        attributed_area_m2=("area_m2", "sum"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        years_represented=("year", "nunique"),
        native_class_count=("change_class", "nunique"),
    ).reindex(PARKS).reset_index()
    summary_path = QA_DIR / "nccn_by_park_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\nWrote {summary_path.relative_to(REPO_ROOT)}")
    print(summary.to_string(index=False))

    # -------------------------------------------------------------------
    # Per-park x year
    # -------------------------------------------------------------------
    by_year = nccn.groupby(["park_code", "year"]).agg(
        record_count=("change_class", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_year_path = QA_DIR / "nccn_by_park_year.csv"
    by_year.to_csv(by_year_path, index=False)
    print(f"\nWrote {by_year_path.relative_to(REPO_ROOT)} ({len(by_year)} rows)")

    # -------------------------------------------------------------------
    # Per-park x native change_class (native ChangeType/Chnge_type vocabulary,
    # preserved verbatim -- no harmonization across parks or sources)
    # -------------------------------------------------------------------
    by_class = nccn.groupby(["park_code", "change_class"]).agg(
        record_count=("year", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_class_path = QA_DIR / "nccn_by_park_class.csv"
    by_class.to_csv(by_class_path, index=False)
    print(f"Wrote {by_class_path.relative_to(REPO_ROOT)} ({len(by_class)} rows)")

    # -------------------------------------------------------------------
    # Per-park x year x native change_class -- the detailed "stack" behind
    # the regional summary and the by-year/by-class tables above. Built
    # from the already-standardized parquet, not new raw processing.
    # -------------------------------------------------------------------
    by_year_class = nccn.groupby(["park_code", "year", "change_class"]).agg(
        record_count=("area_m2", "count"),
        area_m2=("area_m2", "sum"),
    ).reset_index()
    by_year_class_path = QA_DIR / "nccn_by_park_year_class.csv"
    by_year_class.to_csv(by_year_class_path, index=False)
    print(f"Wrote {by_year_class_path.relative_to(REPO_ROOT)} ({len(by_year_class)} rows)")

    print("\nTop 3 change_class by area, per park:")
    for park, grp in by_class.groupby("park_code"):
        top3 = grp.sort_values("area_m2", ascending=False).head(3)
        print(f"  {park}: " + "; ".join(
            f"{r.change_class} ({r.area_m2/1e4:,.0f} ha)" for r in top3.itertuples()
        ))


if __name__ == "__main__":
    main()
