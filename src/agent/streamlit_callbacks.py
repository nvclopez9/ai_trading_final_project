"""Callback handler que pinta tool-calls del agente en directo en Streamlit.

Por qué este módulo
-------------------
``AgentExecutor`` ejecuta un bucle silencioso (LLM -> tool -> observación ->
LLM). Sin retroalimentación visible, el usuario solo ve el spinner "Pensando…"
y un tiempo en blanco que puede ser de varios segundos por tool. Este handler
engancha hooks oficiales de LangChain (``BaseCallbackHandler``) para pintar
en un placeholder de Streamlit qué tool se está ejecutando, cuánto tarda y
si falla.

Cómo se usa
-----------
1. La página crea un ``st.empty()`` debajo del mensaje del asistente.
2. Instancia ``StreamlitToolCallbackHandler(placeholder)``.
3. Pasa el handler al stream del agente vía
   ``config={"callbacks": [handler], ...}``.
4. El handler concatena líneas en una lista interna y re-renderiza el
   placeholder cada vez que llega un evento.

Side effects
------------
Acumula también las tool calls en ``st.session_state["recent_tool_calls"]``
con capacidad de 20 entradas. La página renderiza las últimas 5 en un panel
"Acciones recientes" — así el usuario ve qué ha estado haciendo el agente
incluso después de terminar el turno.

Compatibilidad
--------------
Implementa la firma "verbose" oficial: ``serialized``/``input_str`` para
``on_tool_start``, ``output`` para ``on_tool_end``, ``error`` para
``on_tool_error``. Recibe **kwargs para tolerar campos extra (run_id,
parent_run_id, tags, metadata, inputs) sin romperse.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from uuid import UUID

import streamlit as st
from langchain_core.callbacks.base import BaseCallbackHandler

from src.ui.components import COLOR_DIM, COLOR_MUTED, COLOR_TEXT, _MONO


# Capacidad del buffer global de tool-calls que muestra el panel lateral.
# 20 da margen para ver el contexto de los últimos turnos sin saturar memoria.
_RECENT_CAPACITY = 20


def _summarize_input(input_str: str | None, inputs: dict | None = None) -> str:
    """Genera una pista corta del argumento principal de la tool.

    Las tools del proyecto suelen recibir 1-2 args (ticker, qty, query). Para
    el indicador en directo solo nos interesa enseñar el más representativo:
    si hay un dict con ``ticker`` o ``query``, lo usamos; si no, intentamos
    sacar lo primero del string serializado.
    """
    # Why: la firma de on_tool_start trae tanto ``input_str`` (texto serializado)
    # como ``inputs`` (dict estructurado en versiones recientes). Preferimos el
    # dict cuando está, porque es más fiable.
    if inputs:
        for key in ("ticker", "tickers", "symbol", "query", "term", "concept"):
            if key in inputs and inputs[key]:
                val = inputs[key]
                if isinstance(val, list):
                    return ",".join(str(x) for x in val[:3])
                return str(val)[:32]
        # Fallback: primer valor no nulo del dict.
        for v in inputs.values():
            if v not in (None, "", [], {}):
                return str(v)[:32]
    if input_str:
        # input_str a veces viene como dict-en-string ("{'ticker': 'AAPL'}").
        # No parseamos JSON: con cortar a 32 chars basta para el indicador.
        return str(input_str).strip().strip("{}").strip("'\"")[:32]
    return ""


def _push_recent_tool_call(tool: str, args_summary: str) -> None:
    """Empuja una tool call al buffer de ``recent_tool_calls`` en session_state.

    La página renderiza las últimas 5 en el panel derecha. Mantenemos 20 para
    poder ampliar el panel sin perder histórico al hacer scroll de turnos.
    """
    recent = st.session_state.get("recent_tool_calls", [])
    recent.append(
        {
            "tool": tool,
            "args_summary": args_summary,
            # Hora local HH:MM, suficiente para el panel; no necesitamos fecha.
            "ts": datetime.now().strftime("%H:%M"),
        }
    )
    # Recortamos por la izquierda: siempre nos quedamos con las más recientes.
    if len(recent) > _RECENT_CAPACITY:
        recent = recent[-_RECENT_CAPACITY:]
    st.session_state["recent_tool_calls"] = recent


class StreamlitToolCallbackHandler(BaseCallbackHandler):
    """Handler que pinta tool-calls en directo en un placeholder Streamlit.

    Mantiene una lista interna de líneas (HTML) y re-renderiza el placeholder
    cada vez que entra un evento. El estilo es monoespaciado, color tenue
    (``COLOR_DIM``/``COLOR_MUTED``) y con iconitos sobrios (``▸ ✓ ✗``).
    """

    def __init__(self, placeholder: Any | None = None) -> None:
        # Placeholder de Streamlit donde pintamos. Si es None, el handler sigue
        # funcionando (rellena recent_tool_calls) pero no pinta nada inline.
        self._placeholder = placeholder
        # Líneas HTML acumuladas en este turno; se re-pintan en bloque.
        self._lines: list[str] = []
        # run_id -> (tool_name, args_summary, t0). Usamos run_id porque el
        # AgentExecutor puede tener varias tool calls solapadas en teoría;
        # en la práctica son secuenciales pero esto nos protege.
        self._in_flight: dict[str, tuple[str, str, float]] = {}
        # Contador para localizar la "línea en progreso" y reescribirla cuando
        # llega on_tool_end. Mapea run_id -> índice en self._lines.
        self._line_index: dict[str, int] = {}

    # --- API pública usada por la página ---------------------------------
    def get_tool_calls(self) -> list[dict]:
        """Devuelve la lista de tool calls completadas en este turno.

        La página la usa para alimentar el helper de follow-ups (A4): así
        las sugerencias se basan en las tools realmente ejecutadas, no en
        un regex sobre el texto de salida.
        """
        return list(getattr(self, "_completed_calls", []))

    # --- Hooks de LangChain ----------------------------------------------
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        # Nombre de la tool: ``serialized["name"]`` es lo que LangChain expone.
        # Si por algún motivo no estuviera, caemos a "tool".
        tool_name = (serialized or {}).get("name") or "tool"
        args_summary = _summarize_input(input_str, inputs)
        self._in_flight[str(run_id)] = (tool_name, args_summary, time.monotonic())

        # Línea "en progreso": iconito ▸ con texto tenue.
        line = (
            f"<span style='color:{COLOR_DIM};'>▸</span> "
            f"<code style='background:transparent;border:none;padding:0;"
            f"color:{COLOR_TEXT};font-family:{_MONO};font-size:12px;'>{tool_name}</code>"
            + (
                f" <span style='color:{COLOR_MUTED};font-family:{_MONO};font-size:12px;'>"
                f"{args_summary}</span>"
                if args_summary else ""
            )
            + f" <span style='color:{COLOR_DIM};font-size:11px;'>…</span>"
        )
        self._line_index[str(run_id)] = len(self._lines)
        self._lines.append(line)
        self._render()

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        meta = self._in_flight.pop(rid, None)
        if not meta:
            return
        tool_name, args_summary, t0 = meta
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Línea final: ✓ verde tenue + duración.
        line = (
            f"<span style='color:#10B981;'>✓</span> "
            f"<code style='background:transparent;border:none;padding:0;"
            f"color:{COLOR_TEXT};font-family:{_MONO};font-size:12px;'>{tool_name}</code>"
            + (
                f" <span style='color:{COLOR_MUTED};font-family:{_MONO};font-size:12px;'>"
                f"{args_summary}</span>"
                if args_summary else ""
            )
            + f" <span style='color:{COLOR_DIM};font-family:{_MONO};font-size:11px;'>"
            f"({elapsed_ms} ms)</span>"
        )
        idx = self._line_index.pop(rid, None)
        if idx is not None and idx < len(self._lines):
            self._lines[idx] = line
        else:
            self._lines.append(line)
        self._record_completed(tool_name, args_summary)
        _push_recent_tool_call(tool_name, args_summary)
        self._render()

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        meta = self._in_flight.pop(rid, None)
        tool_name = meta[0] if meta else "tool"
        args_summary = meta[1] if meta else ""

        msg = str(error).splitlines()[0][:120] if str(error) else type(error).__name__
        line = (
            f"<span style='color:#EF4444;'>✗</span> "
            f"<code style='background:transparent;border:none;padding:0;"
            f"color:{COLOR_TEXT};font-family:{_MONO};font-size:12px;'>{tool_name}</code>"
            + (
                f" <span style='color:{COLOR_MUTED};font-family:{_MONO};font-size:12px;'>"
                f"{args_summary}</span>"
                if args_summary else ""
            )
            + f" <span style='color:#EF4444;font-family:{_MONO};font-size:11px;'>"
            f"{msg}</span>"
        )
        idx = self._line_index.pop(rid, None)
        if idx is not None and idx < len(self._lines):
            self._lines[idx] = line
        else:
            self._lines.append(line)
        self._record_completed(tool_name, args_summary)
        _push_recent_tool_call(tool_name, args_summary)
        self._render()

    # --- Internos --------------------------------------------------------
    def _record_completed(self, tool_name: str, args_summary: str) -> None:
        # Buffer "del turno actual" que la página consume al terminar para
        # generar follow-ups basados en las tools realmente llamadas.
        if not hasattr(self, "_completed_calls"):
            self._completed_calls: list[dict] = []
        self._completed_calls.append({"tool": tool_name, "args": args_summary})

    def _render(self) -> None:
        if self._placeholder is None or not self._lines:
            return
        # Re-render completo en cada evento. Es O(n) por evento; con n<=10
        # tools por turno (max_iterations=20) es completamente despreciable.
        body = "<br>".join(self._lines)
        html = (
            f"<div style='margin-top:6px;line-height:1.7;font-size:12px;"
            f"color:{COLOR_MUTED};'>{body}</div>"
        )
        try:
            self._placeholder.markdown(html, unsafe_allow_html=True)
        except Exception:
            # Si Streamlit ya destruyó el placeholder (rerun en mitad), no
            # queremos romper el agente — solo dejamos de pintar.
            pass
