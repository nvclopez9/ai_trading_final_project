"""Pestaña de Streamlit que muestra la cartera simulada del usuario.

Multi-cartera: acepta ``portfolio_id`` como parámetro. Si viene None lee
``st.session_state.active_portfolio_id`` (default 1).
"""
import pandas as pd
import streamlit as st

from src.services import portfolio
from src.services import portfolios
from src.ui.charts import portfolio_allocation_pie, portfolio_pnl_bar
from src.ui.components import fmt_money, fmt_pct


def render_portfolio_tab(portfolio_id: int | None = None) -> None:
    """Pinta la pestaña de cartera para ``portfolio_id`` (o la activa)."""
    if portfolio_id is None:
        portfolio_id = st.session_state.get("active_portfolio_id", 1)
    pid = int(portfolio_id)

    p = portfolios.get_portfolio(pid)
    if p is None:
        st.error(f"La cartera con id={pid} no existe.")
        return

    st.subheader(f"Cartera simulada · {p['name']}")
    st.caption(
        f"Riesgo: **{p['risk']}** · Mercados: **{p['markets']}** · "
        f"Moneda: **{p['currency']}**"
    )

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refrescar", key=f"portfolio_refresh_{pid}"):
            st.rerun()

    try:
        positions = portfolio.get_positions(portfolio_id=pid)
        totals = portfolio.get_portfolio_value(portfolio_id=pid)
        cash = portfolios.cash_available(pid)
    except Exception as e:
        st.error(f"Error leyendo la cartera: {e}")
        return

    if not positions:
        st.info("📭 Tu cartera simulada está vacía. Pídele al agente: \"compra 10 MSFT\".")
        m1, m2 = st.columns(2)
        m1.metric("Cash inicial", fmt_money(p["initial_cash"], p["currency"]))
        m2.metric("Cash disponible", fmt_money(cash, p["currency"]))
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Valor total", fmt_money(totals.get("total_value") or 0, p["currency"]))
    m2.metric("P&L total", fmt_money(totals.get("total_pnl") or 0, p["currency"]))
    m3.metric("Rentabilidad", fmt_pct(totals.get("total_pnl_pct") or 0))
    m4.metric("Cash disponible", fmt_money(cash, p["currency"]))

    df = pd.DataFrame([
        {
            "Ticker": pp["ticker"],
            "Cantidad": pp["qty"],
            "Precio medio": round(pp["avg_price"], 2),
            "Precio actual": round(pp["current_price"], 2) if pp["current_price"] is not None else None,
            "Coste": round(pp["cost_basis"], 2),
            "Valor mercado": round(pp["market_value"], 2) if pp["market_value"] is not None else None,
            "P&L": round(pp["pnl"], 2) if pp["pnl"] is not None else None,
            "P&L %": round(pp["pnl_pct"], 2) if pp["pnl_pct"] is not None else None,
        }
        for pp in positions
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

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

    with st.expander("Historial de transacciones"):
        try:
            txs = portfolio.get_transactions(limit=20, portfolio_id=pid)
        except Exception as e:
            st.error(f"Error leyendo transacciones: {e}")
            txs = []
        if not txs:
            st.write("No hay transacciones registradas.")
        else:
            df_tx = pd.DataFrame([
                {
                    "Fecha": t["ts"],
                    "Ticker": t["ticker"],
                    "Lado": t["side"],
                    "Cantidad": t["qty"],
                    "Precio": round(t["price"], 2),
                }
                for t in txs
            ])
            st.dataframe(df_tx, use_container_width=True, hide_index=True)
