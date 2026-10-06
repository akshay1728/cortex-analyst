"""UI Components for Manufacturing OEE Conversational Analytics App."""

import html
from string import Template

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

# ==============================================================================
# DESIGN TOKENS  (one theme shared by every dashboard - change colours here only)
# ==============================================================================
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Neutrals
INK = "#0F172A"          # headings, big numbers
INK_SOFT = "#475569"     # body / axis labels
MUTED = "#94A3B8"        # captions, tick labels
GRID = "#EEF2F6"         # gridlines
TRACK = "#E7ECF3"       # empty part of gauges
BORDER = "#E3E8EF"       # card borders
BRAND_DEEP = "#2F2B73"   # deep indigo (matches sidebar active button) - header title
ACCENT_BAR = "linear-gradient(90deg, #E8913A 0%, #C4568F 50%, #4F46E5 100%)"  # echoes the logo underline

# Semantic data colours
PRIMARY = "#4F46E5"      # production / run time / shift values
TEAL = "#0EA5A4"         # totals & running sums
ROSE = "#E11D48"         # lost time & scrap

# Backwards-compatible aliases (other modules may still import the old names)
PURPLE_COLOR = PRIMARY
GREEN_COLOR = TEAL
SLATE_COLOR = INK_SOFT
OLIVE_COLOR = PRIMARY
RED_COLOR = ROSE
BLUE_BRIGHT = PRIMARY

_TONES = {"primary": PRIMARY, "teal": TEAL, "danger": ROSE}

# Chart heights (tuned so the tall middle card lines up with the two stacked cards)
H_BARS = 190
H_GAUGE = 190
H_TALL = 440


# ==============================================================================
# SHARED STYLING / HELPERS
# ==============================================================================
_DASH_CSS = Template("""
.dash-header { position: relative; overflow: hidden; display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: 20px 40px; padding: 24px 28px 22px; margin-bottom: 18px; border-radius: 16px;
  background: #fff; border: 1px solid $BORDER; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }
.dash-header::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px; background: $ACCENT_BAR; }
.dash-title-wrap { flex: 1 1 260px; min-width: 0; }
.dash-title { font-family: $FONT; font-size: clamp(1.5rem, 2.4vw, 2.1rem); font-weight: 700; line-height: 1.15;
  letter-spacing: -0.02em; color: $BRAND_DEEP; overflow-wrap: anywhere; }
.dash-subtitle { margin-top: 6px; font-family: $FONT; font-size: 0.95rem; color: $INK_SOFT; }
.dash-stats-box { display: flex; flex-wrap: wrap; gap: 18px 0; }
.dash-stat-item { padding: 0 28px; border-left: 1px solid $BORDER; min-width: 120px; }
.dash-stat-item:first-child { padding-left: 0; border-left: none; }
.dash-stat-val { font-family: $FONT; font-size: 1.9rem; font-weight: 700; line-height: 1.1; color: $INK;
  font-variant-numeric: tabular-nums; }
.dash-stat-lbl { display: flex; align-items: center; gap: 7px; margin-top: 6px; font-family: $FONT;
  font-size: 0.82rem; line-height: 1.25; color: $INK_SOFT; }
.dash-stat-dot { flex: 0 0 8px; width: 8px; height: 8px; border-radius: 50%; }
[data-testid="stVerticalBlockBorderWrapper"]:has(.dash-card-title) { border: 1px solid $BORDER; border-radius: 16px;
  background: #fff; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }
.dash-card-title { font-family: $FONT; font-size: 1rem; font-weight: 600; line-height: 1.3; color: $INK;
  overflow-wrap: anywhere; }
.dash-card-caption { margin-top: 2px; font-family: $FONT; font-size: 0.8rem; line-height: 1.3; color: $MUTED; }
.shift-list { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; }
.shift-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.shift-lbl { font-family: $FONT; font-size: 0.92rem; color: $INK_SOFT; }
.shift-val { min-width: 110px; padding: 8px 16px; border-radius: 10px; background: #EEF0FF; color: $PRIMARY;
  font-family: $FONT; font-size: 1.15rem; font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; }
.shift-total { margin-top: 6px; padding: 14px 16px; border-radius: 12px; background: $TEAL; color: #fff;
  text-align: center; font-family: $FONT; }
.shift-total-lbl { font-size: 0.82rem; opacity: 0.9; }
.shift-total-val { font-size: 1.6rem; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }
""")


