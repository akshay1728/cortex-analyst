"""UI Components for Manufacturing OEE Conversational Analytics App."""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from data.sample_data import calculate_aggregated_oee

def render_sidebar_filters(df: pd.DataFrame) -> Dict[str, Any]:
    """Render sidebar filters and return user selected options."""
    st.sidebar.header("🔍 OEE Global Filters")

    # Date Range Filter
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Plant Filter
    available_plants = ["All"] + sorted(list(df["plant"].unique()))
    selected_plants = st.sidebar.multiselect("Select Plant(s)", options=available_plants, default=["All"])

    # Line Filter
    available_lines = ["All"] + sorted(list(df["line"].unique()))
    selected_lines = st.sidebar.multiselect("Select Line(s)", options=available_lines, default=["All"])

    # Shift Filter
    available_shifts = ["All"] + sorted(list(df["shift"].unique()))
    selected_shifts = st.sidebar.multiselect("Select Shift(s)", options=available_shifts, default=["All"])

    # Product Family Filter
    available_families = ["All"] + sorted(list(df["product_family"].unique()))
    selected_families = st.sidebar.multiselect("Product Family", options=available_families, default=["All"])

    st.sidebar.divider()
    st.sidebar.caption("⚡ Powered by Snowflake Cortex Analyst & AI")

    return {
        "date_range": date_range,
        "plants": selected_plants,
        "lines": selected_lines,
        "shifts": selected_shifts,
        "product_families": selected_families
    }


def render_kpi_cards(kpis: Dict[str, Any]):
    """Render KPI Metric Cards in top row."""
    col1, col2, col3, col4, col5 = st.columns(5)

    oee_val = kpis.get("oee", 0.0)
    avail_val = kpis.get("availability", 0.0)
    perf_val = kpis.get("performance", 0.0)
    qual_val = kpis.get("quality", 0.0)
    dt_val = kpis.get("total_downtime_hours", 0.0)

    col1.metric("Overall OEE", f"{oee_val:.1f}%", delta=f"{oee_val - 85.0:.1f}% vs Target (85%)")
    col2.metric("Availability", f"{avail_val:.1f}%", delta=f"{avail_val - 90.0:.1f}% vs Target")
    col3.metric("Performance", f"{perf_val:.1f}%", delta=f"{perf_val - 95.0:.1f}% vs Target")
    col4.metric("Quality", f"{qual_val:.1f}%", delta=f"{qual_val - 99.0:.1f}% vs Target")
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
        if cols[idx % 3].button(q, key=f"sq_{idx}", use_container_width=True):
            on_click_callback(q)
