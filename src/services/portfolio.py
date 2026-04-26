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
    """Obtiene el precio regular de cierre de un ticker; None si falla."""
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


def _after_hours_price(symbol: str) -> tuple[float | None, float | None]:
    """Devuelve ``(precio, cambio_pct)`` de la sesión extendida (post o pre-market).

    Yahoo expone ``postMarketPrice``/``preMarketPrice`` en ``Ticker.info`` durante
    sesión extendida (USA: 16:00–20:00 ET / 04:00–09:30 ET). Si no hay datos
    devuelve ``(None, None)``. Cualquier excepción se traga: este dato es
    informativo y no debe romper el render de la cartera.
    """
    try:
        info = yf.Ticker(symbol).info or {}
        ah = info.get("postMarketPrice")
        ah_pct = info.get("postMarketChangePercent")
        if ah is None:
            ah = info.get("preMarketPrice")
            ah_pct = info.get("preMarketChangePercent")
        if ah is None:
            return None, None
        ah = float(ah)
        if ah_pct is None:
            ref = info.get("regularMarketPrice") or info.get("currentPrice")
            if ref:
                ah_pct = (ah - float(ref)) / float(ref) * 100
        return ah, float(ah_pct) if ah_pct is not None else None
    except Exception:
        return None, None


def recent_duplicate_buy(
    ticker: str, qty: float, price: float, portfolio_id: int = 1, window_seconds: int = 30
) -> dict | None:
    """Devuelve la transacción BUY casi-idéntica más reciente (<window_seconds) o None.
    Coincidencia: mismo ticker, misma qty, precio dentro de ±1%."""
    symbol = ticker.strip().upper()
    pid = int(portfolio_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT qty, price, ts FROM transactions "
            "WHERE portfolio_id = ? AND ticker = ? AND side = 'BUY' "
            "ORDER BY ts DESC, id DESC LIMIT 1",
            (pid, symbol),
        )
        row = cur.fetchone()
    if row is None:
        return None
    try:
        prev_ts = datetime.fromisoformat(row["ts"])
    except (ValueError, TypeError):
        return None
    delta = (datetime.now(timezone.utc) - prev_ts).total_seconds()
    if delta < 0 or delta > window_seconds:
        return None
    if float(row["qty"]) != float(qty):
        return None
    prev_price = float(row["price"])
    if prev_price <= 0:
        return None
    if abs(prev_price - float(price)) / prev_price > 0.01:
        return None
    return {"qty": float(row["qty"]), "price": prev_price, "seconds_ago": int(delta)}


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
            ah_data = dict(zip(tickers, ex.map(_after_hours_price, tickers)))
    else:
        prices = {t: _current_price(t) for t in tickers}
        ah_data = {t: _after_hours_price(t) for t in tickers}

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

        ah_price, ah_pct = ah_data.get(ticker, (None, None))
        ah_value = qty * ah_price if ah_price is not None else None

        positions.append({
            "ticker": ticker,
            "qty": qty,
            "avg_price": avg_price,
            "current_price": current_price,
            "cost_basis": cost_basis,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "after_hours_price": ah_price,
            "after_hours_change_pct": ah_pct,
            "after_hours_value": ah_value,
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
    total_value_ah = 0.0
    has_ah = False
    stale_tickers: list[str] = []
    for p in positions:
        if p["market_value"] is None:
            stale_tickers.append(p["ticker"])
            continue
        total_cost += p["cost_basis"] or 0.0
        total_value += p["market_value"]
        if p.get("after_hours_value") is not None:
            total_value_ah += p["after_hours_value"]
            has_ah = True
        else:
            total_value_ah += p["market_value"]
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    ah_delta = total_value_ah - total_value if has_ah else None
    ah_delta_pct = (ah_delta / total_value * 100) if (has_ah and total_value) else None
    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "stale_tickers": stale_tickers,
        "total_value_after_hours": total_value_ah if has_ah else None,
        "after_hours_delta": ah_delta,
        "after_hours_delta_pct": ah_delta_pct,
    }
