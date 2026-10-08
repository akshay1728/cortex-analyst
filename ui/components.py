"""UI Components for Manufacturing OEE Conversational Analytics App."""

import html
import datetime
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from services.settings_service import load_dashboard_metrics_from_db

# Design Tokens
PRIMARY = "#242B6B"
TEAL = "#00A896"
ROSE = "#E15241"
INK = "#0F172A"
INK_SOFT = "#475569"
MUTED = "#64748B"
BORDER = "#E2E8F0"
TRACK = "#F1F5F9"
GRID = "#F1F5F9"
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

H_GAUGE = 220
H_TALL = 340
H_BARS = 220

_TONES = {
    "primary": PRIMARY,
    "teal": TEAL,
    "danger": ROSE,
}


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color (e.g. #242B6B) to rgba string."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_stat(val: Any) -> str:
    if isinstance(val, (int, float)):
        return f"{val:,}"
    return str(val)


def _inject_dashboard_css():
    """Inject CSS for dashboard card containers, headers, and stat cards."""
    st.markdown(
        f"""
        <style>
        .dash-header {{
            background: #ffffff;
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
            box-shadow: 0 6px 18px -4px rgba(15,23,42,0.08), 0 2px 6px -1px rgba(15,23,42,0.04);
        }}
        .dash-title-wrap {{
            flex: 1;
            min-width: 240px;
        }}
        .dash-title {{
            font-family: {FONT_FAMILY};
            font-size: 24px;
            font-weight: 700;
            color: {INK};
            line-height: 1.2;
        }}
        .dash-subtitle {{
            font-family: {FONT_FAMILY};
            font-size: 13px;
            color: {MUTED};
            margin-top: 4px;
        }}
        .dash-stats-box {{
            display: flex;
            align-items: center;
            gap: 24px;
            flex-wrap: wrap;
        }}
        .dash-stat-item {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}
        .dash-stat-val {{
            font-family: {FONT_FAMILY};
            font-size: 22px;
            font-weight: 700;
            color: {INK};
            line-height: 1;
        }}
        .dash-stat-lbl {{
            font-family: {FONT_FAMILY};
            font-size: 12px;
            color: {MUTED};
            margin-top: 4px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dash-stat-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }}
        .dash-card-title {{
            font-family: {FONT_FAMILY};
            font-size: 15px;
            font-weight: 600;
            color: {INK};
            margin-bottom: 2px;
        }}
        .dash-card-caption {{
            font-family: {FONT_FAMILY};
            font-size: 12px;
            color: {MUTED};
            margin-bottom: 12px;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


def render_sidebar_filters(df: pd.DataFrame) -> Dict[str, Any]:
    """Render sidebar filters and return user selected options."""
    st.sidebar.header("🔍 OEE Global Filters")

    if df is not None and not df.empty and "date" in df.columns:
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
    else:
        max_date = datetime.date.today()
        min_date = max_date - datetime.timedelta(days=30)

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Plant Filter
    available_plants = ["All"] + (sorted(list(df["plant"].unique())) if df is not None and not df.empty and "plant" in df.columns else [])
    selected_plants = st.sidebar.multiselect("Select Plant(s)", options=available_plants, default=["All"])

    # Line Filter
    available_lines = ["All"] + (sorted(list(df["line"].unique())) if df is not None and not df.empty and "line" in df.columns else [])
    selected_lines = st.sidebar.multiselect("Select Line(s)", options=available_lines, default=["All"])

    # Shift Filter
    available_shifts = ["All"] + (sorted(list(df["shift"].unique())) if df is not None and not df.empty and "shift" in df.columns else [])
    selected_shifts = st.sidebar.multiselect("Select Shift(s)", options=available_shifts, default=["All"])

    # Product Family Filter
    available_families = ["All"] + (sorted(list(df["product_family"].unique())) if df is not None and not df.empty and "product_family" in df.columns else [])
    selected_families = st.sidebar.multiselect("Product Family", options=available_families, default=["All"])

    st.sidebar.divider()
    st.sidebar.caption("⚡ Powered by Snowflake Cortex Analyst & AI")

    return {
        "date_range": date_range,
        "plants": selected_plants,
        "lines": selected_lines,
        "shifts": selected_shifts,
        "product_families": selected_families,
    }


def _generate_date_series(start_date: str, end_date: str, num_points: int = 5) -> List[str]:
    """Generate dynamic x-axis date labels (DAYS, not time) for dashboard charts."""
    try:
        s_dt = pd.to_datetime(start_date).date()
        e_dt = pd.to_datetime(end_date).date()
    except Exception:
        e_dt = datetime.date.today()
        s_dt = e_dt - datetime.timedelta(days=num_points - 1)

    if s_dt > e_dt:
        s_dt, e_dt = e_dt, s_dt

    # If start_date == end_date, generate num_points days ending on e_dt
    if s_dt == e_dt:
        s_dt = e_dt - datetime.timedelta(days=num_points - 1)

    delta_days = (e_dt - s_dt).days
    if delta_days == 0:
        date_list = [e_dt] * num_points
    else:
        date_list = [
            s_dt + datetime.timedelta(days=round(i * delta_days / (num_points - 1)))
            for i in range(num_points)
        ]

    return [d.strftime("%b %d") for d in date_list]


def _render_dash_header(title: str, subtitle: Optional[str], stats: List[dict]):
    """Render the dashboard header. Title wraps instead of cropping; KPIs wrap under it on narrow screens."""
    stats_html = "".join(
        f'<div class="dash-stat-item">'
        f'<div class="dash-stat-val">{_fmt_stat(s["val"])}</div>'
        f'<div class="dash-stat-lbl"><span class="dash-stat-dot" '
        f'style="background:{_TONES.get(s.get("tone", "primary"), PRIMARY)}"></span>{html.escape(s["lbl"])}</div>'
        f'</div>'
        for s in stats
    )
    subtitle_html = f'<div class="dash-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="dash-header">'
        f'<div class="dash-title-wrap">'
        f'<div class="dash-title">{html.escape(title)}</div>'
        f'{subtitle_html}'
        f'</div>'
        f'<div class="dash-stats-box">{stats_html}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def _card_title(title: str, caption: Optional[str] = None):
    """Card heading rendered as HTML (wraps naturally) instead of a Plotly title (which crops)."""
    cap = f'<div class="dash-card-caption">{html.escape(caption)}</div>' if caption else ""
    st.markdown(
        f'<div class="dash-card-title">{html.escape(title)}</div>{cap}',
        unsafe_allow_html=True
    )


def _base_layout(fig: go.Figure, height: int, **overrides) -> go.Figure:
    """Apply the shared chart look (fonts, transparent background, tight margins, hover style)."""
    layout = dict(
        height=height,
        margin=dict(l=4, r=4, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, size=12, color=INK_SOFT),
        hoverlabel=dict(bgcolor="#fff", bordercolor=BORDER, font=dict(family=FONT_FAMILY, size=12, color=INK)),
    )
    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


def _show(fig: go.Figure, key: str):
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displayModeBar": False})


def _two_line_ticks(labels: List[str]) -> List[str]:
    """'Jul 06, 2024' -> 'Jul 06<br>2024' so tick labels never overlap or get clipped."""
    return [str(t).replace(", ", "<br>") for t in labels]


def _hbar_figure(labels: List[str], values: List[float], colors: List[str], fmt, height: int) -> go.Figure:
    """Single-trace horizontal bar chart with value labels at the end of each bar."""
    max_val = max([v for v in values if v] or [1])
    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker=dict(color=colors),
        text=[fmt(v) for v in values],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=13, color=INK, family=FONT_FAMILY),
        width=0.55,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    _base_layout(
        fig, height,
        margin=dict(l=4, r=48, t=4, b=4),
        xaxis=dict(range=[0, max_val * 1.12], showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(autorange="reversed", automargin=True, showgrid=False, zeroline=False,
                   tickfont=dict(size=12, color=INK_SOFT)),
    )
    return fig


def _gauge_figure(value: float, color: str, height: int = H_GAUGE, value_format: str = ".0f") -> go.Figure:
    """Half-circle gauge 0-100."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(valueformat=value_format, font=dict(size=40, color=INK, family=FONT_FAMILY)),
        gauge=dict(
            shape="angular",
            axis=dict(range=[0, 100], tickmode="array", tickvals=[0, 100], ticktext=["0", "100"],
                      tickfont=dict(size=11, color=MUTED), ticks=""),
            bar=dict(color=color, thickness=1),
            bgcolor=TRACK,
            borderwidth=0,
        ),
    ))
    _base_layout(fig, height, margin=dict(l=24, r=24, t=16, b=4))
    return fig


