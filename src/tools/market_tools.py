import yfinance as yf
from langchain_core.tools import tool


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
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

        if price is None:
            hist = t.history(period="5d")
            if hist.empty:
                return f"No se encontraron datos para el ticker '{symbol}'. Verifica que sea válido."
            price = float(hist["Close"].iloc[-1])
            if prev_close is None and len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])

        change_pct = None
        if price is not None and prev_close:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        name = info.get("longName") or info.get("shortName") or symbol
        currency = info.get("currency", "USD")
        pe = info.get("trailingPE")
        mcap = info.get("marketCap")

        price_str = f"{float(price):.2f} {currency}" if price is not None else "n/d"
        change_str = f"{change_pct:+.2f}%" if change_pct is not None else "n/d"
        pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else "n/d"
        mcap_str = f"{mcap:,}" if isinstance(mcap, (int, float)) else "n/d"

        return (
            f"Ticker: {symbol} ({name})\n"
            f"Precio actual: {price_str}\n"
            f"Cambio diario: {change_str}\n"
            f"P/E ratio: {pe_str}\n"
            f"Capitalización de mercado: {mcap_str}"
        )
    except Exception as e:
        return f"Error consultando el ticker '{ticker}': {e}"


@tool
def get_ticker_history(ticker: str, period: str = "1mo") -> str:
    """Devuelve un resumen textual del histórico de precios de un ticker.
    Parámetros: ticker (símbolo), period (ej: '5d', '1mo', '3mo', '6mo', '1y', '5y').
    Incluye precio máximo, mínimo, último cierre y variación del periodo."""
    try:
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty:
            return f"No hay histórico disponible para '{symbol}' en el periodo '{period}'."
        high = float(hist["High"].max())
        low = float(hist["Low"].min())
        first = float(hist["Close"].iloc[0])
        last = float(hist["Close"].iloc[-1])
        change = round((last - first) / first * 100, 2) if first else 0.0
        return (
            f"Histórico de {symbol} ({period}): "
            f"máximo {high:.2f}, mínimo {low:.2f}, último cierre {last:.2f}, "
            f"variación del periodo {change}%."
        )
    except Exception as e:
        return f"Error obteniendo histórico de '{ticker}': {e}"


def _fetch_fallback_quotes():
    rows = []
    for sym in FALLBACK_UNIVERSE:
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
            if price is None or prev is None:
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
            change_pct = (float(price) - float(prev)) / float(prev) * 100 if prev else 0.0
            volume = info.get("regularMarketVolume") or info.get("volume") or 0
            rows.append({
                "ticker": sym,
                "price": float(price),
                "change_pct": float(change_pct),
                "volume": int(volume) if volume else 0,
            })
        except Exception:
            continue
    return rows


def _format_table(rows, category: str) -> str:
    if not rows:
        return "No se pudieron obtener datos de mercado en este momento."
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
    cat = (category or "gainers").strip().lower()
    if cat not in {"gainers", "losers", "actives"}:
        return "Categoría no válida. Usa 'gainers', 'losers' o 'actives'."

    try:
        try:
            from yfinance import Screener  # type: ignore
            screener_key = {
                "gainers": "day_gainers",
                "losers": "day_losers",
                "actives": "most_actives",
            }[cat]
            s = Screener()
            resp = s.get_screener(screener_key, count=10)
            quotes = []
            if isinstance(resp, dict):
                body = resp.get(screener_key) or resp
                quotes = body.get("quotes") if isinstance(body, dict) else []
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
            if rows:
                return _format_table(rows, cat)
        except Exception:
            pass

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
