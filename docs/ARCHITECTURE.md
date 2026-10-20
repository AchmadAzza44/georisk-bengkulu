# Arsitektur

```text
app.py (Streamlit)  ──>  data_loader ──> validation ──> spatial_analysis ──> map_view
                                                              │                  │
                                                              └──────> exporter <┘
```
| Modul | Tanggung jawab |
|---|---|
| `data_loader` | Baca GeoJSON/metadata; `DataLoadError` berpesan jelas |
| `validation` | CRS, geometri (+ perbaikan `make_valid`), kolom, berkas |
| `spatial_analysis` | Jarak ke sungai, indikator per wilayah, skor berbobot, kategori, skenario |
| `map_view` | Folium: layer, popup, choropleth, legenda, marker |
| `terrain` | Baca DEM .hgt, kemiringan, indikator elevasi/kemiringan per wilayah |
| `event_validation` | Muat CSV kejadian, hitung per wilayah, korelasi skor-vs-kejadian |
| `analysis_log` | Catatan analisis JSONL dengan SHA-256 data |
| `exporter` | CSV, HTML peta, PDF (ReportLab) dari data yang sedang tampil |

Alur data: file -> validasi/perbaikan -> indikator (UTM) -> skor -> peta/tabel/ekspor. Hasil dicache per (direktori, radius).
Keputusan: Streamlit + GeoPandas tanpa database/server karena data kecil (10 wilayah, 1.554 ruas sungai); rendering sungai disederhanakan 0,002° hanya untuk tampilan, perhitungan memakai geometri asli.
