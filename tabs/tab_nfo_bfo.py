"""
tabs/tab_nfo_bfo.py
====================
Tab 2 – NFO-BFO Spread Analysis

Automatically generates a ladder of spreads comparing BSE vs NSE index options.
Spread = First Leg Premium  −  (Second Leg Premium × Ratio)

Layout:
  Top controls → Calls table (7 rows) → Puts table (7 rows) → (repeat)
  Each row has a "View Chart" button that reveals the chart inline below the row.
"""

from __future__ import annotations

from datetime import date, timedelta
from math import floor

import streamlit as st
import pandas as pd

from data_api import (
    UNDERLYINGS,
    get_expiries,
    get_ltp,
    get_spread_history,
    compute_day_stats,
    round_to_nearest_50,
    get_atm,
)
from chart_utils import build_spread_line_chart


# ── Config defaults ──────────────────────────────────────────────────────────
_DEFAULT_RATIO      = 3.3
_DEFAULT_MULTIPLIER = 3.3
_DEFAULT_ADDON      = 500
_ROWS_PER_SECTION   = 7


# ── Helpers ──────────────────────────────────────────────────────────────────

def _round_nearest_atm(underlying: str, addon: int) -> int:
    """Round ATM to nearest addon multiple."""
    atm = get_atm(underlying)
    return int(round(atm / addon) * addon)


def _fmt_spread(val: float | None) -> str:
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}"


def _spread_css(val: float | None) -> str:
    if val is None:
        return ""
    if val > 0:
        return "spread-pos"
    if val < 0:
        return "spread-neg"
    return "spread-zero"


# ── Strike ladder ─────────────────────────────────────────────────────────────

def _generate_strikes(first_strike: int, addon: int, count: int) -> list[int]:
    return [first_strike + i * addon for i in range(count)]


def _second_strike(first: int, multiplier: float) -> int:
    return round_to_nearest_50(first / multiplier)


# ── Fetch spread stats for one row ───────────────────────────────────────────

def _fetch_row_stats(
    ex1, und1, exp1, stk1, otype,
    ex2, und2, exp2, stk2,
    ratio, trade_date,
):
    ltp1 = get_ltp(ex1, und1, exp1, stk1, otype)
    ltp2 = get_ltp(ex2, und2, exp2, stk2, otype)

    if ltp1 is None or ltp2 is None:
        return None, None, None, ltp1, ltp2

    current = round(ltp1 - ltp2 * ratio, 2)

    # Day high/low from history
    df = get_spread_history(
        ex1, und1, exp1, stk1, otype,
        ex2, und2, exp2, stk2, otype,
        trade_date, ratio=ratio,
    )
    stats = compute_day_stats(df)
    return current, stats.get("high"), stats.get("low"), ltp1, ltp2


# ── Table renderer ────────────────────────────────────────────────────────────

