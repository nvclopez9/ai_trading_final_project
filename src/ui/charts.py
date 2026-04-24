"""Helpers de Plotly para los gráficos de la UI de Streamlit.

Tres gráficos independientes, cada uno en su función, devolviendo un
``plotly.graph_objects.Figure`` (o ``None`` si no hay datos suficientes).
Hacemos que la UI pueda tratar el None como "no renderizar gráfico" sin
tener que capturar excepciones — todas las funciones envuelven su cuerpo
en try/except para no romper el render de la página si un ticker falla.

Lo usan:
  - ``app.py`` -> ``price_history_chart`` (pestaña de Gráficos).
  - ``src/ui/portfolio_view.py`` -> pie de asignación y bar de P&L.
"""
# Plotly: figuras interactivas. yfinance: datos históricos para price_history_chart.
import plotly.graph_objects as go
import yfinance as yf


def price_history_chart(ticker: str, period: str = "6mo"):
    """Gráfico de línea con el precio de cierre de un ticker en el periodo dado.

    Devuelve None si el ticker es inválido o no hay histórico; la UI
    mostrará un mensaje de error en ese caso.
    """
    try:
        # Normalizamos ticker igual que en las tools de mercado (coherencia).
        symbol = ticker.strip().upper()
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return None
        # Figura + traza scatter en modo "lines": curva simple del Close.
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist["Close"],
            mode="lines",
            name=symbol,
            line=dict(color="#1f77b4", width=2),
        ))
        # Layout: tema claro, altura fija para que cuadre con los contenedores
        # de Streamlit, títulos en español.
        fig.update_layout(
            title=f"Precio histórico de {symbol} ({period})",
            xaxis_title="Fecha",
            yaxis_title="Precio",
            template="plotly_dark",
            height=450,
        )
        return fig
    except Exception:
        # Cualquier fallo (red, ticker raro, etc.) se traduce a None.
        return None


def portfolio_allocation_pie(positions: list[dict]):
    """Gráfico de donut con la distribución del valor de mercado de la cartera.

    Excluye posiciones sin ``market_value`` (ticker "stale" en yfinance),
    para no distorsionar las proporciones con filas incompletas.
    """
    try:
        # Filtro defensivo: si market_value es None o 0, lo ignoramos.
        rows = [p for p in positions if p.get("market_value")]
        if not rows:
            return None
        labels = [p["ticker"] for p in rows]
        values = [p["market_value"] for p in rows]
        # hole=0.35 -> donut (más moderno y legible que un pie clásico).
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.35)])
        fig.update_layout(
            title="Asignación de la cartera (valor de mercado)",
            template="plotly_dark",
            height=400,
        )
        return fig
    except Exception:
        return None


def portfolio_pnl_bar(positions: list[dict]):
    """Gráfico de barras con el P&L por posición, coloreado por signo.

    Verde si el P&L es positivo (o cero), rojo si es negativo. Permite ver
    de un vistazo qué posiciones están ganando o perdiendo.
    """
    try:
        # Incluimos solo las posiciones con pnl calculado (descarta stale).
        rows = [p for p in positions if p.get("pnl") is not None]
        if not rows:
            return None
        tickers = [p["ticker"] for p in rows]
        pnls = [p["pnl"] for p in rows]
        # Colores corporativos típicos de dashboards financieros.
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in pnls]
        fig = go.Figure(data=[go.Bar(x=tickers, y=pnls, marker_color=colors)])
        fig.update_layout(
            title="P&L por posición",
            xaxis_title="Ticker",
            yaxis_title="P&L",
            template="plotly_dark",
            height=400,
        )
        return fig
    except Exception:
        return None
