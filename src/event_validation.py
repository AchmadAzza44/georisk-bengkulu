"""Validasi skor terhadap data kejadian banjir yang DIUNGGAH pengguna (tidak ada data kejadian bawaan)."""

from __future__ import annotations

import io
from typing import Any

import geopandas as gpd
import pandas as pd

LAT_RANGE, LON_RANGE = (-11.5, 6.5), (94.5, 141.5)  # kotak kasar wilayah Indonesia


def load_events(raw: bytes) -> tuple[gpd.GeoDataFrame, list[str]]:
    """CSV dengan kolom `lat`, `lon` (opsional `tanggal`). Baris tidak valid dibuang dan dilaporkan."""
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"CSV kejadian tidak dapat dibaca: {exc}") from exc
    cols = {c.lower(): c for c in df.columns}
    if "lat" not in cols or "lon" not in cols:
        raise ValueError("Kolom wajib 'lat' dan 'lon' tidak ditemukan.")
    lat, lon = pd.to_numeric(df[cols["lat"]], errors="coerce"), pd.to_numeric(df[cols["lon"]], errors="coerce")
    ok = lat.between(*LAT_RANGE) & lon.between(*LON_RANGE)
    notes = []
    if (~ok).any():
        notes.append(f"{int((~ok).sum())} baris dibuang (koordinat kosong/di luar wilayah Indonesia).")
    if ok.sum() == 0:
        raise ValueError("Tidak ada kejadian dengan koordinat valid.")
    gdf = gpd.GeoDataFrame(df[ok].reset_index(drop=True), geometry=gpd.points_from_xy(lon[ok], lat[ok]), crs="EPSG:4326")
    return gdf, notes


def events_per_regency(events: gpd.GeoDataFrame, regencies: gpd.GeoDataFrame, name_column: str = "regency_name") -> pd.DataFrame:
    joined = gpd.sjoin(events, regencies.to_crs(events.crs)[[name_column, "geometry"]], how="inner", predicate="within")
    counts = joined.groupby(name_column).size()
    out = pd.DataFrame({name_column: regencies[name_column]}).merge(counts.rename("jumlah_kejadian"), on=name_column, how="left")
    out["jumlah_kejadian"] = out["jumlah_kejadian"].fillna(0).astype(int)
    return out


def validate_scores(table: pd.DataFrame, counts: pd.DataFrame, name_column: str = "regency_name") -> dict[str, Any]:
    """Korelasi peringkat Spearman antara skor dan jumlah kejadian + irisan 3 teratas. Dengan n kecil, hanya indikatif."""
    merged = table[[name_column, "skor_indikatif"]].merge(counts, on=name_column)
    n_events = int(merged["jumlah_kejadian"].sum())
    n = len(merged)
    result: dict[str, Any] = {"n_wilayah": n, "n_kejadian": n_events, "spearman_rho": None, "irisan_top3": None, "catatan": []}
    if n_events == 0:
        result["catatan"].append("Tidak ada kejadian yang jatuh di dalam wilayah studi.")
        return result
    if merged["jumlah_kejadian"].nunique() > 1:
        result["spearman_rho"] = round(float(merged["skor_indikatif"].corr(merged["jumlah_kejadian"], method="spearman")), 3)
    k = min(3, n)
    top_score = set(merged.nlargest(k, "skor_indikatif")[name_column])
    top_events = set(merged.nlargest(k, "jumlah_kejadian")[name_column])
    result["irisan_top3"] = len(top_score & top_events)
    result["catatan"] += [
        f"n = {n} wilayah: korelasi dengan sampel sekecil ini tidak signifikan secara statistik dan hanya indikatif.",
        "Jumlah kejadian dipengaruhi pelaporan dan jumlah penduduk, bukan hanya bahaya fisik.",
    ]
    return result
