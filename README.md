# 📈 Bot de Inversiones con Agente de IA

> Asistente conversacional de inversiones construido con un **agente LangChain** sobre un **LLM local (Ollama)**. Combina datos de mercado en tiempo real (Yahoo Finance), una base de conocimiento financiera con **RAG** (ChromaDB + PDFs) y una **cartera simulada** persistida en SQLite, todo expuesto en una UI de Streamlit con chat, tabla de posiciones y gráficos.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![LangChain](https://img.shields.io/badge/LangChain-0.3-green) ![Streamlit](https://img.shields.io/badge/Streamlit-UI-red) ![Ollama](https://img.shields.io/badge/Ollama-local-black) ![License](https://img.shields.io/badge/license-educational-lightgrey)

---

## 🗂️ Índice

- [Descripción del problema](#-descripción-del-problema)
- [Arquitectura](#-arquitectura)
- [Flujo del agente](#-flujo-del-agente)
- [Tools disponibles (8)](#-tools-disponibles-8)
- [RAG](#-rag)
- [Persistencia](#-persistencia)
- [Tecnologías](#-tecnologías)
- [Requisitos previos](#-requisitos-previos)
- [Instalación y ejecución](#-instalación-y-ejecución)
- [Ejemplos de uso](#-ejemplos-de-uso)
- [Tests](#-tests)
- [Cumplimiento del enunciado](#-cumplimiento-del-enunciado)
- [Limitaciones conocidas](#-limitaciones-conocidas)
- [Mejoras futuras](#-mejoras-futuras)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Troubleshooting](#-troubleshooting)
- [Licencia](#-licencia)
- [Autor](#-autor)
- [Agradecimientos](#-agradecimientos)

---

## 📝 Descripción del problema

Invertir en bolsa es, para una persona no experta, una mezcla incómoda de dos fricciones:

1. **Datos dispersos**: el precio actual está en un sitio, el histórico en otro, el análisis conceptual en libros o PDFs sueltos y la propia cartera (si la llevas) en una hoja de cálculo.
2. **Jerga técnica**: "P/E ratio", "value investing", "medias móviles"... muchas fuentes asumen que ya sabes de qué hablan.

Este proyecto resuelve ambas fricciones juntas en un único chat:

- **Datos en vivo** vía Yahoo Finance (precio, cambio, P/E, capitalización, histórico, tickers "calientes").
- **Educación fundamentada** vía RAG sobre PDFs financieros reales (glosario, análisis técnico, estrategias de largo plazo) — el agente **cita la fuente** en lugar de alucinar definiciones.
- **Cartera simulada** para practicar compras y ventas sin dinero real y ver P&L en tiempo real.

Público objetivo: usuarios que están aprendiendo a invertir y quieren un primer copiloto que combine números con explicaciones, todo en español y sin enviar datos a la nube (el LLM corre en local con Ollama).

---

## 🏗️ Arquitectura

```
+-----------------------------------------------------------+
|  Streamlit UI (app.py)                                    |
|  +-------------+  +--------------+  +-----------------+   |
|  | Chat agente |  | Cartera sim. |  | Gráficos precio |   |
|  +------+------+  +------+-------+  +--------+--------+   |
+---------|----------------|-------------------|------------+
          v                v                   v
   +-------------+   +--------------+   +-------------+
   |   Agent     |   |  Portfolio   |   |   Plotly    |
   |  LangChain  |   |   Service    |   |  (charts)   |
   | (tool-call) |   |  (SQLite)    |   +-------------+
   +------+------+   +------+-------+
          | 8 tools         |
   +------+------+------+---+-------+-----------+
   v      v      v      v           v           v
 Yahoo   Hot    RAG   Portfolio   Portfolio   Portfolio
 Fin.   Movers (Chroma)  buy       sell       view/tx
 (status/
  history)                        SQLite
                |
                v
          PDFs en data/rag_docs/
```

### Capas

- **UI (Streamlit)**: `app.py` orquesta tres pestañas (chat, cartera, gráficos). No contiene lógica de negocio, solo delega.
- **Agente (LangChain)**: `src/agent/agent_builder.py` construye un `AgentExecutor` (tool-calling) sobre `ChatOllama`, envuelto en `RunnableWithMessageHistory` para aislar el historial por `session_id` de Streamlit.
- **Tools**: 8 funciones Python decoradas con `@tool`, agrupadas en tres módulos (`market_tools.py`, `rag_tool.py`, `portfolio_tools.py`). Son la "API" que el LLM llama.
- **Servicios**: `src/services/portfolio.py` implementa la lógica de cartera (buy/sell con precio medio ponderado, posiciones con P&L); `src/services/db.py` gestiona SQLite.
- **RAG**: `src/rag/ingest.py` procesa PDFs offline; `src/tools/rag_tool.py` consulta el vectorstore Chroma con similarity search.
- **Persistencia**: SQLite (`data/portfolio.db`) para la cartera; ChromaDB (`chroma/`) para el vectorstore.

---

## 🔄 Flujo del agente

1. El usuario escribe en el chat de Streamlit (`st.chat_input`).
2. `app.py` llama a `agent.invoke({"input": ...}, config={"configurable": {"session_id": ...}})`.
3. `RunnableWithMessageHistory` recupera el historial de esa sesión desde un store en memoria y lo inyecta en el prompt (placeholder `chat_history`).
4. `AgentExecutor` pasa el prompt completo a `ChatOllama` (gemma3:4b, num_ctx=12000, temperature=0.2).
5. El LLM decide, en formato tool-calling estructurado, **qué herramienta invocar** (o si responde directamente). La decisión se basa en:
   - El `SYSTEM_PROMPT` con el mapa intención → tool.
   - Los docstrings de las tools (el LLM los lee como descripciones).
6. Se ejecuta la tool elegida:
   - Tools de mercado → Yahoo Finance (yfinance).
   - `search_finance_knowledge` → ChromaDB (RAG, similarity k=4) con embeddings `nomic-embed-text`.
   - Tools de cartera → SQLite (INSERT/UPDATE/DELETE en `positions` y `transactions`).
7. La observación (string) vuelve al `AgentExecutor`, que la añade al scratchpad y repite el paso 5 hasta que el LLM genera `AgentFinish` (respuesta final) o se alcanza `max_iterations=6`.
8. Streamlit pinta la respuesta en la burbuja del asistente; si corresponde, renderiza un gráfico Plotly en otra pestaña.

> **Decisión de diseño — tool-calling vs ReAct**: usamos `create_tool_calling_agent` en lugar de ReAct clásico. ReAct parsea texto tipo `Action: ... / Action Input: ...`, lo cual es frágil con modelos pequeños que se saltan el formato. Tool-calling nativo (soportado por gemma3/qwen3) devuelve llamadas estructuradas — más fiable y menos propenso a loops.

> **Memoria por sesión**: el `AgentExecutor` es stateless. Usamos `RunnableWithMessageHistory` con un store en memoria indexado por `session_id` (generado con `uuid.uuid4()` y guardado en `st.session_state`). Así, dos pestañas distintas del navegador tienen conversaciones independientes.

> **HITL**: el agente **avisa** antes de ejecutar `portfolio_buy`/`portfolio_sell` (regla #7 del system prompt) pero ejecuta directamente, sin botón de confirmación en UI. Compromiso entre UX fluida y seguridad, aceptable porque la cartera es simulada.

---

## 🛠️ Tools disponibles (8)

| Tool | Propósito | Fuente de datos |
|---|---|---|
| `get_ticker_status` | Precio actual, cambio diario, P/E, capitalización y nombre de la empresa. | Yahoo Finance (`yfinance.Ticker.info` con fallback a `history(5d)`) |
| `get_ticker_history` | Máximo, mínimo, último cierre y variación % del periodo (`1mo`, `3mo`, `6mo`, `1y`, `5y`). | Yahoo Finance (`yfinance.Ticker.history`) |
| `get_hot_tickers` | Top 10 por categoría: `gainers`, `losers` o `actives`. | `yfinance.Screener` con fallback a universo S&P500 hardcodeado (30 tickers) |
| `search_finance_knowledge` | Búsqueda semántica (k=4) sobre los PDFs ingestados; devuelve texto + fuente citada. | ChromaDB + embeddings `nomic-embed-text` (Ollama) |
| `portfolio_buy` | Compra simulada a precio de mercado. Calcula avg ponderado si ya hay posición. | SQLite (`positions`, `transactions`) + yfinance para precio |
| `portfolio_sell` | Venta simulada con validación de cantidad; cierra la posición si `qty == 0`. | SQLite (`positions`, `transactions`) + yfinance para precio |
| `portfolio_view` | Tabla ASCII con posiciones, avg, actual, valor, P&L y totales. | SQLite + yfinance (precio actual por ticker, paralelizado) |
| `portfolio_transactions` | Últimas N transacciones en formato tabular. | SQLite (`transactions`) |

**Importante**: TODAS las tools devuelven `str` (no dict). Con modelos pequeños como gemma3:4b, el tool-calling es más fiable cuando la observación ya es texto plano que el LLM puede resumir sin serializar/parsear JSON. Además, cualquier excepción se captura dentro de la tool y se convierte en un mensaje legible.

---

## 📚 RAG

El sistema RAG permite al agente **responder preguntas conceptuales fundamentadas en documentos**, citando la fuente en lugar de alucinar definiciones.

**Pipeline de ingesta (offline, una vez)**:

```
PDFs (data/rag_docs/*.pdf)
        |
        v
   PyPDFLoader         <-- una página = un Document con metadata
        |
        v
   RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        |
        v
   OllamaEmbeddings(nomic-embed-text)    <-- embeddings locales
        |
        v
   Chroma.from_documents(persist_directory="chroma")
```

**Pipeline de consulta (online, en cada pregunta)**:

```
query del usuario
        |
        v
   search_finance_knowledge tool
        |
        v
   _get_vectorstore()    <-- singleton lazy, cachea el vectorstore
        |
        v
   vs.similarity_search(query, k=4)
        |
        v
   Formato [i] Fuente: <pdf> (pág. N)\n<texto>
        |
        v
   El LLM resume y CITA la fuente (regla #6 del system prompt)
```

**Por qué RAG tiene sentido aquí**: los conceptos financieros (P/E, value, growth, medias móviles, dividendos...) están definidos en documentos reales. Sin RAG, el LLM se inventaría detalles. Con RAG, la respuesta está anclada a un PDF concreto (glosario CNMV, guía del inversor, etc.) y el usuario puede verificarla.

**Corpus actual**: 10 PDFs oficiales publicados en abierto por entidades reguladoras — 8 de la **CNMV** en español (50 preguntas sobre inversión, guía del accionista, renta fija, fondos de inversión, manual para universitarios, psicología económica para inversores, fiscalidad de acciones e IRPF, fiscalidad de fondos) y 2 de la **SEC / Investor.gov** en inglés (Saving and Investing Roadmap, Mutual Funds and ETFs). Ver `data/rag_docs/README.md` para la lista completa con URLs y entidad emisora, y `data/rag_docs/LICENCIA.md` para las condiciones de uso. Nada de blogs ni cursos privados: sólo material publicado oficialmente y gratuito.

**Por qué 800/120**: 800 caracteres por chunk es un compromiso entre contexto suficiente para responder y no saturar el prompt. 120 de overlap evita partir frases entre chunks consecutivos.

**Por qué k=4**: suficiente diversidad de fragmentos para cubrir la respuesta sin ensuciar el context window con resultados poco relevantes.

---

## 💾 Persistencia

- **SQLite** (`data/portfolio.db`): dos tablas.
  - `positions(ticker PK, qty, avg_price)`: una fila por posición abierta. El `ticker` es clave primaria porque no queremos duplicados; buy/sell actualizan la fila existente.
  - `transactions(id, ticker, side, qty, price, ts)`: libro de operaciones append-only con timestamp ISO-8601 UTC. Permite reconstruir el historial completo de la cartera.
- **ChromaDB** (`chroma/`): vectorstore persistido con embeddings de los PDFs. Se crea al ejecutar `python -m src.rag.ingest`.

Ambos directorios están en `.gitignore` — cada usuario tiene su propia cartera y sus propios PDFs.

---

## 🧰 Tecnologías

- **Python 3.12 / 3.13** (usa PEP 604 `float | None` y PEP 585 `list[dict]`).
- **Streamlit** — UI y lógica de la app.
- **LangChain 0.3.x** — `langchain`, `langchain-core`, `langchain-community`, `langchain-ollama`, `langchain-openai`, `langchain-chroma`, `langchain-text-splitters`.
- **Ollama** local — LLM `gemma3:4b` / `qwen2.5:3b` + embeddings `nomic-embed-text` (o `mxbai-embed-large` como alternativa).
- **OpenRouter (opcional)** — pasarela cloud a modelos gratuitos con tool-calling (ej. `openai/gpt-oss-20b:free`, `meta-llama/llama-3.3-70b-instruct:free`). Se activa con `LLM_PROVIDER=openrouter` en `.env`.
- **yfinance** — datos de mercado (scraping de Yahoo Finance).
- **ChromaDB** — vectorstore local para el RAG.
- **SQLite** — persistencia de la cartera simulada (incluido en la stdlib).
- **Plotly** — gráficos interactivos (línea de precios, pie de asignación, bar de P&L).
- **Pandas** — DataFrames para la tabla de posiciones y transacciones.
- **python-dotenv** — carga de variables de entorno.
- **pytest** — tests unitarios y de integración.

---

## ✅ Requisitos previos

- [**Ollama**](https://ollama.com/) instalado y en ejecución (`ollama serve`).
- **Python 3.10 – 3.13 (recomendado 3.12 o 3.13). Python 3.14 NO funciona hoy: pydantic V1 usado internamente por LangChain y Chroma aún no soporta 3.14.**
- **Conexión a internet** para `yfinance` (Yahoo Finance).

---

## 🚀 Instalación y ejecución

### Windows (PowerShell)

```powershell
# 1. Clonar el repositorio
git clone <url>
cd "proyecto IA"

# 2. Crear venv con Python 3.13 (o 3.12)
py -3.13 -m venv .venv
.venv\Scripts\activate

# 3. Actualizar pip e instalar dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Copiar variables de entorno
copy .env.example .env

# 5. Descargar modelos Ollama (requiere Ollama instalado: https://ollama.com)
ollama pull gemma3:4b
ollama pull nomic-embed-text
# Alternativa de embeddings (más precisa, más pesada): `ollama pull mxbai-embed-large`
# Si la usas, edita EMBEDDINGS_MODEL en .env.

# 6. Ingestar el RAG (10 PDFs oficiales de CNMV y SEC ya incluidos)
python -m src.rag.ingest

# 7. Arrancar la app
streamlit run app.py
```

### Linux / macOS (bash)

```bash
# 1. Clonar el repositorio
git clone <url>
cd "proyecto IA"

# 2. Crear venv con Python 3.13 (o 3.12)
python3.13 -m venv .venv
source .venv/bin/activate

# 3. Actualizar pip e instalar dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Copiar variables de entorno
cp .env.example .env

# 5. Descargar modelos Ollama (requiere Ollama instalado: https://ollama.com)
ollama pull gemma3:4b
ollama pull nomic-embed-text
# Alternativa de embeddings (más precisa, más pesada): `ollama pull mxbai-embed-large`
# Si la usas, edita EMBEDDINGS_MODEL en .env.

# 6. Ingestar el RAG (10 PDFs oficiales de CNMV y SEC ya incluidos)
python -m src.rag.ingest

# 7. Arrancar la app
streamlit run app.py
```

Abre el navegador en `http://localhost:8501` y empieza a chatear.

---

## 🤖 Cambiar de LLM (Ollama local ↔ OpenRouter cloud)

El agente puede usar **dos motores intercambiables**, configurables sin tocar código vía `.env`:

| Proveedor | Cuándo usarlo | Pros | Contras |
|---|---|---|---|
| **Ollama (local)** | Tienes RAM/CPU/GPU suficientes y quieres privacidad total. | Sin coste, sin cuota, sin red. | Limitado a modelos que quepan en tu PC. |
| **OpenRouter (cloud)** | Quieres un modelo más potente o tu PC va justo. | Acceso a Llama 3.3 70B, Qwen3 80B, GPT-OSS, etc. (varios **gratis**). Tool-calling fiable. | Necesita API key + conexión. |

**Cómo alternar:** edita `.env`, cambia `LLM_PROVIDER`, y **reinicia Streamlit** (la caché `@st.cache_resource` no detecta cambios en variables de entorno).

```bash
# Modo local (default)
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:3b

# Modo cloud — crea API key gratis en https://openrouter.ai/keys
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-oss-20b:free
```

Si `LLM_PROVIDER=openrouter` pero falta la API key, la app hace **fallback automático a Ollama**. El badge **🤖 LLM activo** que aparece en la Home te confirma siempre cuál se está usando realmente.

> ⚠️ **Seguridad**: nunca subas tu `.env` con la API key. Está incluido en `.gitignore`. El archivo a versionar es `.env.example` (sólo placeholders).

---

## 💬 Ejemplos de uso

Preguntas reales que puedes hacerle al bot, cubriendo las cuatro categorías de tools:

**Mercado (status / history)**
- "¿Cómo está Apple?"
- "Dame el histórico de MSFT a 1 año."

**Hot tickers**
- "¿Cuáles son los 5 tickers más calientes hoy?"
- "Mayores caídas del día."

**RAG (educación)**
- "¿Qué es el P/E ratio?"
- "Explícame la estrategia value investing."

**Cartera**
- "Compra 10 acciones de MSFT."
- "Vende 5 de AAPL."
- "¿Cómo va mi cartera?"
- "Últimas transacciones."

---

## 🧪 Tests

```bash
pytest tests/
```

Los tests están en `tests/test_tools.py` y cubren:

- **`test_get_ticker_status_invalid`**: un ticker inventado devuelve un string de error controlado, nunca una excepción.
- **`test_portfolio_buy_sell_flow`**: flujo completo buy → buy (precio medio ponderado) → sell parcial (avg mantenido) → sell total (cierre de posición y borrado de la fila).
- **`test_sell_over_qty_raises`**: vender más de lo que posees lanza `ValueError`.
- **`test_portfolio_value_with_stale`**: un ticker sin precio actual (yfinance caído) se excluye del total y aparece en `stale_tickers`.

Todos los tests usan fixtures pytest para aislar BD (tmp_path) y monkeypatchean `_current_price` para no tocar Yahoo Finance.

---

## 📋 Cumplimiento del enunciado

| Requisito | Cómo se cumple |
|---|---|
| ≥1 agente LangChain | `AgentExecutor` tool-calling en `src/agent/agent_builder.py`, envuelto en `RunnableWithMessageHistory`. |
| ≥2 tools | **8 tools**: `get_ticker_status`, `get_ticker_history`, `get_hot_tickers`, `search_finance_knowledge`, `portfolio_buy`, `portfolio_sell`, `portfolio_view`, `portfolio_transactions`. |
| RAG sobre doc textual | ChromaDB + embeddings `nomic-embed-text` sobre PDFs financieros en `data/rag_docs/`. |
| Integración del agente en flujo app | Chat Streamlit invoca al agente; las tools leen de Yahoo, modifican la BD SQLite y consultan Chroma. |
| Persistencia / servicio externo | SQLite (`positions`, `transactions`) + Yahoo Finance (API externa) + Chroma (vectorstore local). |
| Repo GitHub con README | Este documento. |
| Valor real no trivial | Combina datos de mercado en vivo + educación financiera con citas + cartera simulada con P&L. |
| Acciones sobre otros servicios | Escribe en SQLite, lee de Yahoo, escribe/lee en Chroma. |
| Manejo de errores | `try/except` en cada tool (devuelven string controlado) y en `app.py` (mensaje amigable si Ollama cae). |

---

## ⚠️ Limitaciones conocidas

- **yfinance no es API oficial**: es scraping de Yahoo Finance, puede tener latencia (3-10 s por llamada a `.info`), devolver dicts parciales o fallar puntualmente. Se mitiga con fallbacks a `history(period="5d")` y universo hardcodeado.
- **Cartera 100% simulada**: no se conecta a ningún broker real, no mueve dinero real. Es intencionado (proyecto educativo).
- **Rendimiento depende del hardware**: `gemma3:4b` funciona bien en CPU moderna; con GPU vuela. En portátiles viejos puede tardar 10-20 s por respuesta.
- **Memoria del chat en proceso**: el `_SESSION_STORE` vive en memoria del proceso Streamlit. Si reinicias el servidor, se pierde el historial. Aceptable para MVP; un Redis/SQLite lo resolvería.
- **HITL vía prompt, no vía UI**: el agente avisa antes de comprar/vender pero no pide confirmación explícita. Si el LLM malinterpreta una frase, la operación se ejecuta (mitigado porque es cartera simulada).
- **Ingesta RAG no idempotente**: volver a ejecutar `python -m src.rag.ingest` duplica embeddings. Borrar `chroma/` manualmente para reingestar.
- **Fallback lento de hot_tickers**: si el Screener de yfinance cae, iteramos 30 tickers en serie — puede tardar 30-90 s.

---

## 🔮 Mejoras futuras

- Alertas por email / Telegram cuando un ticker de la cartera sube o baja más de X%.
- Backtesting de estrategias sobre la cartera simulada (evolución histórica del P&L).
- Agente router multi-modelo: uno pequeño y rápido para clasificar la intención, uno grande para análisis profundo.
- Integración con noticias (vía MCP o scraping) para contexto contextual del ticker.
- Autenticación multi-usuario con carteras independientes.
- Dockerización (Ollama + Streamlit + Chroma en un único `docker-compose`).
- Flag `--rebuild` en `ingest.py` para reindexar sin duplicar.
- Botón de confirmación HITL real para compras/ventas (defensa en profundidad).

---

## 📁 Estructura del proyecto

```
proyecto IA/
├── app.py                          # Streamlit: chat + pestañas cartera/gráficos
├── requirements.txt                # Dependencias del proyecto
├── .env.example                    # OLLAMA_MODEL, OLLAMA_HOST, DB_PATH, CHROMA_DIR, EMBEDDINGS_MODEL
├── .gitignore                      # Excluye .env, chroma/, data/portfolio.db, .venv/
├── README.md                       # Este documento
├── qa_log.md                       # Registro de QA por fase
├── data/
│   ├── portfolio.db                # SQLite (gitignored, se crea solo)
│   └── rag_docs/                   # PDFs fuente (no versionados por copyright)
├── chroma/                         # Vectorstore persistido (gitignored)
├── src/
│   ├── agent/
│   │   ├── agent_builder.py        # AgentExecutor + RunnableWithMessageHistory + 8 tools
│   │   └── prompts.py              # SYSTEM_PROMPT en español con mapa intención->tool
│   ├── tools/
│   │   ├── market_tools.py         # get_ticker_status, get_ticker_history, get_hot_tickers
│   │   ├── rag_tool.py             # search_finance_knowledge (Chroma + similarity k=4)
│   │   └── portfolio_tools.py      # portfolio_buy/sell/view/transactions
│   ├── services/
│   │   ├── db.py                   # Esquema y conexión SQLite
│   │   └── portfolio.py            # Lógica de cartera (avg ponderado, P&L, stale tickers)
│   ├── rag/
│   │   └── ingest.py               # Script de ingesta de PDFs a Chroma
│   └── ui/
│       ├── portfolio_view.py       # Pestaña de cartera (tabla + gráficos + transacciones)
│       └── charts.py               # Helpers Plotly (histórico, pie, bar P&L)
└── tests/
    ├── conftest.py                 # Añade raíz del repo al sys.path para imports
    └── test_tools.py               # Smoke tests de tools + flujo completo de cartera
```

---

## 🔧 Troubleshooting

- **"Se ha producido un error al consultar al agente. Verifica que Ollama esté en ejecución"**
  Arranca Ollama (`ollama serve`) y verifica con `ollama list` que el modelo esté descargado (`gemma3:4b`). Confirma el host en `.env` (`OLLAMA_HOST=http://localhost:11434`).

- **"Base de conocimiento no inicializada"**
  Ejecuta `python -m src.rag.ingest` desde la raíz del repo con al menos un PDF en `data/rag_docs/`.

- **El modelo no llama a las tools (responde como si no existieran)**
  Algunos modelos Ollama no soportan tool-calling nativo. Usa `gemma3:4b`, `qwen2.5:7b` o superior. Verifica con `ollama show <modelo>` que sea compatible.

- **PDFs corruptos en la ingesta**
  `ingest.py` los salta individualmente con un mensaje `! Saltado ...` y continúa con el resto. Si todos fallan, sale con código 1. Revisa que sean PDFs válidos (no protegidos con contraseña).

- **`get_hot_tickers` tarda mucho**
  El `Screener` de yfinance falló y cayó al fallback serial (30 tickers). Reintenta en unos minutos o reduce el tamaño de `FALLBACK_UNIVERSE` en `src/tools/market_tools.py`.

- **La pestaña de cartera tarda en cargar con muchas posiciones**
  `get_positions` paraleliza `_current_price` con un `ThreadPoolExecutor` (8 workers) cuando hay más de 3 posiciones. Aun así, yfinance puede responder lento bajo rate-limit. Espera 10-30 s o pulsa el botón "🔄 Refrescar".

- **`chroma/` corrupto o errores al abrirlo**
  Borra el directorio `chroma/` entero y vuelve a ejecutar `python -m src.rag.ingest`. El vectorstore se regenerará desde cero.

- **Tildes / encoding en Windows**
  Asegúrate de que la terminal esté en UTF-8 (`chcp 65001`). Streamlit renderiza UTF-8 sin problema; el issue suele ser la consola.

- **Python < 3.10**
  El proyecto usa anotaciones `float | None` (PEP 604) y `list[dict]` (PEP 585). Actualiza a Python 3.10+ o rompe en el import.

### Error `TypeError: 'function' object is not subscriptable` al importar langchain
Tu intérprete es Python 3.14. Recrea el venv con Python 3.13:
rmdir /s /q .venv
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

---

## 📜 Licencia

Uso educativo. Proyecto desarrollado como **Práctica IX** del curso de Agentes de IA. MIT-like (sin garantías, sin asesoramiento financiero).

---

## 👤 Autor

**Iván Della Ventura** — Práctica IX (Agentes de IA).

---

## 🙏 Agradecimientos

- Al profesor del curso de Agentes de IA por la práctica y las revisiones.
- A la comunidad de **LangChain** por la documentación y los ejemplos de tool-calling.
- A **Ollama** por democratizar el LLM local.
- A la **CNMV** y a la **SEC / Investor.gov** por publicar en abierto las guías y manuales de educación financiera que alimentan el RAG de este proyecto.
