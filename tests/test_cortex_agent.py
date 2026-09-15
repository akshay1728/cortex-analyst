"""Unit tests for Cortex Agent Integration Service."""

import json
import pytest
import pandas as pd
from services.cortex_agent import call_agent, collect_response, tool_results_to_df, get_agent_auth_config, split_suggestions

def test_get_agent_auth_config():
    host, token = get_agent_auth_config()
    # Expect strings or None gracefully
    assert host is None or isinstance(host, str)
    assert token is None or isinstance(token, str)

def test_call_agent_missing_auth_error():
    messages = [{"role": "user", "content": [{"type": "text", "text": "Show OEE by plant"}]}]
    events = list(call_agent(messages))
    assert len(events) >= 1

    blocks = collect_response(events)
    assert len(blocks) >= 1

    assert blocks[0]["type"] == "text"
    assert "Snowflake credentials or session token unavailable" in blocks[0]["text"]

def test_tool_results_to_df_inline():
    tool_results = [
        {
            "json": {
                "result_set": {
                    "resultSetMetaData": {"rowType": [{"name": "Plant"}, {"name": "OEE"}]},
                    "data": [["Bethlehem", 85.5], ["York", 78.2]]
                }
            }
        }
    ]
    df = tool_results_to_df(tool_results)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["Plant", "OEE"]

def test_split_suggestions():
    text_with_sug = "Analysis complete.\n\n[SUGGESTIONS]\n- What is the OEE for Line 1?\n* Show downtime by cause"
    main, sugs = split_suggestions(text_with_sug)
    assert main == "Analysis complete."
    assert len(sugs) == 2
    assert sugs[0] == "What is the OEE for Line 1?"
    assert sugs[1] == "Show downtime by cause"

    text_no_sug = "Analysis without suggestions."
    main_plain, sugs_plain = split_suggestions(text_no_sug)
    assert main_plain == "Analysis without suggestions."
    assert sugs_plain == []

def test_collect_response_buffering():
    raw_events = [
        {"event": "response.text.delta", "data": {"text": "Hello "}},
        {"event": "response.text.delta", "data": {"text": "world!"}},
        {"event": "response.chart", "data": {"chart_spec": "{}"}},
    ]
    blocks = collect_response(raw_events)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "Hello world!"
    assert blocks[1]["type"] == "chart"