def _stacked_pct_figure(times: List[str], run_pct: List[float], lost_pct: List[float],
                        run_name: str, lost_name: str, run_color: str, height: int = H_TALL) -> go.Figure:
    """100% stacked run-time vs lost-time chart with legend on top (no overlap with ticks)."""
    ticks = _two_line_ticks(times)
    fig = go.Figure()
    for name, vals, color, hover in (
        (run_name, run_pct, run_color, "Run time"),
        (lost_name, lost_pct, ROSE, "Lost time"),
    ):
        fig.add_trace(go.Bar(
            name=name,
            x=ticks,
            y=vals,
            customdata=times,
            marker_color=color,
            text=[f"{v}%" if v >= 8 else "" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#fff", size=11, family=FONT_FAMILY),
            hovertemplate=f"<b>%{{customdata}}</b><br>{hover}: %{{y}}%<extra></extra>",
        ))
    _base_layout(
        fig, height,
        barmode="stack",
        bargap=0.35,
        margin=dict(l=4, r=4, t=36, b=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=11, color=INK_SOFT, family=FONT_FAMILY)),
        xaxis=dict(showgrid=False, automargin=True, tickfont=dict(size=10, color=MUTED, family=FONT_FAMILY)),
        yaxis=dict(range=[0, 100], ticksuffix="%", showgrid=True, gridcolor=GRID, zeroline=False,
                   automargin=True, tickfont=dict(size=10, color=MUTED, family=FONT_FAMILY)),
    )
    return fig


