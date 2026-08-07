"""
tabs/tab_nfo_bfo.py - Complete rebuild matching UI reference
- 2 sections only, each with own controls
- Fetch Data button pattern (no auto-processing)
- Current spread + Day H/L in table
- Live chart + Historical chart per section
"""
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd

from data_api import (
    UNDERLYINGS, get_expiries, get_atm, _STRIKE_GAP,
    get_spread_history, compute_day_stats, resample_spread,
    round_to_nearest_50, _build_fyers_symbol, _get_fyers,
    get_expiry_code, _mock_ltp,
)

_DEFAULT_RATIO      = 3.3
_DEFAULT_MULTIPLIER = 3.3
_DEFAULT_ADDON      = 500
_ROWS               = 7

# ── Palette ───────────────────────────────────────────────────────────────────
_BG      = "#06080f"
_PANEL   = "#0e1220"
_CARD    = "#141a30"
_EDGE    = "#1f2846"
_CYAN    = "#00cbd6"
_TEXT    = "#eef0f6"
_MUTED   = "#7c87a5"
_GREEN   = "#10b981"
_RED     = "#ef4444"


def _fmt(val):
    if val is None: return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}"

def _color(val):
    if val is None: return _MUTED
    if val > 0: return _GREEN
    if val < 0: return _RED
    return _MUTED

def _second_strike(first, multiplier):
    return round_to_nearest_50(first / multiplier)

def _generate_strikes(first, addon, count):
    return [first + i * addon for i in range(count)]


# ── Batch fetch LTPs ─────────────────────────────────────────────────────────

def _batch_fetch(strikes, option_type, ex1, und1, exp1, ex2, und2, exp2, multiplier, ratio):
    from data_api import _get_fyers, get_expiry_code, _build_fyers_symbol, _mock_ltp
    stk2_list = [_second_strike(s, multiplier) for s in strikes]
    code1 = get_expiry_code(und1, exp1)
    code2 = get_expiry_code(und2, exp2)
    sym1_list = [_build_fyers_symbol(ex1, und1, code1, s, option_type) for s in strikes]
    sym2_list = [_build_fyers_symbol(ex2, und2, code2, s, option_type) for s in stk2_list]

    fyers = _get_fyers()
    ltp_map = {}
    if fyers:
        all_syms = sym1_list + sym2_list
        for i in range(0, len(all_syms), 50):
            batch = all_syms[i:i+50]
            try:
                resp = fyers.quotes(data={"symbols": ",".join(batch)})
                if resp.get("s") == "ok":
                    for item in resp["d"]:
                        sym = item.get("n","")
                        v   = item.get("v",{})
                        ltp = v.get("lp") or v.get("last_price") or v.get("close_price")
                        if ltp and sym:
                            ltp_map[sym] = float(ltp)
            except Exception as ex:
                st.warning(f"Batch LTP error: {ex}")

    rows = []
    for i, stk1 in enumerate(strikes):
        stk2 = stk2_list[i]
        ltp1 = ltp_map.get(sym1_list[i]) or (_mock_ltp(und1, stk1) if not fyers else None)
        ltp2 = ltp_map.get(sym2_list[i]) or (_mock_ltp(und2, stk2) if not fyers else None)
        current = round(ltp1 - ltp2 * ratio, 2) if ltp1 and ltp2 else None
        rows.append({"stk1": stk1, "stk2": stk2, "current": current,
                     "sym1": sym1_list[i], "sym2": sym2_list[i]})
    return rows


# ── Chart builders ────────────────────────────────────────────────────────────

