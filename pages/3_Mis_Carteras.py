"""Carteras — gestión multi-cartera.

Permite seleccionar la cartera activa, ver su detalle, crearla, reiniciarla
o eliminarla, y listar todas las carteras existentes en formato grid.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolio as pf_service
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.components import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_DIM,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    fmt_money,
    footer_disclaimer,
    hero,
    inject_app_styles,
    section_title,
    sidebar_kpi,
    stat_strip,
    stat_tile,
)

st.set_page_config(page_title="Carteras · Bot de Inversiones", page_icon="🧺", layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

_ = get_agent()
_ = ensure_session_id()

hero(
    "Mis carteras",
    "Gestiona varias carteras simuladas con perfiles de riesgo y mercados distintos.",
)

# -----------------------------------------------------------------------------
# Selector de cartera activa
# -----------------------------------------------------------------------------
all_portfolios = pf_svc.list_portfolios()
if not all_portfolios:
    st.error("No hay carteras en la base de datos. Reinicia la app para que se cree la Default.")
    st.stop()


# ---- Sidebar contextual: agregado de TODAS las carteras ------------------
with st.sidebar:
    st.markdown("<div class='section-eyebrow'>Agregado total</div>", unsafe_allow_html=True)
    _agg_value = 0.0
    _agg_pnl = 0.0
    _agg_cash = 0.0
    _agg_cost = 0.0
    for _p in all_portfolios:
        try:
            _t = pf_service.get_portfolio_value(portfolio_id=_p["id"])
            _agg_value += _t.get("total_value") or 0
            _agg_pnl += _t.get("total_pnl") or 0
            _agg_cost += _t.get("total_cost") or 0
            _agg_cash += pf_svc.cash_available(_p["id"]) or 0
        except Exception:
            continue
    _agg_pct = (_agg_pnl / _agg_cost * 100) if _agg_cost else 0
    st.markdown(sidebar_kpi("Carteras", str(len(all_portfolios))),
                unsafe_allow_html=True)
    st.markdown(sidebar_kpi("Patrimonio total", fmt_money(_agg_value + _agg_cash)),
                unsafe_allow_html=True)
    st.markdown(sidebar_kpi("P&L agregado", fmt_money(_agg_pnl), delta=_agg_pct),
                unsafe_allow_html=True)
    st.markdown(sidebar_kpi("Cash agregado", fmt_money(_agg_cash)),
                unsafe_allow_html=True)

    st.markdown("<div class='section-eyebrow' style='margin-top:14px;'>Atajos</div>",
                unsafe_allow_html=True)
    if st.button("Ver cartera activa →", key="mis_sb_active", use_container_width=True):
        st.switch_page("pages/2_Mi_Cartera.py")

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
    key="cartera_page_active",
)
if selected_id != st.session_state.get("active_portfolio_id"):
    st.session_state["active_portfolio_id"] = selected_id
    set_active_portfolio(selected_id)
    st.toast(f"Cartera activa: {names_by_id[selected_id]}", icon="✅")
else:
    set_active_portfolio(selected_id)

active = pf_svc.get_portfolio(selected_id)
totals = pf_service.get_portfolio_value(portfolio_id=selected_id)
cash = pf_svc.cash_available(selected_id)

# -----------------------------------------------------------------------------
# Tarjeta detalle de la cartera activa
# -----------------------------------------------------------------------------
section_title(active["name"], subtitle=f"ID #{active['id']} · perfil {active['risk']}")

# Pill-card con metadatos compactos.
notes_block = ""
if active.get("notes"):
    notes_block = (
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-top:10px;"
        f"padding-top:10px;border-top:1px solid {COLOR_BORDER};'>"
        f"{active['notes']}</div>"
    )

st.markdown(
    f"""
    <div class='pill-card' style='padding:18px 20px;margin-bottom:14px;'>
      <div style='display:flex;flex-wrap:wrap;gap:18px 28px;align-items:center;'>
        <div>
          <div style='color:{COLOR_DIM};font-size:11px;text-transform:uppercase;letter-spacing:0.1em;'>Riesgo</div>
          <div style='color:{COLOR_TEXT};font-weight:600;font-size:14px;margin-top:2px;'>{active['risk']}</div>
        </div>
        <div>
          <div style='color:{COLOR_DIM};font-size:11px;text-transform:uppercase;letter-spacing:0.1em;'>Mercados</div>
          <div style='color:{COLOR_TEXT};font-weight:600;font-size:14px;margin-top:2px;'>{active['markets']}</div>
        </div>
        <div>
          <div style='color:{COLOR_DIM};font-size:11px;text-transform:uppercase;letter-spacing:0.1em;'>Moneda</div>
          <div style='color:{COLOR_TEXT};font-weight:600;font-size:14px;margin-top:2px;'>{active['currency']}</div>
        </div>
        <div>
          <div style='color:{COLOR_DIM};font-size:11px;text-transform:uppercase;letter-spacing:0.1em;'>Creada</div>
          <div style='color:{COLOR_TEXT};font-weight:600;font-size:14px;margin-top:2px;'>{active['created_at']}</div>
        </div>
      </div>
      {notes_block}
    </div>
    """,
    unsafe_allow_html=True,
)

stat_strip([
    stat_tile("Cash inicial", fmt_money(active["initial_cash"], active["currency"])),
    stat_tile("Cash disponible", fmt_money(cash, active["currency"])),
    stat_tile("Valor actual", fmt_money(totals.get("total_value") or 0, active["currency"])),
    stat_tile(
        "P&L total",
        fmt_money(totals.get("total_pnl") or 0, active["currency"]),
        delta=totals.get("total_pnl_pct") or 0,
    ),
])

# Acciones destructivas con confirmación de dos pasos.
reset_key = f"confirm_reset_{active['id']}"
del_key = f"confirm_delete_{active['id']}"

st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

if st.session_state.get(reset_key):
    st.warning(
        f"⚠️ ¿Seguro que quieres **reiniciar {active['name']}**? Se borrarán "
        "todas sus posiciones, transacciones y watchlist. La cartera "
        f"vuelve a {fmt_money(active['initial_cash'], active['currency'])} de cash. "
        "Riesgo y mercados se mantienen."
    )
    crst1, crst2 = st.columns(2)
    if crst1.button("Sí, reiniciar", type="primary", key="do_reset"):
        try:
            pf_svc.reset_portfolio(active["id"])
            st.session_state[reset_key] = False
            st.toast("Cartera reiniciada.", icon="🔄")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
    if crst2.button("Cancelar", key="cancel_reset"):
        st.session_state[reset_key] = False
        st.rerun()
elif st.session_state.get(del_key):
    st.warning(
        f"⚠️ ¿Seguro que quieres **eliminar {active['name']}**? "
        "Se borrarán sus posiciones, transacciones y watchlist."
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
    if active["id"] == 1:
        ca1, _ca2 = st.columns([1, 3])
        if ca1.button("Reiniciar cartera", key=f"btn_reset_{active['id']}"):
            st.session_state[reset_key] = True
            st.rerun()
        st.caption("La cartera Default (id=1) puede reiniciarse pero no eliminarse.")
    else:
        ca1, ca2, _ca3 = st.columns([1, 1, 2])
        if ca1.button("Reiniciar cartera", key=f"btn_reset_{active['id']}"):
            st.session_state[reset_key] = True
            st.rerun()
        if ca2.button("Eliminar cartera", key=f"btn_delete_{active['id']}"):
            st.session_state[del_key] = True
            st.rerun()

# -----------------------------------------------------------------------------
# Formulario nueva cartera
# -----------------------------------------------------------------------------
section_title("Crear cartera", subtitle="Define el capital inicial, el perfil de riesgo y los mercados objetivo.")

with st.expander("Nueva cartera"):
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

# -----------------------------------------------------------------------------
# Grid con todas las carteras
# -----------------------------------------------------------------------------
section_title("Todas las carteras", subtitle=f"{len(all_portfolios)} carteras en total.")


def _portfolio_card_html(p: dict, is_active: bool) -> str:
    cash_avail = pf_svc.cash_available(p["id"])
    n_pos = pf_svc.count_positions(p["id"])
    border = COLOR_ACCENT if is_active else COLOR_BORDER
    badge_active = (
        f"<span style='font-family:Inter,sans-serif;font-size:10px;font-weight:700;"
        f"color:{COLOR_ACCENT};background:{COLOR_ACCENT}1A;border:1px solid {COLOR_ACCENT}40;"
        f"padding:2px 8px;border-radius:4px;letter-spacing:0.06em;text-transform:uppercase;'>activa</span>"
        if is_active else ""
    )
    risk_chip = (
        f"<span style='font-family:Inter,sans-serif;font-size:11px;font-weight:600;"
        f"color:{COLOR_MUTED};background:{COLOR_BORDER};"
        f"padding:2px 8px;border-radius:4px;'>{p['risk']}</span>"
    )
    id_chip = (
        f"<span style='font-family:JetBrains Mono,monospace;font-size:11px;font-weight:600;"
        f"color:{COLOR_DIM};'>#{p['id']}</span>"
    )

    def _mini(label: str, value: str) -> str:
        return (
            f"<div style='flex:1;'>"
            f"<div style='color:{COLOR_DIM};font-size:10px;text-transform:uppercase;"
            f"letter-spacing:0.1em;margin-bottom:4px;'>{label}</div>"
            f"<div style='color:{COLOR_TEXT};font-family:JetBrains Mono,monospace;"
            f"font-size:14px;font-weight:600;'>{value}</div>"
            f"</div>"
        )

    mini_stats = (
        f"<div style='display:flex;gap:18px;margin-top:14px;'>"
        f"{_mini('Cash inicial', fmt_money(p['initial_cash'], p['currency']))}"
        f"{_mini('Disponible', fmt_money(cash_avail, p['currency']))}"
        f"{_mini('Posiciones', str(n_pos))}"
        f"</div>"
    )

    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid {border};"
        f"border-radius:14px;padding:18px 20px;height:100%;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:10px;'>"
        f"<div>"
        f"<div style='color:{COLOR_TEXT};font-size:18px;font-weight:700;letter-spacing:-0.01em;'>"
        f"{p['name']}</div>"
        f"<div style='display:flex;gap:8px;align-items:center;margin-top:6px;'>"
        f"{id_chip}{risk_chip}"
        f"</div>"
        f"</div>"
        f"{badge_active}"
        f"</div>"
        f"{mini_stats}"
        f"<div style='margin-top:14px;color:{COLOR_MUTED};font-size:12px;'>"
        f"Mercados: <span style='color:{COLOR_TEXT};'>{p['markets']}</span> · "
        f"Moneda: <span style='color:{COLOR_TEXT};'>{p['currency']}</span>"
        f"</div>"
        f"</div>"
    )


# Pinta de 2 en 2
for i in range(0, len(all_portfolios), 2):
    cols = st.columns(2)
    for col, p in zip(cols, all_portfolios[i:i + 2]):
        col.markdown(
            _portfolio_card_html(p, is_active=(p["id"] == selected_id)),
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

footer_disclaimer()
