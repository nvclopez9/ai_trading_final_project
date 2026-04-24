"""Panel de noticias para la pestaña Gráficos.

Renderiza las últimas noticias de un ticker (titular + fecha + fuente + link).
Es una lectura directa de ``yfinance`` a través de ``fetch_ticker_news`` —
NO pasa por el agente, para que el panel cargue rápido y no gaste tokens.
"""
import streamlit as st

from src.tools.market_tools import fetch_ticker_news


def render_news_panel(ticker: str, limit: int = 5) -> None:
    """Dibuja un listado de noticias para ``ticker`` con ``limit`` ítems máx.

    Si no hay noticias o falla la petición mostramos un ``st.info`` suave en
    lugar de un error: la ausencia de noticias no es un bug, sólo un dato.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return
    with st.spinner("Cargando noticias..."):
        items = fetch_ticker_news(ticker, limit=limit)
    if not items:
        st.info(f"No hay noticias disponibles para {ticker} ahora mismo.")
        return
    for n in items:
        # Título como link si tenemos URL, si no como texto plano.
        title = n["title"]
        if n["link"]:
            st.markdown(f"**[{title}]({n['link']})**")
        else:
            st.markdown(f"**{title}**")
        st.caption(f"{n['date']} · {n['source']}")
        st.divider()
