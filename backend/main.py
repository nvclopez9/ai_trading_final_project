"""FastAPI backend for the investment bot.

Run with:
    uvicorn backend.main:app --reload --port 8000

The React frontend (at http://localhost:5173) proxies /api/* here.
"""
import sys
import os

# Make the project root importable from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
