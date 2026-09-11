"""Cortex Agent Integration Service.

Integrates Snowflake Cortex Agent REST API (/api/v2/cortex/agent:run):
1. Posts to Cortex Agent REST endpoint with SSE streaming.
2. Collects streamed delta fragments into ordered content blocks (text, tool_results, chart).
3. Converts tool_results (query_id or inline result_set) to Pandas DataFrames.
4. Renders Vega-Lite / Plotly charts (self-contained specs or data-injected specs).
5. Provides safe offline simulation fallback when Snowflake connection or st.secrets are absent.
"""

import json
import re
import logging
from typing import Generator, Dict, Any, List, Optional, Tuple
import pandas as pd
import requests
import streamlit as st


def split_suggestions(text: str) -> Tuple[str, List[str]]:
    """Return (main_text, [suggestions]) by extracting a trailing [SUGGESTIONS] block."""
    parts = re.split(r'\n?\[SUGGESTIONS\]\s*', text, maxsplit=1)
    if len(parts) == 1:
        return text.strip(), []
    main, block = parts
    suggestions = [
        line.lstrip("-* ").strip()
        for line in block.splitlines()
        if line.strip().startswith(("-", "*"))
    ]
    return main.strip(), suggestions

from services.snowflake_connection import get_snowflake_session
from data.sample_data import generate_oee_dataset

logger = logging.getLogger("cortex_agent_service")


def get_agent_auth_config() -> Tuple[Optional[str], Optional[str]]:
    """Retrieve Snowflake Host and Token for Cortex Agent REST API calls."""
    try:
        session = get_snowflake_session()
        snowflake_host = st.secrets.get("SNOWFLAKE_HOST") if hasattr(st, "secrets") else None

        if not snowflake_host and session is not None:
            # Extract host from session connection parameters if available
            try:
                conn_params = session.connection.rest.host
                snowflake_host = conn_params
            except Exception:
                pass

        token = None
        if session is not None:
            try:
                token = session.connection.rest.token
            except Exception:
                pass

        return snowflake_host, token
    except Exception as e:
        logger.warning(f"Unable to retrieve Snowflake session or host for Cortex Agent: {e}")
        return None, None


def call_agent(messages: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
    """POSTs to /api/v2/cortex/agent:run with stream=True, reads SSE stream, yields data JSON events."""
    snowflake_host, token = get_agent_auth_config()

    if not snowflake_host or not token:
        logger.info("Snowflake host or token missing. Using offline simulated agent generator.")
        for evt in _simulated_agent_stream(messages):
            yield evt
        return

    agent_endpoint = f"https://{snowflake_host}/api/v2/cortex/agent:run"
    headers = {
        "Authorization": f'Snowflake Token="{token}"',
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    # Format messages for Cortex Agent REST API
    formatted_api_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, str):
            formatted_api_messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            formatted_api_messages.append({"role": role, "content": content})

    semantic_view = st.secrets.get("SEMANTIC_VIEW", "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS") if hasattr(st, "secrets") else "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS"

    payload = {
        "model": "claude-sonnet-4-5",
        "messages": formatted_api_messages,
        "tools": [
            {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "traksys_analyst"}},
            {"tool_spec": {"type": "sql_exec", "name": "sql_exec"}},
            {"tool_spec": {"type": "data_to_chart", "name": "data_to_chart"}},
        ],
        "tool_resources": {
            "traksys_analyst": {"semantic_view": semantic_view}
        },
    }

    try:
        resp = requests.post(agent_endpoint, headers=headers, json=payload, stream=True, timeout=60)
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue

    except Exception as req_err:
        logger.error(f"Cortex Agent API request failed: {req_err}. Falling back to simulated response.")
        for evt in _simulated_agent_stream(messages):
            yield evt


def collect_response(events: Generator[Dict[str, Any], None, None]) -> List[Dict[str, Any]]:
    """Merge streaming deltas into a list of finished, ordered content blocks."""
    text_buf = ""
    blocks = []  # ordered list of {"type": ..., ...}

    for evt in events:
        delta = evt.get("data", {}).get("delta", {})
        for item in delta.get("content", []):
            t = item.get("type")

            if t == "text":
                text_buf += item.get("text", "")

            elif t == "chart":
                if text_buf:
                    blocks.append({"type": "text", "text": text_buf})
                    text_buf = ""
                blocks.append({"type": "chart", "spec": item["chart"]["chart_spec"]})

            elif t == "tool_results":
                if text_buf:
                    blocks.append({"type": "text", "text": text_buf})
                    text_buf = ""
                blocks.append({"type": "tool_results", "content": item["tool_results"]})

    if text_buf:
        blocks.append({"type": "text", "text": text_buf})

    return blocks


