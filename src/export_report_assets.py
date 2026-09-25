"""
Export the selected polished-human-report assets (selection finalized
2026-09-24) as standalone files with stable filenames, under
outputs/report/assets/.

This reuses the exact plotting/table logic already in
notebooks/reference_data_assessment.ipynb -- no new analysis, no changed
methodology, no rasterization rerun. It reads only already-produced QA
outputs (outputs/qa/*.csv) and processed parquets (data/processed/), exactly
like the notebook does.

Two things are NOT simple copies of a notebook cell:
  - ads_r10_b6_prevalence_through_time.png: the report uses the refined
    "dominant-class-through-time" heatmap (one row per HUC6 basin, its own
    single most-prevalent DCA class only) instead of the notebook's 20-panel
    small-multiples figure (which stays in the notebook, unchanged, as the
    full multi-class breakdown).
  - ads_r10_a2_dataset_summary.csv's native_classes count: reconciled to 67
    (matching the rasterized Part B tables), not 68 (raw DCA_COMMON_NAME) or
    71 (raw DCA_CODE) -- see the reconciliation block below. Do not change
    this back to a raw .nunique() without re-reading that block.

Also produces methods_concept_figure.png, a hand-built schematic (not derived
from any notebook cell) showing: AOI (context) + attributed polygons (labels)
-> 30 m reference-grid characterization -> subregion x year x native class ->
attributed pixel-years / spatial prevalence.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, Polygon, FancyBboxPatch

from rasterize_common import REPO_ROOT, PROCESSED, QA_DIR
from qa_aoi_constrained_pixel_comparison import load_nccn_aois, load_glkn_aois

OUT = REPO_ROOT / "outputs" / "report" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

PARKS = ["MORA", "NOCA", "OLYM", "LEWI"]
GLKN_PARKS = ["APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"]


def heatmap(pivot, title, fname, figsize=None, annotate_thresh=0):
    col_order = pivot.sum(axis=0).sort_values(ascending=False).index
    pivot = pivot[col_order]
    figsize = figsize or (max(9, 0.55 * len(col_order)), 3.4)
    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", vmin=0)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=55 if figsize[0] < 12 else 60, ha="right", fontsize=8 if figsize[0] < 12 else 7)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    vmax = pivot.values.max()
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if v > annotate_thresh:
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7 if figsize[0] < 12 else 6,
                        color="white" if v > vmax * 0.5 else "black")
    fig.colorbar(im, ax=ax, label="spatial prevalence (%)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote", fname)


def bar(series, xlabel, title, fname, color="#4575b4", figsize=(8, 5)):
    fig, ax = plt.subplots(figsize=figsize)
    series.plot(kind="barh", ax=ax, color=color)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote", fname)


def small_multiples(yc, subregion_col, order, title, fname, ncols, figsize_per_col=4.2, figsize_per_row=2.8,
                     top_k=3, palette_name="tab10"):
    totals = yc.groupby([subregion_col, "native_class"])["pixel_count"].sum().reset_index()
    top_classes = sorted(
        totals.sort_values("pixel_count", ascending=False).groupby(subregion_col).head(top_k)["native_class"].unique()
    )
    yc = yc.copy()
    yc["class_bucket"] = yc["native_class"].where(yc["native_class"].isin(top_classes), "Other")
    palette = plt.get_cmap(palette_name).colors
    color_map = {cls: palette[i % len(palette)] for i, cls in enumerate(top_classes)}
    color_map["Other"] = "#999999"

    nrows = -(-len(order) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(figsize_per_col * ncols, figsize_per_row * nrows), sharex=False)
    axes_flat = axes.flat if hasattr(axes, "flat") else [axes]
    for ax, region in zip(axes_flat, order):
        sub = yc[yc[subregion_col] == region]
        pivot = sub.groupby(["year", "class_bucket"])["spatial_prevalence_pct"].sum().unstack(fill_value=0)
        bottom = None
        for cls in list(top_classes) + ["Other"]:
            if cls not in pivot.columns:
                continue
            vals = pivot[cls].values
            ax.bar(pivot.index, vals, bottom=bottom, color=color_map[cls], width=1.0)
            bottom = vals if bottom is None else bottom + vals
        ax.set_title(region, fontsize=9)
        ax.tick_params(labelsize=6)
    for ax in list(axes_flat)[len(order):]:
        ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[c]) for c in list(top_classes) + ["Other"]]
    fig.legend(handles, list(top_classes) + ["Other"], loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(title, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote", fname)


def export_nccn():
    nccn = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")
    nccn_ml = pd.read_csv(QA_DIR / "nccn_multilabel_qa.csv")

    n1 = pd.DataFrame([{
        "records": len(nccn),
        "years": f"{int(nccn.year.min())}-{int(nccn.year.max())}",
        "subregions": nccn["park_code"].nunique(),
        "native_classes": nccn["change_class"].nunique(),
        "attributed_pixel_years": int(nccn_ml["attributed_pixels"].sum()),
        "pixel_derived_area_ha": round(nccn_ml["attributed_pixels"].sum() * 0.09, 1),
    }])
    n1.to_csv(OUT / "nccn_a2_dataset_summary.csv", index=False)
    print("wrote nccn_a2_dataset_summary.csv")

    nccn_aois = load_nccn_aois(nccn.crs)

    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    for ax, park in zip(axes, PARKS):
        sub = nccn[nccn["park_code"] == park]
        sub.plot(ax=ax, color="#4575b4", edgecolor="none", alpha=0.6)
        gpd.GeoSeries([nccn_aois[park]], crs=nccn.crs).plot(
            ax=ax, facecolor="none", edgecolor="#333333", linewidth=0.9, linestyle="--")
        ax.set_title(f"{park} (n={len(sub):,})", fontsize=9)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("NCCN attributed change polygons, per park, with authoritative analysis AOI outline")
    fig.tight_layout()
    fig.savefig(OUT / "nccn_a6_polygons_by_park_map.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote nccn_a6_polygons_by_park_map.png")

    mapping = pd.read_csv(QA_DIR / "nccn_aoi_generation_mapping_qa.csv")
    mapping = mapping[mapping["used_in_task1"]].copy()
    mapping["authoritative_aoi"] = mapping.apply(
        lambda r: f"{r['park']} Protected Areas" if "Protected" in r["generation"] else "LPa01 LEWI (N+S union)", axis=1)
    mapping["pct_attributed_area_in_aoi"] = mapping.apply(
        lambda r: r["pct_area_in_protected_areas"] if "Protected" in r["generation"] else r["pct_area_in_lpa01_10mi_buffer"], axis=1)
    aoi_totals = pd.read_csv(QA_DIR / "nccn_glkn_aoi_total_pixel_counts.csv")
    aoi_totals = aoi_totals[aoi_totals["source"] == "NCCN"][["subregion", "aoi_pixel_count", "aoi_area_ha"]]
    n6 = mapping.merge(aoi_totals, left_on="park", right_on="subregion")
    n6 = n6[["park", "dataset", "generation", "authoritative_aoi", "aoi_pixel_count", "aoi_area_ha", "pct_attributed_area_in_aoi"]]
    n6.to_csv(OUT / "nccn_b1_aoi_mapping_table.csv", index=False)
    print("wrote nccn_b1_aoi_mapping_table.csv")

    summary = pd.read_csv(QA_DIR / "nccn_subregion_class_summary.csv")
    pivot = summary.pivot(index="subregion", columns="native_class", values="spatial_prevalence_pct").reindex(PARKS).fillna(0)
    heatmap(pivot, "NCCN native-class spatial prevalence by subregion (all years)", "nccn_b4_prevalence_heatmap.png")

    yc = pd.read_csv(QA_DIR / "nccn_subregion_year_class_summary.csv")
    small_multiples(yc, "subregion", PARKS,
                     "NCCN: native-class spatial prevalence (%) by year, within each park\n"
                     "(each park's own top 3 classes, unioned, + Other; stacked bar height is a magnitude view, not a composition metric)",
                     "nccn_b6_prevalence_through_time.png", ncols=4, figsize_per_row=4)


def export_glkn():
    glkn = gpd.read_parquet(PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet")
    glkn_ml = pd.read_csv(QA_DIR / "glkn_multilabel_qa_primary.csv")

    g1 = pd.DataFrame([{
        "records": len(glkn),
        "years": f"{int(glkn.year.min())}-{int(glkn.year.max())}",
        "subregions": glkn["park_code"].nunique(),
        "native_classes": glkn["change_class"].nunique(),
        "attributed_pixel_years": int(glkn_ml["attributed_pixels"].sum()),
        "pixel_derived_area_ha": round(glkn_ml["attributed_pixels"].sum() * 0.09, 1),
    }])
    g1.to_csv(OUT / "glkn_a2_dataset_summary.csv", index=False)
    print("wrote glkn_a2_dataset_summary.csv")

    glkn_aois = load_glkn_aois(glkn.crs)

    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for ax, park in zip(axes.flat, GLKN_PARKS):
        sub = glkn[glkn["park_code"] == park]
        sub.plot(ax=ax, color="#4575b4", edgecolor="none", alpha=0.6)
        gpd.GeoSeries([glkn_aois[park]], crs=glkn.crs).plot(
            ax=ax, facecolor="none", edgecolor="#333333", linewidth=0.9, linestyle="--")
        ax.set_title(f"{park} (n={len(sub):,})", fontsize=9)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
    axes.flat[-1].axis("off")
    fig.suptitle("GLKN confirmed disturbance polygons, per park, with authoritative analysis AOI outline")
    fig.tight_layout()
    fig.savefig(OUT / "glkn_a6_polygons_by_park_map.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote glkn_a6_polygons_by_park_map.png")

    aoi = pd.read_csv(QA_DIR / "nccn_glkn_aoi_total_pixel_counts.csv")
    aoi = aoi[aoi["source"] == "GLKN"][["subregion", "aoi_pixel_count", "aoi_area_ha"]]
    pixel_comp = pd.read_csv(QA_DIR / "nccn_glkn_aoi_constraint_comparison_subregion.csv")
    pixel_comp = pixel_comp[pixel_comp["source"] == "GLKN-primary"]
    g6 = aoi.merge(pixel_comp[["subregion", "existing_attributed_pixel_years", "pct_diff"]], on="subregion")
    g6["pct_attributed_pixel_years_in_aoi"] = (100 + g6["pct_diff"].fillna(0)).round(3)
    g6 = g6.drop(columns=["pct_diff"]).set_index("subregion").reindex(GLKN_PARKS).reset_index()
    g6.to_csv(OUT / "glkn_b1_aoi_table.csv", index=False)
    print("wrote glkn_b1_aoi_table.csv")

    summary = pd.read_csv(QA_DIR / "glkn_primary_subregion_class_summary.csv")
    pivot = summary.pivot(index="subregion", columns="native_class", values="spatial_prevalence_pct").reindex(GLKN_PARKS).fillna(0)
    heatmap(pivot, "GLKN native agent_01 spatial prevalence by subregion (all years, primary)", "glkn_b4_prevalence_heatmap.png",
            figsize=(max(8, 0.6 * pivot.shape[1]), 3.4))

    yc = pd.read_csv(QA_DIR / "glkn_primary_subregion_year_class_summary.csv")
    small_multiples(yc, "subregion", GLKN_PARKS,
                     "GLKN: native agent_01 spatial prevalence (%) by year, within each park\n"
                     "(each park's own top 3 classes, unioned, + Other; stacked bar height is a magnitude view, not a composition metric)",
                     "glkn_b6_prevalence_through_time.png", ncols=4, figsize_per_row=3.5)


def export_ads_r6():
    r6 = gpd.read_parquet(PROCESSED / "ads_r6" / "ads_r6_region6_with_ecoregion.parquet")
    ecoregions = gpd.read_parquet(PROCESSED / "boundaries" / "ads_r6_ecoregions.parquet")
    r6_ml = pd.read_csv(QA_DIR / "ads_r6_subregion_year_dca_multilabel_qa.csv")

    r6_1 = pd.DataFrame([{
        "records": len(r6),
        "years": f"{int(r6.SURVEY_YEA.min())}-{int(r6.SURVEY_YEA.max())}",
        "subregions": 7,
        "native_classes": r6["DCA_COMMON"].nunique(),  # == DCA_CODE.nunique() here, verified 1:1 for R6
        "attributed_pixel_years": int(r6_ml["attributed_pixels"].sum()),
        "pixel_derived_area_ha": round(r6_ml["attributed_pixels"].sum() * 0.09, 1),
    }])
    r6_1.to_csv(OUT / "ads_r6_a2_dataset_summary.csv", index=False)
    print("wrote ads_r6_a2_dataset_summary.csv")

    fig, ax = plt.subplots(figsize=(9, 9))
    ecoregions.plot(ax=ax, column="us_l3name", cmap="tab10", alpha=0.5, edgecolor="black", linewidth=0.8, legend=True,
                     legend_kwds={"loc": "lower left", "fontsize": 7})
    ax.set_title("BugNet R6 EPA Level III ecoregions, dissolved (7 regions)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(OUT / "ads_r6_b1_ecoregion_map.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote ads_r6_b1_ecoregion_map.png")

    summary = pd.read_csv(QA_DIR / "ads_r6_dca_subregion_class_summary.csv")
    TOP_N_COLS = 20
    top_cols = summary.groupby("native_class")["pixel_count"].sum().sort_values(ascending=False).head(TOP_N_COLS).index
    pivot = summary[summary["native_class"].isin(top_cols)].pivot(index="subregion_name", columns="native_class", values="spatial_prevalence_pct").fillna(0)
    pivot = pivot[top_cols]
    region_order = summary.groupby("subregion_name")["pixel_count"].sum().sort_values(ascending=False).index
    pivot = pivot.reindex(region_order)
    heatmap(pivot, f"ADS R6 native DCA spatial prevalence by ecoregion (all years, top {TOP_N_COLS} of 91 DCA codes)",
            "ads_r6_b4_prevalence_heatmap.png", figsize=(max(10, 0.5 * len(top_cols)), 4), annotate_thresh=5)

    yc = pd.read_csv(QA_DIR / "ads_r6_dca_subregion_year_class_summary.csv")
    TOP_K_PER_REGION = 3
    totals_per_sub_class = yc.groupby(["subregion_name", "native_class"])["pixel_count"].sum().reset_index()
    top_classes = sorted(
        totals_per_sub_class.sort_values("pixel_count", ascending=False).groupby("subregion_name").head(TOP_K_PER_REGION)["native_class"].unique()
    )
    yc["class_bucket"] = yc["native_class"].where(yc["native_class"].isin(top_classes), "Other")
    palette = plt.get_cmap("tab20").colors
    color_map = {cls: palette[i % len(palette)] for i, cls in enumerate(top_classes)}
    color_map["Other"] = "#999999"
    region_order = summary.groupby("subregion_name")["pixel_count"].sum().sort_values(ascending=False).index.tolist()
    ncols = 4
    nrows = -(-len(region_order) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 2.8 * nrows), sharex=False)
    axes_flat = axes.flat
    for ax, region in zip(axes_flat, region_order):
        sub = yc[yc["subregion_name"] == region]
        piv = sub.groupby(["year", "class_bucket"])["spatial_prevalence_pct"].sum().unstack(fill_value=0)
        bottom = None
        for cls in list(top_classes) + ["Other"]:
            if cls not in piv.columns:
                continue
            vals = piv[cls].values
            ax.bar(piv.index, vals, bottom=bottom, color=color_map[cls], width=1.0)
            bottom = vals if bottom is None else bottom + vals
        ax.set_title(region, fontsize=8)
        ax.tick_params(labelsize=6)
    for ax in list(axes_flat)[len(region_order):]:
        ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[c]) for c in list(top_classes) + ["Other"]]
    fig.legend(handles, list(top_classes) + ["Other"], loc="lower center", ncol=4, fontsize=6, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle("ADS R6: DCA spatial prevalence (%) by year, within each ecoregion\n"
                 "(each region's own top 3 DCA, unioned, + Other; stacked bar height is a magnitude view, not a composition metric)", y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "ads_r6_b6_prevalence_through_time.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote ads_r6_b6_prevalence_through_time.png")

    dmg_summary = pd.read_csv(QA_DIR / "ads_r6_damagetype_subregion_class_summary.csv")
    ml_dmg_total = pd.read_csv(QA_DIR / "ads_r6_subregion_year_damagetype_multilabel_qa.csv")["attributed_pixels"].sum()
    overall_dmg = dmg_summary.groupby("native_class")["pixel_count"].sum().sort_values(ascending=False)
    overall_dmg_pct = (100 * overall_dmg / ml_dmg_total).round(2)
    bar(overall_dmg_pct, "spatial prevalence (%), all 7 ecoregions combined",
        "ADS R6 overall DAMAGE_TYP spatial prevalence (secondary taxonomy)", "ads_r6_b8_damagetype_bar.png", color="#d73027", figsize=(8, 4))


def export_ads_r10():
    r10 = gpd.read_parquet(PROCESSED / "ads_r10" / "ads_r10_with_huc6.parquet")
    huc6 = gpd.read_parquet(PROCESSED / "boundaries" / "ads_r10_huc6.parquet")
    r10_ml = pd.read_csv(QA_DIR / "ads_r10_subregion_year_dca_multilabel_qa.csv")

    # --- R10 native-class count reconciliation (see module docstring) ---
    # 71 = r10.DCA_CODE.nunique()        -- raw numeric internal code, not the taxonomy field
    #                                        used as "native_class" anywhere else in this project.
    #                                        3 codes are mid-survey renumberings of the SAME real
    #                                        agent under DCA_COMMON_NAME (otherwise a clean 1:1
    #                                        code<->name mapping).
    # 68 = r10.DCA_COMMON_NAME.nunique() -- raw vector data, correct taxonomy field: the real
    #                                        diversity of the SOURCE dataset.
    # 67 = ads_r10_dca_subregion_class_summary.csv["native_class"].nunique() -- the rasterized,
    #                                        subregion-assigned Part B universe. One class,
    #                                        "Rhizosphaera needle disease of fir" (2 polygons,
    #                                        huc6_code null for both -- entirely outside all 20
    #                                        HUC6 subregions, not small-polygon pixel dropout),
    #                                        never appears in any subregion and so has zero rows
    #                                        in the subregion-level summary.
    # B.4/B.5 already say "of 67 total codes" (the rasterized Part B universe). The compact A.2
    # table below reports 67 too, for consistency -- never re-derive this as a plain
    # r10["DCA_CODE"].nunique() or r10["DCA_COMMON_NAME"].nunique() without re-reading this note.
    r10_dca_code_n = r10["DCA_CODE"].nunique()
    r10_dca_name_n = r10["DCA_COMMON_NAME"].nunique()
    r10_pixel_summary_n = pd.read_csv(QA_DIR / "ads_r10_dca_subregion_class_summary.csv")["native_class"].nunique()
    print(f"R10 class-count reconciliation: DCA_CODE={r10_dca_code_n}, DCA_COMMON_NAME={r10_dca_name_n}, "
          f"rasterized Part B universe={r10_pixel_summary_n} (this is what's reported below)")
    assert r10_pixel_summary_n == 67

    r10_1 = pd.DataFrame([{
        "records": len(r10),
        "years": f"{int(r10.SURVEY_YEAR.min())}-{int(r10.SURVEY_YEAR.max())}",
        "subregions": 20,
        "native_classes": r10_pixel_summary_n,
        "attributed_pixel_years": int(r10_ml["attributed_pixels"].sum()),
        "pixel_derived_area_ha": round(r10_ml["attributed_pixels"].sum() * 0.09, 1),
    }])
    r10_1.to_csv(OUT / "ads_r10_a2_dataset_summary.csv", index=False)
    print("wrote ads_r10_a2_dataset_summary.csv")

    fig, ax = plt.subplots(figsize=(9, 9))
    huc6.plot(ax=ax, column="name", cmap="tab20", alpha=0.5, edgecolor="black", linewidth=0.8, legend=True,
              legend_kwds={"loc": "lower left", "fontsize": 6, "ncol": 2})
    ax.set_title("BugNet R10 HUC6 regions, Alaska (20 regions, no dissolve needed)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(OUT / "ads_r10_b1_huc6_map.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote ads_r10_b1_huc6_map.png")

    summary = pd.read_csv(QA_DIR / "ads_r10_dca_subregion_class_summary.csv")
    TOP_N_COLS = 20
    top_cols = summary.groupby("native_class")["pixel_count"].sum().sort_values(ascending=False).head(TOP_N_COLS).index
    pivot = summary[summary["native_class"].isin(top_cols)].pivot(index="subregion_name", columns="native_class", values="spatial_prevalence_pct").fillna(0)
    pivot = pivot[top_cols]
    region_order = summary.groupby("subregion_name")["pixel_count"].sum().sort_values(ascending=False).index
    pivot = pivot.reindex(region_order)
    heatmap(pivot, f"ADS R10 native DCA spatial prevalence by HUC6 basin (all years, top {TOP_N_COLS} of {r10_pixel_summary_n} DCA codes)",
            "ads_r10_b4_prevalence_heatmap.png", figsize=(max(10, 0.5 * len(top_cols)), 7), annotate_thresh=5)

    # B.6 replacement: refined dominant-class-through-time heatmap (print-legible alternative
    # to the notebook's full 20-panel small-multiples, which stays in the notebook unchanged).
    yc = pd.read_csv(QA_DIR / "ads_r10_dca_subregion_year_class_summary.csv")
    dominant = summary.sort_values(["subregion_name", "spatial_prevalence_pct"], ascending=[True, False]).groupby("subregion_name").first()["native_class"]
    years = sorted(yc["year"].unique())
    mat = np.full((len(region_order), len(years)), np.nan)
    for i, region in enumerate(region_order):
        dom_cls = dominant[region]
        sub = yc[(yc.subregion_name == region) & (yc.native_class == dom_cls)]
        for _, row in sub.iterrows():
            j = years.index(row["year"])
            mat[i, j] = row["spatial_prevalence_pct"]
    mat = np.nan_to_num(mat, nan=0.0)
    row_labels = [f"{r}\n({dominant[r]})" for r in region_order]

    fig, ax = plt.subplots(figsize=(15, 9))
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd", vmin=0, vmax=100)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8.5, linespacing=1.3)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years, rotation=90, fontsize=7.5)
    ax.set_xlabel("year", fontsize=10)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if v > 55:
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=5.5,
                        color="white" if v > 50 else "black")
    for i in range(mat.shape[0] + 1):
        ax.axhline(i - 0.5, color="white", linewidth=0.6)
    fig.colorbar(im, ax=ax, label="spatial prevalence of the basin's own dominant DCA class (%)", fraction=0.03, pad=0.02)
    ax.set_title(
        "ADS Region 10: timing of each HUC6 basin's dominant causal agent, 1997–2025\n"
        "Rows sorted by total attributed pixel-years; each row shows ONLY its own single most-prevalent DCA class —\n"
        "secondary/co-occurring classes are not shown here (see the full multi-class breakdown in the notebook)",
        fontsize=11.5, linespacing=1.4,
    )
    fig.tight_layout()
    fig.savefig(OUT / "ads_r10_b6_prevalence_through_time.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote ads_r10_b6_prevalence_through_time.png (refined dominant-class heatmap)")

    dmg_summary = pd.read_csv(QA_DIR / "ads_r10_damagetype_subregion_class_summary.csv")
    ml_dmg_total = pd.read_csv(QA_DIR / "ads_r10_subregion_year_damagetype_multilabel_qa.csv")["attributed_pixels"].sum()
    overall_dmg = dmg_summary.groupby("native_class")["pixel_count"].sum().sort_values(ascending=False)
    overall_dmg_pct = (100 * overall_dmg / ml_dmg_total).round(2)
    bar(overall_dmg_pct, "spatial prevalence (%), all 20 HUC6 basins combined",
        "ADS R10 overall DAMAGE_TYPE spatial prevalence (secondary taxonomy)", "ads_r10_b8_damagetype_bar.png", color="#d73027", figsize=(8, 5))


def export_cross_source():
    x1 = pd.DataFrame([
        dict(source="NCCN", primary_taxonomy="change_class", subregions=4, subregion_type="park_code",
             years="1985-2017", native_classes=16,
             attributed_pixel_years=1_130_380, derived_area_ha=101_734.2, multi_label_pct=0.12),
        dict(source="GLKN (primary, agent_01)", primary_taxonomy="agent_01", subregions=7, subregion_type="park_code",
             years="1990-2021", native_classes=10,
             attributed_pixel_years=4_077_926, derived_area_ha=367_013.3, multi_label_pct=0.00),
        dict(source="GLKN (all agents, 01+02+03)", primary_taxonomy="agent_01/02/03", subregions=7, subregion_type="park_code",
             years="1990-2021", native_classes=10,
             attributed_pixel_years=4_077_926, derived_area_ha=367_013.3, multi_label_pct=1.66),
        dict(source="ADS R6 (DCA)", primary_taxonomy="DCA_CODE", subregions=7, subregion_type="dissolved EPA L3 ecoregion",
             years="1997-2025", native_classes=91,
             attributed_pixel_years=196_383_063, derived_area_ha=17_674_475.7, multi_label_pct=8.21),
        dict(source="ADS R6 (Damage Type)", primary_taxonomy="DAMAGE_TYP", subregions=7, subregion_type="dissolved EPA L3 ecoregion",
             years="1997-2025", native_classes=16,
             attributed_pixel_years=196_383_063, derived_area_ha=17_674_475.7, multi_label_pct=3.43),
        dict(source="ADS R10 (DCA)", primary_taxonomy="DCA_COMMON_NAME", subregions=20, subregion_type="HUC6 basin",
             years="1997-2025", native_classes=67,
             attributed_pixel_years=95_700_410, derived_area_ha=8_613_036.9, multi_label_pct=1.98),
        dict(source="ADS R10 (Damage Type)", primary_taxonomy="DAMAGE_TYPE", subregions=20, subregion_type="HUC6 basin",
             years="1997-2025", native_classes=13,
             attributed_pixel_years=95_700_410, derived_area_ha=8_613_036.9, multi_label_pct=2.54),
    ])
    x1.to_csv(OUT / "cross_source_summary_table.csv", index=False)
    print("wrote cross_source_summary_table.csv")


def export_multilabel_comparison():
    """Same-year multi-label attributed-pixel rate by source/view.

    Computed directly from the authoritative *_multilabel_qa.csv files
    (attributed_pixels, multi_label_pixels per subregion x year), not
    hardcoded -- overall rate = sum(multi_label_pixels) / sum(attributed_pixels)
    across all subregions/years. ADS uses the DCA view (the report's primary
    ADS taxonomy), not Damage Type.
    """
    specs = [
        ("NCCN", QA_DIR / "nccn_multilabel_qa.csv"),
        ("GLKN (primary, agent_01)", QA_DIR / "glkn_multilabel_qa_primary.csv"),
        ("GLKN (all agents, 01+02+03)", QA_DIR / "glkn_multilabel_qa_allagents.csv"),
        ("ADS R6 (DCA)", QA_DIR / "ads_r6_subregion_year_dca_multilabel_qa.csv"),
        ("ADS R10 (DCA)", QA_DIR / "ads_r10_subregion_year_dca_multilabel_qa.csv"),
    ]
    rates = {}
    for label, path in specs:
        df = pd.read_csv(path)
        attributed = df["attributed_pixels"].sum()
        multi = df["multi_label_pixels"].sum()
        rates[label] = 100 * multi / attributed
    series = pd.Series(rates)
    series.to_csv(OUT / "cross_source_multilabel_pct.csv", header=["same_year_multilabel_pct"])
    print("wrote cross_source_multilabel_pct.csv")

    bar(series, "Same-year multi-label attributed pixels (%)",
        "Same-year multi-label attribution rate by source / attribution view",
        "cross_source_multilabel_bar.png", figsize=(8, 4))


def export_methods_figure():
    """Hand-built schematic, not derived from notebook data. See docstring."""
    fig, ax = plt.subplots(figsize=(14, 15.5))
    ax.set_xlim(0, 14); ax.set_ylim(0, 19); ax.axis("off")
    fig.suptitle("How this assessment turns attributed reference data into 30 m pixel summaries", fontsize=14.5, fontweight="bold", y=0.99)

    box_w, BOX_H = 4.6, 2.1
    ROW1_TOP, ROW2_TOP, ROW3_TOP, ROW4_TOP, ROW4_H = 15.6, 11.6, 7.6, 2.6, 1.7

    def title_above(x, y_top, text, dy=0.25, **kw):
        ax.text(x, y_top + dy, text, ha="center", **kw)

    def caption_below(x, y_bot, text, dy=0.25, **kw):
        ax.text(x, y_bot - dy, text, ha="center", **kw)

    axA_l, axB_l = 0.8, 7.2
    axA_cx, axB_cx = axA_l + box_w / 2, axB_l + box_w / 2

    ax.add_patch(FancyBboxPatch((axA_l, ROW1_TOP), box_w, BOX_H, boxstyle="round,pad=0.04", facecolor="#f5f5f5", edgecolor="#555555", linewidth=1.8))
    aoi = Polygon([(axA_l+0.5, ROW1_TOP+0.3), (axA_l+3.9, ROW1_TOP+0.4), (axA_l+4.0, ROW1_TOP+1.8), (axA_l+0.6, ROW1_TOP+1.85)],
                  closed=True, fill=False, edgecolor="#555555", linestyle="--", linewidth=2.4)
    ax.add_patch(aoi)
    title_above(axA_cx, ROW1_TOP+BOX_H, "INPUT A\nAuthoritative study-area AOI", fontsize=11.5, fontweight="bold", linespacing=1.5, va="bottom")
    caption_below(axA_cx, ROW1_TOP, "Geographic / study context only --\nnot used to select or clip labels", fontsize=8.8, style="italic", color="#555555", linespacing=1.4, va="top")

    ax.add_patch(FancyBboxPatch((axB_l, ROW1_TOP), box_w, BOX_H, boxstyle="round,pad=0.04", facecolor="#fdecea", edgecolor="#c0392b", linewidth=1.8))
    p1 = Polygon([(axB_l+0.7, ROW1_TOP+0.6), (axB_l+1.7, ROW1_TOP+0.4), (axB_l+2.1, ROW1_TOP+1.3), (axB_l+1.0, ROW1_TOP+1.55)], closed=True, facecolor="#d73027", edgecolor="none", alpha=0.9)
    p2 = Polygon([(axB_l+2.3, ROW1_TOP+1.15), (axB_l+3.7, ROW1_TOP+1.35), (axB_l+3.5, ROW1_TOP+1.95), (axB_l+2.5, ROW1_TOP+1.75)], closed=True, facecolor="#4575b4", edgecolor="none", alpha=0.9)
    ax.add_patch(p1); ax.add_patch(p2)
    title_above(axB_cx, ROW1_TOP+BOX_H, "INPUT B\nPublished attributed polygons", fontsize=11.5, fontweight="bold", linespacing=1.5, va="bottom", color="#c0392b")
    caption_below(axB_cx, ROW1_TOP, "The actual change labels", fontsize=8.8, style="italic", color="#c0392b", va="top")

    axC_l = 4.0
    axC_cx = axC_l + box_w / 2
    ax.add_patch(Rectangle((axC_l, ROW2_TOP), box_w, BOX_H, fill=False, edgecolor="black", linewidth=1.4))
    aoi2 = Polygon([(axC_l+0.5, ROW2_TOP+0.3), (axC_l+3.9, ROW2_TOP+0.4), (axC_l+4.0, ROW2_TOP+1.8), (axC_l+0.6, ROW2_TOP+1.85)],
                   closed=True, fill=False, edgecolor="#555555", linestyle="--", linewidth=1.8)
    ax.add_patch(aoi2)
    p1c = Polygon([(axC_l+0.7, ROW2_TOP+0.6), (axC_l+1.7, ROW2_TOP+0.4), (axC_l+2.1, ROW2_TOP+1.3), (axC_l+1.0, ROW2_TOP+1.55)], closed=True, facecolor="#d73027", edgecolor="none", alpha=0.9)
    p2c = Polygon([(axC_l+2.3, ROW2_TOP+1.15), (axC_l+4.35, ROW2_TOP+1.4), (axC_l+3.95, ROW2_TOP+2.05), (axC_l+2.5, ROW2_TOP+1.75)], closed=True, facecolor="#4575b4", edgecolor="none", alpha=0.9)
    ax.add_patch(p1c); ax.add_patch(p2c)
    ax.add_patch(Polygon([(axC_l+0.6, ROW2_TOP+0.35), (axC_l+0.7, ROW2_TOP+0.6), (axC_l+1.0, ROW2_TOP+1.55), (axC_l+0.62, ROW2_TOP+1.75)],
                          closed=True, facecolor="none", edgecolor="#b8860b", hatch="///", linewidth=0))
    title_above(axC_cx, ROW2_TOP+BOX_H, "Polygons kept complete --\nNOT clipped to the AOI", fontsize=11.5, fontweight="bold", color="#c0392b", linespacing=1.4, va="bottom")
    caption_below(axC_cx, ROW2_TOP, "Hatched area = unlabeled ground inside the AOI --\nNOT assumed to be no-change", fontsize=8.8, style="italic", color="#b8860b", linespacing=1.4, va="top")

    ax.add_patch(FancyArrowPatch((axA_cx, ROW1_TOP-0.15), (axC_cx-0.5, ROW2_TOP+BOX_H+1.05), connectionstyle="arc3,rad=0.15", arrowstyle="-|>", mutation_scale=16, color="#555555", linewidth=1.3))
    ax.add_patch(FancyArrowPatch((axB_cx, ROW1_TOP-0.15), (axC_cx+0.5, ROW2_TOP+BOX_H+1.05), connectionstyle="arc3,rad=-0.15", arrowstyle="-|>", mutation_scale=16, color="#c0392b", linewidth=1.3))

    axG_l = 4.0
    axG_cx = axG_l + box_w / 2
    ax.add_patch(Rectangle((axG_l, ROW3_TOP), box_w, BOX_H, fill=False, edgecolor="black", linewidth=1.4))
    n = 14
    for i in range(n + 1):
        ax.plot([axG_l+i*box_w/n]*2, [ROW3_TOP, ROW3_TOP+BOX_H], color="#cccccc", linewidth=0.4)
    for i in range(7):
        ax.plot([axG_l, axG_l+box_w], [ROW3_TOP+i*BOX_H/6]*2, color="#cccccc", linewidth=0.4)
    aoi3 = Polygon([(axG_l+0.5, ROW3_TOP+0.3), (axG_l+3.9, ROW3_TOP+0.4), (axG_l+4.0, ROW3_TOP+1.8), (axG_l+0.6, ROW3_TOP+1.85)],
                   closed=True, fill=False, edgecolor="#555555", linestyle="--", linewidth=1.6)
    ax.add_patch(aoi3)
    for gx, gy, c in [(2,1,"#d73027"), (3,1,"#d73027"), (2,2,"#d73027"), (8,3,"#4575b4"), (9,3,"#4575b4"), (9,4,"#4575b4"), (10,4,"#4575b4")]:
        ax.add_patch(Rectangle((axG_l+gx*box_w/n, ROW3_TOP+gy*BOX_H/6), box_w/n, BOX_H/6, facecolor=c, alpha=0.9, edgecolor="black", linewidth=0.3))
    title_above(axG_cx, ROW3_TOP+BOX_H, "Project-defined 30 m\nreference-grid characterization", fontsize=11.5, fontweight="bold", va="bottom", linespacing=1.4)
    caption_below(axG_cx, ROW3_TOP, "Pixel-center rule; grid anchored to the CRS origin, not the AOI/window;\neach native class rasterized independently (0, 1, or >1 labels per pixel)",
                  fontsize=8.8, style="italic", color="#333333", linespacing=1.4, va="top")

    ax.add_patch(FancyArrowPatch((axC_cx, ROW2_TOP-0.15), (axG_cx, ROW3_TOP+BOX_H+1.05), arrowstyle="-|>", mutation_scale=18, color="black", linewidth=1.5))

    out_w, gap = 3.7, 0.55
    total_w = 3*out_w + 2*gap
    start_x = (14 - total_w) / 2
    labels = ["Subregion x year x\nnative class", "Attributed\npixel-years", "Spatial\nprevalence %"]
    fills = ["#eeeeee", "#dbe6f2", "#fbe1e0"]
    edges = ["#555555", "#4575b4", "#d73027"]
    centers = []
    for i, (lab, fc, ec) in enumerate(zip(labels, fills, edges)):
        bx = start_x + i*(out_w+gap)
        centers.append(bx+out_w/2)
        ax.add_patch(FancyBboxPatch((bx, ROW4_TOP), out_w, ROW4_H, boxstyle="round,pad=0.04", facecolor=fc, edgecolor=ec, linewidth=1.8))
        ax.text(bx+out_w/2, ROW4_TOP+ROW4_H/2, lab, ha="center", va="center", fontsize=11, fontweight="bold", linespacing=1.3)
        if i < 2:
            ax.add_patch(FancyArrowPatch((bx+out_w+0.05, ROW4_TOP+ROW4_H/2), (bx+out_w+gap-0.05, ROW4_TOP+ROW4_H/2), arrowstyle="-|>", mutation_scale=16, color="black", linewidth=1.3))
    title_above(centers[1], ROW4_TOP+ROW4_H, "Quantitative outputs", fontsize=11.5, fontweight="bold", va="bottom")
    caption_below(centers[0], ROW4_TOP, "grouped per subregion-year", fontsize=8.5, style="italic", color="#555555", va="top")

    elbow_y = ROW3_TOP - 1.15
    ax.add_patch(FancyArrowPatch((axG_cx, ROW3_TOP-0.15), (axG_cx, elbow_y), arrowstyle="-", color="black", linewidth=1.5))
    ax.add_patch(FancyArrowPatch((axG_cx, elbow_y), (centers[0], elbow_y), arrowstyle="-", color="black", linewidth=1.5))
    ax.add_patch(FancyArrowPatch((centers[0], elbow_y), (centers[0], ROW4_TOP+ROW4_H+0.05), arrowstyle="-|>", mutation_scale=18, color="black", linewidth=1.5))

    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(OUT / "methods_concept_figure.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote methods_concept_figure.png")


def main():
    export_nccn()
    export_glkn()
    export_ads_r6()
    export_ads_r10()
    export_cross_source()
    export_multilabel_comparison()
    export_methods_figure()
    print(f"\nAll report assets written to {OUT}")


if __name__ == "__main__":
    main()
