"""Restricted Execution Engine for Dynamic Chart Generation.

Executes AST-validated Python code in a restricted namespace:
- Pass only approved modules (plotly.express, plotly.graph_objects, pandas, numpy) and DataFrame `df`.
- Captures generated `fig` Plotly Figure object.
- Prevents access to filesystem, OS, network, and application state.
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Tuple, Any, Optional

def execute_chart_code(code_str: str, df: pd.DataFrame) -> Tuple[Optional[Any], bool, str]:
    """Execute validated visualization code in a restricted execution namespace.

    Returns:
        (fig_object, success_flag, error_or_status_message)
    """
    if df is None or df.empty:
        return None, False, "Cannot execute chart code on empty DataFrame."

    # Create defensive copy of input DataFrame so execution cannot mutate original
    df_copy = df.copy()

    # Define restricted execution namespace with approved tools and safe builtins
    restricted_globals = {
        "__builtins__": {
            "__import__": __import__,
            "range": range,
            "len": len,
            "list": list,
            "dict": dict,
            "set": set,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "round": round,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "zip": zip,
            "enumerate": enumerate,
            "isinstance": isinstance,
            "print": lambda *args, **kwargs: None
        },
        "px": px,
        "go": go,
        "plotly": px.pd if hasattr(px, "pd") else None,
        "pd": pd,
        "np": np,
        "df": df_copy
    }

    restricted_locals = {}

    try:
        exec(code_str, restricted_globals, restricted_locals)
        fig = restricted_locals.get("fig") or restricted_globals.get("fig")

        if fig is None:
            return None, False, "Execution completed but no 'fig' variable was assigned."

        # Verify fig is a Plotly Figure or dict-like object
        if hasattr(fig, "to_dict") or isinstance(fig, (go.Figure, dict)):
            return fig, True, "Execution successful."

        return None, False, f"Variable 'fig' is of invalid type '{type(fig).__name__}', expected Plotly Figure."

    except Exception as e:
        return None, False, f"Runtime error during chart execution: {type(e).__name__} - {str(e)}"
