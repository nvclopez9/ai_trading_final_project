# QA Log — Bot de Inversiones

Registro de revisiones de calidad por fase. Cada entrada compara lo implementado con el plan aprobado en `C:\Users\nvclo\.claude\plans\dynamic-doodling-puppy.md`.

Formato por fase:
- **Estado**: ✅ aprobada / ⚠️ con observaciones / ❌ rechazada
- **Cumple plan**: qué items del plan se cumplieron
- **Desviaciones**: qué difiere del plan y si está justificado
- **Bugs/riesgos**: problemas detectados
- **Acciones correctivas**: tareas para el implementer antes de avanzar

---

## Fase 1 — MVP

**Estado**: ✅ (con observaciones menores)
**Fecha**: 2026-04-22

### Cumple plan
- `requirements.txt` incluye todas las dependencias listadas en el plan (streamlit, langchain, langchain-community, langchain-ollama, yfinance, chromadb, pypdf, plotly, pandas, python-dotenv).
- `.env.example` presente con `OLLAMA_MODEL=gemma3:4b`, `OLLAMA_HOST=http://localhost:11434`, `DB_PATH=data/portfolio.db` (coincide con el plan; `gemma3:4b` es el modelo acordado).
- `.gitignore` cubre `.env`, `data/portfolio.db`, `chroma/`, `__pycache__/`, `.venv/` (aunque esto estaba planificado para Fase 4, se adelantó — bien).
- `src/services/db.py` crea las tablas `positions(ticker PK, qty, avg_price)` y `transactions(id, ticker, side, qty, price, ts)` exactamente como pide el plan; usa `CREATE TABLE IF NOT EXISTS` y `Path.mkdir(parents=True, exist_ok=True)` para el directorio.
- `src/tools/market_tools.py` implementa `get_ticker_status(ticker)` y `get_ticker_history(ticker, period)` con `@tool` de `langchain_core.tools`, docstrings en español, y `try/except` que devuelve mensaje controlado para ticker inválido / error de red (cumple "manejo de ticker inválido" del plan).
- `src/agent/agent_builder.py` monta un agente con Ollama (`ChatOllama` con `num_ctx=12000`, `temperature=0.2`), registra las 2 tools de mercado, usa `ConversationBufferMemory` y retorna un `AgentExecutor`.
- `src/agent/prompts.py` define `SYSTEM_PROMPT` en español con reglas de no-inventar-cifras, honestidad ante errores y disclaimer de no-asesoramiento.
- `app.py` carga `.env`, llama a `init_db()` dentro de `@st.cache_resource`, instancia el agente una vez, mantiene historial en `st.session_state.messages`, y envuelve `agent.invoke` en `try/except` con mensaje de fallback si Ollama está apagado.
- Estructura de paquetes con `__init__.py` en `src/`, `src/services/`, `src/tools/`, `src/agent/`, `src/rag/`, `src/ui/` (los dos últimos vacíos, placeholders correctos para fases siguientes).
- Principio "no comentarios salvo imprescindibles": los ficheros no tienen ruido de comentarios, solo docstrings funcionales en las tools (necesarios para que el LLM las entienda). Bien.

### Desviaciones
- **ReAct → tool-calling**: el plan menciona "agente ReAct" pero la implementación usa `create_tool_calling_agent`. **Justificada**: con `ChatOllama` y modelos modernos (gemma3, qwen3 con tool-calling nativo) el patrón tool-calling es más fiable que ReAct basado en parsing de texto. Ningún criterio de salida exige ReAct explícitamente. Conviene documentarlo en el README en Fase 4.
- `.gitignore` y `.env.example` adelantados desde Fase 4 a Fase 1. Neutral/positivo.
- `requirements.txt` no pinea versiones (ni `langchain>=0.3`). No bloquea el MVP pero es un riesgo de reproducibilidad. Nice-to-have para Fase 4.

