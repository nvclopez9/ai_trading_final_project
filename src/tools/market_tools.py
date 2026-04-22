"""Tools de mercado para el agente: consultan Yahoo Finance via ``yfinance``.

Expone tres tools decoradas con ``@tool`` de LangChain para que el agente
pueda invocarlas por nombre:
  - ``get_ticker_status``: estado actual (precio, cambio, P/E, market cap).
  - ``get_ticker_history``: resumen histórico (máx/mín/variación) de un periodo.
  - ``get_hot_tickers``: top 10 tickers del mercado por categoría.

Nota didáctica importante: TODAS las tools devuelven ``str`` (no dict).
Con modelos pequeños como ``gemma3:4b`` el tool-calling es más fiable cuando
la observación ya es texto plano que el LLM puede resumir sin tener que
serializar/parsear JSON. Además, cualquier excepción se captura y se
convierte en un mensaje legible; así el agente nunca recibe un stacktrace
que rompa su bucle de razonamiento.
"""
# yfinance: cliente no oficial de Yahoo Finance (scraping).
import yfinance as yf
# @tool: convierte una función Python en una herramienta invocable por el
# agente. Usa el docstring como descripción que lee el LLM para decidir.
from langchain_core.tools import tool


# Universo de fallback: 30 componentes relevantes del S&P500. Se usa cuando
# el Screener oficial de yfinance falla (estructura cambia, rate-limit, etc.).
# Son pocos para que el bucle serie no tarde minutos; representan sectores
# diversos para que "gainers/losers/actives" den resultados razonables.
FALLBACK_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BRK-B", "JPM", "V",
    "WMT", "XOM", "UNH", "JNJ", "PG", "MA", "HD", "CVX", "LLY", "ABBV",
    "AVGO", "KO", "PEP", "COST", "MRK", "ORCL", "ADBE", "CSCO", "NKE", "DIS",
]


@tool
def get_ticker_status(ticker: str) -> str:
    """Obtiene el estado actual de un ticker bursátil: precio, cambio porcentual,
    P/E ratio, capitalización de mercado y nombre de la empresa.
    Parámetro: ticker (símbolo, por ejemplo 'AAPL', 'MSFT', 'TSLA')."""
    try:
        # Normalizamos el símbolo: yfinance espera mayúsculas y sin espacios.
        # El agente a veces llega con "aapl" o " MSFT " según cómo parsee el LLM.
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        # .info hace scraping y puede devolver None o dict parcial sin lanzar
        # excepción. El ``or {}`` nos da un dict vacío para poder hacer .get
        # sin preocuparnos.
        info = t.info or {}
        # Doble alias: Yahoo a veces expone un campo y a veces el otro.
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

        # Fallback si .info no trajo precio: pedimos los últimos 5 días de
        # historial y usamos el último cierre. Si el histórico también está
        # vacío, el ticker casi seguro no existe.
        if price is None:
            hist = t.history(period="5d")
            if hist.empty:
                return f"No se encontraron datos para el ticker '{symbol}'. Verifica que sea válido."
            price = float(hist["Close"].iloc[-1])
            # Para el cambio diario necesitamos el penúltimo cierre si no lo teníamos.
            if prev_close is None and len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])

        # Cálculo del cambio porcentual diario; si falta prev_close dejamos None.
        change_pct = None
        if price is not None and prev_close:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        # Metadatos presentables; longName suele existir, shortName es fallback.
        name = info.get("longName") or info.get("shortName") or symbol
        currency = info.get("currency", "USD")
        pe = info.get("trailingPE")
        mcap = info.get("marketCap")

        # Formateo defensivo: si algún campo viene como string/None, usamos "n/d"
        # en lugar de petar con un TypeError al formatear.
        price_str = f"{float(price):.2f} {currency}" if price is not None else "n/d"
        change_str = f"{change_pct:+.2f}%" if change_pct is not None else "n/d"
        pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else "n/d"
        mcap_str = f"{mcap:,}" if isinstance(mcap, (int, float)) else "n/d"

        # Respuesta multilínea en español: el LLM la resume al usuario siguiendo
        # la regla 5 del system prompt (no devolver JSON crudo).
        return (
            f"Ticker: {symbol} ({name})\n"
            f"Precio actual: {price_str}\n"
            f"Cambio diario: {change_str}\n"
            f"P/E ratio: {pe_str}\n"
            f"Capitalización de mercado: {mcap_str}"
        )
    except Exception as e:
        # Nunca propagamos excepciones al agente: devolvemos string controlado
        # para que el LLM pueda reaccionar (p.ej. sugerir verificar el símbolo).
        return f"Error consultando el ticker '{ticker}': {e}"


@tool
def get_ticker_history(ticker: str, period: str = "1mo") -> str:
    """Devuelve un resumen textual del histórico de precios de un ticker.
    Parámetros: ticker (símbolo), period (ej: '5d', '1mo', '3mo', '6mo', '1y', '5y').
    Incluye precio máximo, mínimo, último cierre y variación del periodo."""
    try:
        # Misma normalización que en get_ticker_status.
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        # history() devuelve un DataFrame pandas con columnas Open/High/Low/Close/Volume.
        hist = t.history(period=period)
        if hist.empty:
            return f"No hay histórico disponible para '{symbol}' en el periodo '{period}'."
        # Estadísticos básicos: máximo/mínimo del periodo y primer/último cierre
        # para calcular la variación porcentual total del periodo.
        high = float(hist["High"].max())
        low = float(hist["Low"].min())
        first = float(hist["Close"].iloc[0])
        last = float(hist["Close"].iloc[-1])
        # Guardamos contra división por cero (ticker con precio inicial 0 es
        # improbable pero posible con datos corruptos).
        change = round((last - first) / first * 100, 2) if first else 0.0
        return (
            f"Histórico de {symbol} ({period}): "
            f"máximo {high:.2f}, mínimo {low:.2f}, último cierre {last:.2f}, "
            f"variación del periodo {change}%."
        )
    except Exception as e:
        return f"Error obteniendo histórico de '{ticker}': {e}"


