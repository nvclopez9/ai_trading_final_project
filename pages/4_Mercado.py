"""Página Mercado: detalle de un ticker.

Layout estilo Robinhood / pelositracker:
- Hero de página + selector ticker.
- Hero del ticker (nombre + precio + delta) en card grande.
- Strip de KPIs (volumen, market cap, P/E, apertura, anterior cierre).
- Chart de precio con selector de periodo en píldoras.
- Compra rápida inline.
- Tabs: Resumen, Comparar, Análisis, Noticias.

Toda la lógica de negocio (yfinance, agente, portfolio_buy/sell, switch_page,
session_state) se preserva del fichero original.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from src.agent.singleton import ensure_session_id, get_agent
from src.services import portfolio as pf_service
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.charts import price_history_chart
from src.ui.components import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_DIM,
    COLOR_DOWN,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_UP,
    color_for_delta,
    delta_badge,
    empty_state,
    fmt_market_cap,
    fmt_money,
    fmt_pct,
    hero,
    inject_app_styles,
    news_card,
    render_topbar,
    section_title,
    stat_strip,
    stat_tile,
)
from src.ui.news_view import render_news_panel


# ─── Setup ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Mercado · Bot de Inversiones", page_icon="M")
inject_app_styles()
render_topbar(active="Mercado")

hero(
    "Mercado",
    "Precio en vivo, fundamentales, noticias y compra rápida sobre cualquier ticker.",
)

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


# ─── Selector de ticker ─────────────────────────────────────────────────────
default_ticker = st.session_state.get("active_ticker", "AAPL")

col_in, col_pop, col_btn = st.columns([2, 2, 1])
with col_in:
    ticker_input = st.text_input(
        "Ticker",
        value=default_ticker,
        help="Símbolo en mayúsculas, p. ej. AAPL, MSFT, TSLA, SAN.MC",
    )
with col_pop:
    picked = st.selectbox(
        "Populares / watchlist",
        options=["(elige uno)"] + POPULAR_TICKERS,
        index=0,
        key="market_popular_pick",
    )
with col_btn:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    load_clicked = st.button("Cargar", type="primary", use_container_width=True)

# Resolución del ticker activo.
if picked and picked != "(elige uno)":
    st.session_state["active_ticker"] = picked
    ticker = picked
else:
    ticker = (ticker_input or "").strip().upper()
    if ticker:
        st.session_state["active_ticker"] = ticker

if not ticker:
    empty_state(
        "Sin ticker",
        "Introduce un símbolo arriba para ver su detalle (precio, fundamentales y noticias).",
        icon="?",
    )
    st.stop()


# ─── Helpers de datos (cache) ───────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _quote(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    info = t.info or {}
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
    open_ = info.get("regularMarketOpen") or info.get("open")
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
        "open": open_,
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
currency = q["currency"]


# ─── Hero del ticker ────────────────────────────────────────────────────────
_MONO = "'JetBrains Mono','SF Mono','Menlo','Roboto Mono','Consolas',monospace"
delta_color = color_for_delta(delta_abs)
delta_abs_str = fmt_money(delta_abs, currency) if delta_abs is not None else "—"
big_delta_badge = delta_badge(delta_pct, big=True) if delta_pct is not None else ""

st.markdown(
    f"""
    <div class="pill-card" style="padding:24px;margin-bottom:18px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
        <div>
          <div style="font-family:{_MONO};font-size:2rem;font-weight:700;
                      letter-spacing:0.6px;color:{COLOR_TEXT};line-height:1.05;">
            {ticker}
          </div>
          <div style="color:{COLOR_MUTED};font-size:14px;margin-top:6px;max-width:520px;">
            {q['name']}
          </div>
          <div style="color:{COLOR_DIM};font-size:12px;margin-top:8px;">
            {q['sector'] or '—'} · {q['industry'] or '—'}
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-family:{_MONO};font-size:2.5rem;font-weight:700;
                      color:{COLOR_TEXT};letter-spacing:-0.01em;line-height:1.05;">
            {fmt_money(price, currency)}
          </div>
          <div style="margin-top:10px;display:flex;gap:10px;justify-content:flex-end;align-items:center;">
            <span style="color:{delta_color};font-family:{_MONO};font-size:14px;font-weight:600;">
              {delta_abs_str}
            </span>
            {big_delta_badge}
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Strip de KPIs.
stat_strip([
    stat_tile("Volumen", fmt_market_cap(q["volume"]) if q["volume"] else "—"),
    stat_tile("Market Cap", fmt_market_cap(q["market_cap"])),
    stat_tile("P/E", f"{q['pe']:.2f}" if q["pe"] else "—"),
    stat_tile("Apertura", fmt_money(q["open"], currency) if q["open"] else "—"),
    stat_tile("Anterior cierre", fmt_money(prev, currency) if prev else "—"),
])


