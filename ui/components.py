"""UI Components for Manufacturing OEE Conversational Analytics App."""

import html
import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional


# --------------------------------------------------------------------------
# Brand tokens (kept local so this module renders correctly on its own)
# --------------------------------------------------------------------------
KPI_BRAND = {
    "navy": "#242B6B",
    "navy_light": "#3B4394",
    "navy_deep": "#171C4A",
    "coral": "#E15241",
    "gold": "#E0A438",
    "good": "#1E8E5A",
    "good_bg": "#E7F4EE",
    "bad": "#C8392B",
    "bad_bg": "#FBEBE9",
    "flat": "#6C7290",
    "flat_bg": "#F0F1F7",
    "rule": "#E4E7F3",
    "muted": "#6C7290",
    "track": "#ECEEF7",
}

_KPI_CSS = """
<style>
.kpi-strip {{
    background: #FFFFFF;
    border-radius: 16px;
    padding: 4px 0 2px 0;
    box-shadow: 0 10px 26px -18px rgba(31, 41, 107, 0.35);
}}
.kpi-period {{
    font-size: 0.78rem;
    color: {muted};
    padding: 12px 20px 2px 20px;
    letter-spacing: 0.1px;
}}
.kpi-period b {{ color: {navy}; font-weight: 600; }}
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    align-items: stretch;
}}
.kpi-cell {{
    padding: 14px 20px 18px 20px;
    border-left: 1px solid {rule};
}}
.kpi-cell:first-child {{ border-left: none; }}
.kpi-cell.is-lead .kpi-value {{ font-size: 2.15rem; }}
.kpi-label {{
    font-size: 0.82rem;
    font-weight: 500;
    color: {muted};
    margin-bottom: 6px;
}}
.kpi-value {{
    font-family: 'Poppins', 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1.75rem;
    line-height: 1.1;
    color: {navy_deep};
    letter-spacing: -0.5px;
}}
.kpi-value .unit {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {muted};
    margin-left: 3px;
    letter-spacing: 0;
}}
.kpi-track {{
    height: 3px;
    border-radius: 3px;
    background: {track};
    margin: 10px 0 9px 0;
    overflow: hidden;
}}
.kpi-track > span {{
    display: block;
    height: 100%;
    border-radius: 3px;
}}
.kpi-foot {{
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
}}
.kpi-delta {{
    font-size: 0.78rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    white-space: nowrap;
}}
.kpi-delta.up {{ color: {good}; background: {good_bg}; }}
.kpi-delta.down {{ color: {bad}; background: {bad_bg}; }}
.kpi-delta.flat {{ color: {flat}; background: {flat_bg}; }}
.kpi-prev {{
    font-size: 0.76rem;
    color: {muted};
    white-space: nowrap;
}}
@media (max-width: 1100px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .kpi-cell {{ border-left: none; border-top: 1px solid {rule}; }}
    .kpi-cell:nth-child(-n+2) {{ border-top: none; }}
    .kpi-cell:nth-child(odd) {{ border-left: none; }}
    .kpi-cell:nth-child(even) {{ border-left: 1px solid {rule}; }}
}}
</style>
"""


def _fmt_date(val: Any) -> str:
    """Render a date-ish value as a short readable string."""
    if val in (None, "", "N/A"):
        return "—"
    try:
        return pd.to_datetime(val).strftime("%d %b %Y")
    except Exception:
        return html.escape(str(val))


def _num(kpi_data: Dict[str, Any], *keys: str) -> float:
    """First non-null numeric value among the given keys, else 0.0."""
    for k in keys:
        v = kpi_data.get(k)
        if v is not None and v != "":
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return 0.0


def _delta_html(diff: float, higher_is_better: bool, suffix: str) -> str:
    """Delta chip: direction arrow, magnitude, and tone based on what 'good' means."""
    if abs(diff) < 0.05:
        return '<span class="kpi-delta flat">no change</span>'

    arrow = "▲" if diff > 0 else "▼"
    improving = diff > 0 if higher_is_better else diff < 0
    tone = "up" if improving else "down"

    if suffix == "%":
        magnitude = f"{abs(diff):.1f} pts"
    else:
        magnitude = f"{abs(round(diff)):,.0f} hrs"

    return f'<span class="kpi-delta {tone}">{arrow} {magnitude}</span>'


