# Laporan Singkat - GeoRisk Bengkulu
**Materi kuliah:** GIS dan analisis spasial. PRD: `docs/PRD_Tiga_Implementasi_Informatika.md` (root repo), PRD 1.

## Masalah dan tujuan
Data geografis dari banyak sumber sulit dibaca terpisah. GeoRisk menggabungkan batas wilayah, sungai, dan elevasi dalam satu peta, lalu menghitung **analisis indikatif berbasis kriteria** (bukan prediksi banjir) yang metodenya dapat ditelusuri.

## Hubungan fitur dengan materi GIS
| Konsep GIS | Implementasi | Bukti |
|---|---|---|
| Layer, atribut, popup, legenda | Folium: provinsi, kabupaten/kota, sungai, choropleth skor | screenshot 01, 03 |
| CRS dan proyeksi | validasi CRS; jarak, panjang, luas dihitung di UTM (meter), bukan derajat | `test_distance_matches_geodesic_reference` (selisih < 1% dari geodesik pyproj) |
| Validasi geometri | deteksi + `make_valid`, jumlah perbaikan ditampilkan | `test_geometry_validation_and_repair` |
| Analisis spasial | kerapatan sungai, buffer, jarak titik-sungai (`sjoin_nearest`), clip garis per wilayah | `test_indicators_known_values` (hitungan tangan: 100 km², 10 km, 20%) |
| Raster/DEM | SRTM -> elevasi dan kemiringan per wilayah (zonal statistics) | `test_slope_known_values`, `test_terrain_indicators_*` |
| Multi-criteria overlay | skor berbobot 4 faktor, bobot/ambang dapat diatur, perbandingan skenario | `test_four_factor_score_...` |
| Validasi dan keterbatasan | unggah kejadian banjir -> Spearman; halaman metodologi; catatan analisis dengan hash data | `test_events_per_regency_and_validation` |

## Temuan nyata
1. Layer kabupaten semula berisi 23 wilayah (13 milik provinsi tetangga); setelah perbaikan 10.
2. Skor semula memakai bilangan acak; kini deterministik.
3. Faktor sungai saja menempatkan Kota Bengkulu di peringkat 7; faktor elevasi/kemiringan menempatkannya di peringkat 1 (82% area <= 25 m). Korelasi peringkat antar kedua kelompok faktor hanya 0,52. **Pilihan faktor menentukan kesimpulan.**

## Hasil pengujian
29 tes pytest lulus (termasuk data nyata 10 wilayah dan tabel DEM nyata); aplikasi dijalankan di Chromium: peta merender 1.575 objek vektor, ekspor PDF terunduh valid. Detail: `TEST_PLAN.md`.

## Keterbatasan
Tanpa curah hujan, penutup lahan, drainase, dan data kejadian bawaan; **belum divalidasi** terhadap kejadian banjir nyata. Sungai OSM tidak lengkap merata; SRTM adalah permukaan. Resolusi kabupaten/kota. Bobot dan ambang adalah pilihan pengguna. Tile dasar OSM tidak dapat dimuat pada lingkungan pengembangan sehingga screenshot memakai latar abu-abu.

## Demonstrasi
`python scripts/download_data.py && python scripts/prepare_data.py` -> `python -m streamlit run app.py` -> atur bobot -> klik peta untuk jarak sungai -> unggah CSV kejadian (opsional) -> unduh CSV/HTML/PDF -> "Catat analisis ini".
