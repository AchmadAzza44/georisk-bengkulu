"""Ekspor CSV, HTML peta, dan laporan PDF sesuai data yang sedang ditampilkan."""

from __future__ import annotations

import io
from typing import Any

import folium
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = ("Analisis indikatif berbasis kriteria untuk pembelajaran. BUKAN prediksi banjir, peringatan dini, "
              "atau kajian hidrologi, dan belum divalidasi terhadap data kejadian banjir.")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def map_html_bytes(m: folium.Map) -> bytes:
    return m.get_root().render().encode("utf-8")


def stats_frame(stats: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for key, value in stats.items():
        if isinstance(value, dict):
            rows += [{"metrik": f"{key}: {k}", "nilai": v} for k, v in value.items()]
        else:
            rows.append({"metrik": key, "nilai": value})
    return pd.DataFrame(rows)


def pdf_report_bytes(title: str, params: dict[str, Any], table: pd.DataFrame, stats: dict[str, Any],
                     sources: list[str], notes: list[str] | None = None) -> bytes:
    """Laporan PDF: parameter, bobot, hasil per wilayah, statistik, sumber data, dan keterbatasan."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    flow: list[Any] = [Paragraph(title, styles["Title"]), Paragraph(DISCLAIMER, styles["BodyText"]), Spacer(1, 10)]

    flow.append(Paragraph("Parameter analisis", styles["Heading2"]))
    for key, value in params.items():
        flow.append(Paragraph(f"<b>{key}</b>: {value}", styles["BodyText"]))
    flow.append(Paragraph("Hasil per wilayah", styles["Heading2"]))
    data = [list(map(str, table.columns))] + [[f"{v:.2f}" if isinstance(v, float) else str(v) for v in row]
                                              for row in table.itertuples(index=False)]
    grid = Table(data, repeatRows=1)
    grid.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7),
                              ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    flow += [grid, Paragraph("Ringkasan statistik", styles["Heading2"])]
    flow += [Paragraph(f"{k}: {v}", styles["BodyText"]) for k, v in stats.items()]
    flow.append(Paragraph("Sumber data", styles["Heading2"]))
    flow += [Paragraph(s, styles["BodyText"]) for s in sources]
    if notes:
        flow.append(Paragraph("Catatan", styles["Heading2"]))
        flow += [Paragraph(n, styles["BodyText"]) for n in notes]
    flow.append(Paragraph("Keterbatasan", styles["Heading2"]))
    flow += [Paragraph(t, styles["BodyText"]) for t in (
        "Skor dinormalisasi relatif antar wilayah studi; bukan peluang banjir.",
        "Kerapatan sungai OSM dipengaruhi kelengkapan pemetaan sukarelawan.",
        "Belum ada validasi terhadap data kejadian banjir, elevasi, curah hujan, atau tata guna lahan.")]
    doc.build(flow)
    return buf.getvalue()
