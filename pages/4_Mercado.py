"""Página Mercado: detalle de un ticker (hero + chart + stats + noticias + explícame + comparar + análisis + compra).

Feature 2: incluye watchlist/populares, tab Comparar (normalizado t0=100),
tab Análisis (resumen fundamental rápido vía agente), y botón rápido de
compra/venta inline sobre la cartera activa.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.services import portfolio as pf_service
from src.ui.charts import price_history_chart
from src.ui.news_view import render_news_panel
from src.ui.components import (
    fmt_money,
    fmt_pct,
    fmt_market_cap,
    color_for_delta,
)

st.set_page_config(page_title="Mercado · Bot de Inversiones", page_icon="📈")
st.title("📈 Detalle de ticker")

agent = get_agent()
session_id = ensure_session_id()

# Propaga la cartera activa al agente si hay session_state.
_active_pid = st.session_state.get("active_portfolio_id", 1)
set_active_portfolio(_active_pid)

# Watchlist / tickers populares.
POPULAR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK-B", "JPM", "V",
    "SAN.MC", "BBVA.MC", "TEF.MC", "IBE.MC",
    "ASML.AS", "SAP.DE", "MC.PA", "NESN.SW",
    "VWCE.DE", "IWDA.AS",
]

col_pop, col_in = st.columns([1, 2])
with col_pop:
    picked = st.selectbox(
        "Populares / watchlist",
        options=["(elige uno)"] + POPULAR_TICKERS,
        index=0,
        key="market_popular_pick",
    )
    if picked and picked != "(elige uno)":
        st.session_state["active_ticker"] = picked

default_ticker = st.session_state.get("active_ticker", "AAPL")
with col_in:
    ticker = st.text_input(
        "Ticker",
        value=default_ticker,
        help="Símbolo en mayúsculas, p. ej. AAPL, MSFT, TSLA, SAN.MC",
    ).strip().upper()
if ticker:
    st.session_state["active_ticker"] = ticker


@st.cache_data(ttl=300, show_spinner=False)
def _quote(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    info = t.info or {}
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
    if price is None or prev is None:
        hist = t.history(period="5d")
        if not hist.empty:
            price = price or float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev = prev or float(hist["Close"].iloc[-2])
    return {
        "name": info.get("longName") or info.get("shortName") or symbol,
        "currency": info.get("currency") or "USD",
        "price": price,
        "prev_close": prev,
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "beta": info.get("beta"),
        "fifty_two_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_low": info.get("fiftyTwoWeekLow"),
        "volume": info.get("volume"),
        "avg_volume": info.get("averageVolume"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


@st.cache_data(ttl=300, show_spinner=False)
def _history_close(symbol: str, period: str) -> pd.Series | None:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty:
            return None
        return hist["Close"]
    except Exception:
        return None


if not ticker:
    st.info("Introduce un ticker para ver su detalle.")
    st.stop()

with st.spinner(f"Cargando {ticker}..."):
    try:
        q = _quote(ticker)
    except Exception as e:
        st.error(f"No pude obtener datos de {ticker}: {e}")
        st.stop()

price = q["price"]
prev = q["prev_close"]
delta_abs = (price - prev) if (price is not None and prev is not None) else None
delta_pct = ((delta_abs / prev) * 100) if (delta_abs is not None and prev) else None

color = color_for_delta(delta_abs)
arrow = "▲" if (delta_abs or 0) > 0 else ("▼" if (delta_abs or 0) < 0 else "·")
st.markdown(
    f"""
    <div style="line-height:1.2;">
      <div style="font-size:1rem;color:#9AA0A6;">{q['name']} ({ticker})</div>
      <div style="font-size:2.5rem;font-weight:700;">{fmt_money(price, q['currency'])}</div>
      <div style="font-size:1.1rem;color:{color};">
        {arrow} {fmt_money(delta_abs, q['currency']) if delta_abs is not None else '—'}
        ({fmt_pct(delta_pct) if delta_pct is not None else '—'})
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

period = st.radio(
    "Periodo",
    options=["1mo", "3mo", "6mo", "1y", "5y"],
    index=2,
    horizontal=True,
    key="chart_period",
)

with st.spinner("Cargando gráfico..."):
    fig = price_history_chart(ticker, period)
if fig is None:
    st.warning(f"No se pudo cargar el histórico de {ticker} para {period}.")
else:
    st.plotly_chart(fig, use_container_width=True)

# Tabs ampliadas: Stats, News, Explícame, Comparar, Análisis, Comprar.
tab_stats, tab_news, tab_explain, tab_compare, tab_analyze, tab_trade = st.tabs(
    ["📊 Estadísticas", "📰 Noticias", "💡 Explícame", "📈 Comparar", "🧠 Análisis", "⭐ Añadir a cartera"]
)

with tab_stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Cap", fmt_market_cap(q["market_cap"]), help="Capitalización bursátil (precio × acciones en circulación).")
    c2.metric("P/E", f"{q['pe']:.2f}" if q["pe"] else "—", help="Price/Earnings.")
    c3.metric("EPS", f"{q['eps']:.2f}" if q["eps"] else "—", help="Earnings per share.")
    c4.metric("Beta", f"{q['beta']:.2f}" if q["beta"] else "—", help="Sensibilidad vs mercado.")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("52W máx.", fmt_money(q["fifty_two_high"], q["currency"]))
    c6.metric("52W mín.", fmt_money(q["fifty_two_low"], q["currency"]))
    c7.metric("Volumen", fmt_market_cap(q["volume"]) if q["volume"] else "—")
    c8.metric("Vol. medio", fmt_market_cap(q["avg_volume"]) if q["avg_volume"] else "—")

    if q["sector"] or q["industry"]:
        st.caption(f"Sector: {q['sector'] or '—'} · Industria: {q['industry'] or '—'}")