### Bugs / riesgos detectados
- **riesgo (medio)** — `agent_builder.py:38-43`: `ConversationBufferMemory` está deprecada en LangChain 0.3 (emite `LangChainDeprecationWarning`, migración sugerida a `RunnableWithMessageHistory`). Funciona hoy pero puede romper en una actualización. No bloquea Fase 1.
- **riesgo (medio)** — `app.py:14-17`: el agente se cachea con `@st.cache_resource`, lo que implica que `ConversationBufferMemory` es **compartida entre todas las sesiones/usuarios** del Streamlit. Para uso local monousuario es aceptable; si se despliega multi-usuario habría cross-talk de historial. No bloquea Fase 1; dejar nota para Fase 4.
- **riesgo (bajo)** — `market_tools.py:14`: `yf.Ticker(...).info` depende del scraping de Yahoo y puede ser lento (3-10 s) o devolver dicts parciales sin lanzar excepción. El código ya tiene fallback a `history(period="5d")`, lo cual es correcto. Aceptable.
- **riesgo (bajo)** — `db.py:6` y `agent_builder.py:11`: `load_dotenv()` se llama también en `app.py`. Llamadas redundantes, inocuas (no sobreescribe variables ya presentes). Estéticamente mejorable; no es bug.
- **bug cosmético (baja)** — tildes eliminadas en docstrings y system prompt (`bursatil`, `simbolo`, `espanol`, `informacion`). El LLM igualmente responde bien, pero Streamlit sí soporta UTF-8; se puede limpiar en Fase 4 sin urgencia.
- **riesgo (bajo)** — `get_ticker_status` devuelve `dict` o `str` (error). El tool-calling agent maneja ambos, pero conviene uniformar (siempre string) si se observan errores de serialización con algunos modelos de Ollama.

### Criterio de salida de Fase 1
Trazado del flujo "¿Cómo está AAPL?":
1. Streamlit captura input → `agent.invoke({"input": "..."})`.
2. Prompt ChatPromptTemplate compone sistema + historial + human + scratchpad.
3. `ChatOllama` (gemma3:4b) con tool-calling decide invocar `get_ticker_status(ticker="AAPL")`.
4. La tool llama a `yfinance`, obtiene precio real, devuelve dict español.
5. LLM resume en lenguaje natural siguiendo el system prompt.
6. Si Ollama está caído o la tool revienta → `try/except` en app.py y en la tool devuelven mensaje controlado, no stacktrace.

**Criterio cumplido** asumiendo que el usuario tiene Ollama corriendo con `gemma3:4b` descargado y red hacia Yahoo Finance. Validación manual (`streamlit run app.py` + pregunta real) pendiente por el usuario — el código es coherente para que funcione a la primera.

### Acciones correctivas requeridas antes de Fase 2
- Ninguna bloqueante. Se puede avanzar a Fase 2 (RAG + hot tickers).

### Comentarios
- Implementación limpia, compacta y alineada al plan. Las desviaciones son técnicamente mejores que lo planteado originalmente (tool-calling > ReAct para Ollama moderno).
- Para Fase 2 recordar: añadir `langchain-text-splitters` a `requirements.txt`, pullear `nomic-embed-text`, crear `data/rag_docs/`, e implementar `src/rag/ingest.py` + `src/tools/rag_tool.py`. El hot-tickers vía yfinance-screener puede ser frágil — prever fallback a lista hardcodeada (top S&P500).
- Para Fase 4 (pulido): pinear versiones en `requirements.txt`, migrar `ConversationBufferMemory` a `RunnableWithMessageHistory`, aislar memoria por sesión Streamlit, restaurar tildes en prompts/docstrings.

---

## Fase 2 — RAG + hot tickers

**Estado**: ✅ (con observaciones menores)
**Fecha**: 2026-04-22

### Cumple plan
- `requirements.txt` añade `langchain-text-splitters` y `langchain-chroma` como se anticipó en las notas de Fase 1. Resto de dependencias preservadas.
- `.env.example` añade `CHROMA_DIR=chroma` y `EMBEDDINGS_MODEL=nomic-embed-text` — consistente con los defaults que leen tanto `ingest.py` como `rag_tool.py`.
- `data/rag_docs/README.md` explica al usuario qué PDFs colocar (CNMV glosario, guía principiantes, análisis técnico, estrategias value/growth, valoración) y documenta el comando `python -m src.rag.ingest`. Correcto que el repo no incluya PDFs (copyright).
- `src/rag/ingest.py`: usa `PyPDFLoader` de `langchain_community.document_loaders`, `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)` exactamente como se pidió, `OllamaEmbeddings` desde `langchain_ollama` (paquete moderno), `Chroma.from_documents(...)` con `persist_directory` desde env. Maneja carpeta inexistente (la crea), carpeta vacía (print + exit 0), y PDFs corruptos (try/except por fichero, continúa con el resto). Return codes (0 éxito / no-PDFs, 1 todos fallaron) razonables.
- `src/tools/rag_tool.py`: tool decorada `@tool` con docstring claro que distingue uso educativo vs datos de mercado en vivo. Singleton lazy con `_vectorstore` + `_init_error` cacheados a nivel módulo (no se reabre Chroma en cada invocación). Mensajes controlados exactamente como pedían las instrucciones ("Base de conocimiento no inicializada. Ejecuta `python -m src.rag.ingest` primero."). `similarity_search(query, k=4)`. Devuelve string formateado con bloques `[i] Fuente: <pdf> (pag. N)` — permite al LLM citar la fuente como pide el prompt.
- `src/tools/market_tools.py`: `get_ticker_status` ahora devuelve **string** multilínea (resuelve la acción correctiva nice-to-have de Fase 1). `get_hot_tickers(category)` soporta `gainers` / `losers` / `actives`, intenta `yfinance.Screener` primero y cae a universo hardcodeado de 30 tickers (top S&P500) con ordenación correcta por categoría. Validación de `category` con fallback limpio.
- `src/agent/agent_builder.py`: las 4 tools están registradas (`get_ticker_status`, `get_ticker_history`, `get_hot_tickers`, `search_finance_knowledge`). Imports coherentes.
- `src/agent/prompts.py`: añade sección "Eleccion de herramienta" con criterio explícito por tipo de pregunta, y regla #6 obligando a citar el nombre del PDF al usar `search_finance_knowledge`. Cumple la consigna.

