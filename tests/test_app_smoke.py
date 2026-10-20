from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.skipif(not (APP.parent / "data/raw/bengkulu_rivers.geojson").exists(), reason="data belum disiapkan")
def test_app_runs_with_real_data():
    at = AppTest.from_file(str(APP), default_timeout=300).run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Wilayah dianalisis"] == "10"
    assert int(metrics["Rendah"]) + int(metrics["Sedang"]) + int(metrics["Tinggi"]) == 10
    assert any("BUKAN prediksi" in w.value for w in at.warning)


def test_app_reports_missing_data_clearly():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.sidebar.text_input[0].set_value("/tidak/ada").run()
    assert not at.exception and any("tidak ditemukan" in e.value for e in at.error)
