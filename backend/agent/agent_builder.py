"""Construye el agente conversacional de inversiones (pieza central del proyecto).

Implementación compatible con Python 3.14: usa exclusivamente langchain_core
y langchain_openai, evitando langchain.agents que es incompatible con
Python 3.14 por un bug de evaluación de anotaciones de tipo en Pydantic.

El bucle del agente está implementado manualmente (SimpleAgentExecutor) en lugar
de usar AgentExecutor de langchain.agents, que hereda de Chain (Pydantic) y falla
con Python 3.14 al evaluar Optional[dict[str, Any]] via annotationlib.

Componentes:
  ChatOpenAI → NVIDIA NIM
      |
      v
  _build_tool_calling_agent  <-- prompt con SYSTEM_PROMPT + historial + input
      |
      v
  SimpleAgentExecutor         <-- bucle: LLM -> tool -> observación -> LLM -> final
      |
      v
  RunnableWithMessageHistory  <-- aísla la memoria de chat por session_id
"""
import os
import uuid
import json as _json
import re as _re
import asyncio
from typing import Any, AsyncIterator

from dotenv import load_dotenv

from backend.utils.logger import get_logger

log = get_logger("agent.builder")

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough, Runnable
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.agents import AgentActionMessageLog, AgentFinish
from langchain_core.messages import ToolMessage, AIMessage, BaseMessage

from backend.agent.prompts import SYSTEM_PROMPT
from backend.tools.market_tools import (
    get_ticker_status,
    get_ticker_history,
    get_hot_tickers,
    get_ticker_news,
    search_ticker,
    analyze_news_article,
)
from backend.tools.rag_tool import search_finance_knowledge
from backend.tools.portfolio_tools import (
    portfolio_buy,
    portfolio_buy_all_cash,
    portfolio_sell,
    portfolio_view,
    portfolio_transactions,
    portfolio_list,
    portfolio_set_risk,
    portfolio_set_markets,
)
from backend.tools.advisor_tool import (
    analyze_buy_opportunities,
    analyze_sell_candidates,
)
from backend.tools.analysis_tools import (
    compare_tickers,
    get_fundamentals,
)

load_dotenv()

_SESSION_STORE: dict[str, BaseChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = InMemoryChatMessageHistory()
    return _SESSION_STORE[session_id]


def get_active_llm_info() -> tuple[str, str]:
    return ("nvidia", os.getenv("NVIDIA_MODEL", "minimaxai/minimax-m2.7"))


def _build_nvidia_llm() -> ChatOpenAI:
    model = os.getenv("NVIDIA_MODEL", "minimaxai/minimax-m2.7")
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1",
        temperature=0.1,
        max_tokens=2048,
        streaming=True,
        request_timeout=120.0,
        max_retries=2,
    )


def _build_llm():
    return _build_nvidia_llm()


# ---------------------------------------------------------------------------
# Text-format tool call parsing (kimi-k2 quirk)
# ---------------------------------------------------------------------------

_TEXT_TOOL_RE = _re.compile(r'functions\.(\w+):\d+(\{[^}]*\})', _re.DOTALL)
_ARG_BLOCK_RE = _re.compile(r'<\|tool_call_argument_begin\|>(\{.*?\})', _re.DOTALL)


def _content_to_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content) if content else ""


def _try_parse_json(s: str) -> dict | None:
    s = s.strip()
    try:
        return _json.loads(s)
    except Exception:
        pass
    for suffix in ['"}', '"}}', '}', '}}']:
        try:
            return _json.loads(s + suffix)
        except Exception:
            pass
    return None


def _extract_text_tool_args(content_str: str, tool_name: str) -> dict | None:
    for m in _TEXT_TOOL_RE.finditer(content_str):
        if m.group(1) == tool_name:
            result = _try_parse_json(m.group(2))
            if result is not None:
                return result
    for m in _ARG_BLOCK_RE.finditer(content_str):
        result = _try_parse_json(m.group(1))
        if result is not None:
            return result
    return None


def _synthesize_tool_calls(content_str: str) -> list[dict]:
    calls = []
    text_matches = list(_TEXT_TOOL_RE.finditer(content_str))
    if text_matches:
        log.info(f"[parser] text-format matches found: {[m.group(0)[:60] for m in text_matches]}")
    else:
        log.info("[parser] no text-format tool matches found in content")
    for m in text_matches:
        raw_json = m.group(2)
        args = _try_parse_json(raw_json)
        if args is not None:
            calls.append({
                "name": m.group(1),
                "args": args,
                "id": uuid.uuid4().hex[:8],
                "type": "tool_call",
            })
            log.info(f"[parser] synthesized tool call: {m.group(1)}({args})")
        else:
            log.warning(f"[parser] failed to parse JSON for {m.group(1)}: {raw_json!r}")
    return calls