### Desviaciones
- El plan pedía "retriever tool" (genéricamente). La implementación usa `similarity_search` directo en vez de `vs.as_retriever()`. **Neutral**: para k fijo y sin filtros es equivalente y más simple. No afecta el criterio de salida.
- El nombre de la tool es `search_finance_knowledge`, no `rag_finance_knowledge` como sugería el plan. Cambio cosmético; el prompt se actualizó coherentemente. Aceptable.
- `ingest.py` hace `DOCS_DIR = Path("data/rag_docs")` relativa al CWD. Funciona si se ejecuta desde la raíz del repo (`python -m src.rag.ingest`), que es lo documentado. Nice-to-have: resolverla relativa al fichero, pero no bloquea.

### Bugs / riesgos detectados
- **riesgo (medio)** — `rag_tool.py:34`: acceso a atributo privado `_vectorstore._collection.count()`. Funciona hoy con `langchain-chroma`, pero es API no pública y puede romper en upgrades. El `try/except Exception: pass` lo mitiga (si falla la comprobación, se sigue usando el vectorstore). Aceptable; dejar nota.
- **riesgo (bajo, concurrencia)** — singleton module-level sin lock: Streamlit invoca tools desde el hilo del script principal, no desde threads paralelos (cada sesión es secuencial). Si dos peticiones entran simultáneamente al primer arranque podría haber doble inicialización inocua (último gana). No es crítico para el caso monousuario local; no es race condition peligrosa (idempotente). Aceptable.
- **riesgo (bajo)** — `ingest.py` no limpia el vectorstore previo antes de reingestar: ejecutar `ingest.py` dos veces duplica embeddings. No rompe el MVP (devolverá chunks repetidos en top-k) pero el usuario debe borrar `chroma/` manualmente para reingestar. Documentar en Fase 4 o añadir `--rebuild`. No bloquea.
- **riesgo (bajo)** — `get_hot_tickers`: el bloque de fallback itera 30 tickers llamando a `yf.Ticker(...).info` en serie; puede tardar 30–90 s cuando el screener falla. Si el LLM corta por timeout de iteración quedaría sin respuesta. Mitigación: reducir universo o paralelizar en Fase 4. Aceptable para MVP.
- **riesgo (bajo)** — `get_hot_tickers`: la detección de estructura de `Screener.get_screener` asume `dict` con clave del screener o `quotes`. Si yfinance cambia el shape, cae al fallback silenciosamente (está envuelto en try/except) — comportamiento seguro.
- **nota** — `.info` puede ser dict parcial sin `previousClose`: ya se maneja (línea 90-95 de `market_tools.py`) con fallback a `history(period="5d")`. Correcto.
- **consistencia verificada** — `ingest.py` y `rag_tool.py` leen **mismo** `CHROMA_DIR` y **mismo** `EMBEDDINGS_MODEL` vía env con idénticos defaults (`"chroma"` y `"nomic-embed-text"`). Ambos importan `Chroma` de `langchain_chroma` y `OllamaEmbeddings` de `langchain_ollama` (paquetes modernos, no `langchain_community`). Sin drift silencioso.
- **imports** — `PyPDFLoader` viene de `langchain_community.document_loaders`, que es su ubicación actual correcta (no hay loader de PDF en los paquetes partidos aún). OK.

### Acciones correctivas requeridas antes de Fase 3
- Ninguna bloqueante. Se puede avanzar a Fase 3 (cartera + gráficos).

