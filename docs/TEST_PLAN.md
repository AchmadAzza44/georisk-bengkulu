# Test Plan
Jalankan `python -m pytest -q` (hasil terakhir: 29 lulus).
| Kasus | Diharapkan | Tes |
|---|---|---|
| Jarak titik-sungai vs referensi geodesik pyproj | selisih < 1% | test_distance_matches_geodesic_reference |
| Indikator pada wilayah 10x10 km dengan sungai 10 km | 100 km², 10 km, 0,1 km/km², 20% | test_indicators_known_values |
| Skor deterministik, A=100, B=0 | sama di dua pemanggilan | test_score_is_deterministic... |
| Bobot negatif/nol/kolom hilang, ambang salah | ValueError | test_weights_and_thresholds_validated |
| CRS berbeda / tidak ada | terdeteksi | test_crs_validation |
| Geometri tidak valid & kosong | terdeteksi, diperbaiki/dibuang | test_geometry_validation_and_repair |
| File tidak ada / salah format / kosong / rusak | DataLoadError | test_loader_errors |
| Ekspor CSV/PDF sesuai tabel | isi cocok, PDF valid | test_exports |
| 10 kabupaten hanya milik provinsi Bengkulu | tanpa Mentawai/Lahat/dst. | test_real_regencies_are_only_bengkulu_province |
| Aplikasi dengan data nyata / data hilang | 10 wilayah; pesan error jelas | test_app_smoke.py |
| Kemiringan beda-pusat pada ramp 45° | 45,0° | test_slope_known_values |
| Baca .hgt (nodata, ukuran tidak valid), nama tile | NaN, ValueError | test_hgt_roundtrip_nodata_and_tile_origin |
| Indikator terrain pada tile sintetis setengah 10 m / setengah 100 m | ~50% area rendah, >90% datar | test_terrain_indicators_known_half_low_half_high |
| Terrain: tanpa tile / di luar cakupan | error | test_terrain_errors |
| Gabungkan terrain, bobot membalik peringkat | sesuai | test_merge_terrain_validates, test_four_factor_score_... |
| Kejadian: baris tidak valid dibuang, hitung per wilayah, Spearman, kasus nol kejadian | sesuai | test_event_loading_..., test_events_per_regency_and_validation |
| Catatan analisis menyimpan hash dan menambah baris | sesuai | test_analysis_log_appends_and_hashes |
| Tabel terrain nyata masuk akal secara fisik | Kota Bengkulu rendah-datar, Lebong tinggi | test_real_terrain_table_is_physically_plausible |

Belum diuji: filter tidak mengubah data sumber di UI (filter hanya fokus tampilan), uji performa pada layer besar, uji pembukaan file ekspor di aplikasi lain.
