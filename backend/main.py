"""FastAPI backend for the investment bot.

Run with:
    uvicorn backend.main:app --reload --port 8000

The React frontend (at http://localhost:5173) proxies /api/* here.
"""
import sys
import os

# Make the project root importable from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import portfolio, market, chat, news, preferences

app = FastAPI(
    title="Bot de Inversiones API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(chat.router)
app.include_router(news.router)
app.include_router(preferences.router)


@app.on_event("startup")
async def _configure_logging() -> None:
    """Re-apply log level AFTER uvicorn has set up its own logging config."""
    level_str = os.getenv("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_str, logging.WARNING)

    # Configure root logger so all app loggers inherit it
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("[%(levelname)s] %(name)s | %(message)s"))
        root.addHandler(_h)

    # Keep uvicorn's own loggers quiet to avoid noise at debug level
    _uvicorn_level = max(level, logging.WARNING)
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(_name).setLevel(_uvicorn_level)


@app.get("/api/health")
def health():
    return {"status": "ok"}
