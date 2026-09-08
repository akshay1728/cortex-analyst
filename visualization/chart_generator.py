"""Chart Generator Orchestrator Module.

Coordinates:
1. DataFrame metadata extraction and prompt construction (`chart_prompt.py`).
2. Calling Cortex AI / LLM for dynamic code generation.
3. AST security validation (`chart_validator.py`).
4. Controlled execution in restricted namespace (`chart_executor.py`).
5. Fallback & error logging.
"""

import json
import logging
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .chart_prompt import build_visualization_prompt, extract_df_metadata
from .chart_validator import validate_python_code
from .chart_executor import execute_chart_code
from services.cortex_ai import CortexAIService

logger = logging.getLogger("dynamic_chart_generator")

@dataclass
class ChartResult:
    should_visualize: bool
    chart_type: str
    reasoning: str
    python_code: str
    figure: Optional[Any]
    validation_status: str
    is_valid: bool
    error_message: Optional[str] = None

def generate_chart(
    question: str,
    dataframe: pd.DataFrame,
    cortex_ai_service: Optional[CortexAIService] = None,
    analyst_summary: str = ""
) -> ChartResult:
    """Dynamically generate, validate, and execute visualization code based on user question and DataFrame."""

    # Check 1: Empty or invalid DataFrame check
    if dataframe is None or dataframe.empty:
        logger.info("Empty DataFrame provided. Skipping chart generation.")
        return ChartResult(
            should_visualize=False,
            chart_type="none",
            reasoning="DataFrame is empty or missing.",
            python_code="",
            figure=None,
            validation_status="Skipped: Empty DataFrame",
            is_valid=True
        )

    # Check 2: Single scalar metric result check (e.g., 1 row x 1 col)
    if len(dataframe) == 1 and len(dataframe.columns) == 1:
        logger.info("DataFrame contains single scalar value. Skipping chart generation.")
        return ChartResult(
            should_visualize=False,
            chart_type="none",
            reasoning="Query returned a single scalar value; chart is not required.",
            python_code="",
            figure=None,
            validation_status="Skipped: Scalar Value",
            is_valid=True
        )

    # Instantiate Cortex AI service if not supplied
    if cortex_ai_service is None:
        cortex_ai_service = CortexAIService()

    # Step 1: Construct prompt
    prompt = build_visualization_prompt(question, dataframe, analyst_summary)

    # Step 2: Request visualization plan & code from LLM or heuristic simulation
    raw_llm_response = ""
    session = getattr(cortex_ai_service, "session", None)
    if session is not None:
        raw_llm_response = cortex_ai_service.call_cortex_complete(prompt)

    parsed_llm = _parse_llm_json(raw_llm_response)

    # Fallback heuristic code generator if offline/mock mode
    if not parsed_llm:
        parsed_llm = _generate_heuristic_fallback(question, dataframe, analyst_summary)

    should_vis = parsed_llm.get("should_visualize", True)
    chart_type = parsed_llm.get("chart_type", "bar")
    reasoning = parsed_llm.get("reasoning", "")
    python_code = parsed_llm.get("python_code", "").strip()

    if not should_vis or not python_code:
        return ChartResult(
            should_visualize=False,
            chart_type=chart_type,
            reasoning=reasoning,
            python_code="",
            figure=None,
            validation_status="No Chart Required",
            is_valid=True
        )

    # Step 3: AST Code Validation
    is_valid, validation_errors = validate_python_code(python_code)
    if not is_valid:
        error_msg = f"AST Validation Failed: {'; '.join(validation_errors)}"
        logger.warning(f"Validation failed for question '{question}': {error_msg}")
        return ChartResult(
            should_visualize=True,
            chart_type=chart_type,
            reasoning=reasoning,
            python_code=python_code,
            figure=None,
            validation_status="AST Validation Failed",
            is_valid=False,
            error_message=error_msg
        )

    # Step 4: Execute Code in Restricted Namespace
    figure, exec_success, exec_msg = execute_chart_code(python_code, dataframe)
    if not exec_success:
        logger.error(f"Execution failed for question '{question}': {exec_msg}")
        return ChartResult(
            should_visualize=True,
            chart_type=chart_type,
            reasoning=reasoning,
            python_code=python_code,
            figure=None,
            validation_status="Execution Error",
            is_valid=False,
            error_message=exec_msg
        )

    logger.info(f"Successfully generated dynamic chart '{chart_type}' for question: {question}")
    return ChartResult(
        should_visualize=True,
        chart_type=chart_type,
        reasoning=reasoning,
        python_code=python_code,
        figure=figure,
        validation_status="Success",
        is_valid=True
    )


