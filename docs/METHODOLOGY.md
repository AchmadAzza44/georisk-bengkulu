# Metodologi dan Keterbatasan

**Sifat hasil:** *analisis indikatif berbasis kriteria* untuk pembelajaran. Bukan prediksi banjir, bukan peringatan dini, belum divalidasi terhadap kejadian banjir.

## Alur
1. **Muat** GeoJSON (provinsi, 10 kabupaten/kota, sungai) + `data/metadata.json`.
2. **Validasi**: CRS (dikonversi ke EPSG:4326 bila berbeda), geometri tidak valid diperbaiki `make_valid`, geometri kosong dibuang; jumlah tindakan ditampilkan di UI.
3. **Indikator per wilayah** (di CRS UTM hasil `estimate_utm_crs`, satuan meter; bukan di derajat):
   - *Kerapatan sungai* = panjang sungai terpotong batas wilayah (km) / luas (km²).
   - *Area dekat sungai* = % luas wilayah dalam radius `buffer_m` (default 1000 m) dari sungai.
4. **Skor** 0-100 = Σ bobot × indikator ternormalisasi min-max **antar 10 wilayah**. Bobot dinormalisasi hingga berjumlah 1. Faktor konstan tidak membedakan wilayah dan diberi catatan.
5. **Kategori**: Rendah < 33,3 ≤ Sedang < 66,7 ≤ Tinggi (dapat diubah). Kategori bersifat **relatif** terhadap wilayah studi.
6. **Jarak titik ke sungai** (klik peta): `sjoin_nearest` di CRS UTM.
7. **Skenario bobot**: kerapatan saja, area-dekat saja, dan pengaturan pengguna; perubahan peringkat menunjukkan sensitivitas.

Tidak ada komponen acak: input dan parameter yang sama selalu menghasilkan keluaran yang sama (dites).

## Faktor elevasi dan kemiringan (P2)
DEM: AWS Terrain Tiles (tile 'skadi', 1 arc-detik, dasar SRTM untuk Indonesia), 16 tile, disubsampel tiap 3 sel (~90 m). `scripts/download_dem.py` mengunduh, `scripts/compute_terrain.py` menghitung indikator per kabupaten/kota ke `data/processed/regency_terrain.csv` beserta provenance (SHA-256 tile, parameter) di `regency_terrain.meta.json`. Kemiringan dihitung dengan beda pusat pada ukuran sel dalam meter (bukan derajat).
- *Area elevasi rendah* = % luas dengan elevasi <= 25 m. *Area datar* = % luas dengan kemiringan <= 2°. **Kedua ambang adalah pilihan analis, bukan standar hidrologi.**
- Plausibilitas fisik (diperiksa pada tes): Kota Bengkulu rata-rata 16 m (82% area <= 25 m, datar), Lebong 1.083 m.

## Hasil contoh (bobot sama untuk 4 faktor, radius 1000 m)
| Peringkat | Wilayah | Kerapatan sungai | Dekat sungai % | Elevasi rendah % | Datar % | Skor | Kategori |
|---|---|---|---|---|---|---|---|
| 1 | Kota Bengkulu | 0.252 | 36.3 | 81.8 | 67.7 | 66.0 | Sedang |
| 2 | Mukomuko | 0.428 | 59.3 | 12.6 | 17.5 | 58.9 | Sedang |
| 3 | Bengkulu Tengah | 0.362 | 48.7 | 11.4 | 14.3 | 43.0 | Sedang |
| 4 | Bengkulu Utara | 0.356 | 49.5 | 7.4 | 15.2 | 42.1 | Sedang |
| 5 | Bengkulu Selatan | 0.359 | 49.0 | 5.2 | 16.7 | 42.0 | Sedang |
| 6 | Seluma | 0.309 | 42.5 | 22.7 | 22.5 | 40.0 | Sedang |
| 7 | Kaur | 0.307 | 44.5 | 2.8 | 7.7 | 29.4 | Rendah |
| 8 | Lebong | 0.229 | 35.5 | 0.0 | 5.0 | 13.3 | Rendah |
| 9 | Kepahiang | 0.230 | 32.6 | 0.0 | 8.4 | 12.6 | Rendah |
| 10 | Rejang Lebong | 0.167 | 25.7 | 0.0 | 9.5 | 1.8 | Rendah |

**Sensitivitas faktor:** dengan faktor sungai saja Kota Bengkulu berperingkat 7; dengan faktor terrain saja berperingkat 1; gabungan 1. Korelasi peringkat (Spearman) antara skor faktor-sungai dan skor faktor-terrain hanya 0,52 (n = 10): kesimpulan bergantung pada faktor yang dipilih. Tidak ada wilayah berkategori "Tinggi" karena normalisasi min-max antar 10 wilayah dengan rata-rata berbobot jarang mencapai > 66.

## Validasi dan pencatatan
- Validasi terhadap kejadian banjir hanya dapat dilakukan bila pengguna mengunggah CSV kejadian (`lat`, `lon`). Aplikasi menghitung kejadian per wilayah dan korelasi Spearman skor-vs-jumlah kejadian serta irisan 3 teratas, disertai peringatan n kecil. **Tidak ada data kejadian bawaan, sehingga skor belum tervalidasi.**
- Setiap analisis dapat dicatat (`data/analysis_log.jsonl`): waktu, parameter, bobot, ringkasan hasil, dan SHA-256 berkas data.

## Keterbatasan (wajib dibaca)
- Faktor yang ada: sungai OSM dan elevasi/kemiringan SRTM. **Tidak ada** curah hujan, tata guna/penutup lahan, drainase perkotaan, pasang surut, kapasitas sungai, atau data kejadian banjir bawaan.
- Sungai OSM crowdsourced: wilayah yang lebih lengkap dipetakan tampak lebih padat sungai. SRTM adalah permukaan (kanopi/bangunan), bukan tanah telanjang, dan kualitasnya menurun pada relief curam.
- Normalisasi min-max antar 10 wilayah membuat skor relatif; selisih kecil (mis. Bengkulu Tengah/Utara/Selatan, < 1 poin) praktis setara.
- Bobot dan ambang adalah pilihan pengguna, tanpa kalibrasi. Resolusi analisis = kabupaten/kota, terlalu kasar untuk keputusan lokal; "Sedang" tidak berarti aman.
- Langkah validasi yang masih diperlukan: bandingkan dengan catatan kejadian banjir yang kredibel dan tambahkan curah hujan serta penutup lahan.
