"""Unit tests for Settings and PDF generation features."""

import io
import pandas as pd
import pytest
from services.pdf_generator import generate_conversation_pdf
from ui.components import style_dataframe_metrics


def test_pdf_generation_basic():
    messages = [
        {"role": "user", "content": "What is the OEE by plant?"},
        {
            "role": "assistant",
            "content": "Here is the OEE breakdown by plant.",
            "sql_query": "SELECT plant, AVG(oee) AS oee FROM telemetry GROUP BY plant",
            "data": pd.DataFrame({"plant": ["Plant A", "Plant B"], "oee": [82.5, 91.0]})
        }
    ]

    pdf_bytes = generate_conversation_pdf(
        messages=messages,
        title="Test Report",
        subtitle="Test Subtitle"
    )

    assert pdf_bytes is not None
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF header signature check
    assert pdf_bytes.startswith(b"%PDF")


def test_style_dataframe_metrics():
    df = pd.DataFrame({
        "Plant": ["Plant A", "Plant B"],
        "Availability (%)": [80.0, 65.0],
        "Quality": [0.99, 0.95]
    })

    metric_colors_disabled = {
        "availability": {"enabled": False, "threshold": 75.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "quality": {"enabled": False, "threshold": 98.0, "pass_color": "#00ff00", "fail_color": "#ff0000"}
    }

    styled_disabled = style_dataframe_metrics(df, metric_colors_disabled)
    html_disabled = styled_disabled.to_html()
    assert "background-color: #28a745" not in html_disabled

    metric_colors_enabled = {
        "availability": {"enabled": True, "threshold": 75.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "quality": {"enabled": True, "threshold": 98.0, "pass_color": "#00ff00", "fail_color": "#ff0000"}
    }

    styled_enabled = style_dataframe_metrics(df, metric_colors_enabled)
    html_enabled = styled_enabled.to_html()
    assert "background-color: #28a745" in html_enabled
    assert "background-color: #dc3545" in html_enabled
