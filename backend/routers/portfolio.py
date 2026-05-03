"""Portfolio API routes."""
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import portfolio as pf_svc
from backend.services import portfolios as pfs_svc

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


@router.get("/{portfolio_id}/performance")
def get_performance(portfolio_id: int):
    empty = {"dates": [], "portfolio": [], "spy": [], "qqq": []}
    try:
        # 1. Load all transactions sorted ASC
        all_txs = pf_svc.get_transactions(limit=100_000, portfolio_id=portfolio_id)
        if not all_txs:
            return empty
        # Transactions come back sorted DESC; reverse to get ASC
        all_txs = list(reversed(all_txs))

        # 3. First transaction date
        first_ts = all_txs[0]["ts"]
        first_date = first_ts[:10]  # "YYYY-MM-DD"

        # 4. Unique tickers
        tickers = list({tx["ticker"] for tx in all_txs})

        # 5. Fetch price history
        today_str = date.today().isoformat()
        all_symbols = tickers + ["SPY", "QQQ"]
        raw = yf.download(
            all_symbols,
            start=first_date,
            end=today_str,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        if raw.empty:
            return empty

        # Extract Close prices; handle single-ticker vs multi-ticker download shape
        if isinstance(raw.columns, pd.MultiIndex):
            close_df = raw["Close"]
        else:
            close_df = raw[["Close"]].rename(columns={"Close": all_symbols[0]})

        # Forward-fill missing days (weekends / holidays)
        close_df = close_df.ffill()

        # 6. Portfolio initial cash
        pf = pfs_svc.get_portfolio(portfolio_id)
        if pf is None:
            return empty
        initial_cash: float = float(pf["initial_cash"])

        # Build a lookup: date_str -> {ticker: price}
        trading_days = [d.strftime("%Y-%m-%d") for d in close_df.index]

        # Pre-process transactions into a list of (date_str, side, ticker, qty, price)
        tx_records = [
            (tx["ts"][:10], tx["side"], tx["ticker"], float(tx["qty"]), float(tx["price"]))
            for tx in all_txs
        ]

        # 7. Walk through each trading day and compute portfolio value
        portfolio_values: list[float] = []
        running_cash = initial_cash
        running_shares: dict[str, float] = {t: 0.0 for t in tickers}
        tx_idx = 0
        n_tx = len(tx_records)

        for day_str in trading_days:
            # Apply all transactions up to and including this day
            while tx_idx < n_tx and tx_records[tx_idx][0] <= day_str:
                _, side, ticker, qty, price = tx_records[tx_idx]
                if ticker in running_shares:
                    if side == "BUY":
                        running_shares[ticker] += qty
                        running_cash -= qty * price
                    else:
                        running_shares[ticker] -= qty
                        running_cash += qty * price
                tx_idx += 1

            # Portfolio value = sum(shares * close_price) + cash
            equity = 0.0
            for ticker in tickers:
                if ticker in close_df.columns:
                    price_val = close_df.at[close_df.index[trading_days.index(day_str)], ticker]
                    if pd.notna(price_val):
                        equity += running_shares[ticker] * float(price_val)
            portfolio_values.append(equity + running_cash)

        if not portfolio_values:
            return empty

        # 8. Normalize SPY and QQQ so they start at the same absolute value as the portfolio
        pf_day0 = portfolio_values[0]

        def get_series(symbol: str) -> list[float]:
            if symbol not in close_df.columns:
                return [round(pf_day0, 2)] * len(trading_days)
            col = close_df[symbol].values
            spy_day0 = float(col[0]) if pd.notna(col[0]) else None
            if spy_day0 is None or spy_day0 == 0:
                return [round(pf_day0, 2)] * len(trading_days)
            scale = pf_day0 / spy_day0
            result = []
            for v in col:
                result.append(round(float(v) * scale, 2) if pd.notna(v) else None)
            return result

        spy_values = get_series("SPY")
        qqq_values = get_series("QQQ")
        portfolio_rounded = [round(v, 2) for v in portfolio_values]

        return {
            "dates": trading_days,
            "portfolio": portfolio_rounded,
            "spy": spy_values,
            "qqq": qqq_values,
        }
    except Exception:
        return empty


@router.get("/{portfolio_id}/realized-pnl")
def realized_pnl(portfolio_id: int):
    """Returns realized P&L per ticker using average cost method."""
    all_txs = pf_svc.get_transactions(portfolio_id, limit=5000)
    if not all_txs:
        return []

    # Process transactions in chronological order (get_transactions returns DESC)
    txs = list(reversed(all_txs))

    pnl_by_ticker: dict[str, dict] = {}

    for tx in txs:
        ticker = tx["ticker"]
        side = tx["side"]
        qty = float(tx["qty"])
        price = float(tx["price"])

        if ticker not in pnl_by_ticker:
            pnl_by_ticker[ticker] = {
                "ticker": ticker,
                "realized_pnl": 0.0,
                "total_sold_value": 0.0,
                "total_sold_qty": 0.0,
                # running average cost tracking
                "_held_qty": 0.0,
                "_avg_cost": 0.0,
            }

        entry = pnl_by_ticker[ticker]

        if side == "BUY":
            # Update running average cost
            total_cost = entry["_held_qty"] * entry["_avg_cost"] + qty * price
            entry["_held_qty"] += qty
            entry["_avg_cost"] = total_cost / entry["_held_qty"] if entry["_held_qty"] > 0 else price
        else:  # SELL
            sell_pnl = qty * (price - entry["_avg_cost"])
            entry["realized_pnl"] += sell_pnl
            entry["total_sold_value"] += qty * price
            entry["total_sold_qty"] += qty
            entry["_held_qty"] = max(0.0, entry["_held_qty"] - qty)

    # Only return tickers with at least one SELL
    result = []
    for entry in pnl_by_ticker.values():
        if entry["total_sold_qty"] > 0:
            result.append({
                "ticker": entry["ticker"],
                "realized_pnl": round(entry["realized_pnl"], 2),
                "total_sold_qty": round(entry["total_sold_qty"], 2),
            })

    return sorted(result, key=lambda x: x["realized_pnl"], reverse=True)


@router.get("/{portfolio_id}/sector-distribution")
def sector_distribution(portfolio_id: int):
    """Returns sector breakdown of current holdings using yfinance sector data."""
    import yfinance as yf

    positions = pf_svc.get_positions(portfolio_id)
    if not positions:
        return {"sectors": {}, "top_sector": None, "top_sector_pct": 0.0, "warning": False}

    total_value = sum(float(p.get("market_value") or 0) for p in positions)
    if total_value == 0:
        return {"sectors": {}, "top_sector": None, "top_sector_pct": 0.0, "warning": False}

    sector_values: dict[str, float] = {}
    for pos in positions:
        mv = float(pos.get("market_value") or 0)
        if mv <= 0:
            continue
        ticker = pos["ticker"]
        try:
            info = yf.Ticker(ticker).info or {}
            sector = info.get("sector") or "Otros"
        except Exception:
            sector = "Otros"
        sector_values[sector] = sector_values.get(sector, 0.0) + mv

    sectors_pct = {s: round(v / total_value * 100, 1) for s, v in sector_values.items()}
    sectors_pct = dict(sorted(sectors_pct.items(), key=lambda x: x[1], reverse=True))

    top_sector = max(sectors_pct, key=lambda s: sectors_pct[s]) if sectors_pct else None
    top_pct = sectors_pct.get(top_sector, 0.0) if top_sector else 0.0

    return {
        "sectors": sectors_pct,
        "top_sector": top_sector,
        "top_sector_pct": top_pct,
        "warning": top_pct > 50,
    }
