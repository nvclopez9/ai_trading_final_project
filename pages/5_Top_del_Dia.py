"""Página Hot: tickers con más movimiento del día.

Tres tabs (gainers / losers / actives) que consumen la tool
``get_hot_tickers`` y muestran las tablas formateadas. Al clicar un ticker
lo marca como ``active_ticker`` y abre Mercado.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.tools.market_tools import _fetch_fallback_quotes  # type: ignore

st.set_page_config(page_title="Hot tickers · Bot de Inversiones", page_icon="🔥")
st.title("🔥 Tickers con más movimiento")
st.caption("Mayores subidas, bajadas y volumen del universo S&P 500 que seguimos.")

_ = get_agent()
_ = ensure_session_id()


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot() -> list[dict]:
    """Snapshot de 30 tickers representativos con cache de 5 min."""
    return _fetch_fallback_quotes()


with st.spinner("Cargando universo..."):
    try:
        rows = _snapshot()
    except Exception as e:
        st.error(f"No pude cargar los tickers hot: {e}")
        st.stop()

if not rows:
    st.warning("No hay datos disponibles ahora mismo.")
    st.stop()

gainers = sorted(rows, key=lambda r: r["change_pct"], reverse=True)[:10]
losers = sorted(rows, key=lambda r: r["change_pct"])[:10]
actives = sorted(rows, key=lambda r: r["volume"], reverse=True)[:10]


def _render_table(title: str, items: list[dict]) -> None:
    """Dibuja una tabla con un botón por fila para saltar a Mercado."""
    for r in items:
        col_t, col_p, col_c, col_btn = st.columns([1.2, 1, 1, 1])
        col_t.markdown(f"**{r['ticker']}**")
        col_p.write(f"{r['price']:.2f}")
        pct = r["change_pct"]
        color = "#00C851" if pct >= 0 else "#FF4444"
        sign = "+" if pct >= 0 else ""
        col_c.markdown(f"<span style='color:{color};'>{sign}{pct:.2f}%</span>", unsafe_allow_html=True)
        if col_btn.button("Ver", key=f"hot_{title}_{r['ticker']}"):
            st.session_state["active_ticker"] = r["ticker"]
            st.switch_page("pages/4_Mercado.py")


tab_g, tab_l, tab_a = st.tabs(["📈 Gainers", "📉 Losers", "🔊 Most active"])
with tab_g:
    _render_table("gainers", gainers)
with tab_l:
    _render_table("losers", losers)
with tab_a:
    _render_table("actives", actives)
