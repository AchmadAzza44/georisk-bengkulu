"""Download public source data for GeoRisk Bengkulu.

Sources:
  * geoBoundaries (www.geoboundaries.org) - Indonesia ADM1/ADM2 boundaries.
  * OpenStreetMap via Overpass API - rivers within the Bengkulu study area.

All outputs land in data/raw/. See docs/DATA_SOURCES.md for license and
attribution details. Re-running is safe: existing files are kept unless
--force is passed.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

USER_AGENT = "GeoRiskBengkulu/1.0 (academic coursework; contact: student@example.edu)"
GEBOUNDARIES_SHA = "9469f09"
GEBOUNDARIES = {
    "idn_adm1.geojson": (
        f"https://github.com/wmgeolab/geoBoundaries/raw/{GEBOUNDARIES_SHA}"
        "/releaseData/gbOpen/IDN/ADM1/geoBoundaries-IDN-ADM1_simplified.geojson"
    ),
    "idn_adm2.geojson": (
        f"https://github.com/wmgeolab/geoBoundaries/raw/{GEBOUNDARIES_SHA}"
        "/releaseData/gbOpen/IDN/ADM2/geoBoundaries-IDN-ADM2_simplified.geojson"
    ),
}
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# Bengkulu rough bounding box: (south, west, north, east).
BENGKULU_BBOX = (-5.7, 100.9, -2.1, 104.4)
RIVER_QUERY = (
    "[out:json][timeout:180];"
    f'way["waterway"~"^(river|canal)$"]({BENGKULU_BBOX[0]},{BENGKULU_BBOX[1]},'
    f"{BENGKULU_BBOX[2]},{BENGKULU_BBOX[3]});"
    "out geom;"
)


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        destination.write_bytes(response.read())


def _post_overpass(query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                with urllib.request.urlopen(request, timeout=240) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Gagal mengunduh data sungai dari Overpass API: {last_error}")


def _overpass_to_geojson(payload: dict) -> dict:
    features = []
    for element in payload.get("elements", []):
        geometry = element.get("geometry")
        if not geometry or len(geometry) < 2:
            continue
        coordinates = [[point["lon"], point["lat"]] for point in geometry]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "osm_id": element.get("id"),
                    "name": element.get("tags", {}).get("name"),
                    "waterway": element.get("tags", {}).get("waterway", "river"),
                },
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Unduh data sumber publik GeoRisk Bengkulu.")
    parser.add_argument("--force", action="store_true", help="Unduh ulang meski file sudah ada.")
    parser.add_argument("--skip-rivers", action="store_true", help="Lewati unduhan sungai OSM.")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)

    for filename, url in GEBOUNDARIES.items():
        destination = RAW / filename
        if destination.exists() and not args.force:
            print(f"Lewati (sudah ada): {filename}")
            continue
        print(f"Mengunduh {filename} ...")
        _download(url, destination)
        print(f"  tersimpan ({destination.stat().st_size / 1_048_576:.2f} MB)")

    if args.skip_rivers:
        return

    rivers_path = RAW / "osm_rivers.geojson"
    if rivers_path.exists() and not args.force:
        print("Lewati (sudah ada): osm_rivers.geojson")
        return
    print("Mengunduh sungai dari Overpass API (dapat memakan waktu) ...")
    payload = _post_overpass(RIVER_QUERY)
    geojson = _overpass_to_geojson(payload)
    rivers_path.write_text(json.dumps(geojson), encoding="utf-8")
    print(f"  tersimpan {len(geojson['features'])} fitur sungai")


if __name__ == "__main__":
    main()
