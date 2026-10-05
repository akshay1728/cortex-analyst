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

# Standardized design tokens & typography
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Primary theme colors per dashboard
PURPLE_COLOR = "#a05c96"
GREEN_COLOR = "#25e267"
SLATE_COLOR = "#3d4b53"

OLIVE_COLOR = "#b2961d"
RED_COLOR = "#cb0d19"
BLUE_BRIGHT = "#0080FF"


def render_oee_dashboard(
    dashboard_name: str,
    start_date: str,
    end_date: str,
    line_name: str
):
    """Render the OEE Dashboard section sitting above the chat interface."""
    data = load_dashboard_metrics_from_db(dashboard_name, start_date, end_date, line_name)

    if dashboard_name and dashboard_name.lower() == "moghul":
        _render_moghul_dashboard(data, line_name)
        return

    if dashboard_name and dashboard_name.lower() == "marshmallow":
        _render_marshmallow_dashboard(data, line_name)
        return

    # Default / Molded Dashboard Layout
    _render_molded_dashboard(data, line_name)


def _render_dash_header(title: str, subtitle: str, stats: List[dict], theme_color: str):
    """Render standardized top header banner for all dashboards without extra indentation."""
    stats_html = "".join([
        f'<div class="dash-stat-item"><div class="dash-stat-val">{s["val"]:,}</div><div class="dash-stat-lbl">{s["lbl"]}</div></div>'
        for s in stats
    ])

    header_html = (
        f'<style>'
        f'.dash-header {{ display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 14px 24px; border-radius: 12px; border: 1px solid #eef0f4; box-shadow: 0 4px 14px rgba(0,0,0,0.03); margin-bottom: 18px; }}'
        f'.dash-title-box {{ display: flex; align-items: baseline; gap: 16px; }}'
        f'.dash-title {{ font-size: 2.8rem; font-weight: 800; color: {theme_color}; line-height: 1; letter-spacing: -0.5px; }}'
        f'.dash-subtitle {{ font-size: 1.05rem; color: #2b303a; font-weight: 500; }}'
        f'.dash-stats-box {{ display: flex; gap: 36px; }}'
        f'.dash-stat-item {{ text-align: center; }}'
        f'.dash-stat-val {{ font-size: 2.2rem; font-weight: 700; color: #1a1a1a; line-height: 1; }}'
        f'.dash-stat-lbl {{ font-size: 0.82rem; color: #6c757d; margin-top: 4px; }}'
        f'</style>'
        f'<div class="dash-header">'
        f'<div class="dash-title-box"><div class="dash-title">{html.escape(title)}</div><div class="dash-subtitle">{html.escape(subtitle)}</div></div>'
        f'<div class="dash-stats-box">{stats_html}</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)


def _render_marshmallow_dashboard(data: Dict[str, Any], line_name: str):
    """Render Marshmallow dashboard matching image.png specifications."""
    display_line = line_name if line_name and line_name != "All Lines" else "Belt 1"
    run_time = int(data.get("total_run_time_mins", 1227))
    lost_time = int(data.get("total_lost_time_mins", 211))
    scrap = int(data.get("scrap", 8209))

    _render_dash_header(
        title=display_line,
        subtitle="Tuesday, July 07, 2026",
        stats=[
            {"val": run_time, "lbl": "Total Run Time"},
            {"val": lost_time, "lbl": "Total Lost Time"},
            {"val": scrap, "lbl": "Scrap"}
        ],
        theme_color=BLUE_BRIGHT
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])

    # Left Column: Pounds Packed by Shift & Total OEE Gauge
    with col1:
        with st.container(border=True):
            p1 = int(data.get("pounds_packed_shift1", 12357))
            p2 = int(data.get("pounds_packed_shift2", 15338))
            p3 = int(data.get("pounds_packed_shift3", 9390))
            p_total = int(data.get("total_pounds_packed", 37085))

            df_pounds = pd.DataFrame({
                "shift": ["1st shift", "2nd shift", "3rd shift", "Total"],
                "pounds": [p1, p2, p3, p_total]
            })

            fig_pounds_bar = go.Figure()
            for idx, row in df_pounds.iterrows():
                fig_pounds_bar.add_trace(go.Bar(
                    y=[row["shift"]],
                    x=[row["pounds"]],
                    orientation="h",
                    marker_color=BLUE_BRIGHT,
                    text=[f"{int(row['pounds']):,}"],
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(color="white", size=13, family=FONT_FAMILY),
                    hoverinfo="text",
                    hovertext=f"{row['shift']}: {int(row['pounds']):,} lbs",
                    showlegend=False
                ))

            fig_pounds_bar.update_layout(
                title=dict(text="Pounds Packed by Shift", x=0.5, font=dict(size=15, color="#2b303a", family=FONT_FAMILY)),
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=210,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_pounds_bar, use_container_width=True, key="fig_marsh_pounds")

        with st.container(border=True):
            oee_val = int(data.get("overall_oee", 78))
            remaining_oee = max(0, 100 - oee_val)

            fig_gauge = go.Figure(data=[
                go.Pie(
                    values=[oee_val, remaining_oee, 100],
                    labels=["OEE", "Remaining", "Bottom"],
                    marker=dict(colors=[BLUE_BRIGHT, "#e8ecef", "rgba(0,0,0,0)"]),
                    hole=0.72,
                    sort=False,
                    direction="clockwise",
                    rotation=270,
                    showlegend=False,
                    hoverinfo="label+value",
                    textinfo="none"
                )
            ])
            fig_gauge.add_annotation(
                text=f"<b style='font-size:38px;color:#2b303a;'>{oee_val}</b>",
                x=0.5, y=0.22,
                showarrow=False,
                xref="paper", yref="paper"
            )
            fig_gauge.add_annotation(
                text="0",
                x=0.18, y=0.08,
                showarrow=False,
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )
            fig_gauge.add_annotation(
                text="100",
                x=0.82, y=0.08,
                showarrow=False,
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )
            fig_gauge.update_layout(
                title=dict(text="Total OEE", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=190,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_gauge, use_container_width=True, key="fig_marsh_gauge")

    # Middle Column: Scrap Pie Chart
    with col2:
        with st.container(border=True):
            fig_pie = go.Figure(data=[
                go.Pie(
                    labels=["Sum of Total Lbs.", "Sum of Scrap"],
                    values=[37086, 8209],
                    marker=dict(colors=[BLUE_BRIGHT, RED_COLOR]),
                    hoverinfo="label+value+percent",
                    textinfo="label+value+percent",
                    textposition="outside",
                    pull=[0, 0]
                )
            ])
            fig_pie.update_layout(
                title=dict(text="Scrap", x=0.5, font=dict(size=15, color="#2b303a", family=FONT_FAMILY)),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.15,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#495057", family=FONT_FAMILY)
                ),
                margin=dict(l=20, r=20, t=55, b=45),
                height=430,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="fig_marsh_pie")

    # Right Column: Total Run Time Stacked Bar Chart
    with col3:
        with st.container(border=True):
            times = ["Jul 06, 12AM", "Jul 06, 12PM", "Jul 07, 12AM"]
            run_pct = [72, 0, 86]
            lost_pct = [28, 0, 14]

            fig_stacked = go.Figure()
            fig_stacked.add_trace(go.Bar(
                name="Total run time",
                x=times,
                y=run_pct,
                marker_color=BLUE_BRIGHT,
                hovertemplate="<b>%{x}</b><br>Run Time: %{y}%<extra></extra>"
            ))
            fig_stacked.add_trace(go.Bar(
                name="Total lost time",
                x=times,
                y=lost_pct,
                marker_color=RED_COLOR,
                hovertemplate="<b>%{x}</b><br>Lost Time: %{y}%<extra></extra>"
            ))

            fig_stacked.update_layout(
                barmode="stack",
                title=dict(text="Total Run Time", x=0.5, y=0.96, font=dict(size=15, color="#2b303a", family=FONT_FAMILY)),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#495057", family=FONT_FAMILY)
                ),
                xaxis=dict(title="Date", showgrid=False, tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#f0f2f5",
                    range=[0, 100],
                    ticksuffix="%",
                    tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)
                ),
                margin=dict(l=10, r=10, t=50, b=65),
                height=430,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_stacked, use_container_width=True, key="fig_marsh_stacked")


