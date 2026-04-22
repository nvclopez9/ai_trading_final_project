import plotly.graph_objects as go
import yfinance as yf


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
            line=dict(color="#1f77b4", width=2),
        ))
        fig.update_layout(
            title=f"Precio histórico de {symbol} ({period})",
            xaxis_title="Fecha",
            yaxis_title="Precio",
            template="plotly_white",
            height=450,
        )
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
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.35)])
        fig.update_layout(
            title="Asignación de la cartera (valor de mercado)",
            template="plotly_white",
            height=400,
        )
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
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in pnls]
        fig = go.Figure(data=[go.Bar(x=tickers, y=pnls, marker_color=colors)])
        fig.update_layout(
            title="P&L por posición",
            xaxis_title="Ticker",
            yaxis_title="P&L",
            template="plotly_white",
            height=400,
        )
        return fig
    except Exception:
        return None