### Comentarios
- Implementación sólida de Fase 2. La unificación de `get_ticker_status` a string resuelve el nice-to-have de Fase 1. El singleton del vectorstore está bien hecho (cachea también el error para no reintentar abrir Chroma en cada pregunta).
- Para Fase 3 recordar: `src/services/portfolio.py` (buy/sell/positions/value con precio actual vía `market_tools`), `src/tools/portfolio_tools.py` con patrón HITL (confirmación antes de ejecutar), `src/ui/portfolio_view.py` (tabla + pie Plotly + P&L), `src/ui/charts.py` (línea histórica). Registrar las nuevas tools en `agent_builder.py` y extender el system prompt con la regla de confirmación.
- Para Fase 4 (pulido) añadir a la lista: flag `--rebuild` o borrado previo en `ingest.py`, paralelizar/recortar fallback de `get_hot_tickers`, sustituir `_vectorstore._collection.count()` por API pública si LangChain la expone.

---

## Fase 3 — Cartera + gráficos

**Estado**: ✅ (con observaciones menores)
**Fecha**: 2026-04-22

### Cumple plan
- `src/services/portfolio.py`: implementa `buy`, `sell`, `get_positions`, `get_transactions`, `get_portfolio_value`. Normaliza ticker a uppercase con `strip().upper()` de forma consistente en `buy`/`sell`/`_current_price`. Persiste en `transactions` con `datetime.utcnow().isoformat(timespec="seconds")` (ISO-8601).
- `buy` calcula avg ponderado correcto: `new_avg = (cur_qty*cur_avg + qty*price) / new_qty` (línea 50). Inserta nueva fila si no existe.
- `sell` valida `qty <= cur_qty` con `ValueError`, borra fila con `DELETE FROM positions` cuando `new_qty <= 0` (línea 98-101) — no deja huérfanas. En venta parcial mantiene `avg_price` original (línea 103). Valida posición inexistente con `ValueError`.
- `get_positions` gestiona `current_price=None` devolviendo `pnl`/`pnl_pct=None` sin dividir por cero (líneas 138-145); además guarda `if cost_basis else 0.0` como red secundaria.
- `src/tools/portfolio_tools.py`: 4 tools `@tool` (`portfolio_buy`, `portfolio_sell`, `portfolio_view`, `portfolio_transactions`), todas devuelven string. Capturan `ValueError` y `Exception` y devuelven mensaje controlado con prefijo `OK`/`ERROR`.
- `src/ui/charts.py`: 3 funciones devolviendo `Figure` o `None`. `price_history_chart` envuelve todo en try/except, valida `hist.empty` y normaliza ticker. `portfolio_pnl_bar` colorea verde (`#2ca02c`) / rojo (`#d62728`) según signo de P&L.
- `src/ui/portfolio_view.py`: métricas con `st.metric` (valor total, P&L total, rentabilidad), `st.dataframe` para posiciones, `pie` + `bar` en columnas (`c1, c2`), `st.expander("Historial de transacciones")` con tabla, botón `🔄 Refrescar` que dispara `st.rerun()`. Maneja cartera vacía con `st.info` y early return. `import pandas as pd` presente (línea 1).
- `app.py`: `st.tabs(["💬 Chat", "📊 Cartera", "📈 Gráficos"])`. Tab 3 tiene `st.text_input` ticker, `st.selectbox` con opciones `["1mo","3mo","6mo","1y","5y"]` (default `6mo`), botón "Ver gráfico". `init_db()` y agente cacheado dentro de `@st.cache_resource` siguen funcionando.
- `src/agent/agent_builder.py`: 8 tools registradas (4 previas + 4 de cartera). Imports coherentes.
- `src/agent/prompts.py`: regla #7 presente — avisa al usuario antes de ejecutar `portfolio_buy`/`portfolio_sell` con frase corta y luego ejecuta directamente (no pide confirmación explícita). Sección "Eleccion de herramienta" extendida con las 4 tools nuevas.

### Desviaciones
- **OK/ERROR en vez de ✅/❌ en las tool-strings**: el plan no especifica emojis en el output de tools (el emoji estaba en la UI). Justificación técnica del implementer (tool-calling de `gemma3:4b` más fiable con ASCII) es razonable; los modelos pequeños pueden tener problemas de tokenización con emojis dentro de argumentos/observaciones. **Aceptada**. La UI mantiene emojis (🔄, 📭, 💬, 📊, 📈) donde el LLM no interviene. Para Fase 4, si se prueba con un modelo más grande (qwen2.5 / llama3.1-8b), valorar restaurar ✅/❌.
- **HITL vía prompt, no UI**: el plan decía "la UI pide OK". El implementer optó por la regla #7 del system prompt (avisa-ejecuta-confirma) sin botón de confirmación. **Aceptada con reserva**: más ágil pero elimina el cortafuegos real (si el agente malinterpreta una frase, la compra se ejecuta). Dado que es cartera simulada (no dinero real), el riesgo es bajo; dejar constancia para el README como decisión de diseño. Criterio de salida cumplido ("compra 10 AAPL → confirma → persiste → aparece en pestaña").
- `get_portfolio_value` cuenta `cost_basis` incluso cuando `market_value=None`, lo que puede inflar `total_cost` vs `total_value` si yfinance falla puntualmente (el P&L saldría falsamente muy negativo). Nice-to-have: excluir del total si `market_value is None` o duplicar con `total_cost` filtrado. No bloquea.

