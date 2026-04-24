"""Servicio de gestión de carteras (multi-portfolio).

CRUD para la tabla ``portfolios`` y utilidades asociadas (cash disponible,
validaciones de riesgo y mercados). Funciones puras sin Streamlit.
"""
from datetime import datetime, timezone

from src.services.db import get_conn


VALID_RISKS = {"conservador", "moderado", "agresivo"}
VALID_MARKETS = {"USA", "EUROPA", "ASIA", "GLOBAL", "ALL"}


def _normalize_markets(markets) -> str:
    """Normaliza mercados a CSV uppercase sin espacios. Acepta lista o csv.

    Mercados válidos: USA, EUROPA, ASIA, GLOBAL, ALL.
    """
    if isinstance(markets, (list, tuple, set)):
        items = [str(m).strip().upper() for m in markets if str(m).strip()]
    else:
        items = [m.strip().upper() for m in str(markets).split(",") if m.strip()]
    if not items:
        raise ValueError("Debes indicar al menos un mercado.")
    for m in items:
        if m not in VALID_MARKETS:
            raise ValueError(
                f"Mercado no válido: '{m}'. Válidos: {sorted(VALID_MARKETS)}."
            )
    # Dedupe conservando orden.
    seen = []
    for m in items:
        if m not in seen:
            seen.append(m)
    return ",".join(seen)


def _validate_risk(risk: str) -> str:
    r = (risk or "").strip().lower()
    if r not in VALID_RISKS:
        raise ValueError(
            f"Riesgo no válido: '{risk}'. Válidos: {sorted(VALID_RISKS)}."
        )
    return r


def _row_to_dict(row) -> dict:
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "initial_cash": float(row["initial_cash"]),
        "risk": row["risk"],
        "markets": row["markets"],
        "currency": row["currency"],
        "created_at": row["created_at"],
        "notes": row["notes"],
    }


def create_portfolio(
    name: str,
    initial_cash: float,
    risk: str,
    markets,
    currency: str = "USD",
    notes: str | None = None,
) -> dict:
    """Crea una cartera. Devuelve el dict de la fila creada."""
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre de la cartera no puede estar vacío.")
    if initial_cash is None or float(initial_cash) < 0:
        raise ValueError("El dinero inicial debe ser >= 0.")
    risk = _validate_risk(risk)
    markets_csv = _normalize_markets(markets)
    currency = (currency or "USD").strip().upper()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO portfolios (name, initial_cash, risk, markets, currency, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, float(initial_cash), risk, markets_csv, currency, ts, notes),
            )
        except Exception as e:
            raise ValueError(f"No se pudo crear la cartera (¿nombre duplicado?): {e}")
        new_id = cur.lastrowid
        conn.commit()
        cur.execute("SELECT * FROM portfolios WHERE id = ?", (new_id,))
        return _row_to_dict(cur.fetchone())


def list_portfolios() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolios ORDER BY id ASC")
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_portfolio(portfolio_id: int) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolios WHERE id = ?", (int(portfolio_id),))
        return _row_to_dict(cur.fetchone())


def get_portfolio_by_name(name: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolios WHERE name = ?", (name,))
        return _row_to_dict(cur.fetchone())


def delete_portfolio(portfolio_id: int) -> None:
    """Borra una cartera y en cascada sus posiciones y transacciones.

    No permite borrar la cartera 1 (Default) — es un safeguard mínimo para
    que la app siempre tenga al menos una cartera seed disponible.
    """
    pid = int(portfolio_id)
    if pid == 1:
        raise ValueError("La cartera Default (id=1) no se puede eliminar.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        cur.execute("DELETE FROM positions WHERE portfolio_id = ?", (pid,))
        cur.execute("DELETE FROM portfolios WHERE id = ?", (pid,))
        conn.commit()


def update_risk(portfolio_id: int, risk: str) -> dict:
    risk = _validate_risk(risk)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE portfolios SET risk = ? WHERE id = ?",
            (risk, int(portfolio_id)),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Cartera {portfolio_id} no encontrada.")
        conn.commit()
    return get_portfolio(portfolio_id)


def update_markets(portfolio_id: int, markets) -> dict:
    markets_csv = _normalize_markets(markets)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE portfolios SET markets = ? WHERE id = ?",
            (markets_csv, int(portfolio_id)),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Cartera {portfolio_id} no encontrada.")
        conn.commit()
    return get_portfolio(portfolio_id)


def cash_available(portfolio_id: int) -> float:
    """Cash disponible = initial_cash - buys + sells.

    Si el cálculo cae negativo se devuelve 0 (solo informativo, no bloquea).
    """
    pid = int(portfolio_id)
    p = get_portfolio(pid)
    if p is None:
        return 0.0
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(qty*price), 0) AS s FROM transactions "
            "WHERE portfolio_id = ? AND side = 'BUY'",
            (pid,),
        )
        buys = float(cur.fetchone()["s"] or 0.0)
        cur.execute(
            "SELECT COALESCE(SUM(qty*price), 0) AS s FROM transactions "
            "WHERE portfolio_id = ? AND side = 'SELL'",
            (pid,),
        )
        sells = float(cur.fetchone()["s"] or 0.0)
    cash = p["initial_cash"] - buys + sells
    return max(0.0, cash)


def count_positions(portfolio_id: int) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS n FROM positions WHERE portfolio_id = ?",
            (int(portfolio_id),),
        )
        return int(cur.fetchone()["n"])
