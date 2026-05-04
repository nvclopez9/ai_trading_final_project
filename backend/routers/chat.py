"""Chat API routes with SSE streaming."""
import asyncio
import json
import re
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


# kimi-k2-instruct emits its internal tool-calling format as plain text in the
# stream alongside the structured tool calls. These patterns need to be stripped
# so the user only sees the natural-language response.
_ARTIFACT_RE = re.compile(
    r"functions\.\w+:\d+\{[^}]*\}?"              # functions.tool_name:1{...}
    r"|\[\{['\"]type['\"][^\]]+\]"                # [{'type': 'text', 'text': '...'}]
    r"|\d*<\|[^|>]{1,80}\|>"                      # 2<|tool_call_begin|> or <|token|>
    r"|<\|tool_calls?_section_(?:begin|end)\|>"   # section markers
    r"|\d+<\|",                                   # dangling N<|
    re.DOTALL,
)


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


def _clean(raw: str) -> str:
    """Strip kimi-k2 internal tool-call artifacts from a streamed text chunk."""
    return _ARTIFACT_RE.sub("", raw)


def _set_portfolio(portfolio_id: int) -> None:
    try:
        from backend.tools.portfolio_tools import set_active_portfolio
        set_active_portfolio(portfolio_id)
    except Exception:
        pass


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_agent(message: str, session_id: str, portfolio_id: int) -> AsyncIterator[str]:
    """Streams agent response as SSE events.

    Uses astream_events so tokens arrive progressively — the client sees
    output while the model is still generating instead of waiting for the
    full reply.
    """
    _set_portfolio(portfolio_id)

    try:
        from backend.agent.singleton import get_agent
        agent = get_agent()

        yield _sse("thinking", {"message": "Procesando..."})

        log.debug(f"astream_events → session={session_id!r} msg={message[:80]!r}")

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
                    content = _clean(raw)
                    if content:
                        yield _sse("token", {"content": content})

                elif kind == "on_tool_start":
                    yield _sse("tool_call", {
                        "name": event.get("name", "herramienta"),
                        "status": "calling",
                    })
                    log.debug(f"tool_start: {event.get('name')}")

                elif kind == "on_tool_end":
                    yield _sse("tool_call", {
                        "name": event.get("name", "herramienta"),
                        "status": "done",
                    })

        yield _sse("done", {})

    except TimeoutError:
        log.warning(f"agent timeout after {AGENT_TIMEOUT}s (session={session_id!r})")
        yield _sse("error", {
            "message": f"El agente tardó más de {AGENT_TIMEOUT}s. Prueba una pregunta más concreta."
        })
        yield _sse("done", {})

    except Exception as e:
        log.warning(f"chat stream error: {e}")
        yield _sse("error", {"message": str(e)})
        yield _sse("done", {})


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
