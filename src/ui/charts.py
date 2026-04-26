"""Helpers de Plotly. Layout dark coherente con la paleta de la app."""
import plotly.graph_objects as go
import yfinance as yf

from src.ui.components import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_DOWN,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_UP,
)


_LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor=COLOR_BG,
    plot_bgcolor=COLOR_BG,
    font=dict(family="Inter, system-ui, sans-serif", color=COLOR_TEXT, size=12),
    margin=dict(l=12, r=12, t=44, b=12),
    xaxis=dict(showgrid=False, linecolor=COLOR_BORDER, tickcolor=COLOR_BORDER, color=COLOR_MUTED),
    yaxis=dict(gridcolor=COLOR_BORDER, zerolinecolor=COLOR_BORDER, linecolor=COLOR_BORDER, color=COLOR_MUTED),
)


def price_history_chart(ticker: str, period: str = "6mo"):
    try:
        symbol = ticker.strip().upper()
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist["Close"],
            mode="lines",
            name=symbol,
            line=dict(color=COLOR_ACCENT, width=2),
            fill="tozeroy",
            fillcolor=f"{COLOR_ACCENT}1A",
        ))
        layout = dict(_LAYOUT_BASE)
        layout.update(
            title=dict(text=f"{symbol} · {period}", font=dict(size=15, color=COLOR_TEXT)),
            height=420,
        )
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def portfolio_allocation_pie(positions: list[dict]):
    try:
        rows = [p for p in positions if p.get("market_value")]
        if not rows:
            return None
        labels = [p["ticker"] for p in rows]
        values = [p["market_value"] for p in rows]
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            textfont=dict(family="Inter, system-ui, sans-serif", color=COLOR_TEXT),
            marker=dict(line=dict(color=COLOR_BG, width=2)),
        )])
        layout = dict(_LAYOUT_BASE)
        layout.update(
            title=dict(text="Asignación", font=dict(size=15, color=COLOR_TEXT)),
            height=380,
            showlegend=True,
            legend=dict(font=dict(color=COLOR_MUTED, size=11)),
        )
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def portfolio_pnl_bar(positions: list[dict]):
    try:
        rows = [p for p in positions if p.get("pnl") is not None]
        if not rows:
            return None
        tickers = [p["ticker"] for p in rows]
        pnls = [p["pnl"] for p in rows]
        colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in pnls]
        fig = go.Figure(data=[go.Bar(x=tickers, y=pnls, marker_color=colors)])
        layout = dict(_LAYOUT_BASE)
        layout.update(
            title=dict(text="P&L por posición", font=dict(size=15, color=COLOR_TEXT)),
            height=380,
            xaxis=dict(showgrid=False, linecolor=COLOR_BORDER, color=COLOR_MUTED, tickfont=dict(family="JetBrains Mono, monospace")),
        )
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None
