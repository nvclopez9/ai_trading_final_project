"""Helpers de formato y componentes visuales reutilizables.

Todo el formateo numérico se concentra aquí para mantener consistencia
visual en TODA la app (Home, Mercado, Cartera, Hot).

Convenciones:
- Locale visual es_ES: miles con punto, decimales con coma.
- Porcentajes siempre con signo explícito y 2 decimales.
- Market cap abreviado (B$/M$) para que quepa en las tarjetas compactas.
- Verde/rojo semánticos definidos como constantes para no dispersar hex codes.
"""
from __future__ import annotations

# Paleta semántica. Se replica en charts.py y en estilos inline de markdown.
COLOR_UP = "#00C851"
COLOR_DOWN = "#FF4444"
COLOR_NEUTRAL = "#9AA0A6"
COLOR_ACCENT = "#2962FF"
COLOR_WARNING = "#FFB020"


def _to_es_number(x: float, decimals: int = 2) -> str:
    """Convierte un float a notación es_ES ('1.234,56').

    Hacemos el swap manual porque ``locale`` en Windows depende de que el
    locale esté instalado y f-strings con locale no son portables.
    """
    s = f"{x:,.{decimals}f}"
    # Inversión: 1,234.56 -> 1.234,56. Usamos placeholder temporal.
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_money(x: float | None, currency: str = "USD") -> str:
    """Formatea una cantidad monetaria con símbolo de la divisa al final."""
    if x is None:
        return "—"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency)
    return f"{_to_es_number(x)} {symbol}"


def fmt_pct(x: float | None, with_sign: bool = True) -> str:
    """Formatea un porcentaje (el input ya viene en %, p. ej. 1.25 -> +1,25%)."""
    if x is None:
        return "—"
    sign = "+" if with_sign and x >= 0 else ("-" if x < 0 else "")
    return f"{sign}{_to_es_number(abs(x))}%"


def fmt_qty(x: float | None) -> str:
    """Formatea cantidad de acciones: entero si lo es, 4 decimales si fraccional."""
    if x is None:
        return "—"
    if x == int(x):
        return _to_es_number(x, decimals=0)
    return _to_es_number(x, decimals=4)


def fmt_market_cap(x: float | None) -> str:
    """Formatea capitalización abreviada (T$ / B$ / M$)."""
    if x is None or x == 0:
        return "—"
    abs_x = abs(x)
    if abs_x >= 1e12:
        return f"{_to_es_number(x / 1e12)} T$"
    if abs_x >= 1e9:
        return f"{_to_es_number(x / 1e9)} B$"
    if abs_x >= 1e6:
        return f"{_to_es_number(x / 1e6)} M$"
    return fmt_money(x)


def color_for_delta(x: float | None) -> str:
    """Devuelve el hex del color semántico según el signo del delta."""
    if x is None:
        return COLOR_NEUTRAL
    if x > 0:
        return COLOR_UP
    if x < 0:
        return COLOR_DOWN
    return COLOR_NEUTRAL
