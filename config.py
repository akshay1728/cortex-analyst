"""Configuration settings for the Manufacturing OEE Conversational Analytics Application."""

import os

APP_TITLE = "Manufacturing OEE Conversational Analytics"
APP_ICON = "🏭"

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

# Snowflake / Cortex API Configuration defaults (can be overridden by st.secrets or env vars)
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "MANUFACTURING_DB"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "OEE_ANALYTICS")
}
