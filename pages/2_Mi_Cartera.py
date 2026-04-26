"""Página Cartera: posiciones, P&L, evolución, watchlist y exportes.

Multi-cartera: permite cambiar la cartera activa desde el selector. El render
de posiciones está en ``src/ui/portfolio_view.py`` y el chart histórico en
``src/ui/portfolio_charts.py``. Esta página orquesta los tres bloques en
tabs y añade utilidades transversales (export CSV).
"""
import io

import pandas as pd
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolios as pf_svc
from src.services import portfolio as pf_service
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.components import (
    fmt_money,
    fmt_pct,
    hero,
    inject_app_styles,
    render_topbar,
    stat_strip,
    stat_tile,
)
from src.ui.portfolio_charts import render_portfolio_pnl_chart
from src.ui.portfolio_view import render_portfolio_tab
from src.ui.watchlist_view import render_watchlist_tab

st.set_page_config(page_title="Cartera · Bot de Inversiones", page_icon="💼", layout="wide", initial_sidebar_state="collapsed")
inject_app_styles()
render_topbar(active="Cartera")

hero(
    "Mi cartera",
    "Posiciones, P&L y evolución de la cartera activa.",
)

_ = get_agent()
_ = ensure_session_id()

all_portfolios = pf_svc.list_portfolios()
if not all_portfolios:
    st.error("No hay carteras. Ve a Mis Carteras para crear una.")
    st.stop()

# Selector de cartera activa (coherente con la página Carteras).
ids = [p["id"] for p in all_portfolios]
names_by_id = {p["id"]: p["name"] for p in all_portfolios}
current_id = st.session_state.get("active_portfolio_id", ids[0])
if current_id not in ids:
    current_id = ids[0]

sel_col, _spacer = st.columns([2, 5])
with sel_col:
    selected_id = st.selectbox(
        "Cartera activa",
        options=ids,
        format_func=lambda i: f"#{i} · {names_by_id[i]}",
        index=ids.index(current_id),
        key="cartera_page_active",
        label_visibility="collapsed",
    )
st.session_state["active_portfolio_id"] = selected_id
set_active_portfolio(selected_id)


# ---- KPIs -----------------------------------------------------------------
_active_p = pf_svc.get_portfolio(selected_id)
_currency = _active_p["currency"] if _active_p else "USD"

try:
    totals = pf_service.get_portfolio_value(portfolio_id=selected_id)
    cash = pf_svc.cash_available(selected_id)
except Exception as e:
    st.error(f"Error leyendo la cartera: {e}")
    totals, cash = {"total_value": 0, "total_pnl": 0, "total_pnl_pct": 0}, 0.0

total_value = totals.get("total_value") or 0
total_pnl = totals.get("total_pnl") or 0
total_pnl_pct = totals.get("total_pnl_pct") or 0

_ah_total = totals.get("total_value_after_hours")
_ah_delta_pct = totals.get("after_hours_delta_pct")

_tiles = [
    stat_tile("Patrimonio", fmt_money(total_value, _currency)),
    stat_tile("P&L total", fmt_money(total_pnl, _currency), delta=total_pnl_pct),
    stat_tile("Rentabilidad", fmt_pct(total_pnl_pct)),
    stat_tile("Cash disponible", fmt_money(cash, _currency)),
]
if _ah_total is not None:
    _tiles.append(
        stat_tile(
            "After hours",
            fmt_money(_ah_total, _currency),
            delta=_ah_delta_pct,
            hint="Sesión extendida USA",
        )
    )
stat_strip(_tiles)


# ---- Tabs -----------------------------------------------------------------
tab_resumen, tab_watch, tab_export = st.tabs(["Resumen", "Watchlist", "Exportar"])

with tab_resumen:
    render_portfolio_tab(portfolio_id=selected_id)
    st.divider()
    render_portfolio_pnl_chart(portfolio_id=selected_id)

with tab_watch:
    render_watchlist_tab(portfolio_id=selected_id)

with tab_export:
    try:
        positions = pf_service.get_positions(portfolio_id=selected_id)
        if positions:
            df_pos = pd.DataFrame(positions)
            buf_pos = io.StringIO()
            df_pos.to_csv(buf_pos, index=False)
            st.download_button(
                "Descargar posiciones",
                data=buf_pos.getvalue(),
                file_name=f"posiciones_cartera_{selected_id}.csv",
                mime="text/csv",
                key=f"dl_pos_{selected_id}",
            )
        else:
            st.caption("No hay posiciones que exportar.")
        txs = pf_service.get_transactions(limit=10_000, portfolio_id=selected_id)
        if txs:
            df_tx = pd.DataFrame(txs)
            buf_tx = io.StringIO()
            df_tx.to_csv(buf_tx, index=False)
            st.download_button(
                "Descargar transacciones",
                data=buf_tx.getvalue(),
                file_name=f"transacciones_cartera_{selected_id}.csv",
                mime="text/csv",
                key=f"dl_tx_{selected_id}",
            )
        else:
            st.caption("No hay transacciones que exportar.")
    except Exception as e:
        st.warning(f"No se pudo preparar el export: {e}")
