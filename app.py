"""Manufacturing OEE Conversational Analytics Application in Streamlit.

Integrates:
- Chat Interface
- Sidebar Filters
- KPI Cards
- Cortex Analyst (NLU & Structured Data Querying)
- Dynamic Visualization Engine (LLM Code Gen -> AST Security Validation -> Restricted Execution -> Plotly Figure)
- Developer / Debug Mode

UI NOTE:
This file adds a full custom visual theme (fonts, colors, cards, chat bubbles,
sidebar, buttons, hero header w/ logo) on top of the original application
logic. No business logic, data flow, or module contracts were changed —
only presentation.
"""

import base64
import logging
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

from config import APP_TITLE, APP_ICON
from data.sample_data import generate_oee_dataset, calculate_aggregated_oee
from services.cortex_analyst import CortexAnalystService
from services.cortex_ai import CortexAIService
from services.snowflake_connection import get_snowflake_session
from ui.components import render_sidebar_filters, render_kpi_cards, render_sample_questions
from visualization.chart_generator import generate_chart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oee_streamlit_app")

# --------------------------------------------------------------------------
# Brand palette — pulled from the Just Born mark (navy / coral / magenta /
# gold) but tuned down into a calm, premium business-analytics theme.
# --------------------------------------------------------------------------
BRAND = {
    "navy": "#242B6B",        # primary brand ink (from logo wordmark)
    "navy_light": "#3B4394",
    "navy_deep": "#171C4A",
    "coral": "#E15241",       # from the "10" badge
    "magenta": "#A63A96",     # from the ribbon/confetti
    "gold": "#E0A438",        # from the confetti stars
    "bg_top": "#F3F5FC",      # app background gradient, top
    "bg_bottom": "#FFFFFF",   # app background gradient, bottom
    "panel": "#F6F7FD",       # sidebar tint
    "card": "#FFFFFF",
    "card_soft": "#FBFBFE",
    "border": "#E4E7F3",
    "text": "#1E2233",
    "muted": "#6C7290",
    "shadow": "31, 41, 107",  # rgb triplet of navy, used in box-shadows
}

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "just_born_logo.png"


