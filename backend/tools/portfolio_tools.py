"""Tools de cartera simulada (multi-portfolio aware).

Cuatro tools originales (buy/sell/view/transactions) + tres nuevas para
multi-cartera (list/set_risk/set_markets). Todas operan sobre la cartera
activa, que se cambia desde la UI con ``set_active_portfolio``.

NOTA IMPORTANTE: NO existe tool para modificar ``initial_cash``. El dinero
inicial de una cartera es inmutable desde el agente: el usuario debe crear
una nueva cartera desde la UI.
"""
from langchain_core.tools import tool

from backend.services import portfolio
from backend.services import portfolios
from backend.utils.logger import get_logger, timed

log = get_logger("tools.portfolio")

OK_ICON = "✅"
ERR_ICON = "❌"

# Estado módulo-level del portfolio activo. La UI lo ajusta al cambiar el
# selector. Si es None, las tools caen al id 1 (Default).
_ACTIVE_PORTFOLIO_ID: int | None = None

# Why: cuando portfolio_buy detecta un posible duplicado avisa SIN ejecutar;
# si el agente reintenta inmediatamente con los mismos args, dejamos pasar.
_LAST_DUPLICATE_WARNING: tuple[int, str, float, float] | None = None


def set_active_portfolio(portfolio_id: int) -> None:
    """La UI llama a esto cuando el usuario cambia de cartera activa."""
    global _ACTIVE_PORTFOLIO_ID
    _ACTIVE_PORTFOLIO_ID = int(portfolio_id) if portfolio_id is not None else None


def get_active_portfolio_id() -> int:
    return _ACTIVE_PORTFOLIO_ID if _ACTIVE_PORTFOLIO_ID is not None else 1


def _active_name_suffix() -> str:
    """Devuelve sufijo ' (cartera #ID · NOMBRE)' para que el agente indique
    siempre qué cartera está manipulando (evita confusiones cuando el usuario
    tiene varias carteras y opera/lee a la vez)."""
    pid = get_active_portfolio_id()
    p = portfolios.get_portfolio(pid)
    if p is None:
        return f" (cartera #{pid})"
    return f" (cartera #{pid} · {p['name']})"