def _fetch_fallback_quotes():
    """Recorre el universo S&P500 hardcodeado y devuelve cotizaciones básicas.

    Se usa como fallback cuando el Screener de yfinance falla. Iteración
    serie (no paralelizada en Fase 2) para mantener el código simple; con 30
    tickers puede tardar 30-90 segundos — es el principal coste de latencia
    de ``get_hot_tickers`` cuando el Screener no está disponible.
    """
    rows = []
    for sym in FALLBACK_UNIVERSE:
        try:
            # Mismo patrón que get_ticker_status: intentamos info, caemos a history.
            t = yf.Ticker(sym)
            info = t.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
            if price is None or prev is None:
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    # No hay forma de calcular cambio sin dos cierres; saltamos.
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
            # Cambio porcentual diario; prev siempre != 0 aquí (ya checkeado).
            change_pct = (float(price) - float(prev)) / float(prev) * 100 if prev else 0.0
            volume = info.get("regularMarketVolume") or info.get("volume") or 0
            rows.append({
                "ticker": sym,
                "price": float(price),
                "change_pct": float(change_pct),
                "volume": int(volume) if volume else 0,
            })
        except Exception:
            # Un ticker caído no debe tumbar todo el universo: lo saltamos.
            continue
    return rows


def _format_table(rows, category: str) -> str:
    """Formatea una lista de cotizaciones como tabla ASCII alineada.

    Tabla ASCII (no JSON) porque el LLM pequeño la resume mejor y el usuario
    final también puede leerla directamente si el agente la reproduce.
    """
    if not rows:
        return "No se pudieron obtener datos de mercado en este momento."
    # Cabecera con anchos fijos que cuadran para tickers de hasta 7 caracteres.
    header = f"Top 10 '{category}':\n{'Ticker':<8}{'Precio':>12}{'Cambio %':>12}"
    lines = [header, "-" * 32]
    for r in rows[:10]:
        lines.append(f"{r['ticker']:<8}{r['price']:>12.2f}{r['change_pct']:>11.2f}%")
    return "\n".join(lines)


@tool
def get_hot_tickers(category: str = "gainers") -> str:
    """Devuelve los 10 tickers más 'calientes' del mercado en una categoría.
    Parámetro category: 'gainers' (mayor subida %), 'losers' (mayor caída %)
    o 'actives' (mayor volumen). Útil para preguntas sobre el estado general del mercado."""
    # Normalización del argumento + validación del conjunto permitido.
    cat = (category or "gainers").strip().lower()
    if cat not in {"gainers", "losers", "actives"}:
        return "Categoría no válida. Usa 'gainers', 'losers' o 'actives'."

    try:
        # Primer intento: Screener oficial de yfinance (más rápido y fiable).
        # El import va dentro del try porque el módulo Screener puede no
        # existir en versiones antiguas de yfinance; si no está, saltamos al
        # fallback sin romper la tool.
        try:
            from yfinance import Screener  # type: ignore
            # Mapeo entre nuestras categorías y los keys internos de Yahoo.
            screener_key = {
                "gainers": "day_gainers",
                "losers": "day_losers",
                "actives": "most_actives",
            }[cat]
            s = Screener()
            resp = s.get_screener(screener_key, count=10)
            # La estructura de resp ha cambiado entre versiones: a veces
            # {screener_key: {"quotes": [...]}} y a veces directamente {"quotes": [...]}.
            quotes = []
            if isinstance(resp, dict):
                body = resp.get(screener_key) or resp
                quotes = body.get("quotes") if isinstance(body, dict) else []
            # Construimos filas homogéneas con lo que necesitamos para imprimir.
            rows = []
            for q in quotes or []:
                price = q.get("regularMarketPrice")
                change = q.get("regularMarketChangePercent")
                if price is None or change is None:
                    continue
                rows.append({
                    "ticker": q.get("symbol", "?"),
                    "price": float(price),
                    "change_pct": float(change),
                    "volume": int(q.get("regularMarketVolume") or 0),
                })
            # Si el Screener ha dado algo utilizable, devolvemos ya y evitamos el fallback lento.
            if rows:
                return _format_table(rows, cat)
        except Exception:
            # Cualquier fallo del Screener nos manda al fallback sin ruido.
            pass

        # Fallback: pedimos cotizaciones al universo hardcodeado y ordenamos
        # localmente según la categoría solicitada (mayor %, menor %, mayor vol).
        rows = _fetch_fallback_quotes()
        if cat == "gainers":
            rows.sort(key=lambda r: r["change_pct"], reverse=True)
        elif cat == "losers":
            rows.sort(key=lambda r: r["change_pct"])
        else:
            rows.sort(key=lambda r: r["volume"], reverse=True)
        return _format_table(rows, cat)
    except Exception as e:
        return f"Error obteniendo tickers calientes: {e}"
