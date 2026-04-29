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

from src.utils.logger import get_logger, timed

log = get_logger("tools.market")

# Universos curados (acciones por tier + ETFs + commodities + crypto). Vivimos
# en un único módulo `universes.py` para que advisor_tool y otras partes de
# la app compartan las mismas listas y la mantenibilidad sea sencilla.
from src.tools.universes import (
    LARGE_CAP,
    MID_CAP,
    ETFS,
    ETPS_COMMODITIES,
    ETPS_CRYPTO,
)


# Universo de fallback: combinación de large+mid caps + ETFs + commodities +
# crypto-ETPs. Se usa cuando el Screener oficial de yfinance falla
# (estructura cambia, rate-limit, etc.). Es lo bastante variado para que
# "gainers/losers/actives" den resultados representativos en distintos
# segmentos del mercado.
FALLBACK_UNIVERSE = (
    LARGE_CAP + MID_CAP + ETFS + ETPS_COMMODITIES + ETPS_CRYPTO
)


@tool
def get_ticker_status(ticker: str) -> str:
    """Obtiene el estado actual de un ticker bursátil: precio, cambio porcentual,
    P/E ratio, capitalización de mercado y nombre de la empresa.
    Parámetro: ticker (símbolo, por ejemplo 'AAPL', 'MSFT', 'TSLA')."""
    log.debug(f"get_ticker_status called: {ticker}")
    try:
        # Normalizamos el símbolo: yfinance espera mayúsculas y sin espacios.
        # El agente a veces llega con "aapl" o " MSFT " según cómo parsee el LLM.
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        # .info hace scraping y puede devolver None o dict parcial sin lanzar
        # excepción. El ``or {}`` nos da un dict vacío para poder hacer .get
        # sin preocuparnos.
        with timed(log, f"yfinance.Ticker({symbol}).info"):
            info = t.info or {}
        # Doble alias: Yahoo a veces expone un campo y a veces el otro.
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

        # Fallback si .info no trajo precio: pedimos los últimos 5 días de
        # historial y usamos el último cierre. Si el histórico también está
        # vacío, el ticker casi seguro no existe.
        if price is None:
            with timed(log, f"yfinance.Ticker({symbol}).history(5d) [fallback]"):
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

        log.debug(f"result: {symbol} price={price_str} change={change_str}")
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
        log.warning(f"tool error get_ticker_status({ticker}): {e}")
        # Nunca propagamos excepciones al agente: devolvemos string controlado
        # para que el LLM pueda reaccionar (p.ej. sugerir verificar el símbolo).
        return f"Error consultando el ticker '{ticker}': {e}"


@tool
def get_ticker_history(ticker: str, period: str = "1mo") -> str:
    """Devuelve un resumen textual del histórico de precios de un ticker.
    Parámetros: ticker (símbolo), period (ej: '5d', '1mo', '3mo', '6mo', '1y', '5y').
    Incluye precio máximo, mínimo, último cierre y variación del periodo."""
    log.debug(f"get_ticker_history called: {ticker} period={period}")
    try:
        # Misma normalización que en get_ticker_status.
        symbol = ticker.strip().upper()
        t = yf.Ticker(symbol)
        # history() devuelve un DataFrame pandas con columnas Open/High/Low/Close/Volume.
        with timed(log, f"yfinance.Ticker({symbol}).history({period})"):
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
        log.debug(f"result: {symbol} last={last:.2f} change={change}%")
        return (
            f"Histórico de {symbol} ({period}): "
            f"máximo {high:.2f}, mínimo {low:.2f}, último cierre {last:.2f}, "
            f"variación del periodo {change}%."
        )
    except Exception as e:
        log.warning(f"tool error get_ticker_history({ticker}): {e}")
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
    log.debug(f"get_hot_tickers called: category={cat}")
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
            with timed(log, f"yfinance.Screener.get_screener({screener_key})"):
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
                log.debug(f"result: screener returned {len(rows)} rows for {cat}")
                return _format_table(rows, cat)
        except Exception as exc:
            log.warning(f"yfinance Screener failed, using fallback universe: {exc}")
            # Cualquier fallo del Screener nos manda al fallback sin ruido.
            pass

        # Fallback: pedimos cotizaciones al universo hardcodeado y ordenamos
        # localmente según la categoría solicitada (mayor %, menor %, mayor vol).
        log.debug("get_hot_tickers: fetching fallback universe quotes")
        with timed(log, "yfinance fallback universe scan"):
            rows = _fetch_fallback_quotes()
        if cat == "gainers":
            rows.sort(key=lambda r: r["change_pct"], reverse=True)
        elif cat == "losers":
            rows.sort(key=lambda r: r["change_pct"])
        else:
            rows.sort(key=lambda r: r["volume"], reverse=True)
        log.debug(f"result: fallback returned {len(rows)} rows for {cat}")
        return _format_table(rows, cat)
    except Exception as e:
        log.warning(f"tool error get_hot_tickers({category}): {e}")
        return f"Error obteniendo tickers calientes: {e}"


