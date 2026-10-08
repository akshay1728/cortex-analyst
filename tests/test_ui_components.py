"""Unit tests for UI components and x-axis date series formatting."""

import pytest
from ui.components import _generate_date_series, _two_line_ticks, _stacked_pct_figure


def test_generate_date_series_single_date():
    """Verify that single date selection produces days without time components."""
    start_date = "2024-07-06"
    end_date = "2024-07-06"
    series = _generate_date_series(start_date, end_date, num_points=5)

    assert len(series) == 5
    assert series[-1] == "Jul 06"
    for item in series:
        # Check that no time elements (AM, PM, hours/minutes) exist in the label
        assert "AM" not in item
        assert "PM" not in item
        assert ":" not in item


def test_generate_date_series_date_range():
    """Verify that date range selection produces days across the range without time components."""
    start_date = "2024-07-01"
    end_date = "2024-07-05"
    series = _generate_date_series(start_date, end_date, num_points=5)

    assert len(series) == 5
    assert series == ["Jul 01", "Jul 02", "Jul 03", "Jul 04", "Jul 05"]
    for item in series:
        assert "AM" not in item
        assert "PM" not in item
        assert ":" not in item


def test_two_line_ticks():
    """Verify tick label replacement behavior."""
    labels = ["Jul 01", "Jul 02", "Jul 03"]
    ticks = _two_line_ticks(labels)
    assert ticks == ["Jul 01", "Jul 02", "Jul 03"]


def test_stacked_pct_figure_x_axis():
    """Verify stacked run time vs lost time figure x-axis tick data."""
    dates = _generate_date_series("2024-07-06", "2024-07-06", num_points=5)
    run_pct = [80, 85, 90, 88, 85]
    lost_pct = [20, 15, 10, 12, 15]

    fig = _stacked_pct_figure(dates, run_pct, lost_pct, "Run time", "Lost time", "#242B6B")
    assert fig is not None
    # Verify x values in trace matches day ticks
    trace_x = list(fig.data[0].x)
    assert trace_x == dates
    for tick in trace_x:
        assert "AM" not in str(tick)
        assert "PM" not in str(tick)
