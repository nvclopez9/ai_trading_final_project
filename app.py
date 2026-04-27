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
    fmt_pct,
    footer_disclaimer,
    hero,
    holding_card,
    inject_app_styles,
    llm_badge,
    market_row,
    section_title,
    sidebar_kpi,
    stat_strip,
    stat_tile,
)

load_dotenv()

st.set_page_config(
    page_title="Bot de Inversiones",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_app_styles()

_ = get_agent()
_ = ensure_session_id()

if "first_visit" not in st.session_state:
    st.session_state.first_visit = True
    st.toast("Bienvenido. Usa la barra lateral para navegar entre secciones.", icon="👋")


# ---- Sidebar contextual: resumen de la sesión activa ---------------------
with st.sidebar:
    try:
        _all_portfolios_sb = pf_svc.list_portfolios()
    except Exception:
        _all_portfolios_sb = []
    if _all_portfolios_sb:
        _ids_sb = [p["id"] for p in _all_portfolios_sb]
        _names_sb = {p["id"]: p["name"] for p in _all_portfolios_sb}
        _cur_sb = st.session_state.get("active_portfolio_id", _ids_sb[0])
        if _cur_sb not in _ids_sb:
            _cur_sb = _ids_sb[0]
        st.markdown("<div class='section-eyebrow'>Cartera activa</div>", unsafe_allow_html=True)
        _sel_sb = st.selectbox(
            "Cartera activa",
            options=_ids_sb,
            format_func=lambda i: f"#{i} · {_names_sb[i]}",
            index=_ids_sb.index(_cur_sb),
            key="home_sidebar_active_portfolio",
            label_visibility="collapsed",
        )
        st.session_state["active_portfolio_id"] = _sel_sb
        set_active_portfolio(_sel_sb)

        try:
            _pv_sb = get_portfolio_value(portfolio_id=_sel_sb)
            _cash_sb = pf_svc.cash_available(_sel_sb)
            _p_sb = pf_svc.get_portfolio(_sel_sb)
            _curr_sb = _p_sb["currency"] if _p_sb else "USD"
        except Exception:
            _pv_sb, _cash_sb, _curr_sb = {}, 0.0, "USD"
        st.markdown(sidebar_kpi(
            "Patrimonio",
            fmt_money((_pv_sb.get("total_value") or 0) + _cash_sb, _curr_sb),
        ), unsafe_allow_html=True)
        st.markdown(sidebar_kpi(
            "P&L total",
            fmt_money(_pv_sb.get("total_pnl") or 0, _curr_sb),
            delta=_pv_sb.get("total_pnl_pct"),
        ), unsafe_allow_html=True)
        if _pv_sb.get("total_value_after_hours") is not None:
            st.markdown(sidebar_kpi(
                "After hours",
                fmt_money(_pv_sb["total_value_after_hours"], _curr_sb),
                delta=_pv_sb.get("after_hours_delta_pct"),
                hint="Sesión extendida USA",
            ), unsafe_allow_html=True)

    st.markdown("<div class='section-eyebrow' style='margin-top:14px;'>Atajos</div>", unsafe_allow_html=True)
    if st.button("Abrir chat →", key="home_sb_open_chat", use_container_width=True):
        st.switch_page("pages/1_Chat.py")
    if st.button("Ver cartera →", key="home_sb_open_portfolio", use_container_width=True):
        st.switch_page("pages/2_Mi_Cartera.py")
    if st.button("Mercado →", key="home_sb_open_market", use_container_width=True):
        st.switch_page("pages/4_Mercado.py")


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

# Sugerencias contextuales (Fase 4): si el usuario tiene posiciones, generamos
# 4 prompts derivados de su cartera real. Si no, defaults educativos.
def _contextual_suggestions(positions: list[dict]) -> list[str]:
    if not positions:
        return [
            "¿Cómo está AAPL?",
            "Resumen de mi cartera",
            "Noticias de NVDA",
            "Explícame qué es un ETF",
        ]
    top = sorted(positions, key=lambda p: (p.get("market_value") or 0), reverse=True)
    biggest = top[0]["ticker"] if top else None
    out: list[str] = ["Resumen de mi cartera"]
    if biggest:
        out.append(f"Noticias de {biggest}")
        out.append(f"¿Es buen momento para vender {biggest}?")
    if len(top) > 1:
        out.append(f"Compara {top[0]['ticker']} vs {top[1]['ticker']}")
    else:
        out.append("¿Debería diversificar más?")
    return out[:4]


suggestions = _contextual_suggestions(positions)
cols = st.columns(len(suggestions))
for col, text in zip(cols, suggestions):
    with col:
        if st.button(text, key=f"home_suggest_{text}", use_container_width=True):
            st.session_state["prefill_prompt"] = text
            st.switch_page("pages/1_Chat.py")

footer_disclaimer()
