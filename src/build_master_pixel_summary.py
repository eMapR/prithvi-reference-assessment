"""
Combine the four authoritative all-years subregion x native-class summary
tables (already produced by src/build_pixel_summary_tables.py /
src/*_regional_summary.py) into one master pixel-summary table for Task 1:

  outputs/qa/nccn_subregion_class_summary.csv
  outputs/qa/glkn_primary_subregion_class_summary.csv   (primary agent_01 view)
  outputs/qa/ads_r6_dca_subregion_class_summary.csv     (DCA view)
  outputs/qa/ads_r10_dca_subregion_class_summary.csv    (DCA view)

These are the four primary quantitative views actually used in the Task 1
report (GLKN primary-agent, ADS DCA) -- not the GLKN all-agents or ADS
Damage Type variants, which remain separate, unmerged files.

This script performs no rasterization and no recomputation: it only
concatenates the existing, already-verified CSVs above under a common
schema, tags each row with its source, and writes the result. Native class
vocabularies are NOT harmonized across sources -- native_class retains each
source's own values verbatim.

Output: outputs/report/task1_master_pixel_summary.csv
Schema: source, subregion, subregion_name, native_class, pixel_count,
        area_ha, spatial_prevalence_pct
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
QA_DIR = REPO_ROOT / "outputs" / "qa"
OUT_PATH = REPO_ROOT / "outputs" / "report" / "task1_master_pixel_summary.csv"

SOURCES = {
    "NCCN": QA_DIR / "nccn_subregion_class_summary.csv",
    "GLKN_primary": QA_DIR / "glkn_primary_subregion_class_summary.csv",
    "ADS_R6_DCA": QA_DIR / "ads_r6_dca_subregion_class_summary.csv",
    "ADS_R10_DCA": QA_DIR / "ads_r10_dca_subregion_class_summary.csv",
}

SCHEMA = ["source", "subregion", "subregion_name", "native_class", "pixel_count", "area_ha", "spatial_prevalence_pct"]


def load_one(source, path):
    df = pd.read_csv(path)
    if "subregion_name" not in df.columns:
        # NCCN and GLKN: subregion is already the human-readable park code,
        # there is no separate source-provided name field to preserve.
        df = df.copy()
        df["subregion_name"] = df["subregion"]
    df = df.copy()
    df["source"] = source
    return df[SCHEMA]


def main():
    parts = [load_one(source, path) for source, path in SOURCES.items()]
    master = pd.concat(parts, ignore_index=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH} ({len(master)} rows)")
    print(master["source"].value_counts())


if __name__ == "__main__":
    main()