### Bugs / riesgos detectados
- **riesgo (medio)** — `portfolio.py:_current_price` se llama **una vez por posición** en `get_positions()`. Con N posiciones, N llamadas síncronas a `yf.Ticker(...).info` (3-10 s cada una). Cada llamada está **envuelta en try/except** y devuelve `None` (líneas 9-20), por lo que un timeout individual **no rompe el loop**. Correcto. Pero con 10+ posiciones la pestaña cartera puede tardar >30 s. Fase 4: cachear con TTL corto o paralelizar.
- **riesgo (bajo) — race condition SQLite `buy`/`sell`**: ambas funciones hacen `SELECT` + `UPDATE/DELETE` dentro del mismo `with get_conn()` pero sin `BEGIN IMMEDIATE`. En el caso monousuario Streamlit (un thread activo a la vez por sesión) es inocua. Si dos sesiones Streamlit concurrentes ejecutaran `buy` al mismo tiempo sobre el mismo ticker, podrían leer el mismo `cur_qty` y pisarse. No es escenario realista para este proyecto; dejar nota.
- **riesgo (bajo)** — `datetime.utcnow()` está deprecated en Python 3.12+ (warning). Funciona, pero preferible `datetime.now(timezone.utc)`. Fase 4.
- **riesgo (bajo)** — anotaciones `float | None`, `list[dict]` (PEP 604 / PEP 585) requieren **Python 3.10+**. No hay pin en `requirements.txt` ni `.python-version`; asumo 3.10+ dado que se usa Ollama moderno y langchain 0.3. Si el usuario tiene 3.9, rompería en import. Nice-to-have: documentar en README.
- **no bug** — `portfolio_buy` obtiene precio de mercado si no se le pasa (línea 28-31), lanza `ValueError` controlado si falla, que la tool captura y devuelve como string `ERROR ...`. Correcto.
- **no bug** — `sell` borra la fila cuando `new_qty <= 0` (usa `<=` por si flotantes dejan epsilon negativo) y fija `new_qty = 0.0` para el retorno. No quedan huérfanas.
- **cosmético** — encabezado tabla ASCII en `portfolio_view` tool-string: las columnas `Valor`/`P&L` con floats de 3+ dígitos pueden desalinearse (widths fijos). No funcional.
- **cosmético** — `price_history_chart` usa tildes en título (`"Precio histórico"`) y `portfolio_allocation_pie` usa `"Asignación"` — bien, son gráficos (no van al LLM).

### Acciones correctivas requeridas antes de Fase 4
- Ninguna bloqueante. Se puede avanzar a Fase 4 (pulido).
- Decisión sobre ✅/❌ vs OK/ERROR: **mantener OK/ERROR** mientras se use `gemma3:4b`. En Fase 4 probar con modelo mayor y, si la fiabilidad es aceptable, restaurar emojis. Documentarlo en el README como compromiso explícito.
- Decisión HITL: **aceptar HITL-vía-prompt** para este MVP. En el README, mencionar que es cartera simulada y el trade-off (UX fluida vs confirmación explícita).

### Comentarios
- Fase 3 sólida. La lógica de avg ponderado y el manejo de `current_price=None` son correctos y evitan los errores típicos (división por cero, ticker fallido rompiendo el loop). La separación service/tool/ui está bien hecha.
- Para Fase 4 añadir a la lista existente: excluir `cost_basis` del total cuando `market_value is None`, paralelizar `_current_price` en `get_positions`, migrar `datetime.utcnow()`, pinear `python>=3.10` en README/requirements, revaluar restauración de ✅/❌ con modelo mayor, revaluar HITL con botón real si se quiere reforzar.
- Criterio de salida de Fase 3 ("compra 10 AAPL → confirma → persiste → aparece en pestaña cartera con gráfico") se cumple asumiendo Ollama+yfinance operativos. Flujo trazado: prompt regla #7 → `portfolio_buy` tool → `portfolio.buy` → SQLite INSERT posición + INSERT transacción → pestaña Cartera lee `get_positions` + yfinance precio actual → métricas + dataframe + pie + bar + expander transacciones.

---

## Fase 4 — Pulido final

**Estado**: ✅ (con una observación menor)
**Fecha**: 2026-04-22

