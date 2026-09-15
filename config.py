"""Configuration settings for the Manufacturing OEE Conversational Analytics Application."""

import os

APP_TITLE = "Manufacturing OEE Conversational Analytics"
APP_ICON = "🏭"

# Snowflake Schema Configuration (can be configured via environment variable SNOWFLAKE_SCHEMA)
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "").strip()


def get_proc_name(proc_name: str) -> str:
    """Format procedure name with optional schema prefix if SNOWFLAKE_SCHEMA is configured."""
    schema = st_state_schema() or SNOWFLAKE_SCHEMA
    if schema:
        return f"{schema}.{proc_name}"
    return proc_name


def st_state_schema() -> str:
    """Read schema setting from Streamlit session state if available."""
    try:
        import streamlit as st
        if hasattr(st, "session_state") and "settings_db_schema" in st.session_state and st.session_state["settings_db_schema"]:
            return str(st.session_state["settings_db_schema"]).strip()
    except Exception:
        pass
    return ""


# Supported Chart Types in Python Validation Layer
SUPPORTED_CHART_TYPES = [
    "line",
    "bar",
    "grouped_bar",
    "stacked_bar",
    "pie",
    "donut",
    "gauge",
    "scatter",
    "heatmap",
    "table",
    "kpi_card"
]

# Supported Metrics
METRICS = {
    "oee": "Overall Equipment Effectiveness (%)",
    "availability": "Availability (%)",
    "performance": "Performance (%)",
    "quality": "Quality (%)",
    "planned_production_time": "Planned Production Time (hrs)",
    "operating_time": "Operating Time (hrs)",
    "downtime_hours": "Downtime (hrs)",
    "ideal_cycle_time": "Ideal Cycle Time (min)",
    "total_count": "Total Units Produced",
    "good_count": "Good Units",
    "reject_count": "Defective Units"
}

# Snowflake / Cortex API Configuration defaults (can be overridden by environment variables)
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "WH_APPS"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "JBEDW_DEV"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "ANALYTICS_OPERATIONS")
}