def _render_table_section(
    label: str,
    option_type: str,
    strikes: list[int],
    ex1: str, und1: str, exp1: str,
    ex2: str, und2: str, exp2: str,
    multiplier: float,
    ratio: float,
    trade_date: date,
    section_key: str,
):
    st.markdown(
        f'<div class="section-header"><div class="section-dot" '
        f'style="background:{"#58a6ff" if option_type == "CE" else "#d29922"}"></div>'
        f'<h3>{label} — {option_type}</h3></div>',
        unsafe_allow_html=True,
    )

    # Table header
    st.markdown("""
    <table class="spread-table">
      <thead>
        <tr>
          <th style="text-align:left">First Strike</th>
          <th>Second Strike</th>
          <th>Current Spread</th>
          <th>—</th>
          <th>Day High</th>
          <th>Day Low</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="spread-body">
    """, unsafe_allow_html=True)

    st.markdown("</tbody></table>", unsafe_allow_html=True)

    # Render each row with Streamlit columns (allows buttons)
    for i, stk1 in enumerate(strikes):
        stk2 = _second_strike(stk1, multiplier)
        row_key = f"{section_key}_{option_type}_{i}"

        current, high, low, ltp1, ltp2 = _fetch_row_stats(
            ex1, und1, exp1, stk1, option_type,
            ex2, und2, exp2, stk2,
            ratio, trade_date,
        )

        c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 2, 1, 2, 2, 2])

        with c1:
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                f"padding:6px 4px;color:#e6edf3'><b>{stk1}</b></div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                f"padding:6px 4px;color:#8b949e'>{stk2}</div>",
                unsafe_allow_html=True,
            )
        with c3:
            cc = _spread_css(current)
            color_map = {"spread-pos": "#3fb950", "spread-neg": "#f85149", "spread-zero": "#8b949e", "": "#8b949e"}
            spread_color = color_map.get(cc, "#8b949e")
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                f"padding:6px 4px;color:{spread_color};font-weight:600'>"
                f"{_fmt_spread(current)}</div>",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                "<div style='padding:6px 4px;color:#30363d;font-size:0.8rem'>—</div>",
                unsafe_allow_html=True,
            )
        with c5:
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                f"padding:6px 4px;color:#3fb950'>{_fmt_spread(high)}</div>",
                unsafe_allow_html=True,
            )
        with c6:
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                f"padding:6px 4px;color:#f85149'>{_fmt_spread(low)}</div>",
                unsafe_allow_html=True,
            )
        with c7:
            if st.button("📈 View Chart", key=f"btn_{row_key}"):
                # Toggle chart state
                toggle_key = f"chart_open_{row_key}"
                st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

        # Chart expansion
        chart_key = f"chart_open_{row_key}"
        if st.session_state.get(chart_key, False):
            with st.container():
                st.markdown(f"""
                <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;
                            padding:16px;margin:4px 0 12px;">
                    <div class="chart-meta">
                        <div class="chart-meta-item">
                            {und1} <span>{stk1} {option_type}</span>
                        </div>
                        <span style="color:#30363d">vs</span>
                        <div class="chart-meta-item">
                            {und2} <span>{stk2} {option_type}</span>
                        </div>
                        <div class="chart-meta-item">
                            Ratio <span>×{ratio}</span>
                        </div>
                        <div class="chart-meta-item">
                            Date <span>{trade_date.strftime("%d %b %Y")}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Stats
                df = get_spread_history(
                    ex1, und1, exp1, stk1, option_type,
                    ex2, und2, exp2, stk2, option_type,
                    trade_date, ratio=ratio,
                )
                stats = compute_day_stats(df)

                sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
                for col, lbl, k, clr in [
                    (sc1, "Open",    "open",    "#e6edf3"),
                    (sc2, "High",    "high",    "#3fb950"),
                    (sc3, "Low",     "low",     "#f85149"),
                    (sc4, "Current", "current", "#58a6ff"),
                    (sc5, "High @",  "high_time", "#8b949e"),
                    (sc6, "Low @",   "low_time",  "#8b949e"),
                ]:
                    with col:
                        val = stats.get(k)
                        if hasattr(val, "strftime"):
                            display = val.strftime("%H:%M")
                        elif val is not None:
                            sign = "+" if val > 0 else ""
                            display = f"{sign}{val:.2f}"
                        else:
                            display = "—"
                        st.markdown(f"""
                        <div class="metric-card" style="padding:10px 14px">
                            <div class="metric-label">{lbl}</div>
                            <div style="font-family:JetBrains Mono,monospace;font-size:1.1rem;
                                        font-weight:700;color:{clr}">{display}</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                chart_title = (
                    f"{und1} {stk1} vs {und2} {stk2}  ·  {option_type}  ·  "
                    f"{trade_date.strftime('%d %b %Y')}"
                )
                # Only pass timestamp + spread columns to chart
                df_chart = df[["timestamp", "spread"]].copy() if not df.empty else df
                fig = build_spread_line_chart(df_chart, title=chart_title, stats=stats, resolution="Tick")
                st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        # Thin row divider
        st.markdown(
            "<div style='border-top:1px solid #1c2230;margin:0'></div>",
            unsafe_allow_html=True,
        )


# ── Main render ──────────────────────────────────────────────────────────────

