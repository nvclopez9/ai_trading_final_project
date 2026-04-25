"""Universos curados de tickers por tier de capitalización y clase de activo.

Este módulo centraliza las listas que la app usa como "snapshot" del mercado
en distintos puntos:

- ``_fetch_fallback_quotes`` (en ``market_tools.py``) construye su universo
  combinando varias de estas listas para los snapshots de la Home y de
  ``get_hot_tickers``.
- ``analyze_buy_opportunities`` (en ``advisor_tool.py``) usa
  ``get_universe(tier, asset_class)`` para acotar el universo de candidatos
  según lo que el usuario pida (small caps, ETFs de oro, BTC, etc.).

Notas didácticas:
- Las listas son curadas y representativas, no exhaustivas. Para algo
  exhaustivo habría que conectarse a un screener real (Yahoo, FMP, Alpha
  Vantage, etc.). Para un MVP educativo esto es suficiente.
- Los tiers de capitalización se basan en convención USA: small <$2B,
  mid $2-10B, large >$10B. La asignación de cada ticker a un tier puede
  envejecer (un small cap puede pasar a mid en pocos meses); el filtro
  real por ``marketCap`` se aplica además en advisor_tool.
- ETPs apalancados (3x bull/bear) llevan riesgo de decay diario y no son
  holdables a largo plazo. La advisor tool emite aviso automático cuando
  se piden con ``asset_class='leveraged'``.
"""
from __future__ import annotations


# Mega y large caps (>$10B). Mezcla de tech, financial, healthcare, energy,
# consumer, industrial, comunicación. Suficiente para componer carteras
# diversificadas tipo "blue chips".
LARGE_CAP: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
    "AVGO", "JPM", "V", "UNH", "JNJ", "XOM", "WMT", "MA", "PG", "KO",
    "PEP", "HD", "CVX", "BAC", "ORCL", "ADBE", "CRM", "NFLX", "INTC",
    "AMD", "QCOM", "DIS",
]

# Mid caps ($2B-$10B): tech innovador, fintech, e-commerce, plataformas.
MID_CAP: list[str] = [
    "PLTR", "ROKU", "DOCU", "RBLX", "DASH", "HOOD", "COIN", "NET",
    "DDOG", "SNOW", "U", "TWLO", "Z", "ZG", "ETSY", "AFRM", "SHOP",
    "MDB", "CRWD", "ZS", "OKTA", "PINS", "SNAP", "SQ", "SOFI",
]

# Small caps (<$2B): higher risk/reward, growth speculativo. Incluye nombres
# meme/crypto-mining para cubrir lo que un usuario "agresivo" podría pedir.
SMALL_CAP: list[str] = [
    "AAOI", "BIRD", "FUBO", "LMND", "UPST", "RIOT", "MARA", "NKLA",
    "WISH", "FIGS", "OPEN", "BB", "DKNG", "BARK", "GME", "AMC",
    "IRBT", "EVGO", "PLUG", "BBAI", "RKLB", "ASTS", "CLSK",
]

# ETFs (índices, sectoriales, factor, dividendos). Vehículos para inversión
# pasiva y exposición temática.
ETFS: list[str] = [
    "SPY", "QQQ", "VOO", "VTI", "DIA", "IWM",
    "ARKK", "ARKG",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLI", "XLP", "XLB", "XLU", "XLRE",
    "VNQ", "SCHB", "SCHD", "VYM",
]

# ETPs sobre commodities físicos: oro, plata, platino, paladio, petróleo,
# gas natural, agro, materias primas amplias, cobre.
ETPS_COMMODITIES: list[str] = [
    "GLD", "IAU", "SLV", "PPLT", "PALL",
    "USO", "BNO", "UNG",
    "DBA", "DBC", "CPER",
]

# ETPs / ETFs de crypto: spot BTC (IBIT, FBTC, ARKB, GBTC), futuros BTC (BITO,
# BTF), spot ETH (ETHA, ETHV).
ETPS_CRYPTO: list[str] = [
    "IBIT", "FBTC", "BITO", "GBTC", "ARKB", "BTF",
    "ETHA", "ETHV",
]

# ETPs apalancados (3x bull/bear) y volatilidad. Riesgo elevado por decay
# diario: NO son holdables a largo plazo. Se exponen como universo
# explícitamente seleccionable; advisor_tool emite aviso automático.
LEVERAGED_ETPS: list[str] = [
    "TQQQ", "SQQQ",
    "UPRO", "SPXU",
    "SOXL", "SOXS",
    "TNA", "TZA",
    "UVXY", "SVXY",
    "BITX", "ETHU",
]


def _stock_pool_for(tier: str) -> list[str]:
    """Selecciona el pool de acciones según el tier solicitado."""
    t = (tier or "any").strip().lower()
    if t == "small":
        return list(SMALL_CAP)
    if t == "mid":
        return list(MID_CAP)
    if t == "large":
        return list(LARGE_CAP)
    # 'any' o cualquier valor desconocido: combinamos los tres.
    return list(LARGE_CAP) + list(MID_CAP) + list(SMALL_CAP)


def get_universe(tier: str = "large", asset_class: str = "stock") -> list[str]:
    """Devuelve el universo de tickers según tier y asset_class.

    - ``tier``: 'small' | 'mid' | 'large' | 'any' (solo aplica a stocks).
    - ``asset_class``:
        - 'stock'      -> acciones del tier indicado.
        - 'etf'        -> ETFs (sin commodities ni crypto).
        - 'commodity'  -> ETPs sobre commodities físicos.
        - 'crypto'     -> ETPs/ETFs sobre crypto.
        - 'leveraged'  -> ETPs apalancados (riesgo alto).
        - 'all'        -> stocks (del tier) + ETFs + commodities + crypto
                          (excluye apalancados por seguridad).

    Devuelve la lista deduplicada en orden estable.
    """
    ac = (asset_class or "stock").strip().lower()

    if ac == "etf":
        candidates = list(ETFS)
    elif ac == "commodity":
        candidates = list(ETPS_COMMODITIES)
    elif ac == "crypto":
        candidates = list(ETPS_CRYPTO)
    elif ac == "leveraged":
        candidates = list(LEVERAGED_ETPS)
    elif ac == "all":
        candidates = (
            _stock_pool_for(tier)
            + list(ETFS)
            + list(ETPS_COMMODITIES)
            + list(ETPS_CRYPTO)
        )
    else:  # 'stock' (o desconocido)
        candidates = _stock_pool_for(tier)

    # Dedupe conservando orden (preserva la jerarquía de la combinación).
    seen: set[str] = set()
    unique: list[str] = []
    for sym in candidates:
        if sym not in seen:
            seen.add(sym)
            unique.append(sym)
    return unique
