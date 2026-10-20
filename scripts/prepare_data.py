"""Prepare Bengkulu study-area layers from downloaded public source data.

Run after scripts/download_data.py has placed the geoBoundaries and OSM files
in data/raw/. This script clips them to the Bengkulu study area and writes
source-faithful subsets (data/raw/) plus analysis-ready layers (data/processed/).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

STUDY_AREA_NAME = "Bengkulu"
MIN_INSIDE_FRACTION = 0.5


def _read_geojson(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"File sumber tidak ditemukan: {path}. Jalankan scripts/download_data.py dahulu."
        )
    return gpd.read_file(path)


def build_admin_layers() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    adm1 = _read_geojson(RAW / "idn_adm1.geojson")
    province = adm1[adm1["shapeName"] == STUDY_AREA_NAME].copy()
    if province.empty:
        raise RuntimeError("Provinsi Bengkulu tidak ditemukan pada layer ADM1.")

    adm2 = _read_geojson(RAW / "idn_adm2.geojson")
    # `intersects` saja keliru: kabupaten tetangga yang hanya bersinggungan di perbatasan ikut terpilih.
    # Pilih kabupaten/kota yang mayoritas luasnya berada di dalam provinsi (dihitung di CRS terproyeksi).
    projected = adm2.to_crs(adm2.estimate_utm_crs())
    province_proj = province.to_crs(projected.crs).geometry.union_all()
    inside_fraction = projected.geometry.intersection(province_proj).area / projected.geometry.area
    regencies = adm2[inside_fraction >= MIN_INSIDE_FRACTION].copy()
    regencies["regency_name"] = regencies["shapeName"].astype(str)
    regencies = regencies[["regency_name", "shapeID", "geometry"]]

    province = province[["shapeName", "shapeID", "geometry"]].rename(
        columns={"shapeName": "province_name"}
    )
    return province, regencies


def clip_rivers(rivers: gpd.GeoDataFrame, province: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    province_union = province.geometry.union_all()
    clipped = gpd.clip(rivers, province_union)
    clipped = clipped[~clipped.geometry.is_empty].copy()
    if "waterway" not in clipped.columns:
        clipped["waterway"] = "river"
    if "name" not in clipped.columns:
        clipped["name"] = None
    return clipped[["name", "waterway", "geometry"]].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Siapkan layer area studi Bengkulu.")
    parser.add_argument("--skip-rivers", action="store_true", help="Hanya proses batas administrasi.")
    args = parser.parse_args()

    PROCESSED.mkdir(parents=True, exist_ok=True)

    province, regencies = build_admin_layers()
    province.to_file(RAW / "bengkulu_province.geojson", driver="GeoJSON")
    regencies.to_file(RAW / "bengkulu_regencies.geojson", driver="GeoJSON")
    print(f"Provinsi: {len(province)} fitur, kabupaten/kota: {len(regencies)} fitur")

    if not args.skip_rivers:
        rivers_path = RAW / "osm_rivers.geojson"
        if rivers_path.exists():
            rivers = clip_rivers(_read_geojson(rivers_path), province)
            rivers.to_file(RAW / "bengkulu_rivers.geojson", driver="GeoJSON")
            print(f"Sungai: {len(rivers)} fitur")
        else:
            print("osm_rivers.geojson belum ada, lewati pemrosesan sungai.")

    (PROCESSED).mkdir(parents=True, exist_ok=True)
    print("Selesai. Layer tersimpan di data/raw dan data/processed.")


if __name__ == "__main__":
    main()
