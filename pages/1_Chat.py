"""Página Chat: conversación con el agente.

Reutiliza el mismo flujo que tenía ``app.py`` antes de la migración multipage:
historial visual en ``st.session_state.messages``, chips de sugerencia cuando
está vacío, procesamiento vía ``_process_user_message`` centralizado, y
captura de errores con mensaje amable.
"""
import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id

st.set_page_config(page_title="Chat · Bot de Inversiones", page_icon="💬")
st.title("💬 Chat con el agente")

agent = get_agent()
session_id = ensure_session_id()

if "messages" not in st.session_state:
    st.session_state.messages = []


def _process_user_message(user_input: str) -> None:
    """Añade el mensaje al historial, invoca al agente y pinta la respuesta."""
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            with st.spinner("Pensando..."):
                result = agent.invoke(
                    {"input": user_input},
                    config={"configurable": {"session_id": session_id}},
                )
            answer = result.get("output") if isinstance(result, dict) else str(result)
            if not answer:
                answer = "No he podido generar una respuesta."
        except Exception as e:
            answer = (
                "Se ha producido un error al consultar al agente. "
                "Verifica que Ollama esté en ejecución y el modelo esté descargado.\n\n"
                f"Detalle: {e}"
            )
        placeholder.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})


# Chips de sugerencia sólo visibles con el chat vacío.
if not st.session_state.messages:
    st.markdown("**Prueba con una de estas preguntas:**")
    suggestions = [
        "¿Cómo está AAPL?",
        "¿Qué es el P/E ratio?",
        "Dame los tickers más calientes",
        "Muéstrame mi cartera",
    ]
    cols = st.columns(len(suggestions))
    for col, text in zip(cols, suggestions):
        with col:
            if st.button(text, key=f"chip_{text}", use_container_width=True):
                st.session_state.pending_prompt = text
                st.rerun()

# Re-render del historial.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Consumir prompts pendientes: pueden venir del chip, del Home o de la
# pestaña "Explícame" en Mercado (que guardan en prefill_prompt / pending_prompt).
pending = st.session_state.pop("pending_prompt", None) or st.session_state.pop("prefill_prompt", None)
if pending:
    _process_user_message(pending)

# Input de chat anclado al fondo.
user_input = st.chat_input("Pregunta sobre un ticker, p. ej. '¿Cómo está AAPL?'")
if user_input:
    _process_user_message(user_input)
