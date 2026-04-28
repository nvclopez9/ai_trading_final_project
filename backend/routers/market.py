"""Market data API routes."""
import json
from fastapi import APIRouter, HTTPException, Query

import yfinance as yf

router = APIRouter(prefix="/api/market", tags=["market"])


def _info_safe(symbol: str) -> dict:
    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


@router.get("/ticker/{symbol}")
def ticker_status(symbol: str):
    symbol = symbol.strip().upper()
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if price is None:
            hist = t.history(period="5d")
            if hist.empty:
                raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' no encontrado")
            price = float(hist["Close"].iloc[-1])
            if prev_close is None and len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])

        change_pct = None
        if price is not None and prev_close:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        mc = info.get("marketCap")
        mc_str = None
        if mc:
            if mc >= 1e12:
                mc_str = f"{mc/1e12:.2f}T"
            elif mc >= 1e9:
                mc_str = f"{mc/1e9:.2f}B"
            else:
                mc_str = f"{mc/1e6:.0f}M"

        # After-hours
        ah_price = info.get("postMarketPrice") or info.get("preMarketPrice")
        ah_pct = info.get("postMarketChangePercent") or info.get("preMarketChangePercent")
        if ah_price and ah_pct is None and price:
            ah_pct = (float(ah_price) - float(price)) / float(price) * 100

        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "price": round(float(price), 2) if price else None,
            "prev_close": round(float(prev_close), 2) if prev_close else None,
            "change_pct": change_pct,
            "pe_ratio": round(info.get("trailingPE"), 2) if info.get("trailingPE") else None,
            "market_cap": mc,
            "market_cap_str": mc_str,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "volume": info.get("regularMarketVolume") or info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "currency": info.get("currency", "USD"),
            "after_hours_price": float(ah_price) if ah_price else None,
            "after_hours_change_pct": round(float(ah_pct), 2) if ah_pct else None,
            "logo_url": info.get("logo_url"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}/history")
def ticker_history(symbol: str, period: str = "6mo", interval: str = "1d"):
    symbol = symbol.strip().upper()
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period, interval=interval)
        if hist.empty:
            # fallback to shorter period
            hist = t.history(period="1mo", interval=interval)
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No hay historial para '{symbol}'")
        data = []
        for ts, row in hist.iterrows():
            data.append({
                "date": ts.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]) if row["Volume"] else 0,
            })
        return {"symbol": symbol, "period": period, "interval": interval, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}/news")
def ticker_news(symbol: str, limit: int = 10):
    symbol = symbol.strip().upper()
    try:
        from src.tools.market_tools import fetch_ticker_news
        items = fetch_ticker_news(symbol, limit=limit) or []
        return {"symbol": symbol, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}/logo")
def ticker_logo(symbol: str):
    symbol = symbol.strip().upper()
    try:
        from src.ui.logos import get_logo_url
        url = get_logo_url(symbol)
        return {"symbol": symbol, "url": url}
    except Exception:
        return {"symbol": symbol, "url": None}


@router.get("/hot")
def hot_tickers():
    try:
        from src.tools.market_tools import _fetch_fallback_quotes
        rows = _fetch_fallback_quotes()
        gainers = sorted(rows, key=lambda r: r.get("change_pct") or 0, reverse=True)[:10]
        losers = sorted(rows, key=lambda r: r.get("change_pct") or 0)[:10]
        actives = sorted(rows, key=lambda r: r.get("volume") or 0, reverse=True)[:10]
        return {"gainers": gainers, "losers": losers, "actives": actives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
def compare_tickers(tickers: str = Query(..., description="Comma-separated tickers")):
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers")
    results = []
    for sym in symbols[:6]:
        try:
            info = _info_safe(sym)
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
            pct = None
            if price and prev:
                pct = round((float(price) - float(prev)) / float(prev) * 100, 2)
            results.append({
                "symbol": sym,
                "name": info.get("longName") or info.get("shortName") or sym,
                "price": round(float(price), 2) if price else None,
                "change_pct": pct,
                "pe_ratio": round(info.get("trailingPE"), 2) if info.get("trailingPE") else None,
                "market_cap": info.get("marketCap"),
                "sector": info.get("sector"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "beta": info.get("beta"),
            })
        except Exception:
            results.append({"symbol": sym, "error": "No data"})
    return results


@router.get("/fundamentals/{symbol}")
def get_fundamentals(symbol: str):
    symbol = symbol.strip().upper()
    try:
        info = _info_safe(symbol)
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "revenue": info.get("totalRevenue"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "float_shares": info.get("floatShares"),
            "short_ratio": info.get("shortRatio"),
            "analyst_target": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
