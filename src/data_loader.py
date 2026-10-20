"""Membaca layer GeoJSON beserta metadata sumbernya."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd


class DataLoadError(ValueError):
    """Berkas tidak dapat dimuat; pesan aman ditampilkan ke pengguna."""


def load_geojson(path: str | Path) -> gpd.GeoDataFrame:
    path = Path(path)
    if not path.exists():
        raise DataLoadError(f"File tidak ditemukan: {path}")
    if path.suffix.lower() not in (".geojson", ".json", ".shp"):
        raise DataLoadError(f"Format {path.suffix} tidak didukung (gunakan GeoJSON atau Shapefile).")
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:  # noqa: BLE001
        raise DataLoadError(f"{path.name} tidak dapat dibaca sebagai data spasial: {exc}") from exc
    if gdf.empty:
        raise DataLoadError(f"{path.name} tidak memiliki fitur.")
    return gdf


def load_metadata(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise DataLoadError(f"Metadata tidak ditemukan: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"Metadata bukan JSON valid: {exc}") from exc


def list_data_files(raw_dir: str | Path) -> list[Path]:
    """Daftar GeoJSON bermakna (berkas berawalan '_' adalah metadata sumber, bukan layer)."""
    root = Path(raw_dir)
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.geojson") if not p.name.startswith("_"))
