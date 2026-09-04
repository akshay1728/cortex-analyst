"""Visualization Prompt Construction Module.

Constructs DataFrame metadata and dynamic LLM prompt for visualization planning and code generation.
"""

import json
import pandas as pd
from typing import Dict, Any
from config import SUPPORTED_CHART_TYPES

VISUALIZATION_SYSTEM_PROMPT = """You are an expert data visualization engineer specializing in Plotly and Streamlit.

You are given:
1. The user's original natural-language question.
2. A Pandas DataFrame named `df` returned from a database query.
3. Metadata about `df` including column names, data types, row count, and a 1-row sample.

Your task is to determine whether a data visualization would materially improve the answer, and if so, generate executable Python code using Plotly.

Guidelines:
1. Determine if a chart is appropriate. Simple single scalar metrics or empty data do NOT need charts ("should_visualize": false).
2. If visualization IS appropriate, generate python code using Plotly (preferably Plotly Express `px` or `go`).
3. The generated code MUST:
   - Use the provided Pandas DataFrame `df`.
   - Assign the final Plotly Figure to a variable named `fig`.
   - Use actual column names present in `df`.
   - NOT import unauthorized packages (only `plotly`, `plotly.express`, `plotly.graph_objects`, `pandas`, `numpy` are allowed).
   - NOT access filesystem, operating system, network, environment variables, or subprocesses.
   - NOT use `eval`, `exec`, `open`, `__import__`, `globals`, `locals`, or dynamic execution functions.
   - Be clean, concise, and self-contained.

Supported Chart Types:
- bar (vertical or horizontal)
- line
- area
- scatter
- pie / donut
- histogram
- box

Return ONLY a valid JSON object with the following structure:
{
  "should_visualize": true | false,
  "chart_type": "bar|line|area|scatter|pie|donut|histogram|box|none",
  "reasoning": "<Concise explanation why a chart was or was not selected>",
  "python_code": "<Python code snippet generating fig from df>"
}
"""

def extract_df_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract metadata from DataFrame without assuming fixed column names."""
    if df is None or df.empty:
        return {
            "is_empty": True,
            "row_count": 0,
            "columns": [],
            "dtypes": {},
            "sample_record": []
        }

    dtypes_dict = {col: str(dtype) for col, dtype in df.dtypes.items()}
    sample = df.head(1).to_dict(orient="records")

    return {
        "is_empty": False,
        "row_count": len(df),
        "columns": list(df.columns),
        "dtypes": dtypes_dict,
        "sample_record": sample
    }

def build_visualization_prompt(question: str, df: pd.DataFrame, analyst_summary: str = "") -> str:
    """Build complete prompt combining metadata, question, and system instructions."""
    meta = extract_df_metadata(df)

    prompt = f"""
{VISUALIZATION_SYSTEM_PROMPT}

USER QUESTION: "{question}"
ANALYST SUMMARY: "{analyst_summary}"
DATAFRAME METADATA:
- Row Count: {meta['row_count']}
- Columns: {meta['columns']}
- Data Types: {json.dumps(meta['dtypes'])}
- Sample Record (1 Row): {json.dumps(meta['sample_record'], default=str)}

Generate the JSON response:
"""
    return prompt
