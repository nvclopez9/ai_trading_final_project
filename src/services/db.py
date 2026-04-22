"""Capa de acceso a la base de datos SQLite de la cartera simulada.

Este módulo centraliza dos responsabilidades mínimas:
  1. Abrir conexiones a SQLite con un ``row_factory`` que permita acceder a
     las columnas por nombre (``row["ticker"]``) en lugar de por índice.
  2. Crear el esquema (tablas ``positions`` y ``transactions``) si aún no
     existe, de forma idempotente.

Lo usan ``src/services/portfolio.py`` (CRUD de posiciones y transacciones) y
``app.py`` (que llama a ``init_db()`` una vez al arrancar, dentro del bloque
cacheado ``@st.cache_resource``).
"""
# Librería estándar para rutas, variables de entorno y acceso a SQLite.
import os
import sqlite3
from pathlib import Path
# python-dotenv: permite leer el DB_PATH desde un fichero .env si existe.
from dotenv import load_dotenv

# Cargamos .env al importar el módulo. Es seguro llamarlo varias veces (otros
# ficheros también hacen load_dotenv); no sobrescribe variables ya definidas.
load_dotenv()

# Ruta al fichero SQLite. Por defecto queda dentro del repo para simplificar
# la ejecución local; el usuario puede apuntar a otra ubicación vía .env.
DB_PATH = os.getenv("DB_PATH", "data/portfolio.db")


def get_conn() -> sqlite3.Connection:
    """Devuelve una conexión SQLite con row_factory configurado.

    Garantiza que el directorio padre exista (Path.mkdir con parents+exist_ok
    es idempotente) para que la primera ejecución funcione sin setup manual.
    El row_factory sqlite3.Row permite tratar cada fila como un dict-like.
    """
    # Creamos la carpeta data/ si todavía no existe (primer arranque).
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Con esto podemos hacer row["ticker"] en vez de row[0], más legible y
    # resistente a cambios de orden de columnas.
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea las tablas del esquema si no existen. Es idempotente y barata."""
    # Un único with para agrupar ambos CREATE y un solo commit al final: más
    # rápido y atómico si se interrumpe la ejecución a mitad.
    with get_conn() as conn:
        cur = conn.cursor()
        # Tabla positions: una fila por ticker con la posición abierta.
        # ticker es PRIMARY KEY porque no queremos dos filas del mismo símbolo
        # (la lógica de buy/sell actualiza esta fila en lugar de duplicarla).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT PRIMARY KEY,
                qty REAL NOT NULL,
                avg_price REAL NOT NULL
            )
            """
        )
        # Tabla transactions: libro de operaciones inmutable (append-only).
        # Guardamos lado (BUY/SELL), cantidad, precio y timestamp ISO-8601.
        # El id autoincremental sirve como desempate al ordenar por ts.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                side TEXT,
                qty REAL,
                price REAL,
                ts TEXT
            )
            """
        )
        conn.commit()
