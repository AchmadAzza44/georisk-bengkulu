"""GeoRisk Bengkulu - peta dan analisis indikatif potensi risiko banjir berbasis GIS (alat belajar)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st
from shapely.geometry import Point
from streamlit_folium import st_folium

from src.data_loader import DataLoadError, load_geojson, load_metadata
from src.analysis_log import log_run, read_log
from src.event_validation import events_per_regency, load_events, validate_scores
from src.exporter import DISCLAIMER, map_html_bytes, pdf_report_bytes, stats_frame, to_csv_bytes
from src.map_view import (add_geojson_layer, add_layer_control, add_legend, add_marker, add_risk_layer,
                          build_folium_map, get_map_bounds, get_map_center)
from src.spatial_analysis import (FACTOR_LABELS, DEFAULT_THRESHOLDS, calculate_distance_to_river, compare_scenarios,
                                  compute_risk_score, compute_summary_statistics, merge_terrain, regency_indicators)
from src.validation import repair_geometries, validate_crs, validate_geometry

ROOT = Path(__file__).parent
TERRAIN_CSV = ROOT / "data" / "processed" / "regency_terrain.csv"
LOG_PATH = ROOT / "data" / "analysis_log.jsonl"
LAYER_FILES = {"province": "bengkulu_province.geojson", "regencies": "bengkulu_regencies.geojson",
               "rivers": "bengkulu_rivers.geojson"}

st.set_page_config(page_title="GeoRisk Bengkulu", page_icon="🗺️", layout="wide")
st.title("GeoRisk Bengkulu")
st.subheader("Analisis indikatif potensi risiko banjir berbasis kriteria spasial")
st.warning(DISCLAIMER)


@st.cache_data(show_spinner="Memuat dan memvalidasi layer...")
def load_layers(data_dir: str):
    layers, reports = {}, {}
    for key, fname in LAYER_FILES.items():
        gdf = load_geojson(Path(data_dir) / fname)
        crs_report = validate_crs(gdf)
        before = validate_geometry(gdf)
        gdf, repair = repair_geometries(gdf)
        if gdf.crs is not None and not crs_report["valid"]:
            gdf = gdf.to_crs("EPSG:4326")
        layers[key] = gdf
        reports[key] = {"crs": crs_report, "geometry": before, "repair": repair}
    return layers, reports


@st.cache_data(show_spinner="Menghitung indikator sungai per wilayah...")
def cached_indicators(data_dir: str, buffer_m: float):
    layers, _ = load_layers(data_dir)
    return regency_indicators(layers["regencies"], layers["rivers"], buffer_m)


# ---- Data ----
data_dir = st.sidebar.text_input("Direktori data", str(ROOT / "data" / "raw"))
try:
    layers, reports = load_layers(data_dir)
    metadata = load_metadata(ROOT / "data" / "metadata.json")
except DataLoadError as exc:
    st.error(f"{exc}. Siapkan data dengan `python scripts/download_data.py` lalu `python scripts/prepare_data.py`.")
    st.stop()

with st.expander("Validasi data & metadata sumber"):
    for key, rep in reports.items():
        ok = rep["crs"]["valid"] and rep["geometry"]["valid"]
        (st.success if ok else st.info)(
            f"**{LAYER_FILES[key]}** - {rep['crs']['message']} {rep['geometry']['message']} "
            f"Perbaikan: {rep['repair']['diperbaiki']} geometri diperbaiki, {rep['repair']['dibuang_kosong']} kosong dibuang.")
    st.dataframe(pd.DataFrame(metadata).T.rename_axis("berkas").reset_index(), hide_index=True)

# ---- Parameter ----
st.sidebar.header("Parameter analisis")
buffer_m = st.sidebar.slider("Radius 'dekat sungai' (m)", 250, 5000, 1000, 250)
has_terrain = TERRAIN_CSV.exists()
default_w = 0.25 if has_terrain else 0.5
w_density = st.sidebar.slider(f"Bobot: {FACTOR_LABELS['kerapatan_sungai_km_per_km2']}", 0.0, 1.0, default_w, 0.05)
w_near = st.sidebar.slider(f"Bobot: {FACTOR_LABELS['persen_area_dekat_sungai']}", 0.0, 1.0, default_w, 0.05)
w_low = w_flat = 0.0
if has_terrain:
    w_low = st.sidebar.slider(f"Bobot: {FACTOR_LABELS['persen_area_elevasi_rendah']}", 0.0, 1.0, default_w, 0.05)
    w_flat = st.sidebar.slider(f"Bobot: {FACTOR_LABELS['persen_area_datar']}", 0.0, 1.0, default_w, 0.05)
else:
    st.sidebar.caption("Faktor elevasi/kemiringan tidak aktif: jalankan `scripts/download_dem.py` lalu `scripts/compute_terrain.py`.")
low = st.sidebar.slider("Batas Rendah/Sedang", 5, 90, int(round(DEFAULT_THRESHOLDS[0])))
high = st.sidebar.slider("Batas Sedang/Tinggi", 10, 95, int(round(DEFAULT_THRESHOLDS[1])))

if w_density + w_near + w_low + w_flat == 0:
    st.error("Atur minimal satu bobot > 0.")
    st.stop()
if not low < high:
    st.error("Batas Rendah/Sedang harus lebih kecil dari batas Sedang/Tinggi.")
    st.stop()

weights = {"kerapatan_sungai_km_per_km2": w_density, "persen_area_dekat_sungai": w_near}
indicators = cached_indicators(data_dir, float(buffer_m))
if has_terrain:
    indicators = merge_terrain(indicators, pd.read_csv(TERRAIN_CSV))
    weights.update(persen_area_elevasi_rendah=w_low, persen_area_datar=w_flat)
result = compute_risk_score(indicators, weights, (float(low), float(high)))
table = result.table
stats = compute_summary_statistics(table)
regencies = layers["regencies"].reset_index(drop=True)
scored_geo = gpd.GeoDataFrame(table.assign(geometry=regencies.geometry), crs=regencies.crs)

# ---- Peta ----
st.sidebar.header("Layer peta")
show_prov = st.sidebar.checkbox("Batas provinsi", True)
show_reg = st.sidebar.checkbox("Batas kabupaten/kota", True)
show_riv = st.sidebar.checkbox("Sungai (OSM, disederhanakan)", True)
show_risk = st.sidebar.checkbox("Skor indikatif per wilayah", True)
focus = st.sidebar.selectbox("Cari / fokus ke wilayah", ["(seluruh provinsi)"] + sorted(table["regency_name"]))

m = build_folium_map(*get_map_center(layers["province"]), zoom_start=8)
if show_prov:
    add_geojson_layer(m, layers["province"], "Batas provinsi", "#1f3a93", fill_opacity=0.0, weight=3,
                      popup_fields=["province_name"])
if show_reg:
    add_geojson_layer(m, layers["regencies"], "Kabupaten/Kota", "#555555", fill_opacity=0.05, weight=1,
                      popup_fields=["regency_name"])
if show_riv:
    add_geojson_layer(m, layers["rivers"], "Sungai", "#0072B2", fill_opacity=0, weight=1.2,
                      popup_fields=["name", "waterway"], simplify_deg=0.002)
if show_risk:
    add_risk_layer(m, scored_geo, "regency_name")
    add_legend(m)
if focus != "(seluruh provinsi)":
    b = get_map_bounds(scored_geo[scored_geo["regency_name"] == focus])
    m.fit_bounds([[b["lat_min"], b["lon_min"]], [b["lat_max"], b["lon_max"]]])
click_slot = st.session_state.get("click")
if click_slot:
    add_marker(m, click_slot["lat"], click_slot["lon"], f"{click_slot['dist']:,.0f} m dari sungai terdekat")
add_layer_control(m)

left, right = st.columns([3, 2])
with left:
    st.caption("Klik titik di peta untuk menghitung jarak ke sungai terdekat (dihitung di CRS terproyeksi UTM).")
    out = st_folium(m, height=560, use_container_width=True, returned_objects=["last_clicked"])
    if out and out.get("last_clicked"):
        lat, lon = out["last_clicked"]["lat"], out["last_clicked"]["lng"]
        if not click_slot or (click_slot["lat"], click_slot["lon"]) != (lat, lon):
            pt = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
            dist = float(calculate_distance_to_river(pt, layers["rivers"])["jarak_ke_sungai_m"].iloc[0])
            st.session_state["click"] = {"lat": lat, "lon": lon, "dist": dist}
            st.rerun()
    if click_slot:
        st.info(f"Titik ({click_slot['lat']:.4f}, {click_slot['lon']:.4f}): **{click_slot['dist']:,.0f} m** ke sungai OSM terdekat. "
                "Kedekatan dengan sungai bukan bukti tunggal terjadinya banjir.")
with right:
    st.metric("Wilayah dianalisis", stats["jumlah_wilayah"])
    cols = st.columns(3)
    for col, cat in zip(cols, ("Rendah", "Sedang", "Tinggi")):
        col.metric(cat, stats["distribusi_kategori"][cat])
    shown = table if focus == "(seluruh provinsi)" else table[table["regency_name"] == focus]
    show_cols = ["peringkat", "regency_name", "skor_indikatif", "kategori", "kerapatan_sungai_km_per_km2",
                 "persen_area_dekat_sungai", "luas_km2"] + (["persen_area_elevasi_rendah", "persen_area_datar"] if has_terrain else [])
    st.dataframe(shown[show_cols].sort_values("peringkat"), hide_index=True, width="stretch")
    for note in result.notes:
        st.warning(note)

# ---- Perbandingan skenario bobot ----
st.header("Perbandingan skenario bobot")
scenarios = {"kerapatan": {"kerapatan_sungai_km_per_km2": 1.0},
             "dekat_sungai": {"persen_area_dekat_sungai": 1.0},
             "pengaturan_anda": weights}
if has_terrain:
    scenarios["hanya_sungai"] = {"kerapatan_sungai_km_per_km2": 1.0, "persen_area_dekat_sungai": 1.0}
    scenarios["hanya_terrain"] = {"persen_area_elevasi_rendah": 1.0, "persen_area_datar": 1.0}
comparison = compare_scenarios(indicators, scenarios, "regency_name")
st.dataframe(comparison.round(2), hide_index=True, width="stretch")
st.caption("Jika peringkat berubah besar antar skenario, kesimpulan sensitif terhadap pilihan bobot.")

# ---- Validasi dengan data kejadian (opsional, unggahan pengguna) ----
st.header("Validasi terhadap kejadian banjir (opsional)")
st.caption("Tidak ada data kejadian bawaan. Unggah CSV berkolom `lat`, `lon` (mis. dari BNPB/DIBI atau catatan lokal) untuk membandingkan skor dengan jumlah kejadian per wilayah.")
events_file = st.file_uploader("CSV kejadian banjir", type=["csv"], key="events")
validation_summary = None
if events_file is not None:
    try:
        events, ev_notes = load_events(events_file.getvalue())
        for note in ev_notes:
            st.warning(note)
        counts = events_per_regency(events, regencies)
        validation_summary = validate_scores(table, counts)
        st.dataframe(table[["regency_name", "skor_indikatif", "kategori"]].merge(counts, on="regency_name").sort_values("skor_indikatif", ascending=False),
                     hide_index=True, width="stretch")
        st.metric("Korelasi peringkat Spearman (skor vs jumlah kejadian)", validation_summary["spearman_rho"] if validation_summary["spearman_rho"] is not None else "n/a",
                  help=f"{validation_summary['n_kejadian']} kejadian di {validation_summary['n_wilayah']} wilayah; irisan top-3: {validation_summary['irisan_top3']}")
        for note in validation_summary["catatan"]:
            st.info(note)
    except ValueError as exc:
        st.error(str(exc))

# ---- Pencatatan analisis ----
st.header("Catatan analisis")
if st.button("Catat analisis ini"):
    entry = log_run(LOG_PATH, {"radius_m": buffer_m, "bobot": result.weights, "ambang": [low, high],
                               "fokus": focus}, {"statistik": stats, "validasi_kejadian": validation_summary},
                    [Path(data_dir) / f for f in LAYER_FILES.values()] + ([TERRAIN_CSV] if has_terrain else []))
    st.success(f"Tercatat pada {entry['waktu_utc']} (hash data disimpan).")
past = read_log(LOG_PATH, last=5)
if past:
    st.dataframe(pd.DataFrame([{"waktu_utc": e["waktu_utc"], "radius_m": e["parameter"]["radius_m"],
                                "bobot": str({k: round(v, 2) for k, v in e["parameter"]["bobot"].items()}),
                                "kategori": str(e["ringkasan"]["statistik"]["distribusi_kategori"])} for e in past]),
                 hide_index=True, width="stretch")
else:
    st.caption("Belum ada analisis tercatat.")

# ---- Ekspor (sesuai tampilan) ----
st.header("Ekspor")
params = {"Radius dekat sungai (m)": buffer_m,
          "Bobot ternormalisasi": ", ".join(f"{FACTOR_LABELS[k]}={v:.2f}" for k, v in result.weights.items() if v > 0),
          "Ambang kategori": f"<{low} Rendah, <{high} Sedang, lainnya Tinggi"}
sources = [f"{v['nama']} - {v['sumber']} ({v['lisensi']}, {v['tahun_data']})" for v in metadata.values()]
c1, c2, c3 = st.columns(3)
export_table = table[show_cols]
c1.download_button("Unduh tabel (CSV)", to_csv_bytes(export_table), "georisk_hasil.csv", "text/csv")
c2.download_button("Unduh statistik (CSV)", to_csv_bytes(stats_frame(stats)), "georisk_statistik.csv", "text/csv")
c3.download_button("Unduh peta (HTML)", map_html_bytes(m), "georisk_peta.html", "text/html")
st.download_button("Unduh laporan (PDF)",
                   pdf_report_bytes("Laporan GeoRisk Bengkulu", params, export_table.sort_values("peringkat"),
                                    stats, sources, result.notes),
                   "georisk_laporan.pdf", "application/pdf")

# ---- Metodologi ----
st.header("Metodologi dan keterbatasan")
st.markdown(
    f"""
