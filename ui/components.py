"""UI Components for Manufacturing OEE Conversational Analytics App."""

import html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Optional
from services.settings_service import (
    load_dashboard_types_from_db,
    load_production_lines_from_db,
    load_dashboard_metrics_from_db
)

# Brand tokens for dashboard and charts
CARD_BG = "#FFFFFF"
PURPLE_COLOR = "#a05c96"
GREEN_COLOR = "#25e267"
SLATE_COLOR = "#3d4b53"
GRAY_LIGHT = "#e8ecef"


def render_oee_dashboard(
    dashboard_name: str,
    start_date: str,
    end_date: str,
    line_name: str
):
    """Render the OEE Dashboard section sitting above the chat interface.

    Contains 3 vertical column sections matching image.png:
    - Left Column:
        1. Total Pounds (Horizontal Bar Chart for Shifts + Running Sum)
        2. Total Pounds (Curved Area Chart over time)
    - Middle Column:
        1. Total Run Time & Lost Time KPI cards (633 Mins vs 343 Mins)
        2. Total Run Time (100% Stacked Bar Chart comparing Run vs Lost time per time interval)
    - Right Column:
        1. OEE (Horizontal Bar Chart for Shifts)
        2. OEE Gauge Chart (Half-donut gauge displaying Overall OEE)
    """
    data = load_dashboard_metrics_from_db(dashboard_name, start_date, end_date, line_name)

    # CSS for dashboard container styling
    st.markdown(
        """
        <style>
        .dash-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
            border: 1px solid #eef0f4;
            margin-bottom: 16px;
        }
        .kpi-header-box {
            display: flex;
            justify-content: space-around;
            align-items: center;
            background-color: #ffffff;
            border-radius: 10px;
            padding: 10px 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
            border: 1px solid #eef0f4;
            margin-bottom: 12px;
        }
        .kpi-stat-item {
            text-align: center;
        }
        .kpi-stat-val {
            font-size: 1.8rem;
            font-weight: 700;
            color: #2b303a;
            line-height: 1.1;
        }
        .kpi-stat-lbl {
            font-size: 0.8rem;
            color: #6c757d;
            font-weight: 500;
            margin-top: 2px;
        }
        .kpi-divider {
            width: 1px;
            height: 36px;
            background-color: #dce1e7;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 1.1, 1])

    # --------------------------------------------------------------------------
    # COLUMN 1: TOTAL POUNDS (Horizontal Bar + Curved Area)
    # --------------------------------------------------------------------------
    with col1:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # Total Pounds Horizontal Bar
        df_pounds = pd.DataFrame({
            "shift": ["1st shift", "2nd shift", "3rd shift", "Running sum"],
            "pounds": [
                data.get("total_pounds_shift1", 15444),
                data.get("total_pounds_shift2", 9461),
                data.get("total_pounds_shift3", 0),
                data.get("total_pounds_running_sum", 24905)
            ],
            "color": [PURPLE_COLOR, PURPLE_COLOR, PURPLE_COLOR, GREEN_COLOR]
        })

        fig_pounds_bar = go.Figure()
        for idx, row in df_pounds.iterrows():
            fig_pounds_bar.add_trace(go.Bar(
                y=[row["shift"]],
                x=[row["pounds"]],
                orientation="h",
                marker_color=row["color"],
                text=[f"{int(row['pounds']):,}" if row['pounds'] > 0 else "0"],
                textposition="inside" if row['pounds'] > 0 else "outside",
                insidetextanchor="middle",
                textfont=dict(color="white" if row["color"] == PURPLE_COLOR and row['pounds'] > 0 else "black", size=13, family="sans-serif"),
                hoverinfo="text",
                hovertext=f"{row['shift']}: {int(row['pounds']):,} lbs",
                showlegend=False
            ))

        fig_pounds_bar.update_layout(
            title=dict(text="Total Pounds", x=0.5, font=dict(size=16, color="#2b303a")),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#2b303a", family="sans-serif")),
            margin=dict(l=10, r=10, t=35, b=10),
            height=180,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_pounds_bar, use_container_width=True, key="fig_pounds_bar_main")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # Total Pounds Area Chart
        df_area = pd.DataFrame({
            "time": ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"],
            "val": [5000, 7200, 15444, 22000, data.get("total_pounds_running_sum", 24905)]
        })

        fig_pounds_area = go.Figure()
        fig_pounds_area.add_trace(go.Scatter(
            x=df_area["time"],
            y=df_area["val"],
            fill="tozeroy",
            mode="lines",
            line_shape="spline",
            line=dict(color=PURPLE_COLOR, width=2.5),
            fillcolor="rgba(160, 92, 150, 0.45)",
            hoverinfo="x+y",
            hovertemplate="<b>%{x}</b><br>Pounds: %{y:,}<extra></extra>"
        ))
        fig_pounds_area.update_layout(
            title=dict(text="Total Pounds", x=0.5, font=dict(size=16, color="#2b303a")),
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6c757d")),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            margin=dict(l=10, r=10, t=35, b=20),
            height=170,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_pounds_area, use_container_width=True, key="fig_pounds_area_main")
        st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # COLUMN 2: TOTAL RUN TIME (KPI Header + 100% Stacked Bar)
    # --------------------------------------------------------------------------
    with col2:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # KPI Header Cards
        st.markdown(
            f"""
            <div class="kpi-header-box">
                <div class="kpi-stat-item">
                    <div class="kpi-stat-val">{int(data.get('total_run_time_mins', 633))}</div>
                    <div class="kpi-stat-lbl">Total Run Time</div>
                </div>
                <div class="kpi-divider"></div>
                <div class="kpi-stat-item">
                    <div class="kpi-stat-val">{int(data.get('total_lost_time_mins', 343))}</div>
                    <div class="kpi-stat-lbl">Total Lost Time</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Stacked 100% Bar Chart
        times = ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"]
        run_pct = [62, 64, 64, 64, 62]
        lost_pct = [38, 36, 36, 36, 38]

        fig_stacked = go.Figure()
        fig_stacked.add_trace(go.Bar(
            name="Sum of Total run time",
            x=times,
            y=run_pct,
            marker_color=PURPLE_COLOR,
            hovertemplate="<b>%{x}</b><br>Run Time: %{y}%<extra></extra>"
        ))
        fig_stacked.add_trace(go.Bar(
            name="Sum of Total lost time",
            x=times,
            y=lost_pct,
            marker_color=SLATE_COLOR,
            hovertemplate="<b>%{x}</b><br>Lost Time: %{y}%<extra></extra>"
        ))

        fig_stacked.update_layout(
            barmode="stack",
            title=dict(text="Total Run Time", x=0.5, font=dict(size=16, color="#2b303a")),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=11, color="#6c757d")
            ),
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6c757d")),
            yaxis=dict(
                showgrid=True,
                gridcolor="#f0f2f5",
                range=[0, 100],
                ticksuffix="%",
                tickfont=dict(size=10, color="#6c757d")
            ),
            margin=dict(l=10, r=10, t=50, b=20),
            height=305,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_stacked, use_container_width=True, key="fig_stacked_main")
        st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # COLUMN 3: OEE (Horizontal Bar + Gauge)
    # --------------------------------------------------------------------------
    with col3:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # OEE Horizontal Bar
        df_oee = pd.DataFrame({
            "shift": ["1st shift", "2nd shift", "3rd shift"],
            "oee": [
                int(data.get("oee_shift1", 60)),
                int(data.get("oee_shift2", 36)),
                int(data.get("oee_shift3", 0))
            ]
        })

        fig_oee_bar = go.Figure()
        for idx, row in df_oee.iterrows():
            fig_oee_bar.add_trace(go.Bar(
                y=[row["shift"]],
                x=[row["oee"]],
                orientation="h",
                marker_color=PURPLE_COLOR,
                text=[f"{row['oee']}" if row['oee'] > 0 else "0"],
                textposition="inside" if row['oee'] > 0 else "outside",
                insidetextanchor="middle",
                textfont=dict(color="white" if row['oee'] > 0 else "black", size=13, family="sans-serif"),
                hoverinfo="text",
                hovertext=f"{row['shift']}: OEE {row['oee']}%",
                showlegend=False
            ))

        fig_oee_bar.update_layout(
            title=dict(text="OEE", x=0.5, font=dict(size=16, color="#2b303a")),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#2b303a", family="sans-serif")),
            margin=dict(l=10, r=10, t=35, b=10),
            height=180,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_oee_bar, use_container_width=True, key="fig_oee_bar_main")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        # OEE Half Gauge Chart
        overall_oee_val = int(data.get("overall_oee", 47))
        remaining_oee = max(0, 100 - overall_oee_val)

        fig_gauge = go.Figure(data=[
            go.Pie(
                values=[overall_oee_val, remaining_oee, 100],
                labels=["OEE", "Remaining", "Bottom"],
                marker=dict(colors=[PURPLE_COLOR, "#e9ecef", "rgba(0,0,0,0)"]),
                hole=0.72,
                sort=False,
                direction="clockwise",
                rotation=270,
                showlegend=False,
                hoverinfo="label+value",
                textinfo="none"
            )
        ])

        # Add text annotation inside gauge
        fig_gauge.add_annotation(
            text=f"<b style='font-size:36px;color:#2b303a;'>{overall_oee_val}</b>",
            x=0.5, y=0.25,
            showarrow=False,
            xref="paper", yref="paper"
        )
        fig_gauge.add_annotation(
            text="0",
            x=0.18, y=0.08,
            showarrow=False,
            font=dict(size=11, color="#6c757d"),
            xref="paper", yref="paper"
        )
        fig_gauge.add_annotation(
            text="100",
            x=0.82, y=0.08,
            showarrow=False,
            font=dict(size=11, color="#6c757d"),
            xref="paper", yref="paper"
        )

        fig_gauge.update_layout(
            title=dict(text="OEE", x=0.5, font=dict(size=16, color="#2b303a")),
            margin=dict(l=10, r=10, t=35, b=10),
            height=170,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_gauge, use_container_width=True, key="fig_oee_gauge_main")
        st.markdown('</div>', unsafe_allow_html=True)