@tool
def portfolio_buy(ticker: str, qty: float) -> str:
    """Ejecuta una COMPRA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Opera sobre la cartera ACTIVA del usuario.
    Usa esta tool cuando el usuario pida comprar, adquirir o añadir acciones.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer."""
    global _LAST_DUPLICATE_WARNING
    log.debug(f"portfolio_buy called: {ticker} qty={qty}")
    try:
        pid = get_active_portfolio_id()
        symbol = str(ticker).strip().upper()
        qty_f = float(qty)

        # Detección de duplicado reciente (<30s, mismo ticker/qty, precio ±1%).
        price_now = portfolio._current_price(symbol)
        if price_now is not None:
            dup = portfolio.recent_duplicate_buy(symbol, qty_f, price_now, portfolio_id=pid)
            warned_key = (pid, symbol, qty_f, round(price_now, 2))
            if dup is not None and _LAST_DUPLICATE_WARNING != warned_key:
                _LAST_DUPLICATE_WARNING = warned_key
                return (
                    f"⚠️ Posible duplicado: ya hiciste esta misma compra hace "
                    f"{dup['seconds_ago']}s ({qty_f:g} {symbol} a ${dup['price']:.2f}). "
                    f"Confirma con \"sí, repite\" si era intencional."
                )

        with timed(log, f"portfolio.buy({symbol}, {qty_f})"):
            r = portfolio.buy(ticker, qty_f, portfolio_id=pid)
        _LAST_DUPLICATE_WARNING = None
        log.debug(f"result: bought {r['qty']:g} {r['ticker']} @ ${r['price']:.2f}")
        return (
            f"{OK_ICON} Compra ejecutada{_active_name_suffix()}: {r['qty']:g} acciones de {r['ticker']} "
            f"a ${r['price']:.2f}. "
            f"Posición total: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        log.warning(f"portfolio_buy({ticker}): {e}")
        return f"{ERR_ICON} No se pudo ejecutar la compra: {e}"
    except Exception as e:
        log.warning(f"portfolio_buy({ticker}) unexpected error: {e}")
        return f"{ERR_ICON} Error inesperado al comprar '{ticker}': {e}"


@tool
def portfolio_sell(ticker: str, qty: float) -> str:
    """Ejecuta una VENTA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Opera sobre la cartera ACTIVA del usuario.
    Valida posición existente y cantidad suficiente.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer.

    Esta tool valida internamente si la posición existe; llámala SIEMPRE que el
    usuario indique intención de vender, aun cuando creas que no hay posición. Si
    no la hay, devuelve un mensaje útil que puedes mostrar al usuario."""
    log.debug(f"portfolio_sell called: {ticker} qty={qty}")
    try:
        pid = get_active_portfolio_id()
        with timed(log, f"portfolio.sell({ticker}, {qty})"):
            r = portfolio.sell(ticker, float(qty), portfolio_id=pid)
        log.debug(f"result: sold {r['qty']:g} {r['ticker']} @ ${r['price']:.2f} remaining={r['new_qty']:g}")
        if r["new_qty"] == 0:
            return (
                f"{OK_ICON} Venta ejecutada{_active_name_suffix()}: {r['qty']:g} acciones de {r['ticker']} "
                f"a ${r['price']:.2f}. Posición cerrada."
            )
        return (
            f"{OK_ICON} Venta ejecutada{_active_name_suffix()}: {r['qty']:g} acciones de {r['ticker']} "
            f"a ${r['price']:.2f}. "
            f"Posición restante: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        log.warning(f"portfolio_sell({ticker}): {e}")
        return f"{ERR_ICON} No se pudo ejecutar la venta: {e}"
    except Exception as e:
        log.warning(f"portfolio_sell({ticker}) unexpected error: {e}")
        return f"{ERR_ICON} Error inesperado al vender '{ticker}': {e}"


@tool
def portfolio_view() -> str:
    """Muestra el estado actual de la cartera ACTIVA: efectivo disponible,
    posiciones, precio medio, precio actual, valor de mercado, P&L por
    posición, valor total invertido y patrimonio total (cash + posiciones).
    Usa esta tool cuando el usuario pregunte por su cartera, posiciones,
    rentabilidad, efectivo o patrimonio."""
    log.debug("portfolio_view called")
    try:
        pid = get_active_portfolio_id()
        with timed(log, f"portfolio.get_positions(pid={pid})"):
            positions = portfolio.get_positions(portfolio_id=pid)
        cash = portfolios.cash_available(pid)
        name_suffix = _active_name_suffix()

        if not positions:
            return (
                f"Cartera simulada{name_suffix} sin posiciones abiertas.\n"
                f"Efectivo disponible: ${cash:,.2f}\n"
                f"Patrimonio total: ${cash:,.2f} (todo en efectivo)."
            )

        totals = portfolio.get_portfolio_value(portfolio_id=pid)
        invested_value = totals["total_value"]
        net_worth = invested_value + cash

        header = (
            f"{'Ticker':<8}{'Qty':>8}{'Avg':>10}{'Actual':>10}"
            f"{'Valor':>12}{'P&L':>12}{'P&L %':>9}"
        )
        lines = [f"Cartera simulada{name_suffix}:", header, "-" * len(header)]
        for p in positions:
            cur = f"{p['current_price']:.2f}" if p['current_price'] is not None else "n/d"
            mv = f"{p['market_value']:.2f}" if p['market_value'] is not None else "n/d"
            pnl = f"{p['pnl']:+.2f}" if p['pnl'] is not None else "n/d"
            pnlp = f"{p['pnl_pct']:+.2f}%" if p['pnl_pct'] is not None else "n/d"
            lines.append(
                f"{p['ticker']:<8}{p['qty']:>8.2f}{p['avg_price']:>10.2f}"
                f"{cur:>10}{mv:>12}{pnl:>12}{pnlp:>9}"
            )
        lines.append("-" * len(header))
        lines.append(
            f"Valor invertido: ${invested_value:,.2f} | "
            f"coste: ${totals['total_cost']:,.2f} | "
            f"P&L: {totals['total_pnl']:+.2f} ({totals['total_pnl_pct']:+.2f}%)"
        )
        lines.append(
            f"Efectivo disponible: ${cash:,.2f}  |  "
            f"PATRIMONIO TOTAL: ${net_worth:,.2f}"
        )
        if totals.get("stale_tickers"):
            lines.append(
                "Nota: sin precio actual para " + ", ".join(totals["stale_tickers"]) +
                " (excluidos del valor invertido)."
            )
        log.debug(f"result: portfolio pid={pid} positions={len(positions)} net_worth={net_worth:.2f}")
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"portfolio_view error: {e}")
        return f"{ERR_ICON} Error consultando la cartera: {e}"


@tool
def portfolio_transactions(limit: int = 10) -> str:
    """Devuelve las últimas transacciones de la cartera ACTIVA.
    Parámetro limit: número máximo de transacciones a mostrar (por defecto 10)."""
    log.debug(f"portfolio_transactions called: limit={limit}")
    try:
        pid = get_active_portfolio_id()
        with timed(log, f"portfolio.get_transactions(pid={pid}, limit={limit})"):
            txs = portfolio.get_transactions(limit=int(limit), portfolio_id=pid)
        if not txs:
            return f"No hay transacciones registradas{_active_name_suffix()}."
        log.debug(f"result: {len(txs)} transactions returned")
        header = f"{'Fecha':<20}{'Ticker':<8}{'Lado':<6}{'Qty':>8}{'Precio':>10}"
        lines = [f"Últimas {len(txs)} transacciones{_active_name_suffix()}:", header, "-" * len(header)]
        for t in txs:
            lines.append(
                f"{t['ts']:<20}{t['ticker']:<8}{t['side']:<6}"
                f"{t['qty']:>8.2f}{t['price']:>10.2f}"
            )
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"portfolio_transactions error: {e}")
        return f"{ERR_ICON} Error consultando transacciones: {e}"