def _build_live_chart(df: pd.DataFrame, title: str, resolution: str = "1 Minute", chart_type: str = "Line") -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.update_layout(
            height=380, plot_bgcolor=_PANEL, paper_bgcolor=_BG,
            annotations=[dict(text="No data available", showarrow=False,
                x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(color=_MUTED, size=14))]
        )
        return fig

    df_r = resample_spread(df, resolution)

    if chart_type == "Candlestick" and "open" in df_r.columns:
        fig.add_trace(go.Candlestick(
            x=df_r["timestamp"],
            open=df_r["open"], high=df_r["high"],
            low=df_r["low"],  close=df_r["close"],
            increasing_line_color=_GREEN, decreasing_line_color=_RED,
            name="Spread",
        ))
        y_min = float(df_r["low"].min())
        y_max = float(df_r["high"].max())
    else:
        y_col = "spread" if "spread" in df_r.columns else "close"
        y_vals = df_r[y_col]
        fig.add_trace(go.Scatter(
            x=df_r["timestamp"], y=y_vals,
            mode="lines", name="Spread",
            line=dict(color=_CYAN, width=2),
            hovertemplate="<b>%{x|%H:%M}</b><br>Spread: <b>%{y:.2f}</b><extra></extra>",
        ))
        y_min = float(y_vals.min())
        y_max = float(y_vals.max())

    # Smart Y-axis: 5% padding above and below actual data range
    y_range  = max(y_max - y_min, 1.0)
    padding  = y_range * 0.07
    y_lo     = y_min - padding
    y_hi     = y_max + padding

    # H/L/O reference lines
    stats = compute_day_stats(df)
    for val, color, label, dash in [
        (stats.get("high"), _GREEN,   f"H {stats.get('high', 0):.2f}",  "dash"),
        (stats.get("low"),  _RED,     f"L {stats.get('low', 0):.2f}",   "dash"),
        (stats.get("open"), "#d29922",f"O {stats.get('open', 0):.2f}",  "longdash"),
    ]:
        if val is not None:
            fig.add_hline(y=val, line_dash=dash, line_color=color, line_width=1,
                annotation_text=label, annotation_position="right",
                annotation_font_color=color, annotation_font_size=10)

    # X-axis: market hours only (9:10 - 15:35)
    if not df_r.empty:
        ts = pd.to_datetime(df_r["timestamp"].iloc[0])
        d  = ts.date()
        x_min = pd.Timestamp(f"{d} 09:10:00")
        x_max = pd.Timestamp(f"{d} 15:35:00")
    else:
        x_min = x_max = None

    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color=_TEXT), x=0.01),
        height=380, plot_bgcolor=_PANEL, paper_bgcolor=_BG,
        font=dict(color=_MUTED, size=11),
        margin=dict(l=50, r=90, t=40, b=40),
        xaxis=dict(
            gridcolor=_EDGE, rangeslider=dict(visible=False),
            showspikes=True, spikecolor=_MUTED, spikemode="across",
            range=[x_min, x_max] if x_min else None,
            tickformat="%H:%M",
        ),
        yaxis=dict(
            gridcolor=_EDGE, showspikes=True, spikecolor=_MUTED,
            range=[y_lo, y_hi],
            autorange=False,
        ),
        hovermode="x unified",
        legend=dict(bgcolor=_CARD, bordercolor=_EDGE, borderwidth=1),
    )
    return fig


def _build_historical_chart(df_multi: pd.DataFrame, period: str) -> go.Figure:
    """Build daily OHLC candlestick from multi-day spread data."""
    fig = go.Figure()

    if df_multi.empty:
        fig.update_layout(
            height=280, plot_bgcolor=_PANEL, paper_bgcolor=_BG,
            font=dict(color=_MUTED, size=11),
            margin=dict(l=50, r=30, t=20, b=40),
            xaxis=dict(gridcolor=_EDGE),
            yaxis=dict(gridcolor=_EDGE),
            annotations=[dict(text="No historical data — click Fetch Data first",
                showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(color=_MUTED, size=13))]
        )
        return fig

    df_m = df_multi.copy()
    df_m["date"] = pd.to_datetime(df_m["timestamp"]).dt.date
    daily = df_m.groupby("date")["spread"].agg(
        open="first", high="max", low="min", close="last"
    ).reset_index()

    fig.add_trace(go.Candlestick(
        x=daily["date"].astype(str),
        open=daily["open"], high=daily["high"],
        low=daily["low"],  close=daily["close"],
        increasing_line_color=_GREEN, decreasing_line_color=_RED,
        name="Daily Spread",
    ))

    # Smart Y range
    y_min = float(daily["low"].min())
    y_max = float(daily["high"].max())
    y_range = max(y_max - y_min, 1.0)
    padding = y_range * 0.07

    fig.update_layout(
        title=dict(text=f"Historical Spread — {period}", font=dict(size=12, color=_TEXT), x=0.01),
        height=300, plot_bgcolor=_PANEL, paper_bgcolor=_BG,
        font=dict(color=_MUTED, size=11),
        margin=dict(l=50, r=30, t=40, b=40),
        xaxis=dict(gridcolor=_EDGE, rangeslider=dict(visible=False)),
        yaxis=dict(gridcolor=_EDGE, range=[y_min - padding, y_max + padding], autorange=False),
        hovermode="x unified",
    )
    return fig


# ── Section renderer ──────────────────────────────────────────────────────────

