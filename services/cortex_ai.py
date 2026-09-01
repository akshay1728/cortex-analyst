"""Cortex AI / AI_COMPLETE Service for Visualization Decision.

Simulates Snowflake Cortex AI (`SNOWFLAKE.CORTEX.COMPLETE`) model:
1. Analyzes user question + returned query metadata + returned data schema.
2. Selects the optimal visualization type (e.g., line chart, bar chart, donut chart, gauge, heatmap).
3. Produces a structured JSON visualization specification containing chart configuration, x/y dimensions, metrics, color schemes, and annotations.
"""

import json
import pandas as pd
from typing import Dict, Any

class CortexAIService:
    def __init__(self):
        pass

    def decide_visualization(self, question: str, analyst_response: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intent and data to generate structured visualization specification."""
        query_type = analyst_response.get("query_type", "summary")
        data = analyst_response.get("data")
        metric_col = analyst_response.get("metric_col", "oee")
        group_col = analyst_response.get("group_col")
        q_lower = question.lower()

        if data is None or data.empty:
            return self._build_spec(
                chart_type="kpi_card",
                title="No Data Available",
                description="The query returned no records to visualize."
            )

        cols = list(data.columns)

        # Decision Logic based on data shape and intent
        if query_type == "trend" or "trend" in q_lower or "over time" in q_lower or "Date" in cols:
            return self._build_spec(
                chart_type="line",
                title=f"Trend Analysis: {cols[1] if len(cols) > 1 else 'Metric'} Over Time",
                x_axis="Date",
                y_axis=cols[1] if len(cols) > 1 else cols[0],
                color="#1f77b4",
                description="Line chart showing temporal variation of OEE metric."
            )

        if query_type == "breakdown" and group_col:
            category_col = cols[0]
            val_col = cols[1] if len(cols) > 1 else cols[0]

            # Check if pie/donut is suitable (<= 6 categories, composition keyword or downtime reason)
            if len(data) <= 6 and ("pie" in q_lower or "proportion" in q_lower or "distribution" in q_lower or "share" in q_lower or "downtime" in q_lower):
                return self._build_spec(
                    chart_type="donut",
                    title=f"Proportional Breakdown of {val_col} by {category_col}",
                    category_col=category_col,
                    value_col=val_col,
                    description="Donut chart illustrating proportional contribution."
                )

            # Default breakdown to bar chart
            return self._build_spec(
                chart_type="bar",
                title=f"{val_col} Comparison by {category_col}",
                x_axis=category_col,
                y_axis=val_col,
                color="#00a86b",
                description="Bar chart comparing values across dimensions."
            )

        if "gauge" in q_lower or ("oee" in q_lower and query_type == "summary"):
            return self._build_spec(
                chart_type="gauge",
                title="Overall Equipment Effectiveness (OEE) Target",
                value_col="OEE (%)",
                target_value=85.0,
                description="Gauge chart representing OEE against World Class target (85%)."
            )

        # Fallback to KPI cards or table summary
        if query_type == "summary" or len(data) == 1:
            return self._build_spec(
                chart_type="kpi_card",
                title="Manufacturing OEE KPI Overview",
                data_summary=analyst_response.get("summary_text"),
                description="Key Performance Indicator summary cards."
            )

        return self._build_spec(
            chart_type="table",
            title="Aggregated Manufacturing Data Table",
            description="Tabular view of queried metrics."
        )

    def _build_spec(
        self,
        chart_type: str,
        title: str,
        x_axis: str = None,
        y_axis: str = None,
        category_col: str = None,
        value_col: str = None,
        target_value: float = None,
        color: str = "#2b5c8f",
        data_summary: str = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Construct structured visualization spec dict."""
        return {
            "chart_type": chart_type,
            "title": title,
            "description": description,
            "config": {
                "x_axis": x_axis,
                "y_axis": y_axis,
                "category_col": category_col,
                "value_col": value_col,
                "target_value": target_value,
                "primary_color": color,
                "data_summary": data_summary,
                "theme": "light"
            }
        }
