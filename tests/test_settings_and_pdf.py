"""Tests for settings page functionality and PDF generation."""

import io
import pandas as pd
import pytest
import plotly.express as px
from services.pdf_generator import generate_conversation_pdf, _markdown_to_reportlab_html
from ui.components import style_dataframe_metrics


def test_markdown_to_reportlab_html():
    text = "Hello **world** & <test> *italic*"
    res = _markdown_to_reportlab_html(text)
    assert "<b>world</b>" in res
    assert "&amp;" in res
    assert "&lt;test&gt;" in res


def test_generate_conversation_pdf_basic():
    fig = px.line(x=[1, 2, 3], y=[10, 20, 30], title="Test Trend")
    data = pd.DataFrame({"PLANT": ["Plant A", "Plant B"], "OEE": [88.5, 72.1]})
    messages = [
        {"role": "user", "content": "Show OEE trend"},
        {
            "role": "assistant",
            "content": "Here is the **OEE trend**:",
            "sql_query": "SELECT * FROM OEE WHERE OEE >= 75",
            "data": data,
            "figure": fig
        }
    ]

    pdf_bytes = generate_conversation_pdf(
        messages=messages,
        logo_bytes=None,
        title="Test Report",
        subtitle="Test Subtitle"
    )

    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_style_dataframe_metrics():
    df = pd.DataFrame({
        "PLANT": ["Plant A", "Plant B"],
        "AVAILABILITY_PCT": [80.0, 60.0]
    })
    colors_config = {
        "availability": {
            "enabled": True,
            "threshold": 75.0,
            "pass_color": "#28a745",
            "fail_color": "#dc3545"
        }
    }

    styled = style_dataframe_metrics(df, colors_config)
    assert styled is not None


def test_admin_service_functions(monkeypatch):
    from services.settings_service import check_is_admin, load_admin_users_from_db, save_admin_user_to_db, delete_admin_user_from_db

    # Test check_is_admin default when session is None
    assert check_is_admin("TEST_USER") is True

    # Test load_admin_users_from_db when session is None
    admins = load_admin_users_from_db()
    assert isinstance(admins, list)

    # Test save/delete when session is None
    assert save_admin_user_to_db("NEW_ADMIN", True) is False
    assert delete_admin_user_from_db("NEW_ADMIN") is False
