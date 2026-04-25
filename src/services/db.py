"""Capa de acceso a la base de datos SQLite de la cartera simulada.

Este módulo centraliza:
  1. Abrir conexiones a SQLite con row_factory por nombre.
  2. Crear / migrar el esquema (portfolios, positions, transactions) de forma
     idempotente y retrocompatible.

Multi-cartera (Feature 1): se añade la tabla ``portfolios`` y una columna
``portfolio_id`` en ``positions`` y ``transactions`` para permitir varias
carteras del mismo usuario. La migración es retrocompatible: si las tablas
existen sin la columna, la añadimos mediante ALTER TABLE.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/portfolio.db")


def get_conn() -> sqlite3.Connection:
    """Devuelve una conexión SQLite con row_factory configurado."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Habilitamos foreign keys (SQLite las desactiva por defecto).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def init_db() -> None:
    """Crea / migra el esquema. Idempotente y retrocompatible."""
    with get_conn() as conn:
        cur = conn.cursor()

        # Tabla portfolios (nueva en Feature 1).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                initial_cash REAL NOT NULL,
                risk TEXT NOT NULL CHECK (risk IN ('conservador','moderado','agresivo')),
                markets TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                created_at TEXT NOT NULL,
                notes TEXT
            )
            """
        )

        # Positions: creación inicial (con portfolio_id). Si la tabla existía
        # sin columna, la migramos con ALTER TABLE.
        if not _table_exists(cur, "positions"):
            cur.execute(
                """
                CREATE TABLE positions (
                    ticker TEXT NOT NULL,
                    qty REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    portfolio_id INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(portfolio_id, ticker)
                )
                """
            )
        else:
            if not _column_exists(cur, "positions", "portfolio_id"):
                try:
                    cur.execute(
                        "ALTER TABLE positions ADD COLUMN portfolio_id INTEGER NOT NULL DEFAULT 1"
                    )
                except sqlite3.OperationalError:
                    pass
            # Indice único compuesto (portfolio_id, ticker). Si ya existe lo ignoramos.
            try:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_portfolio_ticker "
                    "ON positions(portfolio_id, ticker)"
                )
            except sqlite3.OperationalError:
                pass

        # Transactions: igual patrón.
        if not _table_exists(cur, "transactions"):
            cur.execute(
                """
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    side TEXT,
                    qty REAL,
                    price REAL,
                    ts TEXT,
                    portfolio_id INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        else:
            if not _column_exists(cur, "transactions", "portfolio_id"):
                try:
                    cur.execute(
                        "ALTER TABLE transactions ADD COLUMN portfolio_id INTEGER NOT NULL DEFAULT 1"
                    )
                except sqlite3.OperationalError:
                    pass

        # Watchlist: tickers en seguimiento (no posición) por cartera.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                note TEXT,
                added_at TEXT NOT NULL,
                UNIQUE(portfolio_id, ticker),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
            """
        )

        # Seed: si no hay ninguna cartera, creamos la Default con id=1.
        cur.execute("SELECT COUNT(*) AS n FROM portfolios")
        n = cur.fetchone()["n"]
        if n == 0:
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cur.execute(
                """
                INSERT INTO portfolios (id, name, initial_cash, risk, markets, currency, created_at, notes)
                VALUES (1, 'Default', 10000, 'moderado', 'ALL', 'USD', ?, 'Cartera por defecto')
                """,
                (ts,),
            )

        conn.commit()
