"""Validasi CRS, geometri, kolom, dan berkas sebelum analisis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely import make_valid

EXPECTED_CRS = "EPSG:4326"


def validate_crs(gdf: gpd.GeoDataFrame, expected_crs: str = EXPECTED_CRS) -> dict[str, Any]:
    result: dict[str, Any] = {"valid": False, "current_crs": str(gdf.crs) if gdf.crs else "None",
                              "expected_crs": expected_crs, "message": ""}
    if gdf.crs is None:
        result["message"] = "CRS tidak terdefinisi. Tetapkan CRS sebelum analisis spasial."
    elif gdf.crs.equals(expected_crs):
        result.update(valid=True, message=f"CRS sesuai: {gdf.crs.to_string()}")
    else:
        result["message"] = (f"CRS {gdf.crs.to_string()} berbeda dari {expected_crs}; "
                             "data akan dikonversi dengan to_crs() sebelum ditampilkan.")
    return result


def validate_geometry(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    if gdf.empty:
        return {"valid": False, "total_features": 0, "valid_geometries": 0, "invalid_geometries": 0,
                "empty_geometries": 0, "message": "Dataset tidak memiliki fitur."}
    empty = gdf.geometry.isna() | gdf.geometry.is_empty
    invalid = ~empty & ~gdf.geometry.is_valid
    result = {"total_features": int(len(gdf)), "valid_geometries": int((~empty & ~invalid).sum()),
              "invalid_geometries": int(invalid.sum()), "empty_geometries": int(empty.sum())}
    result["valid"] = result["invalid_geometries"] == 0 and result["empty_geometries"] == 0
    result["message"] = ("Semua geometri valid." if result["valid"] else
                         f"{result['invalid_geometries']} geometri tidak valid dan {result['empty_geometries']} kosong.")
    return result


def repair_geometries(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    """Perbaiki geometri tidak valid dengan ``make_valid`` dan buang yang kosong; kembalikan jumlah tindakan."""
    out = gdf.copy()
    empty = out.geometry.isna() | out.geometry.is_empty
    invalid = ~empty & ~out.geometry.is_valid
    if invalid.any():
        out.loc[invalid, "geometry"] = out.loc[invalid, "geometry"].apply(make_valid)
    out = out[~empty].reset_index(drop=True)
    return out, {"diperbaiki": int(invalid.sum()), "dibuang_kosong": int(empty.sum())}


def validate_columns(gdf: gpd.GeoDataFrame, required_columns: list[str]) -> dict[str, Any]:
    missing = [c for c in required_columns if c not in gdf.columns]
    return {"valid": not missing, "required_columns": required_columns, "missing_columns": missing,
            "message": "Semua kolom wajib tersedia." if not missing else
            f"Kolom wajib tidak ditemukan: {', '.join(missing)}."}


def validate_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {"valid": False, "message": f"File tidak ditemukan: {path}"}
    try:
        gpd.read_file(path)
    except Exception as exc:  # noqa: BLE001 - pesan ramah untuk berkas korup
        return {"valid": False, "message": f"File tidak dapat dibaca sebagai data spasial: {exc}"}
    return {"valid": True, "message": "File dapat dibaca."}