def render_tab():
    st.markdown("### NFO-BFO Spread Analysis")
    st.caption(
        "Automatically generates strike ladders. "
        "Spread = First Leg Premium − (Second Leg Premium × Ratio). "
        "Click **View Chart** to see the historical chart for any row."
    )

    # ── Top Controls ─────────────────────────────────────────────────────────
    with st.expander("⚙️  Controls", expanded=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)

        with r1c1:
            st.markdown("**Exchange**")
            ex1 = st.selectbox("First Leg Exchange", ["BSE", "NSE"], index=0, key="nfo_ex1")
            ex2 = st.selectbox("Second Leg Exchange", ["NSE", "BSE"], index=0, key="nfo_ex2")

        with r1c2:
            st.markdown("**Index**")
            und1_opts = UNDERLYINGS.get(ex1, ["SENSEX"])
            und2_opts = UNDERLYINGS.get(ex2, ["NIFTY"])
            und1 = st.selectbox("First Leg Index", und1_opts, key="nfo_und1")
            und2 = st.selectbox("Second Leg Index", und2_opts, key="nfo_und2")

        with r1c3:
            st.markdown("**Parameters**")
            ratio = st.number_input("Ratio", value=_DEFAULT_RATIO, step=0.01, format="%.4f", key="nfo_ratio")
            multiplier = st.number_input("Multiplier", value=_DEFAULT_MULTIPLIER, step=0.01, format="%.4f", key="nfo_mult")

        with r1c4:
            st.markdown("**Strike Ladder**")
            addon = st.number_input("Add-on", value=_DEFAULT_ADDON, step=50, key="nfo_addon")
            trade_date = st.date_input(
                "Date",
                value=date.today(),
                max_value=date.today(),
                key="nfo_date",
            )

        r2c1, r2c2, _ = st.columns([3, 3, 4])
        with r2c1:
            exp1_list = get_expiries(ex1, und1)
            exp1 = st.selectbox("First Leg Expiry", exp1_list, key="nfo_exp1")
        with r2c2:
            exp2_list = get_expiries(ex2, und2)
            exp2 = st.selectbox("Second Leg Expiry", exp2_list, key="nfo_exp2")

        r3c1, r3c2, _ = st.columns([3, 3, 4])
        with r3c1:
            default_first = _round_nearest_atm(und1, int(addon))
            first_strike = st.number_input(
                "First Strike (ATM start)",
                value=default_first,
                step=int(addon),
                key="nfo_first_strike",
            )

    st.markdown("---")

    # ── Refresh button ────────────────────────────────────────────────────────
    col_rf, col_note = st.columns([2, 8])
    with col_rf:
        if st.button("🔄 Refresh All Prices", key="nfo_refresh"):
            st.cache_data.clear()
            st.rerun()
    with col_note:
        st.caption(f"Showing {_ROWS_PER_SECTION * 4} rows (7 CE + 7 PE + 7 CE + 7 PE)  ·  Ratio: ×{ratio:.2f}  ·  Multiplier: ×{multiplier:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Generate strike ladders ───────────────────────────────────────────────
    strikes = _generate_strikes(int(first_strike), int(addon), _ROWS_PER_SECTION)

    # Block 1: Calls (7 rows)
    _render_table_section(
        label="Section A",
        option_type="CE",
        strikes=strikes,
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        multiplier=multiplier, ratio=ratio,
        trade_date=trade_date,
        section_key="A",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Block 2: Puts (7 rows)
    _render_table_section(
        label="Section A",
        option_type="PE",
        strikes=strikes,
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        multiplier=multiplier, ratio=ratio,
        trade_date=trade_date,
        section_key="B",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Block 3: Calls again (7 rows, next rung of strikes)
    strikes_b = _generate_strikes(int(first_strike) + _ROWS_PER_SECTION * int(addon), int(addon), _ROWS_PER_SECTION)

    _render_table_section(
        label="Section B",
        option_type="CE",
        strikes=strikes_b,
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        multiplier=multiplier, ratio=ratio,
        trade_date=trade_date,
        section_key="C",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Block 4: Puts again (7 rows)
    _render_table_section(
        label="Section B",
        option_type="PE",
        strikes=strikes_b,
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        multiplier=multiplier, ratio=ratio,
        trade_date=trade_date,
        section_key="D",
    )
