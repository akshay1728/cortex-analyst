"""Manufacturing OEE Conversational Analytics Application in Streamlit.

Integrates:
- Chat Interface & Settings Page
- Sidebar Filters & Settings Controls
- KPI Cards
- Cortex Analyst (NLU & Structured Data Querying)
- Dynamic Visualization Engine (LLM Code Gen -> AST Security Validation -> Restricted Execution -> Plotly Figure)
- Metric Color Highlighting for Data Tables
- PDF Export of Conversation with Company Logo & Download Timestamp
- Developer / Debug Mode
"""

import base64
import logging
import datetime
import re
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

from config import APP_TITLE, APP_ICON
from data.sample_data import calculate_aggregated_oee
from services.cortex_agent import call_agent, collect_response, tool_results_to_df, render_chart, split_suggestions, deduplicate_paragraphs, format_oee_markdown
from services.snowflake_connection import get_snowflake_session
from services.pdf_generator import generate_conversation_pdf
from ui.components import render_sidebar_filters, render_kpi_cards, render_sample_questions, style_dataframe_metrics
from ui.settings_page import render_settings_page
from services.cortex_analyst import CortexAnalystService
from services.cortex_ai import CortexAIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oee_streamlit_app")

# --------------------------------------------------------------------------
# Brand palette
# --------------------------------------------------------------------------
BRAND = {
    "navy": "#242B6B",
    "navy_light": "#3B4394",
    "navy_deep": "#171C4A",
    "coral": "#E15241",
    "magenta": "#A63A96",
    "gold": "#E0A438",
    "bg_top": "#F3F5FC",
    "bg_bottom": "#FFFFFF",
    "panel": "#F6F7FD",
    "card": "#FFFFFF",
    "card_soft": "#FBFBFE",
    "border": "#E4E7F3",
    "text": "#1E2233",
    "muted": "#6C7290",
    "shadow": "31, 41, 107",
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


DEFAULT_LOGO_B64 = _get_base64_image(LOGO_PATH)
DEFAULT_LOGO_BYTES = LOGO_PATH.read_bytes() if LOGO_PATH.exists() else None

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
# Initialize Session State Settings
# --------------------------------------------------------------------------
if "settings_targets" not in st.session_state:
    st.session_state.settings_targets = {
        "oee": 85.0,
        "availability": 90.0,
        "performance": 95.0,
        "quality": 99.0
    }

if "settings_colors" not in st.session_state:
    st.session_state.settings_colors = {
        "oee": {"enabled": False, "threshold": 85.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "availability": {"enabled": False, "threshold": 75.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "performance": {"enabled": False, "threshold": 95.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "quality": {"enabled": False, "threshold": 99.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
    }

if "settings_header_title" not in st.session_state:
    st.session_state.settings_header_title = "OEE AI Assistant"

if "settings_header_subtitle" not in st.session_state:
    st.session_state.settings_header_subtitle = (
        "Ask natural language questions about plant performance, equipment availability, "
        "line productivity, and downtime root causes — powered by Cortex Analyst."
    )

if "settings_custom_logo_bytes" not in st.session_state:
    st.session_state.settings_custom_logo_bytes = None

if "settings_pdf_filename_template" not in st.session_state:
    st.session_state.settings_pdf_filename_template = "OEE_Conversation_Report_{YYYYMMDD}.pdf"

# Initialize Session State for Chat History early
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "display": "Hello! I am your **Manufacturing OEE Conversational Assistant**. Ask me anything about OEE, availability, performance, downtime reasons, or production volume across your plants and lines!",
            "content": [{"type": "text", "text": "Hello! I am your Manufacturing OEE Conversational Assistant. Ask me anything about OEE, availability, performance, downtime reasons, or production volume across your plants and lines!"}]
        }
    ]

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

    .stApp {{
        background: linear-gradient(180deg, {BRAND['bg_top']} 0%, {BRAND['bg_bottom']} 420px);
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{background: transparent;}}

    .block-container {{
        padding-top: 1.6rem;
        padding-bottom: 2.5rem;
    }}

    /* Compact Heading Sizes & Colored Headers inside Chat Messages */
    div[data-testid="stChatMessage"] h1 {{ font-size: 1.15rem !important; color: {BRAND['navy']} !important; margin-top: 0.5rem; margin-bottom: 0.3rem; font-weight: 700; }}
    div[data-testid="stChatMessage"] h2 {{ font-size: 1.05rem !important; color: {BRAND['navy']} !important; margin-top: 0.4rem; margin-bottom: 0.3rem; font-weight: 700; }}
    div[data-testid="stChatMessage"] h3 {{ font-size: 0.98rem !important; color: {BRAND['navy']} !important; margin-top: 0.4rem; margin-bottom: 0.2rem; font-weight: 700; }}
    div[data-testid="stChatMessage"] h4 {{ font-size: 0.92rem !important; color: {BRAND['navy_light']} !important; margin-top: 0.3rem; margin-bottom: 0.2rem; font-weight: 600; }}
    div[data-testid="stChatMessage"] strong, div[data-testid="stChatMessage"] b {{ color: {BRAND['navy_deep']}; }}

    /* Custom Bullet and Sub-bullet Icons for Assistant Responses */
    div[data-testid="stChatMessage"] ul {{
        list-style: none !important;
        padding-left: 1.1rem !important;
        margin-top: 0.3rem;
        margin-bottom: 0.5rem;
    }}
    div[data-testid="stChatMessage"] ul > li {{
        position: relative;
        padding-left: 1.2rem;
        margin-bottom: 0.3rem;
        line-height: 1.45;
    }}
    div[data-testid="stChatMessage"] ul > li::before {{
        content: "🔹";
        position: absolute;
        left: 0;
        top: 0.05rem;
        font-size: 0.78rem;
    }}
    div[data-testid="stChatMessage"] ul > li > ul {{
        list-style: none !important;
        padding-left: 0.9rem !important;
        margin-top: 0.25rem;
        margin-bottom: 0.25rem;
    }}
    div[data-testid="stChatMessage"] ul > li > ul > li {{
        position: relative;
        padding-left: 1.1rem;
        margin-bottom: 0.2rem;
    }}
    div[data-testid="stChatMessage"] ul > li > ul > li::before {{
        content: "▸";
        position: absolute;
        left: 0;
        top: -0.05rem;
        font-size: 0.85rem;
        color: {BRAND['coral']};
        font-weight: bold;
    }}

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

    hr {{ border-color: {BRAND['border']}; }}

    .stButton > button, .stDownloadButton > button {{
        border-radius: 10px !important;
        border: 1px solid {BRAND['border']} !important;
        background: {BRAND['card']} !important;
        color: {BRAND['navy']} !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        box-shadow: 0 4px 10px -4px rgba({BRAND['shadow']}, 0.14) !important;
        transition: all 0.18s ease !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        background: linear-gradient(120deg, {BRAND['navy']}, {BRAND['navy_light']}) !important;
        color: #FFFFFF !important;
        border-color: {BRAND['navy']} !important;
        box-shadow: 0 10px 22px -8px rgba({BRAND['shadow']}, 0.32) !important;
        transform: translateY(-1px);
    }}

    div[data-testid="stChatMessage"] {{
        background: {BRAND['card']};
        border-radius: 14px;
        border: 1px solid {BRAND['border']};
        padding: 6px 10px;
        margin-bottom: 12px;
        box-shadow: 0 6px 16px -10px rgba({BRAND['shadow']}, 0.16),
                    0 1px 2px rgba({BRAND['shadow']}, 0.04);
    }}

    [data-testid="stChatInput"] {{
        border-radius: 14px !important;
        box-shadow: 0 8px 22px -10px rgba({BRAND['shadow']}, 0.20) !important;
        border: 1px solid {BRAND['border']} !important;
    }}

    /* Expanders used elsewhere in the app (outside chat) keep their own card look */
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

    /* The chat bubble is already the card — flatten the expander nested inside it
       so the response doesn't sit inside a second, redundant border/shadow. */
    div[data-testid="stChatMessage"] div[data-testid="stExpander"] {{
        border: none !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        overflow: visible;
    }}
    div[data-testid="stChatMessage"] div[data-testid="stExpander"] summary {{
        padding-left: 2px;
    }}
    div[data-testid="stChatMessage"] div[data-testid="stExpander"] > div {{
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        padding-left: 2px;
        padding-right: 2px;
    }}

    /* KPI badges inside assistant responses (color-coded vs. target) */
    div[data-testid="stChatMessage"] .oee-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 1px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.88em;
        white-space: nowrap;
    }}
    div[data-testid="stChatMessage"] .oee-badge-value {{ background: {BRAND['panel']}; color: {BRAND['navy']}; }}

    /* Icon section headers within assistant responses — flat, single rule, no boxed border */
    div[data-testid="stChatMessage"] .oee-section-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: 'Poppins', sans-serif;
        font-weight: 700;
        color: {BRAND['navy']};
        font-size: 0.98rem;
        margin: 16px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid {BRAND['border']};
    }}
    div[data-testid="stChatMessage"] .oee-section-header .icon {{
        font-size: 1.05rem;
    }}

    /* Sub-section labels used for chart/table/SQL/follow-up blocks */
    .oee-subsection {{
        display: flex;
        align-items: center;
        gap: 7px;
        font-weight: 700;
        color: {BRAND['navy_light']};
        font-size: 0.9rem;
        margin: 14px 0 6px 0;
    }}

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
            logger.error(f"Snowflake table query failed: {query_err}")
            return pd.DataFrame()
    return pd.DataFrame()


