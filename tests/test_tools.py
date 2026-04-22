"""Smoke tests de las tools más críticas del proyecto.

Objetivo: dar cobertura básica a los caminos importantes sin depender de
servicios externos (Yahoo Finance, Ollama). Cubrimos:

  1. ``get_ticker_status`` con ticker inválido: debe devolver un STRING
     con mensaje controlado, nunca lanzar una excepción ni devolver None.
  2. Flujo completo buy -> buy (avg ponderado) -> sell parcial (avg
     mantenido) -> sell total (cierre de posición, fila borrada).
  3. Validación: vender más de lo que posees lanza ``ValueError``.
  4. ``get_portfolio_value`` con un ticker "stale" (sin precio actual):
     se excluye del total y aparece en ``stale_tickers``.

Técnica: fixtures pytest para aislar cada test con su propia BD temporal
(``tmp_db``) y monkeypatch de ``_current_price`` para no tocar yfinance.
"""
# pytest: framework de tests + fixtures.
import pytest

# Módulos bajo test. Importamos el módulo db para poder monkeypatchear DB_PATH.
from src.services import db as db_module
from src.services import portfolio
# get_ticker_status es una @tool de LangChain — lo invocamos con el helper
# de abajo porque la forma de llamarla cambia según cómo se registre.
from src.tools.market_tools import get_ticker_status


def _invoke_tool(tool, **kwargs):
    """Invoca una tool de LangChain de forma compatible con versiones distintas.

    LangChain 0.3 expone ``.invoke({"kwarg": ...})``; si estuviéramos con
    funciones planas sin decorar se podría llamar directamente. Este helper
    hace ambos casos transparentes para los tests.
    """
    if hasattr(tool, "invoke"):
        return tool.invoke(kwargs)
    return tool(**kwargs)


def test_get_ticker_status_invalid():
    """Un ticker inventado debe devolver un string de error, no excepción."""
    out = _invoke_tool(get_ticker_status, ticker="ZZZZZZ")
    # Garantía de contrato: siempre string (las tools con modelos pequeños
    # deben devolver str — explicado en el docstring de market_tools.py).
    assert isinstance(out, str)
    # Aceptamos varias redacciones posibles del mensaje de error.
    # Esto es robusto frente a cambios de wording futuros sin romper el test.
    low = out.lower()
    assert ("error" in low) or ("no " in low) or ("no pude" in low) or ("no se" in low)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Crea una BD SQLite temporal y redirige DB_PATH a ella para el test.

    ``tmp_path`` es un directorio único por test que pytest limpia luego.
    ``monkeypatch.setattr`` apunta el módulo db a nuestra BD aislada para
    que el test real no toque data/portfolio.db.
    """
    db_file = tmp_path / "portfolio.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_file))
    # init_db crea las tablas en la BD temporal.
    db_module.init_db()
    return db_file


@pytest.fixture
def fixed_price(monkeypatch):
    """Monkeypatchea ``_current_price`` para devolver un precio controlado.

    Usamos un dict mutable {"value": float} para que cada test pueda
    cambiar el precio "de mercado" en medio de la ejecución (simulando
    compras y ventas a precios distintos).
    """
    prices = {"value": 100.0}

    def _fake_price(_symbol):
        # Ignora el símbolo: todos los tickers "valen" lo mismo en el test.
        return prices["value"]

    monkeypatch.setattr(portfolio, "_current_price", _fake_price)
    return prices


def test_portfolio_buy_sell_flow(tmp_db, fixed_price):
    """Flujo completo buy -> buy -> sell parcial -> sell total."""
    # 1. Compra inicial de 10 acciones a $100. avg debe ser $100.
    fixed_price["value"] = 100.0
    r1 = portfolio.buy("AAPL", 10)
    assert r1["new_qty"] == 10
    assert abs(r1["new_avg_price"] - 100.0) < 1e-6

    # 2. Segunda compra a $120: avg ponderado = (10*100 + 5*120) / 15 = 106.67.
    # Este es el punto didáctico clave: demostrar la media ponderada.
    fixed_price["value"] = 120.0
    r2 = portfolio.buy("AAPL", 5)
    assert r2["new_qty"] == 15
    expected_avg = (10 * 100 + 5 * 120) / 15
    assert abs(r2["new_avg_price"] - expected_avg) < 1e-6

    # 3. Venta parcial: quedan 7 acciones, avg SE MANTIENE (no se recalcula
    # hacia abajo; el coste base de lo que queda es el de la cesta original).
    fixed_price["value"] = 130.0
    r3 = portfolio.sell("AAPL", 8)
    assert r3["new_qty"] == 7
    assert abs(r3["new_avg_price"] - expected_avg) < 1e-6

    # 4. Venta total: new_qty llega a 0 y la fila debe borrarse de positions.
    r4 = portfolio.sell("AAPL", 7)
    assert r4["new_qty"] == 0

    # Confirmación del borrado: get_positions no devuelve AAPL.
    positions = portfolio.get_positions()
    assert all(p["ticker"] != "AAPL" for p in positions)


def test_sell_over_qty_raises(tmp_db, fixed_price):
    """Vender más de lo que posees debe lanzar ValueError (no silencioso)."""
    fixed_price["value"] = 50.0
    portfolio.buy("MSFT", 3)
    # Tenemos 3, intentamos vender 10: ValueError con mensaje explicativo.
    # La tool de cartera (portfolio_sell) capturará este ValueError y lo
    # convertirá en string "❌ No se pudo ejecutar la venta: ...".
    with pytest.raises(ValueError):
        portfolio.sell("MSFT", 10)


def test_portfolio_value_with_stale(tmp_db, monkeypatch):
    """Un ticker sin precio actual debe aparecer en stale_tickers y quedar fuera del total."""
    # Mapa de precios "de mercado": AAPL sí tiene, MSFT no.
    prices_map = {"AAPL": 100.0, "MSFT": 200.0}

    # Primero fijamos un precio de compra estable ($50) para ambas compras
    # y así controlar el cost_basis exactamente.
    def _buy_price(_symbol):
        return 50.0

    monkeypatch.setattr(portfolio, "_current_price", _buy_price)
    portfolio.buy("AAPL", 10)
    portfolio.buy("MSFT", 5)

    # Ahora cambiamos el mock para simular que MSFT se quedó sin precio
    # (yfinance falló, rate-limit, etc.) y AAPL sigue dando 100.
    def _mixed_price(symbol):
        if symbol == "MSFT":
            return None
        return prices_map.get(symbol)

    monkeypatch.setattr(portfolio, "_current_price", _mixed_price)

    # MSFT debe listarse como stale, y total_value debe ser SOLO el de AAPL
    # (10 acciones * $100 = $1000), sin contar MSFT.
    totals = portfolio.get_portfolio_value()
    assert "MSFT" in totals["stale_tickers"]
    assert totals["total_value"] == pytest.approx(10 * 100.0)
