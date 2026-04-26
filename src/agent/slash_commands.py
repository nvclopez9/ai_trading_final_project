"""Slash commands: fast-path determinista sin pasar por el LLM.

Objetivo: cuando el usuario empieza un mensaje con ``/`` (p. ej. ``/precio AAPL``)
ruteamos directamente a la tool/servicio correspondiente sin invocar al agente.
Esto reduce latencia, ahorra tokens y elimina el riesgo de alucinación numérica
porque la cifra viaja sin pasar por el modelo.

Cómo se integra (ver ``pages/1_Chat.py``):

    resp = try_handle_slash(user_input, session_id, active_portfolio_id)
    if resp is not None:
        # Renderizar resp["text"] (+resp["chart"] opcional) y persistir en
        # historia ANTES de salir; sin llamar al agente.
        return

Cada handler devuelve un dict con la siguiente forma:

    {
        "text": str,                          # respuesta principal (markdown)
        "chart": go.Figure | None,            # opcional: gráfico Plotly
        "history_user": str,                  # qué guardar como mensaje user en
                                              # la historia interna del runnable
        "history_ai": str,                    # qué guardar como respuesta AI
        "is_pending_buy": bool (opcional),    # True para HITL de /comprar
        "is_pending_sell": bool (opcional),   # True para HITL de /vender
        "pending_payload": dict (opcional),   # info para confirmación (ticker, qty)
        "clear_history": bool (opcional),     # True para /limpiar
    }

Errores: cada handler valida sus argumentos y devuelve un mensaje legible
(``"❌ ..."``) en ``text`` cuando algo falla. NUNCA propaga excepciones al caller.
"""
from __future__ import annotations

from typing import Optional

from src.agent.agent_builder import get_session_history
from src.services import portfolio as portfolio_svc
from src.services import portfolios as portfolios_svc
from src.tools.market_tools import (
    fetch_ticker_news,
    get_ticker_history,
    get_ticker_status,
)
from src.tools.portfolio_tools import set_active_portfolio
from src.ui.charts import price_history_chart


# ---- Comandos disponibles --------------------------------------------------

# Mantenemos el catálogo en una constante para que ``/ayuda`` pueda introspectarlo
# y los tests puedan asertar el contrato sin acoplarse al wording final.
COMMAND_USAGES: dict[str, str] = {
    "/precio": "/precio TICKER  — estado actual del ticker (precio, cambio %, P/E, market cap).",
    "/historico": "/historico TICKER [PERIODO]  — histórico (default 3mo). Ej: /historico AAPL 6mo.",
    "/comprar": "/comprar TICKER QTY  — propone una compra (HITL: confirmar después).",
    "/vender": "/vender TICKER QTY  — propone una venta (HITL: confirmar después).",
    "/cartera": "/cartera  — posiciones de la cartera activa.",
    "/noticias": "/noticias TICKER  — últimas noticias del ticker.",
    "/limpiar": "/limpiar  — vacía el historial de chat.",
    "/ayuda": "/ayuda  — lista de todos los comandos disponibles.",
}


def _invoke_tool(tool, **kwargs):
    """Invoca una tool de LangChain (decorada con @tool) o una función plana."""
    if hasattr(tool, "invoke"):
        return tool.invoke(kwargs)
    return tool(**kwargs)


def _persist_turn(session_id: str, user_msg: str, ai_msg: str) -> None:
    """Persiste el turno en la historia interna del agente.

    Why: aunque la respuesta no pase por el LLM, queremos que el siguiente turno
    del agente vea este intercambio en su ``chat_history`` para mantener
    coherencia conversacional (p. ej. "y dame el histórico" tras ``/precio AAPL``).
    """
    try:
        history = get_session_history(session_id)
        history.add_user_message(user_msg)
        history.add_ai_message(ai_msg)
    except Exception:
        # No bloqueamos la UI si la historia falla por cualquier motivo.
        pass


# ---- Handlers --------------------------------------------------------------

def _cmd_precio(args: list[str]) -> dict:
    if not args:
        return {"text": f"❌ Falta el ticker.\n`{COMMAND_USAGES['/precio']}`"}
    ticker = args[0].upper()
    raw = _invoke_tool(get_ticker_status, ticker=ticker)
    # Heurística: la tool devuelve mensajes de error empezando por "Error" o
    # conteniendo "No se encontraron datos". En ese caso convertimos al estilo de la guía.
    low = raw.lower()
    if low.startswith("error") or "no se encontraron datos" in low:
        return {"text": f"❌ No encontré el ticker {ticker}."}
    return {"text": f"```\n{raw}\n```"}


