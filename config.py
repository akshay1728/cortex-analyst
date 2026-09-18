"""Configuration settings for the Manufacturing OEE Conversational Analytics Application."""

import os

APP_TITLE = "Manufacturing OEE Conversational Analytics"
APP_ICON = "🏭"

# Directly defined database configuration variables
APP_SCHEMA = os.getenv("APP_SCHEMA", "APPS")
DB = os.getenv("DB", "JBEDW_DEV")
TRACKSYS_SCHEMA = os.getenv("TRACKSYS_SCHEMA", "STAGE_TRAKSYS")
ANALYTICS_SCHEMA = os.getenv("ANALYTICS_SCHEMA", "ANALYTICS_OPERATIONS")
