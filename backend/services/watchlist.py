"""Servicio CRUD de la watchlist por cartera.

Una watchlist es una lista de tickers en seguimiento (NO posiciones reales)
asociada a un ``portfolio_id``. Sirve para que el usuario marque candidatos
sin tener que comprarlos.

Diseño:
- Persistencia en SQLite (tabla ``watchlist`` creada por ``init_db``).
- Cada item devuelto incluye precio actual y cambio diario, calculados de
  forma defensiva con yfinance: si la consulta falla, devolvemos None pero
  nunca lanzamos.
"""
from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf

from backend.services.db import get_conn


def _live_quote(ticker: str) -> tuple[float | None, float | None]:
    """Devuelve (precio_actual, change_pct_diario) de un ticker.

    Si la consulta falla por cualquier motivo (red, ticker malo, rate-limit),
    devolvemos (None, None) — la UI lo pinta como "n/d" y no rompe.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None or prev is None:
            hist = t.history(period="5d")
            if hist.empty or len(hist) < 2:
                return (None, None)
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
        change = ((float(price) - float(prev)) / float(prev) * 100) if prev else None
        return (float(price), change)
    except Exception:
        return (None, None)


def add(portfolio_id: int, ticker: str, note: str | None = None) -> None:
    """Añade un ticker a la watchlist (no duplica gracias a UNIQUE)."""
    sym = ticker.strip().upper()
    if not sym:
        raise ValueError("ticker vacío")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO watchlist (portfolio_id, ticker, note, added_at) "
            "VALUES (?, ?, ?, ?)",
            (int(portfolio_id), sym, note, ts),
        )
        conn.commit()


def remove(portfolio_id: int, ticker: str) -> None:
    """Elimina un ticker de la watchlist de la cartera indicada."""
    sym = ticker.strip().upper()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM watchlist WHERE portfolio_id = ? AND ticker = ?",
            (int(portfolio_id), sym),
        )
        conn.commit()


def list_for(portfolio_id: int) -> list[dict]:
    """Devuelve todos los items de la watchlist + precio en vivo + cambio diario."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ticker, note, added_at FROM watchlist "
            "WHERE portfolio_id = ? ORDER BY added_at DESC",
            (int(portfolio_id),),
        )
        rows = cur.fetchall()

    items: list[dict] = []
    for r in rows:
        price, change = _live_quote(r["ticker"])
        items.append({
            "id": r["id"],
            "ticker": r["ticker"],
            "note": r["note"],
            "added_at": r["added_at"],
            "price": price,
            "change_pct": change,
        })
    return items
