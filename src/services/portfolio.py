"""Servicio de cartera simulada: lógica de compra, venta, posiciones y valor.

Capa intermedia entre la BD SQLite (``src/services/db.py``) y las tools
que expone el agente (``src/tools/portfolio_tools.py``) + la UI
(``src/ui/portfolio_view.py``).

Decisiones clave para la exposición oral:
  - La función ``buy`` calcula el PRECIO MEDIO PONDERADO cuando el usuario
    ya tenía una posición abierta en ese ticker. La fórmula es
    ``(qty_prev * avg_prev + qty_nueva * precio_nuevo) / qty_total``.
    Ponderamos por cantidad porque queremos reflejar el coste REAL de la
    posición total, no la última compra. Ejemplo: compraste 10 a $100 y
    ahora 5 más a $120 -> avg = (1000+600)/15 = 106.67, no 120.
  - En ``sell`` mantenemos ``avg_price`` intacto en ventas parciales: el
    coste base de las acciones que quedan es el mismo que antes; solo
    reducimos la cantidad. Al cerrar la posición (qty <= 0) borramos la
    fila para no dejar posiciones fantasma con qty=0.
  - ``get_positions`` paraleliza la consulta de precios actuales con
    ``ThreadPoolExecutor`` cuando hay >3 posiciones, para que la pestaña
    de cartera no tarde 30+ segundos con yfinance en serie.
  - Los totales de la cartera excluyen los tickers "stale" (sin precio
    actual) para no inflar artificialmente el P&L con coste sin valor.
"""
# concurrent.futures: paralelizar las llamadas a yfinance sin añadir threading.
# datetime: timestamps ISO-8601 UTC (utcnow() está deprecated en 3.12, usamos now(tz)).
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# yfinance para obtener el precio actual en operaciones de compra/venta.
import yfinance as yf

# Conexión SQLite con row_factory configurado.
from src.services.db import get_conn


def _current_price(symbol: str) -> float | None:
    """Obtiene el precio actual de un ticker; devuelve None si falla.

    Mismo patrón que ``market_tools.get_ticker_status`` pero reducido: no
    necesitamos P/E ni market cap, solo el último precio para calcular P&L
    o precio de ejecución en compras/ventas.
    """
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        # Mismo doble alias que en market_tools para cubrir ambos shapes de Yahoo.
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            # Fallback: último Close de los 5 días recientes.
            hist = t.history(period="5d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
        return float(price) if price is not None else None
    except Exception:
        # Silenciamos: el llamante interpreta None como "sin precio disponible"
        # (stale ticker) y actúa en consecuencia (excluir del total, n/d, etc.).
        return None


def buy(ticker: str, qty: float, price: float | None = None) -> dict:
    """Compra simulada: incrementa la posición y registra la transacción.

    Si ``price`` es None se consulta el precio actual de mercado. Si ya
    existía posición en el ticker, se recalcula el precio medio ponderado.
    """
    # Normalización + validación básica: el símbolo siempre en mayúsculas,
    # sin espacios; qty estrictamente positiva.
    symbol = ticker.strip().upper()
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    # Si no pasan precio (caso normal desde la tool), lo pedimos a yfinance.
    # Un fallo aquí es un error que la tool debe reportar — por eso raise.
    if price is None:
        price = _current_price(symbol)
        if price is None:
            raise ValueError(f"No se pudo obtener el precio actual de '{symbol}'.")
    price = float(price)
    qty = float(qty)

    # Todo lo que sigue es una sola transacción SQLite: SELECT + INSERT/UPDATE
    # + INSERT transacción, con un único commit al final para atomicidad.
    with get_conn() as conn:
        cur = conn.cursor()
        # Miramos si ya había posición abierta para este ticker.
        cur.execute("SELECT qty, avg_price FROM positions WHERE ticker = ?", (symbol,))
        row = cur.fetchone()
        if row is None:
            # Nueva posición: el avg es simplemente el precio de la compra.
            new_qty = qty
            new_avg = price
            cur.execute(
                "INSERT INTO positions (ticker, qty, avg_price) VALUES (?, ?, ?)",
                (symbol, new_qty, new_avg),
            )
        else:
            # Posición existente: avg PONDERADO por cantidad.
            # Esto refleja el coste real promedio de la cesta total de acciones,
            # no solo la última compra — fundamental para un P&L correcto después.
            cur_qty = float(row["qty"])
            cur_avg = float(row["avg_price"])
            new_qty = cur_qty + qty
            new_avg = (cur_qty * cur_avg + qty * price) / new_qty if new_qty else price
            cur.execute(
                "UPDATE positions SET qty = ?, avg_price = ? WHERE ticker = ?",
                (new_qty, new_avg, symbol),
            )

        # Registramos la operación en transactions (libro append-only) con
        # timestamp UTC ISO-8601 truncado a segundos (la granularidad de ms
        # no aporta nada en una cartera simulada).
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO transactions (ticker, side, qty, price, ts) VALUES (?, ?, ?, ?, ?)",
            (symbol, "BUY", qty, price, ts),
        )
        conn.commit()

    # Retornamos un dict con el resumen para que la tool lo formatee al usuario.
    return {
        "ticker": symbol,
        "qty": qty,
        "price": price,
        "new_qty": new_qty,
        "new_avg_price": new_avg,
    }


