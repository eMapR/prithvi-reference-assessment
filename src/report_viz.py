"""
Reusable plotting/mapping helpers for the reference-data assessment notebook
(notebooks/reference_data_assessment.ipynb) and any future per-source
notebook sections (GLKN, ADS R6, ADS R10, cross-source).

Kept here rather than inline in the notebook so the notebook stays a short,
readable narrative rather than growing into thousands of lines of plotting
code. Nothing here performs geometry repair, standardization, or any other
data-modifying processing -- these functions only read GeoDataFrames already
produced elsewhere (data/processed/, outputs/qa/) and render them. Any
spatial predicate used here (e.g. classify_inside_outside) is a cheap,
read-only classification for display/coloring purposes, not a reproduction
of the actual processing pipeline in src/process_nccn.py.

Two rendering paths are provided deliberately:
  - folium (interactive_overlay_map): for exploratory use inside Jupyter --
    zoomable/pannable, toggleable layers. Does NOT render in a static
    HTML/PDF export of the notebook.
  - matplotlib (static_overlay_map): PDF/HTML-report-safe equivalent for
    the same layers, for the eventual exported assessment report.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import folium


# -----------------------------------------------------------------------------
# CRS helpers
# -----------------------------------------------------------------------------

def to_wgs84(gdf):
    """Return a copy reprojected to EPSG:4326 (required by folium). Never
    mutates the input; safe to call repeatedly for visualization only."""
    return gdf.to_crs("EPSG:4326")


# -----------------------------------------------------------------------------
# Read-only spatial classification (for map coloring / QA tables only --
# not a substitute for, or duplicate of, the actual processing pipeline)
# -----------------------------------------------------------------------------

def classify_inside_outside(ref_gdf, boundary_geom):
    """Per-feature classification against a single boundary geometry:
    'inside', 'straddle', or 'outside'. Same 3-way logic used in
    src/process_nccn.py's boundary_relationship_qa, recomputed here only
    for map coloring -- the authoritative aggregate numbers live in
    outputs/qa/nccn_boundary_relationship_qa.csv."""
    within = ref_gdf.geometry.within(boundary_geom)
    intersects = ref_gdf.geometry.intersects(boundary_geom)
    out = intersects.map(lambda x: None)  # placeholder, overwritten below
    labels = []
    for w, i in zip(within, intersects):
        if w:
            labels.append("inside")
        elif i:
            labels.append("straddle")
        else:
            labels.append("outside")
    return labels


CLASS_COLORS = {"inside": "#1a9850", "straddle": "#fee08b", "outside": "#d73027"}


# -----------------------------------------------------------------------------
# Static (matplotlib) maps -- PDF/HTML-report-safe
# -----------------------------------------------------------------------------

def static_overlay_map(layers, title="", figsize=(8, 8), ax=None):
    """layers: list of (gdf, plot_kwargs, label) drawn in order (first is
    bottom). Returns (fig, ax). Adds a simple legend from `label`s that have
    a 'facecolor' or 'edgecolor' set."""
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    for gdf, kwargs, label in layers:
        if len(gdf) == 0:
            continue
        gdf.plot(ax=ax, label=label, **kwargs)

    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")

    handles = []
    for _, kwargs, label in layers:
        facecolor = kwargs.get("facecolor")
        color = facecolor if facecolor and facecolor != "none" else (
            kwargs.get("color") or kwargs.get("edgecolor") or "black"
        )
        lw = 1.8 if (not facecolor or facecolor == "none") else 4
        handles.append(plt.Line2D([0], [0], color=color, lw=lw, label=label))
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)

    if own_fig:
        fig.tight_layout()
    return fig, ax


def static_inside_outside_map(ref_gdf, boundary_geom, title="", ax=None, figsize=(8, 8)):
    """Reference polygons colored by inside/straddle/outside the given
    boundary, boundary drawn as an outline on top."""
    labels = classify_inside_outside(ref_gdf, boundary_geom)
    ref = ref_gdf.copy()
    ref["_rel"] = labels

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    for cls, color in CLASS_COLORS.items():
        subset = ref[ref["_rel"] == cls]
        if len(subset):
            subset.plot(ax=ax, facecolor=color, edgecolor="none", alpha=0.75, label=cls)

    import geopandas as gpd
    gpd.GeoSeries([boundary_geom], crs=ref_gdf.crs).boundary.plot(
        ax=ax, color="black", linewidth=1.8
    )

    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal")
    handles = [plt.Line2D([0], [0], color=c, lw=4, label=k) for k, c in CLASS_COLORS.items()]
    handles.append(plt.Line2D([0], [0], color="black", lw=1.8, label="park boundary"))
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)

    if own_fig:
        fig.tight_layout()
    return fig, ax


# -----------------------------------------------------------------------------
# Interactive (folium) maps -- Jupyter-exploratory only
# -----------------------------------------------------------------------------

def interactive_overlay_map(layers, zoom_start=10):
    """layers: list of (gdf, style_dict, name, show_by_default). gdf must be
    in a geographic CRS (use to_wgs84 first) or will be reprojected here.
    Returns a folium.Map with a LayerControl so layers can be toggled.

    Only the geometry is sent to folium (style_function below uses a fixed
    style dict, never feature properties) -- this both keeps the embedded
    GeoJSON small and avoids attribute dtypes folium/JSON can't serialize
    (e.g. pandas Timestamp columns present in some sources' native schemas,
    such as GLKN's interp_date/cert_date)."""
    all_bounds = []
    m = None
    for gdf, style, name, show in layers:
        if len(gdf) == 0:
            continue
        g = gdf if str(gdf.crs).upper().find("4326") >= 0 else to_wgs84(gdf)
        g = g[["geometry"]]  # drop all attributes -- see docstring
        all_bounds.append(g.total_bounds)
        if m is None:
            minx, miny, maxx, maxy = g.total_bounds
            m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=zoom_start,
                            tiles="OpenStreetMap")
        folium.GeoJson(
            g.__geo_interface__,
            name=name,
            style_function=lambda feature, style=style: style,
            show=show,
        ).add_to(m)

    if m is not None and all_bounds:
        import numpy as np
        b = np.array(all_bounds)
        m.fit_bounds([[b[:, 1].min(), b[:, 0].min()], [b[:, 3].max(), b[:, 2].max()]])
        folium.LayerControl(collapsed=False).add_to(m)
    return m


def park_layer_style(kind):
    """Consistent styling shared by both the interactive and static maps for
    the standard layer kinds used throughout the NCCN section. HUC10 and
    HUC12 are deliberately distinguishable (different color AND dash
    pattern) since they are often shown together."""
    styles = {
        "reference": dict(color="#d73027", weight=0, fillColor="#d73027", fillOpacity=0.6),
        "park_boundary": dict(color="#000000", weight=3, fillOpacity=0),
        "huc10": dict(color="#4575b4", weight=1.6, fillOpacity=0.0),
        "huc12": dict(color="#984ea3", weight=1.0, fillOpacity=0.0, dashArray="4,3"),
    }
    return styles[kind]


def park_layer_style_mpl(kind):
    """matplotlib-kwargs equivalent of park_layer_style, for static maps."""
    styles = {
        "reference": dict(facecolor="#d73027", edgecolor="none", alpha=0.6),
        "park_boundary": dict(facecolor="none", edgecolor="#000000", linewidth=1.8),
        "huc10": dict(facecolor="none", edgecolor="#4575b4", linewidth=1.3),
        "huc12": dict(facecolor="none", edgecolor="#984ea3", linewidth=0.8, linestyle="--"),
    }
    return styles[kind]
