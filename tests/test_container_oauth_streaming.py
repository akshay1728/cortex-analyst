"""Unit tests for Container OAuth token reading and SSE streaming generator."""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from services.snowflake_connection import get_snowflake_token
from services.cortex_ai import CortexAIService

def test_get_snowflake_token_exists():
    mock_token_content = "mock_container_oauth_token_xyz123"
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_token_content)):
            token = get_snowflake_token()
            assert token == mock_token_content

def test_get_snowflake_token_not_exists():
    with patch("os.path.exists", return_value=False):
        token = get_snowflake_token()
        assert token is None

def test_ui_stream_generator_decoupling():
    cortex_ai = CortexAIService()

    mock_chunks = [
        json.dumps({"choices": [{"delta": {"content": "Hello "}}]}),
        json.dumps({"choices": [{"delta": {"content": "world!"}}]}),
        json.dumps({"tool_results": [{"query": "SELECT * FROM oee"}]}),
        "[DONE]"
    ]

    callback_metadata = []

    with patch.object(cortex_ai, "stream_cortex_agent", return_value=mock_chunks):
        streamed_text = list(cortex_ai.ui_stream_generator("test prompt", callback_metadata))
        assert "".join(streamed_text) == "Hello world!"
        assert len(callback_metadata) == 1
        assert callback_metadata[0] == [{"query": "SELECT * FROM oee"}]
