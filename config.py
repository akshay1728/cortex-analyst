"""Configuration settings for the Manufacturing OEE Conversational Analytics Application."""

import os

APP_TITLE = "Manufacturing OEE Conversational Analytics"
APP_ICON = "🏭"

# Directly defined database configuration variables
APP_SCHEMA = os.getenv("APP_SCHEMA", "APPS")
DB = os.getenv("DB", "JBEDW_DEV")
TRACKSYS_SCHEMA = os.getenv("TRACKSYS_SCHEMA", "STAGE_TRAKSYS")
ANALYTICS_SCHEMA = os.getenv("ANALYTICS_SCHEMA", "ANALYTICS_OPERATIONS")

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
