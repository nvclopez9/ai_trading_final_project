"""Página Cartera: posiciones, P&L y transacciones.

Multi-cartera: permite cambiar la cartera activa desde el selector. El
render real vive en ``src/ui/portfolio_view.py``.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.portfolio_charts import render_portfolio_pnl_chart
from src.ui.portfolio_view import render_portfolio_tab

st.set_page_config(page_title="Cartera · Bot de Inversiones", page_icon="💼")
st.title("💼 Mi cartera simulada")

_ = get_agent()
_ = ensure_session_id()

# Selector de cartera activa (coherente con la página Carteras).
all_portfolios = pf_svc.list_portfolios()
if all_portfolios:
    ids = [p["id"] for p in all_portfolios]
    names_by_id = {p["id"]: p["name"] for p in all_portfolios}
    current_id = st.session_state.get("active_portfolio_id", ids[0])
    if current_id not in ids:
        current_id = ids[0]
    selected_id = st.selectbox(
        "Cartera activa",
        options=ids,
        format_func=lambda i: f"#{i} · {names_by_id[i]}",
        index=ids.index(current_id),
        key="cartera_page_active",
    )
    st.session_state["active_portfolio_id"] = selected_id
    set_active_portfolio(selected_id)
    render_portfolio_tab(portfolio_id=selected_id)
    # Bloque de evolución del P&L de la cartera completa con selector de timeline.
    st.divider()
    render_portfolio_pnl_chart(portfolio_id=selected_id)
else:
    st.error("No hay carteras. Ve a 🧺 Mis Carteras para crear una.")
