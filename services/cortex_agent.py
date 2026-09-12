"""Cortex Agent Integration Service.

Integrates Snowflake Cortex Agent REST API (/api/v2/cortex/agent:run):
1. Posts to Cortex Agent REST endpoint with SSE streaming.
2. Collects streamed delta fragments into ordered content blocks (text, tool_results, chart, suggested_queries).
3. Converts tool_results (query_id or inline result_set) to Pandas DataFrames.
4. Renders Vega-Lite / Plotly charts (self-contained specs or data-injected specs) with interactive hover pop-out animations and distinct multi-color bar/pie palettes.
"""

import json
import re
import logging
import os
from typing import Generator, Dict, Any, List, Optional, Tuple
import pandas as pd
import requests
import streamlit as st

from services.snowflake_connection import get_snowflake_session

logger = logging.getLogger("cortex_agent_service")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    logger.addHandler(_handler)


def clean_encoding_artifacts(text: str) -> str:
    """Fix mojibake encoding artifacts (e.g. 'Ã' -> '×', 'Ã©' -> 'é')."""
    if not text or not isinstance(text, str):
        return text or ""

    replacements = {
        "Ã": "×",
        "Ã©": "é",
        "Ã ": "à",
        "Ã¨": "è",
        "Ã´": "ô",
        "Ã®": "î",
        "â": "–",
        "â": "—",
        "â": '"',
        "â": '"',
        "â": "'",
        "â¢": "•"
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    try:
        if "Ã" in text or "â" in text:
            fixed = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if len(fixed) > 0 and len(fixed) <= len(text):
                text = fixed
    except Exception:
        pass

    return text


def split_suggestions(text: str) -> Tuple[str, List[str]]:
    """Return (main_text, [suggestions]) by extracting a trailing [SUGGESTIONS] block."""
    text_clean = clean_encoding_artifacts(text)
    parts = re.split(r'\n?\[SUGGESTIONS\]\s*', text_clean, maxsplit=1)
    if len(parts) == 1:
        return text_clean.strip(), []
    main, block = parts
    suggestions = [
        line.lstrip("-* ").strip()
        for line in block.splitlines()
        if line.strip().startswith(("-", "*"))
    ]
    return main.strip(), suggestions


def deduplicate_paragraphs(text: str) -> str:
    """Remove exact or near-duplicate consecutive/repeated paragraphs from text and clean encoding artifacts."""
    if not text:
        return ""
    text_clean = clean_encoding_artifacts(text)
    paragraphs = [p.strip() for p in text_clean.split("\n\n") if p.strip()]
    seen = []
    for p in paragraphs:
        if "tool_use_id" in p or "toolu_" in p or "data_to_chart" in p or "successfully created" in p:
            continue
        if p not in seen:
            seen.append(p)
    return "\n\n".join(seen)


# Fuzzy keyword -> icon map for standalone header-like lines. Substring match
# (not exact), so "Key Observations", "Component Analysis:", "Executive
# Summary" etc. all resolve without needing every exact phrase listed.
# Icons are chosen to be common, widely-rendered emoji (avoid glyphs like the
# eye emoji that render as an unrelated fallback symbol on some systems).
_HEADER_KEYWORDS = [
    ("root cause", "🧩"),
    ("recommend", "✅"),
    ("next step", "➡️"),
    ("finding", "🔍"),
    ("observation", "👁️"),
    ("insight", "💡"),
    ("downtime", "⏱️"),
    ("summary", "📌"),
    ("trend", "📈"),
    ("impact", "🎯"),
    ("component", "🧱"),
    ("overview", "🗂️"),
    ("analysis", "🧠"),
]

# A line is treated as a standalone header only if, once markdown list/bold
# markers are stripped, the ENTIRE line is just a short label (<=6 words)
# ending optionally in a colon — so it never matches a full sentence.
_SECTION_LINE_RE = re.compile(
    r'^[ \t]*(?:#{1,4}[ \t]*)?[\*\-][ \t]*\**[ \t]*([A-Za-z][A-Za-z \-]{1,45}?)[ \t]*:?[ \t]*\**[ \t]*$'
    r'|^[ \t]*\**[ \t]*([A-Za-z][A-Za-z \-]{1,45}?)[ \t]*:[ \t]*\**[ \t]*$',
    re.IGNORECASE | re.MULTILINE
)

# Any single "X%" or range "X-Y%" / "X% to Y%" value.
_NUM_TOKEN_RE = re.compile(
    r'(?i)(?P<range>\d{1,3}(?:\.\d+)?\s*(?:-|–|to)\s*\d{1,3}(?:\.\d+)?\s*%)'
    r'|(?P<single>\d{1,3}(?:\.\d+)?\s*%)'
)

# Numbers preceded by these words describe a reference/target, not a
# measured value, and should never be badged (e.g. "industry targets of
# 60-85%").
_REFERENCE_CONTEXT_RE = re.compile(r'(?i)(target|goal|industry|benchmark)[^.]{0,20}$')


def _section_replacer(match: "re.Match") -> str:
    label_raw = (match.group(1) or match.group(2) or "").strip()
    if not label_raw or len(label_raw.split()) > 6:
        return match.group(0)
    label_lower = label_raw.lower()
    icon = next((ic for kw, ic in _HEADER_KEYWORDS if kw in label_lower), None)
    if not icon:
        return match.group(0)
    return f'<div class="oee-section-header"><span class="icon">{icon}</span>{label_raw.title()}</div>'


def _format_line(line: str) -> str:
    """Highlight every OEE-style percentage value on a line with a single,
    neutral badge style — no color-coding and no comparison against any
    target. Reference values ("industry targets of 60-85%") are skipped.
    """
    out_parts = []
    last_end = 0
    for m in _NUM_TOKEN_RE.finditer(line):
        out_parts.append(line[last_end:m.start()])
        last_end = m.end()

        matched_text = m.group("range") or m.group("single")
        if _REFERENCE_CONTEXT_RE.search(line[:m.start()]):
            out_parts.append(matched_text)
        else:
            out_parts.append(f'<span class="oee-badge oee-badge-value">{matched_text}</span>')

    out_parts.append(line[last_end:])
    return "".join(out_parts)


def format_oee_markdown(text: str) -> str:
    """Post-process agent markdown for display: turns short standalone label
    lines into icon section headers, and gives every OEE/Availability/
    Performance/Quality-style percentage a single neutral highlight badge.

    This does NOT compare values against any target or threshold, and does
    not color-code by pass/fail — it's a plain visual highlight only.
    Reference values ("industry targets of 60-85%") are left unbadged.

    Output contains inline HTML and must be rendered with
    st.markdown(result, unsafe_allow_html=True).
    """
    if not text:
        return text

    lines = text.split("\n")
    out_lines = []
    for line in lines:
        header_match = _SECTION_LINE_RE.match(line)
        if header_match:
            out_lines.append(_section_replacer(header_match))
            continue
        out_lines.append(_format_line(line))

    return "\n".join(out_lines)


def get_agent_auth_config() -> Tuple[Optional[str], Optional[str]]:
    """Retrieve Snowflake Host and Token for Cortex Agent REST API calls.

    Supports:

    1. Container Runtime native OAuth token mounted at /snowflake/session/token.
    2. Environment variable SNOWFLAKE_HOST.
    3. Snowpark session token fallback.
    """
    try:
        snowflake_host = os.environ.get("SNOWFLAKE_HOST")

        session = get_snowflake_session()
        if not snowflake_host and session is not None:
            try:
                snowflake_host = session.connection.host
            except Exception:
                try:
                    snowflake_host = session.connection.rest.host
                except Exception:
                    pass

        token = None
        token_path = "/snowflake/session/token"
        if os.path.exists(token_path):
            try:
                with open(token_path, "r") as f:
                    token = f.read().strip()
            except Exception as e:
                logger.warning(f"Unable to read container token at {token_path}: {e}")

        if not token and session is not None:
            try:
                token = session.connection._conn._token
            except Exception:
                try:
                    token = session.connection.rest.token
                except Exception:
                    pass

        return snowflake_host, token

    except Exception as e:
        logger.warning(f"Unable to retrieve Snowflake session or host for Cortex Agent: {e}")
        return None, None


def call_agent(messages: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
    """POSTs to /api/v2/cortex/agent:run with stream=True, reads SSE stream, logs event types and payloads, yields structured event dicts."""
    snowflake_host, token = get_agent_auth_config()

    if not snowflake_host or not token:
        logger.error("Snowflake host or token missing. Cannot call Cortex Agent API.")
        yield {
            "event": "response.text.delta",
            "data": {
                "text": "❌ **Error**: Snowflake credentials or session token unavailable. Please check your Snowflake connection settings."
            }
        }
        return

    agent_endpoint = f"https://{snowflake_host}/api/v2/cortex/agent:run"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "OAUTH",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    # Dynamic settings retrieval
    history_limit = st.session_state.get("settings_history_count", 10)
    truncated_messages = messages[-history_limit:] if history_limit and len(messages) > history_limit else messages

    formatted_api_messages = []
    for m in truncated_messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, str):
            formatted_api_messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            formatted_api_messages.append({"role": role, "content": content})

    semantic_view = st.session_state.get("settings_semantic_view") or os.environ.get("SEMANTIC_VIEW", "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS")
    warehouse_name = st.session_state.get("settings_warehouse_name") or "WH_APPS"
    analyst_tool_name = st.session_state.get("settings_analyst_tool_name") or "traksys_analyst"
    orchestration_model = st.session_state.get("settings_orchestration_model") or "claude-sonnet-4-5"

    payload = {
        "models": {"orchestration": orchestration_model},
        "messages": formatted_api_messages,
        "tools": [
            {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": analyst_tool_name}},
            {"tool_spec": {"type": "sql_exec", "name": "sql_exec"}},
            {"tool_spec": {"type": "data_to_chart", "name": "data_to_chart"}},
        ],
        "tool_resources": {
            analyst_tool_name: {
                "semantic_view": semantic_view,
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": warehouse_name
                }
            }
        },
    }

    try:
        resp = requests.post(agent_endpoint, headers=headers, json=payload, stream=True, timeout=60)
        resp.raise_for_status()

        current_event = None
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue

            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
                continue

            if line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    logger.info("Cortex Agent SSE stream finished: [DONE]")
                    break
                try:
                    data_obj = json.loads(data_str)
                    logger.info(f"Cortex Agent SSE Event: type='{current_event}', data={json.dumps(data_obj)}")
                    yield {
                        "event": current_event,
                        "data": data_obj
                    }
                except json.JSONDecodeError:
                    logger.debug(f"Raw non-JSON data line: {data_str}")
                    continue

    except Exception as req_err:
        logger.error(f"Cortex Agent API request failed: {req_err}.")
        yield {
            "event": "error",
            "data": {
                "text": f"❌ **Cortex Agent Error**: {req_err}"
            }
        }


def collect_response(events: Generator[Dict[str, Any], None, None]) -> List[Dict[str, Any]]:
    """Merge streaming deltas into a list of finished, ordered content blocks.

    Filter out thinking/reasoning/planning events (`response.thinking`, etc.) and process strictly:
    - `response.text.delta` (for answer text)
    - `response.table` / `response.tool_results` (for data tables)
    - `response.chart` (for Vega/Plotly charts)
    - `response.suggested_queries` (for follow-up questions)
    """
    text_buf = ""
    blocks = []
    seen_chart_specs = set()
    suggested_queries_list = []

    for evt_wrapper in events:
        evt_type = str(evt_wrapper.get("event", ""))
        data = evt_wrapper.get("data", {})
        if not isinstance(data, dict):
            continue

        # Ignore thinking, reasoning, status, or system planning events
        if "thinking" in evt_type.lower() or "reasoning" in evt_type.lower() or data.get("type") in ("thinking", "response.thinking"):
            continue

        status = data.get("status") or (data.get("data", {}).get("status") if isinstance(data.get("data"), dict) else None)
        if status in ("planning", "reevaluating_plan"):
            text_buf = ""
            blocks = [b for b in blocks if b["type"] != "text"]
            continue

        # Skip system agentic metadata
        if data.get("type") == "system_agentic_semantic_context":
            continue

        # Skip tool results that contain internal metadata (e.g. custom_instructions)
        if "content" in data and isinstance(data["content"], list):
            inner = data["content"]
            if inner and isinstance(inner[0], dict):
                j = inner[0].get("json", {})
                if "custom_instructions" in j:
                    continue

        # --- Extract response.suggested_queries ---
        if evt_type == "response.suggested_queries" or "suggested_queries" in data or "suggestions" in data:
            sq_items = data.get("suggested_queries") or data.get("suggestions") or data.get("data", {}).get("suggested_queries")
            if isinstance(sq_items, list):
                for sq in sq_items:
                    q_str = sq.get("query") if isinstance(sq, dict) else str(sq)
                    if q_str and q_str not in suggested_queries_list:
                        suggested_queries_list.append(clean_encoding_artifacts(q_str))

        # --- Extract Text Delta strictly for response.text.delta ---
        delta_text = None

        if evt_type in ("response.text.delta", "text.delta", "message.delta"):
            delta_text = data.get("text") or data.get("delta", {}).get("text")
            if not delta_text and isinstance(data.get("delta"), dict):
                content_arr = data.get("delta", {}).get("content", [])
                for item in content_arr:
                    if item.get("type") == "text":
                        delta_text = (delta_text or "") + item.get("text", "")

        elif evt_type == "response.text" or ("text" in data and "content_index" in data):
            delta_text = data.get("text")

        if delta_text:
            delta_clean = clean_encoding_artifacts(delta_text)
            if any(term in delta_clean for term in ("Present the table", "Looking at the data again:", "Now I need to:", "tool_use_id", "toolu_", "data_to_chart")):
                text_buf = ""
            else:
                text_buf += delta_clean

        # --- Extract Tool Results / Data strictly for response.table / response.tool_results ---
        is_tool_res = (
            evt_type in ("response.table", "response.tool_results", "tool_results") or
            "result_set" in data or
            "query_id" in data or
            "statement_handle" in data
        )
        if is_tool_res:
            if text_buf:
                cleaned_text = deduplicate_paragraphs(text_buf)
                if cleaned_text:
                    blocks.append({"type": "text", "text": cleaned_text})
                text_buf = ""

            tool_content = data.get("content") or [{"json": data}]
            blocks.append({
                "type": "tool_results",
                "content": tool_content
            })

        # --- Extract Chart strictly for response.chart ---
        chart_spec = (
            data.get("chart_spec") or
            data.get("chart", {}).get("chart_spec") or
            (data.get("delta", {}).get("chart", {}).get("chart_spec") if isinstance(data.get("delta"), dict) else None) or
            (data.get("spec") if "chart" in evt_type.lower() or "chart" in data else None)
        )
        if chart_spec and (evt_type in ("response.chart", "chart") or "chart" in evt_type.lower() or "chart_spec" in data or "chart" in data):
            spec_key = str(chart_spec)
            if spec_key not in seen_chart_specs:
                seen_chart_specs.add(spec_key)
                if text_buf:
                    cleaned_text = deduplicate_paragraphs(text_buf)
                    if cleaned_text:
                        blocks.append({"type": "text", "text": cleaned_text})
                    text_buf = ""
                blocks.append({"type": "chart", "spec": chart_spec})

    if text_buf:
        final_clean = deduplicate_paragraphs(text_buf)
        if final_clean:
            blocks.append({"type": "text", "text": final_clean})

    # Add suggested queries block if available
    if suggested_queries_list:
        blocks.append({
            "type": "suggested_queries",
            "queries": suggested_queries_list
        })

    # Fallback chart generation ONLY if no chart block exists
    has_chart = any(b.get("type") == "chart" for b in blocks)
    if not has_chart:
        for b in blocks:
            if b.get("type") == "tool_results":
                df = tool_results_to_df(b.get("content"))
                if df is not None and isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) >= 2:
                    try:
                        from visualization.chart_generator import generate_chart
                        chart_res = generate_chart("OEE Analytics Chart", df)
                        if chart_res and chart_res.should_visualize and chart_res.figure:
                            blocks.append({"type": "chart", "figure": chart_res.figure})
                            break
                    except Exception as e_chart:
                        logger.warning(f"Automatic chart fallback generation failed: {e_chart}")

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

        qid = j.get("query_id") or j.get("statement_handle")
        if qid and session is not None:
            try:
                return session.sql(f"SELECT * FROM TABLE(RESULT_SCAN('{qid}'))").to_pandas()
            except Exception as e:
                logger.warning(f"RESULT_SCAN for query_id '{qid}' failed: {e}")

        rs = j.get("result_set") or j.get("data", {}).get("result_set")
        if rs and isinstance(rs, dict):
            try:
                row_type = rs.get("resultSetMetaData", {}).get("rowType", [])
                cols = [col["name"] for col in row_type] if row_type else None
                data_rows = rs.get("data", [])
                if cols:
                    return pd.DataFrame(data_rows, columns=cols)
                elif data_rows:
                    return pd.DataFrame(data_rows)
            except Exception as e_rs:
                logger.warning(f"Parsing inline result_set failed: {e_rs}")

        if "dataframe" in j and isinstance(j["dataframe"], pd.DataFrame):
            return j["dataframe"]

    return None