def _cell_html(label: str, value_txt: str, unit: str, bar_pct: Optional[float],
               bar_color: str, diff: float, prev_txt: str,
               higher_is_better: bool, suffix: str, lead: bool = False) -> str:
    """One KPI cell: label, value, optional progress rule, delta and previous value."""
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""

    if bar_pct is None:
        track = '<div class="kpi-track"></div>'
    else:
        width = max(0.0, min(100.0, bar_pct))
        track = (
            f'<div class="kpi-track"><span style="width:{width:.1f}%;'
            f'background:{bar_color};"></span></div>'
        )

    return (
        f'<div class="kpi-cell{" is-lead" if lead else ""}">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{value_txt}{unit_html}</div>'
        f'{track}'
        f'<div class="kpi-foot">{_delta_html(diff, higher_is_better, suffix)}'
        f'<span class="kpi-prev">was {prev_txt}</span></div>'
        f'</div>'
    )


def render_kpi_cards(kpi_data: Dict[str, Any], brand: Optional[Dict[str, str]] = None):
    """Render the KPI strip: current period values with change against the previous period."""
    tokens = dict(KPI_BRAND)
    if brand:
        tokens.update({k: v for k, v in brand.items() if k in tokens})

    if not kpi_data:
        kpi_data = {}

    latest_date = _fmt_date(
        kpi_data.get("latest_date") or kpi_data.get("current_date") or kpi_data.get("current_end_date")
    )
    previous_date = _fmt_date(
        kpi_data.get("previous_date") or kpi_data.get("prev_date") or kpi_data.get("previous_end_date")
    )

    curr_oee = _num(kpi_data, "current_oee", "oee")
    prev_oee = _num(kpi_data, "previous_oee")
    curr_avail = _num(kpi_data, "current_availability", "availability")
    prev_avail = _num(kpi_data, "previous_availability")
    curr_perf = _num(kpi_data, "current_performance", "performance")
    prev_perf = _num(kpi_data, "previous_performance")
    curr_qual = _num(kpi_data, "current_quality", "quality")
    prev_qual = _num(kpi_data, "previous_quality")
    curr_dt = _num(kpi_data, "current_downtime_hours", "total_downtime_hours")
    prev_dt = _num(kpi_data, "previous_downtime_hours")

    # Downtime has no natural 0-100 scale, so its rule shows the current period
    # against the larger of the two periods instead.
    dt_scale = max(curr_dt, prev_dt)
    dt_bar = (curr_dt / dt_scale * 100.0) if dt_scale > 0 else 0.0

    cells = [
        _cell_html("Overall OEE", f"{curr_oee:.1f}", "%", curr_oee, tokens["navy"],
                   curr_oee - prev_oee, f"{prev_oee:.1f}%", True, "%", lead=True),
        _cell_html("Availability", f"{curr_avail:.1f}", "%", curr_avail, tokens["navy_light"],
                   curr_avail - prev_avail, f"{prev_avail:.1f}%", True, "%"),
        _cell_html("Performance", f"{curr_perf:.1f}", "%", curr_perf, tokens["navy_light"],
                   curr_perf - prev_perf, f"{prev_perf:.1f}%", True, "%"),
        _cell_html("Quality", f"{curr_qual:.1f}", "%", curr_qual, tokens["navy_light"],
                   curr_qual - prev_qual, f"{prev_qual:.1f}%", True, "%"),
        _cell_html("Downtime", f"{curr_dt:,.0f}", "hrs", dt_bar, tokens["coral"],
                   curr_dt - prev_dt, f"{prev_dt:,.0f} hrs", False, " hrs"),
    ]

    st.markdown(_KPI_CSS.format(**tokens), unsafe_allow_html=True)
    st.markdown(
        f'<div class="kpi-strip">'
        f'<div class="kpi-period">Showing <b>{latest_date}</b>, compared with {previous_date}</div>'
        f'<div class="kpi-grid">{"".join(cells)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


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
            use_container_width=True,
            on_click=on_click_callback,
            args=(q,)
        )


def style_dataframe_metrics(df: pd.DataFrame, metric_colors: dict):
    """Apply background color styling to DataFrame columns matching metric thresholds.

    `metric_colors` format:
    {
        "oee": {"enabled": False, "threshold": 85.0, "pass_color": "#28a745", "fail_color": "#dc3545"},
        "availability": ...
    }
    """
    if df is None or df.empty:
        return df

    # Normalize column mapping
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

        # Find matching columns in DataFrame (case-insensitive substring or exact match)
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
