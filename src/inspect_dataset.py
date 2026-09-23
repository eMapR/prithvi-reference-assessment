"""
Read-only first-look inspection for a single vector dataset (File
Geodatabase, GeoPackage, or shapefile) BEFORE any processing logic is
written against it.

This script never writes to, or modifies, the input path.

Usage:
    python src/inspect_dataset.py data/raw/nccn/some_dataset.gdb
    python src/inspect_dataset.py data/raw/glkn/some_dataset.gpkg --layer disturbance
    python src/inspect_dataset.py data/raw/ads/r6/some_dataset.shp --save

For each layer, reports:
  - geometry type(s)
  - CRS, and whether it is geographic (area must not be computed from it directly)
  - feature count
  - field list and dtypes
  - heuristic (name-based only -- always confirm by eye) guesses at:
      unique ID / change-class / year / region-ID / severity-confidence fields
  - unique values of likely categorical fields (class, region ID)
  - year range of likely year fields
  - geometry validity (invalid / empty / missing counts -- NOT repaired here)
  - an approximate self-intersection signal, skipped above
    MAX_FEATURES_FOR_OVERLAP_CHECK since exact overlap accounting belongs in
    the actual region-summary step, not a first-look inspection
"""

import argparse
import sys
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd

ID_KEYWORDS = ['objectid', 'fid', 'uid', 'gid', 'id']
CLASS_KEYWORDS = ['class', 'agent', 'cause', 'damage', 'disturb', 'type', 'dca']
YEAR_KEYWORDS = ['year', 'yr', 'date', 'survey']
REGION_KEYWORDS = ['park', 'unit', 'huc', 'region', 'forest']
SEVERITY_KEYWORDS = ['severity', 'sever', 'confidence', 'conf', 'sev']

MAX_FEATURES_FOR_OVERLAP_CHECK = 3000


def guess_fields(columns, keywords):
    return [c for c in columns if any(k in c.lower() for k in keywords)]