with tab_news:
    render_news_panel(ticker, limit=5)

with tab_explain:
    st.write(
        f"Pide al agente una explicación breve de qué hace **{ticker}** "
        "y por qué puede interesar."
    )
    explain_key = f"explain_answer_{ticker}"
    explain_prompt_key = f"explain_prompt_{ticker}"
    if st.button("💡 Explícame esta empresa", type="primary", key=f"explain_btn_{ticker}"):
        prompt = (
            f"Explícame brevemente qué hace {ticker} ({q['name']}), en qué sector opera "
            "y qué factores conviene vigilar. Máximo 150 palabras."
        )
        with st.spinner("El agente está pensando..."):
            try:
                result = agent.invoke(
                    {"input": prompt},
                    config={"configurable": {"session_id": session_id}},
                )
                answer = result.get("output") if isinstance(result, dict) else str(result)
            except Exception as e:
                answer = f"No pude obtener respuesta del agente ahora mismo. Detalle: {e}"
        st.session_state[explain_key] = answer or "Sin respuesta."
        st.session_state[explain_prompt_key] = prompt

    if explain_key in st.session_state:
        st.info(st.session_state[explain_key])
        if st.button("↪ Continuar en el chat", key=f"explain_goto_chat_{ticker}"):
            st.session_state["prefill_prompt"] = st.session_state[explain_prompt_key]
            st.switch_page("pages/1_Chat.py")

with tab_compare:
    st.write(f"Compara la evolución de **{ticker}** con otro ticker (normalizado a base 100).")
    other = st.text_input(
        "Otro ticker para comparar",
        value="",
        placeholder="Ej: MSFT, SPY, QQQ",
        key=f"compare_other_{ticker}",
    ).strip().upper()
    if other:
        s1 = _history_close(ticker, period)
        s2 = _history_close(other, period)
        if s1 is None or s1.empty:
            st.warning(f"No pude obtener datos de {ticker}.")
        elif s2 is None or s2.empty:
            st.warning(f"No pude obtener datos de {other}.")
        else:
            s1n = (s1 / float(s1.iloc[0])) * 100
            s2n = (s2 / float(s2.iloc[0])) * 100
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Scatter(x=s1n.index, y=s1n.values, name=ticker, mode="lines"))
            fig_cmp.add_trace(go.Scatter(x=s2n.index, y=s2n.values, name=other, mode="lines"))
            fig_cmp.update_layout(
                title=f"{ticker} vs {other} · base 100 ({period})",
                xaxis_title="Fecha",
                yaxis_title="Índice (base 100)",
                hovermode="x unified",
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

with tab_analyze:
    st.write("Resumen fundamental rápido interpretando precio, P/E, Beta y rango 52w.")
    analyze_key = f"analyze_answer_{ticker}"
    if st.button("🧠 Resumen fundamental rápido", type="primary", key=f"analyze_btn_{ticker}"):
        prompt = (
            f"Analiza brevemente {ticker} ({q['name']}) con los datos siguientes y "
            f"devuelve 3-4 bullets interpretando cada dato (sin inventar):\n"
            f"- Precio actual: {fmt_money(price, q['currency'])}\n"
            f"- P/E: {q['pe']}\n"
            f"- Beta: {q['beta']}\n"
            f"- 52W rango: {q['fifty_two_low']} - {q['fifty_two_high']}\n"
            f"- Sector: {q['sector']}\n"
            "Incluye un disclaimer de que no es asesoramiento financiero."
        )
        with st.spinner("El agente está analizando..."):
            try:
                result = agent.invoke(
                    {"input": prompt},
                    config={"configurable": {"session_id": session_id}},
                )
                ans = result.get("output") if isinstance(result, dict) else str(result)
            except Exception as e:
                ans = f"No pude obtener respuesta: {e}"
        st.session_state[analyze_key] = ans or "Sin respuesta."
    if analyze_key in st.session_state:
        st.info(st.session_state[analyze_key])

with tab_trade:
    st.write(f"Ejecuta una operación simulada de **{ticker}** sobre la cartera activa.")
    _active = pf_svc.get_portfolio(_active_pid)
    if _active:
        st.caption(f"Cartera activa: **{_active['name']}** · Cash disponible: "
                   f"{fmt_money(pf_svc.cash_available(_active['id']), _active['currency'])}")
    with st.form(f"trade_form_{ticker}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            side = st.radio("Tipo", options=["BUY", "SELL"], index=0, horizontal=True)
        with c2:
            qty = st.number_input("Cantidad", min_value=0.0001, step=1.0, value=1.0)
        submit_trade = st.form_submit_button("Ejecutar", type="primary")
        if submit_trade:
            try:
                if side == "BUY":
                    r = pf_service.buy(ticker, float(qty), portfolio_id=_active_pid)
                    st.success(
                        f"✅ Compra ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
                        f"Posición total: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
                    )
                else:
                    r = pf_service.sell(ticker, float(qty), portfolio_id=_active_pid)
                    if r["new_qty"] == 0:
                        st.success(
                            f"✅ Venta ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
                            "Posición cerrada."
                        )
                    else:
                        st.success(
                            f"✅ Venta ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
                            f"Restante: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
                        )
            except ValueError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")
