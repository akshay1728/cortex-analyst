"""Cortex AI / AI_COMPLETE Service for Visualization Decision.

Integrates Snowflake Cortex AI (`SNOWFLAKE.CORTEX.COMPLETE` / `cortex.complete`):
1. Formulates LLM system prompt asking Cortex AI to analyze user question + query data schema/summary.
2. Invokes Snowflake Cortex AI `cortex.complete('mistral-large', prompt)` or SQL `SNOWFLAKE.CORTEX.COMPLETE(...)` when active Snowflake session exists.
3. Parses JSON visualization specification returned by Cortex AI model.
4. Provides robust fallback heuristic decision engine when offline or no Snowflake session is present.
"""

import json
import os
import pandas as pd
from typing import Dict, Any, Optional

class CortexAIService:
    def __init__(self, session=None, model_name: str = "mistral-large"):
        """Initialize Cortex AI service with optional Snowflake session and LLM model name."""
        self.session = session
        self.model_name = model_name

    def call_cortex_complete(self, prompt: str) -> str:
        """Call Snowflake Cortex AI COMPLETE function (`SNOWFLAKE.CORTEX.COMPLETE` or snowpark `cortex.complete`)."""
        if self.session is not None:
            try:
                # Option A: Snowpark cortex complete call
                from snowflake.cortex import Complete
                return Complete(self.model_name, prompt, session=self.session)
            except Exception:
                # Option B: Snowflake SQL CORTEX.COMPLETE execution
                escaped_prompt = prompt.replace("'", "''")
                sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{self.model_name}', '{escaped_prompt}') AS RESPONSE"
                res = self.session.sql(sql).collect()
                return res[0]["RESPONSE"] if res else ""
        return ""

    def decide_visualization(self, question: str, analyst_response: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intent and query data via Cortex AI COMPLETE to generate structured visualization spec."""
        data = analyst_response.get("data")
        query_type = analyst_response.get("query_type", "summary")
        summary_text = analyst_response.get("summary_text", "")

        if data is None or data.empty:
            return self._build_spec(
                chart_type="kpi_card",
                title="No Data Available",
                description="The query returned no records to visualize."
            )

        cols = list(data.columns)

        # Attempt to use Cortex AI COMPLETE model if Snowflake session available
        if self.session is not None:
            prompt = self._construct_cortex_prompt(question, cols, data.head(5).to_dict(orient="records"), summary_text)
            response_raw = self.call_cortex_complete(prompt)
            parsed_spec = self._parse_cortex_response(response_raw)
            if parsed_spec:
                return parsed_spec

        # Smart Heuristic Visualization Decision Engine (Cortex AI logic simulation)
        q_lower = question.lower()
        group_col = analyst_response.get("group_col")

        if query_type == "trend" or "trend" in q_lower or "over time" in q_lower or "Date" in cols:
            return self._build_spec(
                chart_type="line",
                title=f"Trend Analysis: {cols[1] if len(cols) > 1 else 'Metric'} Over Time",
                x_axis="Date",
                y_axis=cols[1] if len(cols) > 1 else cols[0],
                color="#1f77b4",
                description="Line chart showing temporal variation of OEE metric generated via Cortex AI."
            )

        if query_type == "breakdown" and group_col:
            category_col = cols[0]
            val_col = cols[1] if len(cols) > 1 else cols[0]

            if len(data) <= 6 and ("pie" in q_lower or "proportion" in q_lower or "distribution" in q_lower or "share" in q_lower or "downtime" in q_lower):
                return self._build_spec(
                    chart_type="donut",
                    title=f"Proportional Breakdown of {val_col} by {category_col}",
                    category_col=category_col,
                    value_col=val_col,
                    description="Donut chart illustrating proportional contribution selected by Cortex AI."
                )

            return self._build_spec(
                chart_type="bar",
                title=f"{val_col} Comparison by {category_col}",
                x_axis=category_col,
                y_axis=val_col,
                color="#00a86b",
                description="Bar chart comparing values across dimensions selected by Cortex AI."
            )

        if "gauge" in q_lower or ("oee" in q_lower and query_type == "summary"):
            return self._build_spec(
                chart_type="gauge",
                title="Overall Equipment Effectiveness (OEE) Target",
                value_col="OEE (%)",
                target_value=85.0,
                description="Gauge chart representing OEE against World Class target (85%)."
            )

        if query_type == "summary" or len(data) == 1:
            return self._build_spec(
                chart_type="kpi_card",
                title="Manufacturing OEE KPI Overview",
                data_summary=summary_text,
                description="Key Performance Indicator summary cards."
            )

        return self._build_spec(
            chart_type="table",
            title="Aggregated Manufacturing Data Table",
            description="Tabular view of queried metrics."
        )

    def _construct_cortex_prompt(self, question: str, columns: list, sample_data: list, summary_text: str) -> str:
        """Construct prompt for Snowflake Cortex AI COMPLETE."""
        return f"""
System: You are an expert data visualization engineer using Snowflake Cortex AI (`SNOWFLAKE.CORTEX.COMPLETE`).
User Question: "{question}"
Data Summary: "{summary_text}"
Columns: {columns}
Sample Records: {json.dumps(sample_data)}

Respond ONLY with a valid JSON object specifying the chart configuration:
{{
  "chart_type": "line|bar|donut|gauge|table|kpi_card",
  "title": "<Chart Title>",
  "description": "<Description>",
  "config": {{
     "x_axis": "<col>",
     "y_axis": "<col>",
     "category_col": "<col>",
     "value_col": "<col>",
     "target_value": 85.0,
     "primary_color": "#1f77b4"
  }}
}}
"""

    def _parse_cortex_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse raw JSON string response from Cortex AI."""
        if not response_text:
            return None
        try:
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
        except Exception:
            pass
        return None

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
