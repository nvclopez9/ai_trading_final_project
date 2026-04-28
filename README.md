# Bot de Inversiones con Agente de IA

> Asistente conversacional de inversiones construido con un **agente LangChain** sobre un **LLM local (Ollama)** o en la nube (OpenRouter / NVIDIA NIM). Combina datos de mercado en tiempo real (Yahoo Finance), una base de conocimiento financiera con **RAG** (ChromaDB + PDFs) y una **cartera simulada** persistida en SQLite. Expone todo vía una **API FastAPI** que alimenta una **UI React** oscura con estética fintech.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![React](https://img.shields.io/badge/React-19-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![LangChain](https://img.shields.io/badge/LangChain-0.3-green) ![License](https://img.shields.io/badge/license-educational-lightgrey)

---

## Índice

- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos previos](#requisitos-previos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [LLM disponibles](#llm-disponibles)
- [API Reference](#api-reference)
- [Páginas de la UI](#páginas-de-la-ui)
- [Tools del agente](#tools-del-agente)
- [RAG](#rag)
- [Tests](#tests)
- [Cumplimiento del enunciado](#cumplimiento-del-enunciado)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Troubleshooting](#troubleshooting)

---

## Arquitectura

```
┌──────────────────────────────────────────────────────┐
│  React UI  (Vite + Tailwind + Recharts)  :5173       │
│  Chat │ Cartera │ Mercado │ Top │ Noticias │ Ayuda   │
└──────────────────┬───────────────────────────────────┘
                   │ REST + SSE (/api/*)
┌──────────────────▼───────────────────────────────────┐
│  FastAPI Backend                          :8000       │
│  /api/portfolios │ /api/market │ /api/chat/stream     │
│  /api/news       │ /api/preferences                   │
└──────────────────┬───────────────────────────────────┘
                   │
        ┌──────────┴────────────┐
        ▼                       ▼
   LangChain Agent         SQLite DB
   (tool-calling)         (cartera)
   RunnableWithHistory
        │
   ┌────┴──────────────────────┐
   ▼        ▼         ▼        ▼
 yfinance  Chroma    Portfolio Advisor
 (market)  (RAG)     tools     tools
```

### Flujo del agente
1. El usuario escribe en el Chat React.
2. El frontend abre un **SSE stream** a `POST /api/chat/stream`.
3. FastAPI invoca `agent.invoke()` en un thread pool (el agente es síncrono).
4. El agente devuelve eventos `tool_call` (con tool name + status) y `message` (respuesta final) vía SSE.
5. La UI renderiza los indicadores de tool en tiempo real y luego la burbuja de respuesta.

---

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| **Frontend** | React 19, Vite 8, TypeScript, Tailwind CSS v4, Recharts, TanStack Query, React Router v7, Lucide React |
| **Backend** | FastAPI, uvicorn, Pydantic v2 |
| **Agente** | LangChain 0.3 (`create_tool_calling_agent`, `AgentExecutor`, `RunnableWithMessageHistory`) |
| **LLM** | Ollama local (gemma3:4b, qwen3) · OpenRouter cloud · NVIDIA NIM |
| **Datos mercado** | yfinance (Yahoo Finance scraping) |
| **RAG** | ChromaDB, nomic-embed-text / mxbai-embed-large (Ollama), PyPDF |
| **Persistencia** | SQLite (cartera simulada) |
| **UI legacy** | Streamlit (modo `--legacy` de run.sh) |

---

## Requisitos previos

- **Python 3.10–3.13** (recomendado 3.13). Python 3.14 no soportado (pydantic v1 interno de LangChain).
- **Node.js >= 18** y npm para el frontend React.
- **Ollama** instalado y en ejecución (`ollama serve`) si usas LLM local.
- **Conexión a internet** para yfinance y proveedores cloud opcionales.

---

## Instalación y ejecución

### 1. Backend Python

```bash
# Clonar e instalar
git clone <url>
cd "proyecto IA"

python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # edita LLM_PROVIDER, OLLAMA_MODEL, API keys, etc.
```

### 2. Modelos Ollama (si usas LLM local)

```bash
ollama pull gemma3:4b          # LLM del agente (default)
ollama pull nomic-embed-text   # Embeddings para RAG
# Alternativa más precisa: ollama pull mxbai-embed-large
```

### 3. Ingestar RAG

```bash
python -m src.rag.ingest
```

Sólo hay que hacerlo una vez (o si añades PDFs nuevos a `data/rag_docs/`).

### 4. Arrancar todo

```bash
./run.sh
# Abre http://localhost:5173 en el navegador
```

El script arranca el backend FastAPI en `:8000` y el dev server de Vite en `:5173`.

**Modo legacy Streamlit:**
```bash
./run.sh --legacy   # http://localhost:8501
```

---

## LLM disponibles

Configura en `.env` sin tocar código:

| Proveedor | `LLM_PROVIDER` | Var adicional |
|---|---|---|
| Ollama local (default) | `ollama` | `OLLAMA_MODEL=gemma3:4b` |
| OpenRouter cloud | `openrouter` | `OPENROUTER_API_KEY=sk-or-...` + `OPENROUTER_MODEL` |
| NVIDIA NIM | `nvidia` | `NVIDIA_API_KEY=nvapi-...` + `NVIDIA_MODEL=meta-llama/llama-3.1-70b-instruct` |

Si `LLM_PROVIDER=openrouter` o `nvidia` pero falta la API key, se hace **fallback automático a Ollama**.

---

## API Reference

La documentación interactiva está en `http://localhost:8000/api/docs` (Swagger UI).

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/portfolios` | Lista carteras |
| `POST` | `/api/portfolios` | Crea cartera |
| `DELETE` | `/api/portfolios/{id}` | Elimina cartera |
| `POST` | `/api/portfolios/{id}/reset` | Resetea cartera (borra posiciones) |
| `GET` | `/api/portfolios/{id}/value` | Valor total + P&L |
| `GET` | `/api/portfolios/{id}/positions` | Posiciones con precio actual y AH |
| `GET` | `/api/portfolios/{id}/transactions` | Historial de transacciones |
| `POST` | `/api/portfolios/{id}/buy` | Compra simulada |
| `POST` | `/api/portfolios/{id}/sell` | Venta simulada |
| `GET` | `/api/market/ticker/{symbol}` | Estado actual del ticker |
| `GET` | `/api/market/ticker/{symbol}/history` | Histórico OHLCV |
| `GET` | `/api/market/ticker/{symbol}/news` | Noticias del ticker |
| `GET` | `/api/market/hot` | Gainers / Losers / Actives |
| `GET` | `/api/market/compare?tickers=AAPL,MSFT` | Comparativa de tickers |
| `GET` | `/api/market/fundamentals/{symbol}` | Ratios financieros |
| `GET` | `/api/news/portal` | Agregado multi-ticker |
| `GET` | `/api/news/ticker/{symbol}` | Noticias de un ticker |
| `POST` | `/api/chat/stream` | Chat con el agente (SSE) |
| `POST` | `/api/chat/clear` | Limpia historial de sesión |
| `GET` | `/api/preferences` | Preferencias del usuario |
| `PUT` | `/api/preferences` | Actualiza preferencias |

---

## Páginas de la UI

| Página | Ruta | Descripción |
|---|---|---|
| **Chat IA** | `/chat` | Conversación con el agente, indicadores de tool en tiempo real, quick pills |
| **Mi Cartera** | `/portfolio` | Posiciones con P&L, valor AH, gráfico de distribución, transacciones |
| **Mis Carteras** | `/portfolios` | Gestión multi-cartera: crear, resetear, eliminar |
| **Mercado** | `/market` | Ticker search, gráfico histórico, fundamentales, comparador |
| **Top del Día** | `/top` | Gainers / Losers / Más activos del S&P 500 |
| **Noticias** | `/news` | Portal multi-ticker + buscador; "Analizar con IA" envía al chat |
| **Ayuda** | `/help` | Guía de uso, slash commands, disclaimer |

---

## Tools del agente

| Tool | Descripción | Fuente |
|---|---|---|
| `get_ticker_status` | Precio, cambio, P/E, market cap | Yahoo Finance |
| `get_ticker_history` | Resumen histórico por periodo | Yahoo Finance |
| `get_hot_tickers` | Top gainers/losers/actives | Yahoo Finance |
| `get_ticker_news` | Últimas noticias del ticker | Yahoo Finance |
| `search_finance_knowledge` | RAG semántico (k=4) sobre PDFs CNMV/SEC | ChromaDB |
| `portfolio_buy` | Compra simulada con avg ponderado | SQLite |
| `portfolio_sell` | Venta simulada con validación de qty | SQLite |
| `portfolio_view` | Tabla de posiciones con P&L | SQLite + Yahoo |
| `portfolio_transactions` | Historial de operaciones | SQLite |
| `portfolio_list` | Lista carteras disponibles | SQLite |
| `portfolio_set_risk` | Cambia perfil de riesgo | SQLite |
| `portfolio_set_markets` | Cambia mercados objetivo | SQLite |
| `analyze_buy_opportunities` | Propone compras según riesgo | Yahoo + SQLite |
| `analyze_sell_candidates` | Propone ventas según P&L | Yahoo + SQLite |
| `compare_tickers` | Compara hasta 6 tickers | Yahoo Finance |
| `get_fundamentals` | Fundamentales detallados | Yahoo Finance |

---

## RAG

Corpus de 10 PDFs oficiales:
- **CNMV (España):** glosario, guía del accionista, renta fija, fondos de inversión, manual universitarios, psicología económica, fiscalidad IRPF acciones e fondos.
- **SEC / Investor.gov (USA):** Saving and Investing Roadmap, Mutual Funds and ETFs.

Pipeline:
```
PDFs → PyPDFLoader → RecursiveCharacterTextSplitter(800/120)
     → OllamaEmbeddings(nomic-embed-text) → ChromaDB
```

Consulta: `similarity_search(query, k=4)` → texto + fuente citada en la respuesta del agente.

---

## Tests

```bash
pytest tests/
```

Cubre: ticker inválido → error controlado, flujo buy/sell completo, venta excedida lanza ValueError, valor de cartera con ticker stale.

---

## Cumplimiento del enunciado

| Requisito | Cómo se cumple |
|---|---|
| ≥1 agente LangChain | `AgentExecutor` tool-calling en `src/agent/agent_builder.py` con `RunnableWithMessageHistory` |
| ≥2 tools | **16 tools** (mercado, RAG, cartera, advisor, análisis) |
| RAG sobre doc textual | ChromaDB + nomic-embed-text sobre 10 PDFs CNMV/SEC |
| Integración agente en flujo app | Chat React → SSE → FastAPI → agente → tools → respuesta |
| Persistencia / externa | SQLite (cartera) + Yahoo Finance (API externa) + Chroma (RAG) |
| Acciones sobre otros servicios | Escribe en SQLite, lee de Yahoo Finance, escribe/lee Chroma |
| Manejo de errores | try/except en cada tool, fallback de providers LLM, errores en SSE como eventos `error` |

---

## Limitaciones conocidas

- **yfinance** es scraping no oficial: puede tardar 3-10 s por llamada, devolver datos parciales o fallar puntualmente.
- **Cartera 100% simulada**: no conecta a ningún broker real.
- **Rendimiento del LLM**: `gemma3:4b` en CPU puede tardar 10-20 s por respuesta; en GPU es 3-5 s.
- **Memoria del chat en proceso**: el historial se pierde al reiniciar el servidor.
- **SSE no es streaming token-a-token**: el agente devuelve la respuesta completa (LangChain síncrono); se ve el spinner durante el razonamiento y luego aparece el texto completo.

---

## Estructura del proyecto

```
proyecto IA/
├── app.py                    # Streamlit (modo legacy)
├── run.sh                    # Arranca backend + frontend (o --legacy para Streamlit)
├── requirements.txt          # Deps Python (FastAPI, LangChain, yfinance, etc.)
├── .env.example              # Variables de entorno (LLM_PROVIDER, API keys, etc.)
├── backend/
│   ├── main.py               # FastAPI app con CORS
│   └── routers/
│       ├── portfolio.py      # CRUD carteras + compra/venta
│       ├── market.py         # Datos de mercado (ticker, history, hot, compare)
│       ├── chat.py           # SSE streaming del agente
│       ├── news.py           # Portal y búsqueda de noticias
│       └── preferences.py    # Preferencias del usuario
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Router + providers
│   │   ├── context/          # PortfolioContext (cartera activa)
│   │   ├── pages/            # ChatPage, PortfolioPage, MarketPage, TopPage, NewsPage, HelpPage
│   │   ├── components/
│   │   │   ├── layout/       # Sidebar con nav + selector de cartera
│   │   │   ├── ui/           # StatTile, DeltaBadge, TickerLogo
│   │   │   └── charts/       # PriceChart (AreaChart), PortfolioCharts (PieChart)
│   │   └── lib/
│   │       ├── api.ts        # Fetch wrappers + tipos TypeScript + streamChat (SSE)
│   │       └── utils.ts      # fmt, fmtCurrency, fmtPct, pctColor, etc.
│   ├── package.json
│   └── vite.config.ts        # Proxy /api → :8000
├── src/
│   ├── agent/
│   │   ├── agent_builder.py  # AgentExecutor + RunnableWithMessageHistory + 16 tools
│   │   ├── prompts.py        # SYSTEM_PROMPT en español
│   │   ├── singleton.py      # get_agent() con @st.cache_resource
│   │   ├── slash_commands.py # /precio, /cartera, /briefing, etc.
│   │   ├── streamlit_callbacks.py  # Indicadores de tool en tiempo real
│   │   └── verifier.py       # Verificador numérico post-respuesta
│   ├── tools/
│   │   ├── market_tools.py   # Herramientas Yahoo Finance
│   │   ├── rag_tool.py       # Herramienta ChromaDB
│   │   ├── portfolio_tools.py# Herramientas de cartera
│   │   ├── advisor_tool.py   # analyze_buy/sell_opportunities
│   │   ├── analysis_tools.py # compare_tickers, get_fundamentals
│   │   └── universes.py      # Universos de tickers (LARGE_CAP, ETFs, etc.)
│   ├── services/
│   │   ├── db.py             # Schema SQLite + get_conn()
│   │   ├── portfolio.py      # buy/sell/get_positions/get_portfolio_value
│   │   ├── portfolios.py     # CRUD multi-cartera
│   │   └── preferences.py    # Preferencias de usuario
│   ├── rag/
│   │   └── ingest.py         # Ingesta PDFs → Chroma
│   └── ui/
│       ├── components/       # Design system Streamlit (modo legacy)
│       ├── charts.py         # Gráficos Plotly (modo legacy)
│       └── logos.py          # get_logo_url() con cache
├── data/
│   ├── portfolio.db          # SQLite (gitignored)
│   └── rag_docs/             # PDFs fuente
├── chroma/                   # Vectorstore ChromaDB (gitignored)
└── tests/
    ├── conftest.py
    └── test_tools.py         # Smoke tests de tools y flujo de cartera
```

---

## Troubleshooting

**El frontend no carga / error de CORS**
Verifica que FastAPI esté corriendo en `:8000` (`python -m uvicorn backend.main:app --reload`) y que el proxy de Vite esté configurado en `vite.config.ts`.

**"Ollama not running"**
Ejecuta `ollama serve` en otra terminal antes de arrancar el backend.

**"Base de conocimiento no inicializada"**
Ejecuta `python -m src.rag.ingest` con Ollama corriendo y `nomic-embed-text` descargado.

**NVIDIA muy lento**
Verifica que `NVIDIA_MODEL` en `.env` sea un modelo válido de NIM (ej. `meta-llama/llama-3.1-70b-instruct`). El modelo anterior `z-ai/glm4.7` no existe en la API pública — se ha corregido el default.

**Python 3.14**
LangChain y ChromaDB usan internamente pydantic v1, que no soporta Python 3.14. Usa Python 3.13.

---

## Licencia

Uso educativo. Práctica IX del curso de Agentes de IA. MIT-like — sin garantías, sin asesoramiento financiero.

## Autor

**Iván Della Ventura** — Práctica IX (Agentes de IA)
