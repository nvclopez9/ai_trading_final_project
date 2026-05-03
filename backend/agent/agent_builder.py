"""Construye el agente conversacional de inversiones (pieza central del proyecto).

Este módulo orquesta todos los componentes de LangChain que forman el
agente usando exclusivamente NVIDIA NIM como proveedor LLM:

  ChatOpenAI → NVIDIA NIM
      |
      v
  create_tool_calling_agent  <-- prompt con SYSTEM_PROMPT + historial + input
      |
      v
  AgentExecutor              <-- bucle: LLM -> tool -> observación -> LLM -> final
      |
      v
  RunnableWithMessageHistory <-- aísla la memoria de chat por session_id

Puntos didácticos clave para la exposición oral:

1. ¿Qué es un AgentExecutor? Es el bucle que hace funcionar el agente: le
   pasa el mensaje al LLM; si el LLM decide llamar a una tool, la ejecuta,
   mete la observación en el scratchpad y vuelve a preguntar al LLM; así
   hasta que el LLM responde sin pedir más tools (o hasta ``max_iterations``).

2. ¿Qué son las "tools"? Funciones Python decoradas con ``@tool`` cuyo
   docstring el LLM lee como descripción. En cada iteración el LLM decide
   invocar 0, 1 o varias, pasando argumentos JSON estructurados.

3. ¿Por qué ``create_tool_calling_agent`` en vez de ReAct clásico?
   ReAct parsea texto tipo "Action: ..., Action Input: ..." del LLM, lo que
   es frágil con modelos pequeños que se saltan el formato. Tool-calling
   nativo devuelve la llamada a tool como un objeto estructurado — mucho
   más fiable y menos propenso a loops.

4. ¿Por qué ``RunnableWithMessageHistory`` + ``session_id``? El
   ``AgentExecutor`` es stateless. Para que el chat recuerde el contexto de
   los mensajes previos lo envolvemos con RunnableWithMessageHistory, que
   inyecta el historial en el prompt (placeholder ``chat_history``). La
   memoria se indexa por ``session_id`` para aislar sesiones distintas
   entre sí — si dos usuarios abren el mismo servidor, sus chats no se mezclan.

5. ¿Cómo decide qué tool usar? El LLM lee el SYSTEM_PROMPT (que contiene
   un mapa intención->tool) y los docstrings de las tools. Con ese contexto
   y el input del usuario, genera una llamada a tool estructurada. No hay
   árbol de decisión hardcodeado: es el modelo quien elige.
"""
# Librería estándar + dotenv para leer NVIDIA_MODEL y NVIDIA_API_KEY del .env.
import os
from dotenv import load_dotenv

from backend.utils.logger import get_logger

log = get_logger("agent.builder")

# ChatOpenAI: cliente compatible con la API de OpenAI. Lo reutilizamos para
# NVIDIA NIM porque su endpoint sigue el mismo contrato (chat/completions con
# tool-calling). Solo hay que cambiar base_url y la api_key.
from langchain_openai import ChatOpenAI
# AgentExecutor y create_tool_calling_agent: montan el bucle del agente.
from langchain.agents import AgentExecutor, create_tool_calling_agent
# Prompt templates: ChatPromptTemplate compone system + chat_history + human
# + agent_scratchpad (variables que el AgentExecutor rellena en cada iteración).
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# Historia de mensajes: interfaz + implementación in-memory para los chats.
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
# Wrapper que añade memoria al runnable vía callback get_session_history.
from langchain_core.runnables.history import RunnableWithMessageHistory

# Prompt de sistema en español con reglas y mapa intención->tool.
from backend.agent.prompts import SYSTEM_PROMPT
# Las tools del agente, organizadas en 3 módulos (mercado, RAG, cartera).
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

