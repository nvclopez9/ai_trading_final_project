"""Página de Noticias.

Estructura:
- Tab "Portal" — agregador de titulares de varios tickers populares
  (mega-caps + ETFs de índices) ordenados por fecha.
- Tab "Por ticker" — buscador (input + dropdown de tickers interesantes)
  con análisis rápido por noticia y resumen global.

En cualquier noticia el usuario puede pulsar **"Analizar con IA"**: eso
prepara un prompt rico en ``session_state`` y salta al chat con ``st.switch_page``.
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.tools.market_tools import fetch_ticker_news
from src.ui.components import (
    COLOR_MUTED,
    COLOR_TEXT,
    footer_disclaimer,
    hero,
    inject_app_styles,
    news_card,
    section_title,
    sidebar_kpi,
)

st.set_page_config(page_title="Noticias · Bot de Inversiones", page_icon="📰", layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

hero(
    "Noticias",
    "Portal de titulares del mercado y buscador por ticker. Pulsa Analizar con IA en "
    "cualquier noticia para que el agente examine sentimiento, impacto y acciones.",
)

agent = get_agent()
session_id = ensure_session_id()


# ─── Sidebar contextual: filtros + tickers de la cartera ──────────────────
with st.sidebar:
    st.markdown("<div class='section-eyebrow'>Mis tickers</div>", unsafe_allow_html=True)
    try:
        from src.services import portfolio as _pfs
        _active_pid_n = st.session_state.get("active_portfolio_id", 1)
        _holdings = _pfs.get_positions(portfolio_id=_active_pid_n)
        _my_tickers = [h["ticker"] for h in _holdings]
    except Exception:
        _my_tickers = []
    if _my_tickers:
        for t in _my_tickers[:8]:
            if st.button(f"📰 {t}", key=f"news_sb_t_{t}", use_container_width=True):
                st.session_state["news_search_ticker"] = t
                st.rerun()
    else:
        st.caption("Sin posiciones — mostramos los populares.")

    st.markdown("<div class='section-eyebrow' style='margin-top:14px;'>Resumen</div>",
                unsafe_allow_html=True)
    st.markdown(sidebar_kpi("Universo portal", "8", hint="mega-caps + ETFs"),
                unsafe_allow_html=True)
    if st.button("Refrescar feeds", key="news_sb_refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# Universos curados.
PORTAL_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL"]
INTERESTING_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
    "AVGO", "AMD", "NFLX", "JPM", "V", "MA", "UNH", "JNJ",
    "WMT", "XOM", "CVX", "BA", "DIS", "KO", "PEP", "INTC",
    "QCOM", "ORCL", "CRM", "ADBE", "PYPL", "SHOP",
    "SPY", "QQQ", "DIA", "IWM", "VOO", "VTI",
]


def _escape_dollars(text: str) -> str:
    # Streamlit interpreta `$...$` como LaTeX y rompe cifras como "$10 000".
    return text.replace("$", "\\$") if isinstance(text, str) else text


def _news_hash(n: dict) -> str:
    """Hash estable por noticia para keys de widgets y session_state."""
    raw = (n.get("link") or n.get("title", "")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:10]


def _build_analysis_prompt(news: dict, ticker: str) -> str:
    """Compone el prompt que se inyecta al chat al pulsar 'Analizar con IA'."""
    return (
        f"Analiza esta noticia sobre {ticker} en profundidad y dame conclusiones útiles.\n\n"
        f"Noticia:\n"
        f"- Titular: {news.get('title','(sin título)')}\n"
        f"- Fuente: {news.get('source','n/d')}\n"
        f"- Fecha: {news.get('date','n/d')}\n"
        f"- URL: {news.get('link','')}\n\n"
        f"Pasos que quiero que des (usa tus tools, no inventes datos):\n"
        f"1) Resumen de la noticia en 2-3 frases.\n"
        f"2) Sentimiento detectado: positivo / negativo / neutral, con justificación.\n"
        f"3) Llama a get_ticker_status('{ticker}') para conocer precio, cambio diario, P/E y "
        f"capitalización. Llama también a get_ticker_history('{ticker}', '3mo') para situar "
        f"el contexto reciente.\n"
        f"4) Impacto previsible en el precio del valor: corto plazo (días) y medio plazo "
        f"(semanas). Razona por qué.\n"
        f"5) Riesgos y posibles catalizadores adicionales que el lector debería vigilar.\n"
        f"6) Acciones recomendadas como ejercicio educativo: comprar / vender / mantener / esperar, "
        f"y por qué. Si tiene sentido, ofrece llamar a analyze_buy_opportunities o "
        f"analyze_sell_candidates con parámetros razonables, pero NO ejecutes órdenes "
        f"todavía: solo propón.\n"
        f"7) Cierra con un disclaimer explícito de que NO es asesoramiento financiero."
    )


def _send_to_chat(prompt: str) -> None:
    """Inyecta el prompt en session_state y salta al chat."""
    st.session_state["prefill_prompt"] = prompt
    st.switch_page("pages/1_Chat.py")


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_portal_news(tickers: tuple[str, ...], per_ticker: int = 4) -> list[dict]:
    """Pide noticias para varios tickers en paralelo, las funde y ordena por fecha."""
    def _grab(t: str) -> list[dict]:
        try:
            items = fetch_ticker_news(t, limit=per_ticker) or []
            for it in items:
                it["_origin"] = t
            return items
        except Exception:
            return []

    aggregated: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as ex:
        for batch in ex.map(_grab, tickers):
            aggregated.extend(batch)

    seen = set()
    unique = []
    for it in aggregated:
        key = (it.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)

    unique.sort(key=lambda x: x.get("date") or "", reverse=True)
    return unique


def _ask_agent_inline(prompt: str) -> str:
    """Conversación directa con el agente sin saltar de página (botón rápido)."""
    try:
        result = agent.invoke(
            {"input": prompt},
            config={"configurable": {"session_id": session_id}},
        )
        return result.get("output") if isinstance(result, dict) else str(result)
    except Exception as e:
        return f"No pude obtener respuesta del agente: {e}"


def _render_news_item(n: dict, ticker: str, ctx: str) -> None:
    """Renderiza una noticia con news_card + botones de acción debajo.

    ctx: 'portal' o 'search', sirve para distinguir keys de widgets.
    """
    h = _news_hash(n)
    title = n.get("title") or "(sin título)"
    source = n.get("source") or "n/d"
    ts = n.get("date")
    show_ticker = (n.get("_origin") if ctx == "portal" else ticker) or ticker

    st.markdown(
        news_card(title=title, source=source, ts=ts, ticker=show_ticker, url=n.get("link")),
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])
    quick_btn = col_a.button("Opinión rápida", key=f"news_quick_{ctx}_{h}")
    deep_btn = col_b.button("Analizar con IA", key=f"news_deep_{ctx}_{h}", type="primary")

    quick_state = f"news_quick_state_{ctx}_{h}"
    if quick_btn:
        with st.spinner("El agente está leyendo..."):
            st.session_state[quick_state] = _ask_agent_inline(
                f"Comenta brevemente (3 frases) esta noticia sobre {show_ticker}: "
                f"{n.get('title','')} (fuente: {n.get('source','')}, fecha: {n.get('date','')})."
                " Añade disclaimer."
            )
    if quick_state in st.session_state:
        st.info(_escape_dollars(st.session_state[quick_state]))

    if deep_btn:
        _send_to_chat(_build_analysis_prompt(n, show_ticker))


# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tab_portal, tab_search = st.tabs(["Portal", "Por ticker"])


# --- Portal -----------------------------------------------------------------
with tab_portal:
    section_title(
        "Titulares destacados",
        subtitle=(
            f"Agregado de noticias de mega-caps y ETFs índice "
            f"({', '.join(PORTAL_TICKERS)}). Refresco automático cada 5 min."
        ),
    )
    refresh = st.button("Refrescar portal", key="portal_refresh")
    if refresh:
        _fetch_portal_news.clear()
    with st.spinner("Cargando portal..."):
        portal_items = _fetch_portal_news(tuple(PORTAL_TICKERS), per_ticker=4)

    if not portal_items:
        st.warning("No se pudieron cargar noticias en este momento.")
    else:
        # Grid de 2 columnas. Usamos el mismo idx para no chocar entre filas.
        items_to_show = portal_items[:20]
        for i in range(0, len(items_to_show), 2):
            cols = st.columns(2)
            for col, n in zip(cols, items_to_show[i:i + 2]):
                with col:
                    _render_news_item(n, ticker=n.get("_origin", ""), ctx="portal")
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)


# --- Por ticker -------------------------------------------------------------
with tab_search:
    section_title("Buscar noticias por ticker", subtitle="Selecciona un ticker popular o introdúcelo manualmente.")
    default_ticker = st.session_state.get("active_ticker", "AAPL")
    if default_ticker not in INTERESTING_TICKERS:
        select_options = [default_ticker] + INTERESTING_TICKERS
    else:
        select_options = INTERESTING_TICKERS

    col_sel, col_inp = st.columns([2, 2])
    chosen_from_dropdown = col_sel.selectbox(
        "Tickers interesantes",
        options=select_options,
        index=select_options.index(default_ticker) if default_ticker in select_options else 0,
        help="Selección rápida de mega-caps y ETFs populares.",
        key="news_dropdown",
    )
    manual = col_inp.text_input(
        "...o introduce un ticker manualmente",
        value="",
        placeholder="p.ej. PLTR, ASML, SAN.MC",
        key="news_manual",
    ).strip().upper()

    ticker = manual or chosen_from_dropdown

    col_load, col_jump = st.columns([1, 1])
    load_btn = col_load.button("Cargar noticias", type="primary", key="news_load_btn")
    jump_btn = col_jump.button("Llevar este ticker al chat", key="news_jump_chat_btn")

    if jump_btn and ticker:
        st.session_state["active_ticker"] = ticker
        _send_to_chat(
            f"Analiza el estado actual de {ticker}: usa get_ticker_status y "
            f"get_ticker_news para darme un resumen, sentimiento general de las "
            f"últimas noticias, y posibles acciones a considerar (educativo, no "
            f"asesoramiento)."
        )

    news_key = f"news_items_{ticker}"
    if load_btn and ticker:
        with st.spinner("Cargando noticias..."):
            st.session_state[news_key] = fetch_ticker_news(ticker, limit=10)

    items = st.session_state.get(news_key, [])
    if not items:
        st.info("Selecciona o escribe un ticker y pulsa **Cargar noticias**.")
    else:
        st.markdown(
            f"<div style='color:{COLOR_TEXT};font-weight:600;font-size:15px;margin:18px 0 8px 0;'>"
            f"Últimas noticias de {ticker}</div>",
            unsafe_allow_html=True,
        )
        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for col, n in zip(cols, items[i:i + 2]):
                with col:
                    _render_news_item(n, ticker=ticker, ctx="search")
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        # Resumen global del ticker.
        with st.expander("Pedir un resumen del agente sobre todas las noticias"):
            summary_key = f"news_summary_{ticker}"
            if st.button("Generar resumen", key=f"news_summary_btn_{ticker}"):
                bullet_list = "\n".join(
                    f"- [{n.get('date','n/d')}] {n.get('title','')} ({n.get('source','n/d')})"
                    for n in items
                )
                prompt = (
                    f"A continuación tienes los titulares más recientes sobre {ticker}. "
                    "Haz un resumen ejecutivo en 5-6 bullets destacando temas recurrentes, "
                    "posibles catalizadores y riesgos. No inventes cifras. Añade disclaimer.\n\n"
                    f"{bullet_list}"
                )
                with st.spinner("Resumiendo..."):
                    st.session_state[summary_key] = _ask_agent_inline(prompt)
            if summary_key in st.session_state:
                st.markdown(_escape_dollars(st.session_state[summary_key]))

st.markdown(
    f"<div style='color:{COLOR_MUTED};font-size:12px;margin-top:28px;'>"
    f"Las noticias se obtienen vía yfinance. Los análisis con IA usan el agente con tus tools."
    f"</div>",
    unsafe_allow_html=True,
)

footer_disclaimer()
