"""Manufacturing OEE Conversational Analytics Application in Streamlit.

Integrates:
- Chat Interface
- Sidebar Filters
- KPI Cards
- Cortex Analyst (NLU & Structured Data Querying)
- Dynamic Visualization Engine (LLM Code Gen -> AST Security Validation -> Restricted Execution -> Plotly Figure)
- Developer / Debug Mode
"""

import streamlit as st
import pandas as pd
import numpy as np
import logging

from config import APP_TITLE, APP_ICON
from data.sample_data import generate_oee_dataset, calculate_aggregated_oee
from services.cortex_analyst import CortexAnalystService
from services.cortex_ai import CortexAIService
from services.snowflake_connection import get_snowflake_session
from ui.components import render_sidebar_filters, render_kpi_cards, render_sample_questions
from visualization.chart_generator import generate_chart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oee_streamlit_app")

# Page Configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Smart Snowflake Connection
snowflake_session = get_snowflake_session()

# Load / Cache Dataset
@st.cache_data
def load_dataset():
    if snowflake_session is not None:
        try:
            # Query active Snowflake session if available
            return snowflake_session.sql("SELECT * FROM OEE_TELEMETRY").to_pandas()
        except Exception as query_err:
            logger.warning(f"Snowflake table query failed: {query_err}. Using generated telemetry dataset.")
    return generate_oee_dataset()

df_raw = load_dataset()

# Initialize Services
analyst_service = CortexAnalystService(df_raw)
cortex_ai_service = CortexAIService()

# Header Section
st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("Ask natural language questions about plant performance, equipment availability, line productivity, and downtime root causes.")

# Sidebar Filters & Developer Mode
filters = render_sidebar_filters(df_raw)

st.sidebar.divider()
debug_mode = st.sidebar.toggle("🛠️ Developer / Debug Mode", value=False)

# Filter Dataset according to global sidebar controls
df_filtered = analyst_service._apply_filters(df_raw, filters)

# Global KPI Cards
kpis = calculate_aggregated_oee(df_filtered)
render_kpi_cards(kpis)

st.divider()

# Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I am your **Manufacturing OEE Conversational Assistant**. Ask me anything about OEE, availability, performance, downtime reasons, or production volume across your plants and lines!"
        }
    ]

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

def submit_question(q_text: str):
    st.session_state.pending_question = q_text

# Render Sample Question Chips
render_sample_questions(submit_question)

st.write("")

# Render Chat History
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Display SQL Query expander if present
        if "sql_query" in msg and msg["sql_query"]:
            with st.expander("🛠️ Cortex Analyst Generated SQL Query"):
                st.code(msg["sql_query"], language="sql")

        # Display Dynamic Chart if present
        if "figure" in msg and msg["figure"] is not None:
            st.plotly_chart(msg["figure"], use_container_width=True, key=f"hist_chart_{idx}")

        # Display Debug / Developer Expander if enabled
        if debug_mode and "chart_result" in msg and msg["chart_result"]:
            res = msg["chart_result"]
            with st.expander("🔍 Debug: Dynamic Chart Generation Details"):
                st.json({
                    "should_visualize": res.should_visualize,
                    "chart_type": res.chart_type,
                    "reasoning": res.reasoning,
                    "validation_status": res.validation_status,
                    "is_valid": res.is_valid,
                    "error_message": res.error_message
                })
                if res.python_code:
                    st.markdown("**Generated Python Code:**")
                    st.code(res.python_code, language="python")

        # Display Data Table Tab / View
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            with st.expander("📋 View Queried Data Table"):
                st.dataframe(msg["data"], use_container_width=True, key=f"hist_df_{idx}")

# Handle Chat Input or Sample Question Click
user_input = st.chat_input("Ask an OEE question (e.g. 'Show OEE trend by plant over time')")

prompt = user_input or st.session_state.pending_question
if prompt:
    st.session_state.pending_question = None

    # Append user prompt to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process via Cortex Analyst & Dynamic Visualization Engine
    with st.chat_message("assistant"):
        with st.spinner("🤖 Cortex Analyst parsing question & querying structured data..."):
            analyst_res = analyst_service.process_question(prompt, filters)

        summary_text = analyst_res.get("summary_text", "")
        data = analyst_res.get("data")

        # Display Assistant Textual Answer
        st.markdown(summary_text)

        # Display SQL Query
        if analyst_res.get("sql_query"):
            with st.expander("🛠️ Cortex Analyst Generated SQL Query"):
                st.code(analyst_res["sql_query"], language="sql")

        # Dynamic Visualization Planning, Code Generation, AST Validation, and Execution
        chart_res = None
        if data is not None and not data.empty:
            with st.spinner("🎨 Dynamic Visualization Planner generating and validating chart code..."):
                chart_res = generate_chart(
                    question=prompt,
                    dataframe=data,
                    cortex_ai_service=cortex_ai_service,
                    analyst_summary=summary_text
                )

            # Render Plotly Chart if figure was generated
            active_idx = len(st.session_state.messages)
            if chart_res.should_visualize and chart_res.figure is not None:
                st.plotly_chart(chart_res.figure, use_container_width=True, key=f"active_chart_{active_idx}")
            elif chart_res.should_visualize and not chart_res.is_valid:
                st.info(f"ℹ️ Unable to generate visualization: {chart_res.error_message or 'Validation error'}")

            # Developer / Debug Expander
            if debug_mode and chart_res:
                with st.expander("🔍 Debug: Dynamic Chart Generation Details"):
                    st.json({
                        "should_visualize": chart_res.should_visualize,
                        "chart_type": chart_res.chart_type,
                        "reasoning": chart_res.reasoning,
                        "validation_status": chart_res.validation_status,
                        "is_valid": chart_res.is_valid,
                        "error_message": chart_res.error_message
                    })
                    if chart_res.python_code:
                        st.markdown("**Generated Python Code:**")
                        st.code(chart_res.python_code, language="python")

        # Display Data Table
        if data is not None and not data.empty:
            with st.expander("📋 View Queried Data Table"):
                st.dataframe(data, use_container_width=True, key=f"active_df_{active_idx}")

        # Save Assistant Message to Session State
        st.session_state.messages.append({
            "role": "assistant",
            "content": summary_text,
            "sql_query": analyst_res.get("sql_query"),
            "data": data,
            "figure": chart_res.figure if chart_res else None,
            "chart_result": chart_res
        })