def render_sample_questions(on_click_callback):
    """Render quick sample question buttons dynamically loaded strictly from DB or session state."""
    sq_list = st.session_state.get("suggested_questions_list", [])
    if sq_list:
        sample_questions = [q_obj["text"] for q_obj in sq_list if isinstance(q_obj, dict) and q_obj.get("text")]
    else:
        sample_questions = []

    if not sample_questions:
        st.info("No suggested questions are set up yet. Add some on the Settings page.")
        return

    col_count = min(len(sample_questions), 3)
    cols = st.columns(col_count)
    for idx, q in enumerate(sample_questions):
        cols[idx % col_count].button(
            q,
            key=f"sq_{idx}",
            use_container_width=False,
            on_click=on_click_callback,
            args=(q,)
        )


def style_dataframe_metrics(df: pd.DataFrame, metric_colors: dict):
    """Apply background color styling to DataFrame columns matching metric thresholds."""
    if df is None or df.empty:
        return df

    metric_aliases = {
        "oee": ["oee", "oee_pct", "oee_percentage", "overall_oee"],
        "availability": ["availability", "avail", "availability_pct", "availability_percentage"],
        "performance": ["performance", "perf", "performance_pct", "performance_percentage"],
        "quality": ["quality", "qual", "quality_pct", "quality_percentage"]
    }

    styled = df.style

    for m_key, color_cfg in metric_colors.items():
        if not color_cfg.get("enabled", False):
            continue

        thresh = float(color_cfg.get("threshold", 85.0))
        pass_col = color_cfg.get("pass_color", "#28a745")
        fail_col = color_cfg.get("fail_color", "#dc3545")

        aliases = metric_aliases.get(m_key, [m_key])

        matched_cols = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(alias in col_lower for alias in aliases):
                matched_cols.append(col)

        for col in matched_cols:
            def cell_styler(val, threshold=thresh, pass_c=pass_col, fail_c=fail_col):
                try:
                    num_val = float(val)
                    if num_val <= 1.0 and threshold > 1.0:
                        num_val = num_val * 100.0
                    bg_color = pass_c if num_val >= threshold else fail_c
                    return f'background-color: {bg_color}; color: white; font-weight: bold;'
                except (ValueError, TypeError):
                    return ''

            styled = styled.map(cell_styler, subset=[col])

    return styled
