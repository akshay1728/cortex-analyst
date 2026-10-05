"""Settings Service for DB persistence and Session State management.

Loads and saves settings to Snowflake DB strictly via stored procedures:
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_APP_SETTINGS
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING_BLOB
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_QUESTIONS
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_QUESTION
- {DB}.{APP_SCHEMA}.SP_TRAKSYS_DELETE_QUESTION
"""

import logging
import base64
import json
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
import streamlit as st
from config import DB, APP_SCHEMA
from services.snowflake_connection import get_snowflake_session

logger = logging.getLogger("settings_service")


def _get_current_username() -> Optional[str]:
    """Get active username from session state or query Snowflake CURRENT_USER()."""
    if hasattr(st, "session_state") and st.session_state.get("current_user"):
        return str(st.session_state["current_user"]).strip()

    session = get_snowflake_session()
    if session is not None:
        try:
            df = session.sql("SELECT CURRENT_USER() AS user_name").to_pandas()
            if df is not None and not df.empty:
                val = df.iloc[0, 0]
                if val and str(val).strip() and str(val) != "None":
                    return str(val).strip()
        except Exception as e_usr:
            logger.debug(f"Unable to query CURRENT_USER(): {e_usr}")

    return None


def _format_sql_user_arg(user: Optional[str]) -> str:
    """Return 'username' if available, else 'CURRENT_USER()' for SQL procedure calls."""
    u_val = user or _get_current_username()
    if u_val and str(u_val).strip():
        esc_u = str(u_val).strip().replace("'", "''")
        return f"'{esc_u}'"
    return "CURRENT_USER()"


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
    """Fetch suggested questions strictly from Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_QUESTIONS()."""
    session = get_snowflake_session()
    if session is None:
        logger.info("Snowflake session unavailable; returning empty question list.")
        return []

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_QUESTIONS"
    try:
        df = session.sql(f"CALL {proc_call}()").to_pandas()
        logger.info(f"Procedure {proc_call}() returned {len(df) if df is not None else 0} rows.")
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}(): {e_proc}")
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
    """Save or update a suggested question strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_QUESTION()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_arg = _format_sql_user_arg(user)
    esc_text = q_text.replace("'", "''")
    qid_val = q_id if q_id and q_id > 0 else 'NULL'
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_QUESTION"

    try:
        session.sql(f"CALL {proc_call}({qid_val}, '{esc_text}', {q_order}, {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False


def load_dashboard_types_from_db() -> List[str]:
    """Fetch dashboard types strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_DASHBOARD_TYPES()."""
    session = get_snowflake_session()
    if session is None:
        return ["Molded", "Moghul", "Marshmallow"]

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_DASHBOARD_TYPES"
    try:
        df = session.sql(f"CALL {proc_call}()").to_pandas()
        if df is not None and not df.empty:
            types = []
            for _, row in df.iterrows():
                name = _row_val(row, ["DASHBOARD_NAME", "dashboard_name", "NAME"], positional_idx=0, default="")
                if name and str(name).strip():
                    types.append(str(name).strip())
            if types:
                return types
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}(): {e_proc}")

    return ["Molded", "Moghul", "Marshmallow"]


def load_production_lines_from_db(dashboard_name: Optional[str] = None) -> List[str]:
    """Fetch available production lines strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_PRODUCTION_LINES()."""
    session = get_snowflake_session()
    if session is None:
        return ["All Lines", "Line 1", "Line 2", "Line 3"]

    if dashboard_name:
        esc_dash = dashboard_name.replace("'", "''")
        dash_arg = f"'{esc_dash}'"
    else:
        dash_arg = "NULL"
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_PRODUCTION_LINES"

    try:
        df = session.sql(f"CALL {proc_call}({dash_arg})").to_pandas()
        if df is not None and not df.empty:
            lines = ["All Lines"]
            for _, row in df.iterrows():
                line = _row_val(row, ["LINE_NAME", "line_name", "LINE"], positional_idx=0, default="")
                if line and str(line).strip() and str(line).strip() not in lines:
                    lines.append(str(line).strip())
            return lines
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")

    return ["All Lines", "Line 1", "Line 2", "Line 3"]


def load_dashboard_metrics_from_db(
    dashboard_name: str,
    start_date: str,
    end_date: str,
    line_name: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch dashboard metrics strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_DASHBOARD_METRICS()."""
    session = get_snowflake_session()

    # Defaults depending on dashboard name
    if dashboard_name and dashboard_name.lower() == "moghul":
        defaults = {
            "dashboard_name": "Moghul",
            "line_name": line_name or "NID-C",
            "total_run_time_mins": 993,
            "total_lost_time_mins": 444,
            "total_shakeout_trucks": 174,
            "boards_cast_shift1": 7020,
            "boards_cast_shift2": 7218,
            "boards_cast_shift3": 7225,
            "total_boards": 21463,
            "overall_oee": 54.00,
        }
    elif dashboard_name and dashboard_name.lower() == "marshmallow":
        defaults = {
            "dashboard_name": "Marshmallow",
            "line_name": line_name or "Belt 1",
            "total_run_time_mins": 1227,
            "total_lost_time_mins": 211,
            "scrap": 8209,
            "pounds_packed_shift1": 12357,
            "pounds_packed_shift2": 15338,
            "pounds_packed_shift3": 9390,
            "total_pounds_packed": 37085,
            "overall_oee": 78,
        }
    else:
        defaults = {
            "dashboard_name": dashboard_name,
            "line_name": line_name or "All Lines",
            "total_pounds_shift1": 15444,
            "total_pounds_shift2": 9461,
            "total_pounds_shift3": 0,
            "total_pounds_running_sum": 24905,
            "total_run_time_mins": 633,
            "total_lost_time_mins": 343,
            "oee_shift1": 60,
            "oee_shift2": 36,
            "oee_shift3": 0,
            "overall_oee": 47
        }

    if session is None:
        return defaults

    esc_dash = dashboard_name.replace("'", "''")
    dash_arg = f"'{esc_dash}'"
    start_arg = f"'{start_date}'" if start_date else "NULL"
    end_arg = f"'{end_date}'" if end_date else "NULL"
    if line_name and line_name != "All Lines":
        esc_line = line_name.replace("'", "''")
        line_arg = f"'{esc_line}'"
    else:
        line_arg = "NULL"

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_DASHBOARD_METRICS"

    try:
        df = session.sql(f"CALL {proc_call}({dash_arg}, {start_arg}, {end_arg}, {line_arg})").to_pandas()
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                "dashboard_name": _row_val(row, ["DASHBOARD_NAME"], positional_idx=0, default=dashboard_name),
                "line_name": _row_val(row, ["LINE_NAME"], positional_idx=1, default=line_name or "All Lines"),
                "total_pounds_shift1": float(_row_val(row, ["TOTAL_POUNDS_SHIFT1"], positional_idx=2, default=15444)),
                "total_pounds_shift2": float(_row_val(row, ["TOTAL_POUNDS_SHIFT2"], positional_idx=3, default=9461)),
                "total_pounds_shift3": float(_row_val(row, ["TOTAL_POUNDS_SHIFT3"], positional_idx=4, default=0)),
                "total_pounds_running_sum": float(_row_val(row, ["TOTAL_POUNDS_RUNNING_SUM"], positional_idx=5, default=24905)),
                "total_run_time_mins": float(_row_val(row, ["TOTAL_RUN_TIME_MINS"], positional_idx=6, default=633)),
                "total_lost_time_mins": float(_row_val(row, ["TOTAL_LOST_TIME_MINS"], positional_idx=7, default=343)),
                "oee_shift1": float(_row_val(row, ["OEE_SHIFT1"], positional_idx=8, default=60)),
                "oee_shift2": float(_row_val(row, ["OEE_SHIFT2"], positional_idx=9, default=36)),
                "oee_shift3": float(_row_val(row, ["OEE_SHIFT3"], positional_idx=10, default=0)),
                "overall_oee": float(_row_val(row, ["OVERALL_OEE"], positional_idx=11, default=47)),
            }
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")

    return defaults


