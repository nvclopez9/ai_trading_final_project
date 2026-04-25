"""🏠 Home / Dashboard del Bot de Inversiones.

Página raíz de la app (Streamlit Multipage Apps). Desde aquí el usuario ve:
  - Valor total de su cartera simulada y P&L del día.
  - Top 5 posiciones con % y mini-estado.
  - Tres listas rápidas del mercado (gainers / losers / actives).
  - Sugerencias de prompts para entrar rápido al Chat.

Navegación:
  - La sidebar de Streamlit muestra automáticamente las páginas bajo ``pages/``.
  - Los botones CTA de esta home guardan ``active_ticker`` o ``prefill_prompt``
    en session_state y hacen ``st.switch_page`` a la página correspondiente.
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
    fmt_money,
    fmt_pct,
    color_for_delta,
)

load_dotenv()

st.set_page_config(
    page_title="Bot de Inversiones",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

# Bootstrap: asegura BD + agente + session_id cargados antes de las demás páginas.
_ = get_agent()
_ = ensure_session_id()

# Onboarding al primer render de la sesión (sólo 1 vez por pestaña).
if "first_visit" not in st.session_state:
    st.session_state.first_visit = True
    st.toast("¡Bienvenido! Usa la barra lateral para navegar entre secciones.", icon="👋")

# Cabecera con saludo.
st.title("🏠 Bot de Inversiones")
st.caption("Tu asistente conversacional con agente de IA (LangChain + Ollama / OpenRouter).")

# Badge del LLM activo. Lee del .env tras el fallback aplicado en _build_llm()
# para no mentirle al usuario si seleccionó openrouter sin API key.
_llm_provider, _llm_model = get_active_llm_info()
_provider_label = {"ollama": "🖥️ Ollama (local)", "openrouter": "☁️ OpenRouter (cloud)"}.get(
    _llm_provider, _llm_provider
)
st.caption(f"🤖 LLM activo: **{_provider_label}** · `{_llm_model}`")


# -----------------------------------------------------------------------------
# Fila 1 — Resumen de cartera
# -----------------------------------------------------------------------------
# Selector breve de cartera activa (Home).
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
    _sel = st.selectbox(
        "Cartera activa",
        options=_ids,
        format_func=lambda i: f"#{i} · {_names[i]}",
        index=_ids.index(_cur),
        key="home_active_portfolio_selector",
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

left, right = st.columns([1, 1])
with left:
    _active_p = pf_svc.get_portfolio(active_portfolio_id) if _all_portfolios else None
    _title_suffix = f" · {_active_p['name']}" if _active_p else ""
    st.subheader(f"💼 Tu cartera{_title_suffix}")
    total_value = pv.get("total_value", 0) or 0
    total_pnl = pv.get("total_pnl", 0) or 0
    total_pnl_pct = pv.get("total_pnl_pct", 0) or 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor actual", fmt_money(total_value, "USD"))
    c2.metric("P&L", fmt_money(total_pnl, "USD"), delta=fmt_pct(total_pnl_pct))
    c3.metric("Posiciones", str(len(positions)))
    if st.button("Abrir cartera →"):
        st.switch_page("pages/2_Mi_Cartera.py")

with right:
    st.subheader("📌 Top posiciones")
    if not positions:
        st.info("Aún no tienes posiciones. Abre el Chat y di 'Compra 10 acciones de AAPL' para empezar.")
    else:
        top = sorted(
            positions,
            key=lambda p: (p.get("market_value") or 0),
            reverse=True,
        )[:5]
        for p in top:
            t = p["ticker"]
            qty = p["qty"]
            pnl_pct = p.get("pnl_pct")
            col_t, col_q, col_pnl, col_btn = st.columns([1, 1, 1, 1])
            col_t.markdown(f"**{t}**")
            col_q.write(f"{qty} uds")
            if pnl_pct is not None:
                color = color_for_delta(pnl_pct)
                col_pnl.markdown(f"<span style='color:{color};'>{fmt_pct(pnl_pct)}</span>", unsafe_allow_html=True)
            else:
                col_pnl.write("—")
            if col_btn.button("Ver", key=f"home_top_{t}"):
                st.session_state["active_ticker"] = t
                st.switch_page("pages/4_Mercado.py")

st.divider()


# -----------------------------------------------------------------------------
# Fila 2 — Mercado hoy
# -----------------------------------------------------------------------------
st.subheader("🔥 Mercado hoy")


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot() -> list[dict]:
    """Snapshot de 30 tickers. Cache 5 min para no saturar yfinance."""
    return _fetch_fallback_quotes()


try:
    snapshot = _snapshot()
except Exception:
    snapshot = []

if snapshot:
    gainers = sorted(snapshot, key=lambda r: r["change_pct"], reverse=True)[:3]
    losers = sorted(snapshot, key=lambda r: r["change_pct"])[:3]
    actives = sorted(snapshot, key=lambda r: r["volume"], reverse=True)[:3]

    col_g, col_l, col_a = st.columns(3)
    with col_g:
        st.markdown("**📈 Top gainers**")
        for r in gainers:
            st.markdown(
                f"{r['ticker']} &nbsp; <span style='color:#00C851;'>+{r['change_pct']:.2f}%</span>",
                unsafe_allow_html=True,
            )
    with col_l:
        st.markdown("**📉 Top losers**")
        for r in losers:
            st.markdown(
                f"{r['ticker']} &nbsp; <span style='color:#FF4444;'>{r['change_pct']:.2f}%</span>",
                unsafe_allow_html=True,
            )
    with col_a:
        st.markdown("**🔊 Most active**")
        for r in actives:
            vol_m = r["volume"] / 1e6 if r["volume"] else 0
            st.markdown(f"{r['ticker']} &nbsp; {vol_m:.1f} M")

    if st.button("Ver más en 🔥 Top del día →"):
        st.switch_page("pages/5_Top_del_Dia.py")
else:
    st.info("No pudimos cargar el snapshot del mercado ahora mismo.")

st.divider()


# -----------------------------------------------------------------------------
# Fila 3 — Sugerencias del bot
# -----------------------------------------------------------------------------
st.subheader("💡 Sugerencias para empezar")
suggestions = [
    "¿Cómo está AAPL?",
    "Resumen de mi cartera",
    "¿Qué noticias hay de NVDA?",
    "Explícame qué es un ETF",
]
cols = st.columns(len(suggestions))
for col, text in zip(cols, suggestions):
    with col:
        if st.button(text, key=f"home_suggest_{text}", use_container_width=True):
            st.session_state["prefill_prompt"] = text
            st.switch_page("pages/1_Chat.py")

st.divider()
st.caption(
    "⚠️ Información orientativa. Este bot no constituye asesoramiento financiero. "
    "Todos los datos de mercado proceden de Yahoo Finance."
)
