"""Watchlist API routes."""
from fastapi import APIRouter
from pydantic import BaseModel

from backend.services import watchlist as wl_svc

router = APIRouter(prefix="/api/portfolios", tags=["watchlist"])


class WatchBody(BaseModel):
    ticker: str
    note: str | None = None


@router.get("/{portfolio_id}/watchlist")
def list_watchlist(portfolio_id: int):
    return wl_svc.list_for(portfolio_id)


@router.post("/{portfolio_id}/watchlist")
def add_to_watchlist(portfolio_id: int, body: WatchBody):
    try:
        wl_svc.add(portfolio_id, body.ticker, body.note)
        return {"ok": True}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{portfolio_id}/watchlist/{ticker}")
def remove_from_watchlist(portfolio_id: int, ticker: str):
    wl_svc.remove(portfolio_id, ticker)
    return {"ok": True}
