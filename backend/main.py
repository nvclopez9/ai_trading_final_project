"""FastAPI backend for the investment bot.

Run with:
    uvicorn backend.main:app --reload --port 8000

The React frontend (at http://localhost:5173) proxies /api/* here.
"""
import os
import logging
import logging.handlers
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import portfolio, market, chat, news, preferences, watchlist

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
app.include_router(watchlist.router)

_FILE_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_CONSOLE_FMT = logging.Formatter("[%(levelname)s] %(name)s | %(message)s")


@app.on_event("startup")
async def _configure_logging() -> None:
    """Configure root logger with console + rotating file handler after uvicorn startup."""
    level_str = os.getenv("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_str, logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler (replace any existing StreamHandlers so we own the formatter)
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.StreamHandler)
                     or isinstance(h, logging.FileHandler)]
    console = logging.StreamHandler()
    console.setFormatter(_CONSOLE_FMT)
    console.setLevel(level)
    root.addHandler(console)

    # File handler — rotating, 5 MB per file, 5 backups
    log_file = os.getenv("LOG_FILE", "logs/bot.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(_FILE_FMT)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    # Keep uvicorn's own loggers at WARNING to avoid access-log noise
    _uvicorn_level = max(level, logging.WARNING)
    for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(_name).setLevel(_uvicorn_level)

    logging.getLogger("backend").info(
        f"Logging configured: level={level_str}, file={log_path.resolve()}"
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
