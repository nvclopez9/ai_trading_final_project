"""Chat API routes with SSE streaming."""
import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.utils.logger import get_logger, timed

log = get_logger("chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    portfolio_id: int = 1


class ClearRequest(BaseModel):
    session_id: str = "default"


def _set_portfolio(portfolio_id: int) -> None:
    try:
        from backend.tools.portfolio_tools import set_active_portfolio
        set_active_portfolio(portfolio_id)
    except Exception:
        pass


async def _stream_agent(message: str, session_id: str, portfolio_id: int) -> AsyncIterator[str]:
    """Streams agent response as SSE events."""
    import asyncio

    _set_portfolio(portfolio_id)

    def _send(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        from backend.agent.singleton import get_agent

        agent = get_agent()

        yield _send("thinking", {"message": "Procesando..."})

        loop = asyncio.get_event_loop()

        def _run():
            log.debug(f"agent.invoke → session={session_id!r} msg={message[:80]!r}")
            with timed(log, f"agent.invoke(session={session_id})"):
                return agent.invoke(
                    {"input": message},
                    config={"configurable": {"session_id": session_id}},
                )

        result = await loop.run_in_executor(None, _run)
        output = result.get("output", "") if isinstance(result, dict) else str(result)
        log.debug(f"agent.invoke ← {len(output)} chars")
        yield _send("message", {"content": output})
        yield _send("done", {})

    except Exception as e:
        log.warning(f"chat stream error: {e}")
        yield _send("error", {"message": str(e)})
        yield _send("done", {})


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