def render_chart(spec_or_fig: Any, df: Optional[pd.DataFrame] = None, key: Optional[str] = None):
    """Render a chart (Vega-Lite spec, Plotly figure, or self-contained spec) via Streamlit with multi-color palettes and hover animations."""
    if spec_or_fig is None:
        return

    # Path A: Plotly Figure Object
    if hasattr(spec_or_fig, "update_layout") or hasattr(spec_or_fig, "data"):
        try:
            st.plotly_chart(spec_or_fig, use_container_width=True, key=key)
            return
        except Exception as e_plotly:
            logger.warning(f"Plotly chart rendering failed: {e_plotly}")

    # Path B: Vega-Lite Chart Spec (string or dict)
    spec_str = spec_or_fig
    try:
        spec = json.loads(spec_str) if isinstance(spec_str, str) else spec_str
    except Exception as parse_err:
        st.error(f"Failed to parse chart spec JSON: {parse_err}")
        return

    if isinstance(spec, dict):
        # 1. Dimensions & padding configuration
        spec["width"] = "container"
        spec["height"] = 340
        spec["padding"] = {"left": 10, "right": 10, "top": 5, "bottom": 10}
        spec["autosize"] = {"type": "fit-x", "contains": "padding"}

        # Title alignment & styling
        if "title" in spec:
            if isinstance(spec["title"], str):
                spec["title"] = {
                    "text": spec["title"],
                    "anchor": "start",
                    "offset": 8,
                    "fontSize": 15,
                    "font": "Poppins, sans-serif",
                    "color": "#242B6B"
                }
            elif isinstance(spec["title"], dict):
                spec["title"]["anchor"] = "start"
                spec["title"]["offset"] = 8
                spec["title"]["fontSize"] = 15
                spec["title"]["font"] = "Poppins, sans-serif"
                spec["title"]["color"] = "#242B6B"

        # 2. Add mouseover hover selection parameter
        params = spec.get("params", [])
        has_hover = any(p.get("name") in ("hover", "grid") for p in params if isinstance(p, dict))
        if not has_hover:
            params.append({
                "name": "hover",
                "select": {"type": "point", "on": "mouseover", "clear": "mouseout"}
            })
            spec["params"] = params

        encoding = spec.get("encoding", {})
        if isinstance(encoding, dict):
            # Enforce multi-color palette for bar / pie / categorical charts
            x_enc = encoding.get("x", {})
            cat_field = x_enc.get("field") if isinstance(x_enc, dict) else None

            # If color encoding is missing OR set to a single fixed color value, force categorical color mapping by x-axis field
            color_enc = encoding.get("color")
            is_single_color = False
            if isinstance(color_enc, dict) and "value" in color_enc:
                is_single_color = True

            if (color_enc is None or is_single_color) and cat_field:
                encoding["color"] = {
                    "field": cat_field,
                    "type": "nominal",
                    "legend": {"orient": "right", "title": str(cat_field).replace("_", " ").title()},
                    "scale": {"range": ["#242B6B", "#E15241", "#A63A96", "#E0A438", "#3B4394", "#171C4A", "#28A745"]}
                }

            y_enc = encoding.get("y")
            if isinstance(y_enc, dict):
                scale_cfg = y_enc.get("scale", {})
                if not isinstance(scale_cfg, dict):
                    scale_cfg = {}
                scale_cfg.setdefault("zero", False)
                y_enc["scale"] = scale_cfg

            if "tooltip" not in encoding:
                tooltip_channels = []
                for channel, ch_cfg in encoding.items():
                    if isinstance(ch_cfg, dict) and "field" in ch_cfg:
                        tooltip_channels.append({
                            "field": ch_cfg["field"],
                            "type": ch_cfg.get("type", "nominal"),
                            "title": ch_cfg.get("title", ch_cfg["field"])
                        })
                if tooltip_channels:
                    encoding["tooltip"] = tooltip_channels

            # Add pop-out hover animations (opacity, strokeWidth, size)
            mark = spec.get("mark")
            mark_type = mark if isinstance(mark, str) else (mark.get("type", "bar") if isinstance(mark, dict) else "bar")

            mark_dict = mark if isinstance(mark, dict) else {"type": mark_type}
            mark_dict["tooltip"] = True
            mark_dict["cursor"] = "pointer"

            if mark_type in ("bar", "arc", "rect"):
                mark_dict["opacity"] = {"condition": {"param": "hover", "value": 1.0}, "value": 0.65}
                mark_dict["stroke"] = "#171C4A"
                mark_dict["strokeWidth"] = {"condition": {"param": "hover", "value": 2.5}, "value": 0}
            elif mark_type in ("point", "line", "area", "circle", "square"):
                mark_dict["point"] = {
                    "size": {"condition": {"param": "hover", "value": 120}, "value": 40},
                    "filled": True
                }
                mark_dict["opacity"] = {"condition": {"param": "hover", "value": 1.0}, "value": 0.75}

            spec["mark"] = mark_dict

    if isinstance(spec, dict) and "data" in spec:
        st.vega_lite_chart(spec, use_container_width=True, key=key)
    elif df is not None and not df.empty:
        st.vega_lite_chart(df, spec, use_container_width=True, key=key)
    elif isinstance(spec, dict):
        st.vega_lite_chart(spec, use_container_width=True, key=key)
    else:
        st.warning("Chart spec received but no data to plot.")
