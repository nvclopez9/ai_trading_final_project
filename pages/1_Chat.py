"""Página Chat: conversación con el agente.

Patrón oficial de Streamlit para chats:
    1) Renderizar SIEMPRE el historial completo desde session_state.
    2) Cuando entra un input nuevo (chat_input o prefill_prompt), procesarlo:
       - append + render inline del mensaje del usuario,
       - invocar al agente,
       - append + render inline de la respuesta del asistente.
    3) En el siguiente rerun, todo eso ya forma parte del historial y se
       redibuja por el loop. No hay doble render porque la nueva entrada se
       procesa solo en el run en que se recibe.

Notas didácticas:
- No usamos ``placeholder = st.empty()`` para evitar parpadeos cuando el
  agente tarda; ``st.chat_message`` ya gestiona la burbuja y el spinner
  vive dentro de ella.
- ``render_suggestions_panel`` va al final del script para que el catálogo
  no rompa el flujo conversacional. Como el ``st.chat_input`` se ancla al
  fondo de la ventana, el panel queda justo encima del input.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.services import portfolios as pf_svc
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.chat_suggestions import render_suggestions_panel

st.set_page_config(page_title="Chat · Bot de Inversiones", page_icon="💬")
st.title("💬 Chat con el agente")

agent = get_agent()
session_id = ensure_session_id()


# -----------------------------------------------------------------------------
# Selector de cartera activa con CHIPS (no chat). El usuario puede cambiar
# de cartera sin salir del chat: las próximas tools (portfolio_buy, etc.)
# operarán sobre la cartera marcada aquí.
# -----------------------------------------------------------------------------
def _render_portfolio_chips() -> None:
    """Pinta una fila de chips/botones, uno por cartera. Resalta la activa."""
    try:
        portfolios_list = pf_svc.list_portfolios()
    except Exception:
        portfolios_list = []
    if not portfolios_list:
        return

    ids = [p["id"] for p in portfolios_list]
    current = st.session_state.get("active_portfolio_id", ids[0])
    if current not in ids:
        current = ids[0]
        st.session_state["active_portfolio_id"] = current
    set_active_portfolio(current)

    st.caption("Cartera activa")
    # Una columna por cartera, con un máximo razonable por fila para no romper
    # el layout si el usuario tiene muchas carteras.
    n = len(portfolios_list)
    per_row = min(n, 5)
    cols = st.columns(per_row)
    for idx, p in enumerate(portfolios_list):
        col = cols[idx % per_row]
        is_active = p["id"] == current
        # Chip activo se renderiza como botón primary; los demás secondary.
        label = f"{'✅ ' if is_active else ''}#{p['id']} · {p['name']}"
        if col.button(
            label,
            key=f"chat_portfolio_chip_{p['id']}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
            help=f"Riesgo: {p['risk']} · Mercados: {p['markets']}",
        ):
            if not is_active:
                st.session_state["active_portfolio_id"] = p["id"]
                set_active_portfolio(p["id"])
                st.toast(f"Cartera activa: {p['name']}", icon="🧺")
                st.rerun()


_render_portfolio_chips()

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
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})


# 1) Render del historial completo.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
render_suggestions_panel(prefill_state_key="prefill_prompt")