# Store en memoria de historiales de chat indexado por session_id.
# Es un dict de nivel módulo: persiste mientras el proceso Python esté vivo.
# Aceptable para el MVP; una mejora futura sería persistirlo en Redis/SQLite
# para que el usuario reabra la app y siga su conversación.
_SESSION_STORE: dict[str, BaseChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """Callback que RunnableWithMessageHistory llama para obtener el historial.

    Si es la primera vez que vemos este session_id, creamos una historia
    vacía ``InMemoryChatMessageHistory`` y la guardamos en el store. En
    llamadas sucesivas devolvemos la misma instancia para que el estado
    (mensajes previos) se mantenga dentro de la sesión.
    """
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = InMemoryChatMessageHistory()
    return _SESSION_STORE[session_id]


def get_active_llm_info() -> tuple[str, str]:
    """Devuelve (provider, model) para el LLM activo (siempre NVIDIA NIM).

    Útil para mostrar en la UI qué LLM está atendiendo al agente.
    """
    return ("nvidia", os.getenv("NVIDIA_MODEL", "minimaxai/minimax-m2.7"))


def _build_nvidia_llm() -> ChatOpenAI:
    """Construye el cliente de NVIDIA NIM (vía API compatible OpenAI).

    streaming=True: habilita SSE token-a-token para que la UI muestre texto
    fluyendo en lugar de bloquearse hasta que llegue la respuesta completa.
    request_timeout + max_retries: evitan bloqueos indefinidos y reintentan
    en fallos transitorios de red.
    max_tokens=1024: apropiado para un agente tool-calling (no prosa larga);
    reduce el tiempo de inferencia por iteración vs los 2048 anteriores.
    """
    model = os.getenv("NVIDIA_MODEL", "minimaxai/minimax-m2.7")
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1",
        temperature=0.1,
        max_tokens=1024,
        streaming=True,
        request_timeout=60.0,
        max_retries=2,
    )


def _build_llm():
    """Construye el cliente LLM usando NVIDIA NIM."""
    return _build_nvidia_llm()


def build_agent() -> RunnableWithMessageHistory:
    """Construye y devuelve el agente listo para ``invoke()``.

    Se llama UNA sola vez y su resultado se cachea en el singleton. Así no
    reinstanciamos el cliente LLM ni recompilamos el grafo del agente en cada
    request. Importante: si cambias variables del .env (NVIDIA_MODEL, API
    keys), debes reiniciar el servidor para que el agente se reconstruya.
    """
    log.debug("Building agent... provider=nvidia")
    # Cliente del LLM (NVIDIA NIM).
    llm = _build_llm()

    # Lista de tools disponibles para el agente. El orden no importa, pero
    # los docstrings y el SYSTEM_PROMPT deben estar alineados con esta lista.
    tools = [
        get_ticker_status,
        get_ticker_history,
        get_hot_tickers,
        get_ticker_news,
        search_ticker,
        analyze_news_article,
        search_finance_knowledge,
        portfolio_buy,
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

    # Prompt del agente. Los 4 elementos son obligatorios para el tool-calling:
    #  1. system: rol + reglas + mapa intención->tool.
    #  2. chat_history: MessagesPlaceholder que rellena RunnableWithMessageHistory.
    #  3. human: el input del usuario de este turno.
    #  4. agent_scratchpad: donde el AgentExecutor escribe las llamadas a tools
    #     y las observaciones que van recibiendo durante el bucle.
    # Inyectamos las preferencias del usuario como sufijo del system prompt.
    # Si el usuario aún no ha hecho onboarding, devuelve "" y se omite.
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

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", composed_system),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Creamos el agente usando la variante tool-calling (no ReAct). Esta
    # función devuelve un Runnable que, dado un input, produce AgentAction
    # (llamada a tool) o AgentFinish (respuesta final) en cada paso.
    agent = create_tool_calling_agent(llm, tools, prompt)

    # AgentExecutor es el bucle que ejecuta el agente:
    #  - verbose=False: no volcamos trazas al stdout (la UI lo maneja aparte).
    #  - handle_parsing_errors=True: si el LLM produce salida mal formada,
    #    el executor reintenta en lugar de reventar.
    #  - max_iterations=20: tope alto para que pueda ejecutar propuestas con
    #    varias compras/ventas seguidas (cada portfolio_buy es 1 iteración) +
    #    una llamada final a portfolio_view.
    #  - return_intermediate_steps=False: no necesitamos los pasos en la UI;
    #    solo nos quedamos con la respuesta final ("output").
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=20,
        return_intermediate_steps=False,
    )

    # Envolvemos el executor con memoria por sesión.
    # input_messages_key="input": le dice a RunnableWithMessageHistory qué
    # campo del dict de entrada es el "mensaje nuevo" del usuario.
    # history_messages_key="chat_history": dónde inyectar el historial en el
    # prompt (coincide con el MessagesPlaceholder del ChatPromptTemplate).
    log.debug(f"Agent built successfully ({len(tools)} tools registered)")
    return RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
