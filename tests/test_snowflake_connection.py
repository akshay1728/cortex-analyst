"""Unit tests for Smart Snowflake Connection module."""

import pytest
from unittest.mock import MagicMock, patch
import services.snowflake_connection as sf_conn

def test_snowflake_connection_local_secrets():
    mock_conn = MagicMock()
    mock_session = MagicMock()
    mock_conn.session = mock_session

    mock_st = MagicMock()
    mock_st.secrets.get.side_effect = lambda k: {"account": "test"} if k == "snowflake" else None
    mock_st.connection.return_value = mock_conn

    with patch.dict("sys.modules", {"streamlit": mock_st}):
        session = sf_conn.get_snowflake_session()
        assert session == mock_session
        mock_st.connection.assert_called_once_with("snowflake")

def test_snowflake_connection_sis_active_session():
    mock_st = MagicMock()
    mock_st.secrets.get.return_value = None

    mock_sis_session = MagicMock()
    mock_snowpark = MagicMock()
    mock_snowpark.context.get_active_session.return_value = mock_sis_session

    mock_snowflake = MagicMock()
    mock_snowflake.snowpark = mock_snowpark

    with patch.dict("sys.modules", {
        "streamlit": mock_st,
        "snowflake": mock_snowflake,
        "snowflake.snowpark": mock_snowpark,
        "snowflake.snowpark.context": mock_snowpark.context
    }):
        session = sf_conn.get_snowflake_session()
        assert session == mock_sis_session

def test_snowflake_connection_fallback_offline():
    mock_st = MagicMock()
    mock_st.secrets.get.return_value = None

    with patch.dict("sys.modules", {"streamlit": mock_st}):
        session = sf_conn.get_snowflake_session()
        assert session is None
