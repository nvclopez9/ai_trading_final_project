"""Verifier numérico post-hoc: detecta cifras en la respuesta del agente que
no aparecen en las observaciones de las tools que se ejecutaron en ese turno.

Por qué este módulo
-------------------
El agente puede alucinar precios, porcentajes y market caps. Aunque el system
prompt lo prohíbe explícitamente, un cinturón extra es barato: comparamos
cada cifra del texto contra el set de cifras que aparecieron en los outputs
de las tools (intermediate_steps). Si una cifra no tiene respaldo, no
bloqueamos la respuesta — solo añadimos un caption discreto avisando.

Tolerancias
-----------
- Precios: 1% (los precios de yfinance pueden mover entre tool y render).
- Porcentajes: comparación exacta a 2 decimales.
- Market caps en B/T: 5% (yfinance redondea de forma agresiva).
"""
from __future__ import annotations

import re
from typing import Iterable

# ─── Regex de extracción ────────────────────────────────────────────────────
# Precios: $123.45, $1,234.56, 123.45 USD, 1.234,56 €. Capturamos número y unidad.
_PRICE_RE = re.compile(
    r"\$\s*([+-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
)
# Porcentajes: +1.23%, -4.5%, 12,34 %.
_PCT_RE = re.compile(r"([+-]?\d+(?:[.,]\d+)?)\s*%")
# Market caps abreviados: 2.5 T$, 1,8 B, 234 M$.
_CAP_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([TBM])\b", re.IGNORECASE
)


def _to_float(s: str) -> float | None:
    """Convierte '1.234,56' o '1,234.56' a float. Devuelve None si imposible."""
    s = s.strip().replace(" ", "")
    if not s:
        return None
    # Heurística: si tiene tanto '.' como ',', el último es decimal y el otro
    # separador de miles. Si solo tiene uno, asumimos que es decimal.
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_numbers(text: str) -> dict[str, list[float]]:
    """Devuelve {'price': [...], 'pct': [...], 'cap': [...]} con los números
    detectados. Cada bucket en su unidad nativa."""
    prices: list[float] = []
    pcts: list[float] = []
    caps: list[float] = []  # normalizados a USD absolutos

    for m in _PRICE_RE.finditer(text or ""):
        v = _to_float(m.group(1))
        if v is not None:
            prices.append(v)
    for m in _PCT_RE.finditer(text or ""):
        v = _to_float(m.group(1))
        if v is not None:
            pcts.append(v)
    for m in _CAP_RE.finditer(text or ""):
        v = _to_float(m.group(1))
        unit = m.group(2).upper()
        if v is None:
            continue
        mult = {"T": 1e12, "B": 1e9, "M": 1e6}[unit]
        caps.append(v * mult)
    return {"price": prices, "pct": pcts, "cap": caps}


def _observations_text(steps: Iterable) -> str:
    """Junta las observations de intermediate_steps en un único string."""
    chunks: list[str] = []
    for step in steps or []:
        try:
            obs = step[1] if isinstance(step, tuple) else getattr(step, "observation", None)
        except Exception:
            obs = None
        if obs is None:
            continue
        chunks.append(str(obs))
    return "\n".join(chunks)


def _match(value: float, candidates: list[float], tol: float) -> bool:
    """True si ``value`` está dentro de ``tol`` (relativa) de algún candidato."""
    for c in candidates:
        if c == 0:
            if value == 0:
                return True
            continue
        if abs(value - c) / abs(c) <= tol:
            return True
    return False


def verify_response(response_text: str, intermediate_steps: Iterable) -> dict:
    """Devuelve un dict con cifras del texto que no aparecen en las tool outputs.

    Estructura: ``{"unverified_prices": [...], "unverified_pcts": [...],
    "unverified_caps": [...], "total_unverified": N, "checked": M}``.

    Si no hay tool calls (steps vacíos) y el texto contiene cifras, todas
    cuentan como unverified — esto es deliberado: un agente que da números
    sin haber llamado a ninguna tool casi siempre está alucinando.
    """
    if not response_text:
        return {"unverified_prices": [], "unverified_pcts": [],
                "unverified_caps": [], "total_unverified": 0, "checked": 0}

    text_nums = _extract_numbers(response_text)
    obs_text = _observations_text(intermediate_steps)
    obs_nums = _extract_numbers(obs_text)

    unverified_prices = [
        v for v in text_nums["price"] if not _match(v, obs_nums["price"], tol=0.01)
    ]
    unverified_pcts = [
        v for v in text_nums["pct"] if not _match(v, obs_nums["pct"], tol=0.0001)
    ]
    unverified_caps = [
        v for v in text_nums["cap"] if not _match(v, obs_nums["cap"], tol=0.05)
    ]
    checked = (len(text_nums["price"]) + len(text_nums["pct"])
               + len(text_nums["cap"]))
    total_unv = (len(unverified_prices) + len(unverified_pcts)
                 + len(unverified_caps))
    return {
        "unverified_prices": unverified_prices,
        "unverified_pcts": unverified_pcts,
        "unverified_caps": unverified_caps,
        "total_unverified": total_unv,
        "checked": checked,
    }