def _extract_news_item(item: dict) -> dict | None:
    """Normaliza un item de ``yf.Ticker(t).news`` a {title, date, source, link}.

    yfinance ha ido cambiando el esquema entre versiones. Intentamos primero
    la estructura plana legacy (``title``, ``providerPublishTime``, etc.) y
    caemos a la anidada moderna (``content.title``, ``content.pubDate``...).
    Si no hay título reconocible devolvemos None — el caller lo filtra.
    """
    import datetime as _dt
    title = item.get("title")
    link = item.get("link")
    source = item.get("publisher")
    ts = item.get("providerPublishTime")
    date_str = None
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            date_str = _dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except Exception:
            date_str = None

    # Thumbnail (legacy): item["thumbnail"]["resolutions"] -> [{url, width, ...}]
    thumbnail_url = None
    thumb = item.get("thumbnail") or {}
    resolutions = thumb.get("resolutions") if isinstance(thumb, dict) else None
    if isinstance(resolutions, list) and resolutions:
        # Preferimos resolución intermedia (~140px) si existe; si no, la primera.
        chosen = None
        for r in resolutions:
            if not isinstance(r, dict):
                continue
            w = r.get("width") or 0
            if 100 <= w <= 240:
                chosen = r
                break
        chosen = chosen or next((r for r in resolutions if isinstance(r, dict)), None)
        if chosen and chosen.get("url"):
            thumbnail_url = chosen.get("url")

    # Esquema moderno: {"content": {...}}
    if not title:
        content = item.get("content") or {}
        title = content.get("title")
        link = link or (content.get("canonicalUrl") or {}).get("url") or (content.get("clickThroughUrl") or {}).get("url")
        provider = content.get("provider") or {}
        source = source or provider.get("displayName")
        pub = content.get("pubDate") or content.get("displayTime")
        if pub and not date_str:
            date_str = str(pub)[:10]
        # Thumbnail moderno: content.thumbnail.resolutions o content.thumbnail.originalUrl
        if not thumbnail_url:
            cthumb = content.get("thumbnail") or {}
            cres = cthumb.get("resolutions") if isinstance(cthumb, dict) else None
            if isinstance(cres, list):
                chosen = None
                for r in cres:
                    if not isinstance(r, dict):
                        continue
                    w = r.get("width") or 0
                    if 100 <= w <= 240:
                        chosen = r
                        break
                chosen = chosen or next((r for r in cres if isinstance(r, dict)), None)
                if chosen and chosen.get("url"):
                    thumbnail_url = chosen.get("url")
            if not thumbnail_url and isinstance(cthumb, dict):
                thumbnail_url = cthumb.get("originalUrl") or cthumb.get("url")

    if not title:
        return None
    return {
        "title": title.strip(),
        "date": date_str or "s/f",
        "source": source or "desconocido",
        "link": link or "",
        "thumbnail": thumbnail_url,
    }


def fetch_ticker_news(ticker: str, limit: int = 5) -> list[dict]:
    """Helper reutilizable (no @tool): lista de noticias ya normalizadas.

    Usada tanto por la tool ``get_ticker_news`` como por el panel de la UI,
    para evitar duplicar la lógica de normalización del esquema de yfinance.
    Silencia errores devolviendo lista vacía; el caller decide cómo avisar.
    """
    try:
        symbol = ticker.strip().upper()
        with timed(log, f"yfinance.Ticker({symbol}).news"):
            raw = yf.Ticker(symbol).news or []
    except Exception:
        return []
    items = []
    for it in raw:
        norm = _extract_news_item(it)
        if norm:
            items.append(norm)
        if len(items) >= max(1, min(limit, 10)):
            break
    return items


@tool
def get_ticker_news(ticker: str, limit: int = 5) -> str:
    """Devuelve las últimas noticias relevantes de un ticker (titular, fecha, fuente, enlace).
    Parámetros: ticker (símbolo, p. ej. 'AAPL'), limit (máximo de noticias, 1-10, default 5).
    Fuente: Yahoo Finance (sin API key). Usa esta tool cuando el usuario pregunte por noticias,
    titulares o novedades de una empresa."""
    log.debug(f"get_ticker_news called: {ticker} limit={limit}")
    try:
        items = fetch_ticker_news(ticker, limit)
    except Exception as e:
        log.warning(f"tool error get_ticker_news({ticker}): {e}")
        return f"No pude obtener noticias para {ticker.upper()} ahora mismo: {e}"
    log.debug(f"result: {ticker.strip().upper()} returned {len(items)} news items")
    if not items:
        return f"No se encontraron noticias recientes para {ticker.strip().upper()}."
    lines = [f"📰 Noticias recientes para {ticker.strip().upper()} ({len(items)}):", ""]
    for i, n in enumerate(items, start=1):
        lines.append(f"{i}. [{n['date']}] {n['title']} — {n['source']}")
        if n["link"]:
            lines.append(f"   {n['link']}")
    return "\n".join(lines)


