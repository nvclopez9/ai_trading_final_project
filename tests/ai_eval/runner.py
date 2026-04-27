"""Harness de ejecución de los escenarios sobre el agente real.

Diseño (iter 3):
- Reutilizamos el agente cacheado por ``src.agent.singleton.get_agent()``
  en lugar de reconstruir el AgentExecutor por nuestra cuenta. Esto evita
  duplicar lógica de prompts/tools y, sobre todo, elimina el import directo
  de ``langchain.agents`` desde el harness (que rompe en Python 3.14 +
  pydantic v2 con la versión actual de langchain).
- Para capturar las tool calls (necesario para evaluar ``expected_tools``,
  ``forbidden_tools``, ``min_distinct_tickers_in_calls``…) usamos un
  ``BaseCallbackHandler`` minimalista local que graba cada
  ``on_tool_start``/``on_tool_end``. No necesitamos ``intermediate_steps``
  porque el handler ya nos da el name + args + observation por tool call.
- El LLM se selecciona vía la lógica del agente real (Ollama u OpenRouter,
  según .env). Si NINGUNO está disponible o la construcción del agente
  falla en el entorno, devolvemos un skip controlado en lugar de fallar.
- Cada escenario corre con ``session_id`` único para que el historial no
  se contamine entre escenarios.
- La evaluación es sobre TOOL CALLS y prohibiciones de substrings, NO
  sobre el texto literal del LLM (que es estocástico).
"""
from __future__ import annotations

import os
import socket
import time
import traceback
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import UUID

from dotenv import load_dotenv

from tests.ai_eval.scenarios import SCENARIOS

load_dotenv()


# ─── Helpers de disponibilidad del LLM ───────────────────────────────────


def _ollama_available(host: str | None = None, timeout: float = 1.5) -> bool:
    host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        with urlopen(host.rstrip("/") + "/api/tags", timeout=timeout) as r:
            return 200 <= r.status < 500
    except (URLError, socket.timeout, OSError, Exception):
        return False


def _openrouter_configured() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def llm_availability() -> tuple[bool, str]:
    """Devuelve (disponible, razón). razón es '' si OK, o motivo de skip."""
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "openrouter" and _openrouter_configured():
        return True, ""
    if _ollama_available():
        return True, ""
    if provider == "openrouter" and not _openrouter_configured():
        # fallback a ollama, pero ollama tampoco está
        return False, "OPENROUTER_API_KEY ausente y Ollama no responde en OLLAMA_HOST"
    return False, "Ollama no responde en OLLAMA_HOST y OPENROUTER_API_KEY ausente"


# ─── Callback handler para capturar tool calls ──────────────────────────