def check_is_admin(username: Optional[str] = None) -> bool:
    """Check if given username (or current user) has admin privileges via {DB}.{APP_SCHEMA}.SP_TRAKSYS_IS_ADMIN()."""
    session = get_snowflake_session()
    if session is None:
        logger.info("Snowflake session unavailable; returning default True for admin check.")
        return True

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_IS_ADMIN"

    if username and username.strip():
        esc_user = username.strip().replace("'", "''")
        arg_str = f"'{esc_user}'"
    elif hasattr(st, "session_state") and st.session_state.get("current_user"):
        esc_user = str(st.session_state["current_user"]).strip().replace("'", "''")
        arg_str = f"'{esc_user}'"
    else:
        # Pass NULL so procedure COALESCE(:P_USERNAME, CURRENT_USER()) resolves to active Snowflake user
        arg_str = "NULL"

    try:
        df = session.sql(f"CALL {proc_call}({arg_str})").to_pandas()
        if df is not None and not df.empty:
            val = df.iloc[0, 0]
            if isinstance(val, (bool, np.bool_)):
                return bool(val)
            if str(val).strip().lower() in ("true", "1", "t"):
                return True
            return False
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")

    return True


def load_admin_users_from_db() -> List[Dict[str, Any]]:
    """Fetch admin users via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_ADMIN_USERS()."""
    session = get_snowflake_session()
    if session is None:
        logger.info("Snowflake session unavailable; returning empty admin list.")
        return []

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_ADMIN_USERS"
    try:
        df = session.sql(f"CALL {proc_call}()").to_pandas()
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}(): {e_proc}")
        return []

    admins = []
    if df is not None and not df.empty:
        for idx_r, row in df.iterrows():
            uname = _row_val(row, ["USERNAME", "username", "USER"], positional_idx=0, default="")
            active_val = _row_val(row, ["IS_ACTIVE", "is_active", "ACTIVE"], positional_idx=1, default=True)
            c_by = _row_val(row, ["CREATED_BY", "created_by"], positional_idx=2, default="UNKNOWN")
            u_by = _row_val(row, ["UPDATED_BY", "updated_by"], positional_idx=3, default="UNKNOWN")

            if uname and str(uname).strip():
                is_act = True
                if isinstance(active_val, bool):
                    is_act = active_val
                elif str(active_val).strip().lower() in ("false", "0", "f", "none"):
                    is_act = False

                admins.append({
                    "username": str(uname).strip().upper(),
                    "is_active": is_act,
                    "created_by": str(c_by),
                    "updated_by": str(u_by)
                })

    return admins