def _cmd_historico(args: list[str]) -> dict:
    if not args:
        return {"text": f"❌ Falta el ticker.\n`{COMMAND_USAGES['/historico']}`"}
    ticker = args[0].upper()
    period = args[1] if len(args) > 1 else "3mo"
    raw = _invoke_tool(get_ticker_history, ticker=ticker, period=period)
    low = raw.lower()
    if low.startswith("error") or "no hay histórico" in low:
        return {"text": f"❌ No encontré histórico para {ticker} ({period})."}
    chart = None
    try:
        chart = price_history_chart(ticker, period=period)
    except Exception:
        chart = None
    return {
        "text": f"**Histórico {ticker} · {period}**\n\n```\n{raw}\n```",
        "chart": chart,
    }


def _cmd_comprar(args: list[str]) -> dict:
    if len(args) < 2:
        return {"text": f"❌ Faltan argumentos.\n`{COMMAND_USAGES['/comprar']}`"}
    ticker = args[0].upper()
    try:
        qty = float(args[1])
    except ValueError:
        return {"text": f"❌ Cantidad inválida: '{args[1]}'."}
    if qty <= 0:
        return {"text": "❌ La cantidad debe ser mayor que 0."}
    # HITL: solo proponemos. La página renderizará un botón de confirmación.
    return {
        "text": (
            f"⚠ Vas a **COMPRAR** `{qty:g}` acciones de **{ticker}** al precio "
            f"de mercado actual.\n\nPulsa **Confirmar** para ejecutar."
        ),
        "is_pending_buy": True,
        "pending_payload": {"ticker": ticker, "qty": qty, "side": "BUY"},
    }


def _cmd_vender(args: list[str]) -> dict:
    if len(args) < 2:
        return {"text": f"❌ Faltan argumentos.\n`{COMMAND_USAGES['/vender']}`"}
    ticker = args[0].upper()
    try:
        qty = float(args[1])
    except ValueError:
        return {"text": f"❌ Cantidad inválida: '{args[1]}'."}
    if qty <= 0:
        return {"text": "❌ La cantidad debe ser mayor que 0."}
    return {
        "text": (
            f"⚠ Vas a **VENDER** `{qty:g}` acciones de **{ticker}** al precio "
            f"de mercado actual.\n\nPulsa **Confirmar** para ejecutar."
        ),
        "is_pending_sell": True,
        "pending_payload": {"ticker": ticker, "qty": qty, "side": "SELL"},
    }


def _cmd_cartera(portfolio_id: int) -> dict:
    """Render rápido de posiciones cartera activa (no mete LLM por medio)."""
    try:
        pid = int(portfolio_id) if portfolio_id is not None else 1
        # Aseguramos que las tools vean el portfolio activo correcto.
        set_active_portfolio(pid)
        positions = portfolio_svc.get_positions(portfolio_id=pid)
        cash = portfolios_svc.cash_available(pid)
        p = portfolios_svc.get_portfolio(pid)
        name = p["name"] if p else f"#{pid}"
        if not positions:
            txt = (
                f"**Cartera #{pid} · {name}**\n\n"
                f"Sin posiciones abiertas.\n"
                f"Efectivo disponible: `${cash:,.2f}`."
            )
            return {"text": txt}
        totals = portfolio_svc.get_portfolio_value(portfolio_id=pid)
        invested = totals["total_value"]
        net = invested + cash
        lines = [
            f"**Cartera #{pid} · {name}**",
            "",
            "| Ticker | Qty | Avg | Actual | Valor | P&L | P&L % |",
            "|---|---|---|---|---|---|---|",
        ]
        for pos in positions:
            cur = f"{pos['current_price']:.2f}" if pos["current_price"] is not None else "—"
            mv = f"{pos['market_value']:.2f}" if pos["market_value"] is not None else "—"
            pnl = f"{pos['pnl']:+.2f}" if pos["pnl"] is not None else "—"
            pnlp = f"{pos['pnl_pct']:+.2f}%" if pos["pnl_pct"] is not None else "—"
            lines.append(
                f"| {pos['ticker']} | {pos['qty']:g} | {pos['avg_price']:.2f} | "
                f"{cur} | {mv} | {pnl} | {pnlp} |"
            )
        lines.append("")
        lines.append(
            f"Invertido: `${invested:,.2f}`  ·  Cash: `${cash:,.2f}`  ·  "
            f"**Patrimonio: `${net:,.2f}`**"
        )
        return {"text": "\n".join(lines)}
    except Exception as e:
        return {"text": f"❌ Error consultando la cartera: {e}"}


def _cmd_noticias(args: list[str]) -> dict:
    if not args:
        return {"text": f"❌ Falta el ticker.\n`{COMMAND_USAGES['/noticias']}`"}
    ticker = args[0].upper()
    try:
        items = fetch_ticker_news(ticker, limit=5)
    except Exception as e:
        return {"text": f"❌ No pude obtener noticias para {ticker}: {e}"}
    if not items:
        return {"text": f"❌ No encontré noticias recientes para {ticker}."}
    lines = [f"**Noticias recientes · {ticker}**", ""]
    for i, n in enumerate(items, start=1):
        title = n["title"]
        date = n.get("date", "s/f")
        src = n.get("source", "?")
        link = n.get("link", "")
        if link:
            lines.append(f"{i}. [{title}]({link}) — *{src}* ({date})")
        else:
            lines.append(f"{i}. {title} — *{src}* ({date})")
    return {"text": "\n".join(lines)}


