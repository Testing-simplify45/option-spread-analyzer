"""
tabs/tab_spread_analysis.py
============================
Tab 1 – General Spread Analysis

Allows the user to manually select any two option legs and view:
  • Live spread value
  • Historical spread chart (with selectable date & resolution)
  • OHLC stats (Open / High / Low / Current)
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from data_api import (
    EXCHANGES,
    UNDERLYINGS,
    get_expiries,
    get_strikes,
    get_ltp,
    get_spread_history,
    resample_spread,
    compute_day_stats,
    get_atm,
    _STRIKE_GAP,
    get_expiry_code,
)
from chart_utils import build_spread_line_chart


# ── Helpers ──────────────────────────────────────────────────────────────────

def _color_class(val: float | None) -> str:
    if val is None:
        return "neutral"
    return "pos" if val > 0 else ("neg" if val < 0 else "neutral")


def _fmt(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{decimals}f}"


# ── Main render ──────────────────────────────────────────────────────────────

def render_tab():
    st.markdown("### Contract Selection")
    st.caption("Select two option legs. The spread = Leg 1 price − Leg 2 price.")

    col_leg1, col_sep, col_leg2 = st.columns([5, 0.3, 5])

    # ── Leg 1 ────────────────────────────────────────────────────────────────
    with col_leg1:
        st.markdown(
            '<div class="section-header"><div class="section-dot"></div>'
            '<h3>Leg 1 &nbsp;·&nbsp; First Contract</h3></div>',
            unsafe_allow_html=True,
        )
        l1_exchange = st.selectbox("Exchange", EXCHANGES, key="l1_ex")
        l1_under = st.selectbox("Underlying", UNDERLYINGS[l1_exchange], key="l1_und")
        l1_expiries = get_expiries(l1_exchange, l1_under)
        l1_expiry = st.selectbox("Expiry", l1_expiries, key="l1_exp")
        l1_strikes = get_strikes(l1_exchange, l1_under, l1_expiry)
        l1_strike = st.number_input("Strike", value=get_atm(l1_under),
                                     step=_STRIKE_GAP.get(l1_under, 50), key="l1_stk")
        l1_type = st.selectbox("Option Type", ["CE", "PE"], key="l1_type")

    with col_sep:
        st.markdown("<br><br><br><br><br><br><br>⟷", unsafe_allow_html=True)

    # ── Leg 2 ────────────────────────────────────────────────────────────────
    with col_leg2:
        st.markdown(
            '<div class="section-header"><div class="section-dot" style="background:#f85149"></div>'
            '<h3>Leg 2 &nbsp;·&nbsp; Second Contract</h3></div>',
            unsafe_allow_html=True,
        )
        l2_exchange = st.selectbox("Exchange", EXCHANGES, index=1, key="l2_ex")
        l2_under = st.selectbox("Underlying", UNDERLYINGS[l2_exchange], key="l2_und")
        l2_expiries = get_expiries(l2_exchange, l2_under)
        l2_expiry = st.selectbox("Expiry", l2_expiries, key="l2_exp")
        l2_strikes = get_strikes(l2_exchange, l2_under, l2_expiry)
        l2_strike = st.number_input("Strike", value=get_atm(l2_under),
                                     step=_STRIKE_GAP.get(l2_under, 50), key="l2_stk")
        l2_type = st.selectbox("Option Type", ["CE", "PE"], key="l2_type")

    st.markdown("<hr class='leg-divider'>", unsafe_allow_html=True)

    # ── Live Spread ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-header"><div class="section-dot"></div><h3>Live Spread</h3></div>',
        unsafe_allow_html=True,
    )

    refresh_col, _ = st.columns([2, 8])
    with refresh_col:
        refresh = st.button("🔄 Refresh Prices", key="t1_refresh")

    ltp1 = get_ltp(l1_exchange, l1_under, l1_expiry, l1_strike, l1_type)
    ltp2 = get_ltp(l2_exchange, l2_under, l2_expiry, l2_strike, l2_type)
    spread_live = None
    if ltp1 is not None and ltp2 is not None:
        spread_live = round(ltp1 - ltp2, 2)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Leg 1 LTP</div>
            <div class="metric-value neutral">{ltp1 if ltp1 else '—'}</div>
        </div>""", unsafe_allow_html=True)
    with mc2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Leg 2 LTP</div>
            <div class="metric-value neutral">{ltp2 if ltp2 else '—'}</div>
        </div>""", unsafe_allow_html=True)
    with mc3:
        cc = _color_class(spread_live)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Spread</div>
            <div class="metric-value {cc}">{_fmt(spread_live)}</div>
        </div>""", unsafe_allow_html=True)
    with mc4:
        formula = f"{ltp1 or '?'} − {ltp2 or '?'}"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Formula</div>
            <div class="metric-value neutral" style="font-size:1rem;">{formula}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart Controls ───────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-header"><div class="section-dot"></div><h3>Historical Chart</h3></div>',
        unsafe_allow_html=True,
    )

    ctrl1, ctrl2, ctrl3 = st.columns([3, 3, 3])
    with ctrl1:
        date_options = {
            "Today": date.today(),
            "Yesterday": date.today() - timedelta(days=1),
            "2 Days Ago": date.today() - timedelta(days=2),
            "Custom": None,
        }
        date_choice = st.selectbox("Date", list(date_options.keys()), key="t1_date_choice")

    with ctrl2:
        if date_choice == "Custom":
            selected_date = st.date_input(
                "Pick date",
                value=date.today() - timedelta(days=3),
                max_value=date.today(),
                key="t1_custom_date",
            )
        else:
            selected_date = date_options[date_choice]
            st.date_input("Date (locked)", value=selected_date, disabled=True, key="t1_locked_date")

    with ctrl3:
        resolution = st.selectbox(
            "Resolution",
            ["Tick", "30 Seconds", "1 Minute", "5 Minutes", "15 Minutes"],
            index=2,
            key="t1_resolution",
        )

    # ── Load & Display Chart ─────────────────────────────────────────────────
    with st.spinner("Loading historical data..."):
        df = get_spread_history(
            l1_exchange, l1_under, l1_expiry, l1_strike, l1_type,
            l2_exchange, l2_under, l2_expiry, l2_strike, l2_type,
            selected_date,
            ratio=1.0,
        )

    stats = compute_day_stats(df)
    df_resampled = resample_spread(df, resolution)

    # OHLC Metric bar
    sc1, sc2, sc3, sc4 = st.columns(4)
    labels = ["Open", "High", "Low", "Current"]
    keys = ["open", "high", "low", "current"]
    colors = ["neutral", "pos", "neg", _color_class(stats.get("current"))]
    for col, lbl, key, clr in zip([sc1, sc2, sc3, sc4], labels, keys, colors):
        with col:
            val = stats.get(key)
            extra = ""
            if key == "high" and stats.get("high_time"):
                extra = f'<div class="metric-label" style="margin-top:4px">@ {stats["high_time"].strftime("%H:%M")}</div>'
            if key == "low" and stats.get("low_time"):
                extra = f'<div class="metric-label" style="margin-top:4px">@ {stats["low_time"].strftime("%H:%M")}</div>'
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{lbl}</div>
                <div class="metric-value {clr}">{_fmt(val)}</div>
                {extra}
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if df_resampled.empty:
        st.info("No data available for the selected date.")
    else:
        chart_title = (
            f"{l1_under} {l1_strike}{l1_type} − {l2_under} {l2_strike}{l2_type}  ·  "
            f"{selected_date.strftime('%d %b %Y')}  ·  {resolution}"
        )
        fig = build_spread_line_chart(df_resampled, title=chart_title, stats=stats, resolution=resolution)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
