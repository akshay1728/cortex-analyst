"""UI Components for Manufacturing OEE Conversational Analytics App."""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from data.sample_data import calculate_aggregated_oee

def _find_col(df: pd.DataFrame, target_name: str) -> str:
    """Find a column in DataFrame matching target_name (case-insensitive)."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        if str(col).lower() == target_name.lower():
            return col
    return None

def render_sidebar_filters(df: pd.DataFrame) -> Dict[str, Any]:
    """Render sidebar filters and return user selected options.

    Uses relative `st.xxx(...)` calls so this renders correctly whichever container it's called from.
    Handles case-insensitive column lookups for 'date', 'plant', 'line', 'shift', 'product_family'.
    """
    if df is None or df.empty:
        st.info("No telemetry dataset loaded.")
        return {
            "date_range": (),
            "plants": ["All"],
            "lines": ["All"],
            "shifts": ["All"],
            "product_families": ["All"]
        }

    date_col = _find_col(df, "date")
    plant_col = _find_col(df, "plant")
    line_col = _find_col(df, "line")
    shift_col = _find_col(df, "shift")
    family_col = _find_col(df, "product_family")

    # Date Range Filter
    date_range = ()
    if date_col:
        try:
            date_series = pd.to_datetime(df[date_col])
            min_date = date_series.min().date()
            max_date = date_series.max().date()
            date_range = st.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        except Exception:
            pass

    # Plant Filter
    selected_plants = ["All"]
    if plant_col:
        available_plants = ["All"] + sorted(list(df[plant_col].dropna().astype(str).unique()))
        selected_plants = st.multiselect("Select Plant(s)", options=available_plants, default=["All"])

    # Line Filter
    selected_lines = ["All"]
    if line_col:
        available_lines = ["All"] + sorted(list(df[line_col].dropna().astype(str).unique()))
        selected_lines = st.multiselect("Select Line(s)", options=available_lines, default=["All"])

    # Shift Filter
    selected_shifts = ["All"]
    if shift_col:
        available_shifts = ["All"] + sorted(list(df[shift_col].dropna().astype(str).unique()))
        selected_shifts = st.multiselect("Select Shift(s)", options=available_shifts, default=["All"])

    # Product Family Filter
    selected_families = ["All"]
    if family_col:
        available_families = ["All"] + sorted(list(df[family_col].dropna().astype(str).unique()))
        selected_families = st.multiselect("Product Family", options=available_families, default=["All"])

    return {
        "date_range": date_range,
        "plants": selected_plants,
        "lines": selected_lines,
        "shifts": selected_shifts,
        "product_families": selected_families
    }


def render_kpi_cards(kpis: Dict[str, Any], targets: Dict[str, float] = None):
    """Render KPI Metric Cards in top row comparing against target thresholds."""
    if targets is None:
        targets = {"oee": 85.0, "availability": 90.0, "performance": 95.0, "quality": 99.0}

    col1, col2, col3, col4, col5 = st.columns(5)

    oee_val = kpis.get("oee", 0.0)
    avail_val = kpis.get("availability", 0.0)
    perf_val = kpis.get("performance", 0.0)
    qual_val = kpis.get("quality", 0.0)
    dt_val = kpis.get("total_downtime_hours", 0.0)

    target_oee = targets.get("oee", 85.0)
    target_avail = targets.get("availability", 90.0)
    target_perf = targets.get("performance", 95.0)
    target_qual = targets.get("quality", 99.0)

    col1.metric("Overall OEE", f"{oee_val:.1f}%", delta=f"{oee_val - target_oee:.1f}% vs Target ({target_oee:.0f}%)")
    col2.metric("Availability", f"{avail_val:.1f}%", delta=f"{avail_val - target_avail:.1f}% vs Target ({target_avail:.0f}%)")
    col3.metric("Performance", f"{perf_val:.1f}%", delta=f"{perf_val - target_perf:.1f}% vs Target ({target_perf:.0f}%)")
    col4.metric("Quality", f"{qual_val:.1f}%", delta=f"{qual_val - target_qual:.1f}% vs Target ({target_qual:.0f}%)")
    col5.metric("Downtime Hours", f"{dt_val:.1f} hrs", delta_color="inverse")


def render_sample_questions(on_click_callback):
    """Render quick sample question buttons for user convenience."""
    st.markdown("##### 💡 Suggested Questions")
    sample_questions = [
        "What is our overall OEE trend over time?",
        "Compare OEE by plant",
        "Which line has the highest downtime?",
        "What are the top downtime causes?",
        "Show quality rate by product family",
        "Show breakdown of good vs defective units"
    ]

    cols = st.columns(3)
    for idx, q in enumerate(sample_questions):
        cols[idx % 3].button(
            q,
            key=f"sq_{idx}",
            use_container_width=True,
            on_click=on_click_callback,
            args=(q,)
        )


def style_dataframe_metrics(df: pd.DataFrame, metric_colors: dict):
    """Apply background color styling to DataFrame columns matching metric thresholds.

    `metric_colors` format:
    {
        "oee": {"enabled": False, "threshold": 85.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "availability": ...
    }
    """
    if df is None or df.empty:
        return df

    # Normalize column mapping
    metric_aliases = {
        "oee": ["oee", "oee_pct", "oee_percentage", "overall_oee"],
        "availability": ["availability", "avail", "availability_pct", "availability_percentage"],
        "performance": ["performance", "perf", "performance_pct", "performance_percentage"],
        "quality": ["quality", "qual", "quality_pct", "quality_percentage"]
    }

    styled = df.style

    for m_key, color_cfg in metric_colors.items():
        if not color_cfg.get("enabled", False):
            continue

        thresh = float(color_cfg.get("threshold", 85.0))
        pass_col = color_cfg.get("pass_color", "#28a745")
        fail_col = color_cfg.get("fail_color", "#dc3545")

        aliases = metric_aliases.get(m_key, [m_key])

        # Find matching columns in DataFrame (case-insensitive substring or exact match)
        matched_cols = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(alias in col_lower for alias in aliases):
                matched_cols.append(col)

        for col in matched_cols:
            def cell_styler(val, threshold=thresh, pass_c=pass_col, fail_c=fail_col):
                try:
                    num_val = float(val)
                    if num_val <= 1.0 and threshold > 1.0:
                        num_val = num_val * 100.0
                    bg_color = pass_c if num_val >= threshold else fail_c
                    return f'background-color: {bg_color}; color: white; font-weight: bold;'
                except (ValueError, TypeError):
                    return ''

            styled = styled.map(cell_styler, subset=[col])

    return styled
