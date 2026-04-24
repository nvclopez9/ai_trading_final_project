"""Singleton del agente + helpers de sesión.

Centraliza la inicialización del agente (build + init_db) bajo
``@st.cache_resource`` para que multipage comparta la misma instancia entre
páginas. Cada página hace:

    from src.agent.singleton import get_agent, ensure_session_id
    agent = get_agent()
    session_id = ensure_session_id()

Puntos didácticos:

- ``@st.cache_resource`` cachea a nivel de proceso; todas las páginas del
  mismo proceso Streamlit ven el MISMO agente ya cargado.
- ``ensure_session_id`` genera un uuid4 la primera vez que la pestaña del
  navegador abre cualquier página del app y lo reutiliza en toda la sesión.
  Así la memoria del chat se aísla por pestaña del navegador.
"""
import uuid
import streamlit as st

from src.services.db import init_db
from src.agent.agent_builder import build_agent


@st.cache_resource(show_spinner="Inicializando agente...")
def get_agent():
    """Construye (una sola vez) la BD y el agente. Reutilizable entre páginas."""
    init_db()
    return build_agent()


def ensure_session_id() -> str:
    """Devuelve un session_id único por pestaña del navegador."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id