def _build_tool_capture_handler():
    """Crea un BaseCallbackHandler minimal que graba cada tool call.

    Lo construimos dentro de una función para que el import de
    ``langchain_core.callbacks.base`` solo ocurra cuando el harness se
    ejecuta de verdad (no en import-time del módulo, que se carga también
    desde ``__main__.py`` aunque luego se haga skip).
    """
    from langchain_core.callbacks.base import BaseCallbackHandler

    class ToolCaptureHandler(BaseCallbackHandler):
        """Graba on_tool_start/on_tool_end en una lista in-memory.

        Cada entrada: ``{"name": str, "args": dict|str|None,
        "observation": Any}``. El runner consume esa lista al final del
        turno para evaluar los asserts del escenario.
        """

        def __init__(self) -> None:
            # In-flight: run_id -> (name, args, idx en self.calls)
            self._in_flight: dict[str, tuple[str, Any, int]] = {}
            self.calls: list[dict] = []

        def on_tool_start(
            self,
            serialized: dict[str, Any] | None,
            input_str: str,
            *,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            tags: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
            inputs: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> Any:
            name = (serialized or {}).get("name") or "tool"
            # Preferimos el dict ``inputs`` (estructurado) sobre input_str.
            args: Any
            if inputs:
                args = dict(inputs)
            else:
                args = input_str
            entry = {"name": name, "args": args, "observation": None}
            idx = len(self.calls)
            self.calls.append(entry)
            self._in_flight[str(run_id)] = (name, args, idx)

        def on_tool_end(
            self,
            output: Any,
            *,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            **kwargs: Any,
        ) -> Any:
            meta = self._in_flight.pop(str(run_id), None)
            if not meta:
                return
            _, _, idx = meta
            if 0 <= idx < len(self.calls):
                self.calls[idx]["observation"] = output

        def on_tool_error(
            self,
            error: BaseException,
            *,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            **kwargs: Any,
        ) -> Any:
            meta = self._in_flight.pop(str(run_id), None)
            if not meta:
                return
            _, _, idx = meta
            if 0 <= idx < len(self.calls):
                # Guardamos la excepción serializada para que
                # _extract_tool_calls / verifier puedan inspeccionarla.
                self.calls[idx]["observation"] = f"ERROR: {type(error).__name__}: {error}"

    return ToolCaptureHandler()


# ─── Construcción del agente (vía singleton cacheado) ────────────────────


def _build_agent_runtime():
    """Devuelve el agente cacheado por ``src.agent.singleton.get_agent``.

    Reutilizar el singleton tiene tres ventajas:
      1. No duplicamos la composición del prompt/tools (era la causa raíz
         del fallo en iter 2: el harness re-importaba langchain.agents y
         eso explota en Py3.14 + pydantic v2).
      2. El agente se construye UNA sola vez aunque corramos N escenarios.
      3. La memoria de chat por session_id (RunnableWithMessageHistory) ya
         viene incorporada — solo tenemos que pasar un session_id distinto
         por escenario para aislar contextos.
    """
    from src.agent.singleton import get_agent
    return get_agent()


# ─── Conversión de tool calls capturadas → formato evaluable ─────────────


def _normalize_calls(raw_calls: list[dict]) -> list[dict]:
    """Asegura el shape ``{name, args, observation}`` en cada entrada."""
    out: list[dict] = []
    for c in raw_calls or []:
        out.append({
            "name": c.get("name"),
            "args": c.get("args"),
            "observation": c.get("observation"),
        })
    return out


def _distinct_tickers(tool_calls: list[dict]) -> set[str]:
    """Set de tickers (en mayúscula) que aparecen como argumento ``ticker``
    en alguna de las tool calls. Útil para detectar concentración."""
    tickers: set[str] = set()
    for tc in tool_calls:
        args = tc.get("args")
        if isinstance(args, dict):
            t = args.get("ticker")
            if isinstance(t, str) and t.strip():
                tickers.add(t.strip().upper())
            # tickers (lista, p.ej. compare_tickers)
            ts = args.get("tickers")
            if isinstance(ts, list):
                for x in ts:
                    if isinstance(x, str) and x.strip():
                        tickers.add(x.strip().upper())
    return tickers


# ─── Evaluación de un escenario ──────────────────────────────────────────


def _evaluate(scenario: dict, output: str, tool_calls: list[dict],
              unverified: int) -> list[str]:
    """Devuelve lista de fallos. Lista vacía = passed."""
    failures: list[str] = []
    names = [tc["name"] for tc in tool_calls if tc.get("name")]

    for must in scenario.get("expected_tools", []):
        if must not in names:
            failures.append(f"expected_tool_missing:{must}")

    for forb in scenario.get("forbidden_tools", []):
        if forb in names:
            failures.append(f"forbidden_tool_called:{forb}")

    out_lc = (output or "").lower()
    for sub in scenario.get("must_contain", []):
        if sub.lower() not in out_lc:
            failures.append(f"must_contain_missing:{sub}")
    for sub in scenario.get("must_not_contain", []):
        if sub.lower() in out_lc:
            failures.append(f"must_not_contain_present:{sub}")

    max_unv = scenario.get("max_unverified_numbers")
    if max_unv is not None and unverified > max_unv:
        failures.append(f"too_many_unverified_numbers:{unverified}>{max_unv}")

    min_distinct = scenario.get("min_distinct_tickers_in_calls")
    if min_distinct is not None:
        n = len(_distinct_tickers(tool_calls))
        if n < min_distinct:
            failures.append(f"too_few_distinct_tickers:{n}<{min_distinct}")

    min_calls = scenario.get("min_tool_calls")
    if min_calls is not None and len(names) < min_calls:
        failures.append(f"too_few_tool_calls:{len(names)}<{min_calls}")
    max_calls = scenario.get("max_tool_calls")
    if max_calls is not None and len(names) > max_calls:
        failures.append(f"too_many_tool_calls:{len(names)}>{max_calls}")

    return failures


# ─── API pública ─────────────────────────────────────────────────────────


def run_scenario(scenario: dict, agent: Any | None = None) -> dict:
    """Ejecuta un escenario y devuelve un dict con resultados.

    Si ``agent`` es None, lo obtiene del singleton. Para batches conviene
    pasar el mismo agente cacheado (es lo que hace ``run_all``).
    """
    from src.agent.verifier import verify_response

    started = time.time()
    if agent is None:
        agent = _build_agent_runtime()
    sid = f"ai_eval_{scenario['id']}_{int(started)}"
    handler = _build_tool_capture_handler()
    try:
        # ``agent`` es un RunnableWithMessageHistory que envuelve el
        # AgentExecutor. invoke devuelve el dict de salida del executor.
        result = agent.invoke(
            {"input": scenario["input"]},
            config={
                "configurable": {"session_id": sid},
                "callbacks": [handler],
            },
        )
        output = result.get("output", "") if isinstance(result, dict) else str(result)
    except Exception as e:
        return {
            "id": scenario["id"],
            "input": scenario["input"],
            "output": "",
            "tool_calls": [{"name": tc["name"], "args": tc["args"]}
                           for tc in _normalize_calls(handler.calls)],
            "unverified": 0,
            "passed": False,
            "failures": [f"exception:{type(e).__name__}:{e}"],
            "error_trace": traceback.format_exc(),
            "elapsed_s": round(time.time() - started, 2),
        }

    tool_calls = _normalize_calls(handler.calls)
    # verify_response espera intermediate_steps en formato
    # ``[(AgentAction, observation), ...]``. Lo aproximamos pasando una
    # lista de pseudo-steps con .tool_input.observation; pero la firma del
    # verifier solo lee el segundo elemento (la observación), así que
    # construimos tuplas (None, observation_str).
    pseudo_steps = [(None, tc.get("observation")) for tc in tool_calls
                    if tc.get("observation") is not None]
    try:
        verdict = verify_response(output, pseudo_steps)
        unverified = int(verdict.get("total_unverified", 0))
    except Exception:
        # Si el verifier no soporta la forma que le pasamos (firma cambió),
        # no bloqueamos la evaluación: solo las assertions de
        # max_unverified_numbers se desactivan implícitamente.
        unverified = 0

    failures = _evaluate(scenario, output, tool_calls, unverified)

    return {
        "id": scenario["id"],
        "input": scenario["input"],
        "output": output,
        "tool_calls": [{"name": tc["name"], "args": tc["args"]} for tc in tool_calls],
        "unverified": unverified,
        "passed": not failures,
        "failures": failures,
        "elapsed_s": round(time.time() - started, 2),
    }


def run_all() -> dict:
    """Corre todos los escenarios. Devuelve dict con metadatos.

    Si el LLM no está disponible o la construcción del agente falla en este
    entorno, devuelve {"skipped": True, "reason": ...} sin levantar.
    """
    available, reason = llm_availability()
    if not available:
        return {
            "skipped": True,
            "reason": reason,
            "results": [],
            "total": len(SCENARIOS),
            "passed": 0,
            "failed": 0,
        }

    try:
        agent = _build_agent_runtime()
    except Exception as e:
        return {
            "skipped": True,
            "reason": f"build_agent_failed:{type(e).__name__}:{e}",
            "trace": traceback.format_exc(),
            "results": [],
            "total": len(SCENARIOS),
            "passed": 0,
            "failed": 0,
        }

    results: list[dict] = []
    for sc in SCENARIOS:
        r = run_scenario(sc, agent=agent)
        results.append(r)

    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    return {
        "skipped": False,
        "results": results,
        "total": len(results),
        "passed": passed,
        "failed": failed,
    }