@tool
def portfolio_list() -> str:
    """Lista todas las carteras disponibles con un resumen (id, nombre, cash,
    riesgo, mercados, número de posiciones). Usa esta tool cuando el usuario
    pida ver sus carteras o comparar entre ellas."""
    log.debug("portfolio_list called")
    try:
        with timed(log, "portfolios.list_portfolios()"):
            items = portfolios.list_portfolios()
        if not items:
            return "No hay carteras creadas todavía."
        active_id = get_active_portfolio_id()
        log.debug(f"result: {len(items)} portfolios found")
        lines = [f"Carteras disponibles ({len(items)}):"]
        for p in items:
            cash = portfolios.cash_available(p["id"])
            npos = portfolios.count_positions(p["id"])
            marker = " [ACTIVA]" if p["id"] == active_id else ""
            lines.append(
                f"- #{p['id']} {p['name']}{marker} | cash: ${cash:,.2f} "
                f"| riesgo: {p['risk']} | mercados: {p['markets']} "
                f"| posiciones: {npos}"
            )
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"portfolio_list error: {e}")
        return f"{ERR_ICON} Error listando carteras: {e}"


@tool
def portfolio_set_risk(risk: str) -> str:
    """Cambia el nivel de riesgo de la cartera ACTIVA.
    Valores válidos: 'conservador', 'moderado', 'agresivo'."""
    log.debug(f"portfolio_set_risk called: risk={risk}")
    try:
        pid = get_active_portfolio_id()
        p = portfolios.update_risk(pid, risk)
        log.debug(f"result: risk set to '{p['risk']}' for portfolio '{p['name']}'")
        return f"{OK_ICON} Riesgo actualizado a '{p['risk']}' en la cartera '{p['name']}'."
    except ValueError as e:
        log.warning(f"portfolio_set_risk({risk}): {e}")
        return f"{ERR_ICON} No se pudo actualizar el riesgo: {e}"
    except Exception as e:
        log.warning(f"portfolio_set_risk({risk}) unexpected error: {e}")
        return f"{ERR_ICON} Error actualizando riesgo: {e}"


@tool
def portfolio_set_markets(markets: str) -> str:
    """Cambia los mercados objetivo de la cartera ACTIVA.
    Acepta CSV tipo 'USA,Europa' o 'all'. Valores válidos:
    USA, EUROPA, ASIA, GLOBAL, ALL."""
    log.debug(f"portfolio_set_markets called: markets={markets}")
    try:
        pid = get_active_portfolio_id()
        p = portfolios.update_markets(pid, markets)
        log.debug(f"result: markets set to '{p['markets']}' for portfolio '{p['name']}'")
        return (
            f"{OK_ICON} Mercados actualizados a '{p['markets']}' en la cartera "
            f"'{p['name']}'."
        )
    except ValueError as e:
        log.warning(f"portfolio_set_markets({markets}): {e}")
        return f"{ERR_ICON} No se pudo actualizar los mercados: {e}"
    except Exception as e:
        log.warning(f"portfolio_set_markets({markets}) unexpected error: {e}")
        return f"{ERR_ICON} Error actualizando mercados: {e}"
