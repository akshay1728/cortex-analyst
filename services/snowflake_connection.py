"""Smart Snowflake Connection Module.

Supports automatic environment detection for:
1. Streamlit in Snowflake (SiS) / Container Runtime execution (using snowflake.snowpark.context.get_active_session())
2. Graceful fallback when running in standalone offline mode.
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
    """Retrieve an active Snowpark session in Snowflake Runtime environment.

    Returns:
        Snowpark Session object if available, or None if unavailable.
    """
    try:
        import snowflake.snowpark.context as snowpark_ctx
        session = snowpark_ctx.get_active_session()
        if session:
            logger.info("Successfully retrieved active Snowpark session from Snowflake Runtime.")
            return session
    except Exception as sis_err:
        logger.debug("Active Snowpark session not present in runtime environment: %s", sis_err)

    return None
