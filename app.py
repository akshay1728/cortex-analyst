"""Manufacturing OEE Conversational Analytics Application in Streamlit.

Integrates:
- Chat Interface
- Sidebar Filters
- KPI Cards
- Cortex Analyst (NLU & Structured Data Querying)
- Cortex AI / AI_COMPLETE (Visualization Spec Generation)
- Python Validation Layer (Chart Type & Schema Validation)
- Plotly Chart Rendering & Data Tables
"""

import streamlit as st
import pandas as pd
import numpy as np

from config import APP_TITLE, APP_ICON
from data.sample_data import generate_oee_dataset, calculate_aggregated_oee
from services.cortex_analyst import CortexAnalystService
from services.cortex_ai import CortexAIService
from services.python_validator import PythonValidator
from ui.components import render_sidebar_filters, render_kpi_cards, render_sample_questions
from ui.chart_renderer import ChartRenderer

# Page Configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load / Cache Dataset
@st.cache_data
def load_dataset():
    return generate_oee_dataset()

df_raw = load_dataset()

# Initialize Services
analyst_service = CortexAnalystService(df_raw)
ai_service = CortexAIService()
validator = PythonValidator()

# Header Section
st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("Ask natural language questions about plant performance, equipment availability, line productivity, and downtime root causes.")

# Sidebar Filters
filters = render_sidebar_filters(df_raw)

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
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # If response includes SQL Query, display in expander
        if "sql_query" in msg and msg["sql_query"]:
            with st.expander("🛠️ Cortex Analyst Generated SQL Query"):
                st.code(msg["sql_query"], language="sql")

        # If response includes chart spec and data, render visualization
        if "spec" in msg and "data" in msg and msg["data"] is not None:
            spec = msg["spec"]
            data = msg["data"]

            # Validation status notification
            val_status = msg.get("validation_status", "Passed")
            if not msg.get("is_valid", True):
                st.warning(f"⚠️ Python Validation Layer Adjustment: {val_status}")

            chart_type = spec.get("chart_type")
            if chart_type in ["line", "bar", "grouped_bar", "stacked_bar", "pie", "donut", "gauge", "scatter"]:
                fig = ChartRenderer.render_chart(spec, data)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

            # Display Data Table Tab / View
            with st.expander("📋 View Queried Data Table"):
                st.dataframe(data, use_container_width=True)

# Handle Chat Input or Sample Question Click
user_input = st.chat_input("Ask an OEE question (e.g. 'Show OEE trend by plant over time')")

prompt = user_input or st.session_state.pending_question
if prompt:
    st.session_state.pending_question = None

    # Append user prompt to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process via Cortex Analyst & AI Pipeline
    with st.chat_message("assistant"):
        with st.spinner("🤖 Cortex Analyst parsing question & querying structured data..."):
            analyst_res = analyst_service.process_question(prompt, filters)

        with st.spinner("🎨 Cortex AI determining optimal visualization specification..."):
            raw_spec = ai_service.decide_visualization(prompt, analyst_res)

        with st.spinner("⚙️ Python Validation Layer verifying chart schema & constraints..."):
            data = analyst_res.get("data")
            validated_spec, is_valid, val_msg = validator.validate_and_sanitize(raw_spec, data)

        # Build Assistant Response Text
        summary_text = analyst_res.get("summary_text", "")
        st.markdown(summary_text)

        # Display SQL Query
        if analyst_res.get("sql_query"):
            with st.expander("🛠️ Cortex Analyst Generated SQL Query"):
                st.code(analyst_res["sql_query"], language="sql")

        # Display Validation Warning if any
        if not is_valid:
            st.warning(f"⚠️ Python Validation Layer Adjustment: {val_msg}")

        # Render Chart
        fig = ChartRenderer.render_chart(validated_spec, data)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # Display Data Table
        if data is not None and not data.empty:
            with st.expander("📋 View Queried Data Table"):
                st.dataframe(data, use_container_width=True)

        # Save Assistant Message to Session State
        st.session_state.messages.append({
            "role": "assistant",
            "content": summary_text,
            "sql_query": analyst_res.get("sql_query"),
            "spec": validated_spec,
            "data": data,
            "is_valid": is_valid,
            "validation_status": val_msg
        })
