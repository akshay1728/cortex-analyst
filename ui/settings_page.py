"""Settings UI Component for Manufacturing OEE Application."""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from services.settings_service import (
    load_suggested_questions_from_db,
    save_suggested_question_to_db,
    delete_suggested_question_from_db,
    load_app_settings_from_db,
    save_app_setting_to_db,
    save_app_logo_to_db
)


# --------------------------------------------------------------------------
# Flash messages: st.success()/st.warning() right before st.rerun() never
# gets a chance to paint, since the rerun tears down the script before the
# browser renders that frame. Stash the message in session state instead and
# show it on the run that follows the rerun.
# --------------------------------------------------------------------------
def _flash(kind: str, message: str):
    st.session_state["_settings_flash"] = (kind, message)


def _render_flash():
    flash = st.session_state.pop("_settings_flash", None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message)


def _spacer():
    """A single short spacer to align a button with the input beside it,
    in place of a pair of st.write("") calls."""
    st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)


def render_settings_page():
    """Render the application settings page."""
    st.markdown('<div class="section-label">⚙️ Application Settings</div>', unsafe_allow_html=True)
    st.caption("Configure suggested questions, application parameters, Cortex Agent DB settings, company logo, and header text.")

    _render_flash()

    # Load suggested questions and settings from DB
    if "db_questions_loaded" not in st.session_state or st.session_state.get("suggested_questions_list") is None:
        db_qs = load_suggested_questions_from_db()
        st.session_state.suggested_questions_list = db_qs
        st.session_state.db_questions_loaded = True

    if "db_settings_loaded" not in st.session_state:
        db_res = load_app_settings_from_db()
        db_sets = db_res.get("settings", {})

        st.session_state.settings_header_title = db_sets.get("header_title") or "OEE AI Assistant"
        st.session_state.settings_header_subtitle = db_sets.get("header_subtitle") or "Ask natural language questions about plant performance, equipment availability, line productivity, and downtime root causes — powered by Cortex Analyst."
        st.session_state.settings_pdf_filename_template = db_sets.get("pdf_filename_template") or "OEE_Conversation_Report_{YYYYMMDD}.pdf"
        st.session_state.settings_semantic_view = db_sets.get("semantic_view") or "JBEDW_DEV.ANALYTICS_OPERATIONS.SVW_TRAKSYS"
        st.session_state.settings_warehouse_name = db_sets.get("warehouse_name") or "WH_APPS"
        st.session_state.settings_analyst_tool_name = db_sets.get("analyst_tool_name") or "traksys_analyst"
        st.session_state.settings_orchestration_model = db_sets.get("orchestration_model") or "claude-sonnet-4-5"
        st.session_state.settings_history_count = int(db_sets.get("history_count") or 10)

        if db_res.get("logo_bytes") is not None:
            st.session_state.settings_custom_logo_bytes = db_res["logo_bytes"]

        st.session_state.db_settings_loaded = True

    tab_questions, tab_logo, tab_connection, tab_header = st.tabs([
        "💡 Suggested Questions",
        "🖼️ Logo",
        "⚙️ Connection & Agent",
        "🏷️ Header & Banner",
    ])

    # --- Suggested Questions Management (DB Backed) ---
    with tab_questions:
        top_col1, top_col2 = st.columns([7, 3])
        with top_col1:
            st.caption("Manage the sample questions shown at the top of the chat assistant. Questions are fetched from and stored in the database.")
        with top_col2:
            if st.button("🔄 Reload from DB", key="reload_sq_btn", use_container_width=True):
                # Existing text_input/number_input widgets are keyed, so
                # Streamlit ignores value= on later runs unless their keys
                # are cleared first — otherwise "reload" just redisplays
                # whatever was last typed instead of the DB's rows.
                for k in list(st.session_state.keys()):
                    if k.startswith("sq_text_in_") or k.startswith("sq_order_in_"):
                        del st.session_state[k]
                st.session_state.suggested_questions_list = load_suggested_questions_from_db()
                _flash("success", "Refreshed questions from database.")
                st.rerun()

        sq_list = st.session_state.get("suggested_questions_list", [])

        if sq_list:
            st.markdown("##### Existing questions")
            for idx, q_obj in enumerate(sq_list):
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1:
                    q_text_input = st.text_input(
                        f"Question #{idx+1} (ID: {q_obj.get('id', 'New')})",
                        value=q_obj["text"],
                        key=f"sq_text_in_{q_obj.get('id', idx)}_{idx}"
                    )
                with c2:
                    q_order_input = st.number_input(
                        "Order",
                        min_value=1,
                        max_value=100,
                        value=int(q_obj.get("order", idx+1)),
                        key=f"sq_order_in_{q_obj.get('id', idx)}_{idx}"
                    )
                with c3:
                    _spacer()
                    if st.button("❌ Remove", key=f"sq_del_{q_obj.get('id', idx)}_{idx}"):
                        if q_obj.get("id"):
                            delete_suggested_question_from_db(q_obj["id"])
                        st.session_state.suggested_questions_list.pop(idx)
                        _flash("success", "Question removed.")
                        st.rerun()

                sq_list[idx]["text"] = q_text_input
                sq_list[idx]["order"] = q_order_input
        else:
            st.info("No suggested questions found in the database. Add a new question below.")

        st.divider()
        st.markdown("##### ➕ Add new question")
        new_c1, new_c2 = st.columns([8, 2])
        with new_c1:
            new_q_text = st.text_input("New Question Text", key="new_sq_text_input")
        with new_c2:
            _spacer()
            if st.button("➕ Add Question", key="add_sq_btn", use_container_width=True):
                if new_q_text.strip():
                    new_order = len(sq_list) + 1
                    save_suggested_question_to_db(None, new_q_text.strip(), new_order)
                    st.session_state.suggested_questions_list = load_suggested_questions_from_db()
                    _flash("success", "New question added to database!")
                    st.rerun()
                else:
                    st.warning("Please enter question text.")

    # --- Hidden Metric Colors Section (Hidden for now as requested) ---
    HIDE_METRIC_COLORS = True
    if not HIDE_METRIC_COLORS:
        with st.expander("🎨 Metric Colors & Thresholds (Table Highlighting)", expanded=False):
            st.markdown(
                "Configure conditional color formatting for table displays. "
                "By default, metric color highlighting is disabled. Toggle to enable for each metric."
            )

            metrics_list = [
                ("oee", "OEE (%)", 85.0),
                ("availability", "Availability (%)", 75.0),
                ("performance", "Performance (%)", 95.0),
                ("quality", "Quality (%)", 99.0)
            ]

            for m_key, m_label, default_thresh in metrics_list:
                curr_cfg = st.session_state.settings_colors.get(m_key, {
                    "enabled": False,
                    "threshold": default_thresh,
                    "pass_color": "#28a745",
                    "fail_color": "#dc3545"
                })

                st.markdown(f"#### {m_label}")
                m_enabled = st.toggle(f"Enable color highlighting for {m_label}", value=curr_cfg.get("enabled", False), key=f"color_enable_{m_key}")

                c1, c2, c3 = st.columns(3)
                with c1:
                    thresh_val = st.number_input(
                        f"Threshold for {m_label}",
                        min_value=0.0, max_value=100.0,
                        value=float(curr_cfg.get("threshold", default_thresh)),
                        key=f"color_thresh_{m_key}"
                    )
                with c2:
                    pass_col = st.color_picker(
                        f"Color if ≥ {thresh_val}%",
                        value=curr_cfg.get("pass_color", "#28a745"),
                        key=f"color_pass_{m_key}"
                    )
                with c3:
                    fail_col = st.color_picker(
                        f"Color if < {thresh_val}%",
                        value=curr_cfg.get("fail_color", "#dc3545"),
                        key=f"color_fail_{m_key}"
                    )

                st.session_state.settings_colors[m_key] = {
                    "enabled": m_enabled,
                    "threshold": thresh_val,
                    "pass_color": pass_col,
                    "fail_color": fail_col
                }
                st.divider()

    # --- Company Logo Settings (DB Backed) ---
    with tab_logo:
        st.caption("Upload a custom logo stored in the database to display in the sidebar header and PDF export reports.")
        uploaded_logo = st.file_uploader("Upload Company Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

        if uploaded_logo is not None:
            logo_bytes = uploaded_logo.getvalue()
            st.session_state.settings_custom_logo_bytes = logo_bytes
            save_app_logo_to_db(logo_bytes)
            st.success("Custom logo uploaded & saved to Database!")
            st.image(uploaded_logo, width=150, caption="Preview Uploaded Logo")
        elif st.session_state.settings_custom_logo_bytes is not None:
            st.image(st.session_state.settings_custom_logo_bytes, width=150, caption="Current Custom Logo")
            if st.button("Reset to Default Logo"):
                st.session_state.settings_custom_logo_bytes = None
                save_app_setting_to_db("COMPANY_LOGO", "")
                _flash("success", "Logo reset to default.")
                st.rerun()

    # --- Cortex Agent & Database Configuration ---
    with tab_connection:
        st.caption("Configure Snowflake DB parameters, Cortex Agent models, tools, and history limit.")

        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            sem_view = st.text_input(
                "Semantic View Name",
                value=st.session_state.settings_semantic_view,
                key="sett_sem_view"
            )
            wh_name = st.text_input(
                "Warehouse Name",
                value=st.session_state.settings_warehouse_name,
                key="sett_wh_name"
            )
            analyst_name = st.text_input(
                "Cortex Analyst Tool Name",
                value=st.session_state.settings_analyst_tool_name,
                key="sett_analyst_name"
            )
        with col_cfg2:
            model_name = st.text_input(
                "Orchestration Model Name",
                value=st.session_state.settings_orchestration_model,
                key="sett_model_name"
            )
            hist_count = st.number_input(
                "Historical Response Context Count",
                min_value=1, max_value=50,
                value=int(st.session_state.settings_history_count),
                key="sett_hist_count"
            )
            pdf_template = st.text_input(
                "PDF Export Filename Template",
                value=st.session_state.settings_pdf_filename_template,
                help="Placeholders like {YYYYMMDD} or {YYYY-MM-DD} will be auto-replaced with current date.",
                key="sett_pdf_template"
            )

        st.session_state.settings_semantic_view = sem_view
        st.session_state.settings_warehouse_name = wh_name
        st.session_state.settings_analyst_tool_name = analyst_name
        st.session_state.settings_orchestration_model = model_name
        st.session_state.settings_history_count = hist_count
        st.session_state.settings_pdf_filename_template = pdf_template

    # --- Header & Banner Settings ---
    with tab_header:
        st.caption("Customize the title and subtitle shown on the main page banner.")
        h_title = st.text_input(
            "Banner Title",
            value=st.session_state.settings_header_title,
            key="sett_header_title"
        )
        h_subtitle = st.text_area(
            "Banner Subtitle",
            value=st.session_state.settings_header_subtitle,
            key="sett_header_subtitle"
        )

        st.session_state.settings_header_title = h_title
        st.session_state.settings_header_subtitle = h_subtitle

    st.write("")
    if st.button("💾 Save All Settings to Database", type="primary"):
        # Save suggested questions to DB
        for q_item in st.session_state.get("suggested_questions_list", []):
            save_suggested_question_to_db(q_item.get("id"), q_item["text"], q_item.get("order", 1))

        # Save settings key-values to DB
        save_app_setting_to_db("HEADER_TITLE", st.session_state.settings_header_title)
        save_app_setting_to_db("HEADER_SUBTITLE", st.session_state.settings_header_subtitle)
        save_app_setting_to_db("PDF_FILENAME_TEMPLATE", st.session_state.settings_pdf_filename_template)
        save_app_setting_to_db("SEMANTIC_VIEW", st.session_state.settings_semantic_view)
        save_app_setting_to_db("WAREHOUSE_NAME", st.session_state.settings_warehouse_name)
        save_app_setting_to_db("ANALYST_TOOL_NAME", st.session_state.settings_analyst_tool_name)
        save_app_setting_to_db("ORCHESTRATION_MODEL", st.session_state.settings_orchestration_model)
        save_app_setting_to_db("HISTORY_COUNT", st.session_state.settings_history_count)

        if st.session_state.settings_custom_logo_bytes is not None:
            save_app_logo_to_db(st.session_state.settings_custom_logo_bytes)

        _flash("success", "All settings & suggested questions saved successfully to database!")
        st.rerun()
