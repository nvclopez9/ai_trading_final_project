"""Tests deterministas de los slash commands.

Solo ejercitan rutas que NO necesitan LLM real: parseo de argumentos, manejo
de errores, formato de salida, integración con el servicio de cartera.
"""
from unittest.mock import patch

import pytest

from src.agent.slash_commands import (
    COMMAND_USAGES,
    execute_pending_trade,
    try_handle_slash,
)


def test_non_slash_returns_none():
    assert try_handle_slash("hola", "sess", 1) is None
    assert try_handle_slash("¿precio de AAPL?", "sess", 1) is None
    assert try_handle_slash("", "sess", 1) is None


def test_unknown_slash_returns_help_message():
    r = try_handle_slash("/inexistente foo", "sess", 1, persist_history=False)
    assert r is not None
    assert "Comando desconocido" in r["text"]
    assert "/ayuda" in r["text"]


def test_ayuda_lists_commands():
    r = try_handle_slash("/ayuda", "sess", 1, persist_history=False)
    assert r is not None
    for cmd in COMMAND_USAGES:
        assert cmd in r["text"]


def test_comprar_missing_args():
    r = try_handle_slash("/comprar", "sess", 1, persist_history=False)
    assert r is not None
    assert "Faltan argumentos" in r["text"]


def test_comprar_invalid_qty():
    r = try_handle_slash("/comprar AAPL diez", "sess", 1, persist_history=False)
    assert r is not None
    assert "Cantidad inválida" in r["text"]


def test_comprar_zero_qty():
    r = try_handle_slash("/comprar AAPL 0", "sess", 1, persist_history=False)
    assert r is not None
    assert "mayor que 0" in r["text"]


def test_comprar_proposes_pending_trade():
    r = try_handle_slash("/comprar AAPL 5", "sess", 1, persist_history=False)
    assert r is not None
    assert r["is_pending_buy"] is True
    assert r["pending_payload"]["ticker"] == "AAPL"
    assert r["pending_payload"]["qty"] == 5.0
    assert r["pending_payload"]["side"] == "BUY"


def test_vender_proposes_pending_trade():
    r = try_handle_slash("/vender MSFT 2", "sess", 1, persist_history=False)
    assert r is not None
    assert r["is_pending_sell"] is True
    assert r["pending_payload"]["side"] == "SELL"
    assert r["pending_payload"]["qty"] == 2.0


def test_limpiar_returns_clear_flag():
    r = try_handle_slash("/limpiar", "sess", 1, persist_history=False)
    assert r is not None
    assert r["clear_history"] is True


def test_precio_missing_ticker():
    r = try_handle_slash("/precio", "sess", 1, persist_history=False)
    assert r is not None
    assert "Falta el ticker" in r["text"]


def test_precio_uses_get_ticker_status():
    with patch("src.agent.slash_commands.get_ticker_status") as mocked:
        mocked.invoke.return_value = "AAPL · 230.45 USD\nCambio: +1.20%"
        r = try_handle_slash("/precio aapl", "sess", 1, persist_history=False)
    assert r is not None
    mocked.invoke.assert_called_once()
    call_kwargs = mocked.invoke.call_args.args[0]
    assert call_kwargs["ticker"] == "AAPL"


def test_noticias_empty_list():
    with patch("src.agent.slash_commands.fetch_ticker_news", return_value=[]):
        r = try_handle_slash("/noticias TSLA", "sess", 1, persist_history=False)
    assert r is not None
    assert "No encontré noticias" in r["text"]


def test_execute_pending_trade_buy(monkeypatch):
    captured = {}

    def fake_buy(ticker, qty, portfolio_id=1):
        captured["call"] = (ticker, qty, portfolio_id)
        return {"ticker": ticker, "qty": qty, "price": 100.0,
                "new_qty": qty, "new_avg_price": 100.0, "portfolio_id": portfolio_id}

    monkeypatch.setattr("src.agent.slash_commands.portfolio_svc.buy", fake_buy)
    monkeypatch.setattr("src.agent.slash_commands.set_active_portfolio", lambda pid: None)
    msg = execute_pending_trade({"ticker": "AAPL", "qty": 3, "side": "BUY"}, 1)
    assert "Compra ejecutada" in msg
    assert captured["call"] == ("AAPL", 3.0, 1)


def test_execute_pending_trade_invalid_side():
    msg = execute_pending_trade({"ticker": "AAPL", "qty": 1, "side": "INVALID"}, 1)
    assert "Lado desconocido" in msg or "❌" in msg