def _render_section(
    section_id: str, label: str,
    ex1, und1, exp1, ex2, und2, exp2,
    trade_date: date,
):
    # ── Per-section controls inside a form (no rerun until submit) ───────────
    with st.expander(f"⚙️ {label} Controls", expanded=True):
        with st.form(key=f"form_{section_id}"):
            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            with sc1:
                opt_type = st.selectbox("CE / PE", ["CE", "PE"], key=f"{section_id}_type")
            with sc2:
                first_strike = st.number_input(
                    "First Strike", value=_round_atm(und1, _DEFAULT_ADDON),
                    step=100, key=f"{section_id}_strike"
                )
            with sc3:
                multiplier = st.number_input(
                    "Multiplier", value=_DEFAULT_MULTIPLIER, step=0.01,
                    format="%.4f", key=f"{section_id}_mult"
                )
            with sc4:
                ratio = st.number_input(
                    "Ratio", value=_DEFAULT_RATIO, step=0.01,
                    format="%.4f", key=f"{section_id}_ratio"
                )
            with sc5:
                addon = st.number_input(
                    "Add-on", value=_DEFAULT_ADDON, step=50,
                    key=f"{section_id}_addon"
                )
            fetch_btn = st.form_submit_button(
                f"🔄 Fetch {label} Data", type="primary", use_container_width=False
            )

        # Store submitted values in session state so they persist
        if fetch_btn:
            st.session_state[f"{section_id}_submitted"] = {
                "opt_type":     opt_type,
                "first_strike": first_strike,
                "multiplier":   multiplier,
                "ratio":        ratio,
                "addon":        addon,
            }

    # Use submitted values if available, else defaults
    submitted = st.session_state.get(f"{section_id}_submitted", {})
    opt_type     = submitted.get("opt_type",     opt_type if not submitted else "CE")
    first_strike = submitted.get("first_strike", first_strike if not submitted else _round_atm(und1, _DEFAULT_ADDON))
    multiplier   = submitted.get("multiplier",   multiplier if not submitted else _DEFAULT_MULTIPLIER)
    ratio        = submitted.get("ratio",         ratio if not submitted else _DEFAULT_RATIO)
    addon        = submitted.get("addon",         addon if not submitted else _DEFAULT_ADDON)

    strikes = _generate_strikes(int(first_strike), int(addon), _ROWS)

    # ── Section header ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                margin:16px 0 12px;padding-bottom:10px;border-bottom:1px solid {_EDGE}">
        <div style="display:flex;align-items:center;gap:10px">
            <div style="width:8px;height:8px;border-radius:50%;
                        background:{'#58a6ff' if opt_type=='CE' else '#d29922'}"></div>
            <span style="font-size:0.85rem;font-weight:700;color:{_MUTED};
                         text-transform:uppercase;letter-spacing:2px;
                         font-family:JetBrains Mono,monospace">{label} — {opt_type}</span>
        </div>
        <span style="font-size:0.75rem;color:{_MUTED};font-family:JetBrains Mono,monospace">
            Ratio ×{ratio:.4f} · Multiplier ×{multiplier:.4f}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── Table header ─────────────────────────────────────────────────────────
    h1,h2,h3,h4,h5,h6 = st.columns([2,2,2,2,2,2])
    for col, hdr in zip([h1,h2,h3,h4,h5,h6],
                        ["First Strike","Second Strike","Current Spread","Day High","Day Low",""]):
        with col:
            st.markdown(
                f"<div style='font-size:0.7rem;color:{_MUTED};text-transform:uppercase;"
                f"letter-spacing:1px;padding:4px 4px 8px;"
                f"font-family:JetBrains Mono,monospace'>{hdr}</div>",
                unsafe_allow_html=True)

    st.markdown(f"<div style='border-top:1px solid {_EDGE};margin-bottom:4px'></div>",
                unsafe_allow_html=True)

    # ── Fetch data on button click ────────────────────────────────────────────
    data_key = f"{section_id}_data"
    hist_key = f"{section_id}_hist"

    if fetch_btn:
        with st.spinner(f"Fetching {label} data..."):
            rows = _batch_fetch(
                strikes, opt_type,
                ex1, und1, exp1,
                ex2, und2, exp2,
                multiplier, ratio
            )
            # Fetch H/L for each row
            for row in rows:
                df = get_spread_history(
                    ex1, und1, exp1, row["stk1"], opt_type,
                    ex2, und2, exp2, row["stk2"], opt_type,
                    trade_date, ratio=ratio,
                )
                stats = compute_day_stats(df)
                row["high"]    = stats.get("high")
                row["low"]     = stats.get("low")
                row["df"]      = df
            st.session_state[data_key] = rows

    rows = st.session_state.get(data_key, [
        {"stk1": s, "stk2": _second_strike(s, multiplier),
         "current": None, "high": None, "low": None, "df": pd.DataFrame()}
        for s in strikes
    ])

    # ── Render rows ───────────────────────────────────────────────────────────
    for i, row in enumerate(rows):
        row_key = f"{section_id}_{opt_type}_{i}"
        c1,c2,c3,c4,c5,c6 = st.columns([2,2,2,2,2,2])

        def cell(val, color=_TEXT, bold=False):
            fw = "700" if bold else "400"
            return (f"<div style='font-family:JetBrains Mono,monospace;font-size:0.88rem;"
                    f"padding:8px 4px;color:{color};font-weight:{fw}'>{val}</div>")

        with c1: st.markdown(cell(row["stk1"], _TEXT, bold=True), unsafe_allow_html=True)
        with c2: st.markdown(cell(row["stk2"], _MUTED), unsafe_allow_html=True)
        with c3: st.markdown(cell(_fmt(row["current"]), _CYAN if row["current"] else _MUTED, bold=True), unsafe_allow_html=True)
        with c4: st.markdown(cell(_fmt(row.get("high")), _GREEN), unsafe_allow_html=True)
        with c5: st.markdown(cell(_fmt(row.get("low")), _RED), unsafe_allow_html=True)
        with c6:
            if st.button("📈 View Chart", key=f"btn_{row_key}"):
                k = f"chart_{section_id}"
                st.session_state[k] = i
                # Store selected row df
                st.session_state[f"chart_df_{section_id}"] = row.get("df", pd.DataFrame())
                st.session_state[f"chart_title_{section_id}"] = (
                    f"{und1} {row['stk1']} vs {und2} {row['stk2']} · {opt_type}"
                )

        st.markdown(f"<div style='border-top:1px solid {_EDGE}22;margin:2px 0'></div>",
                    unsafe_allow_html=True)

    # ── Live chart (shown when any View Chart clicked) ────────────────────────
    chart_key = f"chart_{section_id}"
    if chart_key in st.session_state:
        selected_idx = st.session_state[chart_key]
        df_chart     = st.session_state.get(f"chart_df_{section_id}", pd.DataFrame())
        chart_title  = st.session_state.get(f"chart_title_{section_id}", "")
        stats        = compute_day_stats(df_chart)

        st.markdown(f"""
        <div style="background:{_PANEL};border:1px solid {_EDGE};border-radius:12px;
                    padding:14px 20px;margin:16px 0 8px">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
                <div style="display:flex;align-items:center;gap:10px">
                    <div style="width:28px;height:28px;border-radius:8px;
                                background:rgba(0,203,214,0.1);border:1px solid rgba(0,203,214,0.3);
                                display:flex;align-items:center;justify-content:center;color:{_CYAN};font-size:12px">⚡</div>
                    <span style="font-size:0.85rem;font-weight:600;color:{_TEXT}">Live Spread Chart</span>
                    <span style="font-size:0.75rem;color:{_MUTED};font-family:JetBrains Mono,monospace">{chart_title}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Stats bar
        sc1,sc2,sc3,sc4,sc5,sc6 = st.columns(6)
        for col, lbl, k, clr in [
            (sc1,"Open","open",_TEXT),
            (sc2,"High","high",_GREEN),
            (sc3,"Low","low",_RED),
            (sc4,"Current","current",_CYAN),
            (sc5,"High @","high_time",_MUTED),
            (sc6,"Low @","low_time",_MUTED),
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
                <div style="background:{_CARD};border:1px solid {_EDGE};border-radius:10px;
                            padding:12px 16px">
                    <div style="font-size:0.68rem;color:{_MUTED};text-transform:uppercase;
                                letter-spacing:1px;font-family:JetBrains Mono,monospace;
                                margin-bottom:6px">{lbl}</div>
                    <div style="font-size:1.2rem;font-weight:700;
                                font-family:JetBrains Mono,monospace;color:{clr}">{display}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Resolution selector
        res_col, type_col, _ = st.columns([2, 2, 6])
        with res_col:
            resolution = st.selectbox(
                "Interval", ["1 Minute","5 Minutes","15 Minutes","30 Seconds"],
                index=0, key=f"res_{section_id}"
            )
        with type_col:
            chart_type = st.selectbox(
                "Type", ["Line","Candlestick"], key=f"ctype_{section_id}"
            )

        # Build chart
        if chart_type == "Candlestick" and not df_chart.empty:
            df_r = resample_spread(df_chart, resolution)
            if "open" in df_r.columns:
                fig = go.Figure(go.Candlestick(
                    x=df_r["timestamp"],
                    open=df_r["open"], high=df_r["high"],
                    low=df_r["low"],  close=df_r["close"],
                    increasing_line_color=_GREEN, decreasing_line_color=_RED,
                ))
            else:
                fig = _build_live_chart(df_chart, chart_title, resolution)
        else:
            fig = _build_live_chart(df_chart, chart_title, resolution)

        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        # ── Historical chart ──────────────────────────────────────────────────
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:20px 0 10px">
            <div style="width:28px;height:28px;border-radius:8px;
                        background:rgba(0,203,214,0.1);border:1px solid rgba(0,203,214,0.3);
                        display:flex;align-items:center;justify-content:center;
                        color:{_CYAN};font-size:12px">🕐</div>
            <span style="font-size:0.85rem;font-weight:600;color:{_TEXT}">Historical Spread Trend</span>
        </div>
        """, unsafe_allow_html=True)

        hist_col, fetch_hist_col, _ = st.columns([2, 2, 6])
        with hist_col:
            hist_days = st.selectbox(
                "Period", ["1D","5D","1M","6M"],
                index=0, key=f"hist_{section_id}"
            )
        with fetch_hist_col:
            st.markdown("<br>", unsafe_allow_html=True)
            fetch_hist = st.button("Load History", key=f"fetch_hist_{section_id}")

        days_map = {"1D": 1, "5D": 5, "1M": 22, "6M": 130}
        n_days = days_map[hist_days]

        if fetch_hist and rows:
            row = rows[selected_idx] if selected_idx < len(rows) else rows[0]
            frames = []
            d = trade_date
            collected = 0
            with st.spinner(f"Loading {hist_days} history..."):
                while collected < n_days:
                    if d.weekday() < 5:
                        df_d = get_spread_history(
                            ex1, und1, exp1, row["stk1"], opt_type,
                            ex2, und2, exp2, row["stk2"], opt_type,
                            d, ratio=ratio,
                        )
                        if not df_d.empty:
                            frames.append(df_d)
                        collected += 1
                    d -= timedelta(days=1)
            st.session_state[f"hist_df_{section_id}"] = (
                pd.concat(frames[::-1], ignore_index=True) if frames else pd.DataFrame()
            )

        df_hist = st.session_state.get(f"hist_df_{section_id}", pd.DataFrame())
        fig_hist = _build_historical_chart(df_hist, hist_days)
        st.plotly_chart(fig_hist, use_container_width=True, config={"scrollZoom": True})


