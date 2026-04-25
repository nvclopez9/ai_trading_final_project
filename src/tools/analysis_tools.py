"""Tools de análisis: comparador y fundamentales.

Dos tools nuevas que el agente puede invocar para análisis cualitativo:
- ``compare_tickers``: compara N tickers (2-6) lado-a-lado en una tabla
  ASCII con métricas clave (precio, P/E, market cap, dividendo, beta...).
- ``get_fundamentals``: ratios fundamentales completos de un ticker
  (valoración, rentabilidad, solidez, mercado).

Ambas devuelven ``str`` para mantener el patrón del resto del proyecto y
maximizar la fiabilidad del tool-calling con modelos pequeños.
"""
from __future__ import annotations

import yfinance as yf
from langchain_core.tools import tool


# Helpers de formato (privados al módulo).

def _safe_float(x) -> float | None:
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _fmt_money(x: float | None) -> str:
    if x is None:
        return "n/d"
    return f"${x:,.2f}"


def _fmt_pct(x: float | None, *, scale: float = 1.0) -> str:
    """Formatea un valor numérico como %. Si scale=100 multiplica por 100
    (yfinance entrega yields como 0.0123 en algunos campos y como 1.23 en otros)."""
    if x is None:
        return "n/d"
    return f"{x * scale:+.2f}%" if scale != 1.0 else f"{x:+.2f}%"


def _fmt_market_cap(x: float | None) -> str:
    if x is None:
        return "n/d"
    if x >= 1e12:
        return f"${x/1e12:.2f}T"
    if x >= 1e9:
        return f"${x/1e9:.2f}B"
    if x >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:,.0f}"


def _fmt_num(x: float | None, decimals: int = 2) -> str:
    if x is None:
        return "n/d"
    return f"{x:.{decimals}f}"


def _ytd_return(symbol: str) -> float | None:
    """Aproximación del retorno YTD usando yfinance.history(period='ytd')."""
    try:
        hist = yf.Ticker(symbol).history(period="ytd")
        if hist.empty or len(hist) < 2:
            return None
        first = float(hist["Close"].iloc[0])
        last = float(hist["Close"].iloc[-1])
        if first == 0:
            return None
        return (last - first) / first * 100
    except Exception:
        return None


def _collect_compare_row(symbol: str) -> dict:
    """Construye un dict con las métricas mínimas para la fila comparativa."""
    sym = symbol.strip().upper()
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        price = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
        prev = _safe_float(info.get("regularMarketPreviousClose") or info.get("previousClose"))
        change = ((price - prev) / prev * 100) if (price and prev) else None
        return {
            "ticker": sym,
            "name": info.get("longName") or info.get("shortName") or sym,
            "price": price,
            "change_pct": change,
            "pe": _safe_float(info.get("trailingPE")),
            "mcap": _safe_float(info.get("marketCap")),
            "div_yield": _safe_float(info.get("dividendYield")),
            "high52": _safe_float(info.get("fiftyTwoWeekHigh")),
            "low52": _safe_float(info.get("fiftyTwoWeekLow")),
            "beta": _safe_float(info.get("beta")),
            "ytd": _ytd_return(sym),
            "error": None,
        }
    except Exception as e:
        return {"ticker": sym, "error": str(e)}