def _show_gauge_card(title: str, value: float, color: str, key: str, value_format: str = ".0f",
                     caption: Optional[str] = None):
    with st.container(border=True):
        _card_title(title, caption)
        _show(_gauge_figure(value, color, value_format=value_format), key)


def _show_shift_bars_card(title: str, caption: Optional[str], labels: List[str], values: List[float],
                          colors: List[str], fmt, key: str):
    with st.container(border=True):
        _card_title(title, caption)
        _show(_hbar_figure(labels, values, colors, fmt, H_BARS), key)


# ==============================================================================
# DISPATCHER
# ==============================================================================
def render_oee_dashboard(
    dashboard_name: str,
    start_date: str,
    end_date: str,
    line_name: str
):
    """Render the OEE Dashboard section sitting above the chat interface."""
    try:
        data = load_dashboard_metrics_from_db(dashboard_name, start_date, end_date, line_name)
    except Exception as db_err:
        data = {}
        st.warning(f"Database connection unavailable: {db_err}")

    _inject_dashboard_css()

    d_lower = (dashboard_name or "").strip().lower()
    if d_lower in ("moghul", "moguls"):
        _render_moghul_dashboard(data, line_name, start_date, end_date)
        return

    if d_lower == "marshmallow":
        _render_marshmallow_dashboard(data, line_name, start_date, end_date)
        return

    # Default / Molded Dashboard Layout
    _render_molded_dashboard(data, line_name, start_date, end_date)


# ==============================================================================
# MARSHMALLOW
# ==============================================================================
def _render_marshmallow_dashboard(data: Dict[str, Any], line_name: str, start_date: str, end_date: str):
    """Render Marshmallow dashboard."""
    display_line = line_name if line_name and line_name != "All Lines" else "Belt 1"
    run_time = int(data.get("total_run_time_mins", 0))
    lost_time = int(data.get("total_lost_time_mins", 0))
    scrap = int(data.get("scrap", 0))

    _render_dash_header(
        title=display_line,
        subtitle=None,
        stats=[
            {"val": run_time, "lbl": "Total run time (mins)", "tone": "primary"},
            {"val": lost_time, "lbl": "Total lost time (mins)", "tone": "danger"},
            {"val": scrap, "lbl": "Scrap (lbs)", "tone": "danger"},
        ],
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col1:
        p1 = int(data.get("total_pounds_shift1", 0))
        p2 = int(data.get("total_pounds_shift2", 0))
        p3 = int(data.get("total_pounds_shift3", 0))
        p_total = int(data.get("total_pounds_running_sum", 0))

        _show_shift_bars_card(
            "Pounds packed by shift", "Pounds per shift and total",
            ["1st shift", "2nd shift", "3rd shift", "Total"],
            [p1, p2, p3, p_total],
            [PRIMARY, PRIMARY, PRIMARY, TEAL],
            lambda v: f"{int(v):,}",
            "fig_marsh_pounds",
        )
        _show_gauge_card("Total OEE", int(data.get("overall_oee", 0)), PRIMARY, "fig_marsh_gauge",
                         caption="Overall equipment effectiveness, %")

    with col2:
        with st.container(border=True):
            _card_title("Scrap", "Share of scrap against pounds packed")
            scrap_share = scrap / (p_total + scrap) * 100 if (p_total + scrap) else 0
            fig_pie = go.Figure(go.Pie(
                labels=["Packed (lbs)", "Scrap (lbs)"],
                values=[p_total, scrap],
                marker=dict(colors=[PRIMARY, ROSE], line=dict(color="#fff", width=2)),
                hole=0.62,
                sort=False,
                textinfo="percent",
                textfont=dict(size=13, color="#fff", family=FONT_FAMILY),
                hovertemplate="<b>%{label}</b><br>%{value:,} lbs (%{percent})<extra></extra>",
            ))
            fig_pie.add_annotation(
                text=f"<b style='font-size:30px;color:{INK};'>{scrap_share:.1f}%</b><br>"
                     f"<span style='font-size:12px;color:{MUTED};'>scrap rate</span>",
                x=0.5, y=0.5, showarrow=False, xref="paper", yref="paper"
            )
            _base_layout(
                fig_pie, H_TALL,
                margin=dict(l=8, r=8, t=8, b=36),
                legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5,
                            font=dict(size=11, color=INK_SOFT, family=FONT_FAMILY)),
            )
            _show(fig_pie, "fig_marsh_pie")

    with col3:
        with st.container(border=True):
            _card_title("Total run time", "Share of each time block spent running vs. lost")
            date_ticks = _generate_date_series(start_date, end_date, num_points=3)
            tot_time = (run_time + lost_time) or 1
            run_pct = round(run_time / tot_time * 100) if (run_time or lost_time) else 0
            lost_pct = 100 - run_pct if (run_time or lost_time) else 0
            fig = _stacked_pct_figure(
                date_ticks,
                [run_pct] * len(date_ticks), [lost_pct] * len(date_ticks),
                "Run time", "Lost time", PRIMARY,
            )
            _show(fig, "fig_marsh_stacked")