def sell(ticker: str, qty: float, price: float | None = None) -> dict:
    """Venta simulada: decrementa la posición o la cierra, y registra la transacción."""
    symbol = ticker.strip().upper()
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    with get_conn() as conn:
        cur = conn.cursor()
        # Validaciones: la posición debe existir y tener cantidad suficiente.
        # Si no, ValueError con mensaje claro (la tool lo convierte a string).
        cur.execute("SELECT qty, avg_price FROM positions WHERE ticker = ?", (symbol,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No tienes posición abierta en '{symbol}'.")
        cur_qty = float(row["qty"])
        cur_avg = float(row["avg_price"])
        if qty > cur_qty:
            raise ValueError(
                f"No puedes vender {qty} de '{symbol}': solo posees {cur_qty}."
            )

        # Obtenemos precio de ejecución (mercado actual) si no se pasó explícito.
        # Hacerlo DESPUÉS de validar qty evita pagar la latencia de yfinance
        # cuando la venta iba a fallar por validación de todos modos.
        if price is None:
            price = _current_price(symbol)
            if price is None:
                raise ValueError(f"No se pudo obtener el precio actual de '{symbol}'.")
        price = float(price)
        qty = float(qty)

        # Si al restar la venta la cantidad cae a cero (o por debajo por
        # epsilons de coma flotante), cerramos la posición borrando la fila.
        new_qty = cur_qty - qty
        if new_qty <= 0:
            cur.execute("DELETE FROM positions WHERE ticker = ?", (symbol,))
            # Preservamos el avg para devolverlo en el dict de resultado,
            # pero forzamos new_qty a 0.0 (no negativo) para la respuesta.
            new_avg = cur_avg
            new_qty = 0.0
        else:
            # Venta parcial: el avg NO cambia (las acciones remanentes tienen
            # el mismo coste base que antes). Solo actualizamos la cantidad.
            new_avg = cur_avg
            cur.execute(
                "UPDATE positions SET qty = ? WHERE ticker = ?",
                (new_qty, symbol),
            )

        # Igual que en buy: insertamos la operación en el libro con timestamp UTC.
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO transactions (ticker, side, qty, price, ts) VALUES (?, ?, ?, ?, ?)",
            (symbol, "SELL", qty, price, ts),
        )
        conn.commit()

    return {
        "ticker": symbol,
        "qty": qty,
        "price": price,
        "new_qty": new_qty,
        "new_avg_price": new_avg,
    }


def get_positions() -> list[dict]:
    """Devuelve la cartera: una fila por posición con coste, valor y P&L.

    Paraleliza la consulta de precios actuales cuando hay >3 posiciones
    (speedup N/8 en el peor caso). Para 1-3 posiciones, el overhead de
    crear el pool supera el ahorro.
    """
    # Leemos las posiciones de la BD (poco costoso).
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ticker, qty, avg_price FROM positions ORDER BY ticker ASC")
        rows = cur.fetchall()

    # Recogemos los tickers para consultar sus precios actuales en bloque.
    tickers = [r["ticker"] for r in rows]
    if len(tickers) > 3:
        # Pool de 8 workers: compromiso entre paralelismo y no saturar yfinance.
        # ex.map mantiene el orden de entrada, así que zip produce el dict correcto.
        with ThreadPoolExecutor(max_workers=8) as ex:
            prices = dict(zip(tickers, ex.map(_current_price, tickers)))
    else:
        # Pocas posiciones: llamadas secuenciales, más simples.
        prices = {t: _current_price(t) for t in tickers}

    # Componemos el resultado final combinando datos de BD y precios actuales.
    positions = []
    for r in rows:
        ticker = r["ticker"]
        qty = float(r["qty"])
        avg_price = float(r["avg_price"])
        current_price = prices.get(ticker)
        cost_basis = qty * avg_price
        # Si yfinance no devolvió precio, todas las métricas dependientes
        # quedan como None para que la UI las pinte vacías (no como 0, que
        # sería engañoso).
        if current_price is None:
            market_value = None
            pnl = None
            pnl_pct = None
        else:
            market_value = qty * current_price
            pnl = market_value - cost_basis
            # Evitamos división por cero si cost_basis es 0 por algún motivo raro.
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


def get_transactions(limit: int = 50) -> list[dict]:
    """Últimas N transacciones ordenadas por fecha descendente.

    Ordenamos por ts DESC y desempatamos por id DESC porque dos operaciones
    del mismo segundo tendrán el mismo ts truncado — el id (autoincremental)
    garantiza un orden estable.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ticker, side, qty, price, ts FROM transactions "
            "ORDER BY ts DESC, id DESC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
    # Convertimos sqlite3.Row a dicts "normales" para no acoplar al consumidor
    # (la UI) con el tipo de la librería.
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


def get_portfolio_value() -> dict:
    """Totales agregados de la cartera + lista de tickers sin precio actual.

    Excluye del total valor y del total coste las posiciones sin
    ``market_value`` (stale). Esto evita inflar negativamente el P&L
    cuando un ticker concreto no responde — mejor reportar
    ``stale_tickers`` y mostrar el P&L del resto con coherencia.
    """
    # Reutilizamos get_positions para no duplicar la lógica de cálculo.
    positions = get_positions()
    total_value = 0.0
    total_cost = 0.0
    stale_tickers: list[str] = []
    for p in positions:
        if p["market_value"] is None:
            # Apuntamos el ticker a la lista "stale" y NO sumamos su coste al
            # total para que la comparación valor/coste sea justa.
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
