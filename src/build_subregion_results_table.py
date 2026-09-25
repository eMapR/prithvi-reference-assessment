"""
Build the compact per-subregion results table for Task 1 report Section 7
(cross-source bridge to focal-domain selection).

For each of the 38 subregions (NCCN 4, GLKN primary 7, ADS R6 DCA 7,
ADS R10 DCA 20), reports:
  - Attributed pixel-years: the unique per-subregion pixel-year denominator,
    i.e. same-year multi-label pixels counted once -- taken from the
    existing authoritative *_multilabel_qa.csv files (attributed_pixels
    summed over years), NOT the sum of per-class pixel counts in
    outputs/report/task1_master_pixel_summary.csv (which double-counts
    same-year multi-label pixels; see that file's own multi-label excess
    vs. these totals).
  - Native classes represented: count of distinct native_class rows for
    that subregion in the master pixel-summary table.
  - Leading/second/third native class and their spatial_prevalence_pct,
    from the master pixel-summary table.

Reads only existing outputs; performs no rasterization or recomputation.
Prints a GitHub-flavored Markdown table to stdout for direct insertion into
report/task1_reference_data_assessment.md.
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
QA_DIR = REPO_ROOT / "outputs" / "qa"
MASTER_PATH = REPO_ROOT / "outputs" / "report" / "task1_master_pixel_summary.csv"

DENOM_FILES = {
    "NCCN": QA_DIR / "nccn_multilabel_qa.csv",
    "GLKN_primary": QA_DIR / "glkn_multilabel_qa_primary.csv",
    "ADS_R6_DCA": QA_DIR / "ads_r6_subregion_year_dca_multilabel_qa.csv",
    "ADS_R10_DCA": QA_DIR / "ads_r10_subregion_year_dca_multilabel_qa.csv",
}

SOURCE_LABELS = {
    "NCCN": "NCCN",
    "GLKN_primary": "GLKN",
    "ADS_R6_DCA": "ADS Region 6",
    "ADS_R10_DCA": "ADS Region 10",
}

# report row order: source grouping in the same order as report Sections 3-6,
# subregions within a source in the same order as the report's own tables/figures
SUBREGION_ORDER = {
    "NCCN": ["MORA", "NOCA", "OLYM", "LEWI"],
    "GLKN_primary": ["APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"],
    "ADS_R6_DCA": [
        "Blue Mountains", "Cascades", "Eastern Cascades Slopes and Foothills",
        "Coast Range", "North Cascades", "Northern Rockies",
        "Klamath Mountains/California High North Coast Range",
    ],
    "ADS_R10_DCA": None,  # sorted by descending attributed pixel-years below
}


def denom_by_subregion(source):
    df = pd.read_csv(DENOM_FILES[source])
    key = "subregion_name" if "subregion_name" in df.columns else "subregion"
    return df.groupby(key)["attributed_pixels"].sum()


def main():
    master = pd.read_csv(MASTER_PATH)
    rows = []

    for source in ["NCCN", "GLKN_primary", "ADS_R6_DCA", "ADS_R10_DCA"]:
        denom = denom_by_subregion(source)
        sub = master[master["source"] == source]

        order = SUBREGION_ORDER[source]
        if order is None:
            order = denom.sort_values(ascending=False).index.tolist()

        for name in order:
            grp = sub[sub["subregion_name"] == name].sort_values(
                "spatial_prevalence_pct", ascending=False
            )
            n_classes = len(grp)
            top3 = grp.head(3)
            pixel_years = int(denom.loc[name])

            def fmt(i):
                if i < len(top3):
                    r = top3.iloc[i]
                    return f"{r.native_class} ({r.spatial_prevalence_pct:.1f}%)"
                return "--"

            rows.append(
                {
                    "Source": SOURCE_LABELS[source],
                    "Subregion": name,
                    "Attributed pixel-years": f"{pixel_years:,}",
                    "Native classes represented": n_classes,
                    "Leading native class (%)": fmt(0),
                    "Second native class (%)": fmt(1),
                    "Third native class (%)": fmt(2),
                }
            )

    out = pd.DataFrame(rows)
    assert len(out) == 38, f"expected 38 subregions, got {len(out)}"

    cols = list(out.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in out.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")

    print("\n".join(lines))
    print(f"\n[{len(out)} rows]")


if __name__ == "__main__":
    main()
