"""Python Validation Layer for Visualization Specifications.

Verifies and validates visualization specifications from Cortex AI before rendering:
1. Validates chart_type against SUPPORTED_CHART_TYPES.
2. Validates required columns exist in the DataFrame.
3. Ensures valid data types for axes (e.g. numeric y-axis, categorical/date x-axis).
4. Handles fallback to safe alternatives (e.g., table or bar chart) if spec validation fails.
"""

import pandas as pd
from typing import Dict, Any, Tuple
from config import SUPPORTED_CHART_TYPES

class PythonValidator:
    def __init__(self):
        self.supported_types = set(SUPPORTED_CHART_TYPES)

    def validate_and_sanitize(self, spec: Dict[str, Any], data: pd.DataFrame) -> Tuple[Dict[str, Any], bool, str]:
        """Validate chart spec against data and list of supported chart types.

        Returns:
            (validated_spec, is_valid, warning_or_error_message)
        """
        if not isinstance(spec, dict) or "chart_type" not in spec:
            fallback = self._get_fallback_spec(data, "Invalid spec format. Defaulting to table rendering.")
            return fallback, False, "Invalid specification format."

        chart_type = spec.get("chart_type")
        config = spec.get("config", {})

        # Check supported chart type
        if chart_type not in self.supported_types:
            fallback = self._get_fallback_spec(data, f"Chart type '{chart_type}' is unsupported by validation layer. Defaulting to bar/table.")
            return fallback, False, f"Unsupported chart type '{chart_type}'."

        if data is None or data.empty:
            # If no data, allow kpi_card or table
            spec["chart_type"] = "kpi_card"
            return spec, True, "No data available."

        cols = list(data.columns)

        # Validate chart specific column presence and types
        if chart_type in ["line", "bar", "scatter"]:
            x_col = config.get("x_axis")
            y_col = config.get("y_axis")

            if not x_col or x_col not in cols:
                x_col = cols[0]
                config["x_axis"] = x_col

            if not y_col or y_col not in cols:
                y_col = cols[1] if len(cols) > 1 else cols[0]
                config["y_axis"] = y_col

            # Verify y-axis numeric
            if not pd.api.types.is_numeric_dtype(data[config["y_axis"]]):
                # Attempt conversion or fallback
                try:
                    data[config["y_axis"]] = pd.to_numeric(data[config["y_axis"]])
                except Exception:
                    fallback = self._get_fallback_spec(data, f"Y-axis '{config['y_axis']}' is non-numeric.")
                    return fallback, False, f"Y-axis column '{config['y_axis']}' must be numeric."

        elif chart_type in ["pie", "donut"]:
            cat_col = config.get("category_col") or cols[0]
            val_col = config.get("value_col") or (cols[1] if len(cols) > 1 else cols[0])

            if cat_col not in cols:
                cat_col = cols[0]
            if val_col not in cols or not pd.api.types.is_numeric_dtype(data[val_col]):
                val_col = cols[1] if len(cols) > 1 and pd.api.types.is_numeric_dtype(data[cols[1]]) else cols[0]

            config["category_col"] = cat_col
            config["value_col"] = val_col

        elif chart_type == "gauge":
            val_col = config.get("value_col")
            if not val_col or val_col not in cols:
                # Find first numeric column
                numeric_cols = data.select_dtypes(include=["number"]).columns
                if len(numeric_cols) > 0:
                    config["value_col"] = numeric_cols[0]
                else:
                    spec["chart_type"] = "kpi_card"

        spec["config"] = config
        return spec, True, "Validation passed."

    def _get_fallback_spec(self, data: pd.DataFrame, reason: str) -> Dict[str, Any]:
        """Construct fallback spec when validation fails."""
        if data is not None and not data.empty and len(data.columns) >= 2:
            cols = list(data.columns)
            return {
                "chart_type": "bar",
                "title": f"Fallback Chart View ({cols[1]} by {cols[0]})",
                "description": f"Validation Layer Fallback: {reason}",
                "config": {
                    "x_axis": cols[0],
                    "y_axis": cols[1],
                    "primary_color": "#e74c3c"
                }
            }

        return {
            "chart_type": "table",
            "title": "Fallback Table View",
            "description": f"Validation Layer Fallback: {reason}",
            "config": {}
        }
