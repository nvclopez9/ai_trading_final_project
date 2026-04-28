"""Portfolio API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services import portfolio as pf_svc
from src.services import portfolios as pfs_svc

router = APIRouter(prefix="/api/portfolios", tags=["portfolio"])


class CreatePortfolioBody(BaseModel):
    name: str
    initial_cash: float = 10000.0
    risk: str = "moderado"
    markets: str = "USA"
    currency: str = "USD"
    notes: str | None = None


class TradeBody(BaseModel):
    ticker: str
    qty: float
    price: float | None = None


@router.get("")
def list_portfolios():
    return pfs_svc.list_portfolios()


@router.post("")
def create_portfolio(body: CreatePortfolioBody):
    try:
        return pfs_svc.create_portfolio(
            name=body.name,
            initial_cash=body.initial_cash,
            risk=body.risk,
            markets=body.markets,
            currency=body.currency,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: int):
    try:
        pfs_svc.delete_portfolio(portfolio_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/reset")
def reset_portfolio(portfolio_id: int):
    try:
        pfs_svc.reset_portfolio(portfolio_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: int):
    p = pfs_svc.get_portfolio(portfolio_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Cartera no encontrada")
    return p


@router.get("/{portfolio_id}/value")
def get_portfolio_value(portfolio_id: int):
    try:
        return pf_svc.get_portfolio_value(portfolio_id=portfolio_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}/positions")
def get_positions(portfolio_id: int):
    return pf_svc.get_positions(portfolio_id=portfolio_id)


@router.get("/{portfolio_id}/transactions")
def get_transactions(portfolio_id: int, limit: int = 50):
    return pf_svc.get_transactions(limit=limit, portfolio_id=portfolio_id)


@router.get("/{portfolio_id}/cash")
def get_cash(portfolio_id: int):
    return {"cash": pfs_svc.cash_available(portfolio_id)}


@router.post("/{portfolio_id}/buy")
def buy(portfolio_id: int, body: TradeBody):
    try:
        return pf_svc.buy(body.ticker, body.qty, body.price, portfolio_id=portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/sell")
def sell(portfolio_id: int, body: TradeBody):
    try:
        return pf_svc.sell(body.ticker, body.qty, body.price, portfolio_id=portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
