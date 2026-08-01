"""
chart_utils.py
==============
Reusable Plotly chart builders for spread visualization.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Color palette (matches the dark CSS theme) ───────────────────────────────
_BG       = "#0d1117"
_SURFACE  = "#161b22"
_BORDER   = "#30363d"
_ACCENT   = "#58a6ff"
_GREEN    = "#3fb950"
_RED      = "#f85149"
_MUTED    = "#8b949e"
_TEXT     = "#e6edf3"
_AMBER    = "#d29922"


def build_spread_line_chart(
    df: pd.DataFrame,
    title: str = "Spread",
    stats: dict | None = None,
    resolution: str = "Tick",
) -> go.Figure:
    """
    Build an interactive Plotly line chart for spread data.

    If resolution == 'Tick', df must have columns: timestamp, spread
    Otherwise df must have columns: timestamp, open, high, low, close
    """
    fig = go.Figure()

    if resolution == "Tick" or "spread" in df.columns:
        y_col = "spread"
        y = df[y_col]
        color_array = [_GREEN if v >= 0 else _RED for v in y]

        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=y,
            mode="lines",
            name="Spread",
            line=dict(color=_ACCENT, width=1.8),
            fill="tozeroy",
            fillcolor="rgba(88,166,255,0.08)",
            hovertemplate="<b>%{x|%H:%M:%S}</b><br>Spread: <b>%{y:.2f}</b><extra></extra>",
        ))

        # Zero line
        fig.add_hline(y=0, line_dash="dot", line_color=_MUTED, line_width=1, opacity=0.5)

        # Stats overlays
        if stats:
            if stats.get("high") is not None:
                fig.add_hline(
                    y=stats["high"], line_dash="dash",
                    line_color=_GREEN, line_width=0.8, opacity=0.6,
                    annotation_text=f"H {stats['high']:.2f}",
                    annotation_position="right",
                    annotation_font_color=_GREEN,
                    annotation_font_size=10,
                )
            if stats.get("low") is not None:
                fig.add_hline(
                    y=stats["low"], line_dash="dash",
                    line_color=_RED, line_width=0.8, opacity=0.6,
                    annotation_text=f"L {stats['low']:.2f}",
                    annotation_position="right",
                    annotation_font_color=_RED,
                    annotation_font_size=10,
                )
            if stats.get("open") is not None:
                fig.add_hline(
                    y=stats["open"], line_dash="longdash",
                    line_color=_AMBER, line_width=0.8, opacity=0.5,
                    annotation_text=f"O {stats['open']:.2f}",
                    annotation_position="right",
                    annotation_font_color=_AMBER,
                    annotation_font_size=10,
                )

    else:
        # OHLC candlestick mode
        fig.add_trace(go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Spread",
            increasing_line_color=_GREEN,
            decreasing_line_color=_RED,
        ))

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="JetBrains Mono, monospace", size=14, color=_TEXT),
            x=0.02,
        ),
        plot_bgcolor=_SURFACE,
        paper_bgcolor=_BG,
        font=dict(family="Inter, sans-serif", color=_MUTED, size=11),
        margin=dict(l=60, r=80, t=50, b=50),
        xaxis=dict(
            gridcolor=_BORDER,
            tickfont=dict(size=10, color=_MUTED),
            rangeslider=dict(visible=False),
            showspikes=True,
            spikecolor=_MUTED,
            spikemode="across",
            spikethickness=1,
        ),
        yaxis=dict(
            gridcolor=_BORDER,
            tickfont=dict(size=10, color=_MUTED),
            showspikes=True,
            spikecolor=_MUTED,
        ),
        hovermode="x unified",
        legend=dict(
            bgcolor=_SURFACE,
            bordercolor=_BORDER,
            borderwidth=1,
            font=dict(color=_TEXT, size=10),
        ),
        dragmode="zoom",
    )

    # Modebar buttons
    fig.update_layout(
        modebar=dict(
            bgcolor=_SURFACE,
            color=_MUTED,
            activecolor=_ACCENT,
        )
    )

    return fig