@st.cache_data(show_spinner=False)
def _get_base64_image(path: Path) -> str:
    """Read an image file and return a base64 string, or '' if missing."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return ""


LOGO_B64 = _get_base64_image(LOGO_PATH)

# --------------------------------------------------------------------------
# Page Configuration
# --------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------------------------------
# Global Custom CSS Theme
# --------------------------------------------------------------------------
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: {BRAND['text']};
    }}

    /* ---------- App background: soft navy-tinted gradient, gives cards ---------- */
    /* something to visibly float above via shadow, instead of flat white ---- */
    .stApp {{
        background: linear-gradient(180deg, {BRAND['bg_top']} 0%, {BRAND['bg_bottom']} 420px);
    }}

    /* ---------- Hide default streamlit chrome ---------- */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{background: transparent;}}

    .block-container {{
        padding-top: 1.6rem;
        padding-bottom: 2.5rem;
    }}

    /* ---------- Hero header: logo + title merged into one soft panel ---------- */
    /* No card border/box around the logo itself — it sits directly on the   */
    /* same gradient as the page, with only a drop-shadow for lift, so the   */
    /* (transparent) PNG reads as part of the UI rather than a pasted asset. */
    .hero-banner {{
        display: flex;
        align-items: center;
        gap: 22px;
        padding: 22px 28px;
        margin-bottom: 22px;
        border-radius: 18px;
        background: linear-gradient(120deg, #FFFFFF 0%, #F5F1FA 55%, #FDF3EE 100%);
        box-shadow: 0 14px 34px -12px rgba({BRAND['shadow']}, 0.22),
                    0 2px 8px rgba({BRAND['shadow']}, 0.06);
        position: relative;
        overflow: hidden;
    }}
    .hero-banner::before {{
        content: "";
        position: absolute;
        top: -60%; right: -8%;
        width: 260px; height: 260px;
        background: radial-gradient(circle, rgba(224,164,56,0.16) 0%, rgba(224,164,56,0) 70%);
        pointer-events: none;
    }}
    .hero-banner::after {{
        content: "";
        position: absolute;
        bottom: -70%; left: 30%;
        width: 220px; height: 220px;
        background: radial-gradient(circle, rgba(166,58,150,0.10) 0%, rgba(166,58,150,0) 70%);
        pointer-events: none;
    }}
    .hero-logo svg {{
        height: 62px;
        width: 62px;
        display: block;
        /* drop-shadow (not a box-shadow) hugs the actual icon shape so it */
        /* reads as an object with depth, not a sticker */
        filter: drop-shadow(0 6px 10px rgba({BRAND['shadow']}, 0.20));
    }}
    .hero-text {{ position: relative; z-index: 1; }}
    .hero-title {{
        font-family: 'Poppins', sans-serif;
        font-weight: 700;
        font-size: 1.65rem;
        line-height: 1.25;
        margin: 0;
        color: {BRAND['navy']};
        letter-spacing: -0.2px;
    }}
    .hero-subtitle {{
        margin-top: 6px;
        color: {BRAND['muted']};
        font-size: 0.92rem;
        max-width: 680px;
        line-height: 1.5;
    }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background: {BRAND['panel']};
        border-right: 1px solid {BRAND['border']};
    }}
    section[data-testid="stSidebar"] > div {{
        padding-top: 0.5rem;
    }}
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] .stSubheader {{
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: {BRAND['navy']} !important;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}
    section[data-testid="stSidebar"] label {{
        color: {BRAND['text']} !important;
        font-weight: 500;
        font-size: 0.92rem;
    }}
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
        background-color: #FFFFFF !important;
        border-radius: 8px !important;
        border: 1px solid {BRAND['border']} !important;
        color: {BRAND['text']} !important;
        box-shadow: 0 1px 2px rgba({BRAND['shadow']}, 0.05) !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div:focus-within,
    section[data-testid="stSidebar"] input:focus {{
        border-color: {BRAND['navy_light']} !important;
        box-shadow: 0 0 0 3px rgba(59, 67, 148, 0.12) !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: {BRAND['border']};
    }}
    /* toggle accent */
    section[data-testid="stSidebar"] [data-baseweb="checkbox"] span {{
        background-color: {BRAND['navy_light']} !important;
    }}

    /* ---------- Sidebar logo: no card, no border box — just the mark, ---- */
    /* lifted off the panel with a drop-shadow so it feels native to the UI */
    .sidebar-logo-wrap {{
        text-align: center;
        padding: 20px 10px 22px 10px;
        margin-bottom: 6px;
    }}
    .sidebar-logo-wrap img {{
        width: 100%;
        max-width: 168px;
        filter: drop-shadow(0 8px 14px rgba({BRAND['shadow']}, 0.18));
    }}
    .sidebar-logo-divider {{
        height: 3px;
        border-radius: 3px;
        margin: 0 auto 14px auto;
        width: 60%;
        background: linear-gradient(90deg, {BRAND['coral']}, {BRAND['magenta']}, {BRAND['gold']});
        opacity: 0.85;
    }}

    /* ---------- KPI Metric Cards ---------- */
    div[data-testid="stMetric"] {{
        background: {BRAND['card']};
        border-radius: 14px;
        padding: 16px 18px 12px 18px;
        border: 1px solid {BRAND['border']};
        box-shadow: 0 8px 20px -10px rgba({BRAND['shadow']}, 0.18),
                    0 1px 3px rgba({BRAND['shadow']}, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 14px 26px -10px rgba({BRAND['shadow']}, 0.24),
                    0 2px 5px rgba({BRAND['shadow']}, 0.07);
    }}
    div[data-testid="stMetric"] label {{
        color: {BRAND['muted']} !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem !important;
        letter-spacing: 0.5px;
    }}
    div[data-testid="stMetricValue"] {{
        color: {BRAND['navy']} !important;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }}

    /* ---------- Section divider ---------- */
    hr {{ border-color: {BRAND['border']}; }}

    /* ---------- Buttons (sample question chips, general buttons) ---------- */
    .stButton > button {{
        border-radius: 10px !important;
        border: 1px solid {BRAND['border']} !important;
        background: {BRAND['card']} !important;
        color: {BRAND['navy']} !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        box-shadow: 0 4px 10px -4px rgba({BRAND['shadow']}, 0.14) !important;
        transition: all 0.18s ease !important;
    }}
    .stButton > button:hover {{
        background: linear-gradient(120deg, {BRAND['navy']}, {BRAND['navy_light']}) !important;
        color: #FFFFFF !important;
        border-color: {BRAND['navy']} !important;
        box-shadow: 0 10px 22px -8px rgba({BRAND['shadow']}, 0.32) !important;
        transform: translateY(-1px);
    }}
    .stButton > button:active {{
        transform: translateY(0px);
    }}

    /* ---------- Chat messages ---------- */
    div[data-testid="stChatMessage"] {{
        background: {BRAND['card']};
        border-radius: 14px;
        border: 1px solid {BRAND['border']};
        padding: 6px 10px;
        margin-bottom: 12px;
        box-shadow: 0 6px 16px -10px rgba({BRAND['shadow']}, 0.16),
                    0 1px 2px rgba({BRAND['shadow']}, 0.04);
    }}

    /* ---------- Chat input ---------- */
    [data-testid="stChatInput"] {{
        border-radius: 14px !important;
        box-shadow: 0 8px 22px -10px rgba({BRAND['shadow']}, 0.20) !important;
        border: 1px solid {BRAND['border']} !important;
    }}

    /* ---------- Expanders (SQL / Data / Debug panels) ---------- */
    div[data-testid="stExpander"] {{
        border-radius: 12px !important;
        border: 1px solid {BRAND['border']} !important;
        overflow: hidden;
        background: {BRAND['card']};
        box-shadow: 0 4px 12px -6px rgba({BRAND['shadow']}, 0.10);
    }}
    div[data-testid="stExpander"] summary {{
        font-weight: 600;
        color: {BRAND['navy']};
    }}

    /* ---------- Sidebar expanders: stack flush as one continuous panel ---------- */
    section[data-testid="stSidebar"] div[data-testid="stExpander"] {{
        margin-bottom: 0 !important;
        border-radius: 0 !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stExpander"] + div[data-testid="stExpander"] {{
        border-top: none !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stExpander"]:first-of-type {{
        border-top-left-radius: 12px !important;
        border-top-right-radius: 12px !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stExpander"]:last-of-type {{
        border-bottom-left-radius: 12px !important;
        border-bottom-right-radius: 12px !important;
        margin-bottom: 12px !important;
    }}

    /* ---------- Dataframe ---------- */
    div[data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid {BRAND['border']};
        box-shadow: 0 4px 12px -6px rgba({BRAND['shadow']}, 0.10);
    }}

    /* ---------- Section label ---------- */
    .section-label {{
        font-family: 'Poppins', sans-serif;
        font-weight: 700;
        color: {BRAND['navy']};
        font-size: 0.98rem;
        margin: 22px 0 10px 2px;
        display: flex;
        align-items: center;
        gap: 8px;
        padding-bottom: 8px;
        border-bottom: 2px solid {BRAND['border']};
    }}

    /* ---------- Scrollbar polish ---------- */
    ::-webkit-scrollbar {{ width: 9px; height: 9px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: rgba({BRAND['shadow']}, 0.28);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba({BRAND['shadow']}, 0.45); }}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Initialize Smart Snowflake Connection
# --------------------------------------------------------------------------
snowflake_session = get_snowflake_session()


@st.cache_data
def load_dataset():
    if snowflake_session is not None:
        try:
            return snowflake_session.sql("SELECT * FROM OEE_TELEMETRY").to_pandas()
        except Exception as query_err:
            logger.warning(f"Snowflake table query failed: {query_err}. Using generated telemetry dataset.")
    return generate_oee_dataset()


df_raw = load_dataset()

# Initialize Services
analyst_service = CortexAnalystService(df_raw)
cortex_ai_service = CortexAIService()

# --------------------------------------------------------------------------
# Page Header — a performance-gauge glyph (built as inline SVG, not the
# logo) sits in the same soft shadowed panel as the title, so it reads as
# part of the UI. The logo itself now only appears in the sidebar.
# --------------------------------------------------------------------------
GAUGE_ICON_SVG = f"""
<svg viewBox="0 0 100 76" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="gaugeRed" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{BRAND['coral']}"/>
            <stop offset="100%" stop-color="{BRAND['magenta']}"/>
        </linearGradient>
        <linearGradient id="gaugeGold" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{BRAND['gold']}"/>
            <stop offset="100%" stop-color="#F0C25E"/>
        </linearGradient>
        <linearGradient id="gaugeNavy" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{BRAND['navy_light']}"/>
            <stop offset="100%" stop-color="{BRAND['navy']}"/>
        </linearGradient>
    </defs>
    <!-- three performance bands: low / mid / high, classic OEE gauge -->
    <path d="M12,60 A38,38 0 0,1 31,27.1" fill="none" stroke="url(#gaugeRed)"
          stroke-width="9" stroke-linecap="round"/>
    <path d="M31,27.1 A38,38 0 0,1 69,27.1" fill="none" stroke="url(#gaugeGold)"
          stroke-width="9" stroke-linecap="round"/>
    <path d="M69,27.1 A38,38 0 0,1 88,60" fill="none" stroke="url(#gaugeNavy)"
          stroke-width="9" stroke-linecap="round"/>
    <!-- needle pointing into the high-performance band -->
    <line x1="50" y1="60" x2="73" y2="41" stroke="{BRAND['navy_deep']}"
          stroke-width="4.5" stroke-linecap="round"/>
    <circle cx="50" cy="60" r="7.5" fill="{BRAND['navy_deep']}"/>
    <circle cx="50" cy="60" r="3" fill="{BRAND['gold']}"/>
