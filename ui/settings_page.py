"""Settings UI Component for Manufacturing OEE Application."""

import streamlit as st
import pandas as pd
from pathlib import Path


def render_settings_page():
    """Render the application settings page."""
    st.markdown("## ⚙️ Application Settings")
    st.markdown("Customize OEE targets, metric color formatting thresholds, company branding logo, and header text.")

    # Ensure session state defaults exist for settings
    if "settings_targets" not in st.session_state:
        st.session_state.settings_targets = {
            "oee": 85.0,
            "availability": 90.0,
            "performance": 95.0,
            "quality": 99.0
        }

    if "settings_colors" not in st.session_state:
        st.session_state.settings_colors = {
            "oee": {"threshold": 85.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
            "availability": {"threshold": 75.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
            "performance": {"threshold": 95.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
            "quality": {"threshold": 99.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
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

    # --- Section 1: Target Settings ---
    with st.expander("🎯 Target Settings", expanded=True):
        st.markdown("Set global benchmark targets for OEE and core components.")
        col1, col2 = st.columns(2)
        with col1:
            t_oee = st.number_input(
                "Target OEE (%)",
                min_value=0.0, max_value=100.0,
                value=float(st.session_state.settings_targets["oee"]),
                key="sett_t_oee"
            )
            t_avail = st.number_input(
                "Target Availability (%)",
                min_value=0.0, max_value=100.0,
                value=float(st.session_state.settings_targets["availability"]),
                key="sett_t_avail"
            )
        with col2:
            t_perf = st.number_input(
                "Target Performance (%)",
                min_value=0.0, max_value=100.0,
                value=float(st.session_state.settings_targets["performance"]),
                key="sett_t_perf"
            )
            t_qual = st.number_input(
                "Target Quality (%)",
                min_value=0.0, max_value=100.0,
                value=float(st.session_state.settings_targets["quality"]),
                key="sett_t_qual"
            )

        st.session_state.settings_targets = {
            "oee": t_oee,
            "availability": t_avail,
            "performance": t_perf,
            "quality": t_qual
        }

    # --- Section 2: Metric Color Selection ---
    with st.expander("🎨 Metric Colors & Thresholds (Table Highlighting)", expanded=True):
        st.markdown(
            "Configure conditional color formatting for table displays. "
            "If a metric value is greater than or equal to the threshold, it will use the **Pass Color**, otherwise the **Fail Color**."
        )

        metrics_list = [
            ("oee", "OEE (%)", 85.0),
            ("availability", "Availability (%)", 75.0),
            ("performance", "Performance (%)", 95.0),
            ("quality", "Quality (%)", 99.0)
        ]

        for m_key, m_label, default_thresh in metrics_list:
            curr_cfg = st.session_state.settings_colors.get(m_key, {
                "threshold": default_thresh,
                "pass_color": "#28a745",
                "fail_color": "#dc3545"
            })

            st.markdown(f"#### {m_label}")
            c1, c2, c3 = st.columns(3)
            with c1:
                thresh_val = st.number_input(
                    f"Threshold for {m_label}",
                    min_value=0.0, max_value=100.0,
                    value=float(curr_cfg["threshold"]),
                    key=f"color_thresh_{m_key}"
                )
            with c2:
                pass_col = st.color_picker(
                    f"Color if ≥ {thresh_val}%",
                    value=curr_cfg["pass_color"],
                    key=f"color_pass_{m_key}"
                )
            with c3:
                fail_col = st.color_picker(
                    f"Color if < {thresh_val}%",
                    value=curr_cfg["fail_color"],
                    key=f"color_fail_{m_key}"
                )

            st.session_state.settings_colors[m_key] = {
                "threshold": thresh_val,
                "pass_color": pass_col,
                "fail_color": fail_col
            }
            st.divider()

    # --- Section 3: Logo Settings ---
    with st.expander("🖼️ Company Logo Settings", expanded=True):
        st.markdown("Upload a custom logo to display in the sidebar header and PDF export reports.")
        uploaded_logo = st.file_uploader("Upload Company Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

        if uploaded_logo is not None:
            st.session_state.settings_custom_logo_bytes = uploaded_logo.getvalue()
            st.success("Custom logo updated successfully!")
            st.image(uploaded_logo, width=150, caption="Preview Uploaded Logo")
        elif st.session_state.settings_custom_logo_bytes is not None:
            st.image(st.session_state.settings_custom_logo_bytes, width=150, caption="Current Custom Logo")
            if st.button("Reset to Default Logo"):
                st.session_state.settings_custom_logo_bytes = None
                st.rerun()

    # --- Section 4: Header & Banner Settings ---
    with st.expander("🏷️ Header & Banner Text Settings", expanded=True):
        st.markdown("Customize the title and subtitle shown on the main page banner.")
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

    st.success("Settings automatically saved for this session!")
