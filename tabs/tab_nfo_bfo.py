"""
tabs/tab_nfo_bfo.py - Clean version: H/L only in chart, not in table
"""
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st

from data_api import (
    UNDERLYINGS, get_expiries, get_strikes, get_atm,
    get_spread_history, compute_day_stats,
    round_to_nearest_50, _build_fyers_symbol, _mock_ltp,
)
from chart_utils import build_spread_line_chart

_DEFAULT_RATIO      = 3.3
_DEFAULT_MULTIPLIER = 3.3
_DEFAULT_ADDON      = 500
_ROWS_PER_SECTION   = 7


def _round_nearest_atm(underlying, addon):
    atm = get_atm(underlying)
    return int(round(atm / addon) * addon)

def _fmt(val):
    if val is None: return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}"

def _color(val):
    if val is None: return "#8b949e"
    if val > 0: return "#3fb950"
    if val < 0: return "#f85149"
    return "#8b949e"

def _second_strike(first, multiplier):
    return round_to_nearest_50(first / multiplier)

def _generate_strikes(first, addon, count):
    return [first + i * addon for i in range(count)]

def _prev_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ── Batch fetch LTPs for entire section ──────────────────────────────────────

def _fetch_section_ltps(
    strikes, option_type,
    ex1, und1, exp1,
    ex2, und2, exp2,
    multiplier, ratio,
):
    """
    Fetch all LTPs for a section in ONE batch API call.
    Returns list of (stk1, stk2, current_spread) per row.
    """
    from data_api import _get_fyers

    stk2_list = [_second_strike(s, multiplier) for s in strikes]
    sym1_list = [_build_fyers_symbol(ex1, und1, exp1, s, option_type) for s in strikes]
    sym2_list = [_build_fyers_symbol(ex2, und2, exp2, s, option_type) for s in stk2_list]

    fyers = _get_fyers()
    ltp_map = {}

    if fyers is not None:
        all_symbols = sym1_list + sym2_list
        for i in range(0, len(all_symbols), 50):
            batch = all_symbols[i:i+50]
            try:
                resp = fyers.quotes(data={"symbols": ",".join(batch)})
                if resp.get("s") == "ok":
                    for item in resp["d"]:
                        sym = item.get("n", "")
                        v = item.get("v", {})
                        ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
                        if ltp and sym:
                            ltp_map[sym] = float(ltp)
            except Exception as ex:
                st.warning(f"Batch LTP error: {ex}")

    rows = []
    for i, stk1 in enumerate(strikes):
        stk2 = stk2_list[i]
        sym1 = sym1_list[i]
        sym2 = sym2_list[i]

        if fyers is not None:
            ltp1 = ltp_map.get(sym1)
            ltp2 = ltp_map.get(sym2)
        else:
            ltp1 = _mock_ltp(und1, stk1)
            ltp2 = _mock_ltp(und2, stk2)

        current = None
        if ltp1 is not None and ltp2 is not None:
            current = round(ltp1 - ltp2 * ratio, 2)

        rows.append({
            "stk1": stk1, "stk2": stk2,
            "sym1": sym1, "sym2": sym2,
            "ltp1": ltp1, "ltp2": ltp2,
            "current": current,
        })

    return rows


# ── Table section renderer ────────────────────────────────────────────────────