df_raw = load_dataset()

# Initialize Services
analyst_service = CortexAnalystService(df_raw)
cortex_ai_service = CortexAIService()

# --------------------------------------------------------------------------
# Render Logo in Sidebar Top
# --------------------------------------------------------------------------
if st.session_state.settings_custom_logo_bytes is not None:
    logo_b64_str = base64.b64encode(st.session_state.settings_custom_logo_bytes).decode("utf-8")
    active_logo_bytes = st.session_state.settings_custom_logo_bytes
else:
    logo_b64_str = DEFAULT_LOGO_B64
    active_logo_bytes = DEFAULT_LOGO_BYTES

if logo_b64_str:
    st.sidebar.markdown(
        f"""
        <div class="sidebar-logo-wrap">
            <img src="data:image/png;base64,{logo_b64_str}" />
        </div>
        <div class="sidebar-logo-divider"></div>
        """,
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------
# Navigation Sidebar
# --------------------------------------------------------------------------
st.sidebar.markdown("### 📌 Navigation")
nav_selection = st.sidebar.radio(
    "Go to",
    options=["💬 Chat Assistant", "⚙️ Settings"],
    label_visibility="collapsed"
)

st.sidebar.divider()

# --------------------------------------------------------------------------
# Render Dynamic Banner Header
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
    <path d="M12,60 A38,38 0 0,1 31,27.1" fill="none" stroke="url(#gaugeRed)"
          stroke-width="9" stroke-linecap="round"/>
    <path d="M31,27.1 A38,38 0 0,1 69,27.1" fill="none" stroke="url(#gaugeGold)"
          stroke-width="9" stroke-linecap="round"/>
    <path d="M69,27.1 A38,38 0 0,1 88,60" fill="none" stroke="url(#gaugeNavy)"
          stroke-width="9" stroke-linecap="round"/>
    <line x1="50" y1="60" x2="73" y2="41" stroke="{BRAND['navy_deep']}"
          stroke-width="4.5" stroke-linecap="round"/>
    <circle cx="50" cy="60" r="7.5" fill="{BRAND['navy_deep']}"/>
    <circle cx="50" cy="60" r="3" fill="{BRAND['gold']}"/>
</svg>
"""

header_title = st.session_state.get("settings_header_title", "OEE AI Assistant")
header_subtitle = st.session_state.get("settings_header_subtitle", "Ask natural language questions about plant performance")

st.markdown(f"""
<div class="hero-banner">
    <div class="hero-logo">{GAUGE_ICON_SVG}</div>
    <div class="hero-text">
        <div class="hero-title">{header_title}</div>
        <div class="hero-subtitle">{header_subtitle}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# --------------------------------------------------------------------------
# Page Routing
# --------------------------------------------------------------------------
if nav_selection == "⚙️ Settings":
    render_settings_page()

else:
    # --- Chat Assistant Page ---
    # Hide filters section in sidebar for now as requested
    HIDE_FILTERS_SIDEBAR = True
    if not HIDE_FILTERS_SIDEBAR:
        with st.sidebar.expander("🧭 Filters", expanded=True):
            filters = render_sidebar_filters(df_raw)
        st.sidebar.divider()
    else:
        filters = {
            "date_range": (),
            "plants": ["All"],
            "lines": ["All"],
            "shifts": ["All"],
            "product_families": ["All"]
        }

    debug_mode = st.sidebar.toggle("🛠️ Developer / Debug Mode", value=False)

    # Filter Dataset
    df_filtered = analyst_service._apply_filters(df_raw, filters) if not df_raw.empty else df_raw

    # KPI Cards using settings targets
    st.markdown('<div class="section-label">📊 Plant Performance Overview</div>', unsafe_allow_html=True)
    kpis = calculate_aggregated_oee(df_filtered) if not df_filtered.empty else {"oee": 0.0, "availability": 0.0, "performance": 0.0, "quality": 0.0, "total_downtime_hours": 0.0}
    render_kpi_cards(kpis, st.session_state.settings_targets)

    st.divider()

    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    def set_pending_question(q_text: str):
        st.session_state.pending_question = q_text

    # Check chat input or pending question from button click
    user_input = st.chat_input("Ask an OEE question (e.g. 'Show OEE trend by plant over time')")
    prompt = user_input or st.session_state.pending_question

    if prompt:
        st.session_state.pending_question = None
        st.session_state.messages.append({
            "role": "user",
            "display": prompt,
            "content": [{"type": "text", "text": prompt}]
        })
        st.session_state.active_prompt = prompt
    else:
        st.session_state.active_prompt = None

    # Sample Questions
    st.markdown('<div class="section-label">💡 Try asking</div>', unsafe_allow_html=True)
    render_sample_questions(set_pending_question)

    st.write("")

    # Conversation Section Header with anchor for auto-scrolling
    st.markdown('<div id="conversation-section" class="section-label">💬 Conversation</div>', unsafe_allow_html=True)

    # Trigger smooth scroll to conversation section when a question button was clicked or prompt entered
    if prompt:
        st.markdown(
            """
            <script>
                var el = parent.document.getElementById('conversation-section');
                if (el) {
                    el.scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            </script>
            """,
            unsafe_allow_html=True
        )

    ASSISTANT_AVATAR = "🤖"
    USER_AVATAR = "🧑‍🏭"

    # Render Chat History
    assistant_indices = [i for i, m in enumerate(st.session_state.messages) if m["role"] == "assistant"]
    latest_assistant_idx = assistant_indices[-1] if assistant_indices else None

    def _get_display_str(msg_obj: dict) -> str:
        if "display" in msg_obj and isinstance(msg_obj["display"], str):
            return msg_obj["display"]
        content = msg_obj.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join([item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"])
        return str(content)

    def _render_response_text(raw_text: str):
        """Apply KPI-badge + section-header formatting, then render as HTML-enabled markdown."""
        if not raw_text:
            return
        formatted = format_oee_markdown(raw_text)
        st.markdown(formatted, unsafe_allow_html=True)

    def _subsection(icon: str, label: str):
        st.markdown(f'<div class="oee-subsection">{icon} {label}</div>', unsafe_allow_html=True)

    def _response_label(idx: int) -> str:
        if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user":
            q = _get_display_str(st.session_state.messages[idx - 1]).strip()
            preview = q[:60] + ("…" if len(q) > 60 else "")
            return f"💬 {preview}"
        return "💬 Assistant response"

    for idx, msg in enumerate(st.session_state.messages):
        avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            disp_text = _get_display_str(msg)
            if msg["role"] != "assistant":
                st.markdown(disp_text)
                continue

            is_latest = (idx == latest_assistant_idx and st.session_state.active_prompt is None)
            with st.expander(_response_label(idx), expanded=is_latest):
                main_msg, suggestions_from_text = split_suggestions(disp_text)
                clean_main_msg = deduplicate_paragraphs(main_msg)
                if clean_main_msg:
                    _render_response_text(clean_main_msg)

                if "sql_query" in msg and msg["sql_query"]:
                    _subsection("🛠️", "Cortex Analyst Generated SQL Query")
                    st.code(msg["sql_query"], language="sql")

                # Track queries from blocks
                suggested_queries = list(suggestions_from_text)
                if "blocks" in msg and isinstance(msg["blocks"], list):
                    last_df = msg.get("data")
                    for b_idx, b in enumerate(msg["blocks"]):
                        if b.get("type") == "chart":
                            # Note: "Visualization Chart" sub-heading removed as requested
                            chart_target = b.get("spec") or b.get("figure")
                            render_chart(chart_target, last_df, key=f"hist_cortex_chart_{idx}_{b_idx}")
                        elif b.get("type") == "tool_results":
                            tool_df = tool_results_to_df(b.get("content"))
                            if tool_df is not None and not tool_df.empty:
                                last_df = tool_df
                                _subsection("📋", "Queried Data Table")
                                styled_df = style_dataframe_metrics(tool_df, st.session_state.settings_colors)
                                st.dataframe(styled_df, use_container_width=True, key=f"hist_tool_df_{idx}_{b_idx}")
                        elif b.get("type") == "suggested_queries":
                            for q_item in b.get("queries", []):
                                if q_item not in suggested_queries:
                                    suggested_queries.append(q_item)

                elif "data" in msg and msg["data"] is not None and not msg["data"].empty:
                    _subsection("📋", "Queried Data Table")
                    styled_df = style_dataframe_metrics(msg["data"], st.session_state.settings_colors)
                    st.dataframe(styled_df, use_container_width=True, key=f"hist_df_{idx}")

                # Display suggested query buttons ONLY if this is the active latest assistant message
                if is_latest and suggested_queries:
                    _subsection("💡", "Suggested Follow-ups")
                    s_cols = st.columns(min(len(suggested_queries), 3))
                    for s_i, sug in enumerate(suggested_queries):
                        c_idx = s_i % len(s_cols)
                        s_cols[c_idx].button(
                            f"🔍 {sug}",
                            key=f"hist_sug_{idx}_{s_i}",
                            on_click=set_pending_question,
                            args=(sug,)
                        )

    # If there is an active prompt to run, execute Cortex Agent inside the Conversation block
    if st.session_state.get("active_prompt"):
        active_prompt = st.session_state.active_prompt
        st.session_state.active_prompt = None

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            preview = active_prompt.strip()[:60] + ("…" if len(active_prompt.strip()) > 60 else "")
            with st.expander(f"💬 {preview}", expanded=True):
                with st.spinner("🤖 Calling Cortex Agent..."):
                    api_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                    ]
                    events = call_agent(api_messages)
                    blocks = collect_response(events)

                latest_df = None
                active_idx = len(st.session_state.messages)

                text_parts = [b["text"] for b in blocks if b["type"] == "text" and b.get("text")]
                raw_display_text = "\n\n".join(text_parts) if text_parts else ""
                display_text = deduplicate_paragraphs(raw_display_text)

                main_t, text_sug = split_suggestions(display_text)
                if main_t:
                    _render_response_text(main_t)

                act_suggestions = list(text_sug)
                for b_idx, b in enumerate(blocks):
                    if b["type"] == "tool_results":
                        latest_df = tool_results_to_df(b["content"])
                        if latest_df is not None and not latest_df.empty:
                            _subsection("📋", "Queried Data Table")
                            styled_data = style_dataframe_metrics(latest_df, st.session_state.settings_colors)
                            st.dataframe(styled_data, use_container_width=True, key=f"act_df_{active_idx}_{b_idx}")
                    elif b["type"] == "chart":
                        # Note: "Visualization Chart" sub-heading removed as requested
                        chart_target = b.get("spec") or b.get("figure")
                        render_chart(chart_target, latest_df, key=f"act_chart_{active_idx}_{b_idx}")
                    elif b["type"] == "suggested_queries":
                        for sq in b.get("queries", []):
                            if sq not in act_suggestions:
                                act_suggestions.append(sq)

                if act_suggestions:
                    _subsection("💡", "Suggested Follow-ups")
                    s_cols = st.columns(min(len(act_suggestions), 3))
                    for s_i, sug in enumerate(act_suggestions):
                        c_idx = s_i % len(s_cols)
                        s_cols[c_idx].button(
                            f"🔍 {sug}",
                            key=f"act_sug_{active_idx}_{s_i}",
                            on_click=set_pending_question,
                            args=(sug,)
                        )

            st.session_state.messages.append({
                "role": "assistant",
                "display": display_text,
                "content": [{"type": "text", "text": display_text}],
                "blocks": blocks,
                "data": latest_df
            })

# --------------------------------------------------------------------------
# Render Sidebar PDF Export & Footer (Placed AFTER chat input execution)
# --------------------------------------------------------------------------
with st.sidebar:
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        st.divider()
        st.markdown("### 📥 Export Conversation")
        try:
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            today_dash = datetime.datetime.now().strftime("%Y-%m-%d")

            tmpl = st.session_state.get("settings_pdf_filename_template", "OEE_Conversation_Report_{YYYYMMDD}.pdf")
            pdf_fname = tmpl.replace("{YYYYMMDD}", today_str).replace("{YYYY-MM-DD}", today_dash)

            sb_pdf_bytes = generate_conversation_pdf(
                messages=st.session_state.messages,
                logo_bytes=active_logo_bytes,
                title=st.session_state.settings_header_title,
                subtitle=st.session_state.settings_header_subtitle
            )
            st.download_button(
                label="📄 Download Conversation (PDF)",
                data=sb_pdf_bytes,
                file_name=pdf_fname,
                mime="application/pdf",
                use_container_width=True,
                key="sidebar_pdf_btn"
            )
        except Exception as pdf_err:
            logger.error(f"Sidebar PDF generation error: {pdf_err}")

    st.markdown(
        f"""
        <div style="margin-top: 20px; padding-top: 14px; border-top: 1px solid {BRAND['border']};
                    font-size: 0.75rem; color: {BRAND['muted']}; text-align:center;">
            Manufacturing Analytics Assistant<br/>
        </div>
        """,
        unsafe_allow_html=True,
    )