# ─── Chart de precio + selector de periodo en píldoras ──────────────────────
section_title("Histórico", f"Evolución del precio de {ticker}.")

PERIODS = ["1mo", "3mo", "6mo", "1y", "5y"]
if "chart_period" not in st.session_state:
    st.session_state["chart_period"] = "6mo"

period_cols = st.columns(len(PERIODS))
for i, p in enumerate(PERIODS):
    is_active = st.session_state["chart_period"] == p
    with period_cols[i]:
        if st.button(
            p,
            key=f"period_btn_{p}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state["chart_period"] = p
            st.rerun()

period = st.session_state["chart_period"]

with st.spinner("Cargando gráfico..."):
    fig = price_history_chart(ticker, period)
if fig is None:
    st.warning(f"No se pudo cargar el histórico de {ticker} para {period}.")
else:
    st.plotly_chart(fig, use_container_width=True)


# ─── Compra rápida inline ───────────────────────────────────────────────────
section_title("Compra rápida", "Operación simulada sobre la cartera activa.")

_active = pf_svc.get_portfolio(_active_pid)
if _active:
    cash_avail = pf_svc.cash_available(_active["id"])
    st.markdown(
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-bottom:10px;'>"
        f"Cartera activa: <b style='color:{COLOR_TEXT};'>{_active['name']}</b> · "
        f"Cash disponible: <b style='color:{COLOR_TEXT};'>"
        f"{fmt_money(cash_avail, _active['currency'])}</b>"
        "</div>",
        unsafe_allow_html=True,
    )

with st.container():
    st.markdown('<div class="pill-card" style="padding:20px;">', unsafe_allow_html=True)
    qty_col, buy_col, sell_col = st.columns([2, 1, 1])
    with qty_col:
        trade_qty = st.number_input(
            "Cantidad",
            min_value=0.0001,
            step=1.0,
            value=1.0,
            key=f"trade_qty_{ticker}",
        )
    with buy_col:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        buy_clicked = st.button(
            "Comprar", type="primary", use_container_width=True, key=f"buy_{ticker}"
        )
    with sell_col:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        sell_clicked = st.button(
            "Vender", use_container_width=True, key=f"sell_{ticker}"
        )
    st.markdown("</div>", unsafe_allow_html=True)

if buy_clicked:
    try:
        r = pf_service.buy(ticker, float(trade_qty), portfolio_id=_active_pid)
        st.success(
            f"Compra ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
            f"Posición total: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Error inesperado: {e}")

if sell_clicked:
    try:
        r = pf_service.sell(ticker, float(trade_qty), portfolio_id=_active_pid)
        if r["new_qty"] == 0:
            st.success(
                f"Venta ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
                "Posición cerrada."
            )
        else:
            st.success(
                f"Venta ejecutada: {r['qty']:g} {r['ticker']} a ${r['price']:.2f}. "
                f"Restante: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
            )
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Error inesperado: {e}")


# ─── Tabs ───────────────────────────────────────────────────────────────────
tab_summary, tab_compare, tab_analyze, tab_news = st.tabs([
    "Resumen", "Comparar", "Análisis", "Noticias",
])

# ── Tab Resumen ─────────────────────────────────────────────────────────────
with tab_summary:
    stat_strip([
        stat_tile("EPS", f"{q['eps']:.2f}" if q["eps"] else "—"),
        stat_tile("Beta", f"{q['beta']:.2f}" if q["beta"] else "—"),
        stat_tile("52W máx.", fmt_money(q["fifty_two_high"], currency) if q["fifty_two_high"] else "—"),
        stat_tile("52W mín.", fmt_money(q["fifty_two_low"], currency) if q["fifty_two_low"] else "—"),
    ])

    stat_strip([
        stat_tile("Vol. medio", fmt_market_cap(q["avg_volume"]) if q["avg_volume"] else "—"),
        stat_tile("Sector", q["sector"] or "—"),
        stat_tile("Industria", q["industry"] or "—"),
        stat_tile("Divisa", currency),
    ])

    # Bloque "Explícame".
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    section_title(
        "Explícame esta empresa",
        "Resumen breve generado por el agente con los datos del ticker.",
    )

    explain_key = f"explain_answer_{ticker}"
    explain_prompt_key = f"explain_prompt_{ticker}"

    if st.button(
        "Generar resumen",
        type="primary",
        key=f"explain_btn_{ticker}",
    ):
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
        st.markdown(
            f"""
            <div class="pill-card" style="padding:18px;margin-top:8px;">
              <div style="color:{COLOR_TEXT};font-size:14px;line-height:1.6;
                          white-space:pre-wrap;">{st.session_state[explain_key]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Continuar en el chat",
            key=f"explain_goto_chat_{ticker}",
        ):
            st.session_state["prefill_prompt"] = st.session_state[explain_prompt_key]
            st.switch_page("pages/1_Chat.py")


# ── Tab Comparar ────────────────────────────────────────────────────────────
with tab_compare:
    st.markdown(
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-bottom:12px;'>"
        f"Compara la evolución de <b style='color:{COLOR_TEXT};'>{ticker}</b> con otro "
        f"ticker (normalizado a base 100, periodo {period})."
        "</div>",
        unsafe_allow_html=True,
    )
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
            fig_cmp.add_trace(go.Scatter(
                x=s1n.index, y=s1n.values, name=ticker, mode="lines",
                line=dict(color=COLOR_ACCENT, width=2),
            ))
            fig_cmp.add_trace(go.Scatter(
                x=s2n.index, y=s2n.values, name=other, mode="lines",
                line=dict(color=COLOR_UP, width=2),
            ))
            fig_cmp.update_layout(
                template="plotly_dark",
                title=f"{ticker} vs {other} · base 100 ({period})",
                xaxis_title="Fecha",
                yaxis_title="Índice (base 100)",
                hovermode="x unified",
                margin=dict(l=10, r=10, t=50, b=10),
                paper_bgcolor=COLOR_SURFACE,
                plot_bgcolor=COLOR_SURFACE,
            )
            st.plotly_chart(fig_cmp, use_container_width=True)


# ── Tab Análisis ────────────────────────────────────────────────────────────
with tab_analyze:
    st.markdown(
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-bottom:12px;'>"
        "Resumen fundamental rápido interpretando precio, P/E, Beta y rango 52w."
        "</div>",
        unsafe_allow_html=True,
    )
    analyze_key = f"analyze_answer_{ticker}"
    if st.button(
        "Generar análisis fundamental",
        type="primary",
        key=f"analyze_btn_{ticker}",
    ):
        prompt = (
            f"Analiza brevemente {ticker} ({q['name']}) con los datos siguientes y "
            f"devuelve 3-4 bullets interpretando cada dato (sin inventar):\n"
            f"- Precio actual: {fmt_money(price, currency)}\n"
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
        st.markdown(
            f"""
            <div class="pill-card" style="padding:18px;margin-top:8px;">
              <div style="color:{COLOR_TEXT};font-size:14px;line-height:1.6;
                          white-space:pre-wrap;">{st.session_state[analyze_key]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Tab Noticias ────────────────────────────────────────────────────────────
with tab_news:
    st.markdown(
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-bottom:12px;'>"
        f"Últimos titulares relacionados con <b style='color:{COLOR_TEXT};'>{ticker}</b>."
        "</div>",
        unsafe_allow_html=True,
    )
    render_news_panel(ticker, limit=6)
