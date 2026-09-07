"""Smart Snowflake Connection Module.

Supports automatic environment detection for both:
1. Local Streamlit Desktop execution (using st.connection("snowflake") and st.secrets)
2. Streamlit in Snowflake (SiS) execution (using snowflake.snowpark.context.get_active_session())
3. Graceful fallback when running in standalone offline mode.
"""

from typing import Optional, Any
import logging

logger = logging.getLogger("snowflake_connection")

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
