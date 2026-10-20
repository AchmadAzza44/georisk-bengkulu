# Data Sources

## Batas Administrasi (geoBoundaries)
- **Sumber:** https://www.geoboundaries.org/
- **File mentah:** `idn_adm1.geojson`, `idn_adm2.geojson` (seluruh Indonesia); metadata sumber: `_geoboundaries_idn_adm*.json`
- **ADM1 (provinsi):** tahun 2017, sumber OpenStreetMap/Wambacher, lisensi ODbL 1.0
- **ADM2 (kabupaten/kota):** tahun 2020, sumber BPS, WFP, OCHA ROAP, lisensi **CC BY 3.0 IGO** (bukan ODbL)
- **Build geoBoundaries:** 12 Des 2023
- **CRS:** EPSG:4326 (WGS 84)
- **Turunan:** `bengkulu_province.geojson` (1 fitur) dan `bengkulu_regencies.geojson` (10 kabupaten/kota). Kabupaten dipilih bila >=50% luasnya berada di provinsi; versi sebelumnya memakai `intersects` sehingga 13 kabupaten provinsi tetangga ikut tersaring (sudah diperbaiki)
- **Keterbatasan:** Data batas administrasi mungkin tidak mencerminkan perubahan terbaru.

## Sungai (OpenStreetMap)
- **Sumber:** https://www.openstreetmap.org/ via Overpass API
- **File:** `osm_rivers.geojson` (mentah) dan `bengkulu_rivers.geojson` (dipotong ke provinsi, 1.554 fitur)
- **Tanggal unduhan:** 19 Oktober 2026
- **Lisensi:** Open Data Commons Open Database License 1.0 (ODbL)
- **CRS:** EPSG:4326 (WGS 84)
- **Cakupan:** Wilayah Provinsi Bengkulu
- **Keterbatasan:** Data OSM bersifat crowdsourced dan mungkin tidak lengkap atau tidak akur
  ati di semua daerah.

## Elevasi (DEM)
- **Sumber:** AWS Terrain Tiles (tile `skadi`, `.hgt.gz`, 1 arc-detik ~30 m), https://registry.opendata.aws/terrain-tiles/ ; untuk Indonesia data dasarnya SRTM (NASA/USGS).
- **Berkas:** `data/dem/*.hgt.gz` (16 tile, ~109 MB, **tidak di-commit**; unduh dengan `scripts/download_dem.py`). Turunan yang di-commit: `data/processed/regency_terrain.csv` + `regency_terrain.meta.json` (SHA-256 tile).
- **Tanggal unduhan:** 20 Oktober 2026. **Lisensi/atribusi:** ikuti ketentuan Terrain Tiles dan SRTM; lisensi eksplisit tidak diverifikasi dari sumber ini, periksa sebelum redistribusi tile mentah.
- **CRS:** EPSG:4326. **Keterbatasan:** permukaan (bukan tanah), void SRTM bernilai NaN dan dikecualikan (0% pada hasil saat ini).

## Data yang belum tersedia
Curah hujan, penutup/tata guna lahan, dan data kejadian banjir tidak disertakan. Data kejadian dapat diunggah pengguna untuk validasi (lihat `METHODOLOGY.md`).

## Catatan
- Setiap dataset harus mencatat sumber, tanggal, lisensi, CRS, resolusi atau skala,
  cakupan, dan keterbatasan.
- Jangan menganggap semua data tersedia sebelum memeriksanya.
- Periksa dan samakan CRS sebelum operasi spasial.
