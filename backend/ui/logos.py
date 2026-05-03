"""Resolución de URLs de logos de empresa para tickers.

Estrategia (en orden):
  1. ``yfinance.Ticker(ticker).info["logo_url"]`` si está y no está vacío.
  2. Fallback: ``https://financialmodelingprep.com/image-stock/{TICKER}.png``
     (gratis, sin auth). No comprobamos si existe — el ``<img onerror>``
     en el HTML lo oculta si devuelve 404.

La función está cacheada con ``functools.lru_cache`` (memoria del proceso)
para compartir resultados entre llamadas repetidas sin re-consultar yfinance.
"""
from __future__ import annotations

from functools import lru_cache


_FMP_FALLBACK = "https://financialmodelingprep.com/image-stock/{symbol}.png"


@lru_cache(maxsize=512)
def _resolve(symbol: str) -> str | None:
    """Intenta varias fuentes y devuelve la primera URL no vacía.

    Devuelve siempre el fallback FMP si no hay logo en yfinance: el caller
    pintará la imagen con ``onerror`` para esconderla si falla la carga.
    """
    if not symbol:
        return None
    sym = symbol.strip().upper()
    if not sym:
        return None
    # Intento 1: yfinance .info["logo_url"]
    try:
        import yfinance as yf  # local import para no penalizar si no se usa
        info = yf.Ticker(sym).info or {}
        url = info.get("logo_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    except Exception:
        # Cualquier fallo (sin red, rate-limit, esquema cambiado): seguimos
        # al fallback. NUNCA propagamos.
        pass
    # Intento 2 (fallback): FMP. URL determinista — el <img onerror> oculta
    # la imagen si el endpoint devuelve 404.
    return _FMP_FALLBACK.format(symbol=sym)


def get_logo_url(ticker: str) -> str | None:
    """Devuelve la URL del logo del ticker o ``None`` si no hay candidato."""
    return _resolve(ticker)


def logo_img_html(
    ticker: str,
    size: int = 24,
    *,
    rounded: bool = True,
    bg_surface: str = "#1B2230",
    border: str = "#252D3D",
) -> str:
    """HTML ``<img>`` con fallback gracioso (oculta la imagen si 404).

    - ``size`` en px (alto y ancho).
    - Bordes y fondo discretos para imágenes con transparencia.
    - ``loading="lazy"`` y ``onerror`` para no romper el layout.
    """
    url = get_logo_url(ticker)
    if not url:
        return ""
    radius = "50%" if rounded else "6px"
    return (
        f"<img src='{url}' alt='{ticker}' loading='lazy' "
        f"onerror=\"this.style.display='none'\" "
        f"style='width:{size}px;height:{size}px;border-radius:{radius};"
        f"object-fit:contain;background:{bg_surface};border:1px solid {border};"
        f"flex-shrink:0;'/>"
    )
