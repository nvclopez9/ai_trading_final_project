"""Construye el agente conversacional de inversiones (pieza central del proyecto).

Este módulo orquesta todos los componentes de LangChain que forman el
agente:

  ChatOllama (LLM local)
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
   nativo (soportado por gemma3/qwen3 en Ollama) devuelve la llamada a tool
   como un objeto estructurado — mucho más fiable y menos propenso a loops.

4. ¿Por qué ``RunnableWithMessageHistory`` + ``session_id``? El
   ``AgentExecutor`` es stateless. Para que el chat recuerde el contexto de
   los mensajes previos lo envolvemos con RunnableWithMessageHistory, que
   inyecta el historial en el prompt (placeholder ``chat_history``). La
   memoria se indexa por ``session_id`` para aislar sesiones distintas de
   Streamlit entre sí — si dos usuarios abren el mismo servidor, sus
   chats no se mezclan.

5. ¿Cómo decide qué tool usar? El LLM lee el SYSTEM_PROMPT (que contiene
   un mapa intención->tool) y los docstrings de las tools. Con ese contexto
   y el input del usuario, genera una llamada a tool estructurada. No hay
   árbol de decisión hardcodeado: es el modelo quien elige.
"""
# Librería estándar + dotenv para leer OLLAMA_MODEL y OLLAMA_HOST del .env.
import os
from dotenv import load_dotenv

# LangChain — construcción del agente y tools.
# ChatOllama: cliente de LangChain para el servidor Ollama local.
from langchain_ollama import ChatOllama
# ChatOpenAI: cliente compatible con la API de OpenAI. Lo reutilizamos para
# OpenRouter porque su endpoint sigue el mismo contrato (chat/completions con
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
from src.agent.prompts import SYSTEM_PROMPT
# Las 8 tools del agente, organizadas en 3 módulos (mercado, RAG, cartera).
from src.tools.market_tools import (
    get_ticker_status,
    get_ticker_history,
    get_hot_tickers,
    get_ticker_news,
)
from src.tools.rag_tool import search_finance_knowledge
from src.tools.portfolio_tools import (
    portfolio_buy,
    portfolio_sell,
    portfolio_view,
    portfolio_transactions,
    portfolio_list,
    portfolio_set_risk,
    portfolio_set_markets,
)
from src.tools.advisor_tool import (
    analyze_buy_opportunities,
    analyze_sell_candidates,
)
from src.tools.analysis_tools import (
    compare_tickers,
    get_fundamentals,
)

load_dotenv()

# Store en memoria de historiales de chat indexado por session_id.
# Es un dict de nivel módulo: persiste mientras el proceso Python esté vivo
# (no sobrevive a reinicios del Streamlit). Aceptable para el MVP; una
# mejora futura sería persistirlo en Redis/SQLite para que el usuario
# reabra la app y siga su conversación.
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
    """Devuelve (provider, model) según la configuración activa del .env.

    Útil para mostrar en la UI qué LLM está atendiendo al agente. Replica
    exactamente la misma lógica de selección/fallback que ``_build_llm`` para
    que el badge no mienta sobre lo que realmente se está usando.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            return ("ollama", os.getenv("OLLAMA_MODEL", "gemma3:4b"))
        return ("openrouter", os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"))
    return ("ollama", os.getenv("OLLAMA_MODEL", "gemma3:4b"))


def _build_ollama_llm() -> ChatOllama:
    """Construye el cliente de Ollama local.

    - num_ctx=12000: contexto suficiente para chat largo + observaciones de
      tools (tablas ASCII de cartera y chunks del RAG pueden ocupar bastante).
    - temperature=0.2: baja para que sea determinista al citar cifras y
      elegir tools. No queremos creatividad al dar precios.
    """
    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return ChatOllama(
        model=model,
        base_url=host,
        num_ctx=12000,
        # Why: extracto1.md mostró el agente fabricando precios y tablas
        # ($208.26 NVDA, $82.57 INTC, etc.) sin haber llamado a ninguna tool.
        # Bajar temperatura a 0.1 reduce alucinaciones numéricas y empuja al
        # modelo a usar las tools en lugar de "rellenar" con su memoria.
        temperature=0.1,
    )


def _build_openrouter_llm() -> ChatOpenAI:
    """Construye el cliente de OpenRouter (vía API compatible OpenAI).

    OpenRouter expone una pasarela única hacia decenas de modelos (incluidos
    varios gratis). Como su API replica el contrato de OpenAI, podemos
    reutilizar ``ChatOpenAI`` cambiando solo ``base_url`` y ``api_key``.

    - default_headers: HTTP-Referer y X-Title son opcionales, pero
      OpenRouter los usa para sus rankings públicos de uso por app.
    """
    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    site = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8501")
    app_name = os.getenv("OPENROUTER_APP_NAME", "Bot de Inversiones")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        # Why: ver _build_ollama_llm — bajamos a 0.1 para reducir invención
        # de cifras evidenciada en extracto1.md (líneas 89-99, 113-128).
        temperature=0.1,
        default_headers={"HTTP-Referer": site, "X-Title": app_name},
    )


def _build_llm():
    """Selecciona el cliente LLM según ``LLM_PROVIDER`` del .env.

    Si el proveedor es ``openrouter`` pero falta la API key, hace fallback
    silencioso a Ollama para que la app siga funcionando localmente sin
    necesidad de configurar credenciales.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY", "").strip():
            # Fallback transparente: sin API key no podemos hablar con OpenRouter.
            return _build_ollama_llm()
        return _build_openrouter_llm()
    return _build_ollama_llm()


def build_agent() -> RunnableWithMessageHistory:
    """Construye y devuelve el agente listo para ``invoke()``.

    Se llama UNA sola vez desde ``app.py`` dentro de un bloque
    ``@st.cache_resource``: así no reinstanciamos el cliente LLM ni
    recompilamos el grafo del agente en cada rerun de Streamlit (que ocurre
    a cada interacción del usuario). Importante: si cambias variables del
    .env (LLM_PROVIDER, modelos, API keys), debes reiniciar Streamlit para
    que la caché se invalide y se reconstruya el agente.
    """
    # Cliente del LLM (Ollama local u OpenRouter remoto, según .env).
    llm = _build_llm()

    # Lista de tools disponibles para el agente. El orden no importa, pero
    # los docstrings y el SYSTEM_PROMPT deben estar alineados con esta lista.
    tools = [
        get_ticker_status,
        get_ticker_history,
        get_hot_tickers,
        get_ticker_news,
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
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
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
    #    una llamada final a portfolio_view. Con 6 se cortaba a mitad de
    #    propuestas de 4-5 órdenes y dejaba la cartera incoherente.
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
    return RunnableWithMessageHistory(
        executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