# ---------------------------------------------------------------------------
# Output parsing: converts AIMessage → AgentActionMessageLog | AgentFinish
# ---------------------------------------------------------------------------

def _parse_llm_output(message: AIMessage, content_str: str) -> AgentFinish | list[AgentActionMessageLog]:
    """Parses LLM output, handling kimi-k2 quirks."""
    existing = list(getattr(message, "tool_calls", None) or [])

    log.info(
        f"[parser] structured tool_calls={len(existing)} | "
        f"content_len={len(content_str)} | "
        f"content_full={content_str!r}"
    )
    if existing:
        log.info(f"[parser] structured calls: {existing}")

    # Fix 3: synthesize tool calls from text when tool_calls=[]
    if not existing:
        synth = _synthesize_tool_calls(content_str)
        if synth:
            log.info(f"[parser] Fix3: injecting {len(synth)} synthesized call(s)")
            existing = synth
        else:
            log.info("[parser] Fix3: no synthesis — AgentFinish")

    raw_ak_tcs = getattr(message, "additional_kwargs", {}).get("tool_calls", [])
    if raw_ak_tcs:
        log.info(f"[parser] additional_kwargs tool_calls: {raw_ak_tcs}")

    if not existing:
        output_text = content_str or ""
        return AgentFinish(return_values={"output": output_text}, log=output_text)

    fixed = []
    for tc in existing:
        if not isinstance(tc, dict):
            fixed.append(tc)
            continue
        tc = dict(tc)
        # Fix 1: null id
        if not tc.get("id"):
            tc["id"] = uuid.uuid4().hex[:8]
            log.info(f"[parser] Fix1: assigned id to {tc.get('name')}")
        # Fix 2: empty args — try text-format first
        if not tc.get("args"):
            recovered = _extract_text_tool_args(content_str, tc.get("name", ""))
            if recovered:
                log.info(f"[parser] Fix2: recovered args for {tc['name']}: {recovered}")
                tc["args"] = recovered
            else:
                log.warning(f"[parser] Fix2: could not recover args for {tc.get('name')}")
        # Fix 2b: fall back to additional_kwargs raw function.arguments
        if not tc.get("args"):
            for raw in raw_ak_tcs:
                if not isinstance(raw, dict):
                    continue
                fn = raw.get("function", {})
                if not isinstance(fn, dict):
                    continue
                raw_str = fn.get("arguments", "")
                log.info(f"[parser] Fix2b: checking raw fn={fn.get('name')!r} arguments={raw_str!r}")
                if fn.get("name") == tc.get("name") and raw_str not in ("", "{}"):
                    r2 = _try_parse_json(raw_str)
                    if r2:
                        log.info(f"[parser] Fix2b: recovered from additional_kwargs: {r2}")
                        tc["args"] = r2
                        break
            if not tc.get("args"):
                log.warning(f"[parser] Fix2b: additional_kwargs also empty for {tc.get('name')}")
        fixed.append(tc)

    log.info(f"[parser] final calls dispatched: {[{'name': c.get('name'), 'args': c.get('args')} for c in fixed]}")

    actions = []
    for tc in fixed:
        name = tc.get("name", "")
        args = tc.get("args") or {}
        tc_id = tc.get("id") or uuid.uuid4().hex[:8]
        log_str = f"\nInvoking: `{name}` with `{args}`\n"
        actions.append(AgentActionMessageLog(
            tool=name,
            tool_input=args,
            log=log_str,
            message_log=[message],
            tool_call_id=tc_id,
        ))
    return actions


def _format_scratchpad(intermediate_steps: list[tuple]) -> list[BaseMessage]:
    """Convert (AgentActionMessageLog, observation) pairs to messages."""
    messages: list[BaseMessage] = []
    for action, observation in intermediate_steps:
        if isinstance(action, AgentActionMessageLog):
            messages.extend(action.message_log)
            messages.append(ToolMessage(
                content=str(observation),
                tool_call_id=action.tool_call_id,
            ))
        else:
            messages.append(AIMessage(content=action.log))
            messages.append(ToolMessage(
                content=str(observation),
                tool_call_id=getattr(action, "tool_call_id", ""),
            ))
    return messages


# ---------------------------------------------------------------------------
# Simple async agent executor (replaces langchain.agents.AgentExecutor)
# ---------------------------------------------------------------------------

