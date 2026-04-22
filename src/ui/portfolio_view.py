import pandas as pd
import streamlit as st

from src.services import portfolio
from src.ui.charts import portfolio_allocation_pie, portfolio_pnl_bar


def render_portfolio_tab() -> None:
    st.subheader("Cartera simulada")

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refrescar", key="portfolio_refresh"):
            st.rerun()

    try:
        positions = portfolio.get_positions()
        totals = portfolio.get_portfolio_value()
    except Exception as e:
        st.error(f"Error leyendo la cartera: {e}")
        return

    if not positions:
        st.info("📭 Tu cartera simulada está vacía. Pídele al agente: \"compra 10 MSFT\".")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Valor total", f"${totals['total_value']:.2f}")
    m2.metric("P&L total", f"${totals['total_pnl']:+.2f}")
    m3.metric("Rentabilidad", f"{totals['total_pnl_pct']:+.2f}%")

    df = pd.DataFrame([
        {
            "Ticker": p["ticker"],
            "Cantidad": p["qty"],
            "Precio medio": round(p["avg_price"], 2),
            "Precio actual": round(p["current_price"], 2) if p["current_price"] is not None else None,
            "Coste": round(p["cost_basis"], 2),
            "Valor mercado": round(p["market_value"], 2) if p["market_value"] is not None else None,
            "P&L": round(p["pnl"], 2) if p["pnl"] is not None else None,
            "P&L %": round(p["pnl_pct"], 2) if p["pnl_pct"] is not None else None,
        }
        for p in positions
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
            txs = portfolio.get_transactions(limit=20)
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