def _render_section(
    label, option_type, strikes,
    ex1, und1, exp1,
    ex2, und2, exp2,
    multiplier, ratio, trade_date,
    section_key,
):
    st.markdown(
        f'<div class="section-header">'
        f'<div class="section-dot" style="background:{"#58a6ff" if option_type=="CE" else "#d29922"}"></div>'
        f'<h3>{label} — {option_type}</h3></div>',
        unsafe_allow_html=True,
    )

    # Column headers
    h1,h2,h3,h4 = st.columns([2,2,3,2])
    for col, hdr in zip([h1,h2,h3,h4], ["First Strike","Second Strike","Current Spread",""]):
        with col:
            st.markdown(
                f"<div style='font-size:0.72rem;color:#8b949e;text-transform:uppercase;"
                f"letter-spacing:1px;padding:4px 4px 8px;font-family:JetBrains Mono,monospace'>"
                f"{hdr}</div>", unsafe_allow_html=True)

    st.markdown("<div style='border-top:1px solid #1e263d;margin-bottom:4px'></div>", unsafe_allow_html=True)

    # Fetch all LTPs in one batch
    with st.spinner(f"Loading {option_type} spreads..."):
        rows = _fetch_section_ltps(
            strikes, option_type,
            ex1, und1, exp1,
            ex2, und2, exp2,
            multiplier, ratio,
        )

    # Render rows
    for i, row in enumerate(rows):
        row_key = f"{section_key}_{option_type}_{i}"
        c1,c2,c3,c4 = st.columns([2,2,3,2])

        def cell(val, color="#e6edf3", bold=False):
            fw = "700" if bold else "400"
            return (f"<div style='font-family:JetBrains Mono,monospace;font-size:0.9rem;"
                    f"padding:8px 4px;color:{color};font-weight:{fw}'>{val}</div>")

        with c1: st.markdown(cell(row["stk1"], "#e6edf3", bold=True), unsafe_allow_html=True)
        with c2: st.markdown(cell(row["stk2"], "#8b949e"), unsafe_allow_html=True)
        with c3: st.markdown(cell(_fmt(row["current"]), _color(row["current"]), bold=True), unsafe_allow_html=True)
        with c4:
            if st.button("📈 View Chart", key=f"btn_{row_key}"):
                k = f"chart_{row_key}"
                st.session_state[k] = not st.session_state.get(k, False)

        # Chart (lazy — only renders on click, fetches history HERE)
        if st.session_state.get(f"chart_{row_key}", False):
            stk1, stk2 = row["stk1"], row["stk2"]
            with st.spinner("Loading chart data..."):
                df = get_spread_history(
                    ex1, und1, exp1, stk1, option_type,
                    ex2, und2, exp2, stk2, option_type,
                    trade_date, ratio=ratio,
                )
            stats = compute_day_stats(df)

            # Stats bar
            sc1,sc2,sc3,sc4,sc5,sc6 = st.columns(6)
            for col, lbl, k, clr in [
                (sc1,"Open","open","#e6edf3"),
                (sc2,"High","high","#3fb950"),
                (sc3,"Low","low","#f85149"),
                (sc4,"Current","current","#58a6ff"),
                (sc5,"High @","high_time","#8b949e"),
                (sc6,"Low @","low_time","#8b949e"),
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

            df_chart = df[["timestamp","spread"]].copy() if not df.empty else df
            title = f"{und1} {stk1} vs {und2} {stk2}  ·  {option_type}  ·  {trade_date.strftime('%d %b %Y')}"
            fig = build_spread_line_chart(df_chart, title=title, stats=stats, resolution="Tick")
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        st.markdown("<div style='border-top:1px solid #1c2230;margin:2px 0'></div>", unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render_tab():
    st.markdown("### NFO-BFO Spread Analysis")
    st.caption("Spread = First Leg − (Second Leg × Ratio)  ·  Click View Chart for High/Low/Open/Close")

    with st.expander("⚙️  Controls", expanded=True):
        r1c1,r1c2,r1c3,r1c4 = st.columns(4)
        with r1c1:
            st.markdown("**Exchange**")
            ex1 = st.selectbox("First Leg Exchange", ["BSE","NSE"], index=0, key="nfo_ex1")
            ex2 = st.selectbox("Second Leg Exchange", ["NSE","BSE"], index=0, key="nfo_ex2")
        with r1c2:
            st.markdown("**Index**")
            und1 = st.selectbox("First Leg Index", UNDERLYINGS.get(ex1,["SENSEX"]), key="nfo_und1")
            und2 = st.selectbox("Second Leg Index", UNDERLYINGS.get(ex2,["NIFTY"]), key="nfo_und2")
        with r1c3:
            st.markdown("**Parameters**")
            ratio = st.number_input("Ratio", value=_DEFAULT_RATIO, step=0.01, format="%.4f", key="nfo_ratio")
            multiplier = st.number_input("Multiplier", value=_DEFAULT_MULTIPLIER, step=0.01, format="%.4f", key="nfo_mult")
        with r1c4:
            st.markdown("**Strike Ladder**")
            addon = st.number_input("Add-on", value=_DEFAULT_ADDON, step=50, key="nfo_addon")
            trade_date = st.date_input("Date", value=date.today(), max_value=date.today(), key="nfo_date")

        r2c1,r2c2,_ = st.columns([3,3,4])
        with r2c1:
            exp1 = st.selectbox("First Leg Expiry", get_expiries(ex1, und1), key="nfo_exp1")
        with r2c2:
            exp2 = st.selectbox("Second Leg Expiry", get_expiries(ex2, und2), key="nfo_exp2")

        r3c1,_,__ = st.columns([3,3,4])
        with r3c1:
            first_strike = st.number_input(
                "First Strike", value=_round_nearest_atm(und1, int(addon)),
                step=int(addon), key="nfo_first_strike"
            )

    st.markdown("---")

    col_rf, col_note = st.columns([2,8])
    with col_rf:
        if st.button("🔄 Refresh", key="nfo_refresh"):
            st.rerun()
    with col_note:
        st.caption(f"Ratio ×{ratio:.4f}  ·  Multiplier ×{multiplier:.4f}  ·  High/Low visible in chart on click")

    st.markdown("<br>", unsafe_allow_html=True)

    strikes_a = _generate_strikes(int(first_strike), int(addon), _ROWS_PER_SECTION)
    strikes_b = _generate_strikes(int(first_strike) + _ROWS_PER_SECTION * int(addon), int(addon), _ROWS_PER_SECTION)

    _render_section("Section A","CE", strikes_a, ex1,und1,exp1, ex2,und2,exp2, multiplier,ratio,trade_date,"A")
    st.markdown("<br>", unsafe_allow_html=True)
    _render_section("Section A","PE", strikes_a, ex1,und1,exp1, ex2,und2,exp2, multiplier,ratio,trade_date,"B")
    st.markdown("<br>", unsafe_allow_html=True)
    _render_section("Section B","CE", strikes_b, ex1,und1,exp1, ex2,und2,exp2, multiplier,ratio,trade_date,"C")
    st.markdown("<br>", unsafe_allow_html=True)
    _render_section("Section B","PE", strikes_b, ex1,und1,exp1, ex2,und2,exp2, multiplier,ratio,trade_date,"D")