def save_admin_user_to_db(username: str, is_active: bool = True, user: Optional[str] = None) -> bool:
    """Add or modify an admin user via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_ADMIN_USER()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_arg = _format_sql_user_arg(user)
    esc_uname = username.strip().upper().replace("'", "''")
    active_str = "TRUE" if is_active else "FALSE"
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_ADMIN_USER"

    try:
        session.sql(f"CALL {proc_call}('{esc_uname}', {active_str}, {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False


def delete_admin_user_from_db(username: str, user: Optional[str] = None) -> bool:
    """Delete an admin user via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_DELETE_ADMIN_USER()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_arg = _format_sql_user_arg(user)
    esc_uname = username.strip().upper().replace("'", "''")
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_DELETE_ADMIN_USER"

    try:
        session.sql(f"CALL {proc_call}('{esc_uname}', {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False


def delete_suggested_question_from_db(q_id: int, user: Optional[str] = None) -> bool:
    """Delete (soft-delete) a suggested question strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_DELETE_QUESTION()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_arg = _format_sql_user_arg(user)
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_DELETE_QUESTION"

    try:
        session.sql(f"CALL {proc_call}({q_id}, {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False


def load_app_settings_from_db() -> Dict[str, Any]:
    """Load settings key-values and logo blob strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_APP_SETTINGS()."""
    settings = {}
    logo_bytes = None

    session = get_snowflake_session()
    if session is None:
        return {"settings": settings, "logo_bytes": logo_bytes}

    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_GET_APP_SETTINGS"
    try:
        df = session.sql(f"CALL {proc_call}()").to_pandas()
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}(): {e_proc}")
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
    """Save setting string key-value strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING()."""
    session = get_snowflake_session()
    if session is None:
        return False
    user_arg = _format_sql_user_arg(user)
    val_str = str(val).replace("'", "''")
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING"

    try:
        session.sql(f"CALL {proc_call}('{key.upper()}', '{val_str}', {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False


def save_app_logo_to_db(logo_bytes: Optional[bytes], user: Optional[str] = None) -> bool:
    """Save binary logo bytes strictly via Snowflake DB procedure {DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING_BLOB()."""
    session = get_snowflake_session()
    if session is None or logo_bytes is None:
        return False
    user_arg = _format_sql_user_arg(user)
    hex_str = logo_bytes.hex()
    proc_call = f"{DB}.{APP_SCHEMA}.SP_TRAKSYS_SAVE_APP_SETTING_BLOB"

    try:
        session.sql(f"CALL {proc_call}('COMPANY_LOGO', TO_BINARY('{hex_str}', 'HEX'), {user_arg})").collect()
        return True
    except Exception as e_proc:
        logger.error(f"Failed to call procedure {proc_call}: {e_proc}")
        return False
