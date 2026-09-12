"""Cortex Agent Integration Service.

Integrates Snowflake Cortex Agent REST API (/api/v2/cortex/agent:run):
1. Posts to Cortex Agent REST endpoint with SSE streaming.
2. Collects streamed delta fragments into ordered content blocks (text, tool_results, chart).
3. Converts tool_results (query_id or inline result_set) to Pandas DataFrames.
4. Renders Vega-Lite / Plotly charts (self-contained specs or data-injected specs).
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

logger = logging.getLogger("cortex_agent_service")


import os

def get_agent_auth_config() -> Tuple[Optional[str], Optional[str]]:
    """Retrieve Snowflake Host and Token for Cortex Agent REST API calls in Snowflake Container Runtime.

    Supports:
    1. Container Runtime native OAuth token mounted at /snowflake/session/token.
    2. Environment variable SNOWFLAKE_HOST or active Snowpark session.
    """
    try:
        snowflake_host = os.environ.get("SNOWFLAKE_HOST")

        session = get_snowflake_session()
        if not snowflake_host and session is not None:
            try:
                snowflake_host = session.connection.rest.host
            except Exception:
                pass

        token = None
        # Path 1: Container Runtime Native OAuth Token File
        token_path = "/snowflake/session/token"
        if os.path.exists(token_path):
            try:
                with open(token_path, "r") as f:
                    token = f.read().strip()
            except Exception as e:
                logger.warning(f"Unable to read container token at {token_path}: {e}")

        # Path 2: Snowpark session token fallback
        if not token and session is not None:
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
        logger.error("Snowflake host or token missing. Cannot call Cortex Agent API.")
        yield {
            "event": "message.delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "text",
                            "text": "❌ **Error**: Snowflake credentials or session token unavailable. Please check your Snowflake connection settings."
                        }
                    ]
                }
            }
        }
        return

    agent_endpoint = f"https://{snowflake_host}/api/v2/cortex/agent:run"

    # Format messages for Cortex Agent REST API
    formatted_api_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, str):
            formatted_api_messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            formatted_api_messages.append({"role": role, "content": content})

    semantic_view = os.environ.get("SEMANTIC_VIEW", "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS")

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

    # Try auth header schemes: 'Snowflake Token="..."' and 'Bearer ...'
    auth_headers_to_try = [
        {"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json", "Accept": "text/event-stream"},
        {"Authorization": f'Bearer {token}', "Content-Type": "application/json", "Accept": "text/event-stream"},
    ]

    resp = None
    last_err = None

    for headers in auth_headers_to_try:
        try:
            r = requests.post(agent_endpoint, headers=headers, json=payload, stream=True, timeout=60)
            if r.status_code == 401:
                logger.info("401 Unauthorized with auth header scheme. Trying alternative auth scheme...")
                last_err = requests.HTTPError(f"401 Client Error: Unauthorized for url: {agent_endpoint}", response=r)
                continue
            r.raise_for_status()
            resp = r
            break
        except requests.HTTPError as h_err:
            last_err = h_err
            if h_err.response is not None and h_err.response.status_code == 401:
                continue
            raise h_err

    if resp is None and last_err is not None:
        logger.error(f"Cortex Agent API request failed: {last_err}.")
        yield {
            "event": "message.delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ **Cortex Agent Error**: {last_err}"
                        }
                    ]
                }
            }
        }
        return

    try:
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
        logger.error(f"Cortex Agent API stream reading failed: {req_err}.")
        yield {
            "event": "message.delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ **Cortex Agent Error**: {req_err}"
                        }
                    ]
                }
            }
        }


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
