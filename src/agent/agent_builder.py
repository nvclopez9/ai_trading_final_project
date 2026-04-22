"""Construye el agente conversacional de inversiones.

Flujo: el usuario escribe en el chat de Streamlit, el AgentExecutor (tool-calling
sobre ChatOllama) decide qué herramienta invocar (mercado, RAG o cartera), ejecuta
la tool, recibe la observación y compone la respuesta final en lenguaje natural.
El historial se aísla por sesión Streamlit mediante RunnableWithMessageHistory,
usando un store en memoria indexado por session_id.
"""
import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from src.agent.prompts import SYSTEM_PROMPT
from src.tools.market_tools import get_ticker_status, get_ticker_history, get_hot_tickers
from src.tools.rag_tool import search_finance_knowledge
from src.tools.portfolio_tools import (
    portfolio_buy,
    portfolio_sell,
    portfolio_view,
    portfolio_transactions,
)

load_dotenv()

_SESSION_STORE: dict[str, BaseChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = InMemoryChatMessageHistory()
    return _SESSION_STORE[session_id]


def build_agent() -> RunnableWithMessageHistory:
    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    llm = ChatOllama(
        model=model,
        base_url=host,
        num_ctx=12000,
        temperature=0.2,
    )

    tools = [
        get_ticker_status,
        get_ticker_history,
        get_hot_tickers,
        search_finance_knowledge,
        portfolio_buy,
        portfolio_sell,
        portfolio_view,
        portfolio_transactions,
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=6,
        return_intermediate_steps=False,
    )

    return RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