def tool_results_to_df(tool_results: Any) -> Optional[pd.DataFrame]:
    """Turn a tool_results block into a Pandas DataFrame."""
    session = get_snowflake_session()

    if isinstance(tool_results, list):
        content_items = tool_results
    elif isinstance(tool_results, dict):
        content_items = tool_results.get("content", [])
    else:
        content_items = []

    for c in content_items:
        j = c.get("json", {}) if isinstance(c, dict) else {}

        # Path A: query_id / statement_handle with session
        qid = j.get("query_id") or j.get("statement_handle")
        if qid and session is not None:
            try:
                return session.sql(f"SELECT * FROM TABLE(RESULT_SCAN('{qid}'))").to_pandas()
            except Exception as e:
                logger.warning(f"RESULT_SCAN for query_id '{qid}' failed: {e}")

        # Path B: inline result set
        rs = j.get("result_set")
        if rs and isinstance(rs, dict):
            try:
                cols = [col["name"] for col in rs.get("resultSetMetaData", {}).get("rowType", [])]
                data_rows = rs.get("data", [])
                return pd.DataFrame(data_rows, columns=cols)
            except Exception as e_rs:
                logger.warning(f"Parsing inline result_set failed: {e_rs}")

        # Path C: inline dataframe or direct dict
        if "dataframe" in j and isinstance(j["dataframe"], pd.DataFrame):
            return j["dataframe"]

    return None


def render_chart(spec_str: str, df: Optional[pd.DataFrame] = None, key: Optional[str] = None):
    """Render a chart spec (self-contained OR spec + injected df) via st.vega_lite_chart."""
    try:
        spec = json.loads(spec_str) if isinstance(spec_str, str) else spec_str
    except Exception as parse_err:
        st.error(f"Failed to parse chart spec JSON: {parse_err}")
        return

    if isinstance(spec, dict):
        spec.pop("width", None)
        spec.pop("height", None)

    if isinstance(spec, dict) and "data" in spec:
        st.vega_lite_chart(spec, use_container_width=True, key=key)
    elif df is not None and not df.empty:
        st.vega_lite_chart(df, spec, use_container_width=True, key=key)
    else:
        st.warning("Chart spec received but no data to plot.")


def _simulated_agent_stream(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates simulated Cortex Agent SSE events for offline/mock development."""
    last_msg = messages[-1] if messages else {}
    content = last_msg.get("content", "")
    if isinstance(content, list):
        q_text = " ".join([item.get("text", "") for item in content if item.get("type") == "text"])
    else:
        q_text = str(content)

    q_lower = q_text.lower()
    df_raw = generate_oee_dataset()

    # Determine metric and grouping for offline response
    if "availability" in q_lower:
        metric = "availability"
        m_label = "Availability (%)"
    elif "performance" in q_lower:
        metric = "performance"
        m_label = "Performance (%)"
    elif "quality" in q_lower:
        metric = "quality"
        m_label = "Quality (%)"
    elif "downtime" in q_lower or "cause" in q_lower or "reason" in q_lower:
        metric = "downtime_hours"
        m_label = "Downtime (Hours)"
    else:
        metric = "oee"
        m_label = "OEE (%)"

    if "plant" in q_lower:
        group_col = "plant"
        g_label = "Plant"
    elif "line" in q_lower:
        group_col = "line"
        g_label = "Line"
    elif "shift" in q_lower:
        group_col = "shift"
        g_label = "Shift"
    elif "downtime" in q_lower or "cause" in q_lower or "reason" in q_lower:
        group_col = "downtime_reason"
        g_label = "Downtime Reason"
    else:
        group_col = "plant"
        g_label = "Plant"

    if metric == "downtime_hours":
        res_df = df_raw.groupby(group_col)[metric].sum().reset_index()
    else:
        res_df = df_raw.groupby(group_col)[metric].mean().reset_index()

    res_df[metric] = res_df[metric].round(2)
    res_df = res_df.sort_values(by=metric, ascending=False)
    res_df.columns = [g_label, m_label]

    # Convert res_df to inline result set
    cols_meta = [{"name": c} for c in res_df.columns]
    data_matrix = res_df.values.tolist()

    summary_text = (
        f"### 🤖 Cortex Agent Executive Analysis: {m_label} by {g_label}\n\n"
        f"- **Top Segment**: **{res_df.iloc[0][g_label]}** at **{res_df.iloc[0][m_label]}**.\n"
        f"- **Segment Average**: **{res_df[m_label].mean():.2f}** across {len(res_df)} evaluated categories.\n\n"
        f"**Recommendation**: Optimize operations based on top segment practices."
    )

    chart_spec_dict = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": {"type": "bar", "color": "#242B6B", "tooltip": True},
        "encoding": {
            "x": {"field": g_label, "type": "nominal", "axis": {"labelAngle": 0}},
            "y": {"field": m_label, "type": "quantitative"}
        }
    }

    return [
        {
            "event": "message.delta",
            "data": {"delta": {"content": [{"type": "text", "text": summary_text}]}}
        },
        {
            "event": "message.delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "tool_results",
                            "tool_results": [
                                {
                                    "json": {
                                        "result_set": {
                                            "resultSetMetaData": {"rowType": cols_meta},
                                            "data": data_matrix
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        },
        {
            "event": "message.delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "chart",
                            "chart": {
                                "chart_spec": json.dumps(chart_spec_dict)
                            }
                        }
                    ]
                }
            }
        }
    ]
