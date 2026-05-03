"""Singleton del agente + helpers de sesión.

Centraliza la inicialización del agente (build + init_db) en un singleton
de módulo para que todas las partes del backend compartan la misma instancia.

Uso:
    from backend.agent.singleton import get_agent
    agent = get_agent()

Puntos didácticos:

- ``get_agent`` cachea el agente a nivel de proceso; todas las requests al
  mismo proceso uvicorn comparten el MISMO agente ya cargado.
- La función ``rebuild_agent`` invalida la caché para forzar reconstrucción,
  útil si cambian las preferencias del usuario (que se inyectan en el system
  prompt al construir el agente).
"""
import uuid

from backend.services.db import init_db
from backend.agent.agent_builder import build_agent

_agent = None


def get_agent():
    """Construye (una sola vez) la BD y el agente. Reutilizable entre requests."""
    global _agent
    if _agent is None:
        init_db()
        _agent = build_agent()
    return _agent


def rebuild_agent() -> None:
    """Invalida el agente cacheado para forzar reconstrucción.

    Lo llamamos cuando cambian las preferencias del usuario (que se inyectan
    en el system prompt al construir el agente, así que un cambio implica
    recompilar el prompt).
    """
    global _agent
    _agent = None


def ensure_session_id() -> str:
    """Genera un session_id único (UUID4). Útil si el caller no provee uno."""
    return str(uuid.uuid4())