def _cmd_limpiar(session_id: str) -> dict:
    """Vacía el historial visual y la memoria interna del agente."""
    try:
        get_session_history(session_id).clear()
    except Exception:
        pass
    return {
        "text": "🧹 Historial vaciado.",
        "clear_history": True,
    }


def _cmd_ayuda() -> dict:
    lines = ["**Comandos disponibles**", ""]
    for cmd, usage in COMMAND_USAGES.items():
        lines.append(f"- `{usage}`")
    return {"text": "\n".join(lines)}


# ---- Entrypoint ------------------------------------------------------------

def try_handle_slash(
    text: str,
    session_id: str,
    portfolio_id: Optional[int] = None,
    *,
    persist_history: bool = True,
) -> Optional[dict]:
    """Si ``text`` es un slash command, lo ejecuta y devuelve el dict con la
    respuesta. Si no, devuelve ``None`` y el caller debe seguir el flujo normal
    (invocar al agente).

    Parámetros:
      - text: el input del usuario (cualquier whitespace por delante se ignora).
      - session_id: identificador de sesión Streamlit (para persistir historia).
      - portfolio_id: id de la cartera activa (necesario para ``/cartera``).
      - persist_history: si True, escribe el turno en la historia del agente.
        Lo desactivamos en tests para no requerir un session real.
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/precio":
        result = _cmd_precio(args)
    elif cmd == "/historico":
        result = _cmd_historico(args)
    elif cmd == "/comprar":
        result = _cmd_comprar(args)
    elif cmd == "/vender":
        result = _cmd_vender(args)
    elif cmd == "/cartera":
        result = _cmd_cartera(portfolio_id if portfolio_id is not None else 1)
    elif cmd == "/noticias":
        result = _cmd_noticias(args)
    elif cmd == "/limpiar":
        result = _cmd_limpiar(session_id)
    elif cmd == "/ayuda":
        result = _cmd_ayuda()
    else:
        # Slash desconocido: avisamos al usuario sin pasar por el LLM.
        result = {
            "text": (
                f"❌ Comando desconocido: `{cmd}`. Escribe `/ayuda` para ver "
                f"los disponibles."
            )
        }

    # Defaults para que el caller no tenga que hacer .get() en cada campo.
    result.setdefault("chart", None)
    result.setdefault("history_user", stripped)
    result.setdefault("history_ai", result["text"])
    result.setdefault("is_pending_buy", False)
    result.setdefault("is_pending_sell", False)
    result.setdefault("pending_payload", None)
    result.setdefault("clear_history", False)

    # Persistencia en historia (solo si no estamos limpiando: limpiar borra
    # primero, no queremos volver a escribir nada).
    if persist_history and not result["clear_history"]:
        _persist_turn(session_id, result["history_user"], result["history_ai"])

    return result


def execute_pending_trade(payload: dict, portfolio_id: int) -> str:
    """Ejecuta una compra/venta tras la confirmación HITL.

    El handler ``/comprar`` y ``/vender`` solo PROPONEN. La UI llama a esta
    función cuando el usuario pulsa "Confirmar" en el botón.
    """
    try:
        ticker = str(payload["ticker"]).upper()
        qty = float(payload["qty"])
        side = str(payload["side"]).upper()
        pid = int(portfolio_id) if portfolio_id is not None else 1
        set_active_portfolio(pid)
        if side == "BUY":
            r = portfolio_svc.buy(ticker, qty, portfolio_id=pid)
            return (
                f"✅ Compra ejecutada: {r['qty']:g} {r['ticker']} @ "
                f"${r['price']:.2f}. Posición total: {r['new_qty']:g} @ avg "
                f"${r['new_avg_price']:.2f}."
            )
        elif side == "SELL":
            r = portfolio_svc.sell(ticker, qty, portfolio_id=pid)
            if r["new_qty"] == 0:
                return (
                    f"✅ Venta ejecutada: {r['qty']:g} {r['ticker']} @ "
                    f"${r['price']:.2f}. Posición cerrada."
                )
            return (
                f"✅ Venta ejecutada: {r['qty']:g} {r['ticker']} @ "
                f"${r['price']:.2f}. Restante: {r['new_qty']:g} @ avg "
                f"${r['new_avg_price']:.2f}."
            )
        return f"❌ Lado desconocido: {side}"
    except ValueError as e:
        return f"❌ No se pudo ejecutar: {e}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"
