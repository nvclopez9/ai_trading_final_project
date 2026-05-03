"""Servicio de preferencias del usuario (Fase 3).

Singleton row (id=1) en SQLite con: ``risk_profile``, ``time_horizon``,
``favorite_sectors`` (CSV), ``excluded_tickers`` (CSV), ``onboarded_at``.

Estas preferencias se inyectan en el system prompt del agente para que las
recomendaciones (``analyze_buy_opportunities``, RAG, comparativas) las tengan
en cuenta sin que el usuario tenga que repetirlas en cada turno.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.services.db import get_conn, init_db


_VALID_RISK = {"conservador", "moderado", "agresivo"}
_VALID_HORIZON = {"corto", "medio", "largo"}


def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _join_csv(items: list[str] | None) -> str:
    if not items:
        return ""
    return ",".join(p.strip() for p in items if p and p.strip())


def get_preferences() -> dict:
    """Devuelve las preferencias del usuario o defaults si no hay onboarding.

    Estructura: ``{risk_profile, time_horizon, favorite_sectors (list),
    excluded_tickers (list), onboarded (bool)}``.
    """
    init_db()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_preferences WHERE id = 1")
        row = cur.fetchone()
    if row is None:
        return {
            "risk_profile": "moderado",
            "time_horizon": "medio",
            "favorite_sectors": [],
            "excluded_tickers": [],
            "onboarded": False,
        }
    return {
        "risk_profile": row["risk_profile"],
        "time_horizon": row["time_horizon"],
        "favorite_sectors": _split_csv(row["favorite_sectors"]),
        "excluded_tickers": _split_csv(row["excluded_tickers"]),
        "onboarded": bool(row["onboarded_at"]),
    }


def update_preferences(
    risk_profile: str | None = None,
    time_horizon: str | None = None,
    favorite_sectors: list[str] | None = None,
    excluded_tickers: list[str] | None = None,
    mark_onboarded: bool = True,
) -> dict:
    """Crea o actualiza las preferencias. Solo los campos no-None se modifican."""
    init_db()
    if risk_profile is not None and risk_profile not in _VALID_RISK:
        raise ValueError(f"risk_profile inválido: {risk_profile}")
    if time_horizon is not None and time_horizon not in _VALID_HORIZON:
        raise ValueError(f"time_horizon inválido: {time_horizon}")

    current = get_preferences()
    new = {
        "risk_profile": risk_profile if risk_profile is not None else current["risk_profile"],
        "time_horizon": time_horizon if time_horizon is not None else current["time_horizon"],
        "favorite_sectors": _join_csv(
            favorite_sectors if favorite_sectors is not None else current["favorite_sectors"]
        ),
        "excluded_tickers": _join_csv(
            [t.upper() for t in (excluded_tickers if excluded_tickers is not None else current["excluded_tickers"])]
        ),
    }
    onboarded_at = (
        datetime.now(timezone.utc).isoformat(timespec="seconds")
        if mark_onboarded else None
    )

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM user_preferences WHERE id = 1")
        exists = cur.fetchone() is not None
        if exists:
            cur.execute(
                """
                UPDATE user_preferences
                SET risk_profile = ?, time_horizon = ?,
                    favorite_sectors = ?, excluded_tickers = ?,
                    onboarded_at = COALESCE(?, onboarded_at)
                WHERE id = 1
                """,
                (
                    new["risk_profile"], new["time_horizon"],
                    new["favorite_sectors"], new["excluded_tickers"],
                    onboarded_at,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_preferences
                  (id, risk_profile, time_horizon, favorite_sectors,
                   excluded_tickers, onboarded_at)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (
                    new["risk_profile"], new["time_horizon"],
                    new["favorite_sectors"], new["excluded_tickers"],
                    onboarded_at,
                ),
            )
        conn.commit()

    return get_preferences()


def render_for_prompt() -> str:
    """Compone una línea para inyectar en el system prompt.

    Devuelve algo del estilo:
      "Perfil del usuario: riesgo moderado, horizonte medio. Sectores favoritos:
       tech, salud. Evita: TSLA, MO."

    Si no hay preferencias (onboarded=False), devuelve string vacío.
    """
    prefs = get_preferences()
    if not prefs["onboarded"]:
        return ""
    parts = [
        f"riesgo {prefs['risk_profile']}",
        f"horizonte {prefs['time_horizon']}",
    ]
    line = f"Perfil del usuario: {', '.join(parts)}."
    if prefs["favorite_sectors"]:
        line += f" Sectores favoritos: {', '.join(prefs['favorite_sectors'])}."
    if prefs["excluded_tickers"]:
        line += f" Evita: {', '.join(prefs['excluded_tickers'])}."
    return line