def _parse_llm_json(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON payload from LLM text response."""
    if not response_text:
        return None
    try:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end != 0:
            return json.loads(response_text[start:end])
    except Exception:
        pass
    return None


def _generate_heuristic_fallback(question: str, df: pd.DataFrame, analyst_summary: str) -> Dict[str, Any]:
    """Generates dynamic Plotly code by inspecting DataFrame columns and data types without hardcoding business metrics."""
    q_lower = question.lower()
    cols = list(df.columns)

    # Identify column types dynamically from DataFrame
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetime64"]).columns.tolist()

    # Detect date/time columns dynamically
    for col in cols:
        if col not in datetime_cols and ("date" in col.lower() or "time" in col.lower() or "month" in col.lower() or "day" in col.lower()):
            if col in categorical_cols:
                categorical_cols.remove(col)
            datetime_cols.append(col)

    # 1. Scalar / single value check
    if len(df) <= 1 and len(cols) <= 1:
        return {
            "should_visualize": False,
            "chart_type": "none",
            "reasoning": "Result contains scalar metric.",
            "python_code": ""
        }

    # 2. Relationship / Scatter (Check explicitly before time series if question asks about comparison/relationship between numeric metrics)
    if len(numeric_cols) >= 2 and ("vs" in q_lower or "compare" in q_lower or "relation" in q_lower or "correlation" in q_lower or "scatter" in q_lower):
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]
        color_clause = f', color="{categorical_cols[0]}"' if categorical_cols else ""

        code = f"""import plotly.express as px

fig = px.scatter(
    df,
    x="{x_col}",
    y="{y_col}"{color_clause},
    title="{question.title()}"
)
"""
        return {
            "should_visualize": True,
            "chart_type": "scatter",
            "reasoning": f"Scatter relationship between numeric metrics '{x_col}' and '{y_col}'.",
            "python_code": code
        }

    # 3. Categorical Comparison (e.g. question asks for comparison by category/area/site)
    if categorical_cols and ("by" in q_lower or "comparison" in q_lower or "area" in q_lower or "site" in q_lower or "plant" in q_lower) and not ("trend" in q_lower or "over time" in q_lower or "last 12 months" in q_lower or "monthly trend" in q_lower):
        cat_col = categorical_cols[0]
        val_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])

        code = f"""import plotly.express as px

fig = px.bar(
    df,
    x="{cat_col}",
    y="{val_col}",
    title="{question.title()}",
    text_auto=".1f",
    color_discrete_sequence=["#242B6B"]
)
fig.update_traces(marker_color="#242B6B", textfont_color="white")
"""
        return {
            "should_visualize": True,
            "chart_type": "bar",
            "reasoning": f"Categorical bar comparison chart comparing '{val_col}' by '{cat_col}'.",
            "python_code": code
        }

    # 4. Time Series / Trend
    if ("trend" in q_lower or "over time" in q_lower or "last 12 months" in q_lower or "history" in q_lower or "timeline" in q_lower) or (datetime_cols and not categorical_cols):
        time_col = datetime_cols[0] if datetime_cols else (categorical_cols[0] if categorical_cols else cols[0])
        val_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])

        # Check multi-series (color)
        color_clause = ""
        if len(categorical_cols) > 0 and categorical_cols[0] != time_col:
            color_clause = f', color="{categorical_cols[0]}"'

        code = f"""import plotly.express as px

fig = px.line(
    df,
    x="{time_col}",
    y="{val_col}"{color_clause},
    title="{question.title()}",
    markers=True
)
"""
        return {
            "should_visualize": True,
            "chart_type": "line",
            "reasoning": f"Time series trend visualization with time column '{time_col}'.",
            "python_code": code
        }

    # 5. Distribution / Histogram
    if len(numeric_cols) >= 1 and ("distribution" in q_lower or "histogram" in q_lower or "box" in q_lower):
        val_col = numeric_cols[0]
        code = f"""import plotly.express as px

fig = px.histogram(
    df,
    x="{val_col}",
    title="{question.title()}"
)
"""
        return {
            "should_visualize": True,
            "chart_type": "histogram",
            "reasoning": f"Histogram distribution of metric '{val_col}'.",
            "python_code": code
        }

    # 6. Composition / Pie or Donut
    if len(df) <= 6 and ("pie" in q_lower or "proportion" in q_lower or "share" in q_lower):
        cat_col = categorical_cols[0] if categorical_cols else cols[0]
        val_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
        code = f"""import plotly.express as px

fig = px.pie(
    df,
    names="{cat_col}",
    values="{val_col}",
    title="{question.title()}",
    hole=0.4
)
"""
        return {
            "should_visualize": True,
            "chart_type": "donut",
            "reasoning": f"Proportional composition donut chart by '{cat_col}'.",
            "python_code": code
        }

    # Default Categorical Comparison / Bar Chart
    cat_col = categorical_cols[0] if categorical_cols else cols[0]
    val_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])

    code = f"""import plotly.express as px

fig = px.bar(
    df,
    x="{cat_col}",
    y="{val_col}",
    title="{question.title()}",
    text_auto=".1f",
    color_discrete_sequence=["#242B6B"]
)
fig.update_traces(marker_color="#242B6B", textfont_color="white")
"""
    return {
        "should_visualize": True,
        "chart_type": "bar",
        "reasoning": f"Categorical bar comparison chart comparing '{val_col}' by '{cat_col}'.",
        "python_code": code
    }
