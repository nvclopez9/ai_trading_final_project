"""Página Top del Día: tickers con más movimiento.

Tres tabs (gainers / losers / actives) consumen el snapshot del universo
S&P 500 y muestran tarjetas compactas con ticker, precio y delta. Al
clicar un ticker lo marca como ``active_ticker`` y abre Mercado.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.tools.market_tools import _fetch_fallback_quotes  # type: ignore
from src.ui.components import (
    COLOR_DIM,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    delta_badge,
    hero,
    inject_app_styles,
)

st.set_page_config(page_title="Top del día · Bot de Inversiones", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

hero(
    "Top del día",
    "Mayores subidas, bajadas y volumen del universo S&P 500.",
)

_ = get_agent()
_ = ensure_session_id()


@st.cache_data(ttl=300, show_spinner=False)
def _snapshot() -> list[dict]:
    return _fetch_fallback_quotes()


with st.spinner("Cargando universo..."):
    try:
        rows = _snapshot()
    except Exception as e:
        st.error(f"No pude cargar los tickers: {e}")
        st.stop()

if not rows:
    st.warning("No hay datos disponibles ahora mismo.")
    st.stop()

gainers = sorted(rows, key=lambda r: r["change_pct"], reverse=True)[:10]
losers = sorted(rows, key=lambda r: r["change_pct"])[:10]
actives = sorted(rows, key=lambda r: r["volume"], reverse=True)[:10]


def _card_html(r: dict) -> str:
    """Genera HTML para una tarjeta de ticker (sin botón, que lo añade Streamlit)."""
    ticker = r["ticker"]
    price = r.get("price") or 0.0
    pct = r.get("change_pct") or 0.0
    volume = r.get("volume") or 0
    vol_str = ""
    if volume:
        vol_str = (
            f"<div style='color:{COLOR_DIM};font-size:11px;font-family:JetBrains Mono,monospace;"
            f"margin-top:6px;'>{volume / 1e6:.1f}M vol</div>"
        )
    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid #252D3D;"
        f"border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:8px;height:100%;'>"
        f"<div style='font-family:JetBrains Mono,monospace;font-weight:700;letter-spacing:0.4px;"
        f"font-size:1.1rem;color:{COLOR_TEXT};'>{ticker}</div>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:1.1rem;font-weight:600;"
        f"color:{COLOR_TEXT};'>{price:.2f}</div>"
        f"<div>{delta_badge(pct, big=True)}</div>"
        f"{vol_str}"
        f"</div>"
    )


def _render_grid(title: str, items: list[dict]) -> None:
    """Pinta un grid de 5 columnas con las tarjetas y un botón Ver bajo cada una."""
    if not items:
        st.info("Sin resultados.")
        return
    # Render 5 por fila.
    for i in range(0, len(items), 5):
        chunk = items[i:i + 5]
        cols = st.columns(5)
        for col, r in zip(cols, chunk):
            col.markdown(_card_html(r), unsafe_allow_html=True)
            col.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            if col.button("Ver", key=f"hot_{title}_{r['ticker']}", use_container_width=True):
                st.session_state["active_ticker"] = r["ticker"]
                st.switch_page("pages/4_Mercado.py")
        # Espacio entre filas para que las cards no queden pegadas verticalmente.
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        # Si la última fila tiene menos de 5, deja el resto vacío (st.columns ya equilibra).


tab_g, tab_l, tab_a = st.tabs(["Gainers", "Losers", "Most active"])
with tab_g:
    _render_grid("gainers", gainers)
with tab_l:
    _render_grid("losers", losers)
with tab_a:
    _render_grid("actives", actives)

st.markdown(
    f"<div style='color:{COLOR_MUTED};font-size:12px;margin-top:24px;'>"
    f"Snapshot cacheado 5 min. Pulsa <b>Ver</b> para abrir el ticker en Mercado."
    f"</div>",
    unsafe_allow_html=True,
)
