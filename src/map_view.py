"""Peta Folium: layer, legenda, popup, dan choropleth kategori."""

from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

CATEGORY_COLORS = {"Rendah": "#fee08b", "Sedang": "#f46d43", "Tinggi": "#a50026"}
# Pola garis juga diberikan di legenda/tooltip teks sehingga warna bukan satu-satunya pembeda.


def build_folium_map(center_lat: float = -3.8, center_lon: float = 102.3, zoom_start: int = 8) -> folium.Map:
    return folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles="OpenStreetMap",
                      control_scale=True)


def _safe_fields(gdf: gpd.GeoDataFrame, fields: list[str] | None) -> list[str]:
    return [f for f in (fields or []) if f in gdf.columns]


def add_geojson_layer(m: folium.Map, gdf: gpd.GeoDataFrame, layer_name: str, color: str = "blue",
                      fill_color: str | None = None, weight: float = 2, fill_opacity: float = 0.5,
                      popup_fields: list[str] | None = None, simplify_deg: float | None = None,
                      show: bool = True) -> folium.Map:
    """Tambah layer; atribut ditampilkan sebagai popup. Fitur dikonversi ke EPSG:4326 bila perlu."""
    data = gdf.to_crs("EPSG:4326") if gdf.crs is not None else gdf
    if simplify_deg:
        data = data.copy()
        data["geometry"] = data.geometry.simplify(simplify_deg)
    fields = _safe_fields(data, popup_fields)
    keep = data[fields + ["geometry"]] if fields else data[["geometry"]]
    folium.GeoJson(
        keep.to_json(), name=layer_name, show=show,
        style_function=lambda _f: {"color": color, "weight": weight, "fillColor": fill_color or color,
                                   "fillOpacity": fill_opacity},
        popup=folium.GeoJsonPopup(fields=fields, aliases=fields) if fields else None,
        tooltip=folium.GeoJsonTooltip(fields=fields[:1], aliases=fields[:1]) if fields else None,
    ).add_to(m)
    return m


def add_risk_layer(m: folium.Map, table: gpd.GeoDataFrame, name_column: str, layer_name: str = "Skor indikatif",
                   show: bool = True) -> folium.Map:
    """Choropleth kategori; tooltip menyebut kategori & skor dalam teks."""
    data = table.to_crs("EPSG:4326")[[name_column, "skor_indikatif", "kategori", "peringkat", "geometry"]]
    folium.GeoJson(
        data.to_json(), name=layer_name, show=show,
        style_function=lambda f: {"color": "#333333", "weight": 1.5, "fillOpacity": 0.65,
                                  "fillColor": CATEGORY_COLORS.get(f["properties"]["kategori"], "#cccccc")},
        popup=folium.GeoJsonPopup(fields=[name_column, "kategori", "skor_indikatif", "peringkat"],
                                  aliases=["Wilayah", "Kategori (relatif)", "Skor indikatif", "Peringkat"]),
        tooltip=folium.GeoJsonTooltip(fields=[name_column, "kategori"], aliases=["Wilayah", "Kategori"]),
    ).add_to(m)
    return m


def add_layer_control(m: folium.Map) -> folium.Map:
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def add_legend(m: folium.Map, title: str = "Skor indikatif (relatif)",
               categories: dict[str, str] | None = None) -> folium.Map:
    categories = categories or CATEGORY_COLORS
    rows = "".join(
        f'<div><span style="background:{c};width:16px;height:16px;display:inline-block;margin-right:6px;'
        f'border:1px solid #333"></span>{name}</div>' for name, c in categories.items())
    html = (f'<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;padding:8px 10px;'
            f'border:2px solid grey;border-radius:5px;font-size:13px"><b>{title}</b>{rows}'
            f'<div style="font-size:11px;margin-top:4px">Bukan prediksi banjir</div></div>')
    m.get_root().html.add_child(folium.Element(html))
    return m


def add_marker(m: folium.Map, lat: float, lon: float, label: str) -> folium.Map:
    folium.Marker([lat, lon], tooltip=label, popup=label).add_to(m)
    return m


def map_to_html(m: folium.Map, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))


def get_map_bounds(gdf: gpd.GeoDataFrame) -> dict[str, float]:
    minx, miny, maxx, maxy = gdf.to_crs("EPSG:4326").total_bounds
    return {"lat_min": float(miny), "lat_max": float(maxy), "lon_min": float(minx), "lon_max": float(maxx)}


def get_map_center(gdf: gpd.GeoDataFrame) -> tuple[float, float]:
    b = get_map_bounds(gdf)
    return (b["lat_min"] + b["lat_max"]) / 2, (b["lon_min"] + b["lon_max"]) / 2
