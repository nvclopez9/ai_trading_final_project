"""Chat API routes with SSE streaming."""
import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.utils.logger import get_logger

log = get_logger("chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

AGENT_TIMEOUT = 240  # seconds — kill slow queries before the client drops


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    portfolio_id: int = 1


class ClearRequest(BaseModel):
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Stateful artifact filter
# ---------------------------------------------------------------------------
# kimi-k2-instruct emits its internal tool-calling format as plain text in the
# stream alongside the structured tool calls. These tokens span chunk boundaries
# so we need a stateful cleaner rather than a simple regex substitution.
#
# Format examples:
#   functions.portfolio_buy:1{"ticker": "NVDA", "qty": 10}
#   [{'type': 'text', 'text': 'some response text...'}]
#   2<|tool_call_argument_begin|>{"ticker": "NVDA"}
#   <|tool_calls_section_end|>

_TRIGGERS: list[tuple[str, str]] = (
    [("[{'type'", "'}]"), ('[{"type"', '"}]')]          # list-format content blocks
    + [(f"{d}<|", "|>") for d in range(10)]             # N<|special_token|>
    + [("<|", "|>"), ("functions.", "}")]                # bare tokens + text tool calls
)
_MAX_TRIGGER_LEN = max(len(s) for s, _ in _TRIGGERS)


class _StreamCleaner:
    """Strips kimi-k2 artifact tokens from a streaming text, handling cross-chunk spans."""

    def __init__(self):
        self._buf = ""
        self._end: str | None = None   # what we're waiting for to end suppression

    def feed(self, text: str) -> str:
        self._buf += text
        out: list[str] = []
        while True:
            if self._end:
                idx = self._buf.find(self._end)
                if idx >= 0:
                    self._buf = self._buf[idx + len(self._end):]
                    self._end = None
                else:
                    break  # artifact continues in next chunk
            else:
                best_idx = len(self._buf)
                best_slen = 0
                best_end = None
                for start, end in _TRIGGERS:
                    i = self._buf.find(start)
                    if 0 <= i < best_idx:
                        best_idx, best_slen, best_end = i, len(start), end

                if best_end is not None:
                    out.append(self._buf[:best_idx])
                    self._buf = self._buf[best_idx + best_slen:]
                    self._end = best_end
                else:
                    # Hold back a small tail — it might be the start of an artifact
                    safe = max(0, len(self._buf) - (_MAX_TRIGGER_LEN - 1))
                    out.append(self._buf[:safe])
                    self._buf = self._buf[safe:]
                    break
        return "".join(out)

    def flush(self) -> str:
        result = self._buf if not self._end else ""
        self._buf = ""
        self._end = None
        return result


def _extract_text(content) -> str:
    """Normalise AIMessageChunk content — handles str and list[dict] forms."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content) if content else ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_portfolio(portfolio_id: int) -> None:
    try:
        from backend.tools.portfolio_tools import set_active_portfolio
        set_active_portfolio(portfolio_id)
    except Exception:
        pass


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Streaming agent
# ---------------------------------------------------------------------------

async def _stream_agent(message: str, session_id: str, portfolio_id: int) -> AsyncIterator[str]:
    _set_portfolio(portfolio_id)

    try:
        from backend.agent.singleton import get_agent
        agent = get_agent()

        yield _sse("thinking", {"message": "Procesando..."})
        log.info(f"[chat] astream_events → session={session_id!r} portfolio={portfolio_id} msg={message[:80]!r}")

        cleaner = _StreamCleaner()
        iteration = 0

        async with asyncio.timeout(AGENT_TIMEOUT):
            async for event in agent.astream_events(
                {"input": message},
                config={"configurable": {"session_id": session_id}},
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    raw = _extract_text(getattr(chunk, "content", "") if chunk else "")
                    clean = cleaner.feed(raw)
                    if clean:
                        yield _sse("token", {"content": clean})

                elif kind == "on_chat_model_end":
                    iteration += 1
                    out = event["data"].get("output")
                    tc = getattr(out, "tool_calls", None) or []
                    text_content = _extract_text(getattr(out, "content", "")) if out else ""
                    log.info(
                        f"[chat] llm_end iter={iteration} "
                        f"tool_calls={len(tc)} "
                        f"content_snippet={text_content[:100]!r}"
                    )
                    if tc:
                        log.info(f"[chat] llm tool_calls detail: {tc}")

                elif kind == "on_tool_start":
                    tool_input = event["data"].get("input", {})
                    log.info(f"[chat] tool_start: {event.get('name')} input={tool_input}")
                    yield _sse("tool_call", {
                        "name": event.get("name", "herramienta"),
                        "status": "calling",
                    })

                elif kind == "on_tool_end":
                    tool_output = str(event["data"].get("output", ""))[:120]
                    log.info(f"[chat] tool_end: {event.get('name')} output={tool_output!r}")
                    yield _sse("tool_call", {
                        "name": event.get("name", "herramienta"),
                        "status": "done",
                    })

                elif kind == "on_chain_end" and event.get("name") == "AgentExecutor":
                    final_out = event["data"].get("output", {})
                    log.info(f"[chat] AgentExecutor finished: output_keys={list(final_out.keys()) if isinstance(final_out, dict) else type(final_out).__name__}")

        # Flush any buffered clean text
        tail = cleaner.flush()
        if tail:
            yield _sse("token", {"content": tail})

        yield _sse("done", {})

    except TimeoutError:
        log.warning(f"agent timeout after {AGENT_TIMEOUT}s (session={session_id!r})")
        yield _sse("error", {
            "message": f"El agente tardó más de {AGENT_TIMEOUT}s. Prueba una pregunta más concreta."
        })
        yield _sse("done", {})

    except Exception as e:
        err_str = str(e)
        log.warning(f"chat stream error: {err_str}")
        if "429" in err_str or "Too Many Requests" in err_str:
            msg = "El servidor de IA ha recibido demasiadas peticiones. Espera unos segundos y vuelve a intentarlo."
        else:
            msg = err_str
        yield _sse("error", {"message": msg})
        yield _sse("done", {})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(body: ChatRequest):
    async def _generator():
        async for chunk in _stream_agent(body.message, body.session_id, body.portfolio_id):
            yield chunk

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/clear")
def clear_session(body: ClearRequest):
    try:
        from backend.agent.agent_builder import _SESSION_STORE
        _SESSION_STORE.pop(body.session_id, None)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
