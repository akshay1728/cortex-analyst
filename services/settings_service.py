"""Settings Service for DB persistence and Session State management.

Loads and saves settings to Snowflake DB tables/procedures with CREATED_BY and UPDATED_BY audit columns:
- APP_SETTINGS / PROC_GET_APP_SETTINGS / PROC_SAVE_APP_SETTING / PROC_SAVE_APP_SETTING_BLOB
- APP_SUGGESTED_QUESTIONS / PROC_GET_SUGGESTED_QUESTIONS / PROC_SAVE_SUGGESTED_QUESTION / PROC_DELETE_SUGGESTED_QUESTION
"""

import logging
import base64
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st
from services.snowflake_connection import get_snowflake_session

logger = logging.getLogger("settings_service")

DEFAULT_SUGGESTED_QUESTIONS = [
    "What is our overall OEE trend over time?",
    "Compare OEE by plant",
    "Which line has the highest downtime?",
    "What are the top downtime causes?",
    "Show quality rate by product family",
    "Show breakdown of good vs defective units"
]

DEFAULT_SETTINGS = {
    "header_title": "OEE AI Assistant",
    "header_subtitle": "Ask natural language questions about plant performance, equipment availability, line productivity, and downtime root causes — powered by Cortex Analyst.",
    "pdf_filename_template": "OEE_Conversation_Report_{YYYYMMDD}.pdf",
    "semantic_view": "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS",
    "warehouse_name": "WH_APPS",
    "analyst_tool_name": "traksys_analyst",
    "orchestration_model": "claude-sonnet-4-5",
    "history_count": 10,
    "oee_target": 85.0,
    "availability_target": 90.0,
    "performance_target": 95.0,
    "quality_target": 99.0
}


def _get_current_username() -> str:
    """Get active username or default string."""
    if hasattr(st, "session_state") and "current_user" in st.session_state and st.session_state["current_user"]:
        return str(st.session_state["current_user"])
    return "APP_USER"


def load_suggested_questions_from_db() -> List[Dict[str, Any]]:
    """Fetch suggested questions from Snowflake DB or return defaults."""
    session = get_snowflake_session()
    if session is None:
        return [{"id": i+1, "text": q, "order": i+1, "created_by": "DEFAULT", "updated_by": "DEFAULT"} for i, q in enumerate(DEFAULT_SUGGESTED_QUESTIONS)]

    try:
        df = session.sql("CALL PROC_GET_SUGGESTED_QUESTIONS()").to_pandas()
        if df is not None and not df.empty:
            questions = []
            for _, row in df.iterrows():
                questions.append({
                    "id": int(row.get("QUESTION_ID", 0)),
                    "text": str(row.get("QUESTION_TEXT", "")),
                    "order": int(row.get("DISPLAY_ORDER", 0)),
                    "created_by": str(row.get("CREATED_BY", "UNKNOWN")),
                    "updated_by": str(row.get("UPDATED_BY", "UNKNOWN"))
                })
            if questions:
                return questions
    except Exception:
        try:
            df = session.sql("SELECT QUESTION_ID, QUESTION_TEXT, DISPLAY_ORDER, CREATED_BY, UPDATED_BY FROM APP_SUGGESTED_QUESTIONS WHERE IS_ACTIVE = TRUE ORDER BY DISPLAY_ORDER ASC, QUESTION_ID ASC").to_pandas()
            if df is not None and not df.empty:
                questions = []
                for _, row in df.iterrows():
                    questions.append({
                        "id": int(row.get("QUESTION_ID", 0)),
                        "text": str(row.get("QUESTION_TEXT", "")),
                        "order": int(row.get("DISPLAY_ORDER", 0)),
                        "created_by": str(row.get("CREATED_BY", "UNKNOWN")),
                        "updated_by": str(row.get("UPDATED_BY", "UNKNOWN"))
                    })
                if questions:
                    return questions
        except Exception as e:
            logger.warning(f"Unable to query APP_SUGGESTED_QUESTIONS from DB: {e}")

    return [{"id": i+1, "text": q, "order": i+1, "created_by": "DEFAULT", "updated_by": "DEFAULT"} for i, q in enumerate(DEFAULT_SUGGESTED_QUESTIONS)]


