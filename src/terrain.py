"""Indikator elevasi dan kemiringan per wilayah dari DEM SRTM (format .hgt). Deterministik, tanpa rasterio."""

from __future__ import annotations

import gzip
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

NODATA = -32768
ARC_SEC_M = 30.8667  # panjang 1 arc-detik lintang (m)


def read_hgt(path: str | Path) -> np.ndarray:
    """Baca tile SRTM .hgt(.gz): int16 big-endian, persegi (mis. 3601x3601). Nodata menjadi NaN."""
    path = Path(path)
    raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    n = int(math.isqrt(len(raw) // 2))
    if n * n * 2 != len(raw) or n < 3:
        raise ValueError(f"Ukuran berkas DEM tidak valid: {path.name}")
    arr = np.frombuffer(raw, dtype=">i2").reshape(n, n).astype(np.float32)
    arr[arr == NODATA] = np.nan
    return arr


def tile_origin(name: str) -> tuple[int, int]:
    """'S04E102' -> (lintang_barat_daya=-4, bujur=102)."""
    name = Path(name).name.split(".")[0]
    lat = int(name[1:3]) * (1 if name[0] == "N" else -1)
    lon = int(name[4:7]) * (1 if name[3] == "E" else -1)
    return lat, lon


def mosaic(dem_dir: str | Path, step: int = 3) -> tuple[np.ndarray, float, float, float]:
    """Gabungkan semua tile menjadi satu grid, diambil tiap ``step`` sel. Kembalikan (grid, lon_min, lat_max, delta_derajat)."""
    files = sorted(Path(dem_dir).glob("*.hgt*"))
    if not files:
        raise FileNotFoundError(f"Tidak ada tile DEM di {dem_dir}. Jalankan scripts/download_dem.py.")
    origins = {f: tile_origin(f.name) for f in files}
    lats = [o[0] for o in origins.values()]
    lons = [o[1] for o in origins.values()]
    sample = read_hgt(files[0])
    per_tile = (sample.shape[0] - 1) // step
    rows, cols = (max(lats) - min(lats) + 1) * per_tile, (max(lons) - min(lons) + 1) * per_tile
    grid = np.full((rows, cols), np.nan, dtype=np.float32)
    for f, (lat, lon) in origins.items():
        arr = read_hgt(f)[:-1:step, :-1:step][:per_tile, :per_tile]  # buang baris/kolom tumpang-tindih tepi
        r0, c0 = (max(lats) - lat) * per_tile, (lon - min(lons)) * per_tile
        grid[r0 : r0 + per_tile, c0 : c0 + per_tile] = arr
    return grid, float(min(lons)), float(max(lats) + 1), step / (sample.shape[0] - 1)


def slope_degrees(elev: np.ndarray, dx_m: float, dy_m: float) -> np.ndarray:
    """Kemiringan (derajat) dengan beda pusat; sel tepi/nodata menjadi NaN."""
    dzdy, dzdx = np.gradient(elev, dy_m, dx_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def terrain_indicators(regencies: gpd.GeoDataFrame, dem_dir: str | Path, step: int = 3, zonal_stride: int = 2,
                       low_elev_m: float = 25.0, flat_deg: float = 2.0, name_column: str = "regency_name") -> pd.DataFrame:
    """Per wilayah: elevasi rata-rata/median, % area elevasi rendah (<= low_elev_m), kemiringan rata-rata, % area datar (<= flat_deg).

    Ambang adalah pilihan analis (bukan standar hidrologi) dan dicatat pada keluaran metadata.
    """
    grid, lon0, lat0, delta = mosaic(dem_dir, step)
    lat_mid = lat0 - grid.shape[0] * delta / 2
    dy = ARC_SEC_M * (delta * 3600)
    dx = dy * math.cos(math.radians(lat_mid))
    slope = slope_degrees(grid, dx, dy)
    elev, slp = grid[::zonal_stride, ::zonal_stride], slope[::zonal_stride, ::zonal_stride]
    lons = lon0 + (np.arange(elev.shape[1]) * zonal_stride + 0.5) * delta
    lats = lat0 - (np.arange(elev.shape[0]) * zonal_stride + 0.5) * delta
    rows = []
    for _, reg in regencies.to_crs("EPSG:4326").iterrows():
        minx, miny, maxx, maxy = reg.geometry.bounds
        ci = np.where((lons >= minx) & (lons <= maxx))[0]
        ri = np.where((lats >= miny) & (lats <= maxy))[0]
        if len(ci) == 0 or len(ri) == 0:
            raise ValueError(f"DEM tidak menutupi {reg[name_column]}.")
        lon_g, lat_g = np.meshgrid(lons[ci], lats[ri])
        shapely.prepare(reg.geometry)
        inside = shapely.contains_xy(reg.geometry, lon_g.ravel(), lat_g.ravel()).reshape(lon_g.shape)
        e = elev[np.ix_(ri, ci)][inside]
        s = slp[np.ix_(ri, ci)][inside]
        valid = ~np.isnan(e) & ~np.isnan(s)
        if valid.sum() == 0:
            raise ValueError(f"Tidak ada sel DEM valid untuk {reg[name_column]}.")
        e, s = e[valid], s[valid]
        rows.append({name_column: reg[name_column], "elevasi_rata_m": float(e.mean()), "elevasi_median_m": float(np.median(e)),
                     "persen_area_elevasi_rendah": float((e <= low_elev_m).mean() * 100),
                     "kemiringan_rata_derajat": float(s.mean()), "persen_area_datar": float((s <= flat_deg).mean() * 100),
                     "sel_valid": int(valid.sum()), "persen_sel_valid": float(valid.sum() / max(inside.sum(), 1) * 100)})
    return pd.DataFrame(rows).round(3)
