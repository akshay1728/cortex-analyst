"""Comprehensive Tests for Dynamic Chart Generation and AST Security Validation.

Scenarios tested:
1. Categorical comparison ("Show OEE by production area") -> Bar chart
2. Time series ("Show OEE trend for the last 12 months") -> Line chart
3. Relationship ("Compare downtime and OEE") -> Scatter chart
4. Distribution / Production volume by site -> Categorical / bar chart
5. Scalar total question ("What is the total production volume?") -> No chart required
6. Empty DataFrame -> Clean handling without chart or application failure
7. Malicious code injection attempt (`import os; os.system(...)`) -> AST validation rejection
8. Code referencing non-existent column -> Runtime execution error handled gracefully
"""

import pytest
import pandas as pd
import numpy as np

from visualization.chart_generator import generate_chart
from visualization.chart_validator import validate_python_code
from visualization.chart_executor import execute_chart_code


@pytest.fixture
def sample_oee_df():
    return pd.DataFrame({
        "PRODUCTION_AREA": ["Assembly 1", "Assembly 2", "Machining 1", "Machining 2"],
        "OEE": [82.5, 76.1, 88.4, 72.0],
        "DOWNTIME_MINUTES": [45, 120, 20, 180],
        "MONTH": pd.date_range("2026-01-01", periods=4, freq="ME")
    })


def test_1_categorical_comparison(sample_oee_df):
    """Test 1: Show OEE by production area -> Bar chart."""
    res = generate_chart("Show OEE by production area", sample_oee_df)
    assert res.should_visualize is True
    assert res.chart_type in ["bar", "grouped_bar"]
    assert res.is_valid is True
    assert res.figure is not None


def test_2_time_series(sample_oee_df):
    """Test 2: Show OEE trend for the last 12 months -> Line chart."""
    res = generate_chart("Show OEE trend for the last 12 months", sample_oee_df)
    assert res.should_visualize is True
    assert res.chart_type in ["line", "area"]
    assert res.is_valid is True
    assert res.figure is not None


def test_3_relationship_scatter(sample_oee_df):
    """Test 3: Compare downtime and OEE -> Scatter plot."""
    res = generate_chart("Compare downtime and OEE", sample_oee_df)
    assert res.should_visualize is True
    assert res.chart_type == "scatter"
    assert res.is_valid is True
    assert res.figure is not None


def test_4_production_volume_by_site(sample_oee_df):
    """Test 4: Show production volume by site -> Categorical comparison chart."""
    res = generate_chart("Show production volume by site", sample_oee_df)
    assert res.should_visualize is True
    assert res.is_valid is True
    assert res.figure is not None


def test_5_scalar_total_question():
    """Test 5: What is the total production volume? -> Scalar result, no chart required."""
    scalar_df = pd.DataFrame([{"TOTAL_VOLUME": 1500000}])
    res = generate_chart("What is the total production volume?", scalar_df)
    assert res.should_visualize is False
    assert res.figure is None


def test_6_empty_dataframe():
    """Test 6: Empty DataFrame -> No chart and no application failure."""
    empty_df = pd.DataFrame()
    res = generate_chart("Show OEE by area", empty_df)
    assert res.should_visualize is False
    assert res.figure is None
    assert "empty" in res.reasoning.lower()


def test_7_malicious_code_ast_validation():
    """Test 7: Generated malicious code attempts (`import os; os.system(...)`) -> Validation failure."""
    malicious_code_1 = """import os
os.system('rm -rf /')
import plotly.express as px
fig = px.bar(df, x='PRODUCTION_AREA', y='OEE')
"""
    is_valid_1, errors_1 = validate_python_code(malicious_code_1)
    assert is_valid_1 is False
    assert any("Forbidden import" in err for err in errors_1)

    malicious_code_2 = """
import plotly.express as px
eval("open('/etc/passwd').read()")
fig = px.bar(df, x='PRODUCTION_AREA', y='OEE')
"""
    is_valid_2, errors_2 = validate_python_code(malicious_code_2)
    assert is_valid_2 is False
    assert any("Forbidden builtin call" in err for err in errors_2)


def test_8_non_existent_column_error_handling(sample_oee_df):
    """Test 8: Generated code references a column that does not exist -> Handled gracefully."""
    bad_code = """import plotly.express as px
fig = px.bar(df, x="NON_EXISTENT_COLUMN", y="OEE")
"""
    fig, success, msg = execute_chart_code(bad_code, sample_oee_df)
    assert success is False
    assert "NON_EXISTENT_COLUMN" in msg or "KeyError" in msg or "ValueError" in msg