def _round_atm(underlying, addon):
    atm = get_atm(underlying)
    return int(round(atm / addon) * addon)


# ── Main render ───────────────────────────────────────────────────────────────

def render_tab():
    # ── Top Controls ─────────────────────────────────────────────────────────
    st.markdown("### NFO-BFO Spread Analysis")
    st.caption("Configure legs below. Click **Fetch Data** in each section to load spreads.")

    with st.expander("⚙️ Common Controls", expanded=True):
        with st.form(key="nfo_common_form"):
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                st.markdown("**First Leg**")
                ex1  = st.selectbox("Exchange",   ["BSE","NSE"], index=0,  key="nfo_ex1")
                und1 = st.selectbox("Index",      UNDERLYINGS.get(ex1,["SENSEX"]), key="nfo_und1")
                exp1_list = get_expiries(ex1, und1)
                exp1 = st.selectbox("Expiry",     exp1_list, key="nfo_exp1")
            with r2:
                st.markdown("**Second Leg**")
                ex2  = st.selectbox("Exchange",   ["NSE","BSE"], index=0,  key="nfo_ex2")
                und2 = st.selectbox("Index",      UNDERLYINGS.get(ex2,["NIFTY"]), key="nfo_und2")
                exp2_list = get_expiries(ex2, und2)
                exp2 = st.selectbox("Expiry",     exp2_list, key="nfo_exp2")
            with r3:
                st.markdown("**Date**")
                trade_date = st.date_input("Date", value=date.today(),
                                           max_value=date.today(), key="nfo_date")
            with r4:
                st.markdown(" ")
                st.markdown("<br>", unsafe_allow_html=True)
                st.form_submit_button("✅ Apply Common Settings", use_container_width=True)

    st.markdown("---")

    # ── Section A ─────────────────────────────────────────────────────────────
    _render_section(
        section_id="A", label="Section A",
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        trade_date=trade_date,
    )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ── Section B ─────────────────────────────────────────────────────────────
    _render_section(
        section_id="B", label="Section B",
        ex1=ex1, und1=und1, exp1=exp1,
        ex2=ex2, und2=und2, exp2=exp2,
        trade_date=trade_date,
    )
