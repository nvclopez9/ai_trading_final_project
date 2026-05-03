"""User preferences API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesBody(BaseModel):
    risk_profile: str | None = None
    time_horizon: str | None = None
    favorite_sectors: list[str] | None = None
    excluded_tickers: list[str] | None = None
    mark_onboarded: bool = True


@router.get("")
def get_preferences():
    from backend.services.preferences import get_preferences as _get
    return _get()


@router.put("")
def update_preferences(body: PreferencesBody):
    try:
        from backend.services.preferences import update_preferences as _update
        return _update(
            risk_profile=body.risk_profile,
            time_horizon=body.time_horizon,
            favorite_sectors=body.favorite_sectors,
            excluded_tickers=body.excluded_tickers,
            mark_onboarded=body.mark_onboarded,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
