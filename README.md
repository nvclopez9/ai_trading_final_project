# Bot de Inversiones con Agente de IA

> Asistente conversacional de inversiones construido con un **agente LangChain** sobre **NVIDIA NIM**. Combina datos de mercado en tiempo real (Yahoo Finance), una base de conocimiento financiera con **RAG** (ChromaDB + PDFs) y una **cartera simulada** persistida en SQLite. Expone todo vía una **API FastAPI** que alimenta una **UI React** con estética fintech oscura.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![React](https://img.shields.io/badge/React-19-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688) ![LangChain](https://img.shields.io/badge/LangChain-0.3-green)

---

## Índice

- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Requisitos previos](#requisitos-previos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Arrancar la aplicación](#arrancar-la-aplicación)
- [RAG — Indexar documentos](#rag--indexar-documentos)
- [API Reference](#api-reference)
- [Páginas de la UI](#páginas-de-la-ui)
- [Tools del agente](#tools-del-agente)
- [Tests](#tests)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Cumplimiento del enunciado](#cumplimiento-del-enunciado)
- [Troubleshooting](#troubleshooting)

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│  React 19 + Vite  (frontend — :5173)                     │
│  Chat · Cartera · Mercado · Top · Noticias · Perfil      │
└─────────────────────┬────────────────────────────────────┘
                      │  REST + SSE streaming (/api/*)
┌─────────────────────▼────────────────────────────────────┐
│  FastAPI  (backend — :8000)                              │
│  /api/chat  /api/portfolios  /api/market  /api/news      │
└─────────────────────┬────────────────────────────────────┘
                      │
         ┌────────────▼──────────────┐
         │  LangChain AgentExecutor  │  ← create_tool_calling_agent
         │  + RunnableWithHistory    │  ← memoria por session_id
         └────────────┬──────────────┘
                      │  tool calling (18 herramientas)
     ┌────────────────┼──────────────────────────┐
     ▼                ▼                          ▼
  yfinance       ChromaDB (RAG)            SQLite
  Yahoo Finance  PDFs financieros          Carteras simuladas
                      │
                      ▼
            NVIDIA NIM API (LLM)
            mistralai/mistral-small-3.1-24b-instruct
```

### Flujo del agente
1. El usuario escribe en el Chat.
2. El frontend abre un **SSE stream** a `POST /api/chat/stream`.
3. FastAPI invoca `agent.astream_events()` — los tokens fluyen en tiempo real.
4. El LLM decide qué herramientas invocar; LangChain las ejecuta y devuelve las observaciones.
5. Cada token de la respuesta final se envía al cliente conforme se genera.
6. El frontend acumula los tokens y los renderiza progresivamente (sin esperar el final).

---

## Stack tecnológico

| Capa | Tecnologías |
|---|---|
| **Frontend** | React 19, Vite, TypeScript, Tailwind CSS v4, Recharts, TanStack Query, React Router |
| **Backend** | FastAPI, uvicorn, Pydantic v2, Python 3.13 |
| **Agente IA** | LangChain 0.3 — `create_tool_calling_agent`, `AgentExecutor`, `RunnableWithMessageHistory` |
| **LLM** | NVIDIA NIM (`mistralai/mistral-small-3.1-24b-instruct`) vía API compatible OpenAI |
| **Datos mercado** | yfinance (Yahoo Finance) |
| **RAG** | ChromaDB + mxbai-embed-large (Ollama) + PyPDF |
| **Persistencia** | SQLite (carteras y transacciones) |
| **Logs** | Python `logging` + `RotatingFileHandler` (5 MB × 5 backups) |

---

## Requisitos previos

- **Python 3.10–3.13** (recomendado 3.13)
- **Node.js >= 18** y npm
- **NVIDIA Build API key** — [obtener aquí](https://build.nvidia.com)
- **Ollama** (solo para el RAG):
  ```bash
  ollama pull mxbai-embed-large
  ```

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd "proyecto IA"

# 2. Entorno virtual Python
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate

# 3. Dependencias Python
pip install -r requirements.txt

# 4. Dependencias frontend
cd frontend && npm install && cd ..

# 5. Configurar variables de entorno
cp .env.example .env
# → editar .env con tu NVIDIA_API_KEY
```

---

## Configuración

Archivo `.env` en la raíz del proyecto:

```env
# Obligatorio — API Key de NVIDIA Build
NVIDIA_API_KEY=nvapi-...

# Modelo LLM (cualquier modelo de integrate.api.nvidia.com con tool calling)
NVIDIA_MODEL=mistralai/mistral-small-3.1-24b-instruct

# Nivel de log: debug | info | warning | error
LOG_LEVEL=info

# Ruta del archivo de logs
LOG_FILE=logs/bot.log

# Base de datos SQLite
DB_PATH=data/portfolio.db

# ChromaDB (RAG)
CHROMA_DIR=chroma

# Modelo de embeddings (Ollama)
EMBEDDINGS_MODEL=mxbai-embed-large
```

### Modelos NVIDIA recomendados

| Modelo | Parámetros | Velocidad aprox. | Calidad tool calling |
|---|---|---|---|
| `meta/llama-3.1-8b-instruct` | 8B | ~15s | Básica |
| `mistralai/mistral-small-3.1-24b-instruct` | 24B | ~45s | **Buena ✓** |
| `meta/llama-3.1-70b-instruct` | 70B | ~90s | Excelente |

---

## Arrancar la aplicación

### Windows (recomendado)
```
Doble clic en  start.bat
```
Abre dos ventanas CMD (backend y frontend) y lanza el navegador automáticamente.

> **Importante:** Para aplicar cambios en el código o en `.env`, cierra las ventanas del backend/frontend y vuelve a abrir `start.bat`. El servidor **no** se recarga automáticamente.

### Bash (Linux / macOS / WSL / Git Bash)
```bash
bash run.sh
```

### Manual
```bash
# Terminal 1 — Backend
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev -- --port 5173
```

Accede a `http://localhost:5173`

---

## RAG — Indexar documentos

Antes de usar el chat con preguntas conceptuales, indexa los PDFs:

```bash
# 1. Coloca los PDFs en data/rag_docs/
# 2. Con Ollama corriendo:
python -m backend.rag.ingest
```

Para reindexar tras añadir PDFs nuevos:
```bash
rm -rf chroma/
python -m backend.rag.ingest
```

---

## API Reference

Documentación interactiva: `http://localhost:8000/api/docs`

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/portfolios` | Lista carteras |
| `POST` | `/api/portfolios` | Crea cartera |
| `DELETE` | `/api/portfolios/{id}` | Elimina cartera |
| `POST` | `/api/portfolios/{id}/reset` | Resetea cartera |
| `GET` | `/api/portfolios/{id}/positions` | Posiciones con precio actual |
| `GET` | `/api/portfolios/{id}/transactions` | Historial de transacciones |
| `GET` | `/api/portfolios/{id}/performance` | Rendimiento histórico vs SPY/QQQ |
| `GET` | `/api/portfolios/{id}/realized-pnl` | P&L realizado por ticker |
| `GET` | `/api/portfolios/{id}/sector-distribution` | Distribución sectorial |
| `GET/POST/DELETE` | `/api/portfolios/{id}/watchlist` | Watchlist de la cartera |
| `GET` | `/api/market/ticker/{symbol}` | Estado actual del ticker |
| `GET` | `/api/market/history/{symbol}` | Histórico OHLCV |
| `GET` | `/api/market/search` | Búsqueda de tickers por nombre |
| `GET` | `/api/market/hot` | Gainers / Losers / Actives |
| `GET` | `/api/news/{symbol}` | Noticias de un ticker |
| `POST` | `/api/chat/stream` | Chat con el agente (SSE, token a token) |
| `POST` | `/api/chat/clear` | Limpia historial de sesión |
| `GET/PUT` | `/api/preferences` | Perfil y preferencias del usuario |
| `GET` | `/api/health` | Health check |

---

## Páginas de la UI

| Página | Ruta | Descripción |
|---|---|---|
| **Chat IA** | `/chat` | Conversación con el agente — streaming token a token, indicadores de tool en tiempo real |
| **Mi Cartera** | `/portfolio` | Posiciones, P&L, gráfico de distribución, rendimiento vs SPY/QQQ, transacciones paginadas |
| **Mis Carteras** | `/portfolios` | Gestión multi-cartera: crear, resetear, eliminar |
| **Mercado** | `/market` | Búsqueda de tickers, gráfico con filtros de tiempo, fundamentales, noticias, watchlist |
| **Top del Día** | `/top` | Mayores subidas, bajadas y más activos |
| **Noticias** | `/news` | Feed de noticias financieras; "Analizar con IA" envía al chat |
| **Perfil** | `/profile` | Preferencias del usuario (riesgo, horizonte, mercados) |

---

## Tools del agente

El agente dispone de **18 herramientas**. Para la documentación detallada de cada una (parámetros, comportamiento, ejemplos de uso) consulta [`docs/TOOLS.md`](docs/TOOLS.md).

| Tool | Descripción | Fuente de datos |
|---|---|---|
| `get_ticker_status` | Precio, cambio diario, P/E, market cap | Yahoo Finance |
| `get_ticker_history` | Resumen histórico por periodo | Yahoo Finance |
| `get_hot_tickers` | Top gainers / losers / actives | Yahoo Finance |
| `get_ticker_news` | Últimas noticias del ticker | Yahoo Finance |
| `search_ticker` | Búsqueda de símbolo por nombre de empresa | Yahoo Finance |
| `analyze_news_article` | Contexto de mercado para analizar una noticia | Yahoo Finance |
| `search_finance_knowledge` | RAG semántico (k=4) sobre PDFs financieros | ChromaDB |
| `portfolio_buy` | Compra simulada al precio de mercado | SQLite |
| `portfolio_sell` | Venta simulada con validación | SQLite |
| `portfolio_view` | Posiciones, P&L y patrimonio | SQLite + Yahoo |
| `portfolio_transactions` | Historial de operaciones | SQLite |
| `portfolio_list` | Lista todas las carteras | SQLite |
| `portfolio_set_risk` | Cambia perfil de riesgo (conservador/moderado/agresivo) | SQLite |
| `portfolio_set_markets` | Cambia mercados objetivo | SQLite |
| `analyze_buy_opportunities` | Propone compras según riesgo y mercado | Yahoo + SQLite |
| `analyze_sell_candidates` | Propone ventas según P&L de posiciones | Yahoo + SQLite |
| `compare_tickers` | Tabla comparativa de 2–6 tickers | Yahoo Finance |
| `get_fundamentals` | Ratios financieros completos (P/E, ROE, FCF…) | Yahoo Finance |

---

## Tests

```bash
# Tests unitarios
pytest tests/ -v

# Evaluación automática con escenarios reales (requiere servidor corriendo)
python -m tests.ai_eval
```

---

## Estructura del proyecto

```
proyecto IA/
├── .env                      # Variables de entorno (no incluir en git)
├── .env.example              # Plantilla de configuración
├── .gitignore
├── requirements.txt          # Dependencias Python
├── start.bat                 # Lanzador Windows (recomendado)
├── run.sh                    # Lanzador Bash (Linux/macOS/WSL)
│
├── backend/                  # FastAPI + lógica del agente
│   ├── main.py               # App FastAPI, CORS, logging startup
│   ├── agent/
│   │   ├── agent_builder.py  # AgentExecutor + RunnableWithMessageHistory
│   │   ├── prompts.py        # System prompt del agente en español
│   │   ├── singleton.py      # Caché del agente (una instancia por proceso)
│   │   └── verifier.py       # Validaciones post-respuesta
│   ├── routers/              # Endpoints FastAPI
│   │   ├── chat.py           # POST /api/chat/stream — SSE token a token
│   │   ├── portfolio.py      # CRUD carteras, compra/venta, performance
│   │   ├── market.py         # Precios, historial, búsqueda
│   │   ├── news.py           # Noticias por ticker
│   │   ├── watchlist.py      # Watchlist por cartera
│   │   └── preferences.py    # Perfil del usuario
│   ├── tools/                # Herramientas del agente (@tool de LangChain)
│   │   ├── market_tools.py   # Mercado: precios, historial, hot, noticias, búsqueda
│   │   ├── portfolio_tools.py# Cartera: buy, sell, view, transactions, list, set_risk/markets
│   │   ├── advisor_tool.py   # analyze_buy_opportunities, analyze_sell_candidates
│   │   ├── analysis_tools.py # compare_tickers, get_fundamentals
│   │   ├── rag_tool.py       # search_finance_knowledge (ChromaDB)
│   │   └── universes.py      # Universos de tickers por tier y clase de activo
│   ├── services/             # Lógica de negocio sin dependencias del agente
│   │   ├── db.py             # Schema SQLite + conexión
│   │   ├── portfolio.py      # buy/sell/positions/value para cartera activa
│   │   ├── portfolios.py     # CRUD multi-cartera
│   │   ├── preferences.py    # Preferencias de usuario
│   │   └── watchlist.py      # Watchlist
│   ├── rag/
│   │   └── ingest.py         # Script: PDF → chunks → embeddings → ChromaDB
│   └── utils/
│       └── logger.py         # get_logger(), timed() context manager
│
├── frontend/                 # React + TypeScript + Vite
│   └── src/
│       ├── App.tsx           # Router + providers
│       ├── pages/            # ChatPage, PortfolioPage, MarketPage, TopPage, NewsPage…
│       ├── components/
│       │   ├── layout/       # Sidebar con nav + selector de cartera
│       │   ├── charts/       # PriceChart, PortfolioCharts, CompareChart
│       │   └── ui/           # StatTile, DeltaBadge, TickerLogo, Toast
│       ├── context/          # PortfolioContext (cartera activa global)
│       └── lib/
│           ├── api.ts        # Cliente HTTP, tipos TypeScript, streamChat (SSE)
│           └── utils.ts      # Formatters: fmtCurrency, fmtPct, pctColor…
│
├── docs/
│   └── TOOLS.md              # Documentación detallada de las 18 herramientas
│
├── tests/
│   ├── test_tools.py         # Tests unitarios de herramientas
│   ├── test_verifier.py      # Tests del verificador
│   └── ai_eval/              # Evaluación automática con escenarios reales
│
├── data/
│   ├── portfolio.db          # SQLite — gitignored
│   └── rag_docs/             # PDFs fuente para el RAG
│
├── logs/
│   └── bot.log               # Logs rotativos — gitignored
│
└── chroma/                   # Vectorstore ChromaDB — gitignored
```

---

## Cumplimiento del enunciado

| Requisito | Implementación |
|---|---|
| ≥1 agente LangChain | `AgentExecutor` + `create_tool_calling_agent` en `backend/agent/agent_builder.py` con `RunnableWithMessageHistory` |
| ≥2 herramientas | **18 tools** en `backend/tools/` — ver [`docs/TOOLS.md`](docs/TOOLS.md) |
| RAG sobre documento textual | ChromaDB + PDFs financieros CNMV/SEC → `search_finance_knowledge` |
| Integración agente en flujo app | Chat React → SSE → FastAPI → `astream_events` → tokens en tiempo real |
| Persistencia | SQLite (carteras) + ChromaDB (vectores RAG) |
| Integración con servicio externo | Yahoo Finance (yfinance) + NVIDIA NIM API |
| Acciones sobre otros servicios | Escribe en SQLite, lee de Yahoo Finance, lee/escribe ChromaDB |
| Manejo de errores | try/except en cada tool, timeout en el agente, errores como eventos SSE |

---

## Troubleshooting

**El chat no responde / se queda colgado**
- Verifica que el servidor se haya reiniciado con `start.bat` tras cambiar `.env`.
- Comprueba en el log (`logs/bot.log`) qué modelo está usando y si hay errores 404/401.
- El modelo `NVIDIA_MODEL` debe soportar tool calling — usa los recomendados de la tabla.

**"Base de conocimiento no inicializada"**
- Ejecuta `python -m backend.rag.ingest` con Ollama corriendo y `mxbai-embed-large` descargado.

**Error 404 de NVIDIA API**
- El modelo indicado en `NVIDIA_MODEL` no está disponible en tu API key/tier.
- Usa `mistralai/mistral-small-3.1-24b-instruct` o `meta/llama-3.1-8b-instruct`.

**El frontend no carga / error CORS**
- Verifica que FastAPI esté en `:8000` y el proxy de Vite esté configurado en `vite.config.ts`.

**yfinance devuelve datos vacíos**
- Yahoo Finance cambia sus endpoints periódicamente. Actualiza yfinance: `pip install -U yfinance`.

---

## Autor

**Iván Della Ventura** — Práctica IX — Agentes de IA

*Este software es educativo. No constituye asesoramiento financiero.*