def _inject_dashboard_css():
    """Inject the shared dashboard CSS once per render (collapsed to one line so markdown can't misread it)."""
    css = _DASH_CSS.substitute(
        FONT=FONT_FAMILY, INK=INK, INK_SOFT=INK_SOFT, MUTED=MUTED, BORDER=BORDER,
        BRAND_DEEP=BRAND_DEEP, ACCENT_BAR=ACCENT_BAR, PRIMARY=PRIMARY, TEAL=TEAL
    )
    css = " ".join(line.strip() for line in css.splitlines() if line.strip())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_stat(val) -> str:
    try:
        return f"{val:,}"
    except (TypeError, ValueError):
        return html.escape(str(val))


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
    """'Jul 06, 12AM' -> 'Jul 06<br>12AM' so tick labels never overlap or get clipped."""
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
    data = load_dashboard_metrics_from_db(dashboard_name, start_date, end_date, line_name)
    _inject_dashboard_css()

    d_lower = (dashboard_name or "").strip().lower()
    if d_lower in ("moghul", "moguls"):
        _render_moghul_dashboard(data, line_name)
        return

    if d_lower == "marshmallow":
        _render_marshmallow_dashboard(data, line_name)
        return

    # Default / Molded Dashboard Layout
    _render_molded_dashboard(data, line_name)


# ==============================================================================
# MARSHMALLOW
# ==============================================================================
def _render_marshmallow_dashboard(data: Dict[str, Any], line_name: str):
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
        p1 = int(data.get("pounds_packed_shift1", 12357))
        p2 = int(data.get("pounds_packed_shift2", 15338))
        p3 = int(data.get("pounds_packed_shift3", 9390))
        p_total = int(data.get("total_pounds_packed", 37085))

        _show_shift_bars_card(
            "Pounds packed by shift", "Pounds per shift and total",
            ["1st shift", "2nd shift", "3rd shift", "Total"],
            [p1, p2, p3, p_total],
            [PRIMARY, PRIMARY, PRIMARY, TEAL],
            lambda v: f"{int(v):,}",
            "fig_marsh_pounds",
        )
        _show_gauge_card("Total OEE", int(data.get("overall_oee", 78)), PRIMARY, "fig_marsh_gauge",
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
            fig = _stacked_pct_figure(
                ["Jul 06, 12AM", "Jul 06, 12PM", "Jul 07, 12AM"],
                [72, 0, 86], [28, 0, 14],
                "Run time", "Lost time", PRIMARY,
            )
            _show(fig, "fig_marsh_stacked")


# ==============================================================================
# MOGHUL
# ==============================================================================
def _render_moghul_dashboard(data: Dict[str, Any], line_name: str):
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
            fig = _stacked_pct_figure(
                ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"],
                [59, 62, 64, 60, 69], [41, 38, 36, 40, 31],
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
def _render_molded_dashboard(data: Dict[str, Any], line_name: str):
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
        _show_shift_bars_card(
            "Total pounds", "Pounds per shift and running sum",
            ["1st shift", "2nd shift", "3rd shift", "Running sum"],
            [
                data.get("total_pounds_shift1", 15444),
                data.get("total_pounds_shift2", 9461),
                data.get("total_pounds_shift3", 0),
                data.get("total_pounds_running_sum", 24905),
            ],
            [PRIMARY, PRIMARY, PRIMARY, TEAL],
            lambda v: f"{int(v):,}",
            "fig_pounds_bar_main",
        )

        with st.container(border=True):
            _card_title("Total pounds trend", "Cumulative pounds over time")
            df_area = pd.DataFrame({
                "time": ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"],
                "val": [5000, 7200, 15444, 22000, data.get("total_pounds_running_sum", 24905)]
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
            fig = _stacked_pct_figure(
                ["Jul 06, 12AM", "Jul 06, 6AM", "Jul 06, 12PM", "Jul 06, 6PM", "Jul 07, 12AM"],
                [62, 64, 64, 64, 62], [38, 36, 36, 36, 38],
                "Run time", "Lost time", PRIMARY,
            )
            _show(fig, "fig_stacked_main")

    # Column 3: OEE (bars + gauge)
    with col3:
        _show_shift_bars_card(
            "Shift OEE", "Overall equipment effectiveness per shift, %",
            ["1st shift", "2nd shift", "3rd shift"],
            [
                int(data.get("oee_shift1", 60)),
                int(data.get("oee_shift2", 36)),
                int(data.get("oee_shift3", 0)),
            ],
            [PRIMARY, PRIMARY, PRIMARY],
            lambda v: f"{int(v)}%",
            "fig_oee_bar_main",
        )
        _show_gauge_card("Total OEE", int(data.get("overall_oee", 47)), PRIMARY, "fig_oee_gauge_main",
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