**Data:** batas provinsi & kabupaten/kota (geoBoundaries) dan sungai OSM; sumber, lisensi, tahun, dan batasan ada di panel metadata.

**Indikator per wilayah** (dihitung di CRS UTM, satuan meter):
1. *Kerapatan sungai* = panjang sungai di dalam wilayah (km) / luas wilayah (km²).
2. *Area dekat sungai* = persen luas wilayah dalam radius **{buffer_m} m** dari sungai.
3. *Area elevasi rendah* = persen luas dengan elevasi <= 25 m (SRTM ~90 m) dan 4. *Area datar* = persen luas dengan kemiringan <= 2° (aktif bila DEM sudah diproses). Ambang adalah pilihan analis.

**Skor** = jumlah berbobot indikator yang dinormalisasi min-max **antar 10 wilayah** (0-100), lalu dikategorikan dengan
ambang {low}/{high}. Skor bersifat **relatif**: wilayah dengan skor 0 bukan "aman", wilayah 100 bukan "pasti banjir".

**Keterbatasan:** tanpa curah hujan, tata guna lahan/penutup lahan, drainase, atau data kejadian banjir bawaan; validasi hanya bila pengguna mengunggah data kejadian. Kelengkapan
sungai OSM tidak merata sehingga ikut memengaruhi indikator. Penentuan bobot dan ambang bersifat pilihan pengguna.
Detail: `docs/METHODOLOGY.md`.
"""
)
