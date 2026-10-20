"""Unduh tile DEM (Mapzen/AWS Terrain Tiles, format 'skadi' .hgt.gz, 1 arc-detik ~30 m) yang menutupi Provinsi Bengkulu.

Sumber: https://registry.opendata.aws/terrain-tiles/ (AWS Open Data). Untuk Indonesia data dasarnya SRTM (NASA/USGS).
Atribusi dan syarat: ikuti ketentuan Terrain Tiles/SRTM; berkas DEM mentah TIDAK di-commit (data/dem/ di-.gitignore).
Tile yang tidak ada (laut lepas) dilewati.
"""

import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
DEM_DIR = ROOT / "data" / "dem"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}{lat:02d}/{ns}{lat:02d}{ew}{lon:03d}.hgt.gz"


def tile_name(lat_floor: int, lon_floor: int) -> tuple[str, str]:
    ns, ew = ("N" if lat_floor >= 0 else "S"), ("E" if lon_floor >= 0 else "W")
    return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}", URL.format(ns=ns, lat=abs(lat_floor), ew=ew, lon=abs(lon_floor))


def main() -> None:
    province = gpd.read_file(ROOT / "data" / "raw" / "bengkulu_province.geojson")
    minx, miny, maxx, maxy = province.total_bounds
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    for lat in range(math.floor(miny), math.floor(maxy) + 1):
        for lon in range(math.floor(minx), math.floor(maxx) + 1):
            name, url = tile_name(lat, lon)
            target = DEM_DIR / f"{name}.hgt.gz"
            if target.exists():
                print(f"{name}: sudah ada")
                continue
            try:
                urllib.request.urlretrieve(url, target)
                print(f"{name}: {target.stat().st_size / 1e6:.1f} MB")
            except urllib.error.HTTPError as exc:
                print(f"{name}: dilewati ({exc.code})", file=sys.stderr)


if __name__ == "__main__":
    main()
