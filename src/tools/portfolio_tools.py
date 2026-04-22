"""Tools de cartera simulada que expone el agente al usuario.

Son la capa de adaptación entre el agente LangChain (que llama funciones
con argumentos tipados y espera un string de vuelta) y los servicios de
lógica pura en ``src/services/portfolio.py`` (que trabajan con dicts y
lanzan ``ValueError`` en caso de entradas inválidas).

Cuatro tools:
  - ``portfolio_buy``: compra N acciones al precio de mercado actual.
  - ``portfolio_sell``: vende N acciones (valida cantidad disponible).
  - ``portfolio_view``: tabla ASCII con posiciones y P&L.
  - ``portfolio_transactions``: últimas N transacciones.

Didáctico: todas devuelven string (no dict) para que el modelo pequeño no
se atasque serializando JSON. Los ``ValueError`` del servicio (cantidad
<= 0, sin posición, qty insuficiente) se traducen a mensajes claros con
prefijo emoji para que el usuario final vea al instante si salió bien.
"""
# @tool: decorador de LangChain que convierte la función en una herramienta
# invocable por el LLM. Lee el docstring como descripción de la tool.
from langchain_core.tools import tool

# Lógica de cartera. Importamos el módulo entero (no los símbolos) para que
# los tests puedan monkeypatchear ``portfolio._current_price`` sin tocar la tool.
from src.services import portfolio

# Iconos de éxito/error. Van en las respuestas de las tools (que luego lee
# el LLM y reproduce en su respuesta final al usuario).
OK_ICON = "✅"
ERR_ICON = "❌"


@tool
def portfolio_buy(ticker: str, qty: float) -> str:
    """Ejecuta una COMPRA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Persiste la operación en la cartera simulada del usuario (SQLite).
    Usa esta tool cuando el usuario pida comprar, adquirir o añadir acciones.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer."""
    try:
        # Delegamos en portfolio.buy: recupera precio actual, hace avg ponderado
        # si ya existía posición, inserta la transacción. Puede lanzar ValueError
        # si qty <= 0 o yfinance no devuelve precio.
        r = portfolio.buy(ticker, float(qty))
        # Formato humano: qty con :g evita decimales si es entero (10 vs 10.00).
        return (
            f"{OK_ICON} Compra ejecutada: {r['qty']:g} acciones de {r['ticker']} "
            f"a ${r['price']:.2f}. "
            f"Posición total: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        # Errores de validación: mensaje claro, no stacktrace.
        return f"{ERR_ICON} No se pudo ejecutar la compra: {e}"
    except Exception as e:
        # Cualquier otro error (BD bloqueada, etc.): también controlado.
        return f"{ERR_ICON} Error inesperado al comprar '{ticker}': {e}"


@tool
def portfolio_sell(ticker: str, qty: float) -> str:
    """Ejecuta una VENTA simulada de 'qty' acciones del 'ticker' al precio de mercado actual.
    Valida que exista la posición y que la cantidad sea suficiente.
    Usa esta tool cuando el usuario pida vender, deshacerse o reducir una posición.
    Antes de llamarla, avisa brevemente al usuario de lo que vas a hacer."""
    try:
        # portfolio.sell valida posición existente y qty <= disponible, borra
        # la posición de la tabla si new_qty llega a cero, y registra la transacción.
        r = portfolio.sell(ticker, float(qty))
        # Mensaje distinto si cierra la posición vs si queda cantidad remanente.
        if r["new_qty"] == 0:
            return (
                f"{OK_ICON} Venta ejecutada: {r['qty']:g} acciones de {r['ticker']} "
                f"a ${r['price']:.2f}. Posición cerrada."
            )
        return (
            f"{OK_ICON} Venta ejecutada: {r['qty']:g} acciones de {r['ticker']} "
            f"a ${r['price']:.2f}. "
            f"Posición restante: {r['new_qty']:g} @ avg ${r['new_avg_price']:.2f}."
        )
    except ValueError as e:
        return f"{ERR_ICON} No se pudo ejecutar la venta: {e}"
    except Exception as e:
        return f"{ERR_ICON} Error inesperado al vender '{ticker}': {e}"


@tool
def portfolio_view() -> str:
    """Muestra el estado actual de la cartera simulada: posiciones abiertas, precio medio,
    precio actual, valor de mercado, P&L por posición y totales.
    Usa esta tool cuando el usuario pregunte por su cartera, posiciones o rentabilidad."""
    try:
        # Dos queries: posiciones (fila por ticker) y totales (agregado).
        # Ambos ya traen precio actual cacheado para cada ticker.
        positions = portfolio.get_positions()
        if not positions:
            return "Tu cartera simulada está vacía."
        totals = portfolio.get_portfolio_value()

        # Cabecera de tabla ASCII con anchos fijos. El LLM la resume al usuario
        # o la reproduce tal cual según la pregunta.
        header = (
            f"{'Ticker':<8}{'Qty':>8}{'Avg':>10}{'Actual':>10}"
            f"{'Valor':>12}{'P&L':>12}{'P&L %':>9}"
        )
        lines = ["Cartera simulada:", header, "-" * len(header)]
        # Pintamos cada posición con todas sus métricas. Si current_price vino
        # como None (yfinance caído para ese ticker) ponemos "n/d" — coherente
        # con get_ticker_status.
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
        # Fila de totales: valor, coste, P&L absoluto y P&L relativo.
        lines.append(
            f"TOTAL valor: ${totals['total_value']:.2f} | "
            f"coste: ${totals['total_cost']:.2f} | "
            f"P&L: {totals['total_pnl']:+.2f} ({totals['total_pnl_pct']:+.2f}%)"
        )
        # Si hubo tickers sin precio (yfinance caído), los listamos para que
        # el usuario sepa que no están contados en el total.
        if totals.get("stale_tickers"):
            lines.append(
                "Nota: sin precio actual para " + ", ".join(totals["stale_tickers"]) +
                " (excluidos del total)."
            )
        return "\n".join(lines)
    except Exception as e:
        return f"{ERR_ICON} Error consultando la cartera: {e}"


@tool
def portfolio_transactions(limit: int = 10) -> str:
    """Devuelve las últimas transacciones (compras y ventas) realizadas en la cartera simulada.
    Parámetro limit: número máximo de transacciones a mostrar (por defecto 10)."""
    try:
        # int(limit) es defensivo: el LLM a veces pasa "10" (string) como argumento.
        txs = portfolio.get_transactions(limit=int(limit))
        if not txs:
            return "No hay transacciones registradas."
        # Tabla ASCII con cabecera alineada. ts ya viene en ISO-8601.
        header = f"{'Fecha':<20}{'Ticker':<8}{'Lado':<6}{'Qty':>8}{'Precio':>10}"
        lines = [f"Últimas {len(txs)} transacciones:", header, "-" * len(header)]
        for t in txs:
            lines.append(
                f"{t['ts']:<20}{t['ticker']:<8}{t['side']:<6}"
                f"{t['qty']:>8.2f}{t['price']:>10.2f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"{ERR_ICON} Error consultando transacciones: {e}"