### Cumple plan
- `requirements.txt` lleva cabecera `# Requiere Python 3.10+`, versiones de LangChain pineadas a la familia 0.3.x (`langchain`, `langchain-core`, `langchain-community` con `>=0.3,<0.4`), `langchain-ollama>=0.2,<0.4`, `langchain-chroma>=0.1,<0.3`, `langchain-text-splitters>=0.3,<0.4`, y `pytest>=8.0,<9.0` añadido.
- `src/agent/agent_builder.py` migrado a `RunnableWithMessageHistory`: docstring de módulo que describe el flujo (usuario → AgentExecutor → tool → respuesta); store module-level `_SESSION_STORE: dict[str, BaseChatMessageHistory]`; función `get_session_history(session_id)` con `InMemoryChatMessageHistory`; `build_agent()` retorna `RunnableWithMessageHistory(executor, get_session_history, input_messages_key="input", history_messages_key="chat_history")`. Sin rastros de `ConversationBufferMemory` en `src/` (grep solo lo encuentra en el propio `qa_log.md` histórico).
- `app.py`: `import uuid` arriba; bloque `if "session_id" not in st.session_state: st.session_state.session_id = str(uuid.uuid4())`; `agent.invoke({"input": user_input}, config={"configurable": {"session_id": st.session_state.session_id}})`. Manejo de error envuelve el invoke y muestra mensaje controlado.
- `src/services/portfolio.py`: imports `from concurrent.futures import ThreadPoolExecutor` y `from datetime import datetime, timezone`. `get_positions` paraleliza `_current_price` con `ThreadPoolExecutor(max_workers=8)` cuando `len(tickers) > 3` (líneas 133-137), serial en otro caso. `buy` y `sell` usan `datetime.now(timezone.utc).isoformat(timespec="seconds")` (líneas 57, 110). `get_portfolio_value` construye `stale_tickers: list[str]` con los tickers sin `market_value`, los excluye del total y los retorna en el dict (líneas 193-208).
- `src/tools/portfolio_tools.py`: constantes `OK_ICON = "✅"` y `ERR_ICON = "❌"` al tope del módulo. Todos los mensajes de éxito/error las usan. `portfolio_view` muestra una línea adicional `"Nota: sin precio actual para <tickers> (excluidos del total)."` cuando `totals.get("stale_tickers")` no está vacío (líneas 83-87).
- Tildes restauradas en prompts y docstrings: `src/agent/prompts.py` conserva "capitalización", "búsqueda", "categorías", "análisis", "información"; las tools de portfolio y market usan "posición", "búsqueda semántica", "histórico", "último", "rentabilidad". Grep de `[áéíóúñÁÉÍÓÚÑ]` sobre `src/` devuelve 69 coincidencias en 9 ficheros — consistente.
- `tests/conftest.py` añade la raíz del proyecto al `sys.path` para que `from src...` funcione al ejecutar pytest desde la raíz.
- `tests/test_tools.py` incluye los 4 tests pedidos: `test_get_ticker_status_invalid` (smoke), `test_portfolio_buy_sell_flow` (avg ponderado, venta parcial, cierre), `test_sell_over_qty_raises` (ValueError), `test_portfolio_value_with_stale` (stale_tickers poblado, total excluye stale). Fixtures `tmp_db` (monkeypatchea `db_module.DB_PATH` a tmp_path) y `fixed_price` (monkeypatchea `portfolio._current_price`) correctas.
- `README.md` ampliamente reescrito (268 líneas, >150 solicitadas). Secciones presentes: Problema, Arquitectura (ASCII art), Flujo del agente, Las 8 tools (tabla), RAG, Tecnologías, Requisitos, Instrucciones paso a paso, Ejemplos de preguntas, Cumplimiento del enunciado (tabla), Limitaciones, Mejoras futuras, Estructura del proyecto, Troubleshooting, Tests, Licencia.

### Desviaciones
- Ninguna funcional respecto al plan de Fase 4.

### Bugs/riesgos
- ⚠️ **README.md está codificado en UTF-16 LE (con BOM)**, no en UTF-8. `Grep` lo identifica explícitamente como "binary file" y al leerlo con herramientas orientadas a UTF-8 cada carácter aparece separado por null-bytes. Impacto: GitHub detecta UTF-16 y lo renderiza, pero las tildes y emojis pueden salir como `�` al abrirlo con editores que asumen UTF-8, y `diff`/`wc` dan resultados engañosos. Recomendación fuerte: reescribir el fichero en UTF-8 sin BOM antes de subir al repo final.
- Nota menor: `get_hot_tickers` en modo fallback sigue siendo serial (documentado en README > Limitaciones). No bloqueante.

