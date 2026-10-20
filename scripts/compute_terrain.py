"""Hitung indikator elevasi/kemiringan per kabupaten/kota -> data/processed/regency_terrain.csv (+ .meta.json provenance)."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.terrain import terrain_indicators  # noqa: E402

LOW_ELEV_M, FLAT_DEG, STEP, STRIDE = 25.0, 2.0, 3, 2


def main() -> None:
    regencies = gpd.read_file(ROOT / "data" / "raw" / "bengkulu_regencies.geojson")
    table = terrain_indicators(regencies, ROOT / "data" / "dem", step=STEP, zonal_stride=STRIDE,
                               low_elev_m=LOW_ELEV_M, flat_deg=FLAT_DEG)
    out = ROOT / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "regency_terrain.csv", index=False)
    tiles = sorted((ROOT / "data" / "dem").glob("*.hgt.gz"))
    meta = {
        "dibuat_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sumber": "AWS Terrain Tiles (skadi .hgt.gz, 1 arc-detik; dasar SRTM untuk Indonesia)",
        "url": "https://registry.opendata.aws/terrain-tiles/",
        "tile": {t.name: hashlib.sha256(t.read_bytes()).hexdigest() for t in tiles},
        "parameter": {"ambang_elevasi_rendah_m": LOW_ELEV_M, "ambang_datar_derajat": FLAT_DEG,
                      "subsampling_dem": f"tiap {STEP} sel (~90 m)", "stride_zonal": STRIDE},
        "batasan": ["Ambang adalah pilihan analis, bukan standar hidrologi.", "SRTM adalah permukaan (termasuk kanopi/bangunan), bukan tanah telanjang.",
                    "Resolusi ~90 m untuk statistik per kabupaten; tidak untuk keputusan lokal."],
    }
    (out / "regency_terrain.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
