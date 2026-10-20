"""Analisis spasial indikatif berbasis kriteria. Deterministik: tidak ada komponen acak atau data rekaan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

DEFAULT_THRESHOLDS = (100 / 3, 200 / 3)
CATEGORIES = ("Rendah", "Sedang", "Tinggi")
FACTOR_LABELS = {
    "kerapatan_sungai_km_per_km2": "Kerapatan sungai (km/km²)",
    "persen_area_dekat_sungai": "Area dekat sungai (%)",
    "persen_area_elevasi_rendah": "Area elevasi rendah <=25 m (%)",
    "persen_area_datar": "Area datar, kemiringan <=2° (%)",
}
TERRAIN_FACTORS = ("persen_area_elevasi_rendah", "persen_area_datar")


def merge_terrain(indicators: pd.DataFrame, terrain: pd.DataFrame, name_column: str = "regency_name") -> pd.DataFrame:
    """Gabungkan indikator elevasi/kemiringan ke indikator sungai; semua wilayah harus punya padanan."""
    needed = [name_column, *TERRAIN_FACTORS]
    missing = [c for c in needed if c not in terrain.columns]
    if missing:
        raise ValueError(f"Kolom terrain tidak lengkap: {', '.join(missing)}")
    merged = indicators.merge(terrain[needed + [c for c in terrain.columns if c not in needed and c not in indicators.columns]],
                              on=name_column, how="left", validate="one_to_one")
    absent = merged[merged[TERRAIN_FACTORS[0]].isna()][name_column].tolist()
    if absent:
        raise ValueError(f"Wilayah tanpa data terrain: {', '.join(absent)}")
    return merged


def projected_crs(gdf: gpd.GeoDataFrame):
    """CRS UTM yang sesuai dengan lokasi data (satuan meter) untuk panjang/luas/jarak."""
    if gdf.crs is None:
        raise ValueError("CRS tidak terdefinisi; tetapkan CRS sebelum analisis spasial.")
    return gdf.estimate_utm_crs()


def calculate_distance_to_river(points_gdf: gpd.GeoDataFrame, rivers_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Jarak (meter) tiap titik ke sungai terdekat, dihitung di CRS terproyeksi, bukan derajat."""
    if rivers_gdf.empty:
        raise ValueError("Layer sungai kosong; jarak tidak dapat dihitung.")
    if points_gdf.empty:
        out = points_gdf.copy()
        out["jarak_ke_sungai_m"] = pd.Series(dtype=float)
        return out
    crs = projected_crs(rivers_gdf)
    pts = points_gdf.to_crs(crs)[["geometry"]].reset_index(drop=True)
    rivers = rivers_gdf.to_crs(crs)[["geometry"]]
    joined = gpd.sjoin_nearest(pts, rivers, how="left", distance_col="jarak_ke_sungai_m")
    distance = joined.groupby(level=0)["jarak_ke_sungai_m"].min().reindex(range(len(pts)))
    out = points_gdf.copy()
    out["jarak_ke_sungai_m"] = distance.to_numpy().round(1)
    return out


def regency_indicators(regencies: gpd.GeoDataFrame, rivers: gpd.GeoDataFrame, buffer_m: float = 1000.0) -> pd.DataFrame:
    """Indikator sungai per wilayah: kerapatan (km/km²) dan persen luas dalam radius ``buffer_m`` dari sungai."""
    if buffer_m <= 0:
        raise ValueError("buffer_m harus > 0.")
    if regencies.empty or rivers.empty:
        raise ValueError("Layer wilayah dan sungai tidak boleh kosong.")
    crs = projected_crs(regencies)
    reg = regencies.to_crs(crs).reset_index(drop=True)
    riv = rivers.to_crs(crs)
    riv = riv[~riv.geometry.is_empty & riv.geometry.notna()].reset_index(drop=True)
    index = riv.sindex
    rows = []
    for geom in reg.geometry:
        hits = riv.geometry.iloc[index.query(geom, predicate="intersects")]
        area_km2 = geom.area / 1e6
        if hits.empty:
            length_km, near_pct = 0.0, 0.0
        else:
            length_km = float(hits.intersection(geom).length.sum() / 1000)
            near_pct = float(hits.buffer(buffer_m).union_all().intersection(geom).area / geom.area * 100)
        rows.append({"luas_km2": area_km2, "panjang_sungai_km": length_km,
                     "kerapatan_sungai_km_per_km2": length_km / area_km2 if area_km2 else 0.0,
                     "persen_area_dekat_sungai": near_pct})
    out = pd.DataFrame(rows)
    name_cols = [c for c in regencies.columns if c != "geometry"]
    return pd.concat([regencies[name_cols].reset_index(drop=True), out.round(4)], axis=1)


