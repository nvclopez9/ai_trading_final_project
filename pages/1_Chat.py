"""Página Chat: conversación con el agente.

Layout coherente con el resto de la app (sidebar nativo de Streamlit como
navegación). Lateral izquierda: cartera activa, perfil, cómo usar, acciones
recientes. Cuerpo: hero + chat + sugerencias + catálogo de prompts.
"""
from __future__ import annotations

import re
import time

import streamlit as st

from src.agent.agent_builder import get_session_history
from src.agent.singleton import ensure_session_id, get_agent, rebuild_agent
from src.agent.slash_commands import execute_pending_trade, try_handle_slash
from src.agent.streamlit_callbacks import StreamlitToolCallbackHandler
from src.agent.verifier import verify_response
from src.services import portfolios as pf_svc
from src.services.preferences import get_preferences, update_preferences
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.chat_suggestions import render_suggestions_panel
from src.ui.components import (
    COLOR_BORDER,
    COLOR_DIM,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_WARNING,
    _MONO,
    footer_disclaimer,
    hero,
    inject_app_styles,
    section_title,
)

st.set_page_config(
    page_title="Chat · Bot de Inversiones",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_app_styles()


# ─── Sidebar: cartera, perfil, ayuda, acciones recientes ────────────────────
with st.sidebar:
    st.markdown(
        "<div class='section-eyebrow'>Cartera activa</div>",
        unsafe_allow_html=True,
    )
    try:
        portfolios_list = pf_svc.list_portfolios()
    except Exception:
        portfolios_list = []
    if portfolios_list:
        ids = [p["id"] for p in portfolios_list]
        names_by_id = {p["id"]: p["name"] for p in portfolios_list}
        current = st.session_state.get("active_portfolio_id", ids[0])
        if current not in ids:
            current = ids[0]
        sel = st.selectbox(
            "Cartera activa",
            options=ids,
            format_func=lambda i: f"#{i} · {names_by_id[i]}",
            index=ids.index(current),
            key="chat_active_portfolio_selector",
            label_visibility="collapsed",
        )
        if sel != st.session_state.get("active_portfolio_id"):
            st.session_state["active_portfolio_id"] = sel
            set_active_portfolio(sel)
            st.toast(f"Cartera activa: {names_by_id[sel]}", icon="🧺")
            st.rerun()
        else:
            st.session_state["active_portfolio_id"] = sel
            set_active_portfolio(sel)
    else:
        st.caption("No hay carteras disponibles.")

    _prefs = get_preferences()
    with st.expander(
        f"Perfil · {_prefs['risk_profile']} / {_prefs['time_horizon']}"
        + (" ✓" if _prefs["onboarded"] else ""),
        expanded=False,
    ):
        with st.form("prefs_form_chat"):
            risk = st.selectbox(
                "Riesgo", ["conservador", "moderado", "agresivo"],
                index=["conservador", "moderado", "agresivo"].index(_prefs["risk_profile"]),
            )
            horizon = st.selectbox(
                "Horizonte", ["corto", "medio", "largo"],
                index=["corto", "medio", "largo"].index(_prefs["time_horizon"]),
                help="Corto = días/semanas, Medio = meses, Largo = años.",
            )
            sectors = st.text_input(
                "Sectores favoritos",
                value=", ".join(_prefs["favorite_sectors"]),
                placeholder="tech, salud",
            )
            excluded = st.text_input(
                "Tickers a evitar",
                value=", ".join(_prefs["excluded_tickers"]),
                placeholder="MO, XOM",
            )
            if st.form_submit_button("Guardar"):
                update_preferences(
                    risk_profile=risk,
                    time_horizon=horizon,
                    favorite_sectors=[s.strip() for s in sectors.split(",") if s.strip()],
                    excluded_tickers=[t.strip().upper() for t in excluded.split(",") if t.strip()],
                )
                rebuild_agent()
                st.toast("Preferencias guardadas.", icon="✅")
                st.rerun()

    st.markdown(
        f"""
        <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
                    border-radius:12px;padding:14px 16px;margin-top:14px;">
          <div class='section-eyebrow' style='margin-bottom:8px;'>Cómo usar</div>
          <ul style='margin:0;padding-left:18px;color:{COLOR_TEXT};font-size:12px;
                     line-height:1.6;'>
            <li>Cotizaciones: <em>"precio de TSLA"</em></li>
            <li>Operar: <em>"compra 5 NVDA"</em></li>
            <li>Comparar: <em>"AAPL vs MSFT"</em></li>
            <li>Slash: <code>/precio AAPL</code>, <code>/cartera</code></li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    recent = st.session_state.get("recent_tool_calls", [])
    if recent:
        st.markdown(
            "<div class='section-eyebrow' style='margin:18px 0 8px 0;'>Acciones recientes</div>",
            unsafe_allow_html=True,
        )
        rows_html = ""
        for r in reversed(recent[-5:]):
            tool = r.get("tool", "?")
            args = r.get("args_summary", "")
            ts = r.get("ts", "")
            rows_html += (
                f"<div style='display:flex;justify-content:space-between;gap:6px;"
                f"font-family:{_MONO};font-size:11px;padding:6px 0;"
                f"border-bottom:1px solid {COLOR_BORDER};'>"
                f"<span style='color:{COLOR_TEXT};white-space:nowrap;overflow:hidden;"
                f"text-overflow:ellipsis;flex:0 0 auto;max-width:120px;'>{tool}</span>"
                f"<span style='color:{COLOR_MUTED};white-space:nowrap;overflow:hidden;"
                f"text-overflow:ellipsis;flex:1 1 auto;'>{args}</span>"
                f"<span style='color:{COLOR_DIM};flex:0 0 auto;'>{ts}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
            f"border-radius:12px;padding:6px 14px;'>{rows_html}</div>",
            unsafe_allow_html=True,
        )


# ─── Hero ───────────────────────────────────────────────────────────────────
hero("Chat", "Pregúntale al agente sobre precios, noticias, conceptos o tu cartera.")

agent = get_agent()
session_id = ensure_session_id()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "follow_ups" not in st.session_state:
    st.session_state.follow_ups = []
if "pending_trade" not in st.session_state:
    st.session_state.pending_trade = None


# ─── Onboarding (banner sólo si no hay perfil) ─────────────────────────────
if not get_preferences()["onboarded"]:
    st.markdown(
        f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
        f"border-radius:12px;padding:14px 18px;margin-bottom:14px;'>"
        f"<div style='color:{COLOR_TEXT};font-weight:600;'>Configura tu perfil en 10s</div>"
        f"<div style='color:{COLOR_MUTED};font-size:13px;margin-top:4px;'>"
        f"El agente personaliza recomendaciones según tu riesgo y horizonte. "
        f"Puedes cambiarlo después en el panel lateral."
        f"</div></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, _ = st.columns([1, 1, 1, 3])
    if c1.button("Conservador / largo", key="onboard_cons_largo"):
        update_preferences(risk_profile="conservador", time_horizon="largo")
        rebuild_agent()
        st.rerun()
    if c2.button("Moderado / medio", key="onboard_mod_medio"):
        update_preferences(risk_profile="moderado", time_horizon="medio")
        rebuild_agent()
        st.rerun()
    if c3.button("Agresivo / corto", key="onboard_agr_corto"):
        update_preferences(risk_profile="agresivo", time_horizon="corto")
        rebuild_agent()
        st.rerun()


# ─── Helpers ────────────────────────────────────────────────────────────────
def _escape_dollars(text: str) -> str:
    return text.replace("$", "\\$") if isinstance(text, str) else text


_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")
_STOPWORD_TICKERS = {"USD", "EUR", "ETF", "AI", "IA", "P", "E", "PE", "S", "ES", "BCE", "FED", "PIB"}


def _suggest_followups(response_text: str, tool_calls: list[dict]) -> list[str]:
    """Genera 2-3 prompts de seguimiento basados en tools llamadas y texto."""
    sugs: list[str] = []
    tickers: list[str] = []
    for c in tool_calls or []:
        for t in _TICKER_RE.findall(c.get("args", "")):
            if t not in tickers and t not in _STOPWORD_TICKERS:
                tickers.append(t)
    if not tickers:
        for t in _TICKER_RE.findall(response_text or ""):
            if t in tickers or t in _STOPWORD_TICKERS:
                continue
            tickers.append(t)
            if len(tickers) >= 2:
                break

    if tickers:
        t = tickers[0]
        sugs.append(f"Ver gráfico de {t}")
        sugs.append(f"Noticias de {t}")
        if len(tickers) > 1:
            sugs.append(f"Comparar {tickers[0]} vs {tickers[1]}")
        else:
            sugs.append(f"¿Es buen momento para comprar {t}?")
    elif any(w in (response_text or "").lower() for w in ("cartera", "posicion", "p&l", "pnl")):
        sugs = ["Resumen de mi cartera", "¿Debería rebalancear?", "Top movers de hoy"]
    elif any(w in (response_text or "").lower() for w in (" es un", " es una", "ratio", "índice", "indice")):
        sugs = ["Explica con un ejemplo", "Profundiza un poco más", "¿Cómo se aplica en la práctica?"]
    else:
        sugs = ["¿Qué más debería saber?", "Resumen de mi cartera"]
    return sugs[:3]


def _verifier_caption(verdict: dict) -> str | None:
    if not verdict or verdict.get("total_unverified", 0) == 0:
        return None
    n = verdict["total_unverified"]
    return (
        f"<div style='margin-top:8px;color:{COLOR_WARNING};font-size:11px;"
        f"font-family:{_MONO};'>⚠ {n} cifra{'s' if n != 1 else ''} sin "
        f"respaldo en tools — trátala{'s' if n != 1 else ''} con cuidado.</div>"
    )


def _stream_agent(user_input: str, indicator_placeholder, text_placeholder) -> tuple[str, list[dict]]:
    handler = StreamlitToolCallbackHandler(indicator_placeholder)
    answer = ""
    try:
        for chunk in agent.stream(
            {"input": user_input},
            config={
                "configurable": {"session_id": session_id},
                "callbacks": [handler],
            },
        ):
            if isinstance(chunk, dict) and "output" in chunk:
                piece = chunk["output"]
                if isinstance(piece, str):
                    answer = piece
                    text_placeholder.markdown(_escape_dollars(answer))
        if not answer:
            result = agent.invoke(
                {"input": user_input},
                config={
                    "configurable": {"session_id": session_id},
                    "callbacks": [handler],
                },
            )
            answer = result.get("output") if isinstance(result, dict) else str(result)
            text_placeholder.markdown(_escape_dollars(answer or ""))
    except Exception as e:
        answer = (
            "⚠️ Se ha producido un error al consultar al agente. "
            "Verifica que el LLM esté disponible (Ollama corriendo o "
            f"OPENROUTER_API_KEY válida).\n\nDetalle: `{e}`"
        )
        text_placeholder.markdown(answer)
    return answer or "No he podido generar una respuesta.", handler.get_tool_calls()


def _render_slash_result(result: dict) -> None:
    with st.chat_message("assistant"):
        st.markdown(result["text"])
        if result.get("chart") is not None:
            try:
                st.plotly_chart(result["chart"], use_container_width=True)
            except Exception:
                pass
        if result.get("is_pending_buy") or result.get("is_pending_sell"):
            st.session_state.pending_trade = result["pending_payload"]
        if result.get("clear_history"):
            st.session_state.messages = []
            st.session_state.follow_ups = []
            st.session_state.pending_trade = None


def _handle_user_message(user_input: str) -> None:
    if user_input.strip().startswith("/"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        active_pid = st.session_state.get("active_portfolio_id", 1)
        result = try_handle_slash(user_input, session_id, portfolio_id=active_pid)
        if result is not None:
            _render_slash_result(result)
            st.session_state.messages.append({"role": "assistant", "content": result["text"]})
            st.session_state.follow_ups = []
            return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        text_ph = st.empty()
        indicator_ph = st.empty()
        with st.spinner("Pensando..."):
            t0 = time.monotonic()
            answer, tool_calls = _stream_agent(user_input, indicator_ph, text_ph)
            elapsed = time.monotonic() - t0
        text_ph.markdown(_escape_dollars(answer))

        steps = [(type("A", (), {"tool": c["tool"]})(), c.get("args", "")) for c in tool_calls]
        verdict = verify_response(answer, steps)
        cap = _verifier_caption(verdict)
        if cap:
            st.markdown(cap, unsafe_allow_html=True)

        st.markdown(
            f"<div style='color:{COLOR_DIM};font-size:11px;font-family:{_MONO};margin-top:6px;'>"
            f"{len(tool_calls)} tool{'s' if len(tool_calls) != 1 else ''} · {elapsed:.1f}s</div>",
            unsafe_allow_html=True,
        )

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.follow_ups = _suggest_followups(answer, tool_calls)


# ─── Cuerpo principal del chat (ancho completo; lateral va en sidebar) ─────
quick_prompts = [
    "¿Cómo está AAPL?",
    "Resumen de mi cartera",
    "Noticias de NVDA",
    "Explícame qué es un ETF",
]
qcols = st.columns(len(quick_prompts))
for col, qp in zip(qcols, quick_prompts):
    with col:
        if st.button(qp, key=f"chat_quick_{qp}", use_container_width=True):
            st.session_state["pending_prompt"] = qp
            st.rerun()

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# Render del historial
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if msg["role"] == "assistant":
            content = _escape_dollars(content)
        st.markdown(content)

# HITL para slash /comprar /vender
if st.session_state.pending_trade is not None:
    payload = st.session_state.pending_trade
    side = payload.get("side", "BUY")
    label = "Confirmar compra" if side == "BUY" else "Confirmar venta"
    c1, c2, _spacer = st.columns([1, 1, 4])
    if c1.button(label, type="primary", key="confirm_pending_trade"):
        active_pid = st.session_state.get("active_portfolio_id", 1)
        result_msg = execute_pending_trade(payload, active_pid)
        st.session_state.messages.append({"role": "assistant", "content": result_msg})
        try:
            get_session_history(session_id).add_ai_message(result_msg)
        except Exception:
            pass
        st.session_state.pending_trade = None
        st.rerun()
    if c2.button("Cancelar", key="cancel_pending_trade"):
        st.session_state.messages.append({"role": "assistant", "content": "Operación cancelada."})
        st.session_state.pending_trade = None
        st.rerun()

# Follow-up chips
if st.session_state.follow_ups and st.session_state.pending_trade is None:
    fu_cols = st.columns(len(st.session_state.follow_ups))
    for i, (col, sug) in enumerate(zip(fu_cols, st.session_state.follow_ups)):
        with col:
            if st.button(sug, key=f"followup_{i}_{sug[:30]}", use_container_width=True):
                st.session_state["pending_prompt"] = sug
                st.session_state.follow_ups = []
                st.rerun()

# Procesar prompt pendiente o input nuevo
pending = st.session_state.pop("pending_prompt", None) or st.session_state.pop("prefill_prompt", None)
if pending:
    _handle_user_message(pending)

user_input = st.chat_input("Pregunta sobre un ticker, p. ej. '¿Cómo está AAPL?' o /ayuda")
if user_input:
    _handle_user_message(user_input)


# ─── Catálogo de prompts (al final, plegado) ────────────────────────────────
section_title("Catálogo de prompts", "Explora todo lo que el agente sabe hacer")
render_suggestions_panel(prefill_state_key="prefill_prompt")

footer_disclaimer()
