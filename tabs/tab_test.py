"""
tabs/tab_test.py
================
Test tab to validate 1-min candle High/Low calculation.
Simple spread: Leg1 - (Leg2 × Ratio)
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_api import (
    EXCHANGES, UNDERLYINGS, get_expiries, get_strikes,
    _build_fyers_symbol, _get_fyers, get_expiry_code,
    get_atm, _STRIKE_GAP,
)


def _fetch_1min_candles(fyers, symbol: str, trade_date: date) -> pd.DataFrame:
    """
    Fetch 1-minute OHLC candles from Fyers.
    Returns DataFrame with columns: timestamp, open, high, low, close
    """
    date_str = trade_date.strftime("%Y-%m-%d")
    try:
        resp = fyers.history(data={
            "symbol":     symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": date_str,
            "range_to":   date_str,
            "cont_flag":  "1",
        })

        if resp.get("s") == "ok" and resp.get("candles"):
            df = pd.DataFrame(
                resp["candles"],
                columns=["timestamp","open","high","low","close","volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            return df

        # Show full response so we can debug
        st.warning(f"Candle response for {symbol}: {resp}")

    except Exception as ex:
        st.error(f"Candle fetch error for {symbol}: {ex}")

    return pd.DataFrame()


def render_tab():
    st.markdown("### 🧪 Test Tab — 1-Min Candle Spread")
    st.caption(
        "Testing if Fyers 1-min candles work correctly. "
        "Spread = Leg1 Close − (Leg2 Close × Ratio). "
        "High/Low computed from candle highs/lows."
    )

    st.markdown("---")

    # ── Controls ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        trade_date = st.date_input(
            "Date", value=date.today(), max_value=date.today(), key="test_date"
        )
    with col2:
        ratio = st.number_input(
            "Ratio", value=3.3, step=0.01, format="%.4f", key="test_ratio"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔄 Fetch Data", key="test_fetch")

    st.markdown("---")

    # ── Leg 1 ─────────────────────────────────────────────────────────────────
    st.markdown("#### Leg 1")
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        l1_ex  = st.selectbox("Exchange",    EXCHANGES, index=1, key="t_l1_ex")
    with c2:
        l1_und = st.selectbox("Underlying",  UNDERLYINGS[l1_ex], key="t_l1_und")
    with c3:
        l1_exp = st.selectbox("Expiry",      get_expiries(l1_ex, l1_und), key="t_l1_exp")
    with c4:
        l1_stk = st.number_input("Strike", value=get_atm(l1_und),
                                  step=_STRIKE_GAP.get(l1_und, 50), key="t_l1_stk")
    with c5:
        l1_typ = st.selectbox("Type", ["CE","PE"], key="t_l1_typ")

    # ── Leg 2 ─────────────────────────────────────────────────────────────────
    st.markdown("#### Leg 2")
    d1,d2,d3,d4,d5 = st.columns(5)
    with d1:
        l2_ex  = st.selectbox("Exchange",    EXCHANGES, index=0, key="t_l2_ex")
    with d2:
        l2_und = st.selectbox("Underlying",  UNDERLYINGS[l2_ex], key="t_l2_und")
    with d3:
        l2_exp = st.selectbox("Expiry",      get_expiries(l2_ex, l2_und), key="t_l2_exp")
    with d4:
        l2_stk = st.number_input("Strike", value=get_atm(l2_und),
                                  step=_STRIKE_GAP.get(l2_und, 50), key="t_l2_stk")
    with d5:
        l2_typ = st.selectbox("Type", ["CE","PE"], key="t_l2_typ")

    st.markdown("---")

    # ── Fetch & Display ───────────────────────────────────────────────────────
    if not fetch_btn:
        st.info("👆 Configure your legs above and click **Fetch Data**")
        return

    fyers = _get_fyers()
    if fyers is None:
        st.error("❌ Not connected to Fyers! Please login first.")
        return

    sym1 = _build_fyers_symbol(l1_ex, l1_und, get_expiry_code(l1_und, l1_exp), l1_stk, l1_typ)
    sym2 = _build_fyers_symbol(l2_ex, l2_und, get_expiry_code(l2_und, l2_exp), l2_stk, l2_typ)

    st.markdown(f"**Fetching:** `{sym1}` and `{sym2}`")

    with st.spinner("Fetching 1-min candles from Fyers..."):
        df1 = _fetch_1min_candles(fyers, sym1, trade_date)
        df2 = _fetch_1min_candles(fyers, sym2, trade_date)

    # ── Show raw data for debugging ───────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Leg 1 candles:** `{sym1}`")
        if df1.empty:
            st.error("❌ No data returned for Leg 1")
        else:
            st.success(f"✅ {len(df1)} candles received")
            st.dataframe(df1.tail(5), use_container_width=True)

    with col_b:
        st.markdown(f"**Leg 2 candles:** `{sym2}`")
        if df2.empty:
            st.error("❌ No data returned for Leg 2")
        else:
            st.success(f"✅ {len(df2)} candles received")
            st.dataframe(df2.tail(5), use_container_width=True)

    if df1.empty or df2.empty:
        st.error("Cannot compute spread — one or both legs have no data.")
        return

    # ── Compute Spread ────────────────────────────────────────────────────────
    df1 = df1.set_index("timestamp")
    df2 = df2.set_index("timestamp")

    # Align on common timestamps
    combined = pd.DataFrame({
        "leg1_close": df1["close"],
        "leg2_close": df2["close"],
        "leg1_high":  df1["high"],
        "leg1_low":   df1["low"],
        "leg2_high":  df2["high"],
        "leg2_low":   df2["low"],
    }).dropna()

    if combined.empty:
        st.error("❌ No overlapping timestamps between Leg 1 and Leg 2!")
        st.info("Leg 1 times: " + str(df1.index[:3].tolist()))
        st.info("Leg 2 times: " + str(df2.index[:3].tolist()))
        return

    # Spread close = leg1_close - (leg2_close × ratio)
    combined["spread"]      = combined["leg1_close"] - combined["leg2_close"] * ratio
    # Spread high  = leg1_high  - (leg2_low   × ratio)  ← conservative estimate
    combined["spread_high"] = combined["leg1_high"]  - combined["leg2_low"]  * ratio
    # Spread low   = leg1_low   - (leg2_high  × ratio)
    combined["spread_low"]  = combined["leg1_low"]   - combined["leg2_high"] * ratio

    combined = combined.reset_index()

    # ── Day Stats ─────────────────────────────────────────────────────────────
    day_open    = round(float(combined["spread"].iloc[0]), 2)
    day_high    = round(float(combined["spread_high"].max()), 2)
    day_low     = round(float(combined["spread_low"].min()), 2)
    day_current = round(float(combined["spread"].iloc[-1]), 2)
    high_time   = combined.loc[combined["spread_high"].idxmax(), "timestamp"].strftime("%H:%M")
    low_time    = combined.loc[combined["spread_low"].idxmin(),  "timestamp"].strftime("%H:%M")

    # ── Metric Cards ──────────────────────────────────────────────────────────
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    for col, lbl, val, clr in [
        (m1, "Open",    f"{day_open:+.2f}",    "#e6edf3"),
        (m2, "High",    f"{day_high:+.2f}",    "#3fb950"),
        (m3, "Low",     f"{day_low:+.2f}",     "#f85149"),
        (m4, "Current", f"{day_current:+.2f}", "#58a6ff"),
        (m5, "High @",  high_time,             "#8b949e"),
        (m6, "Low @",   low_time,              "#8b949e"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;
                        padding:12px 16px;display:flex;flex-direction:column;gap:4px">
                <div style="font-size:0.7rem;color:#8b949e;text-transform:uppercase;
                            letter-spacing:1px;font-family:JetBrains Mono,monospace">{lbl}</div>
                <div style="font-size:1.4rem;font-weight:700;font-family:JetBrains Mono,monospace;
                            color:{clr}">{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart ─────────────────────────────────────────────────────────────────
    fig = go.Figure()

    # Spread line
    fig.add_trace(go.Scatter(
        x=combined["timestamp"], y=combined["spread"],
        mode="lines", name="Spread",
        line=dict(color="#58a6ff", width=1.8),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.06)",
        hovertemplate="<b>%{x|%H:%M}</b><br>Spread: <b>%{y:.2f}</b><extra></extra>",
    ))

    # High/Low bands
    fig.add_trace(go.Scatter(
        x=combined["timestamp"], y=combined["spread_high"],
        mode="lines", name="Candle High",
        line=dict(color="#3fb950", width=0.8, dash="dot"),
        hovertemplate="%{x|%H:%M} High: %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=combined["timestamp"], y=combined["spread_low"],
        mode="lines", name="Candle Low",
        line=dict(color="#f85149", width=0.8, dash="dot"),
        fill="tonexty", fillcolor="rgba(63,185,80,0.04)",
        hovertemplate="%{x|%H:%M} Low: %{y:.2f}<extra></extra>",
    ))

    # Day High/Low lines
    fig.add_hline(y=day_high, line_dash="dash", line_color="#3fb950", line_width=1,
                  annotation_text=f"H {day_high:.2f}", annotation_position="right",
                  annotation_font_color="#3fb950", annotation_font_size=10)
    fig.add_hline(y=day_low,  line_dash="dash", line_color="#f85149", line_width=1,
                  annotation_text=f"L {day_low:.2f}",  annotation_position="right",
                  annotation_font_color="#f85149", annotation_font_size=10)
    fig.add_hline(y=day_open, line_dash="longdash", line_color="#d29922", line_width=0.8,
                  annotation_text=f"O {day_open:.2f}", annotation_position="right",
                  annotation_font_color="#d29922", annotation_font_size=10)

    title = (f"{l1_und} {l1_stk}{l1_typ} − {l2_und} {l2_stk}{l2_typ} ×{ratio}  ·  "
             f"{trade_date.strftime('%d %b %Y')}")

    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#e6edf3"), x=0.01),
        plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=11),
        margin=dict(l=60, r=80, t=50, b=50),
        xaxis=dict(gridcolor="#30363d", rangeslider=dict(visible=False),
                   showspikes=True, spikecolor="#8b949e", spikemode="across"),
        yaxis=dict(gridcolor="#30363d", showspikes=True, spikecolor="#8b949e"),
        hovermode="x unified",
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
                    font=dict(color="#e6edf3", size=10)),
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    # ── Raw spread table ──────────────────────────────────────────────────────
    with st.expander("📋 Raw spread data"):
        st.dataframe(
            combined[["timestamp","leg1_close","leg2_close","spread","spread_high","spread_low"]],
            use_container_width=True
        )