def inspect_layer(path, layer_name, out_lines):
    out_lines.append(f"\n{'=' * 70}\nLAYER: {layer_name}\n{'=' * 70}")
    gdf = gpd.read_file(path, layer=layer_name)

    if not isinstance(gdf, gpd.GeoDataFrame) or 'geometry' not in gdf.columns:
        out_lines.append("NON-SPATIAL TABLE (no geometry column) -- likely a lookup/code/schema table.")
        out_lines.append(f"Row count: {len(gdf)}")
        out_lines.append(f"\nFields ({len(gdf.columns)}):")
        for col in gdf.columns:
            out_lines.append(f"  - {col}: {gdf[col].dtype}")
        if len(gdf) <= 50:
            out_lines.append(f"\nFull contents ({len(gdf)} rows):")
            out_lines.append(gdf.to_string())
        else:
            out_lines.append(f"\nFirst 20 rows (of {len(gdf)}):")
            out_lines.append(gdf.head(20).to_string())
        return

    out_lines.append(f"Feature count: {len(gdf)}")
    out_lines.append(f"Geometry type(s): {sorted(gdf.geom_type.dropna().unique().tolist())}")
    out_lines.append(f"CRS: {gdf.crs}")
    if gdf.crs is not None and gdf.crs.is_geographic:
        out_lines.append(
            "  NOTE: geographic CRS -- do not compute area directly from this; "
            "reproject to an appropriate projected/equal-area CRS first."
        )

    geom_col = gdf.geometry.name
    non_geom_cols = [c for c in gdf.columns if c != geom_col]

    out_lines.append(f"\nFields ({len(non_geom_cols)}):")
    for col in non_geom_cols:
        out_lines.append(f"  - {col}: {gdf[col].dtype}")

    id_candidates = guess_fields(non_geom_cols, ID_KEYWORDS)
    class_candidates = guess_fields(non_geom_cols, CLASS_KEYWORDS)
    year_candidates = guess_fields(non_geom_cols, YEAR_KEYWORDS)
    region_candidates = guess_fields(non_geom_cols, REGION_KEYWORDS)
    severity_candidates = guess_fields(non_geom_cols, SEVERITY_KEYWORDS)

    out_lines.append("\nHeuristic field guesses (name-based only -- confirm by eye):")
    out_lines.append(f"  Likely unique ID field(s):           {id_candidates or 'none found'}")
    out_lines.append(f"  Likely change-class field(s):        {class_candidates or 'none found'}")
    out_lines.append(f"  Likely year field(s):                {year_candidates or 'none found'}")
    out_lines.append(f"  Likely region/park/HUC field(s):      {region_candidates or 'none found'}")
    out_lines.append(f"  Likely severity/confidence field(s):  {severity_candidates or 'none found'}")

    for col in dict.fromkeys(class_candidates + region_candidates):  # de-duped, order preserved
        try:
            vc = gdf[col].value_counts(dropna=False)
            out_lines.append(f"\nUnique values of '{col}' ({vc.shape[0]} distinct):")
            out_lines.append(vc.to_string())
        except TypeError:
            out_lines.append(f"\n  (could not summarize '{col}': unhashable value type)")

    for col in year_candidates:
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            out_lines.append(
                f"\nDate range for '{col}' (native datetime column): "
                f"{gdf[col].min()} - {gdf[col].max()} ({int(gdf[col].isna().sum())} missing)"
            )
            continue
        numeric = pd.to_numeric(gdf[col], errors='coerce')
        n_bad = numeric.isna().sum() - gdf[col].isna().sum()
        out_lines.append(
            f"\nYear range for '{col}': {numeric.min()} - {numeric.max()} "
            f"({int(n_bad)} non-numeric values, {int(gdf[col].isna().sum())} missing)"
        )

    valid = gdf.geometry.is_valid
    n_invalid = int((~valid).sum())
    n_empty = int(gdf.geometry.is_empty.sum())
    n_missing = int(gdf.geometry.isna().sum())
    out_lines.append(
        f"\nGeometry validity: {n_invalid} invalid, {n_empty} empty, "
        f"{n_missing} missing (of {len(gdf)}). Not repaired -- raw data untouched."
    )

    n = len(gdf)
    if n == 0:
        out_lines.append("\nOverlap check: skipped (no features).")
    elif n > MAX_FEATURES_FOR_OVERLAP_CHECK:
        out_lines.append(
            f"\nOverlap check: skipped ({n} features > {MAX_FEATURES_FOR_OVERLAP_CHECK} limit). "
            f"Exact same-class/cross-class/cross-year overlap accounting belongs in the "
            f"region-summary step, not this first-look inspection."
        )
    else:
        try:
            valid_gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]
            joined = gpd.sjoin(valid_gdf, valid_gdf, predicate='intersects', how='inner')
            joined = joined[joined.index != joined['index_right']]
            n_pairs = len(joined) // 2  # each intersecting pair appears twice (symmetric join)
            out_lines.append(
                f"\nOverlap check (approximate): {n_pairs} intersecting feature pairs among "
                f"{len(valid_gdf)} valid features. Does not distinguish same-class vs "
                f"cross-class vs cross-year overlap -- that comes later."
            )
        except Exception as exc:
            out_lines.append(f"\nOverlap check failed: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('path', help='Path to .gdb / .gpkg / .shp')
    parser.add_argument('--layer', help='Inspect only this layer (default: all layers)')
    parser.add_argument(
        '--save', action='store_true',
        help='Also write the report to outputs/qa/<dataset>_inspection.txt'
    )
    args = parser.parse_args()

    raw_path = args.path
    is_gdal_virtual = raw_path.startswith('/vsi')
    path = raw_path if is_gdal_virtual else Path(raw_path)
    if not is_gdal_virtual and not path.exists():
        sys.exit(f"Path not found: {path}")

    try:
        layers = fiona.listlayers(str(path))
    except Exception as exc:
        sys.exit(f"Could not list layers (is this a valid GDB/GPKG/shapefile?): {exc}")

    out_lines = [f"DATASET INSPECTION: {path}", f"Layers found: {layers}"]

    target_layers = [args.layer] if args.layer else layers
    for layer_name in target_layers:
        inspect_layer(path, layer_name, out_lines)

    report = "\n".join(out_lines)
    print(report)

    if args.save:
        qa_dir = Path(__file__).resolve().parent.parent / 'outputs' / 'qa'
        qa_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(raw_path.replace('/vsizip/', '')).stem if is_gdal_virtual else path.stem
        out_path = qa_dir / f"{stem}_inspection.txt"
        out_path.write_text(report)
        print(f"\nSaved report to {out_path}")


if __name__ == '__main__':
    main()
