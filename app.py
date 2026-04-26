"""Home / Dashboard del Bot de Inversiones.

Página raíz de la app multipage. Estructura:
  - Hero (título + tagline + badge LLM activo).
  - Selector de cartera + fila de stat tiles (patrimonio, P&L, posiciones, cash).
  - Top posiciones en grid de holding cards.
  - Snapshot de mercado (gainers / losers / actives) en tres columnas.
  - Sugerencias de prompts compactos para entrar al Chat.

Sin emojis decorativos: la jerarquía la marcan los espacios y los pesos
tipográficos definidos en ``inject_app_styles``.
"""
from dotenv import load_dotenv
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.agent.agent_builder import get_active_llm_info
from src.services.portfolio import get_positions, get_portfolio_value
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.tools.market_tools import _fetch_fallback_quotes  # type: ignore
from src.ui.components import (
    COLOR_DIM,
    COLOR_MUTED,
    empty_state,
    fmt_money,
    hero,
    holding_card,
    inject_app_styles,
    llm_badge,
    market_row,
    render_topbar,
    section_title,
    stat_strip,
    stat_tile,
)

load_dotenv()

st.set_page_config(
    page_title="Bot de Inversiones",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_app_styles()
render_topbar(active="Inicio")

_ = get_agent()
_ = ensure_session_id()

if "first_visit" not in st.session_state:
    st.session_state.first_visit = True
    st.toast("Bienvenido. Usa la barra lateral para navegar entre secciones.", icon="👋")


# ---- Hero -------------------------------------------------------------------
_llm_provider, _llm_model = get_active_llm_info()
_provider_label = {"ollama": "Ollama · local", "openrouter": "OpenRouter · cloud"}.get(
    _llm_provider, _llm_provider
)

hero(
    "Bot de Inversiones",
    "Asistente conversacional con un agente LangChain. Cartera simulada, "
    "precios en vivo y RAG sobre material oficial CNMV / SEC.",
    badge_html=llm_badge(_provider_label, _llm_model),
)


# ---- Selector de cartera ----------------------------------------------------
try:
    _all_portfolios = pf_svc.list_portfolios()
except Exception:
    _all_portfolios = []

if _all_portfolios:
    _ids = [p["id"] for p in _all_portfolios]
    _names = {p["id"]: p["name"] for p in _all_portfolios}
    _cur = st.session_state.get("active_portfolio_id", _ids[0])
    if _cur not in _ids:
        _cur = _ids[0]
    sel_col, _spacer = st.columns([2, 5])
    with sel_col:
        _sel = st.selectbox(
            "Cartera activa",
            options=_ids,
            format_func=lambda i: f"#{i} · {_names[i]}",
            index=_ids.index(_cur),
            key="home_active_portfolio_selector",
            label_visibility="collapsed",
        )
    st.session_state["active_portfolio_id"] = _sel
    set_active_portfolio(_sel)
    active_portfolio_id = _sel
else:
    active_portfolio_id = 1


with st.spinner("Calculando cartera..."):
    try:
        positions = get_positions(portfolio_id=active_portfolio_id)
        pv = get_portfolio_value(portfolio_id=active_portfolio_id)
    except Exception as e:
        st.error(f"No pude leer la cartera: {e}")
        positions, pv = [], {"total_value": 0, "total_cost": 0, "total_pnl": 0, "total_pnl_pct": 0, "stale_tickers": []}


# ---- KPIs principales ------------------------------------------------------
_active_p = pf_svc.get_portfolio(active_portfolio_id) if _all_portfolios else None
_currency = _active_p["currency"] if _active_p else "USD"
_cash = pf_svc.cash_available(active_portfolio_id) if _all_portfolios else 0.0
total_value = pv.get("total_value", 0) or 0
total_pnl = pv.get("total_pnl", 0) or 0
total_pnl_pct = pv.get("total_pnl_pct", 0) or 0

stat_strip([
    stat_tile("Patrimonio", fmt_money(total_value, _currency)),
    stat_tile("P&L total", fmt_money(total_pnl, _currency), delta=total_pnl_pct),
    stat_tile("Posiciones", str(len(positions))),
    stat_tile("Cash disponible", fmt_money(_cash, _currency)),
])


# ---- Top posiciones --------------------------------------------------------
section_title("Top posiciones", "Las cinco mayores por valor de mercado.")

if not positions:
    empty_state(
        "Aún no tienes posiciones",
        "Abre el Chat y prueba con \"compra 10 acciones de AAPL\" para empezar.",
        icon="📈",
    )
else:
    top = sorted(positions, key=lambda p: (p.get("market_value") or 0), reverse=True)[:5]
    cols = st.columns(5)
    for col, p in zip(cols, top):
        col.markdown(
            holding_card(
                ticker=p["ticker"],
                qty=p["qty"],
                value=p.get("market_value"),
                pnl_pct=p.get("pnl_pct"),
                currency=_currency,
                avg_price=p.get("avg_price"),
                after_hours_price=p.get("after_hours_price"),
                after_hours_change_pct=p.get("after_hours_change_pct"),
            ),
            unsafe_allow_html=True,
        )
    st.write("")
    bcol1, bcol2, _ = st.columns([1.4, 1.4, 4])
    if bcol1.button("Abrir cartera", key="home_open_portfolio"):
        st.switch_page("pages/2_Mi_Cartera.py")
    if bcol2.button("Comparar tickers", key="home_compare_tickers"):
        st.session_state["prefill_prompt"] = "Compara AAPL vs MSFT"
        st.switch_page("pages/1_Chat.py")


# ---- Movers de hoy ---------------------------------------------------------
section_title("Movers de hoy", "Snapshot del universo S&P 500 (cache 5 min)")


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot() -> list[dict]:
    return _fetch_fallback_quotes()


try:
    snapshot = _snapshot()
except Exception:
    snapshot = []


def _market_block(label: str, items: list[dict]) -> None:
    st.markdown(
        f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.1em;"
        f"color:{COLOR_MUTED};margin-bottom:10px;font-weight:500;'>{label}</div>",
        unsafe_allow_html=True,
    )
    rows_html = ""
    for r in items:
        rows_html += market_row(
            ticker=r["ticker"],
            price=r.get("price"),
            change_pct=r.get("change_pct"),
            volume=r.get("volume"),
        )
    st.markdown(f"<div class='pill-card'>{rows_html}</div>", unsafe_allow_html=True)


if snapshot:
    gainers = sorted(snapshot, key=lambda r: r["change_pct"], reverse=True)[:5]
    losers = sorted(snapshot, key=lambda r: r["change_pct"])[:5]
    actives = sorted(snapshot, key=lambda r: r["volume"], reverse=True)[:5]
    col_g, col_l, col_a = st.columns(3)
    with col_g:
        _market_block("Gainers", gainers)
    with col_l:
        _market_block("Losers", losers)
    with col_a:
        _market_block("Most active", actives)
    st.write("")
    if st.button("Ver mercado completo →", key="home_to_top_dia"):
        st.switch_page("pages/5_Top_del_Dia.py")
else:
    st.info("No pudimos cargar el snapshot del mercado ahora mismo.")


# ---- Sugerencias -----------------------------------------------------------
section_title("Empieza por aquí", "Atajos al chat con prompts comunes")

suggestions = [
    "¿Cómo está AAPL?",
    "Resumen de mi cartera",
    "Noticias de NVDA",
    "Explícame qué es un ETF",
]
cols = st.columns(len(suggestions))
for col, text in zip(cols, suggestions):
    with col:
        if st.button(text, key=f"home_suggest_{text}", use_container_width=True):
            st.session_state["prefill_prompt"] = text
            st.switch_page("pages/1_Chat.py")

st.write("")
st.markdown(
    f"<p style='color:{COLOR_DIM};font-size:11px;margin-top:24px;'>"
    f"Información orientativa. Este bot no constituye asesoramiento financiero. "
    f"Datos de mercado vía Yahoo Finance.</p>",
    unsafe_allow_html=True,
)
