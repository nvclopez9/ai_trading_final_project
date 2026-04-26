"""Renderizado de la watchlist (tab dentro de Mi Cartera).

Función pública: ``render_watchlist_tab(portfolio_id)``. Muestra:
- Input + botón "Añadir".
- Tabla con cada ticker (nota, precio actual, cambio %, antigüedad).
- Botones "Eliminar" y "💬 Llevar al chat" por fila.
"""
from __future__ import annotations

import streamlit as st

from src.services import watchlist as wl
from src.ui.components import fmt_money, fmt_pct, color_for_delta


def render_watchlist_tab(portfolio_id: int) -> None:
    """Render principal del tab Watchlist."""
    st.subheader("👁️ Tickers en seguimiento")
    st.caption(
        "Marca tickers de interés sin comprarlos. Útil para guardar candidatos "
        "del Mercado o de las recomendaciones del agente."
    )

    # Form de alta.
    with st.form(key=f"wl_add_form_{portfolio_id}", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        with c1:
            new_ticker = st.text_input(
                "Ticker",
                placeholder="ej. NVDA",
                key=f"wl_new_ticker_{portfolio_id}",
            )
        with c2:
            new_note = st.text_input(
                "Nota (opcional)",
                placeholder="Por qué te interesa",
                key=f"wl_new_note_{portfolio_id}",
            )
        if st.form_submit_button("➕ Añadir", type="primary"):
            if new_ticker.strip():
                try:
                    wl.add(portfolio_id, new_ticker, new_note or None)
                    st.success(f"Añadido {new_ticker.strip().upper()} a la watchlist.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo añadir: {e}")
            else:
                st.warning("Introduce un ticker antes de añadir.")

    # Lista actual.
    with st.spinner("Cargando watchlist..."):
        items = wl.list_for(portfolio_id)

    if not items:
        st.info("Tu watchlist está vacía. Añade tickers que quieras vigilar.")
        return

    # Tabla con botones por fila.
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    header = st.columns([1.5, 2, 1.2, 1.2, 1.5, 1.2, 1])
    header[0].markdown("**Ticker**")
    header[1].markdown("**Nota**")
    header[2].markdown("**Precio**")
    header[3].markdown("**Δ día**")
    header[4].markdown("**Añadido**")
    header[5].markdown("**Chat**")
    header[6].markdown("**Quitar**")
    st.markdown(
        "<div style='border-top:1px solid #252D3D;margin:8px 0 12px 0;'></div>",
        unsafe_allow_html=True,
    )

    for it in items:
        cols = st.columns([1.5, 2, 1.2, 1.2, 1.5, 1.2, 1])
        cols[0].markdown(f"`{it['ticker']}`")
        cols[1].write(it["note"] or "—")
        cols[2].write(fmt_money(it["price"]) if it["price"] is not None else "—")
        chg = it["change_pct"]
        if chg is not None:
            color = color_for_delta(chg)
            cols[3].markdown(
                f"<span style='color:{color};'>{fmt_pct(chg)}</span>",
                unsafe_allow_html=True,
            )
        else:
            cols[3].write("—")
        cols[4].caption(it["added_at"][:10])
        if cols[5].button("💬", key=f"wl_chat_{it['id']}", help="Pedir al agente que lo analice"):
            st.session_state["active_ticker"] = it["ticker"]
            st.session_state["prefill_prompt"] = (
                f"Analiza {it['ticker']} considerando incluirlo en mi cartera: "
                f"usa get_ticker_status, get_fundamentals y get_ticker_news. "
                f"Recuérdame también la nota que tengo guardada: '{it['note'] or 'sin nota'}'."
            )
            st.switch_page("pages/1_Chat.py")
        if cols[6].button("🗑️", key=f"wl_del_{it['id']}", help="Eliminar de la watchlist"):
            try:
                wl.remove(portfolio_id, it["ticker"])
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar: {e}")
