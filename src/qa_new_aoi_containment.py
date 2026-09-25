"""
QA: how well existing attributed reference polygons (NCCN, GLKN) fall within
newly-supplied authoritative study-area/AOI boundaries.

Inputs (raw, never modified):
  - data/raw/boundaries/nps/Prithvi_NCCN/LPa01_LEWI_MORA_NOCA_OLYM.shp
      Natasha's original-analysis (1985-2009/10/11) 10-mile-buffer study areas,
      one polygon per park (LEWI split into north/south units).
  - data/raw/boundaries/nps/Prithvi_NCCN/{MORA,NOCA,OLYM}_USFS_NPS_StudyArea.shp
      Natasha's later-analysis (1987-2017) "Protected Areas" study areas
      (NPS lands + USFS Wilderness parcels). No LEWI file exists in this set.
  - data/raw/boundaries/glkn/GLKN_LandTrendr_AOIs.shp
      GLKN's per-park LandTrendr analysis-area AOI (9 units: the 7 park_codes
      used elsewhere in this project, plus PIRO and GRPO, which have no
      reference disturbance data in our processed GLKN dataset).

This is a read-only assessment of containment -- it does NOT change subregion
definitions, rerun rasterization, or alter any pixel-summary table. See
outputs/qa/nccn_natasha_aoi_containment_qa.csv and
outputs/qa/glkn_landtrendr_aoi_containment_qa.csv for the results.
"""

import geopandas as gpd
import pandas as pd

from rasterize_common import REPO_ROOT, PROCESSED, QA_DIR

NCCN_AOI_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "nps" / "Prithvi_NCCN"
GLKN_AOI_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "glkn"

GLKN_PARKS = ["APIS", "INDU", "ISRO", "MISS", "SACN", "SLBE", "VOYA"]


def nccn_containment():
    nccn = gpd.read_parquet(PROCESSED / "nccn" / "nccn_standardized.parquet")

    lpa01 = gpd.read_file(NCCN_AOI_DIR / "LPa01_LEWI_MORA_NOCA_OLYM.shp").to_crs(nccn.crs)
    lpa01_by_park = lpa01.dissolve(by="PARK_CODE").geometry

    protected = {}
    for p in ["MORA", "NOCA", "OLYM"]:
        g = gpd.read_file(NCCN_AOI_DIR / f"{p}_USFS_NPS_StudyArea.shp")
        g["geometry"] = g.geometry.buffer(0)  # repair the 1 ring self-intersection (NOCA/Glacier Peak Wilderness)
        protected[p] = g.to_crs(nccn.crs).geometry.union_all()

    rows = []
    for park in ["MORA", "NOCA", "OLYM", "LEWI"]:
        sub = nccn[nccn.park_code == park].copy()
        sub["geometry"] = sub.geometry.buffer(0)
        total_area = sub.geometry.area.sum()
        total_count = len(sub)

        lpa_geom = lpa01_by_park.loc[park]
        area_in_lpa = sub.geometry.intersection(lpa_geom).area.sum()
        count_in_lpa = sub.geometry.intersects(lpa_geom).sum()

        row = dict(
            park=park, total_count=total_count, total_area_ha=round(total_area / 1e4, 1),
            pct_area_in_lpa01_10mi_buffer=round(100 * area_in_lpa / total_area, 2),
            pct_count_intersect_lpa01_10mi_buffer=round(100 * count_in_lpa / total_count, 2),
        )

        if park in protected:
            prot_geom = protected[park]
            area_in_prot = sub.geometry.intersection(prot_geom).area.sum()
            count_in_prot = sub.geometry.intersects(prot_geom).sum()
            row["pct_area_in_protected_areas"] = round(100 * area_in_prot / total_area, 2)
            row["pct_count_intersect_protected_areas"] = round(100 * count_in_prot / total_count, 2)
        else:
            row["pct_area_in_protected_areas"] = None
            row["pct_count_intersect_protected_areas"] = None

        rows.append(row)

    df = pd.DataFrame(rows)
    out = QA_DIR / "nccn_natasha_aoi_containment_qa.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.name}")
    return df


def glkn_containment():
    glkn = gpd.read_parquet(PROCESSED / "glkn" / "glkn_confirmed_standardized.parquet")

    aoi = gpd.read_file(GLKN_AOI_DIR / "GLKN_LandTrendr_AOIs.shp")
    aoi["park_upper"] = aoi["park"].str.upper()
    aoi["geometry"] = aoi.geometry.buffer(0)  # repair the 1 ring self-intersection (ISRO)
    assert aoi.crs.to_wkt() == glkn.crs.to_wkt(), "GLKN AOI and reference-polygon CRS mismatch"

    rows = []
    for park in GLKN_PARKS:
        sub = glkn[glkn.park_code == park].copy()
        sub["geometry"] = sub.geometry.buffer(0)
        total_area = sub.geometry.area.sum()
        total_count = len(sub)

        aoi_row = aoi[aoi.park_upper == park]
        if len(aoi_row) == 0:
            rows.append(dict(park=park, total_count=total_count, total_area_ha=round(total_area / 1e4, 1),
                              pct_area_in_landtrendr_aoi=None, pct_count_intersect_landtrendr_aoi=None,
                              note="NO AOI FOUND"))
            continue

        aoi_geom = aoi_row.geometry.union_all()
        area_in = sub.geometry.intersection(aoi_geom).area.sum()
        count_in = sub.geometry.intersects(aoi_geom).sum()
        rows.append(dict(
            park=park, total_count=total_count, total_area_ha=round(total_area / 1e4, 1),
            pct_area_in_landtrendr_aoi=round(100 * area_in / total_area, 2),
            pct_count_intersect_landtrendr_aoi=round(100 * count_in / total_count, 2),
            note="",
        ))

    df = pd.DataFrame(rows)
    out = QA_DIR / "glkn_landtrendr_aoi_containment_qa.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.name}")
    return df


def main():
    print("NCCN containment vs. Natasha's two study-area generations:")
    print(nccn_containment())
    print()
    print("GLKN containment vs. LandTrendr analysis-area AOI:")
    print(glkn_containment())


if __name__ == "__main__":
    main()