### Acciones correctivas
- [ ] Reconvertir `README.md` a UTF-8 sin BOM (VSCode → "Save with Encoding → UTF-8" o `iconv -f UTF-16 -t UTF-8`). Verificar que las tildes y los emojis (💬 📊 📈 ✅ ❌) se vean correctamente.
- [ ] (Opcional) Ejecutar `pytest tests/` localmente para confirmar que los 4 tests pasan antes del commit final.

### Checklist final del enunciado

| Requisito | Cumple | Evidencia |
|---|---|---|
| ≥1 agente LangChain | ✅ | `src/agent/agent_builder.py:69` (`create_tool_calling_agent`) + `AgentExecutor` l.71, envuelto en `RunnableWithMessageHistory` l.80 |
| ≥2 tools | ✅ | 8 tools: `get_ticker_status`, `get_ticker_history`, `get_hot_tickers`, `search_finance_knowledge`, `portfolio_buy`, `portfolio_sell`, `portfolio_view`, `portfolio_transactions` (registradas en `agent_builder.py:49-58`) |
| RAG doc textual | ✅ | `src/rag/ingest.py` (PyPDFLoader + RecursiveCharacterTextSplitter + Chroma + nomic-embed-text); `src/tools/rag_tool.py:search_finance_knowledge` consulta vectorstore `./chroma/` sobre PDFs en `data/rag_docs/` |
| Agente integrado en flujo | ✅ | `app.py:23` construye el agente; `app.py:49-52` lo invoca con `session_id` desde el chat de Streamlit, mostrando la respuesta en `st.chat_message` |
| Persistencia/servicio externo | ✅ | SQLite (`src/services/db.py`, `portfolio.db`), Yahoo Finance vía `yfinance` (`src/tools/market_tools.py`), ChromaDB persistida en `./chroma/` |
| Repo GitHub con README | ⚠️ | `README.md` existe (268 líneas, todas las secciones) pero en UTF-16 LE — corregir encoding antes de push |
| Manejo de errores | ✅ | `try/except` en las 8 tools devolviendo string controlado con `ERR_ICON`; `try/except` en `app.py:47-61` con mensaje "Verifica que Ollama esté en ejecución"; `ValueError` propagados desde `portfolio.buy/sell` y capturados en las tools |

### Comentarios
- Fase 4 bien ejecutada. La migración a `RunnableWithMessageHistory` sigue la recomendación oficial de LangChain 0.3 (ConversationBufferMemory está deprecated); el `session_id` por uuid garantiza aislamiento entre tabs/usuarios. La paralelización de precios con umbral `>3` es un buen trade-off (no vale la pena pagar el overhead del executor para 1-2 posiciones). Los 4 tests cubren los casos críticos (inválido, flujo feliz, error de negocio, degradación con stale).
- Único bloqueante antes del push final: el encoding del README. Una vez convertido a UTF-8, el proyecto cumple el enunciado íntegramente.

---

## Fase 5 — Mejoras UI/UX + multipage

**Estado**: ✅
**Fecha**: 2026-04-24

### Cumple
- Migración correcta a Streamlit Multipage (`app.py` Home + 5 páginas en `pages/`). Cada página hace `st.set_page_config` con `page_title` y `page_icon`.
- Singleton del agente en `src/agent/singleton.py` con `@st.cache_resource`, invocado desde cada página (evita reinicializar Ollama al navegar).
- `session_state` usado como bus entre páginas: `active_ticker`, `prefill_prompt`, `pending_prompt`, `session_id`, `messages`. Coincide con el contrato del `DISEÑO_UI.md §7.4`.
- Tema dark (`#0E1117`), `gatherUsageStats = false` y `[server] headless = true` configurados en `.streamlit/config.toml`.
- 9 tools registradas en `agent_builder.py` coherentes con la lista del `SYSTEM_PROMPT` (incluye la nueva `get_ticker_news`).
- README.md ahora en UTF-8 (observación de Fase 4 resuelta).
- No hay imports muertos en `app.py` del Home tras la migración (no se importa `render_portfolio_tab`, `price_history_chart`, etc.: cada página se encarga).
- `_process_user_message` vive únicamente en `pages/1_Chat.py`; no hay duplicado en `app.py`.
- Botones "Ver" en `pages/4_Hot.py` con keys prefijadas por tab (`hot_{title}_{ticker}`) — no colisionan entre gainers/losers/actives.

