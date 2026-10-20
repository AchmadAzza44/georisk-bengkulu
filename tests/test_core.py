"""Tes GeoRisk Bengkulu: validasi, jarak, indikator, skor deterministik, ekspor, dan data nyata."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from pyproj import Geod
from shapely.geometry import LineString, Point, Polygon, box

from src.data_loader import DataLoadError, list_data_files, load_geojson, load_metadata
from src.exporter import pdf_report_bytes, stats_frame, to_csv_bytes
from src.spatial_analysis import (calculate_distance_to_river, classify, compare_scenarios, compute_risk_score,
                                  compute_summary_statistics, normalize_weights, regency_indicators)
from src.validation import repair_geometries, validate_columns, validate_crs, validate_file, validate_geometry

ROOT = Path(__file__).resolve().parents[1]
UTM = "EPSG:32748"


def wgs(geoms, **cols):
    return gpd.GeoDataFrame(cols, geometry=geoms, crs=UTM).to_crs("EPSG:4326")


@pytest.fixture
def two_regencies():
    """Wilayah A (10x10 km) dilintasi sungai 10 km; wilayah B (10x10 km) tanpa sungai. Dibangun di UTM agar ukuran pasti."""
    regs = wgs([box(300000, 9600000, 310000, 9610000), box(320000, 9600000, 330000, 9610000)],
               regency_name=["A", "B"])
    rivers = wgs([LineString([(300000, 9605000), (310000, 9605000)])], name=["S"])
    return regs, rivers


def test_distance_matches_geodesic_reference():
    river = gpd.GeoDataFrame({"n": [1]}, geometry=[LineString([(102.0, -3.4), (102.1, -3.4)])], crs="EPSG:4326")
    pts = gpd.GeoDataFrame({"id": [1, 2]}, geometry=[Point(102.05, -3.41), Point(102.05, -3.4)], crs="EPSG:4326")
    d = calculate_distance_to_river(pts, river)["jarak_ke_sungai_m"].tolist()
    expected = Geod(ellps="WGS84").inv(102.05, -3.41, 102.05, -3.4)[2]
    assert d[0] == pytest.approx(expected, rel=0.01)
    assert d[1] == pytest.approx(0, abs=1)


def test_distance_input_not_mutated_and_empty_rivers_error():
    river = gpd.GeoDataFrame(geometry=[LineString([(102, -3), (102.1, -3)])], crs="EPSG:4326")
    pts = gpd.GeoDataFrame(geometry=[Point(102.0, -3.1)], crs="EPSG:4326")
    calculate_distance_to_river(pts, river)
    assert "jarak_ke_sungai_m" not in pts.columns
    with pytest.raises(ValueError):
        calculate_distance_to_river(pts, river.iloc[0:0])


def test_indicators_known_values(two_regencies):
    regs, rivers = two_regencies
    ind = regency_indicators(regs, rivers, buffer_m=1000).set_index("regency_name")
    assert ind.loc["A", "luas_km2"] == pytest.approx(100, rel=0.01)
    assert ind.loc["A", "panjang_sungai_km"] == pytest.approx(10, rel=0.01)
    assert ind.loc["A", "kerapatan_sungai_km_per_km2"] == pytest.approx(0.1, rel=0.01)
    assert ind.loc["A", "persen_area_dekat_sungai"] == pytest.approx(20, rel=0.02)
    assert ind.loc["B", "panjang_sungai_km"] == 0 and ind.loc["B", "persen_area_dekat_sungai"] == 0


def test_indicators_input_validation(two_regencies):
    regs, rivers = two_regencies
    with pytest.raises(ValueError):
        regency_indicators(regs, rivers, buffer_m=0)
    with pytest.raises(ValueError):
        regency_indicators(regs, rivers.iloc[0:0])
    with pytest.raises(ValueError):
        regency_indicators(regs.set_crs(None, allow_override=True), rivers)


def test_score_is_deterministic_and_hand_checkable(two_regencies):
    regs, rivers = two_regencies
    ind = regency_indicators(regs, rivers)
    w = {"kerapatan_sungai_km_per_km2": 1, "persen_area_dekat_sungai": 1}
    a, b = compute_risk_score(ind, w).table, compute_risk_score(ind, w).table
    pd.testing.assert_frame_equal(a, b)  # tidak ada komponen acak
    s = a.set_index("regency_name")
    assert s.loc["A", "skor_indikatif"] == 100 and s.loc["B", "skor_indikatif"] == 0
    assert s.loc["A", "kategori"] == "Tinggi" and s.loc["B", "kategori"] == "Rendah"
    assert s.loc["A", "peringkat"] == 1


def test_weights_and_thresholds_validated(two_regencies):
    regs, rivers = two_regencies
    ind = regency_indicators(regs, rivers)
    with pytest.raises(ValueError):
        compute_risk_score(ind, {"tidak_ada": 1})
    with pytest.raises(ValueError):
        compute_risk_score(ind, {"kerapatan_sungai_km_per_km2": 0})
    with pytest.raises(ValueError):
        normalize_weights({"a": -1, "b": 2})
    with pytest.raises(ValueError):
        compute_risk_score(ind, {"kerapatan_sungai_km_per_km2": 1}, thresholds=(70, 30))
    assert sum(normalize_weights({"a": 2, "b": 6}).values()) == pytest.approx(1)


def test_constant_factor_noted_not_silently_used():
    df = pd.DataFrame({"regency_name": ["x", "y"], "f": [5.0, 5.0]})
    res = compute_risk_score(df, {"f": 1})
    assert res.table["skor_indikatif"].tolist() == [0, 0] and res.notes


def test_classify_boundaries():
    out = classify(pd.Series([0, 33.3, 33.4, 66.6, 66.7, 100]))
    assert out.tolist() == ["Rendah", "Rendah", "Sedang", "Sedang", "Tinggi", "Tinggi"]


def test_scenarios_and_summary(two_regencies):
    regs, rivers = two_regencies
    ind = regency_indicators(regs, rivers)
    comp = compare_scenarios(ind, {"x": {"kerapatan_sungai_km_per_km2": 1}, "y": {"persen_area_dekat_sungai": 1}}, "regency_name")
    assert {"skor_x", "peringkat_y"} <= set(comp.columns)
    stats = compute_summary_statistics(compute_risk_score(ind, {"kerapatan_sungai_km_per_km2": 1}).table)
    assert stats["jumlah_wilayah"] == 2 and sum(stats["distribusi_kategori"].values()) == 2


def test_crs_validation():
    g = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
    assert validate_crs(g)["valid"]
    assert not validate_crs(g.to_crs(UTM))["valid"]
    assert not validate_crs(gpd.GeoDataFrame(geometry=[Point(0, 0)]))["valid"]


def test_geometry_validation_and_repair():
    bow_tie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
    g = gpd.GeoDataFrame({"n": [1, 2, 3]}, geometry=[bow_tie, box(0, 0, 1, 1), Polygon()], crs="EPSG:4326")
    rep = validate_geometry(g)
    assert not rep["valid"] and rep["invalid_geometries"] == 1 and rep["empty_geometries"] == 1
    fixed, actions = repair_geometries(g)
    assert actions == {"diperbaiki": 1, "dibuang_kosong": 1}
    assert validate_geometry(fixed)["valid"] and len(fixed) == 2
    assert not validate_geometry(g.iloc[0:0])["valid"]


def test_columns_and_file_validation(tmp_path):
    g = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    assert validate_columns(g, ["a"])["valid"] and validate_columns(g, ["b"])["missing_columns"] == ["b"]
    bad = tmp_path / "rusak.geojson"
    bad.write_text("bukan geojson")
    assert not validate_file(bad)["valid"] and not validate_file(tmp_path / "x.geojson")["valid"]


def test_loader_errors(tmp_path):
    with pytest.raises(DataLoadError):
        load_geojson(tmp_path / "tidak_ada.geojson")
    (tmp_path / "x.txt").write_text("x")
    with pytest.raises(DataLoadError):
        load_geojson(tmp_path / "x.txt")
    (tmp_path / "k.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    with pytest.raises(DataLoadError):
        load_geojson(tmp_path / "k.geojson")
    (tmp_path / "rusak.geojson").write_text("{{{")
    with pytest.raises(DataLoadError):
        load_geojson(tmp_path / "rusak.geojson")
    assert list_data_files(tmp_path / "nope") == []
    (tmp_path / "_meta.geojson").write_text("{}")
    assert all(not p.name.startswith("_") for p in list_data_files(tmp_path))


def test_exports(two_regencies):
    regs, rivers = two_regencies
    table = compute_risk_score(regency_indicators(regs, rivers), {"kerapatan_sungai_km_per_km2": 1}).table
    csv = to_csv_bytes(table).decode()
    assert csv.splitlines()[0].startswith("regency_name") and len(csv.splitlines()) == 3
    stats = compute_summary_statistics(table)
    pdf = pdf_report_bytes("Uji", {"p": 1}, table[["regency_name", "skor_indikatif"]], stats, ["sumber"], ["catatan"])
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert not stats_frame(stats).empty


# ---- Data nyata ----
@pytest.mark.skipif(not (ROOT / "data/raw/bengkulu_regencies.geojson").exists(), reason="data belum disiapkan")
def test_real_regencies_are_only_bengkulu_province():
    regs = load_geojson(ROOT / "data/raw/bengkulu_regencies.geojson")
    prov = load_geojson(ROOT / "data/raw/bengkulu_province.geojson")
    assert len(regs) == 10
    assert not {"Kepulauan Mentawai", "Lahat", "Kerinci", "Musi Rawas"} & set(regs["regency_name"])
    proj = prov.estimate_utm_crs()
    inside = regs.to_crs(proj).intersection(prov.to_crs(proj).union_all()).area / regs.to_crs(proj).area
    assert (inside > 0.9).all()


@pytest.mark.skipif(not (ROOT / "data/raw/bengkulu_rivers.geojson").exists(), reason="data belum disiapkan")
def test_real_pipeline_runs_and_is_reproducible():
    regs = load_geojson(ROOT / "data/raw/bengkulu_regencies.geojson")
    rivers = load_geojson(ROOT / "data/raw/bengkulu_rivers.geojson")
    ind = regency_indicators(regs, rivers)
    assert (ind["luas_km2"] > 0).all() and (ind["persen_area_dekat_sungai"].between(0, 100)).all()
    w = {"kerapatan_sungai_km_per_km2": 1, "persen_area_dekat_sungai": 1}
    pd.testing.assert_frame_equal(compute_risk_score(ind, w).table, compute_risk_score(ind, w).table)


def test_metadata_covers_all_layers():
    meta = load_metadata(ROOT / "data/metadata.json")
    for fname in ("bengkulu_province.geojson", "bengkulu_regencies.geojson", "bengkulu_rivers.geojson"):
        assert {"sumber", "lisensi", "crs", "tahun_data", "batasan"} <= set(meta[fname])


# ---------- terrain (elevasi/kemiringan) ----------
import gzip

import numpy as np

from src.analysis_log import file_sha256, log_run, read_log
from src.event_validation import events_per_regency, load_events, validate_scores
from src.spatial_analysis import FACTOR_LABELS, merge_terrain
from src.terrain import read_hgt, slope_degrees, terrain_indicators, tile_origin


def write_tile(path, n=361, left=10, right=100):
    arr = np.full((n, n), left, dtype=">i2")
    arr[:, n // 2 :] = right
    path.write_bytes(gzip.compress(arr.tobytes()))


def test_slope_known_values():
    ramp = np.tile(np.arange(5, dtype=np.float32)[:, None] * 30.0, (1, 5))  # naik 30 m per sel ke arah baris
    s = slope_degrees(ramp, dx_m=30.0, dy_m=30.0)
    assert s[2, 2] == pytest.approx(45.0, abs=0.01)
    assert slope_degrees(np.full((5, 5), 7.0, dtype=np.float32), 30, 30)[2, 2] == 0


def test_hgt_roundtrip_nodata_and_tile_origin(tmp_path):
    arr = np.full((5, 5), 12, dtype=">i2")
    arr[0, 0] = -32768
    f = tmp_path / "S04E102.hgt.gz"
    f.write_bytes(gzip.compress(arr.tobytes()))
    out = read_hgt(f)
    assert out.shape == (5, 5) and np.isnan(out[0, 0]) and out[2, 2] == 12
    assert tile_origin("S04E102.hgt.gz") == (-4, 102) and tile_origin("N01W003") == (1, -3)
    (tmp_path / "bad.hgt").write_bytes(b"123")
    with pytest.raises(ValueError):
        read_hgt(tmp_path / "bad.hgt")


def test_terrain_indicators_known_half_low_half_high(tmp_path):
    write_tile(tmp_path / "N00E000.hgt.gz")
    regs = gpd.GeoDataFrame({"regency_name": ["X"]}, geometry=[box(0.1, 0.1, 0.9, 0.9)], crs="EPSG:4326")
    t = terrain_indicators(regs, tmp_path).iloc[0]
    assert t["persen_area_elevasi_rendah"] == pytest.approx(50.0, abs=3)   # separuh wilayah 10 m (<=25), separuh 100 m
    assert 50 < t["elevasi_rata_m"] < 60 and t["persen_sel_valid"] == 100
    assert t["persen_area_datar"] > 90  # hanya tepi tangga yang curam


def test_terrain_errors(tmp_path):
    regs = gpd.GeoDataFrame({"regency_name": ["X"]}, geometry=[box(0.1, 0.1, 0.9, 0.9)], crs="EPSG:4326")
    with pytest.raises(FileNotFoundError):
        terrain_indicators(regs, tmp_path)
    write_tile(tmp_path / "N00E000.hgt.gz")
    far = gpd.GeoDataFrame({"regency_name": ["Y"]}, geometry=[box(50, 50, 51, 51)], crs="EPSG:4326")
    with pytest.raises(ValueError):
        terrain_indicators(far, tmp_path)


def test_merge_terrain_validates(two_regencies):
    regs, rivers = two_regencies
    ind = regency_indicators(regs, rivers)
    terrain = pd.DataFrame({"regency_name": ["A", "B"], "persen_area_elevasi_rendah": [80, 10], "persen_area_datar": [70, 5]})
    merged = merge_terrain(ind, terrain)
    res = compute_risk_score(merged, {"persen_area_elevasi_rendah": 1, "persen_area_datar": 1}).table.set_index("regency_name")
    assert res.loc["A", "kategori"] == "Tinggi" and res.loc["B", "kategori"] == "Rendah"
    with pytest.raises(ValueError):
        merge_terrain(ind, terrain.iloc[:1])
    with pytest.raises(ValueError):
        merge_terrain(ind, terrain.drop(columns=["persen_area_datar"]))
    assert set(FACTOR_LABELS) >= {"persen_area_elevasi_rendah", "persen_area_datar"}


def test_four_factor_score_deterministic_and_weights_matter(two_regencies):
    regs, rivers = two_regencies
    ind = merge_terrain(regency_indicators(regs, rivers),
                        pd.DataFrame({"regency_name": ["A", "B"], "persen_area_elevasi_rendah": [10, 90], "persen_area_datar": [10, 90]}))
    only_river = compute_risk_score(ind, {"kerapatan_sungai_km_per_km2": 1}).table.set_index("regency_name")
    only_terrain = compute_risk_score(ind, {"persen_area_elevasi_rendah": 1}).table.set_index("regency_name")
    assert only_river.loc["A", "peringkat"] == 1 and only_terrain.loc["B", "peringkat"] == 1  # bobot membalik peringkat


# ---------- validasi kejadian & log ----------
def test_event_loading_reports_dropped_rows():
    gdf, notes = load_events(b"lat,lon\n-3.8,102.3\nabc,1\n50,102\n-3.9,102.4\n")
    assert len(gdf) == 2 and len(notes) == 1
    for bad in (b"x,y\n1,2\n", b"lat,lon\n99,0\n"):
        with pytest.raises(ValueError):
            load_events(bad)


def test_events_per_regency_and_validation(two_regencies):
    regs, rivers = two_regencies
    table = compute_risk_score(regency_indicators(regs, rivers), {"kerapatan_sungai_km_per_km2": 1}).table
    in_a = regs.geometry.iloc[0].representative_point()
    events = gpd.GeoDataFrame(geometry=[in_a, in_a, in_a], crs="EPSG:4326")
    counts = events_per_regency(events, regs)
    assert counts.set_index("regency_name")["jumlah_kejadian"].to_dict() == {"A": 3, "B": 0}
    res = validate_scores(table, counts)
    assert res["spearman_rho"] == 1.0 and res["irisan_top3"] == 2 and any("tidak signifikan" in c for c in res["catatan"])
    none = validate_scores(table, counts.assign(jumlah_kejadian=0))
    assert none["spearman_rho"] is None and none["catatan"]


def test_analysis_log_appends_and_hashes(tmp_path):
    data = tmp_path / "d.geojson"
    data.write_text("abc")
    log = tmp_path / "log.jsonl"
    e1 = log_run(log, {"radius": 1000}, {"n": 10}, [data])
    log_run(log, {"radius": 2000}, {"n": 10}, [data])
    entries = read_log(log)
    assert len(entries) == 2 and entries[0]["data"]["d.geojson"] == file_sha256(data) == e1["data"]["d.geojson"]
    assert read_log(log, last=1)[0]["parameter"]["radius"] == 2000 and read_log(tmp_path / "none") == []


@pytest.mark.skipif(not (ROOT / "data/processed/regency_terrain.csv").exists(), reason="terrain belum dihitung")
def test_real_terrain_table_is_physically_plausible():
    t = pd.read_csv(ROOT / "data/processed/regency_terrain.csv").set_index("regency_name")
    assert len(t) == 10 and (t["persen_sel_valid"] > 95).all()
    assert t.loc["Kota Bengkulu", "elevasi_rata_m"] < 50 and t.loc["Lebong", "elevasi_rata_m"] > 700  # kota pesisir vs dataran tinggi
    assert t["persen_area_elevasi_rendah"].between(0, 100).all() and t["persen_area_datar"].between(0, 100).all()
    assert t.loc["Kota Bengkulu", "persen_area_elevasi_rendah"] > t.loc["Lebong", "persen_area_elevasi_rendah"]