def _format_compare_table(rows: list[dict]) -> str:
    """Tabla ASCII alineada para que el LLM no la deforme y el usuario la lea
    bien si el agente la reproduce literal."""
    if not rows:
        return "Sin datos para comparar."
    # Encabezado.
    header = (
        f"{'Ticker':<8}{'Precio':>12}{'Δ día':>10}{'P/E':>8}"
        f"{'MCap':>10}{'Div%':>8}{'52W High':>12}{'52W Low':>12}"
        f"{'Beta':>7}{'YTD%':>9}"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        if r.get("error"):
            lines.append(f"{r['ticker']:<8}  Error: {r['error'][:60]}")
            continue
        # yfinance entrega dividendYield ya en porcentaje (1.23 = 1.23%).
        # Algunos campos pueden venir como fraccional (0.0123); lo manejamos
        # heurísticamente: si <1, asumimos fracción y x100.
        dy = r.get("div_yield")
        if dy is not None and dy < 1:
            dy = dy * 100
        lines.append(
            f"{r['ticker']:<8}"
            f"{_fmt_money(r.get('price')):>12}"
            f"{(_fmt_num(r.get('change_pct'))+ '%') if r.get('change_pct') is not None else 'n/d':>10}"
            f"{_fmt_num(r.get('pe')):>8}"
            f"{_fmt_market_cap(r.get('mcap')):>10}"
            f"{(_fmt_num(dy)+ '%') if dy is not None else 'n/d':>8}"
            f"{_fmt_money(r.get('high52')):>12}"
            f"{_fmt_money(r.get('low52')):>12}"
            f"{_fmt_num(r.get('beta')):>7}"
            f"{(_fmt_num(r.get('ytd'))+ '%') if r.get('ytd') is not None else 'n/d':>9}"
        )
    return "\n".join(lines)


@tool
def compare_tickers(tickers: list[str]) -> str:
    """Compara entre 2 y 6 tickers lado-a-lado. Devuelve una tabla con
    nombre, precio actual, cambio diario, P/E, market cap, dividend yield,
    52-week high/low, beta y retorno YTD aproximado.

    Útil cuando el usuario pide 'compara X vs Y', 'cuál es mejor entre X y Z',
    'AAPL vs MSFT vs GOOGL', etc.

    Ejemplo de input: ['AAPL', 'MSFT', 'NVDA']."""
    try:
        if not tickers or not isinstance(tickers, list):
            return "❌ Debes pasar una lista de tickers (2-6 elementos)."
        cleaned = [str(t).strip().upper() for t in tickers if str(t).strip()]
        if len(cleaned) < 2:
            return "❌ Necesito al menos 2 tickers para comparar."
        if len(cleaned) > 6:
            return f"❌ Demasiados tickers ({len(cleaned)}). Máximo 6 a la vez."
        rows = [_collect_compare_row(t) for t in cleaned]
        ok_rows = [r for r in rows if not r.get("error")]
        if not ok_rows:
            return f"❌ No se pudieron obtener datos para ninguno: {cleaned}"
        out = [f"📊 COMPARATIVA — {', '.join(cleaned)}", ""]
        out.append(_format_compare_table(rows))
        out.append("")
        out.append(
            "Nota: cifras vivas de Yahoo Finance; pueden variar entre llamadas. "
            "P/E negativo o n/d implica empresa en pérdidas o sin earnings reportados. "
            "Beta >1 = más volátil que el mercado, <1 = menos volátil."
        )
        return "\n".join(out)
    except Exception as e:
        return f"❌ Error en compare_tickers: {e}"


@tool
def get_fundamentals(ticker: str) -> str:
    """Devuelve los ratios fundamentales clave de un ticker, agrupados por
    bloque temático: Valoración (P/E, P/B, P/S, P/FCF), Rentabilidad (ROE,
    ROA, márgenes, dividendo, payout), Solidez (debt/equity, current ratio,
    free cash flow), Mercado (market cap, beta, 52w high/low, EPS).

    Útil para análisis a largo plazo, comparativa value vs growth, o cuando
    el usuario pregunta '¿cómo de sano es financieramente X?', 'fundamentales
    de X', 'ratios de Y', etc."""
    try:
        sym = ticker.strip().upper()
        info = yf.Ticker(sym).info or {}
        if not info or info.get("regularMarketPrice") is None:
            return f"❌ Sin datos fundamentales para '{sym}'. Verifica el símbolo."

        name = info.get("longName") or info.get("shortName") or sym
        # Yields/margins en yfinance: heurística — si <1 es fracción, x100.
        def _maybe_pct(x):
            v = _safe_float(x)
            if v is None:
                return None
            return v * 100 if abs(v) < 1 else v

        # Bloque 1: Valoración
        pe = _safe_float(info.get("trailingPE"))
        fpe = _safe_float(info.get("forwardPE"))
        pb = _safe_float(info.get("priceToBook"))
        ps = _safe_float(info.get("priceToSalesTrailing12Months"))
        peg = _safe_float(info.get("pegRatio"))
        # Bloque 2: Rentabilidad
        roe = _maybe_pct(info.get("returnOnEquity"))
        roa = _maybe_pct(info.get("returnOnAssets"))
        pmargin = _maybe_pct(info.get("profitMargins"))
        omargin = _maybe_pct(info.get("operatingMargins"))
        gmargin = _maybe_pct(info.get("grossMargins"))
        dy = _maybe_pct(info.get("dividendYield"))
        payout = _maybe_pct(info.get("payoutRatio"))
        # Bloque 3: Solidez
        de = _safe_float(info.get("debtToEquity"))  # ya en formato 0-200
        cr = _safe_float(info.get("currentRatio"))
        qr = _safe_float(info.get("quickRatio"))
        fcf = _safe_float(info.get("freeCashflow"))
        # Bloque 4: Mercado
        mcap = _safe_float(info.get("marketCap"))
        beta = _safe_float(info.get("beta"))
        h52 = _safe_float(info.get("fiftyTwoWeekHigh"))
        l52 = _safe_float(info.get("fiftyTwoWeekLow"))
        eps = _safe_float(info.get("trailingEps"))
        sector = info.get("sector") or "n/d"
        industry = info.get("industry") or "n/d"

        lines = [
            f"📑 FUNDAMENTALES — {sym} ({name})",
            f"Sector: {sector} · Industria: {industry}",
            "",
            "Valoración:",
            f"  P/E (TTM): {_fmt_num(pe)}    Forward P/E: {_fmt_num(fpe)}    PEG: {_fmt_num(peg)}",
            f"  P/B: {_fmt_num(pb)}    P/S (TTM): {_fmt_num(ps)}",
            "",
            "Rentabilidad:",
            f"  ROE: {(_fmt_num(roe)+'%') if roe is not None else 'n/d'}    "
            f"ROA: {(_fmt_num(roa)+'%') if roa is not None else 'n/d'}",
            f"  Margen bruto: {(_fmt_num(gmargin)+'%') if gmargin is not None else 'n/d'}    "
            f"Margen operativo: {(_fmt_num(omargin)+'%') if omargin is not None else 'n/d'}    "
            f"Margen neto: {(_fmt_num(pmargin)+'%') if pmargin is not None else 'n/d'}",
            f"  Dividend yield: {(_fmt_num(dy)+'%') if dy is not None else 'n/d'}    "
            f"Payout ratio: {(_fmt_num(payout)+'%') if payout is not None else 'n/d'}",
            "",
            "Solidez:",
            f"  Debt/Equity: {_fmt_num(de)}    Current ratio: {_fmt_num(cr)}    Quick ratio: {_fmt_num(qr)}",
            f"  Free cash flow: {_fmt_market_cap(fcf)}",
            "",
            "Mercado:",
            f"  Market cap: {_fmt_market_cap(mcap)}    Beta: {_fmt_num(beta)}    EPS (TTM): {_fmt_num(eps)}",
            f"  Rango 52 sem: {_fmt_money(l52)} – {_fmt_money(h52)}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error en get_fundamentals para '{ticker}': {e}"
