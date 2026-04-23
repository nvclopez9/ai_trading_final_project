# Plan de mejoras — Bot de Inversiones

> Propuestas priorizadas para la siguiente iteración. Cada mejora incluye: motivación, diseño técnico, ficheros afectados, estimación de esfuerzo (S/M/L) y riesgos.
>
> **Estado de partida (2026-04-23)**: MVP cerrado tras Fase 4 del plan `dynamic-doodling-puppy.md`. Stack: Streamlit + LangChain 0.3 (tool-calling) + Ollama (gemma3:4b) + Chroma + yfinance + SQLite. 8 tools registradas, 3 pestañas (Chat, Cartera, Gráficos), tests 4/4 verdes. Ver `README.md`, `qa_log.md` y `bug_report.md`.
>
> **Criterio de priorización**: (1) impacto visible en la demo de clase, (2) factibilidad sin rehacer arquitectura, (3) defendibilidad técnica en la exposición.

---

## Indice

- [Prioridad 1 — Impacto visible en demo](#prioridad-1--impacto-visible-en-demo)
- [Prioridad 2 — Experiencia de chat](#prioridad-2--experiencia-de-chat)
- [Prioridad 3 — Análisis y visualización](#prioridad-3--análisis-y-visualización)
- [Prioridad 4 — Calidad y robustez](#prioridad-4--calidad-y-robustez)
- [Prioridad 5 — Multiusuario / despliegue](#prioridad-5--multiusuario--despliegue)
- [Mejoras transversales de UI/UX](#mejoras-transversales-de-uiux)
- [Tabla resumen](#tabla-resumen)
- [Orden de ataque sugerido](#orden-de-ataque-sugerido)

---

## Prioridad 1 — Impacto visible en demo

### 1.1 Buscador de tickers con autocompletado

**Motivación**: el usuario no siempre recuerda el símbolo exacto (ej. "Iberdrola" → `IBE.MC`, "LVMH" → `MC.PA`). Hoy la pestaña `📈 Gráficos` y las tools de cartera asumen que el usuario ya conoce el ticker. Un buscador por nombre de empresa elimina fricción y es un feature muy visible en la demo.

**Diseño**:
- **Fuente de datos**: CSV local `data/tickers/universe.csv` con columnas `ticker,name,exchange,currency`. Poblarlo una vez con un universo razonable (~1500 filas): S&P 500 + IBEX 35 + Euro Stoxx 50 + FTSE 100 + Nasdaq 100. Se puede generar offline con un script `scripts/build_ticker_universe.py` que use `yfinance.Tickers` o listas públicas (Wikipedia CSV).
- **Búsqueda fuzzy**: `rapidfuzz.process.extract(query, choices, limit=10, scorer=WRatio)` sobre la columna `name + ticker`. Latencia <20 ms sobre 1500 filas.
- **Componente Streamlit**: un `st.text_input("Buscar empresa…")` que en cada pulsación de tecla (via `on_change` callback) filtra y actualiza un `st.selectbox` con los top-10 matches formateados como `"AAPL — Apple Inc. (NASDAQ)"`. Al seleccionar, el ticker se copia a `st.session_state.chart_ticker`.
- **Ubicación**: (a) dentro de la pestaña `📈 Gráficos` reemplazando el actual `st.text_input("Ticker")`, (b) en un `st.sidebar.expander("🔎 Buscar ticker")` accesible desde cualquier pestaña.
- **Nueva tool opcional** `resolve_ticker(company_name)` que usa el mismo índice: permite al agente responder "¿cómo está Iberdrola?" resolviendo a `IBE.MC` antes de llamar a `get_ticker_status`.

**Ficheros afectados**:
- Nuevo: `data/tickers/universe.csv`, `scripts/build_ticker_universe.py`, `src/services/ticker_index.py` (carga + búsqueda fuzzy cacheada con `@lru_cache`).
- Nuevo: `src/ui/ticker_search.py` (componente reutilizable).
- Modificar: `app.py` (tab 3 + sidebar), `src/agent/agent_builder.py` (registrar tool), `src/agent/prompts.py` (regla de uso), `requirements.txt`.

**Dependencias nuevas**: `rapidfuzz>=3.0,<4.0`.

**Esfuerzo**: M (3-4 h incluyendo poblar el CSV).

**Riesgos**:
- El universo inicial puede quedarse corto (usuario pregunta por un ticker OTC no listado). Mitigación: fallback a pasar el texto crudo a yfinance si la búsqueda fuzzy score <50.
- Tickers internacionales con sufijos `.MC`, `.PA`, `.L`: documentar en la columna `exchange` y en la UI.

**Cómo demo-arlo**: teclear "apple" → aparecen AAPL, AAPL.MX, etc.; seleccionar → el gráfico se carga; también preguntar al chat "¿cómo va Iberdrola?" y ver que resuelve a IBE.MC.

---

### 1.2 Noticias reales por ticker

**Motivación**: requisito explícito del usuario. Ver un precio sin el contexto de la noticia del día es medio feature; añade realismo al bot y da pie a preguntas naturales ("¿por qué NVDA baja hoy?"). Aparece ya en el plan original como "Mejora futura" pero no se implementó.

**Diseño**:
- **Fuente recomendada (sin API key)**: `yfinance.Ticker(ticker).news` — devuelve una lista de dicts con `title`, `publisher`, `link`, `providerPublishTime` (epoch), `thumbnail`. Gratis, sin key, mismo stack que el resto.
- **Alternativa si yfinance.news cae**: RSS de Yahoo Finance (`https://feeds.finance.yahoo.com/rss/2.0/headline?s=<TICKER>&region=US&lang=en-US`) parseado con `feedparser`. Documentada en el docstring como fallback.
- **Nueva tool** `get_ticker_news(ticker: str, limit: int = 5) -> str`:
  ```
  get_ticker_news("AAPL", 5)
  → "Noticias recientes de AAPL:
     [1] 2026-04-22 | Reuters — Apple unveils new iPad Pro
         https://...
     [2] ..."
  ```
  Formato texto plano (coherente con el resto de tools — el LLM resume bien y evita problemas de serialización con gemma3:4b).
- **Componente UI**: en la pestaña `📈 Gráficos`, debajo del gráfico, un bloque "📰 Noticias recientes" que llama a la misma función del servicio y renderiza cards con `st.container(border=True)` y links clickables. Cachear 10 min con `@st.cache_data(ttl=600)` para no saturar Yahoo.

**Ficheros afectados**:
- Nuevo: `src/services/news.py` (wrapper sobre `yfinance.news` + fallback RSS).
- Nuevo: `src/tools/news_tool.py` (@tool `get_ticker_news`).
- Nuevo: `src/ui/news_panel.py` (componente Streamlit).
- Modificar: `app.py` (tab 3), `src/agent/agent_builder.py`, `src/agent/prompts.py` (añadir regla "si el usuario pregunta por noticias/novedades de un ticker, usa `get_ticker_news`"), `README.md` (actualizar lista a 9 tools).

**Dependencias nuevas**: `feedparser>=6.0,<7.0` (opcional, solo para fallback).

**Esfuerzo**: S (2 h).

**Riesgos**:
- `yfinance.news` a veces devuelve lista vacía para tickers pequeños o no-US. Mitigar con fallback RSS y mensaje controlado.
- Las noticias están mayoritariamente en inglés. Documentar la limitación; traducirlas con el LLM local es caro y lento, no merece la pena en demo.
- Rate limit implícito de Yahoo: cache TTL 10 min por ticker.

**Cómo demo-arlo**: preguntar al chat "¿qué noticias hay de NVDA?" → el agente llama a la tool → lista con titulares + links; pestaña Gráficos muestra las mismas noticias debajo del chart.

---

### 1.3 Guía de uso embebida en la UI

**Motivación**: requisito explícito del usuario. En la demo, el profesor o los compañeros abrirán la app y no sabrán por dónde empezar. Un onboarding breve y una pestaña `❓ Ayuda` siempre disponible es el diferencial entre un proyecto "funciona" y un proyecto "se entiende solo".

**Diseño**:
- **Nueva pestaña `❓ Ayuda`** (cuarta en `st.tabs`). Contenido:
  1. **Qué puedo preguntarle** — 4 categorías con 2-3 ejemplos literales cada una (clickables con `st.button` que copian el texto al `st.session_state.pending_prompt` y hacen `st.rerun()` llevando a la pestaña Chat):
     - **Mercado**: "¿Cómo está Apple?", "Dame el histórico de MSFT a 1 año".
     - **Tickers calientes**: "Top gainers de hoy", "Mayores caídas".
     - **Educación**: "¿Qué es el P/E ratio?", "Explícame value investing".
     - **Cartera**: "Compra 10 MSFT", "¿Cómo va mi cartera?", "Últimas transacciones".
     - **Noticias** (tras 1.2): "Noticias de NVDA".
  2. **Cómo interpretar respuestas** — breve glosario de elementos que aparecen en la salida del agente (citas de fuente RAG, mensajes `✅ OK` / `❌ ERROR` de las tools de cartera, nota "sin precio actual").
  3. **Qué NO hace** — disclaimers: cartera simulada, no conecta con broker real, no es asesoramiento financiero.
  4. Link al README para detalles técnicos.
- **Onboarding primer uso**: al arrancar, si `"first_visit" not in st.session_state`, mostrar `st.toast("👋 ¡Bienvenido! Visita la pestaña ❓ Ayuda para ejemplos de preguntas.", icon="👋")` durante 5 s y marcar `st.session_state.first_visit = False`.
- **Sidebar permanente** con un `st.sidebar.markdown` breve ("Pregúntale al bot sobre precios, noticias, conceptos o tu cartera") + link a la pestaña Ayuda.

**Ficheros afectados**:
- Nuevo: `src/ui/help_tab.py`.
- Modificar: `app.py` (añadir tab4, sidebar, toast first-visit).

**Dependencias nuevas**: ninguna.

**Esfuerzo**: S (1.5-2 h).

**Riesgos**: mínimos. Posible desincronización con el system prompt si se añaden/quitan tools sin actualizar la ayuda — mitigación: documentar en `prompts.py` que cualquier cambio de tool debe reflejarse en `help_tab.py`.

**Cómo demo-arlo**: abrir la app → toast de bienvenida → click en pestaña Ayuda → click en el ejemplo "¿Qué es el P/E ratio?" → salta al chat con la pregunta ya enviada.

---

## Prioridad 2 — Experiencia de chat

### 2.1 Sugerencias rápidas (chips) en el chat

**Motivación**: reducir la fricción de escribir. Los chips son un patrón reconocible (ChatGPT, Gemini) que muestra al usuario qué puede preguntar sin leerse la ayuda.

**Diseño**:
- Encima del `st.chat_input`, renderizar 4-6 `st.button` en columnas con ejemplos rotativos. Al pulsar, se guarda el texto en `st.session_state.pending_prompt` y se llama a `st.rerun()`; en el siguiente rerun, si `pending_prompt` existe, se inyecta como si el usuario lo hubiera tecleado.
- Los chips cambian según contexto: si la cartera está vacía, sugerir "Compra 10 AAPL"; si tiene posiciones, sugerir "¿Cómo va mi cartera?"; primer mensaje → sugerir pregunta educativa.

**Ficheros afectados**: `app.py` (tab 1), opcionalmente `src/ui/chat_chips.py`.

**Dependencias nuevas**: ninguna.

**Esfuerzo**: S (1 h).

**Riesgos**: ninguno relevante.

**Cómo demo-arlo**: abrir la app → ver 4 chips → click → el chat procesa la pregunta.

---

### 2.2 Streaming de respuestas

**Motivación**: gemma3:4b tarda 5-15 s en responder en CPU. Sin streaming, el usuario ve un spinner durante todo ese tiempo. Con streaming tokenizado, ve el texto apareciendo progresivamente — sensación de inmediatez que impresiona en demo.

**Diseño**:
- Sustituir `agent.invoke(...)` por `agent.stream(...)` (o `agent.astream_events` para capturar también llamadas a tools). `RunnableWithMessageHistory` expone `.stream()` igual que `.invoke()`.
- Renderizar con el patrón Streamlit: `placeholder.markdown(partial_text + "▌")` dentro del loop, retirando el cursor al final.
- **Reto**: el output de un `AgentExecutor` streamea eventos (tool_start, tool_end, on_llm_new_token), no solo tokens finales. Filtrar por `event == "on_chat_model_stream"` y concatenar `chunk.content`.

**Ficheros afectados**: `app.py` (tab 1), posiblemente `src/agent/agent_builder.py` para exponer un wrapper.

**Dependencias nuevas**: ninguna.

**Esfuerzo**: M (3 h, principal coste = entender `astream_events`).

**Riesgos**:
- Algunos modelos Ollama no hacen streaming fiable cuando hay tool-calling (se espera a completar todo antes de emitir). Probar con gemma3:4b y, si falla, documentar como limitación.
- Los errores mid-stream son más difíciles de manejar; mantener el try/except amplio.

**Cómo demo-arlo**: pregunta larga tipo "explícame value investing con 5 ejemplos" → el texto aparece token a token en vez de de golpe.

---

### 2.3 Indicador de tool en uso

**Motivación**: didáctico para la defensa del proyecto. Mostrar "🔧 Llamando a `get_ticker_status`…" mientras el agente razona hace visible lo que hoy es una caja negra. Útil para demostrar al profesor que el agente realmente llama tools.

**Diseño**:
- Usar `astream_events` (ya introducido en 2.2) para capturar `on_tool_start` y `on_tool_end`. En un `st.status` dinámico encima del placeholder de respuesta, mostrar un log tipo:
  ```
  🔧 get_ticker_status(ticker="AAPL") → ejecutando…
  ✅ get_ticker_status → 312 chars
  🔧 search_finance_knowledge(query="P/E ratio") → ejecutando…
  ✅ search_finance_knowledge → 1.2 KB
  ```
- Colapsable (`st.status(..., expanded=False)`) para no saturar a usuarios no técnicos.

**Ficheros afectados**: `app.py` (tab 1).

**Dependencias nuevas**: ninguna.

**Esfuerzo**: S-M (2 h, dependiente de 2.2).

**Riesgos**: ruido visual si una pregunta dispara 3-4 tools. Mantener colapsado por defecto.

**Cómo demo-arlo**: preguntar "compara Apple y Microsoft" → ver en directo las llamadas paralelas a `get_ticker_status` para ambos tickers.

---

## Prioridad 3 — Análisis y visualización

### 3.1 Comparador de tickers

**Motivación**: una pregunta natural ("¿Apple o Microsoft?") hoy requiere dos turnos del chat. Un comparador lado-a-lado en la UI es muy visual en demo.

**Diseño**:
- Nueva subsección en `📈 Gráficos` o pestaña dedicada `⚖️ Comparar`. Dos (o N hasta 4) selectores de ticker con el buscador de 1.1. Selector de periodo común.
- Gráfico Plotly con **precios normalizados** (`price[t] / price[0] * 100`) para comparar rentabilidades relativas, no precios absolutos.
- Tabla comparativa con columnas: Precio actual, Cambio 1d, P/E, Market cap, Rentabilidad periodo. Datos via `get_ticker_status` + `get_ticker_history` existentes.

**Ficheros afectados**: nuevo `src/ui/compare_view.py`, `app.py`, `src/ui/charts.py` (helper `normalized_price_comparison_chart`).

**Dependencias nuevas**: ninguna.

**Esfuerzo**: M (3 h).

**Riesgos**: coste de latencia (N tickers × yfinance). Cachear con `@st.cache_data(ttl=300)`.

**Cómo demo-arlo**: seleccionar AAPL, MSFT, NVDA, periodo 1y → gráfico normalizado muestra quién batió a quién.

---

### 3.2 Indicadores técnicos básicos en los gráficos

**Motivación**: value-add educativo (media móvil, RSI) que conecta con los PDFs del RAG. "El bot sabe lo que es una SMA-50 porque lo ha leído en el PDF, y te la dibuja".

**Diseño**:
- En `src/ui/charts.py:price_history_chart`, añadir checkboxes opcionales en la UI ("SMA 20", "SMA 50", "Bollinger ±2σ"). Calcular con pandas (`df['Close'].rolling(20).mean()`), no añadir librería técnica pesada.
- Renderizar como líneas/bandas superpuestas con Plotly.

**Ficheros afectados**: `src/ui/charts.py`, `app.py` (tab 3).

**Dependencias nuevas**: ninguna (pandas basta).

**Esfuerzo**: S (1.5 h).

**Riesgos**: mínimos. No complicar con RSI/MACD aún; SMA cubre 80% del valor didáctico.

**Cómo demo-arlo**: ver gráfico de AAPL con SMA-50 y comentar "el precio ha cruzado la media móvil al alza" — aterriza el concepto del RAG.

---

### 3.3 Historial temporal del valor de la cartera

**Motivación**: hoy `portfolio_view` muestra fotografía actual. Falta la **evolución** del valor total de la cartera a lo largo del tiempo — típico dashboard de broker.

**Diseño**:
- Al ejecutar `buy`/`sell`, añadir una fila a una nueva tabla `portfolio_snapshots(ts, total_cost, total_value)` con el valor justo después de la operación. Opcionalmente, un "snapshotter" diario que se dispara al abrir la app si `date(last_snapshot) < today()`.
- Gráfico Plotly `step` o `line` con la evolución. Mostrar en la pestaña Cartera encima de la tabla.

**Ficheros afectados**: `src/services/db.py` (migración schema — añadir tabla, ADD COLUMN idempotente), `src/services/portfolio.py` (snapshot post-buy/sell), `src/ui/portfolio_view.py`, `src/ui/charts.py`.

**Dependencias nuevas**: ninguna.

**Esfuerzo**: M (3 h, principal coste = migración segura del esquema existente).

**Riesgos**:
- Migración de BD: usar `CREATE TABLE IF NOT EXISTS` y `PRAGMA user_version` para hacer idempotente en usuarios con BD anterior.
- Primer uso tras actualizar: el gráfico sale vacío hasta la primera operación. Mostrar mensaje pedagógico.

**Cómo demo-arlo**: 3 compras seguidas → ver cómo sube el valor total en el gráfico evolutivo.

---

## Prioridad 4 — Calidad y robustez

### 4.1 Tests end-to-end con mocks de Ollama

**Motivación**: hoy los 4 tests cubren tools/servicios en aislamiento, pero no el flujo agente → tool → servicio. Un test E2E con `FakeListChatModel` de LangChain permite validar que el prompt + mapping de intención → tool funcionan.

**Diseño**:
- Nuevo `tests/test_agent_flow.py`: usar `langchain_core.language_models.fake.FakeMessagesListChatModel` configurado para emitir una respuesta con `tool_calls` predefinido. Construir el `AgentExecutor` inyectando este fake en vez de `ChatOllama`.
- 3 tests: (a) pregunta de mercado → llama a `get_ticker_status`; (b) pregunta educativa → llama a `search_finance_knowledge`; (c) compra → llama a `portfolio_buy` y persiste en SQLite tmp.

**Ficheros afectados**: nuevos `tests/test_agent_flow.py` y posiblemente `src/agent/agent_builder.py` (aceptar `llm` inyectable en vez de hardcodear `ChatOllama`).

**Dependencias nuevas**: ninguna (ya está en `langchain-core`).

**Esfuerzo**: M (3-4 h).

**Riesgos**: tocar `agent_builder.py` con cuidado de no romper la interfaz actual. Añadir parámetro `llm` con default a la fábrica actual.

**Cómo demo-arlo**: `pytest tests/ -v` muestra 7/7 passed incluyendo el flujo E2E.

---

### 4.2 Métricas de latencia y tokens

**Motivación**: útil para la defensa ("¿cuánto tarda?", "¿cuántos tokens por respuesta?"). Fácil de añadir con callbacks de LangChain.

**Diseño**:
- Callback handler `src/agent/metrics.py` que registra `on_llm_start`/`on_llm_end` timestamps, tokens in/out (`response.usage_metadata` en Ollama). Loggea en un fichero JSONL `logs/metrics.jsonl`.
- Panel opcional en el sidebar con `st.metric("Última respuesta", f"{latency:.1f}s")` + histograma agregado.

**Ficheros afectados**: nuevo `src/agent/metrics.py`, modificar `agent_builder.py` (registrar callback), `app.py`.

**Dependencias nuevas**: ninguna.

**Esfuerzo**: S-M (2 h).

**Riesgos**: Ollama puede no reportar `usage_metadata` completa. Degradar a solo latencia si tokens=None.

**Cómo demo-arlo**: pregunta → en el sidebar aparece "9.3 s · 847 tokens".

---

### 4.3 Logs estructurados

**Motivación**: hoy los `print`/excepciones van a stdout sin estructura. Para depurar una demo fallida, logs JSON con niveles son mucho mejores.

**Diseño**:
- Módulo `src/logging_config.py` con `logging.basicConfig` + formatter JSON (`python-json-logger`). Niveles: INFO para flujo normal, WARNING para fallback yfinance, ERROR para excepciones. Fichero rotativo `logs/app.log` (RotatingFileHandler, 5 MB × 3).
- Reemplazar `print` en tools/servicios por `logger.info/warning/error`.

**Ficheros afectados**: nuevo `src/logging_config.py`, barrido por `src/**/*.py` reemplazando prints (~10 sitios).

**Dependencias nuevas**: `python-json-logger>=2.0,<3.0`.

**Esfuerzo**: S (1.5 h).

**Riesgos**: ninguno.

**Cómo demo-arlo**: `tail -f logs/app.log` durante una interacción → ver eventos estructurados.

---

## Prioridad 5 — Multiusuario / despliegue

### 5.1 Autenticación básica

**Motivación**: hoy cualquiera que abra la URL ve la cartera de cualquiera (BD única). Para una demo compartida en red, auth simple aporta credibilidad.

**Diseño**:
- `streamlit-authenticator` con config YAML (`auth_config.yaml`, gitignored) y usuarios hasheados bcrypt.
- El `username` autenticado se usa como namespace tanto para el `session_id` del agente como para el `DB_PATH` (ej. `data/portfolios/<user>.db`).

**Ficheros afectados**: `app.py`, `src/services/db.py` (DB_PATH parametrizable), nuevo `auth_config.yaml.example`.

**Dependencias nuevas**: `streamlit-authenticator>=0.3,<0.5`.

**Esfuerzo**: M (3-4 h).

**Riesgos**: complejiza el arranque. Documentar bien en README. Mantener un modo `AUTH_ENABLED=false` por defecto para local dev.

**Cómo demo-arlo**: abrir app → login → ver que cada usuario tiene su cartera aislada.

---

### 5.2 Dockerfile + docker-compose

**Motivación**: portabilidad y reproducibilidad. El profesor puede levantar la app con `docker compose up` sin instalar Python ni Ollama.

**Diseño**:
- `Dockerfile` Python 3.12-slim con dependencias pineadas, copia el código, expone 8501, CMD `streamlit run app.py`.
- `docker-compose.yml` con dos servicios: `app` (el anterior) y `ollama` (imagen oficial `ollama/ollama`) con volumen persistente. Red compartida; `OLLAMA_HOST=http://ollama:11434`.
- Script `entrypoint.sh` que hace `ollama pull gemma3:4b` y `nomic-embed-text` en el primer arranque si faltan.

**Ficheros afectados**: nuevos `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `entrypoint.sh`, sección README.

**Dependencias nuevas**: ninguna (Docker externo).

**Esfuerzo**: M (4 h, principal coste = primeros 30 min de build + probar pulls).

**Riesgos**: Ollama dentro de Docker puede tener performance menor sin GPU. Documentar el trade-off.

**Cómo demo-arlo**: `docker compose up` → app disponible en localhost:8501 sin tocar nada más.

---

### 5.3 Persistencia multi-sesión del historial de chat

**Motivación**: hoy `_SESSION_STORE` vive en memoria — si reinicias el server se pierde el chat. Para una demo que se pause y retome, persistir ayuda.

**Diseño**:
- Sustituir `InMemoryChatMessageHistory` por `SQLChatMessageHistory` de `langchain-community` apuntando a una tabla `chat_history` dentro de `portfolio.db` (o separada).
- Por sesión + usuario (combinable con 5.1).

**Ficheros afectados**: `src/agent/agent_builder.py`, `src/services/db.py`.

**Dependencias nuevas**: ninguna (ya en `langchain-community`).

**Esfuerzo**: S (1.5 h).

**Riesgos**: el historial crece sin límite. Añadir `MAX_HISTORY_MESSAGES=20` y truncar en `get_session_history`.

**Cómo demo-arlo**: chatear, matar el server, reabrir → el historial sigue ahí.

---

## Mejoras transversales de UI/UX

### T.1 Tema oscuro por defecto
**Motivación**: estética, coherencia con herramientas financieras (Bloomberg/TradingView son oscuras). **Diseño**: `.streamlit/config.toml` con `[theme] base="dark"` + paleta custom (primary verde, accent naranja). **Ficheros**: nuevo `.streamlit/config.toml`. **Esfuerzo**: S (15 min). **Riesgo**: ninguno. **Demo**: se ve al abrir.

### T.2 Exportar cartera a CSV
**Motivación**: usuario puede querer backup o analizar en Excel. **Diseño**: botón `st.download_button("📥 Exportar CSV", df.to_csv(index=False), "cartera.csv")` en la pestaña Cartera; opcional segundo botón para transacciones. **Ficheros**: `src/ui/portfolio_view.py`. **Esfuerzo**: S (20 min). **Riesgo**: ninguno. **Demo**: click → descarga.

### T.3 Reset sesión / limpiar chat
**Motivación**: en demos encadenadas conviene empezar limpio sin matar el server. **Diseño**: botón `🗑️ Nueva conversación` en el sidebar que hace `st.session_state.messages = []`, genera nuevo `session_id = uuid4()` y llama a `st.rerun()`. El historial del agente se descarta al cambiar `session_id` (nuevo namespace en `_SESSION_STORE`). **Ficheros**: `app.py`. **Esfuerzo**: S (15 min). **Riesgo**: ninguno.

### T.4 Favicon + branding custom
**Motivación**: profesionalismo visual. **Diseño**: crear `assets/favicon.png` (icono bolsa simple) y pasarlo a `st.set_page_config(page_icon="assets/favicon.png")`. Añadir un `st.logo("assets/logo.png")` si hay logo. **Ficheros**: `app.py`, nuevo `assets/`. **Esfuerzo**: S (30 min incluyendo buscar/crear icono). **Riesgo**: ninguno.

### T.5 Deshacer última operación de cartera
**Motivación**: humanizar la UI simulada. Si el agente interpretó mal una orden ("vende 100" en vez de "10"), deshacer salva la demo. **Diseño**: botón `↩️ Deshacer última operación` en la pestaña Cartera que: lee la última fila de `transactions`, aplica la operación inversa (`buy` si fue `sell` y viceversa) al mismo precio, marca ambas como `reversed=true` (nueva columna) para no aparecer dos veces en el historial. **Ficheros**: `src/services/portfolio.py` (+ migración schema), `src/ui/portfolio_view.py`. **Esfuerzo**: M (2-3 h por la migración y los edge cases: venta total que borró la posición, etc.). **Riesgo**: lógica subtil — tests unitarios obligatorios.

### T.6 Traducción de etiquetas yfinance
**Motivación**: hoy algunas salidas de `get_ticker_status` filtran términos en inglés (`Previous Close`, `Market Cap`). Hablamos al usuario en español en el prompt pero las tools no siempre. **Diseño**: diccionario `LABEL_ES` en `src/tools/market_tools.py` con mapeo `{"previousClose": "Cierre anterior", "marketCap": "Capitalización", ...}`. Aplicarlo al construir el string de salida. **Ficheros**: `src/tools/market_tools.py`. **Esfuerzo**: S (45 min). **Riesgo**: ninguno. **Demo**: ver respuesta toda en español.

---

## Tabla resumen

| ID | Título | Prioridad | Esfuerzo | Impacto demo |
|---|---|---|---|---|
| 1.1 | Buscador de tickers con autocompletado | P1 | M | Alto |
| 1.2 | Noticias reales por ticker | P1 | S | Alto |
| 1.3 | Guía de uso embebida en la UI | P1 | S | Alto |
| 2.1 | Chips de sugerencias en el chat | P2 | S | Medio |
| 2.2 | Streaming de respuestas | P2 | M | Alto |
| 2.3 | Indicador de tool en uso | P2 | S-M | Alto (didáctico) |
| 3.1 | Comparador de tickers | P3 | M | Alto |
| 3.2 | Indicadores técnicos (SMA, Bollinger) | P3 | S | Medio |
| 3.3 | Historial temporal del valor de cartera | P3 | M | Medio |
| 4.1 | Tests E2E con mocks de Ollama | P4 | M | Bajo (defensa) |
| 4.2 | Métricas de latencia y tokens | P4 | S-M | Medio (defensa) |
| 4.3 | Logs estructurados JSON | P4 | S | Bajo |
| 5.1 | Autenticación básica | P5 | M | Bajo (demo local) |
| 5.2 | Dockerfile + docker-compose | P5 | M | Medio |
| 5.3 | Persistencia multi-sesión del historial | P5 | S | Bajo |
| T.1 | Tema oscuro por defecto | T | S | Medio |
| T.2 | Exportar cartera a CSV | T | S | Bajo |
| T.3 | Reset sesión / limpiar chat | T | S | Bajo |
| T.4 | Favicon + branding custom | T | S | Bajo |
| T.5 | Deshacer última operación | T | M | Medio |
| T.6 | Traducción etiquetas yfinance | T | S | Medio |

---

## Orden de ataque sugerido

Para la próxima sesión de implementación, este orden maximiza quick wins demo-ables sin dependencias bloqueantes:

1. **T.1 Tema oscuro** (15 min). Cambio estético inmediato; marca el "antes/después" de la iteración.
2. **1.3 Guía de uso** (~2 h). Desbloquea el resto de la demo: el usuario puede guiarse solo. No depende de nada más.
3. **1.2 Noticias reales** (~2 h). Alto impacto visible, sin tocar arquitectura; mejor hacerlo antes que 1.1 porque no introduce dependencias nuevas grandes ni índices locales.
4. **1.1 Buscador de tickers** (~3-4 h). Requiere poblar CSV y añadir `rapidfuzz`; impacto alto y reutilizable por el comparador (3.1).
5. **2.2 Streaming + 2.3 Indicador de tool** (~4-5 h combinados, comparten base técnica `astream_events`). Convierte la demo de "espera el spinner" a "ves al agente pensar en directo" — el mayor salto perceptivo de todo el plan.

Con esos 5 items (aprox. 11-13 h de trabajo) el bot pasa de MVP correcto a demo memorable. Todo lo demás es mejora incremental que puede atacarse en iteraciones posteriores según tiempo disponible.