def save_suggested_question_to_db(q_id: Optional[int], q_text: str, q_order: int = 1, user: Optional[str] = None) -> bool:
    """Save or update a suggested question in DB with created_by / updated_by."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    try:
        esc_text = q_text.replace("'", "''")
        esc_user = user_val.replace("'", "''")
        qid_val = q_id if q_id and q_id > 0 else 'NULL'
        session.sql(f"CALL PROC_SAVE_SUGGESTED_QUESTION({qid_val}, '{esc_text}', {q_order}, '{esc_user}')").collect()
        return True
    except Exception:
        try:
            esc_text = q_text.replace("'", "''")
            esc_user = user_val.replace("'", "''")
            if q_id and q_id > 0:
                session.sql(f"UPDATE APP_SUGGESTED_QUESTIONS SET QUESTION_TEXT = '{esc_text}', DISPLAY_ORDER = {q_order}, UPDATED_BY = '{esc_user}', UPDATED_AT = CURRENT_TIMESTAMP() WHERE QUESTION_ID = {q_id}").collect()
            else:
                session.sql(f"INSERT INTO APP_SUGGESTED_QUESTIONS (QUESTION_TEXT, DISPLAY_ORDER, CREATED_BY, UPDATED_BY) VALUES ('{esc_text}', {q_order}, '{esc_user}', '{esc_user}')").collect()
            return True
        except Exception as e:
            logger.error(f"Failed to save suggested question to DB: {e}")
            return False


def delete_suggested_question_from_db(q_id: int, user: Optional[str] = None) -> bool:
    """Delete (soft-delete) a suggested question from DB with updated_by user."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    try:
        session.sql(f"CALL PROC_DELETE_SUGGESTED_QUESTION({q_id}, '{esc_user}')").collect()
        return True
    except Exception:
        try:
            session.sql(f"UPDATE APP_SUGGESTED_QUESTIONS SET IS_ACTIVE = FALSE, UPDATED_BY = '{esc_user}', UPDATED_AT = CURRENT_TIMESTAMP() WHERE QUESTION_ID = {q_id}").collect()
            return True
        except Exception as e:
            logger.error(f"Failed to delete suggested question from DB: {e}")
            return False


def load_app_settings_from_db() -> Dict[str, Any]:
    """Load settings key-values and logo blob from Snowflake DB."""
    settings = dict(DEFAULT_SETTINGS)
    logo_bytes = None

    session = get_snowflake_session()
    if session is None:
        return {"settings": settings, "logo_bytes": logo_bytes}

    try:
        df = session.sql("SELECT SETTING_KEY, SETTING_VALUE, SETTING_BLOB, CREATED_BY, UPDATED_BY FROM APP_SETTINGS").to_pandas()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                key = str(row.get("SETTING_KEY", "")).lower()
                val = row.get("SETTING_VALUE")
                blob = row.get("SETTING_BLOB")

                if key and val is not None and str(val) != "None":
                    val_str = str(val)
                    if key in ("history_count",):
                        try:
                            settings[key] = int(val_str)
                        except ValueError:
                            pass
                    elif key in ("oee_target", "availability_target", "performance_target", "quality_target"):
                        try:
                            settings[key] = float(val_str)
                        except ValueError:
                            pass
                    else:
                        settings[key] = val_str

                if key == "company_logo" and blob is not None:
                    if isinstance(blob, (bytes, bytearray)):
                        logo_bytes = bytes(blob)
                    elif isinstance(blob, str) and blob:
                        try:
                            logo_bytes = base64.b64decode(blob)
                        except Exception:
                            pass

    except Exception as e:
        logger.warning(f"Unable to read APP_SETTINGS from DB: {e}")

    return {"settings": settings, "logo_bytes": logo_bytes}


def save_app_setting_to_db(key: str, val: Any, user: Optional[str] = None) -> bool:
    """Save setting string key-value to Snowflake DB with created_by / updated_by."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    try:
        val_str = str(val).replace("'", "''")
        session.sql(f"CALL PROC_SAVE_APP_SETTING('{key.upper()}', '{val_str}', '{esc_user}')").collect()
        return True
    except Exception:
        try:
            val_str = str(val).replace("'", "''")
            session.sql(f"""
                MERGE INTO APP_SETTINGS t
                USING (SELECT '{key.upper()}' AS k, '{val_str}' AS v, '{esc_user}' AS u) s
                ON t.SETTING_KEY = s.k
                WHEN MATCHED THEN UPDATE SET SETTING_VALUE = s.v, UPDATED_BY = s.u, UPDATED_AT = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (SETTING_KEY, SETTING_VALUE, CREATED_BY, UPDATED_BY, UPDATED_AT) VALUES (s.k, s.v, s.u, s.u, CURRENT_TIMESTAMP())
            """).collect()
            return True
        except Exception as e:
            logger.error(f"Failed to save setting '{key}' to DB: {e}")
            return False


def save_app_logo_to_db(logo_bytes: Optional[bytes], user: Optional[str] = None) -> bool:
    """Save binary logo bytes to APP_SETTINGS in DB with created_by / updated_by."""
    session = get_snowflake_session()
    if session is None or logo_bytes is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    try:
        hex_str = logo_bytes.hex()
        session.sql(f"CALL PROC_SAVE_APP_SETTING_BLOB('COMPANY_LOGO', TO_BINARY('{hex_str}', 'HEX'), '{esc_user}')").collect()
        return True
    except Exception:
        try:
            hex_str = logo_bytes.hex()
            session.sql(f"""
                MERGE INTO APP_SETTINGS t
                USING (SELECT 'COMPANY_LOGO' AS k, TO_BINARY('{hex_str}', 'HEX') AS b, '{esc_user}' AS u) s
                ON t.SETTING_KEY = s.k
                WHEN MATCHED THEN UPDATE SET SETTING_BLOB = s.b, UPDATED_BY = s.u, UPDATED_AT = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (SETTING_KEY, SETTING_BLOB, CREATED_BY, UPDATED_BY, UPDATED_AT) VALUES (s.k, s.b, s.u, s.u, CURRENT_TIMESTAMP())
            """).collect()
            return True
        except Exception as e:
            logger.error(f"Failed to save logo blob to DB: {e}")
            return False
