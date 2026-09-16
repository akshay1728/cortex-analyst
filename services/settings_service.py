"""Settings Service for DB persistence and Session State management.

Loads and saves settings to Snowflake DB strictly via stored procedures:
- {schema}.SP_TRAKSYS_GET_APP_SETTINGS
- {schema}.SP_TRAKSYS_SAVE_APP_SETTING
- {schema}.SP_TRAKSYS_SAVE_APP_SETTING_BLOB
- {schema}.SP_TRAKSYS_GET_QUESTIONS
- {schema}.SP_TRAKSYS_SAVE_QUESTION
- {schema}.SP_TRAKSYS_DELETE_QUESTION
"""

import logging
import base64
import json
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st
from config import get_proc_name
from services.snowflake_connection import get_snowflake_session

logger = logging.getLogger("settings_service")


def _get_current_username() -> str:
    """Get active username or default string."""
    if hasattr(st, "session_state") and "current_user" in st.session_state and st.session_state["current_user"]:
        return str(st.session_state["current_user"])
    return "APP_USER"


def _row_val(row: Any, possible_keys: List[str], positional_idx: Optional[int] = None, default: Any = None) -> Any:
    """Case-insensitive dictionary/Series lookup for DataFrame rows with positional fallback."""
    if row is None:
        return default

    # If row has dictionary/Series keys
    if hasattr(row, "keys"):
        row_keys = {str(k).lower(): k for k in row.keys()}
        for key in possible_keys:
            k_lower = key.lower()
            if k_lower in row_keys:
                actual_key = row_keys[k_lower]
                val = row[actual_key]
                if val is not None and str(val) != "None" and str(val) != "nan":
                    return val

    # Positional fallback for index-based rows
    if positional_idx is not None:
        try:
            if hasattr(row, "iloc"):
                val = row.iloc[positional_idx]
            else:
                val = row[positional_idx]
            if val is not None and str(val) != "None" and str(val) != "nan":
                return val
        except Exception:
            pass

    return default


def load_suggested_questions_from_db() -> List[Dict[str, Any]]:
    """Fetch suggested questions strictly from Snowflake DB procedure SP_TRAKSYS_GET_QUESTIONS()."""
    session = get_snowflake_session()
    if session is None:
        logger.info("Snowflake session unavailable; returning empty question list.")
        return []

    proc_name = get_proc_name("SP_TRAKSYS_GET_QUESTIONS")
    try:
        df = session.sql(f"CALL {proc_name}()").to_pandas()
        logger.info(f"Procedure {proc_name}() returned {len(df) if df is not None else 0} rows.")
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}(): {e_proc}")
        return []

    if df is not None and not df.empty:
        questions = []
        for idx_r, row in df.iterrows():
            if len(df.columns) == 1 and isinstance(row.iloc[0], str):
                try:
                    j_obj = json.loads(row.iloc[0])
                    if isinstance(j_obj, dict):
                        row = j_obj
                except Exception:
                    pass

            q_id = _row_val(row, ["QUESTION_ID", "question_id", "ID"], positional_idx=0, default=idx_r+1)
            q_text = _row_val(row, ["QUESTION_TEXT", "question_text", "TEXT", "QUESTION"], positional_idx=1, default="")
            q_order = _row_val(row, ["DISPLAY_ORDER", "display_order", "ORDER"], positional_idx=2, default=idx_r+1)
            c_by = _row_val(row, ["CREATED_BY", "created_by"], positional_idx=3, default="UNKNOWN")
            u_by = _row_val(row, ["UPDATED_BY", "updated_by"], positional_idx=4, default="UNKNOWN")

            if q_text and str(q_text).strip():
                try:
                    q_id_int = int(q_id)
                except (ValueError, TypeError):
                    q_id_int = idx_r + 1

                try:
                    q_order_int = int(q_order)
                except (ValueError, TypeError):
                    q_order_int = idx_r + 1

                questions.append({
                    "id": q_id_int,
                    "text": str(q_text).strip(),
                    "order": q_order_int,
                    "created_by": str(c_by),
                    "updated_by": str(u_by)
                })

        logger.info(f"Parsed {len(questions)} valid suggested questions from DB procedure.")
        return questions

    return []