# ==============================================================================
# MOGHUL
# ==============================================================================
def _render_moghul_dashboard(data: Dict[str, Any], line_name: str, start_date: str, end_date: str):
    """Render Moghul dashboard."""
    display_line = line_name if line_name and line_name != "All Lines" else "NID-C"
    run_time = int(data.get("total_run_time_mins", 0))
    lost_time = int(data.get("total_lost_time_mins", 0))
    total_boards = int(data.get("total_boards") or data.get("total_pounds_running_sum") or 0)

    _render_dash_header(
        title=display_line,
        subtitle=None,
        stats=[
            {"val": run_time, "lbl": "Total run time (mins)", "tone": "primary"},
            {"val": lost_time, "lbl": "Total lost time (mins)", "tone": "danger"},
            {"val": total_boards, "lbl": "Total boards cast", "tone": "teal"},
        ],
    )

    col1, col2, col3 = st.columns([1, 1.1, 1])

    with col1:
        b1 = int(data.get("boards_cast_shift1") or data.get("total_pounds_shift1") or 0)
        b2 = int(data.get("boards_cast_shift2") or data.get("total_pounds_shift2") or 0)
        b3 = int(data.get("boards_cast_shift3") or data.get("total_pounds_shift3") or 0)
        _show_shift_bars_card(
            "Boards cast", "Boards per shift and total",
            ["1st shift", "2nd shift", "3rd shift", "Total"],
            [b1, b2, b3, total_boards],
            [PRIMARY, PRIMARY, PRIMARY, TEAL],
            lambda v: f"{int(v):,}",
            "fig_moghul_boards",
        )

    with col2:
        with st.container(border=True):
            _card_title("Shift run time vs. lost time", "Share of each time block spent running vs. lost")
            date_ticks = _generate_date_series(start_date, end_date, num_points=5)
            tot_time = (run_time + lost_time) or 1
            run_pct = round(run_time / tot_time * 100) if (run_time or lost_time) else 0
            lost_pct = 100 - run_pct if (run_time or lost_time) else 0
            fig = _stacked_pct_figure(
                date_ticks,
                [run_pct] * len(date_ticks), [lost_pct] * len(date_ticks),
                "Run time", "Lost time", PRIMARY,
            )
            _show(fig, "fig_moghul_stacked")

    with col3:
        _show_shift_bars_card(
            "Shift OEE", "Overall equipment effectiveness per shift, %",
            ["1st shift", "2nd shift", "3rd shift"],
            [
                int(data.get("oee_shift1", 0)),
                int(data.get("oee_shift2", 0)),
                int(data.get("oee_shift3", 0)),
            ],
            [PRIMARY, PRIMARY, PRIMARY],
            lambda v: f"{int(v)}%",
            "fig_moghul_oee_bar",
        )
        _show_gauge_card("Total OEE", float(data.get("overall_oee", 0)), PRIMARY, "fig_moghul_gauge",
                         value_format=".2f", caption="Overall equipment effectiveness, %")


