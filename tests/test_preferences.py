"""Tests del servicio de preferencias del usuario."""
import os
import tempfile

import pytest


@pytest.fixture
def tmp_db(monkeypatch):
    """Aísla cada test en una BD temporal limpia."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("DB_PATH", tmp.name)
    # Forzamos recarga del módulo db para que coja el nuevo DB_PATH.
    import importlib
    from src.services import db
    importlib.reload(db)
    from src.services import preferences as prefs
    importlib.reload(prefs)
    yield prefs
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


def test_defaults_when_no_row(tmp_db):
    p = tmp_db.get_preferences()
    assert p["risk_profile"] == "moderado"
    assert p["time_horizon"] == "medio"
    assert p["favorite_sectors"] == []
    assert p["excluded_tickers"] == []
    assert p["onboarded"] is False


def test_update_creates_row(tmp_db):
    tmp_db.update_preferences(
        risk_profile="agresivo",
        time_horizon="corto",
        favorite_sectors=["tech", "salud"],
        excluded_tickers=["mo", "xom"],
    )
    p = tmp_db.get_preferences()
    assert p["risk_profile"] == "agresivo"
    assert p["time_horizon"] == "corto"
    assert "tech" in p["favorite_sectors"]
    # Excluded tickers se normalizan a mayúsculas.
    assert "MO" in p["excluded_tickers"]
    assert "XOM" in p["excluded_tickers"]
    assert p["onboarded"] is True


def test_update_preserves_unset_fields(tmp_db):
    tmp_db.update_preferences(risk_profile="conservador", time_horizon="largo")
    tmp_db.update_preferences(favorite_sectors=["energia"])
    p = tmp_db.get_preferences()
    # No tocados → conservan el valor anterior.
    assert p["risk_profile"] == "conservador"
    assert p["time_horizon"] == "largo"
    assert p["favorite_sectors"] == ["energia"]


def test_render_for_prompt_empty_when_not_onboarded(tmp_db):
    assert tmp_db.render_for_prompt() == ""


def test_render_for_prompt_includes_profile(tmp_db):
    tmp_db.update_preferences(
        risk_profile="conservador",
        time_horizon="largo",
        favorite_sectors=["tech"],
        excluded_tickers=["MO"],
    )
    line = tmp_db.render_for_prompt()
    assert "conservador" in line
    assert "largo" in line
    assert "tech" in line
    assert "MO" in line


def test_invalid_risk_raises(tmp_db):
    with pytest.raises(ValueError):
        tmp_db.update_preferences(risk_profile="loco")


def test_invalid_horizon_raises(tmp_db):
    with pytest.raises(ValueError):
        tmp_db.update_preferences(time_horizon="eterno")