# ── Real-time ticker search ─────────────────────────────────────────────────

def _yahoo_search_raw(query: str, limit: int = 8) -> list[dict]:
    """Llama a Yahoo Finance search API y devuelve la lista cruda de quotes."""
    import urllib.request
    import urllib.parse
    import json as _json

    url = (
        "https://query1.finance.yahoo.com/v1/finance/search"
        f"?q={urllib.parse.quote(query.strip())}"
        f"&quotesCount={limit}&newsCount=0&lang=en&enableNavLinks=false"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })
    with urllib.request.urlopen(req, timeout=6) as resp:
        return _json.loads(resp.read().decode()).get("quotes", []) or []


@tool
def search_ticker(query: str) -> str:
    """Busca tickers bursátiles por nombre de empresa o símbolo parcial en tiempo real.
    Úsala cuando no sepas el símbolo exacto de una empresa o quieras buscar por nombre.
    Parámetro: query — nombre de empresa o símbolo aproximado (ej: 'Apple', 'banco santander', 'tesla', 'SAP')."""
    log.debug(f"search_ticker called: {query!r}")
    try:
        with timed(log, f"yahoo_search({query!r})"):
            quotes = _yahoo_search_raw(query, limit=8)
        if not quotes:
            return f"No se encontraron tickers para '{query}'."
        lines = [f"Resultados de búsqueda para '{query}':"]
        for item in quotes:
            sym = item.get("symbol", "")
            if not sym:
                continue
            name = item.get("longname") or item.get("shortname") or sym
            exchange = item.get("exchDisp") or item.get("exchange") or ""
            qt = item.get("typeDisp") or item.get("quoteType") or ""
            lines.append(f"  • {sym} — {name} [{exchange}] ({qt})")
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"search_ticker error for {query!r}: {e}")
        return f"Error al buscar tickers para '{query}': {e}"


@tool
def analyze_news_article(ticker: str, title: str, source: str = "", url: str = "") -> str:
    """Obtiene el contexto de mercado completo para analizar una noticia financiera.
    Devuelve: precio actual, variación diaria, tendencia de 3 meses, market cap y P/E
    del ticker relacionado, listos para que el agente redacte el análisis de impacto.
    Parámetros:
    - ticker: símbolo bursátil relacionado con la noticia (ej: 'AAPL', 'TSLA')
    - title: titular exacto de la noticia
    - source: fuente periodística (ej: 'Reuters', 'Bloomberg')
    - url: enlace a la noticia (opcional, se incluye en el resumen)."""
    sym = ticker.strip().upper()
    log.debug(f"analyze_news_article called: ticker={sym!r} title={title[:60]!r}")
    try:
        t = yf.Ticker(sym)
        with timed(log, f"analyze_news.info({sym})"):
            info = t.info or {}

        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        name = info.get("longName") or info.get("shortName") or sym
        sector = info.get("sector") or "N/D"
        pe = info.get("trailingPE")
        mc = info.get("marketCap")

        mc_str = "N/D"
        if mc:
            mc_str = f"${mc/1e12:.1f}T" if mc >= 1e12 else f"${mc/1e9:.1f}B"

        change_str = "N/D"
        if price and prev and float(prev) != 0:
            chg = (float(price) - float(prev)) / float(prev) * 100
            change_str = f"{chg:+.2f}%"

        with timed(log, f"analyze_news.history({sym}, 3mo)"):
            hist = t.history(period="3mo")

        trend_str = "N/D"
        if not hist.empty and len(hist) >= 2:
            h_start = float(hist["Close"].iloc[0])
            h_end = float(hist["Close"].iloc[-1])
            if h_start != 0:
                h_pct = (h_end - h_start) / h_start * 100
                h_high = float(hist["High"].max())
                h_low = float(hist["Low"].min())
                trend_str = f"{h_pct:+.1f}% (máx ${h_high:.2f} / mín ${h_low:.2f})"

        lines = [
            f"NOTICIA: {title}",
            f"Fuente: {source or 'N/D'}",
        ]
        if url:
            lines.append(f"URL: {url}")
        lines += [
            "",
            f"CONTEXTO DE MERCADO — {sym} ({name})",
            f"Sector: {sector}",
            f"Precio actual: ${float(price):.2f}" if price else "Precio: N/D",
            f"Variación hoy: {change_str}",
            f"Market Cap: {mc_str}",
            f"P/E ratio: {f'{pe:.2f}' if isinstance(pe, (int, float)) else 'N/D'}",
            f"Tendencia 3 meses: {trend_str}",
        ]
        return "\n".join(lines)

    except Exception as e:
        log.warning(f"analyze_news_article error for {sym!r}: {e}")
        return (
            f"NOTICIA: {title}\n"
            f"Fuente: {source or 'N/D'}\n"
            f"URL: {url}\n\n"
            f"No se pudieron obtener datos de mercado para {sym}: {e}\n"
            "Analiza la noticia basándote en el titular y lo que sepas del ticker."
        )
