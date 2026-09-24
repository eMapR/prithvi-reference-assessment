"""
Descriptive summary tables built from the already-produced 30 m reference-grid
pixel outputs (outputs/qa/*_pixels.csv, *_multilabel_qa*.csv). Purely a
reshaping/summarization step -- no new rasterization, no raw-data processing.

For each source (NCCN, GLKN primary, GLKN all-agents, ADS R6 DCA, ADS R6
DamageType, ADS R10 DCA, ADS R10 DamageType), produces two tables:

  {prefix}_subregion_class_summary.csv
      subregion | native_class | pixel_count | area_ha | spatial_prevalence_pct
      (all years combined)

  {prefix}_subregion_year_class_summary.csv
      subregion | year | native_class | pixel_count | area_ha | spatial_prevalence_pct
      (the temporal structure)

SPATIAL PREVALENCE, not attribution composition:

  spatial_prevalence_pct = native-class pixel count / unique attributed
  pixel count (for that subregion, or that subregion-year) x 100

"Spatial prevalence is the percentage of unique attributed 30 m
reference-grid pixels carrying a given native label. Percentages may sum to
more than 100% because individual pixels can carry multiple valid
attributions." This is a deliberate choice, not an error: if a pixel
legitimately carries both bark beetle and root disease, both agents are
each reported at their own full spatial prevalence -- neither agent's
apparent prevalence is reduced because another valid attribution shares
that pixel. The percentages are NOT normalized to sum to 100% and this
table does NOT represent attribution composition (share of a fixed total).

No diversity scores, no ranking, no focal-area selection -- descriptive only.
"""

import pandas as pd

from rasterize_common import QA_DIR


def build_summary(long_csv, multilabel_csv, prefix, subregion_cols):
    """subregion_cols: list of columns identifying a subregion (e.g.
    ['subregion'] for NCCN/GLKN, ['subregion','subregion_name'] for ADS)."""
    long_df = pd.read_csv(QA_DIR / long_csv)
    ml_df = pd.read_csv(QA_DIR / multilabel_csv)

    # --- all-years subregion x class summary ---
    allyears = long_df.groupby(subregion_cols + ["native_class"]).agg(
        pixel_count=("pixel_count", "sum")
    ).reset_index()
    allyears["area_ha"] = (allyears["pixel_count"] * 0.09).round(4)

    denom_allyears = ml_df.groupby(subregion_cols)["attributed_pixels"].sum().rename("_unique_attributed_pixels")
    allyears = allyears.merge(denom_allyears, on=subregion_cols, how="left")
    allyears["spatial_prevalence_pct"] = (
        100 * allyears["pixel_count"] / allyears["_unique_attributed_pixels"]
    ).round(3)
    allyears = allyears.drop(columns=["_unique_attributed_pixels"])
    allyears = allyears.sort_values(subregion_cols + ["pixel_count"], ascending=[True] * len(subregion_cols) + [False])
    allyears = allyears[subregion_cols + ["native_class", "pixel_count", "area_ha", "spatial_prevalence_pct"]]
    out1 = QA_DIR / f"{prefix}_subregion_class_summary.csv"
    allyears.to_csv(out1, index=False)

    # --- subregion x year x class summary (temporal structure) ---
    denom_year = ml_df.set_index(subregion_cols + ["year"])["attributed_pixels"].rename("_unique_attributed_pixels")
    yearclass = long_df.merge(denom_year.reset_index(), on=subregion_cols + ["year"], how="left")
    yearclass["spatial_prevalence_pct"] = (
        100 * yearclass["pixel_count"] / yearclass["_unique_attributed_pixels"]
    ).round(3)
    yearclass = yearclass.drop(columns=["_unique_attributed_pixels"])
    yearclass = yearclass.sort_values(subregion_cols + ["year", "pixel_count"],
                                       ascending=[True] * len(subregion_cols) + [True, False])
    yearclass = yearclass[subregion_cols + ["year", "native_class", "pixel_count", "area_ha", "spatial_prevalence_pct"]]
    out2 = QA_DIR / f"{prefix}_subregion_year_class_summary.csv"
    yearclass.to_csv(out2, index=False)

    print(f"{prefix}: wrote {out1.name} ({len(allyears)} rows), {out2.name} ({len(yearclass)} rows)")
    return allyears, yearclass


def main():
    print("Building descriptive pixel-summary tables (spatial prevalence, no new rasterization)...\n")

    build_summary("nccn_subregion_year_class_pixels.csv", "nccn_multilabel_qa.csv",
                   "nccn", ["subregion"])

    build_summary("glkn_subregion_year_class_pixels_primary.csv", "glkn_multilabel_qa_primary.csv",
                   "glkn_primary", ["subregion"])
    build_summary("glkn_subregion_year_class_pixels_allagents.csv", "glkn_multilabel_qa_allagents.csv",
                   "glkn_allagents", ["subregion"])

    build_summary("ads_r6_subregion_year_dca_pixels.csv", "ads_r6_subregion_year_dca_multilabel_qa.csv",
                   "ads_r6_dca", ["subregion", "subregion_name"])
    build_summary("ads_r6_subregion_year_damagetype_pixels.csv", "ads_r6_subregion_year_damagetype_multilabel_qa.csv",
                   "ads_r6_damagetype", ["subregion", "subregion_name"])

    build_summary("ads_r10_subregion_year_dca_pixels.csv", "ads_r10_subregion_year_dca_multilabel_qa.csv",
                   "ads_r10_dca", ["subregion", "subregion_name"])
    build_summary("ads_r10_subregion_year_damagetype_pixels.csv", "ads_r10_subregion_year_damagetype_multilabel_qa.csv",
                   "ads_r10_damagetype", ["subregion", "subregion_name"])

    print("\nDone.")


if __name__ == "__main__":
    main()