def _render_moghul_dashboard(data: Dict[str, Any], line_name: str):
    """Render Moghul dashboard matching image.png specifications."""
    display_line = line_name if line_name and line_name != "All Lines" else "NID-C"
    run_time = int(data.get("total_run_time_mins", 993))
    lost_time = int(data.get("total_lost_time_mins", 444))
    trucks = int(data.get("total_shakeout_trucks", 174))

    _render_dash_header(
        title=display_line,
        subtitle="Tuesday, July 07, 2026",
        stats=[
            {"val": run_time, "lbl": "Total run time"},
            {"val": lost_time, "lbl": "Total lost time"},
            {"val": trucks, "lbl": "Total shakeout trucks"}
        ],
        theme_color=OLIVE_COLOR
    )

    st.markdown(
        f"""
        <style>
        .shift-box-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .shift-lbl {{
            font-size: 0.92rem;
            color: #495057;
            font-family: {FONT_FAMILY};
        }}
        .shift-val-badge {{
            background-color: {OLIVE_COLOR};
            color: white;
            font-weight: 700;
            font-size: 1.25rem;
            padding: 8px 24px;
            border-radius: 4px;
            min-width: 120px;
            text-align: center;
        }}
        .shift-val-badge-total {{
            background-color: {OLIVE_COLOR};
            color: white;
            font-weight: 700;
            font-size: 1.35rem;
            padding: 10px;
            border-radius: 4px;
            width: 100%;
            text-align: center;
            margin-top: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 1.3, 1])

    # Left Column: Boards Cast & Total OEE Gauge
    with col1:
        with st.container(border=True):
            st.markdown(f'<div style="text-align:center; font-weight:600; font-size:1.05rem; color:#2b303a; font-family:{FONT_FAMILY}; margin-bottom:12px;">Boards Cast</div>', unsafe_allow_html=True)
            b1 = int(data.get("boards_cast_shift1", 7020))
            b2 = int(data.get("boards_cast_shift2", 7218))
            b3 = int(data.get("boards_cast_shift3", 7225))
            b_total = int(data.get("total_boards", 21463))

            st.markdown(
                f"""
                <div class="shift-box-row">
                    <span class="shift-lbl">1st shift</span>
                    <span class="shift-val-badge">{b1:,}</span>
                </div>
                <div class="shift-box-row">
                    <span class="shift-lbl">2nd shift</span>
                    <span class="shift-val-badge">{b2:,}</span>
                </div>
                <div class="shift-box-row">
                    <span class="shift-lbl">3rd shift</span>
                    <span class="shift-val-badge">{b3:,}</span>
                </div>
                <div class="shift-box-row" style="margin-top:14px;">
                    <span class="shift-lbl">Total Boards</span>
                </div>
                <div class="shift-val-badge-total">{b_total:,}</div>
                """,
                unsafe_allow_html=True
            )

        with st.container(border=True):
            oee_val = float(data.get("overall_oee", 54.00))
            remaining_oee = max(0.0, 100.0 - oee_val)

            fig_gauge = go.Figure(data=[
                go.Pie(
                    values=[oee_val, remaining_oee, 100.0],
                    labels=["OEE", "Remaining", "Bottom"],
                    marker=dict(colors=[OLIVE_COLOR, "#f0f0f8", "rgba(0,0,0,0)"]),
                    hole=0.72,
                    sort=False,
                    direction="clockwise",
                    rotation=270,
                    showlegend=False,
                    hoverinfo="label+value",
                    textinfo="none"
                )
            ])
            fig_gauge.add_annotation(
                text=f"<b style='font-size:38px;color:#2b303a;'>{oee_val:.2f}</b>",
                x=0.5, y=0.22,
                showarrow=False,
                xref="paper", yref="paper"
            )
            fig_gauge.add_annotation(
                text="0.00",
                x=0.18, y=0.08,
                showarrow=False,
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )
            fig_gauge.add_annotation(
                text="100.00",
                x=0.82, y=0.08,
                showarrow=False,
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )
            fig_gauge.update_layout(
                title=dict(text="Total OEE", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=190,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_gauge, use_container_width=True, key="fig_moghul_gauge")

    # Middle Column: 100% Stacked bar chart for Total shift run time and Total lost time
    with col2:
        with st.container(border=True):
            times = ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"]
            run_pct = [59, 0, 0, 0, 69]
            lost_pct = [41, 0, 0, 0, 31]

            fig_stacked = go.Figure()
            fig_stacked.add_trace(go.Bar(
                name="Total shift run time",
                x=times,
                y=run_pct,
                marker_color=OLIVE_COLOR,
                hovertemplate="<b>%{x}</b><br>Run Time: %{y}%<extra></extra>"
            ))
            fig_stacked.add_trace(go.Bar(
                name="Total lost time",
                x=times,
                y=lost_pct,
                marker_color=RED_COLOR,
                hovertemplate="<b>%{x}</b><br>Lost Time: %{y}%<extra></extra>"
            ))

            fig_stacked.update_layout(
                barmode="stack",
                title=dict(text="Total shift run time and Total lost time", x=0.5, y=0.96, font=dict(size=14, color="#2b303a", family=FONT_FAMILY)),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#495057", family=FONT_FAMILY)
                ),
                xaxis=dict(title="Date", showgrid=False, tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#f0f2f5",
                    range=[0, 100],
                    ticksuffix="%",
                    tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)
                ),
                margin=dict(l=10, r=10, t=50, b=65),
                height=430,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_stacked, use_container_width=True, key="fig_moghul_stacked")

    # Right Column: Total Shakeout Trucks
    with col3:
        with st.container(border=True):
            df_trucks = pd.DataFrame({
                "day": ["6", "7"],
                "trucks": [144, 174]
            })

            fig_trucks = go.Figure()
            fig_trucks.add_trace(go.Bar(
                x=df_trucks["day"],
                y=df_trucks["trucks"],
                marker_color=OLIVE_COLOR,
                width=0.45,
                hovertemplate="Day %{x}<br>Trucks: %{y}<extra></extra>"
            ))
            fig_trucks.update_layout(
                title=dict(text="Total shakeout trucks", x=0.5, font=dict(size=15, color="#2b303a", family=FONT_FAMILY)),
                xaxis=dict(title="Day<br>July / Qtr 3 / 2026", showgrid=False, tickfont=dict(size=11, color="#2b303a", family=FONT_FAMILY)),
                yaxis=dict(title="Total trucks", showgrid=True, gridcolor="#f0f2f5", tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=30),
                height=430,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_trucks, use_container_width=True, key="fig_moghul_trucks")


def _render_molded_dashboard(data: Dict[str, Any], line_name: str):
    """Render Molded dashboard layout with consistent top header banner."""
    display_line = line_name if line_name and line_name != "All Lines" else "Molded Line"
    run_time = int(data.get("total_run_time_mins", 633))
    lost_time = int(data.get("total_lost_time_mins", 343))
    pounds_sum = int(data.get("total_pounds_running_sum", 24905))

    _render_dash_header(
        title=display_line,
        subtitle="Tuesday, July 07, 2026",
        stats=[
            {"val": run_time, "lbl": "Total Run Time (Mins)"},
            {"val": lost_time, "lbl": "Total Lost Time (Mins)"},
            {"val": pounds_sum, "lbl": "Total Pounds (Lbs)"}
        ],
        theme_color=PURPLE_COLOR
    )

    col1, col2, col3 = st.columns([1, 1.1, 1])

    # --------------------------------------------------------------------------
    # COLUMN 1: TOTAL POUNDS (Horizontal Bar + Curved Area)
    # --------------------------------------------------------------------------
    with col1:
        with st.container(border=True):
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
                    textfont=dict(color="white" if row["color"] == PURPLE_COLOR and row['pounds'] > 0 else "black", size=13, family=FONT_FAMILY),
                    hoverinfo="text",
                    hovertext=f"{row['shift']}: {int(row['pounds']):,} lbs",
                    showlegend=False
                ))

            fig_pounds_bar.update_layout(
                title=dict(text="Total Pounds", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=200,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_pounds_bar, use_container_width=True, key="fig_pounds_bar_main")

        with st.container(border=True):
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
                title=dict(text="Total Pounds Trend", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                margin=dict(l=10, r=10, t=55, b=20),
                height=190,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_pounds_area, use_container_width=True, key="fig_pounds_area_main")

    # --------------------------------------------------------------------------
    # COLUMN 2: TOTAL RUN TIME (100% Stacked Bar)
    # --------------------------------------------------------------------------
    with col2:
        with st.container(border=True):
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
                title=dict(text="Total Run Time vs Lost Time", x=0.5, y=0.96, font=dict(size=15, color="#2b303a", family=FONT_FAMILY)),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#6c757d", family=FONT_FAMILY)
                ),
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#f0f2f5",
                    range=[0, 100],
                    ticksuffix="%",
                    tickfont=dict(size=10, color="#6c757d", family=FONT_FAMILY)
                ),
                margin=dict(l=10, r=10, t=50, b=65),
                height=410,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_stacked, use_container_width=True, key="fig_stacked_main")

    # --------------------------------------------------------------------------
    # COLUMN 3: OEE (Horizontal Bar + Gauge)
    # --------------------------------------------------------------------------
    with col3:
        with st.container(border=True):
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
                    textfont=dict(color="white" if row['oee'] > 0 else "black", size=13, family=FONT_FAMILY),
                    hoverinfo="text",
                    hovertext=f"{row['shift']}: OEE {row['oee']}%",
                    showlegend=False
                ))

            fig_oee_bar.update_layout(
                title=dict(text="Shift OEE", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(autorange="reversed", tickfont=dict(size=12, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=200,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_oee_bar, use_container_width=True, key="fig_oee_bar_main")

        with st.container(border=True):
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
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )
            fig_gauge.add_annotation(
                text="100",
                x=0.82, y=0.08,
                showarrow=False,
                font=dict(size=11, color="#6c757d", family=FONT_FAMILY),
                xref="paper", yref="paper"
            )

            fig_gauge.update_layout(
                title=dict(text="Total OEE", x=0.5, font=dict(size=16, color="#2b303a", family=FONT_FAMILY)),
                margin=dict(l=10, r=10, t=55, b=10),
                height=190,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_gauge, use_container_width=True, key="fig_oee_gauge_main")


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
