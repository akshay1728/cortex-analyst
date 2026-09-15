"""Smart Snowflake Connection Module.

Supports automatic environment detection for:
1. Container Runtime Native OAuth Token (/snowflake/session/token)
2. Local Streamlit Desktop execution (using st.connection("snowflake") and st.secrets)
3. Streamlit in Snowflake (SiS) execution (using snowflake.snowpark.context.get_active_session())
4. Graceful fallback when running in standalone offline mode.
"""

import os
from typing import Optional, Any
import logging

logger = logging.getLogger("snowflake_connection")

def get_snowflake_token() -> Optional[str]:
    """Reads the local OAuth token embedded in the Snowflake Container Runtime if available.

    Path: /snowflake/session/token
    """
    token_path = "/snowflake/session/token"
    if os.path.exists(token_path):
        try:
            with open(token_path, "r") as f:
                token = f.read().strip()
                if token:
                    logger.info("Found active Snowflake Container Native OAuth Token at %s", token_path)
                    return token
        except Exception as err:
            logger.warning("Error reading container OAuth token at %s: %s", token_path, err)
    return None

def get_snowflake_session() -> Optional[Any]:
    """Retrieve an active Snowpark session depending on the execution environment.

    Returns:
        Snowpark Session object if available, or None if in offline/local mock mode.
    """
    try:
        import streamlit as st

        # 1. Automatic Environment Detection: Check local Streamlit secrets configuration
        secrets_has_snowflake = False
        try:
            if hasattr(st, "secrets") and st.secrets and st.secrets.get("snowflake"):
                secrets_has_snowflake = True
        except Exception:
            secrets_has_snowflake = False

        if secrets_has_snowflake:
            logger.info("Detected local Streamlit environment with secrets.toml configured. Initializing st.connection('snowflake').")
            conn = st.connection("snowflake")
            return getattr(conn, "session", None)

        # 2. Check Streamlit in Snowflake (SiS) execution environment
        try:
            import snowflake.snowpark.context as snowpark_ctx
            session = snowpark_ctx.get_active_session()
            if session:
                logger.info("Successfully retrieved active Snowpark session from Streamlit in Snowflake (SiS).")
                return session
        except Exception as sis_err:
            logger.debug("Streamlit in Snowflake active session not present: %s", sis_err)

    except Exception as err:
        logger.warning("Unable to initialize Snowflake session: %s. Falling back to synthetic offline data mode.", err)

    logger.info("Operating in standalone simulation mode with synthetic data.")
    return None