def save_suggested_question_to_db(q_id: Optional[int], q_text: str, q_order: int = 1, user: Optional[str] = None) -> bool:
    """Save or update a suggested question strictly via Snowflake DB procedure SP_TRAKSYS_SAVE_QUESTION()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    esc_text = q_text.replace("'", "''")
    esc_user = user_val.replace("'", "''")
    qid_val = q_id if q_id and q_id > 0 else 'NULL'
    proc_name = get_proc_name("SP_TRAKSYS_SAVE_QUESTION")

    try:
        session.sql(f"CALL {proc_name}({qid_val}, '{esc_text}', {q_order}, '{esc_user}')").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}: {e_proc}")
        return False


def delete_suggested_question_from_db(q_id: int, user: Optional[str] = None) -> bool:
    """Delete (soft-delete) a suggested question strictly via Snowflake DB procedure SP_TRAKSYS_DELETE_QUESTION()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    proc_name = get_proc_name("SP_TRAKSYS_DELETE_QUESTION")

    try:
        session.sql(f"CALL {proc_name}({q_id}, '{esc_user}')").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}: {e_proc}")
        return False


def load_app_settings_from_db() -> Dict[str, Any]:
    """Load settings key-values and logo blob strictly via Snowflake DB procedure SP_TRAKSYS_GET_APP_SETTINGS()."""
    settings = {}
    logo_bytes = None

    session = get_snowflake_session()
    if session is None:
        return {"settings": settings, "logo_bytes": logo_bytes}

    proc_name = get_proc_name("SP_TRAKSYS_GET_APP_SETTINGS")
    try:
        df = session.sql(f"CALL {proc_name}()").to_pandas()
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}(): {e_proc}")
        return {"settings": settings, "logo_bytes": logo_bytes}

    if df is not None and not df.empty:
        for _, row in df.iterrows():
            if len(df.columns) == 1 and isinstance(row.iloc[0], str):
                try:
                    j_obj = json.loads(row.iloc[0])
                    if isinstance(j_obj, dict):
                        row = j_obj
                except Exception:
                    pass

            key_raw = _row_val(row, ["SETTING_KEY", "setting_key", "KEY"], positional_idx=0, default="")
            val_raw = _row_val(row, ["SETTING_VALUE", "setting_value", "VALUE"], positional_idx=1, default=None)
            blob = _row_val(row, ["SETTING_BLOB", "setting_blob", "BLOB"], positional_idx=2, default=None)

            key = str(key_raw).lower() if key_raw else ""

            if key and val_raw is not None and str(val_raw) != "None":
                val_str = str(val_raw)
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

    return {"settings": settings, "logo_bytes": logo_bytes}


def save_app_setting_to_db(key: str, val: Any, user: Optional[str] = None) -> bool:
    """Save setting string key-value strictly via Snowflake DB procedure SP_TRAKSYS_SAVE_APP_SETTING()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    val_str = str(val).replace("'", "''")
    proc_name = get_proc_name("SP_TRAKSYS_SAVE_APP_SETTING")

    try:
        session.sql(f"CALL {proc_name}('{key.upper()}', '{val_str}', '{esc_user}')").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}: {e_proc}")
        return False


def save_app_logo_to_db(logo_bytes: Optional[bytes], user: Optional[str] = None) -> bool:
    """Save binary logo bytes strictly via Snowflake DB procedure SP_TRAKSYS_SAVE_APP_SETTING_BLOB()."""
    session = get_snowflake_session()
    if session is None or logo_bytes is None:
        return False
    user_val = user or _get_current_username()
    esc_user = user_val.replace("'", "''")
    hex_str = logo_bytes.hex()
    proc_name = get_proc_name("SP_TRAKSYS_SAVE_APP_SETTING_BLOB")

    try:
        session.sql(f"CALL {proc_name}('COMPANY_LOGO', TO_BINARY('{hex_str}', 'HEX'), '{esc_user}')").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_name}: {e_proc}")
        return False
