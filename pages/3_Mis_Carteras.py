"""🧺 Carteras — gestión multi-cartera.

Primera página de la sidebar (prefijo ``0_``). Permite:
  - Seleccionar la cartera ACTIVA (se guarda en session_state y se propaga
    a las tools del agente).
  - Ver resumen de la cartera activa (cash, valor, P&L).
  - Crear nuevas carteras con nombre, cash inicial, riesgo, mercados.
  - Listar todas las carteras con tabla resumen.
  - Eliminar carteras (excepto la Default).
"""
import pandas as pd
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolio as pf_service
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.components import fmt_money, fmt_pct

st.set_page_config(page_title="Carteras · Bot de Inversiones", page_icon="🧺")

_ = get_agent()
_ = ensure_session_id()

st.title("🧺 Mis carteras")
st.caption("Gestiona varias carteras simuladas con perfiles y mercados distintos.")

# -----------------------------------------------------------------------------
# Selector de cartera activa
# -----------------------------------------------------------------------------
all_portfolios = pf_svc.list_portfolios()
if not all_portfolios:
    st.error("No hay carteras en la base de datos. Reinicia la app para que se cree la Default.")
    st.stop()

names_by_id = {p["id"]: p["name"] for p in all_portfolios}
ids = [p["id"] for p in all_portfolios]

current_id = st.session_state.get("active_portfolio_id", ids[0])
if current_id not in ids:
    current_id = ids[0]

selected_id = st.selectbox(
    "Cartera activa",
    options=ids,
    format_func=lambda i: f"#{i} · {names_by_id[i]}",
    index=ids.index(current_id),
    key="portfolios_active_selector",
)
if selected_id != st.session_state.get("active_portfolio_id"):
    st.session_state["active_portfolio_id"] = selected_id
    set_active_portfolio(selected_id)
    st.toast(f"Cartera activa: {names_by_id[selected_id]}", icon="✅")
else:
    # Asegura que la tool knows aunque no haya cambio.
    set_active_portfolio(selected_id)

active = pf_svc.get_portfolio(selected_id)
totals = pf_service.get_portfolio_value(portfolio_id=selected_id)
cash = pf_svc.cash_available(selected_id)

st.divider()

# -----------------------------------------------------------------------------
# Tarjeta detalle de la cartera activa
# -----------------------------------------------------------------------------
st.subheader(f"📊 {active['name']}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Cash inicial", fmt_money(active["initial_cash"], active["currency"]))
col2.metric("Cash disponible", fmt_money(cash, active["currency"]))
col3.metric("Valor actual", fmt_money(totals.get("total_value") or 0, active["currency"]))
col4.metric(
    "P&L total",
    fmt_money(totals.get("total_pnl") or 0, active["currency"]),
    delta=fmt_pct(totals.get("total_pnl_pct") or 0),
)

st.caption(
    f"**Riesgo:** {active['risk']}  ·  **Mercados:** {active['markets']}  ·  "
    f"**Moneda:** {active['currency']}  ·  **Creada:** {active['created_at']}"
)
if active.get("notes"):
    st.caption(f"📝 {active['notes']}")

# Botón eliminar (excepto Default id=1).
if active["id"] != 1:
    del_key = f"confirm_delete_{active['id']}"
    if st.session_state.get(del_key):
        st.warning(
            f"¿Seguro que quieres eliminar **{active['name']}**? "
            "Se borrarán sus posiciones y transacciones."
        )
        cdel1, cdel2 = st.columns(2)
        if cdel1.button("Sí, eliminar", type="primary", key="do_delete"):
            try:
                pf_svc.delete_portfolio(active["id"])
                st.session_state[del_key] = False
                st.session_state["active_portfolio_id"] = 1
                set_active_portfolio(1)
                st.toast("Cartera eliminada.", icon="🗑️")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        if cdel2.button("Cancelar", key="cancel_delete"):
            st.session_state[del_key] = False
            st.rerun()
    else:
        if st.button("🗑️ Eliminar cartera", key=f"btn_delete_{active['id']}"):
            st.session_state[del_key] = True
            st.rerun()
else:
    st.caption("La cartera Default (id=1) no puede eliminarse.")

st.divider()

# -----------------------------------------------------------------------------
# Formulario nueva cartera
# -----------------------------------------------------------------------------
with st.expander("➕ Nueva cartera"):
    with st.form("new_portfolio_form", clear_on_submit=True):
        name = st.text_input("Nombre", help="Debe ser único.")
        initial_cash = st.number_input(
            "Dinero inicial",
            min_value=100.0,
            step=100.0,
            value=10000.0,
            help="Este valor NO podrá modificarse después (ni desde el agente).",
        )
        risk = st.radio(
            "Riesgo",
            options=["conservador", "moderado", "agresivo"],
            index=1,
            horizontal=True,
        )
        markets = st.multiselect(
            "Mercados",
            options=["USA", "EUROPA", "ASIA", "GLOBAL", "ALL"],
            default=["USA", "EUROPA"],
        )
        currency = st.selectbox("Moneda", options=["USD", "EUR"], index=0)
        notes = st.text_area("Notas (opcional)", value="", height=80)
        submitted = st.form_submit_button("Crear cartera", type="primary")
        if submitted:
            try:
                new_p = pf_svc.create_portfolio(
                    name=name,
                    initial_cash=float(initial_cash),
                    risk=risk,
                    markets=markets,
                    currency=currency,
                    notes=notes.strip() or None,
                )
                st.toast(f"Cartera '{new_p['name']}' creada.", icon="🧺")
                st.session_state["active_portfolio_id"] = new_p["id"]
                set_active_portfolio(new_p["id"])
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo crear: {e}")

st.divider()

# -----------------------------------------------------------------------------
# Tabla con todas las carteras
# -----------------------------------------------------------------------------
st.subheader("📋 Todas las carteras")
rows = []
for p in all_portfolios:
    rows.append({
        "ID": p["id"],
        "Nombre": p["name"],
        "Cash inicial": round(p["initial_cash"], 2),
        "Cash disponible": round(pf_svc.cash_available(p["id"]), 2),
        "Riesgo": p["risk"],
        "Mercados": p["markets"],
        "Moneda": p["currency"],
        "Posiciones": pf_svc.count_positions(p["id"]),
        "Creada": p["created_at"],
    })
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)
