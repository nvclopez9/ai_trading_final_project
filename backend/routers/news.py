"""News API routes."""
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/news", tags=["news"])

PORTAL_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL"]


def _grab_news(ticker: str, limit: int = 4) -> list[dict]:
    try:
        from src.tools.market_tools import fetch_ticker_news
        items = fetch_ticker_news(ticker, limit=limit) or []
        for it in items:
            it["_origin"] = ticker
        return items
    except Exception:
        return []


@router.get("/portal")
def portal_news(per_ticker: int = 4):
    aggregated: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for batch in ex.map(lambda t: _grab_news(t, per_ticker), PORTAL_TICKERS):
            aggregated.extend(batch)

    seen = set()
    unique = []
    for it in aggregated:
        key = (it.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)

    unique.sort(key=lambda x: x.get("date") or "", reverse=True)
    return unique[:30]


@router.get("/ticker/{symbol}")
def ticker_news(symbol: str, limit: int = 10):
    symbol = symbol.strip().upper()
    try:
        from src.tools.market_tools import fetch_ticker_news
        items = fetch_ticker_news(symbol, limit=limit) or []
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
