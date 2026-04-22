"""Pestaña de Streamlit que muestra la cartera simulada del usuario.

Layout:
  1. Botón "Refrescar" que fuerza un ``st.rerun()`` para volver a pedir
     precios actuales a yfinance (sin esto, Streamlit solo re-ejecutaría
     al interactuar con otro widget).
  2. Tres métricas arriba (valor total, P&L total, rentabilidad %).
  3. Tabla con una fila por posición (pandas DataFrame).
  4. Dos gráficos Plotly en columnas (pie de asignación + bar de P&L).
  5. Expander con el historial de transacciones.

Este módulo NO habla con el agente; es un render puro contra
``src/services/portfolio.py``. El agente modifica la BD mediante las tools
de cartera y esta vista refleja el estado resultante.
"""
# pandas: construir DataFrames que Streamlit pinta como tabla interactiva.
# streamlit: widgets, layout y rerun.
import pandas as pd
import streamlit as st

# Servicios de cartera (CRUD + agregados) y helpers de gráficos.
from src.services import portfolio
from src.ui.charts import portfolio_allocation_pie, portfolio_pnl_bar


def render_portfolio_tab() -> None:
    """Pinta toda la pestaña de cartera. La llama ``app.py`` dentro de su tab2."""
    st.subheader("Cartera simulada")

    # Botón de refresco: yfinance puede variar en segundos; el usuario decide
    # cuándo quiere pagar la latencia de re-consultar precios.
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refrescar", key="portfolio_refresh"):
            st.rerun()

    # Llamadas a los servicios. Si la BD aún no existe o hay un fallo raro,
    # mostramos un error controlado y salimos sin romper la página.
    try:
        positions = portfolio.get_positions()
        totals = portfolio.get_portfolio_value()
    except Exception as e:
        st.error(f"Error leyendo la cartera: {e}")
        return

    # Caso cartera vacía: pista accionable al usuario sobre cómo empezar.
    if not positions:
        st.info("📭 Tu cartera simulada está vacía. Pídele al agente: \"compra 10 MSFT\".")
        return

    # Tres métricas en una fila: valor, P&L absoluto y P&L porcentual.
    # st.metric aplica estilo "KPI card" coherente con el resto de la app.
    m1, m2, m3 = st.columns(3)
    m1.metric("Valor total", f"${totals['total_value']:.2f}")
    m2.metric("P&L total", f"${totals['total_pnl']:+.2f}")
    m3.metric("Rentabilidad", f"{totals['total_pnl_pct']:+.2f}%")

    # Construimos un DataFrame con las columnas en español. Los None se
    # preservan para que el dataframe muestre celda vacía (mejor que "n/d"
    # en una tabla numérica que se ordena). Redondeamos a 2 decimales.
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
    # use_container_width=True: la tabla ocupa todo el ancho disponible.
    # hide_index=True: no mostramos el índice 0..N de pandas.
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Dos gráficos lado a lado: pie de asignación y bar de P&L.
    c1, c2 = st.columns(2)
    with c1:
        fig_pie = portfolio_allocation_pie(positions)
        if fig_pie is not None:
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            # Caption en vez de error: si no hay datos es algo esperado,
            # no un fallo de la app.
            st.caption("Sin datos suficientes para el gráfico de asignación.")
    with c2:
        fig_pnl = portfolio_pnl_bar(positions)
        if fig_pnl is not None:
            st.plotly_chart(fig_pnl, use_container_width=True)
        else:
            st.caption("Sin datos suficientes para el gráfico de P&L.")

    # Expander con las últimas 20 transacciones; oculto por defecto para no
    # saturar la vista principal.
    with st.expander("Historial de transacciones"):
        try:
            txs = portfolio.get_transactions(limit=20)
        except Exception as e:
            st.error(f"Error leyendo transacciones: {e}")
            txs = []
        if not txs:
            st.write("No hay transacciones registradas.")
        else:
            # DataFrame paralelo al de posiciones pero con las 5 columnas de la transacción.
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
