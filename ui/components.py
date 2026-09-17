"""UI Components for Manufacturing OEE Conversational Analytics App."""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from data.sample_data import calculate_aggregated_oee



def render_kpi_cards(kpi_data: Dict[str, Any]):
    """Render KPI Metric Cards in top row comparing current vs previous period."""
    if not kpi_data:
        kpi_data = {}

    curr_start = kpi_data.get("current_start_date") or kpi_data.get("curr_start") or "N/A"
    curr_end = kpi_data.get("current_end_date") or kpi_data.get("curr_end") or "N/A"
    prev_start = kpi_data.get("previous_start_date") or kpi_data.get("prev_start") or "N/A"
    prev_end = kpi_data.get("previous_end_date") or kpi_data.get("prev_end") or "N/A"

    # Display comparison period dates
    st.caption(
        f"📅 **Current Period:** {curr_start} to {curr_end} | "
        f"📅 **Previous Comparison Period:** {prev_start} to {prev_end}"
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    curr_oee = float(kpi_data.get("current_oee") or kpi_data.get("oee", 0.0))
    prev_oee = float(kpi_data.get("previous_oee", 0.0))
    diff_oee = curr_oee - prev_oee

    curr_avail = float(kpi_data.get("current_availability") or kpi_data.get("availability", 0.0))
    prev_avail = float(kpi_data.get("previous_availability", 0.0))
    diff_avail = curr_avail - prev_avail

    curr_perf = float(kpi_data.get("current_performance") or kpi_data.get("performance", 0.0))
    prev_perf = float(kpi_data.get("previous_performance", 0.0))
    diff_perf = curr_perf - prev_perf

    curr_qual = float(kpi_data.get("current_quality") or kpi_data.get("quality", 0.0))
    prev_qual = float(kpi_data.get("previous_quality", 0.0))
    diff_qual = curr_qual - prev_qual

    curr_dt = float(kpi_data.get("current_downtime_hours") or kpi_data.get("total_downtime_hours", 0.0))
    prev_dt = float(kpi_data.get("previous_downtime_hours", 0.0))
    diff_dt = curr_dt - prev_dt

    col1.metric("Overall OEE", f"{curr_oee:.1f}%", delta=f"{diff_oee:+.1f}% vs Prev ({prev_oee:.1f}%)")
    col2.metric("Availability", f"{curr_avail:.1f}%", delta=f"{diff_avail:+.1f}% vs Prev ({prev_avail:.1f}%)")
    col3.metric("Performance", f"{curr_perf:.1f}%", delta=f"{diff_perf:+.1f}% vs Prev ({prev_perf:.1f}%)")
    col4.metric("Quality", f"{curr_qual:.1f}%", delta=f"{diff_qual:+.1f}% vs Prev ({prev_qual:.1f}%)")
    col5.metric("Downtime Hours", f"{round(curr_dt):,d} hrs", delta=f"{round(diff_dt):+,d} hrs vs Prev", delta_color="inverse")


def render_sample_questions(on_click_callback):
    """Render quick sample question buttons dynamically loaded strictly from DB or session state."""
    st.markdown("##### 💡 Suggested Questions")

    sq_list = st.session_state.get("suggested_questions_list", [])
    if sq_list:
        sample_questions = [q_obj["text"] for q_obj in sq_list if isinstance(q_obj, dict) and q_obj.get("text")]
    else:
        sample_questions = []

    if not sample_questions:
        st.info("No suggested questions configured in the database.")
        return

    cols = st.columns(min(len(sample_questions), 3))
    for idx, q in enumerate(sample_questions):
        cols[idx % min(len(sample_questions), 3)].button(
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
