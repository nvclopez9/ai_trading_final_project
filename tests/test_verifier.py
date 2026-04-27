"""Tests del verifier numérico post-hoc."""
from src.agent.verifier import verify_response


def _step(observation: str):
    """Crea un AgentAction-like + observation tuple imitando intermediate_steps."""
    return (object(), observation)


def test_no_response_returns_zero():
    v = verify_response("", [])
    assert v["total_unverified"] == 0
    assert v["checked"] == 0


def test_text_without_numbers_passes():
    v = verify_response("AAPL es un buen valor según el RAG.", [])
    assert v["total_unverified"] == 0
    assert v["checked"] == 0


def test_price_appears_in_observation_passes():
    obs = "Ticker: AAPL\nPrecio: $230.45\nCambio: +1.2%"
    v = verify_response("AAPL cotiza a $230.45 (+1.20%).", [_step(obs)])
    # 230.45 dentro de 1% de 230.45 — match. 1.20% match exacto a 1.2%.
    assert v["total_unverified"] == 0


def test_price_within_tolerance_passes():
    obs = "Precio: $230.00"
    v = verify_response("Cotiza a $231.50 hoy.", [_step(obs)])
    # 1.5/230 ≈ 0.65% < 1% tolerancia.
    assert len(v["unverified_prices"]) == 0


def test_price_outside_tolerance_fails():
    obs = "Precio: $230.00"
    v = verify_response("Mi target es $300.00.", [_step(obs)])
    assert 300.00 in v["unverified_prices"]
    assert v["total_unverified"] >= 1


def test_no_steps_means_all_unverified():
    v = verify_response("AAPL a $230 con +1.5%.", [])
    assert v["total_unverified"] >= 2  # precio y porcentaje


def test_market_cap_t():
    obs = "Market cap: 3.5T"
    v = verify_response("Capitaliza 3.55 T$.", [_step(obs)])
    # Tolerancia 5% → 3.55 vs 3.5 = 1.4% < 5%.
    assert len(v["unverified_caps"]) == 0


def test_pct_exact_match():
    obs = "Cambio: -2.34%"
    v = verify_response("Caída del -2.34%.", [_step(obs)])
    assert len(v["unverified_pcts"]) == 0


def test_mixed_some_verified_some_not():
    obs = "Precio: $230.00, Cambio: +1.5%"
    v = verify_response(
        "AAPL cotiza a $230.10 (+1.5%) y mi target es $400.",
        [_step(obs)],
    )
    # $230.10 ok, +1.5% ok, $400 no.
    assert 400.0 in v["unverified_prices"]
    assert v["total_unverified"] == 1