class SimpleAgentExecutor(Runnable):
    """Minimal async agent executor that avoids langchain.chains.Chain (Python 3.14 compat)."""

    def __init__(self, agent_chain, tools: list, max_iterations: int = 20):
        self._agent = agent_chain
        self._tools = {t.name: t for t in tools}
        self._max_iterations = max_iterations

    def invoke(self, inputs: dict, config=None) -> dict:
        return asyncio.get_event_loop().run_until_complete(self.ainvoke(inputs, config))

    async def ainvoke(self, inputs: dict, config=None) -> dict:
        intermediate_steps: list[tuple] = []
        agent_input = dict(inputs)

        for i in range(self._max_iterations):
            agent_input["intermediate_steps"] = intermediate_steps
            try:
                result = await self._agent.ainvoke(agent_input, config=config)
            except Exception as e:
                log.warning(f"[executor] agent invoke error on iter {i}: {e}")
                return {"output": f"Error en el agente: {e}"}

            if isinstance(result, AgentFinish):
                return result.return_values
            if isinstance(result, list):
                for action in result:
                    tool_fn = self._tools.get(action.tool)
                    if tool_fn is None:
                        observation = f"Tool '{action.tool}' no encontrada."
                        log.warning(f"[executor] tool not found: {action.tool}")
                    else:
                        try:
                            log.info(f"[executor] calling tool {action.tool}({action.tool_input})")
                            if asyncio.iscoroutinefunction(tool_fn.func if hasattr(tool_fn, 'func') else tool_fn):
                                observation = await tool_fn.ainvoke(action.tool_input)
                            else:
                                observation = await asyncio.get_event_loop().run_in_executor(
                                    None, lambda: tool_fn.invoke(action.tool_input)
                                )
                            log.info(f"[executor] tool result: {str(observation)[:120]!r}")
                        except Exception as e:
                            observation = f"Error ejecutando {action.tool}: {e}"
                            log.warning(f"[executor] tool error: {e}")
                    intermediate_steps.append((action, observation))
            else:
                log.warning(f"[executor] unexpected result type: {type(result)}")
                break

        return {"output": "El agente alcanzó el límite de iteraciones sin respuesta final."}

    async def astream_events(self, inputs: dict, config=None, version: str = "v2"):
        """Yield events compatible with langchain_core astream_events format."""
        intermediate_steps: list[tuple] = []
        agent_input = dict(inputs)

        yield {"event": "on_chain_start", "name": "AgentExecutor", "data": {"input": inputs}}

        for i in range(self._max_iterations):
            agent_input["intermediate_steps"] = intermediate_steps

            # Stream the LLM response
            accumulated_chunks = []
            accumulated_content = ""
            accumulated_message = None

            try:
                async for chunk in self._agent.astream(agent_input, config=config):
                    # chunk is AIMessageChunk from the LLM
                    if hasattr(chunk, "content"):
                        chunk_text = _content_to_str(getattr(chunk, "content", ""))
                        yield {"event": "on_chat_model_stream", "data": {"chunk": chunk}}
                        accumulated_content += chunk_text
                        accumulated_chunks.append(chunk)
                    elif isinstance(chunk, (AgentFinish, list)):
                        # Direct output (no streaming at this step)
                        accumulated_message = chunk
                        break
            except Exception as e:
                log.warning(f"[executor] astream error on iter {i}: {e}")
                yield {"event": "on_chain_end", "name": "AgentExecutor", "data": {"output": {"output": str(e)}}}
                return

            # If we got direct output (no streaming), process it
            if accumulated_message is not None:
                if isinstance(accumulated_message, AgentFinish):
                    output = accumulated_message.return_values
                    yield {"event": "on_chain_end", "name": "AgentExecutor", "data": {"output": output}}
                    return
                # list of actions — handled below after streaming
                actions = accumulated_message
            else:
                # Reconstruct the full message from chunks and parse
                if not accumulated_chunks:
                    break
                # Build AIMessage from accumulated content
                last_chunk = accumulated_chunks[-1]
                if hasattr(last_chunk, "tool_calls"):
                    tool_calls = getattr(last_chunk, "tool_calls", []) or []
                else:
                    tool_calls = []
                # Also check additional_kwargs
                ak = {}
                for c in accumulated_chunks:
                    for k, v in getattr(c, "additional_kwargs", {}).items():
                        if isinstance(v, list) and k == "tool_calls":
                            if k not in ak:
                                ak[k] = v
                        else:
                            ak[k] = v

                full_message = AIMessage(
                    content=accumulated_content,
                    tool_calls=tool_calls,
                    additional_kwargs=ak,
                )

                yield {
                    "event": "on_chat_model_end",
                    "data": {
                        "output": full_message,
                        "input": agent_input,
                    },
                }

                parsed = _parse_llm_output(full_message, accumulated_content)

                if isinstance(parsed, AgentFinish):
                    output = parsed.return_values
                    yield {"event": "on_chain_end", "name": "AgentExecutor", "data": {"output": output}}
                    return
                actions = parsed

            # Execute tools
            for action in actions:
                yield {
                    "event": "on_tool_start",
                    "name": action.tool,
                    "data": {"input": action.tool_input},
                }
                tool_fn = self._tools.get(action.tool)
                if tool_fn is None:
                    observation = f"Tool '{action.tool}' no encontrada."
                    log.warning(f"[executor] tool not found: {action.tool}")
                else:
                    try:
                        log.info(f"[executor] calling tool {action.tool}({action.tool_input})")
                        observation = await asyncio.get_event_loop().run_in_executor(
                            None, lambda t=tool_fn, inp=action.tool_input: t.invoke(inp)
                        )
                        log.info(f"[executor] tool result: {str(observation)[:120]!r}")
                    except Exception as e:
                        observation = f"Error ejecutando {action.tool}: {e}"
                        log.warning(f"[executor] tool error: {e}")

                yield {
                    "event": "on_tool_end",
                    "name": action.tool,
                    "data": {"output": observation},
                }
                intermediate_steps.append((action, observation))

        # max_iterations reached
        output = {"output": "El agente alcanzó el límite de iteraciones sin respuesta final."}
        yield {"event": "on_chain_end", "name": "AgentExecutor", "data": {"output": output}}