### Desviaciones
- `src/ui/charts.py` usaba `plotly_white` en lugar de un tema coherente con la app (dark). Menor — **corregido** (fix aplicado).
- `src/ui/portfolio_view.py` formateaba métricas con `f"${x:.2f}"` en lugar de los helpers `fmt_money`/`fmt_pct` centralizados. Menor — **corregido**.
- El wireframe del DISEÑO_UI §6.3 sugiere timeframes `1D 5D 1M 6M YTD 1A 5A`; la implementación usa el subconjunto de yfinance `1mo 3mo 6mo 1y 5y`. Aceptable (alineado con `get_ticker_history`).
- Emojis en `pages/*.py` sin prefijo numérico-emoji canónico del DISEÑO (`1_💬_Chat.py` → `1_Chat.py`). Decisión del implementer (evitar problemas con Windows/git). Aceptable; emoji presente en `page_icon`.

### Bugs detectados y estado

| Bug | Severidad | Estado |
|---|---|---|
| `pages/2_Mercado.py` — botón "↪ Continuar en el chat" anidado dentro del `if st.button("💡 Explícame...")`; tras el rerun del primer clic el segundo botón nunca llega a renderizarse y es inalcanzable | media | fixed |
| `src/ui/portfolio_view.py` — métricas con formato `${x:.2f}` ignorando los helpers es_ES del resto de la app (inconsistencia visual) | baja | fixed |
| `src/ui/charts.py` — tema `plotly_white` cuando la app es dark (contraste pobre en gráficos) | baja | fixed |
| Falta smoke test para `get_ticker_news` (nueva tool sin cobertura) | baja | fixed (tests/test_tools.py → `test_get_ticker_news_smoke`) |
| `src/tools/market_tools._fetch_fallback_quotes` se importa con `# type: ignore` desde `app.py` y `pages/4_Hot.py` (underscore = privado) | baja | documentado — dejar para refactor posterior (promover a pública o centralizar) |
| Duplicación ligera de `_snapshot()` (cacheada) entre `app.py` y `pages/4_Hot.py` | baja | documentado — no es urgente, esfuerzo M para centralizar en `src/services` |

### Fixes aplicados

- `pages/2_Mercado.py:145-170` — Botón "Explícame" refactorizado para persistir la respuesta en `st.session_state[explain_key]` y que el botón "↪ Continuar en el chat" siga visible tras el rerun; además se añaden `key` únicos por ticker a ambos botones para evitar colisiones si el usuario cambia de ticker.
- `src/ui/portfolio_view.py` — Import de `fmt_money`/`fmt_pct` desde `src.ui.components`; las tres `st.metric` superiores usan ya los helpers centralizados (formato es_ES, mismos símbolos que Home y Mercado).
- `src/ui/charts.py` — `template="plotly_white"` → `template="plotly_dark"` en los 3 gráficos (price history, pie, bar) para coherencia con el tema oscuro global.
- `tests/test_tools.py` — Nuevo `test_get_ticker_news_smoke` que monkeypatchea `fetch_ticker_news` para no depender de red y valida (a) output con items contiene titular + ticker, (b) output con lista vacía contiene ticker y es string (nunca excepción).

### Nice-to-have no aplicados (para futuras iteraciones)

- Centralizar `_fetch_fallback_quotes` (o un wrapper público `get_market_snapshot`) en `src/services/market_snapshot.py` y eliminar el `# type: ignore` en Home y Hot.
- En `pages/2_Mercado.py`, exponer los timeframes del wireframe (`1D/5D/YTD/1A`) traduciéndolos al vocabulario de yfinance (`1d`, `5d`, `ytd`, `1y`).
- Persistir `active_ticker` entre sesiones (decisión abierta del DISEÑO; hoy sólo vive en memoria).
- En `portfolio_view`, reutilizar también los helpers para las celdas del DataFrame (`Precio actual`, `P&L`), no sólo las métricas de cabecera.
- `get_hot_tickers` fallback sigue siendo serial (documentado desde Fase 2); paralelizar con `ThreadPoolExecutor` daría 3-5× más velocidad cuando Screener falla.

### Tests

- pytest: **5 passed / 0 failed** (`tests/test_tools.py` — los 4 previos + `test_get_ticker_news_smoke`).
- py_compile: **OK** sobre `app.py`, las 5 páginas, `src/agent/*.py`, `src/services/*.py`, `src/tools/*.py`, `src/ui/*.py`, `src/ui/components/__init__.py`, `src/rag/ingest.py`.

### Comentarios

- La migración multipage quedó limpia: sin imports residuales ni duplicación de `_process_user_message`. Las claves de session_state están bien alineadas con el contrato del DISEÑO_UI.
- El bug del botón "Continuar en el chat" era el único con impacto funcional real (el usuario nunca podía navegar al chat desde "Explícame"); los demás fixes son de coherencia visual y cobertura de tests.
- El proyecto está listo para demo: 9 tools, 5 páginas navegables, tema coherente, tests verdes.
