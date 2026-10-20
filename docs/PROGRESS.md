# Progress

## M0 — Foundation
- [x] Repository dan struktur folder
- [x] Environment dan dependencies
- [x] README

## M1 — Data
- [x] Sumber data didokumentasikan (lisensi ADM2 dikoreksi)
- [x] Validasi input tersedia
- [x] Data dapat diproses (bug 13 kabupaten tetangga diperbaiki)

## M2 — Core MVP
- [x] Peta interaktif, layer kontrol, popup, legenda
- [x] Error state ditangani (data hilang/rusak)

## M3 — Spatial analysis & evaluation
- [x] Indikator di CRS terproyeksi, skor deterministik (komponen acak dihapus)
- [x] Overlay faktor elevasi dan kemiringan (SRTM) dengan bobot yang dapat dikonfigurasi
- [x] Tes fungsional (29 lulus) — `docs/TEST_PLAN.md`
- [x] Kekurangan dicatat — `docs/METHODOLOGY.md`
- [x] Modul validasi terhadap kejadian (unggahan pengguna)
- [ ] Validasi nyata: belum ada data kejadian kredibel di repo

## M4 — Export & Release
- [x] CSV, HTML, PDF
- [x] Pencatatan analisis (JSONL + hash data)
- [x] Screenshot demo (`docs/screenshots/`), laporan (`docs/LAPORAN.md`)
- [ ] Instruksi reproduksi diuji pada lingkungan bersih
