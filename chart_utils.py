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
    Build an interactive Plotly line/candlestick chart for spread data.
    - Smart Y-axis: fits to actual data range with 7% padding
    - X-axis: locked to market hours (9:10–15:35)
    """
    fig = go.Figure()

    if df.empty:
        fig.update_layout(
            height=420, plot_bgcolor=_SURFACE, paper_bgcolor=_BG,
            annotations=[dict(text="No data available", showarrow=False,
                x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(color=_MUTED, size=14))]
        )
        return fig

    if resolution == "Tick" or "spread" in df.columns:
        y = df["spread"]
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=y,
            mode="lines",
            name="Spread",
            line=dict(color=_ACCENT, width=1.8),
            hovertemplate="<b>%{x|%H:%M}</b><br>Spread: <b>%{y:.2f}</b><extra></extra>",
        ))
        y_min = float(y.min())
        y_max = float(y.max())

        # Stats overlays
        if stats:
            for val, color, label, dash in [
                (stats.get("high"), _GREEN, f"H {stats.get('high',0):.2f}", "dash"),
                (stats.get("low"),  _RED,   f"L {stats.get('low',0):.2f}",  "dash"),
                (stats.get("open"), _AMBER, f"O {stats.get('open',0):.2f}", "longdash"),
            ]:
                if val is not None:
                    fig.add_hline(
                        y=val, line_dash=dash, line_color=color,
                        line_width=1, opacity=0.8,
                        annotation_text=label, annotation_position="right",
                        annotation_font_color=color, annotation_font_size=10,
                    )

    else:
        # Candlestick mode
        fig.add_trace(go.Candlestick(
            x=df["timestamp"],
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="Spread",
            increasing_line_color=_GREEN,
            decreasing_line_color=_RED,
        ))
        y_min = float(df["low"].min())
        y_max = float(df["high"].max())

        if stats:
            for val, color, label, dash in [
                (stats.get("high"), _GREEN, f"H {stats.get('high',0):.2f}", "dash"),
                (stats.get("low"),  _RED,   f"L {stats.get('low',0):.2f}",  "dash"),
                (stats.get("open"), _AMBER, f"O {stats.get('open',0):.2f}", "longdash"),
            ]:
                if val is not None:
                    fig.add_hline(
                        y=val, line_dash=dash, line_color=color, line_width=1,
                        annotation_text=label, annotation_position="right",
                        annotation_font_color=color, annotation_font_size=10,
                    )

    # ── Smart Y-axis: 7% padding above and below data range ──────────────────
    y_range  = max(y_max - y_min, 1.0)
    padding  = y_range * 0.07
    y_lo     = y_min - padding
    y_hi     = y_max + padding

    # ── X-axis: market hours only ─────────────────────────────────────────────
    x_min = x_max = None
    if not df.empty and "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"].iloc[0])
        d  = ts.date()
        x_min = pd.Timestamp(f"{d} 09:10:00")
        x_max = pd.Timestamp(f"{d} 15:35:00")

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
        margin=dict(l=60, r=90, t=50, b=50),
        xaxis=dict(
            gridcolor=_BORDER,
            tickfont=dict(size=10, color=_MUTED),
            rangeslider=dict(visible=False),
            showspikes=True,
            spikecolor=_MUTED,
            spikemode="across",
            spikethickness=1,
            tickformat="%H:%M",
            range=[x_min, x_max] if x_min else None,
        ),
        yaxis=dict(
            gridcolor=_BORDER,
            tickfont=dict(size=10, color=_MUTED),
            showspikes=True,
            spikecolor=_MUTED,
            range=[y_lo, y_hi],
            autorange=False,
        ),
        hovermode="x unified",
        legend=dict(
            bgcolor=_SURFACE,
            bordercolor=_BORDER,
            borderwidth=1,
            font=dict(color=_TEXT, size=10),
        ),
        dragmode="zoom",
        modebar=dict(bgcolor=_SURFACE, color=_MUTED, activecolor=_ACCENT),
    )

    return fig