</svg>
"""

st.markdown(f"""
<div class="hero-banner">
    <div class="hero-logo">{GAUGE_ICON_SVG}</div>
    <div class="hero-text">
        <div class="hero-title">OEE AI Assistant</div>
        <div class="hero-subtitle">
            Ask natural language questions about plant performance, equipment availability,
            line productivity, and downtime root causes — powered by Cortex Analyst.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# --------------------------------------------------------------------------
# Sidebar: Logo, Filters & Developer Mode
# --------------------------------------------------------------------------
if LOGO_B64:
    st.sidebar.markdown(
        f"""
        <div class="sidebar-logo-wrap">
            <img src="data:image/png;base64,{LOGO_B64}" />
        </div>
        <div class="sidebar-logo-divider"></div>
        """,
        unsafe_allow_html=True,
    )

with st.sidebar.expander("🧭 Filters", expanded=True):
    filters = render_sidebar_filters(df_raw)

with st.sidebar.expander("🎯 OEE Target Benchmarks", expanded=True):
    target_oee = st.number_input("Target OEE (%)", min_value=0.0, max_value=100.0, value=85.0, step=1.0)
    target_avail = st.number_input("Target Availability (%)", min_value=0.0, max_value=100.0, value=90.0, step=1.0)
    target_perf = st.number_input("Target Performance (%)", min_value=0.0, max_value=100.0, value=95.0, step=1.0)
    target_qual = st.number_input("Target Quality (%)", min_value=0.0, max_value=100.0, value=99.0, step=1.0)