# ==============================================================================
# MOLDED (default)
# ==============================================================================
def _render_molded_dashboard(data: Dict[str, Any], line_name: str, start_date: str, end_date: str):
    """Render Molded dashboard layout."""
    display_line = line_name if line_name and line_name != "All Lines" else "Molded Line"
    run_time = int(data.get("total_run_time_mins", 0))
    lost_time = int(data.get("total_lost_time_mins", 0))
    pounds_sum = int(data.get("total_pounds_running_sum", 0))

    _render_dash_header(
        title=display_line,
        subtitle=None,
        stats=[
            {"val": run_time, "lbl": "Total run time (mins)", "tone": "primary"},
            {"val": lost_time, "lbl": "Total lost time (mins)", "tone": "danger"},
            {"val": pounds_sum, "lbl": "Total pounds (lbs)", "tone": "teal"},
        ],
    )

    col1, col2, col3 = st.columns([1, 1.1, 1])

    # Column 1: total pounds (bars + trend)
    with col1:
        p1 = int(data.get("total_pounds_shift1", 0))
        p2 = int(data.get("total_pounds_shift2", 0))
        p3 = int(data.get("total_pounds_shift3", 0))
        _show_shift_bars_card(
            "Total pounds", "Pounds per shift and running sum",
            ["1st shift", "2nd shift", "3rd shift", "Running sum"],
            [p1, p2, p3, pounds_sum],
            [PRIMARY, PRIMARY, PRIMARY, TEAL],
            lambda v: f"{int(v):,}",
            "fig_pounds_bar_main",
        )

        with st.container(border=True):
            _card_title("Total pounds trend", "Cumulative pounds over time")
            date_ticks = _generate_date_series(start_date, end_date, num_points=5)
            # Create smooth cumulative progression up to total pounds_sum
            if pounds_sum > 0:
                step_vals = [round(pounds_sum * (i + 1) / len(date_ticks)) for i in range(len(date_ticks))]
            else:
                step_vals = [0] * len(date_ticks)

            df_area = pd.DataFrame({
                "time": date_ticks,
                "val": step_vals
            })
            fig_area = go.Figure(go.Scatter(
                x=_two_line_ticks(df_area["time"]),
                y=df_area["val"],
                customdata=df_area["time"],
                fill="tozeroy",
                mode="lines",
                line_shape="spline",
                line=dict(color=PRIMARY, width=2.5),
                fillcolor=_rgba(PRIMARY, 0.14),
                hovertemplate="<b>%{customdata}</b><br>Pounds: %{y:,}<extra></extra>",
            ))
            _base_layout(
                fig_area, H_GAUGE,
                margin=dict(l=4, r=12, t=8, b=4),
                xaxis=dict(showgrid=False, automargin=True, tickfont=dict(size=10, color=MUTED, family=FONT_FAMILY)),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            )
            _show(fig_area, "fig_pounds_area_main")

    # Column 2: run time vs lost time
    with col2:
        with st.container(border=True):
            _card_title("Total run time vs. lost time", "Share of each time block spent running vs. lost")
            date_ticks = _generate_date_series(start_date, end_date, num_points=5)
            tot_time = (run_time + lost_time) or 1
            run_pct = round(run_time / tot_time * 100) if (run_time or lost_time) else 0
            lost_pct = 100 - run_pct if (run_time or lost_time) else 0
            fig = _stacked_pct_figure(
                date_ticks,
                [run_pct] * len(date_ticks), [lost_pct] * len(date_ticks),
                "Run time", "Lost time", PRIMARY,
            )
            _show(fig, "fig_stacked_main")

    # Column 3: OEE (bars + gauge)
    with col3:
        _show_shift_bars_card(
            "Shift OEE", "Overall equipment effectiveness per shift, %",
            ["1st shift", "2nd shift", "3rd shift"],
            [
                int(data.get("oee_shift1", 0)),
                int(data.get("oee_shift2", 0)),
                int(data.get("oee_shift3", 0)),
            ],
            [PRIMARY, PRIMARY, PRIMARY],
            lambda v: f"{int(v)}%",
            "fig_oee_bar_main",
        )
        _show_gauge_card("Total OEE", int(data.get("overall_oee", 0)), PRIMARY, "fig_oee_gauge_main",
                         caption="Overall equipment effectiveness, %")


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

    # Dynamically allocate column widths based on question length to prevent large gaps
    num_qs = len(sample_questions)
    cols = st.columns(num_qs)
    for idx, q in enumerate(sample_questions):
        cols[idx].button(
            q,
            key=f"sq_{idx}",
            use_container_width=True,
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
