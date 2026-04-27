"""Pestaña de Streamlit que muestra la cartera simulada del usuario.

Multi-cartera: acepta ``portfolio_id`` como parámetro. Si viene None lee
``st.session_state.active_portfolio_id`` (default 1).
"""
import streamlit as st

from src.services import portfolio
from src.services import portfolios
from src.ui.charts import portfolio_allocation_pie, portfolio_pnl_bar
from src.ui.components import (
    empty_state,
    holding_card,
    section_title,
    trade_row,
)


def render_portfolio_tab(portfolio_id: int | None = None) -> None:
    """Pinta la pestaña de cartera para ``portfolio_id`` (o la activa)."""
    if portfolio_id is None:
        portfolio_id = st.session_state.get("active_portfolio_id", 1)
    pid = int(portfolio_id)

    p = portfolios.get_portfolio(pid)
    if p is None:
        st.error(f"La cartera con id={pid} no existe.")
        return

    section_title(
        p["name"],
        f"Riesgo: {p['risk']} · Mercados: {p['markets']} · Moneda: {p['currency']}",
    )

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("Refrescar", key=f"portfolio_refresh_{pid}"):
            st.rerun()

    try:
        positions = portfolio.get_positions(portfolio_id=pid)
    except Exception as e:
        st.error(f"Error leyendo la cartera: {e}")
        return

    if not positions:
        empty_state(
            "Cartera vacía",
            "Pídele al agente \"compra 10 MSFT\".",
            icon="📭",
        )
        return

    # ---- Grid de holdings (rows de 5 cards) -------------------------------
    currency = p["currency"]
    per_row = 5
    for start in range(0, len(positions), per_row):
        chunk = positions[start:start + per_row]
        cols = st.columns(per_row)
        for col, pp in zip(cols, chunk):
            col.markdown(
                holding_card(
                    ticker=pp["ticker"],
                    qty=pp["qty"],
                    value=pp.get("market_value"),
                    pnl_pct=pp.get("pnl_pct"),
                    currency=currency,
                    avg_price=pp.get("avg_price"),
                    after_hours_price=pp.get("after_hours_price"),
                    after_hours_change_pct=pp.get("after_hours_change_pct"),
                ),
                unsafe_allow_html=True,
            )
        # Espacio entre filas — sin esto, las cards quedan pegadas verticalmente
        # cuando hay más de 5 posiciones.
        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    # ---- Charts: allocation + pnl ----------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        fig_pie = portfolio_allocation_pie(positions)
        if fig_pie is not None:
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.caption("Sin datos suficientes para el gráfico de asignación.")
    with c2:
        fig_pnl = portfolio_pnl_bar(positions)
        if fig_pnl is not None:
            st.plotly_chart(fig_pnl, use_container_width=True)
        else:
            st.caption("Sin datos suficientes para el gráfico de P&L.")

    # ---- Historial reciente ---------------------------------------------
    with st.expander("Historial reciente"):
        try:
            txs = portfolio.get_transactions(limit=20, portfolio_id=pid)
        except Exception as e:
            st.error(f"Error leyendo transacciones: {e}")
            txs = []
        if not txs:
            st.write("No hay transacciones registradas.")
        else:
            rows_html = ""
            for t in txs:
                rows_html += trade_row(
                    ts=t["ts"],
                    ticker=t["ticker"],
                    side=t["side"],
                    qty=t["qty"],
                    price=t["price"],
                    currency=currency,
                )
            st.markdown(
                f"<div class='pill-card'>{rows_html}</div>",
                unsafe_allow_html=True,
            )
