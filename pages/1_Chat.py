"""Página Chat: conversación con el agente.

Patrón oficial de Streamlit para chats:
    1) Renderizar SIEMPRE el historial completo desde session_state.
    2) Cuando entra un input nuevo (chat_input o prefill_prompt), procesarlo:
       - append + render inline del mensaje del usuario,
       - invocar al agente,
       - append + render inline de la respuesta del asistente.
    3) En el siguiente rerun, todo eso ya forma parte del historial y se
       redibuja por el loop.

Layout dark fintech: sugerencias rápidas arriba como píldoras horizontales,
chat a ancho completo, selector de cartera y guía de uso en el sidebar nativo.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.chat_suggestions import render_suggestions_panel
from src.ui.components import (
    COLOR_BORDER,
    COLOR_DIM,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    hero,
    inject_app_styles,
    section_title,
)

st.set_page_config(page_title="Chat · Bot de Inversiones", page_icon="💬", layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

# ---- Sidebar: cartera activa + guía de uso --------------------------------
with st.sidebar:
    st.markdown(
        f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.1em;"
        f"color:{COLOR_MUTED};font-weight:500;margin-bottom:8px;'>Cartera activa</div>",
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

    st.markdown(
        f"""
        <div style="background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};
                    border-radius:12px;padding:14px 16px;margin-top:18px;">
          <div style='font-size:11px;text-transform:uppercase;letter-spacing:0.1em;
                      color:{COLOR_MUTED};font-weight:500;margin-bottom:8px;'>Cómo usar</div>
          <ul style='margin:0;padding-left:18px;color:{COLOR_TEXT};font-size:12px;
                     line-height:1.6;'>
            <li>Pide cotizaciones: <em>"precio de TSLA"</em></li>
            <li>Opera tu cartera: <em>"compra 5 NVDA"</em></li>
            <li>Pide explicaciones: <em>"qué es un ETF"</em></li>
            <li>Compara: <em>"AAPL vs MSFT"</em></li>
          </ul>
          <div style='color:{COLOR_DIM};font-size:11px;margin-top:10px;'>
            La cartera seleccionada arriba es la que usarán las operaciones.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---- Hero ------------------------------------------------------------------
hero(
    "Chat",
    "Pregúntale al agente sobre precios, noticias, conceptos o tu cartera.",
)

agent = get_agent()
session_id = ensure_session_id()


# Historial visual del chat (independiente de la memoria interna del agente,
# que vive en RunnableWithMessageHistory indexada por session_id).
if "messages" not in st.session_state:
    st.session_state.messages = []


def _invoke_agent(user_input: str) -> str:
    """Llama al agente y devuelve la respuesta como string. Captura errores."""
    try:
        result = agent.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}},
        )
        answer = result.get("output") if isinstance(result, dict) else str(result)
        return answer or "No he podido generar una respuesta."
    except Exception as e:
        return (
            "⚠️ Se ha producido un error al consultar al agente. "
            "Verifica que el LLM esté disponible (Ollama corriendo o "
            f"OPENROUTER_API_KEY válida).\n\nDetalle: `{e}`"
        )


def _escape_dollars(text: str) -> str:
    # Why: Streamlit interpreta `$...$` como LaTeX y rompe cifras como "$10 000".
    return text.replace("$", "\\$") if isinstance(text, str) else text


def _handle_user_message(user_input: str) -> None:
    """Procesa un input nuevo: lo añade al historial, lo pinta inline,
    invoca al agente y pinta la respuesta.

    Patrón "render inline en este rerun": las dos burbujas se dibujan después
    del loop de historial, lo que las coloca visualmente al final de la
    conversación. En el siguiente rerun ya forman parte de ``messages`` y
    el loop las redibuja en su sitio sin duplicarse.
    """
    # Mensaje del usuario.
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Mensaje del asistente.
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            answer = _invoke_agent(user_input)
        st.markdown(_escape_dollars(answer))
    st.session_state.messages.append({"role": "assistant", "content": answer})


# ---- Sugerencias rápidas (siempre arriba) ---------------------------------
quick_prompts = [
    "¿Cómo está AAPL?",
    "Resumen de mi cartera",
    "Noticias de NVDA",
    "Explícame qué es un ETF",
]
cols = st.columns(len(quick_prompts))
for col, qp in zip(cols, quick_prompts):
    with col:
        if st.button(qp, key=f"chat_quick_{qp}", use_container_width=True):
            st.session_state["pending_prompt"] = qp
            st.rerun()

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ---- Chat (ancho completo) ------------------------------------------------
# 1) Render del historial completo.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if msg["role"] == "assistant":
            content = _escape_dollars(content)
        st.markdown(content)

# 2) Consumir prompts pendientes (procedentes del Home, Mercado, Noticias o
#    de los chips de sugerencias). Solo uno por rerun: priorizamos
#    ``pending_prompt`` (uso interno) sobre ``prefill_prompt`` (UI).
pending = st.session_state.pop("pending_prompt", None) or st.session_state.pop("prefill_prompt", None)
if pending:
    _handle_user_message(pending)

# 3) Input del usuario. ``st.chat_input`` se ancla al fondo de la ventana
#    independientemente de su posición en el script.
user_input = st.chat_input("Pregunta sobre un ticker, p. ej. '¿Cómo está AAPL?'")
if user_input:
    _handle_user_message(user_input)

# 4) Catálogo de sugerencias (60+ prompts). Va al final para no fragmentar
#    el flujo: el expander queda plegado por defecto cuando ya hay charla.
section_title("Catálogo de prompts", "Explora todo lo que el agente sabe hacer")
render_suggestions_panel(prefill_state_key="prefill_prompt")
