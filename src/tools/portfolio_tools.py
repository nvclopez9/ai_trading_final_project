"""Tools de cartera simulada (multi-portfolio aware).

Cuatro tools originales (buy/sell/view/transactions) + tres nuevas para
multi-cartera (list/set_risk/set_markets). Todas operan sobre la cartera
activa, que se cambia desde la UI con ``set_active_portfolio``.

NOTA IMPORTANTE: NO existe tool para modificar ``initial_cash``. El dinero
inicial de una cartera es inmutable desde el agente: el usuario debe crear
una nueva cartera desde la UI.
"""
from langchain_core.tools import tool

from src.services import portfolio
from src.services import portfolios

OK_ICON = "✅"
ERR_ICON = "❌"

# Estado módulo-level del portfolio activo. La UI lo ajusta al cambiar el
# selector. Si es None, las tools caen al id 1 (Default).
_ACTIVE_PORTFOLIO_ID: int | None = None


def set_active_portfolio(portfolio_id: int) -> None:
    """La UI llama a esto cuando el usuario cambia de cartera activa."""
    global _ACTIVE_PORTFOLIO_ID
    _ACTIVE_PORTFOLIO_ID = int(portfolio_id) if portfolio_id is not None else None


def get_active_portfolio_id() -> int:
    return _ACTIVE_PORTFOLIO_ID if _ACTIVE_PORTFOLIO_ID is not None else 1


def _active_name_suffix() -> str:
    """Devuelve sufijo ' (cartera: NOMBRE)' para que el agente indique qué cartera usa."""
    pid = get_active_portfolio_id()
    p = portfolios.get_portfolio(pid)
    if p is None:
        return f" (cartera id={pid})"
    return f" (cartera: {p['name']})"


@tool
def portfolio_buy(ticker: str, qty: float) -> str:
    """Ejecuta una COMPRA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Opera sobre la cartera ACTIVA del usuario.
    Usa esta tool cuando el usuario pida comprar, adquirir o añadir acciones.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer."""
    try:
        pid = get_active_portfolio_id()
        r = portfolio.buy(ticker, float(qty), portfolio_id=pid)
        return (
            f"{OK_ICON} Compra ejecutada{_active_name_suffix()}: {r['qty']:g} acciones de {r['ticker']} "
            f"a ${r['price']:.2f}. "
            f"Posición total: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        return f"{ERR_ICON} No se pudo ejecutar la compra: {e}"
    except Exception as e:
        return f"{ERR_ICON} Error inesperado al comprar '{ticker}': {e}"


@tool
def portfolio_sell(ticker: str, qty: float) -> str:
    """Ejecuta una VENTA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Opera sobre la cartera ACTIVA del usuario.
    Valida posición existente y cantidad suficiente.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer."""
    try:
        pid = get_active_portfolio_id()
        r = portfolio.sell(ticker, float(qty), portfolio_id=pid)
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
        return f"{ERR_ICON} No se pudo ejecutar la venta: {e}"
    except Exception as e:
        return f"{ERR_ICON} Error inesperado al vender '{ticker}': {e}"


@tool
def portfolio_view() -> str:
    """Muestra el estado actual de la cartera ACTIVA: efectivo disponible,
    posiciones, precio medio, precio actual, valor de mercado, P&L por
    posición, valor total invertido y patrimonio total (cash + posiciones).
    Usa esta tool cuando el usuario pregunte por su cartera, posiciones,
    rentabilidad, efectivo o patrimonio."""
    try:
        pid = get_active_portfolio_id()
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
        return "\n".join(lines)
    except Exception as e:
        return f"{ERR_ICON} Error consultando la cartera: {e}"


@tool
def portfolio_transactions(limit: int = 10) -> str:
    """Devuelve las últimas transacciones de la cartera ACTIVA.
    Parámetro limit: número máximo de transacciones a mostrar (por defecto 10)."""
    try:
        pid = get_active_portfolio_id()
        txs = portfolio.get_transactions(limit=int(limit), portfolio_id=pid)
        if not txs:
            return f"No hay transacciones registradas{_active_name_suffix()}."
        header = f"{'Fecha':<20}{'Ticker':<8}{'Lado':<6}{'Qty':>8}{'Precio':>10}"
        lines = [f"Últimas {len(txs)} transacciones{_active_name_suffix()}:", header, "-" * len(header)]
        for t in txs:
            lines.append(
                f"{t['ts']:<20}{t['ticker']:<8}{t['side']:<6}"
                f"{t['qty']:>8.2f}{t['price']:>10.2f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"{ERR_ICON} Error consultando transacciones: {e}"


@tool
def portfolio_list() -> str:
    """Lista todas las carteras disponibles con un resumen (id, nombre, cash,
    riesgo, mercados, número de posiciones). Usa esta tool cuando el usuario
    pida ver sus carteras o comparar entre ellas."""
    try:
        items = portfolios.list_portfolios()
        if not items:
            return "No hay carteras creadas todavía."
        active_id = get_active_portfolio_id()
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
        return f"{ERR_ICON} Error listando carteras: {e}"


@tool
def portfolio_set_risk(risk: str) -> str:
    """Cambia el nivel de riesgo de la cartera ACTIVA.
    Valores válidos: 'conservador', 'moderado', 'agresivo'."""
    try:
        pid = get_active_portfolio_id()
        p = portfolios.update_risk(pid, risk)
        return f"{OK_ICON} Riesgo actualizado a '{p['risk']}' en la cartera '{p['name']}'."
    except ValueError as e:
        return f"{ERR_ICON} No se pudo actualizar el riesgo: {e}"
    except Exception as e:
        return f"{ERR_ICON} Error actualizando riesgo: {e}"


@tool
def portfolio_set_markets(markets: str) -> str:
    """Cambia los mercados objetivo de la cartera ACTIVA.
    Acepta CSV tipo 'USA,Europa' o 'all'. Valores válidos:
    USA, EUROPA, ASIA, GLOBAL, ALL."""
    try:
        pid = get_active_portfolio_id()
        p = portfolios.update_markets(pid, markets)
        return (
            f"{OK_ICON} Mercados actualizados a '{p['markets']}' en la cartera "
            f"'{p['name']}'."
        )
    except ValueError as e:
        return f"{ERR_ICON} No se pudo actualizar los mercados: {e}"
    except Exception as e:
        return f"{ERR_ICON} Error actualizando mercados: {e}"