targets = {
    "oee": target_oee,
    "availability": target_avail,
    "performance": target_perf,
    "quality": target_qual
}

st.sidebar.divider()
debug_mode = st.sidebar.toggle("🛠️ Developer / Debug Mode", value=False)

st.sidebar.markdown(
    f"""
    <div style="margin-top: 20px; padding-top: 14px; border-top: 1px solid {BRAND['border']};
                font-size: 0.75rem; color: {BRAND['muted']}; text-align:center;">
        Manufacturing Analytics Assistant<br/>Built on Snowflake Cortex
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Filter Dataset according to global sidebar controls
# --------------------------------------------------------------------------
df_filtered = analyst_service._apply_filters(df_raw, filters)

# --------------------------------------------------------------------------
# Global KPI Cards
# --------------------------------------------------------------------------
st.markdown('<div class="section-label">📊 Plant Performance Overview</div>', unsafe_allow_html=True)
kpis = calculate_aggregated_oee(df_filtered)
render_kpi_cards(kpis, targets)

st.divider()

# --------------------------------------------------------------------------
# Session State for Chat History
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Sample Question Chips
# --------------------------------------------------------------------------
st.markdown('<div class="section-label">💡 Try asking</div>', unsafe_allow_html=True)
render_sample_questions(submit_question)

st.write("")
st.markdown('<div class="section-label">💬 Conversation</div>', unsafe_allow_html=True)

ASSISTANT_AVATAR = "🤖"
USER_AVATAR = "🧑‍🏭"

# --------------------------------------------------------------------------
# Render Chat History
# --------------------------------------------------------------------------
assistant_indices = [i for i, m in enumerate(st.session_state.messages) if m["role"] == "assistant"]
latest_assistant_idx = assistant_indices[-1] if assistant_indices else None


def _response_label(idx: int) -> str:
    """Build an expander label from the user question that preceded this reply."""
    if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user":
        q = st.session_state.messages[idx - 1]["content"].strip()
        preview = q[:60] + ("…" if len(q) > 60 else "")
        return f"💬 {preview}"
    return "💬 Assistant response"


for idx, msg in enumerate(st.session_state.messages):
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] != "assistant":
            st.markdown(msg["content"])
            continue

        # Every assistant reply lives inside its own expander. Only the most
        # recent reply opens automatically; earlier ones stay collapsed.
        is_latest = (idx == latest_assistant_idx)
        with st.expander(_response_label(idx), expanded=is_latest):
            st.markdown(msg["content"])

            if "sql_query" in msg and msg["sql_query"]:
                st.markdown("**🛠️ Cortex Analyst Generated SQL Query**")
                st.code(msg["sql_query"], language="sql")

            if "figure" in msg and msg["figure"] is not None:
                st.plotly_chart(msg["figure"], use_container_width=True, key=f"hist_chart_{idx}")

            if debug_mode and "chart_result" in msg and msg["chart_result"]:
                res = msg["chart_result"]
                st.markdown("**🔍 Debug: Dynamic Chart Generation Details**")
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

            if "data" in msg and msg["data"] is not None and not msg["data"].empty:
                st.markdown("**📋 Queried Data Table**")
                st.dataframe(msg["data"], use_container_width=True, key=f"hist_df_{idx}")

# --------------------------------------------------------------------------
# Handle Chat Input or Sample Question Click
# --------------------------------------------------------------------------
user_input = st.chat_input("Ask an OEE question (e.g. 'Show OEE trend by plant over time')")

prompt = user_input or st.session_state.pending_question
if prompt:
    st.session_state.pending_question = None

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("🤖 Cortex Analyst parsing question & querying structured data..."):
            analyst_res = analyst_service.process_question(prompt, filters)

        summary_text = analyst_res.get("summary_text", "")
        data = analyst_res.get("data")

        # New reply — its expander opens automatically. On the next rerun it
        # will be rendered by the history loop above and collapsed like the
        # rest, since a fresh response will then be the newest one.
        preview = prompt.strip()[:60] + ("…" if len(prompt.strip()) > 60 else "")
        with st.expander(f"💬 {preview}", expanded=True):
            st.markdown(summary_text)

            if analyst_res.get("sql_query"):
                st.markdown("**🛠️ Cortex Analyst Generated SQL Query**")
                st.code(analyst_res["sql_query"], language="sql")

            chart_res = None
            if data is not None and not data.empty:
                with st.spinner("🎨 Dynamic Visualization Planner generating and validating chart code..."):
                    chart_res = generate_chart(
                        question=prompt,
                        dataframe=data,
                        cortex_ai_service=cortex_ai_service,
                        analyst_summary=summary_text
                    )

                active_idx = len(st.session_state.messages)
                if chart_res.should_visualize and chart_res.figure is not None:
                    st.plotly_chart(chart_res.figure, use_container_width=True, key=f"active_chart_{active_idx}")
                elif chart_res.should_visualize and not chart_res.is_valid:
                    st.info(f"ℹ️ Unable to generate visualization: {chart_res.error_message or 'Validation error'}")

                if debug_mode and chart_res:
                    st.markdown("**🔍 Debug: Dynamic Chart Generation Details**")
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

            if data is not None and not data.empty:
                st.markdown("**📋 Queried Data Table**")
                st.dataframe(data, use_container_width=True, key=f"active_df_{active_idx}")

        st.session_state.messages.append({
            "role": "assistant",
            "content": summary_text,
            "sql_query": analyst_res.get("sql_query"),
            "data": data,
            "figure": chart_res.figure if chart_res else None,
            "chart_result": chart_res
        })
