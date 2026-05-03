# Bot de Inversiones con Agente de IA

> Asistente conversacional de inversiones construido con un **agente LangChain** sobre **NVIDIA NIM** (API compatible OpenAI). Combina datos de mercado en tiempo real (Yahoo Finance), una base de conocimiento financiera con **RAG** (ChromaDB + PDFs) y una **cartera simulada** persistida en SQLite. Expone todo vía una **API FastAPI** que alimenta una **UI React** oscura con estética fintech.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![React](https://img.shields.io/badge/React-19-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![LangChain](https://img.shields.io/badge/LangChain-0.3-green) ![License](https://img.shields.io/badge/license-educational-lightgrey)

---

## Índice

- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos previos](#requisitos-previos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Configuración del LLM](#configuración-del-llm)
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
4. El agente devuelve eventos `thinking` (inicio) y `message` (respuesta final) vía SSE.
5. La UI renderiza el spinner durante el razonamiento y luego la burbuja de respuesta.

---

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| **Frontend** | React 19, Vite 8, TypeScript, Tailwind CSS v4, Recharts, TanStack Query, React Router v7, Lucide React |
| **Backend** | FastAPI, uvicorn, Pydantic v2 |
| **Agente** | LangChain 0.3 (`create_tool_calling_agent`, `AgentExecutor`, `RunnableWithMessageHistory`) |
| **LLM** | NVIDIA NIM (API compatible OpenAI) |
| **Datos mercado** | yfinance (Yahoo Finance scraping) |
| **RAG** | ChromaDB, nomic-embed-text (Ollama), PyPDF |
| **Persistencia** | SQLite (cartera simulada) |

---

## Requisitos previos

- **Python 3.10–3.13** (recomendado 3.13). Python 3.14 no soportado (pydantic v1 interno de LangChain).
- **Node.js >= 18** y npm para el frontend React.
- **NVIDIA NIM API key** (`NVIDIA_API_KEY`) para el agente LLM.
- **Ollama** instalado y en ejecución (`ollama serve`) si usas el RAG con embeddings locales.
- **Conexión a internet** para yfinance y la API de NVIDIA NIM.

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
cp .env.example .env   # edita NVIDIA_API_KEY, NVIDIA_MODEL, etc.
```

### 2. Modelos Ollama (solo para RAG)

```bash
ollama pull nomic-embed-text   # Embeddings para RAG
# Alternativa más precisa: ollama pull mxbai-embed-large
```

Solo se necesitan si vas a usar la herramienta `search_finance_knowledge` (RAG sobre PDFs).

### 3. Ingestar RAG

```bash
python -m backend.rag.ingest
```

Sólo hay que hacerlo una vez (o si añades PDFs nuevos a `data/rag_docs/`).

### 4. Arrancar todo

```bash
bash run.sh
# Abre http://localhost:5173 en el navegador
```

El script arranca el backend FastAPI en `:8000` y el dev server de Vite en `:5173`.

---

## Configuración del LLM

El agente usa exclusivamente **NVIDIA NIM**. Configura en `.env`:

```env
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=minimaxai/minimax-m2.7
```

El endpoint de NVIDIA NIM sigue el contrato de la API de OpenAI (`/v1/chat/completions`
con tool-calling nativo), por lo que se usa `ChatOpenAI` de LangChain apuntando a
`https://integrate.api.nvidia.com/v1`.

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
| `GET` | `/api/portfolios/{id}/positions` | Posiciones con precio actual |
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
| `search_ticker` | Búsqueda de ticker por nombre de empresa | Yahoo Finance |
| `analyze_news_article` | Contexto de mercado para analizar una noticia | Yahoo Finance |
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

Para reindexar (tras añadir PDFs):
```bash
rm -rf chroma/
python -m backend.rag.ingest
```

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
| ≥1 agente LangChain | `AgentExecutor` tool-calling en `backend/agent/agent_builder.py` con `RunnableWithMessageHistory` |
| ≥2 tools | **18 tools** (mercado, RAG, cartera, advisor, análisis) |
| RAG sobre doc textual | ChromaDB + nomic-embed-text sobre 10 PDFs CNMV/SEC |
| Integración agente en flujo app | Chat React → SSE → FastAPI → agente → tools → respuesta |
| Persistencia / externa | SQLite (cartera) + Yahoo Finance (API externa) + Chroma (RAG) |
| Acciones sobre otros servicios | Escribe en SQLite, lee de Yahoo Finance, escribe/lee Chroma |
| Manejo de errores | try/except en cada tool, errores en SSE como eventos `error` |

---

## Limitaciones conocidas

- **yfinance** es scraping no oficial: puede tardar 3-10 s por llamada, devolver datos parciales o fallar puntualmente.
- **Cartera 100% simulada**: no conecta a ningún broker real.
- **Memoria del chat en proceso**: el historial se pierde al reiniciar el servidor.
- **SSE no es streaming token-a-token**: el agente devuelve la respuesta completa (LangChain síncrono); se ve el spinner durante el razonamiento y luego aparece el texto completo.

---

## Estructura del proyecto

```
proyecto IA/
├── run.sh                    # Arranca backend FastAPI + frontend React
├── requirements.txt          # Deps Python (FastAPI, LangChain, yfinance, etc.)
├── .env.example              # Variables de entorno (NVIDIA_API_KEY, etc.)
├── backend/
│   ├── main.py               # FastAPI app con CORS
│   ├── routers/
│   │   ├── portfolio.py      # CRUD carteras + compra/venta
│   │   ├── market.py         # Datos de mercado (ticker, history, hot, compare)
│   │   ├── chat.py           # SSE streaming del agente
│   │   ├── news.py           # Portal y búsqueda de noticias
│   │   └── preferences.py    # Preferencias del usuario
│   ├── agent/
│   │   ├── agent_builder.py  # AgentExecutor + RunnableWithMessageHistory + 18 tools
│   │   ├── prompts.py        # SYSTEM_PROMPT en español
│   │   ├── singleton.py      # get_agent() singleton de proceso
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
│   │   ├── preferences.py    # Preferencias de usuario
│   │   └── watchlist.py      # Watchlist por cartera
│   ├── rag/
│   │   └── ingest.py         # Ingesta PDFs → Chroma
│   └── ui/
│       └── logos.py          # get_logo_url() con lru_cache
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

**"Base de conocimiento no inicializada"**
Ejecuta `python -m backend.rag.ingest` con Ollama corriendo y `nomic-embed-text` descargado.

**Error de NVIDIA API**
Verifica que `NVIDIA_API_KEY` en `.env` sea válido y que `NVIDIA_MODEL` sea un modelo disponible en NIM (ej. `minimaxai/minimax-m2.7`).

**Python 3.14**
LangChain y ChromaDB usan internamente pydantic v1, que no soporta Python 3.14. Usa Python 3.13.

---

## Licencia

Uso educativo. Práctica IX del curso de Agentes de IA. MIT-like — sin garantías, sin asesoramiento financiero.

## Autor

**Iván Della Ventura** — Práctica IX (Agentes de IA)