# ---------------------------------------------------------------------------
# Agent chain (LLM + prompt + output parser)
# ---------------------------------------------------------------------------

def _build_agent_chain(llm, tools, prompt):
    """Builds the agent runnable: prompt | llm | parse."""

    async def _invoke_chain(inputs: dict, config=None):
        scratchpad = _format_scratchpad(inputs.get("intermediate_steps", []))
        chain_input = {k: v for k, v in inputs.items() if k != "intermediate_steps"}
        chain_input["agent_scratchpad"] = scratchpad
        message = await (prompt | llm.bind_tools(tools)).ainvoke(chain_input, config=config)
        content_str = _content_to_str(getattr(message, "content", ""))
        return _parse_llm_output(message, content_str)

    async def _stream_chain(inputs: dict, config=None):
        scratchpad = _format_scratchpad(inputs.get("intermediate_steps", []))
        chain_input = {k: v for k, v in inputs.items() if k != "intermediate_steps"}
        chain_input["agent_scratchpad"] = scratchpad
        async for chunk in (prompt | llm.bind_tools(tools)).astream(chain_input, config=config):
            yield chunk

    class _AgentChain(Runnable):
        async def ainvoke(self, inputs, config=None):
            return await _invoke_chain(inputs, config)

        def invoke(self, inputs, config=None):
            import asyncio as _aio
            loop = _aio.new_event_loop()
            try:
                return loop.run_until_complete(_invoke_chain(inputs, config))
            finally:
                loop.close()

        async def astream(self, inputs, config=None):
            async for chunk in _stream_chain(inputs, config):
                yield chunk

    return _AgentChain()


# ---------------------------------------------------------------------------
# Public build function
# ---------------------------------------------------------------------------

def build_agent() -> RunnableWithMessageHistory:
    """Construye y devuelve el agente listo para invoke().

    Usa solo langchain_core + langchain_openai para compatibilidad con Python 3.14.
    """
    log.debug("Building agent... provider=nvidia")
    llm = _build_llm()

    tools = [
        get_ticker_status,
        get_ticker_history,
        get_hot_tickers,
        get_ticker_news,
        search_ticker,
        analyze_news_article,
        search_finance_knowledge,
        portfolio_buy,
        portfolio_buy_all_cash,
        portfolio_sell,
        portfolio_view,
        portfolio_transactions,
        portfolio_list,
        portfolio_set_risk,
        portfolio_set_markets,
        analyze_buy_opportunities,
        analyze_sell_candidates,
        compare_tickers,
        get_fundamentals,
    ]

    try:
        from backend.services.preferences import render_for_prompt
        prefs_line = render_for_prompt()
    except Exception:
        prefs_line = ""
    composed_system = SYSTEM_PROMPT
    if prefs_line:
        composed_system = (
            SYSTEM_PROMPT
            + "\n\nContexto del usuario (tenlo en cuenta en cualquier "
            "recomendación o filtro de tickers):\n"
            + prefs_line
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", composed_system),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent_chain = _build_agent_chain(llm, tools, prompt)

    executor = SimpleAgentExecutor(
        agent_chain=agent_chain,
        tools=tools,
        max_iterations=20,
    )

    log.debug(f"Agent built successfully ({len(tools)} tools registered)")
    return RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
