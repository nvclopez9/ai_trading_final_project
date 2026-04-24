"""Servicio de cartera simulada: lógica de compra, venta, posiciones y valor.

Las funciones aceptan ``portfolio_id`` para soportar multi-cartera (Feature
1). Por compatibilidad con los tests antiguos que no pasan el argumento, el
parámetro tiene default=1 (Default seed).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import yfinance as yf

from src.services.db import get_conn


def _current_price(symbol: str) -> float | None:
    """Obtiene el precio actual de un ticker; devuelve None si falla."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            hist = t.history(period="5d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
        return float(price) if price is not None else None
    except Exception:
        return None


def buy(ticker: str, qty: float, price: float | None = None, portfolio_id: int = 1) -> dict:
    """Compra simulada. Scoped por ``portfolio_id``."""
    symbol = ticker.strip().upper()
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    pid = int(portfolio_id)

    if price is None:
        price = _current_price(symbol)
        if price is None:
            raise ValueError(f"No se pudo obtener el precio actual de '{symbol}'.")
    price = float(price)
    qty = float(qty)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT qty, avg_price FROM positions WHERE ticker = ? AND portfolio_id = ?",
            (symbol, pid),
        )
        row = cur.fetchone()
        if row is None:
            new_qty = qty
            new_avg = price
            cur.execute(
                "INSERT INTO positions (ticker, qty, avg_price, portfolio_id) VALUES (?, ?, ?, ?)",
                (symbol, new_qty, new_avg, pid),
            )
        else:
            cur_qty = float(row["qty"])
            cur_avg = float(row["avg_price"])
            new_qty = cur_qty + qty
            new_avg = (cur_qty * cur_avg + qty * price) / new_qty if new_qty else price
            cur.execute(
                "UPDATE positions SET qty = ?, avg_price = ? WHERE ticker = ? AND portfolio_id = ?",
                (new_qty, new_avg, symbol, pid),
            )

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO transactions (ticker, side, qty, price, ts, portfolio_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, "BUY", qty, price, ts, pid),
        )
        conn.commit()

    return {
        "ticker": symbol,
        "qty": qty,
        "price": price,
        "new_qty": new_qty,
        "new_avg_price": new_avg,
        "portfolio_id": pid,
    }


def sell(ticker: str, qty: float, price: float | None = None, portfolio_id: int = 1) -> dict:
    """Venta simulada. Scoped por ``portfolio_id``."""
    symbol = ticker.strip().upper()
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    pid = int(portfolio_id)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT qty, avg_price FROM positions WHERE ticker = ? AND portfolio_id = ?",
            (symbol, pid),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No tienes posición abierta en '{symbol}'.")
        cur_qty = float(row["qty"])
        cur_avg = float(row["avg_price"])
        if qty > cur_qty:
            raise ValueError(
                f"No puedes vender {qty} de '{symbol}': solo posees {cur_qty}."
            )

        if price is None:
            price = _current_price(symbol)
            if price is None:
                raise ValueError(f"No se pudo obtener el precio actual de '{symbol}'.")
        price = float(price)
        qty = float(qty)

        new_qty = cur_qty - qty
        if new_qty <= 0:
            cur.execute(
                "DELETE FROM positions WHERE ticker = ? AND portfolio_id = ?",
                (symbol, pid),
            )
            new_avg = cur_avg
            new_qty = 0.0
        else:
            new_avg = cur_avg
            cur.execute(
                "UPDATE positions SET qty = ? WHERE ticker = ? AND portfolio_id = ?",
                (new_qty, symbol, pid),
            )

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO transactions (ticker, side, qty, price, ts, portfolio_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, "SELL", qty, price, ts, pid),
        )
        conn.commit()

    return {
        "ticker": symbol,
        "qty": qty,
        "price": price,
        "new_qty": new_qty,
        "new_avg_price": new_avg,
        "portfolio_id": pid,
    }


def get_positions(portfolio_id: int = 1) -> list[dict]:
    """Devuelve posiciones de la cartera indicada, con precio actual y P&L."""
    pid = int(portfolio_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT ticker, qty, avg_price FROM positions "
            "WHERE portfolio_id = ? ORDER BY ticker ASC",
            (pid,),
        )
        rows = cur.fetchall()

    tickers = [r["ticker"] for r in rows]
    if len(tickers) > 3:
        with ThreadPoolExecutor(max_workers=8) as ex:
            prices = dict(zip(tickers, ex.map(_current_price, tickers)))
    else:
        prices = {t: _current_price(t) for t in tickers}

    positions = []
    for r in rows:
        ticker = r["ticker"]
        qty = float(r["qty"])
        avg_price = float(r["avg_price"])
        current_price = prices.get(ticker)
        cost_basis = qty * avg_price
        if current_price is None:
            market_value = None
            pnl = None
            pnl_pct = None
        else:
            market_value = qty * current_price
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
        positions.append({
            "ticker": ticker,
            "qty": qty,
            "avg_price": avg_price,
            "current_price": current_price,
            "cost_basis": cost_basis,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
    return positions


def get_transactions(limit: int = 50, portfolio_id: int = 1) -> list[dict]:
    """Últimas N transacciones de la cartera indicada."""
    pid = int(portfolio_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ticker, side, qty, price, ts FROM transactions "
            "WHERE portfolio_id = ? "
            "ORDER BY ts DESC, id DESC LIMIT ?",
            (pid, int(limit)),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "ticker": r["ticker"],
            "side": r["side"],
            "qty": float(r["qty"]) if r["qty"] is not None else 0.0,
            "price": float(r["price"]) if r["price"] is not None else 0.0,
            "ts": r["ts"],
        }
        for r in rows
    ]


def get_portfolio_value(portfolio_id: int = 1) -> dict:
    """Totales agregados de la cartera indicada."""
    positions = get_positions(portfolio_id=portfolio_id)
    total_value = 0.0
    total_cost = 0.0
    stale_tickers: list[str] = []
    for p in positions:
        if p["market_value"] is None:
            stale_tickers.append(p["ticker"])
            continue
        total_cost += p["cost_basis"] or 0.0
        total_value += p["market_value"]
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "stale_tickers": stale_tickers,
    }
