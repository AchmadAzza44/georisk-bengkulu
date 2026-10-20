# GeoRisk Bengkulu

Sistem Pemetaan dan Analisis Potensi Risiko Banjir Berbasis GIS.

## Deskripsi

GeoRisk Bengkulu adalah aplikasi GIS untuk mengeksplorasi informasi geografis dan
membuat analisis indikatif potensi risiko banjir berdasarkan faktor spasial yang
tersedia. Aplikasi menyajikan peta interaktif, layer sungai dan batas wilayah,
faktor geografis, kategori skor, statistik, serta laporan.

## Fitur yang berjalan

- Peta interaktif: batas provinsi, 10 kabupaten/kota, sungai OSM, choropleth skor, kontrol layer, legenda, popup atribut, pencarian/fokus wilayah.
- Validasi CRS & geometri otomatis (perbaikan dilaporkan); panel metadata sumber/lisensi.
- Indikator sungai dan **elevasi/kemiringan (SRTM)** per wilayah dihitung di CRS UTM; skor berbobot yang dapat dikonfigurasi (bobot, radius, ambang), **deterministik**.
- Perbandingan skenario bobot; klik peta untuk jarak ke sungai terdekat.
- Ekspor CSV, HTML peta, dan laporan PDF (parameter, hasil, sumber, keterbatasan).

- Validasi opsional terhadap CSV kejadian banjir unggahan pengguna; pencatatan analisis dengan hash data.

**Bukan** prediksi banjir atau peringatan dini. Tanpa hujan/penutup lahan; belum divalidasi terhadap kejadian nyata. Baca `docs/METHODOLOGY.md`.

## Struktur folder
```text
app.py                # titik masuk Streamlit
src/                  # data_loader, validation, spatial_analysis, terrain, event_validation, analysis_log, map_view, exporter
data/raw/             # batas wilayah (geoBoundaries) dan sungai (OSM); file berawalan _ = metadata sumber
data/processed/       # regency_terrain.csv (+ .meta.json provenance); data/dem/ = tile SRTM (tidak di-commit)
data/metadata.json    # sumber, lisensi, CRS, batasan tiap layer
scripts/              # download_data, prepare_data, download_dem, compute_terrain
tests/                # 29 tes pytest
docs/                 # DATA_SOURCES, METHODOLOGY, ARCHITECTURE, TEST_PLAN, PROGRESS, LAPORAN, screenshots/
```

## Prasyarat

- Python 3.10+
- GeoPandas, Shapely, Folium, Pandas, Streamlit

## Instalasi

```powershell
pip install -r requirements.txt
python -m pytest -q   # opsional: 29 tes
```

## Menjalankan Aplikasi

```powershell
python -m streamlit run app.py
```

## Unduhan Data

Sebelum menjalankan aplikasi, unduh dan siapkan data:

```powershell
python scripts/download_data.py
python scripts/prepare_data.py
python scripts/download_dem.py       # opsional: DEM SRTM (~109 MB) untuk faktor elevasi
python scripts/compute_terrain.py    # hasil sudah di-commit di data/processed/
```

## Sumber Data

- Batas administrasi: geoBoundaries (ADM1 ODbL 1.0; ADM2 CC BY 3.0 IGO)
- Sungai: OpenStreetMap via Overpass API (ODbL)

Lihat `docs/DATA_SOURCES.md` untuk detail lengkap.

## Lisensi

Data sumber menggunakan lisensi publik. Lihat `docs/DATA_SOURCES.md` untuk detail.
