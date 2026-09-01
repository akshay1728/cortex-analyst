"""Comprehensive Unit Tests for Manufacturing OEE Conversational Analytics App."""

import pytest
import pandas as pd
import numpy as np

from data.sample_data import generate_oee_dataset, calculate_aggregated_oee
from services.cortex_analyst import CortexAnalystService
from services.cortex_ai import CortexAIService
from services.python_validator import PythonValidator
from ui.chart_renderer import ChartRenderer

@pytest.fixture
def sample_df():
    return generate_oee_dataset(days=30, seed=123)

def test_data_generation(sample_df):
    assert not sample_df.empty
    assert len(sample_df) > 0
    expected_cols = [
        "date", "plant", "line", "shift", "product_family", "product",
        "planned_hours", "downtime_hours", "operating_hours", "downtime_reason",
        "target_rate", "total_units", "good_units", "reject_units",
        "availability", "performance", "quality", "oee"
    ]
    for col in expected_cols:
        assert col in sample_df.columns

def test_aggregated_oee_calculation(sample_df):
    metrics = calculate_aggregated_oee(sample_df)
    assert "oee" in metrics
    assert "availability" in metrics
    assert "performance" in metrics
    assert "quality" in metrics
    assert 0 <= metrics["oee"] <= 100
    assert 0 <= metrics["availability"] <= 100
    assert 0 <= metrics["performance"] <= 100
    assert 0 <= metrics["quality"] <= 100

def test_cortex_analyst_queries(sample_df):
    analyst = CortexAnalystService(sample_df)

    # Test trend query
    res_trend = analyst.process_question("What is the OEE trend over time?")
    assert res_trend["query_type"] == "trend"
    assert "date" in res_trend["sql_query"].lower()
    assert not res_trend["data"].empty

    # Test grouped plant query
    res_plant = analyst.process_question("Compare OEE by plant")
    assert res_plant["query_type"] == "breakdown"
    assert res_plant["group_col"] == "plant"
    assert not res_plant["data"].empty

    # Test downtime query
    res_dt = analyst.process_question("What are the top downtime reasons?")
    assert res_dt["group_col"] == "downtime_reason"
    assert not res_dt["data"].empty

def test_cortex_ai_decision(sample_df):
    analyst = CortexAnalystService(sample_df)
    ai = CortexAIService()

    # Trend question -> line chart
    r_trend = analyst.process_question("OEE trend over time")
    spec_trend = ai.decide_visualization("OEE trend over time", r_trend)
    assert spec_trend["chart_type"] == "line"

    # Plant question -> bar chart
    r_plant = analyst.process_question("OEE by plant")
    spec_plant = ai.decide_visualization("OEE by plant", r_plant)
    assert spec_plant["chart_type"] in ["bar", "grouped_bar"]

    # Downtime pie question -> donut chart
    r_dt = analyst.process_question("Show downtime proportion distribution")
    spec_dt = ai.decide_visualization("Show downtime proportion distribution", r_dt)
    assert spec_dt["chart_type"] in ["donut", "pie", "bar"]

def test_python_validator():
    validator = PythonValidator()
    df = pd.DataFrame({
        "Plant": ["Alpha", "Beta"],
        "OEE": [85.2, 78.4]
    })

    # Test valid bar chart spec
    valid_spec = {
        "chart_type": "bar",
        "config": {"x_axis": "Plant", "y_axis": "OEE"}
    }
    val_spec, is_valid, msg = validator.validate_and_sanitize(valid_spec, df)
    assert is_valid is True
    assert val_spec["chart_type"] == "bar"

    # Test unsupported chart type -> fallback
    invalid_spec = {
        "chart_type": "unsupported_3d_scatter",
        "config": {}
    }
    val_spec, is_valid, msg = validator.validate_and_sanitize(invalid_spec, df)
    assert is_valid is False
    assert val_spec["chart_type"] == "bar"

def test_chart_renderer():
    df = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=5),
        "OEE (%)": [80.0, 82.5, 81.0, 85.0, 87.2]
    })

    # Test line chart
    spec_line = {
        "chart_type": "line",
        "title": "Test Line Chart",
        "config": {"x_axis": "Date", "y_axis": "OEE (%)"}
    }
    fig_line = ChartRenderer.render_chart(spec_line, df)
    assert fig_line is not None

    # Test gauge chart
    spec_gauge = {
        "chart_type": "gauge",
        "title": "OEE Target Gauge",
        "config": {"value_col": "OEE (%)", "target_value": 85.0}
    }
    fig_gauge = ChartRenderer.render_chart(spec_gauge, df)
    assert fig_gauge is not None