@dataclass(frozen=True)
class ScoreResult:
    table: pd.DataFrame
    weights: dict[str, float]
    notes: list[str]


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError("Minimal satu faktor diperlukan.")
    if any(w < 0 for w in weights.values()):
        raise ValueError("Bobot tidak boleh negatif.")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Jumlah bobot harus > 0.")
    return {k: w / total for k, w in weights.items()}


def compute_risk_score(df: pd.DataFrame, weights: dict[str, float],
                       thresholds: tuple[float, float] = DEFAULT_THRESHOLDS) -> ScoreResult:
    """Skor 0-100 = jumlah berbobot faktor yang dinormalisasi min-max ANTAR wilayah studi (bersifat relatif).

    Skor menunjukkan peringkat relatif kriteria sungai, bukan peluang banjir. Tanpa validasi kejadian.
    """
    missing = [c for c in weights if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom faktor tidak ditemukan: {', '.join(missing)}")
    low, high = thresholds
    if not 0 < low < high < 100:
        raise ValueError("Ambang harus memenuhi 0 < batas_sedang < batas_tinggi < 100.")
    w = normalize_weights(weights)
    notes: list[str] = []
    score = pd.Series(0.0, index=df.index)
    result = df.copy()
    for col, weight in w.items():
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise ValueError(f"Faktor '{col}' memiliki nilai kosong/non-numerik.")
        span = values.max() - values.min()
        if span == 0:
            norm = pd.Series(0.0, index=df.index)
            notes.append(f"Faktor '{col}' bernilai sama di semua wilayah sehingga tidak membedakan skor.")
        else:
            norm = (values - values.min()) / span
        result[f"norm_{col}"] = norm.round(4)
        score += norm * weight * 100
    result["skor_indikatif"] = score.round(2)
    result["kategori"] = classify(result["skor_indikatif"], thresholds)
    result["peringkat"] = result["skor_indikatif"].rank(ascending=False, method="min").astype(int)
    return ScoreResult(result, w, notes)


def classify(scores: pd.Series, thresholds: tuple[float, float] = DEFAULT_THRESHOLDS) -> pd.Series:
    low, high = thresholds
    return pd.Series(np.select([scores < low, scores < high], CATEGORIES[:2], CATEGORIES[2]), index=scores.index)


def compare_scenarios(df: pd.DataFrame, scenarios: dict[str, dict[str, float]], name_column: str) -> pd.DataFrame:
    """Bandingkan skema bobot: skor dan peringkat tiap wilayah per skenario."""
    frames = []
    for label, weights in scenarios.items():
        res = compute_risk_score(df, weights).table[[name_column, "skor_indikatif", "peringkat"]]
        frames.append(res.rename(columns={"skor_indikatif": f"skor_{label}", "peringkat": f"peringkat_{label}"})
                      .set_index(name_column))
    return pd.concat(frames, axis=1).reset_index()


def compute_summary_statistics(table: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {"jumlah_wilayah": int(len(table))}
    if "kategori" in table:
        stats["distribusi_kategori"] = {c: int((table["kategori"] == c).sum()) for c in CATEGORIES}
    if "skor_indikatif" in table and len(table):
        stats.update(skor_rata_rata=round(float(table["skor_indikatif"].mean()), 2),
                     skor_tertinggi=float(table["skor_indikatif"].max()),
                     skor_terendah=float(table["skor_indikatif"].min()))
    return stats
