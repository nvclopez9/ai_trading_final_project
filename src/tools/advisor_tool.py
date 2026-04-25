"""Tools de asesoría: el agente compone análisis y propuestas ejecutables.

Estas tools NO operan en el mercado: solo combinan información ya disponible
(estado de la cartera + snapshot del mercado + perfil de riesgo) para producir
una **propuesta concreta de compra/venta** que el LLM presenta al usuario y,
si éste lo aprueba, ejecuta llamando a ``portfolio_buy`` / ``portfolio_sell``
una vez por línea.

Diseño didáctico:
- ``analyze_buy_opportunities``: dado un presupuesto (USD o % del patrimonio),
  selecciona N tickers candidatos del universo del proyecto según el horizonte
  temporal y el perfil de riesgo, y reparte el dinero entre ellos. Devuelve una
  tabla razonada + un bloque PROPUESTA EJECUTABLE con qty cerrada por ticker.
- ``analyze_sell_candidates``: mira las posiciones actuales y sugiere cuáles
  vender (cortar pérdidas, tomar beneficios o reducir exposición), con qty.

La salida es siempre **string plano** (regla 5 del system prompt). El bloque
PROPUESTA EJECUTABLE va con un formato muy reconocible para que el LLM lo
mapee 1:1 a llamadas a ``portfolio_buy``/``portfolio_sell``.
"""
from __future__ import annotations

from langchain_core.tools import tool

import yfinance as yf

from src.services import portfolio
from src.services import portfolios
from src.tools.market_tools import _fetch_fallback_quotes
from src.tools.portfolio_tools import get_active_portfolio_id
from src.tools.universes import get_universe


# Mapeo perfil de riesgo -> número de picks y peso de momentum vs estabilidad.
# - conservador: pocas posiciones, premia estabilidad (cambio diario moderado, no chicharros).
# - moderado: equilibrio.
# - agresivo: más picks, premia momentum (mayores subidas recientes).
_RISK_PROFILE = {
    "conservador": {"picks": 3, "momentum_weight": 0.2, "max_change_abs": 5.0},
    "moderado":    {"picks": 4, "momentum_weight": 0.5, "max_change_abs": 10.0},
    "agresivo":    {"picks": 5, "momentum_weight": 0.9, "max_change_abs": 25.0},
}


def _score_candidate(row: dict, momentum_weight: float, horizon: str) -> float:
    """Score simple para rankear candidatos del snapshot de mercado.

    ``row`` viene de ``_fetch_fallback_quotes`` con keys ticker/price/change_pct/volume.
    - Para horizonte corto: prioriza momentum (change_pct) y volumen.
    - Para horizonte largo: penaliza overextension (cambios diarios extremos)
      y sigue dando algo de peso al volumen como proxy de liquidez.
    """
    change = float(row.get("change_pct") or 0.0)
    volume = float(row.get("volume") or 0)
    # Normalización suave del volumen (log10) para no dominar el score.
    log_vol = (volume ** 0.5) / 1000.0  # raíz cuadrada en miles, suficiente.

    if horizon == "short":
        # En corto premiamos los que más suben hoy (con peso del riesgo).
        return change * momentum_weight + log_vol * 0.1
    elif horizon == "long":
        # En largo penalizamos volatilidad extrema y damos algo a la liquidez.
        return -abs(change) * 0.3 + log_vol * 0.5 + change * (momentum_weight * 0.2)
    else:  # medium
        return change * momentum_weight * 0.6 + log_vol * 0.2


def _patrimony(portfolio_id: int) -> tuple[float, float, float]:
    """Devuelve (cash, invested_value, net_worth) de la cartera."""
    cash = portfolios.cash_available(portfolio_id)
    totals = portfolio.get_portfolio_value(portfolio_id=portfolio_id)
    invested = float(totals.get("total_value") or 0.0)
    return cash, invested, cash + invested


# Umbrales convencionales en USD para clasificación por marketCap.
_TIER_BOUNDS = {
    "small": (0, 2_000_000_000),
    "mid":   (2_000_000_000, 10_000_000_000),
    "large": (10_000_000_000, float("inf")),
}


def _fetch_quotes_for(symbols: list[str]) -> list[dict]:
    """Réplica parametrizada de ``_fetch_fallback_quotes`` para una lista
    arbitraria. Devuelve dicts con ticker/price/change_pct/volume/market_cap.

    Iteración serie: con 30-50 tickers tarda 30-90s pero es código simple
    y consistente con el patrón del resto del proyecto.
    """
    rows: list[dict] = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
            if price is None or prev is None:
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
            change_pct = (float(price) - float(prev)) / float(prev) * 100 if prev else 0.0
            volume = info.get("regularMarketVolume") or info.get("volume") or 0
            mcap = info.get("marketCap")
            rows.append({
                "ticker": sym,
                "price": float(price),
                "change_pct": float(change_pct),
                "volume": int(volume) if volume else 0,
                "market_cap": float(mcap) if isinstance(mcap, (int, float)) else None,
            })
        except Exception:
            continue
    return rows


def _filter_by_tier(rows: list[dict], tier: str) -> list[dict]:
    """Filtra por rango de market_cap según tier. Si el ticker no tiene
    market_cap conocido (ETFs, ETPs, commodities), pasa el filtro siempre
    para no excluirlo (su universo curado ya implica una clasificación).
    """
    bounds = _TIER_BOUNDS.get(tier.lower())
    if not bounds:
        return rows
    lo, hi = bounds
    out = []
    for r in rows:
        mc = r.get("market_cap")
        if mc is None:
            out.append(r)  # ETFs/ETPs no se filtran por marketCap.
            continue
        if lo <= mc < hi:
            out.append(r)
    return out


@tool
def analyze_buy_opportunities(
    pct_of_patrimony: float | None = None,
    amount_usd: float | None = None,
    horizon: str = "short",
    num_picks: int | None = None,
    market_cap_tier: str = "any",
    asset_class: str = "stock",
) -> str:
    """Análisis automatizado para sugerir COMPRAS basadas en la cartera activa,
    el snapshot del mercado y el perfil de riesgo de la cartera.

    Parámetros:
    - pct_of_patrimony: porcentaje del PATRIMONIO TOTAL (cash + posiciones) a invertir,
      en escala 0-100. Por ejemplo 50 invierte la mitad. Solo se usa si amount_usd no se pasa.
    - amount_usd: cantidad fija en USD a invertir. Tiene prioridad sobre pct_of_patrimony.
    - horizon: 'short' (días/semanas, momentum), 'medium' (meses) o 'long' (año+,
      prioriza estabilidad y liquidez). Default 'short'.
    - num_picks: número de tickers entre los que repartir. Si None, se decide
      según el riesgo de la cartera (conservador 3, moderado 4, agresivo 5).
    - market_cap_tier: 'small' (<$2B), 'mid' ($2-10B), 'large' (>$10B), 'any' (todos).
      Solo aplica a acciones; con asset_class != 'stock' el universo ya viene definido.
    - asset_class: 'stock' (default), 'etf' (índices/sectoriales/factor),
      'commodity' (oro, plata, petróleo, gas...), 'crypto' (BTC/ETH ETPs spot y futuros),
      'leveraged' (3x apalancados, alto riesgo, NO holdables long-term),
      'all' (mezcla stocks + etf + commodity + crypto, sin apalancados).

    Devuelve un análisis textual con la lógica y un bloque PROPUESTA EJECUTABLE
    con líneas formato 'COMPRAR <qty> <TICKER>' que el agente debe presentar
    al usuario. Si el usuario aprueba, el agente debe llamar a portfolio_buy
    una vez por cada línea de la propuesta. NO ejecuta órdenes esta tool."""
    try:
        pid = get_active_portfolio_id()
        p = portfolios.get_portfolio(pid)
        if p is None:
            return "❌ No hay cartera activa configurada."

        cash, invested, net_worth = _patrimony(pid)

        # Cálculo del presupuesto efectivo. Si amount_usd manda, usamos ese.
        if amount_usd is not None and amount_usd > 0:
            budget = float(amount_usd)
            budget_basis = f"importe fijo de ${budget:,.2f}"
        elif pct_of_patrimony is not None and pct_of_patrimony > 0:
            pct = max(0.0, min(100.0, float(pct_of_patrimony)))
            budget = net_worth * pct / 100.0
            budget_basis = f"{pct:.1f}% del patrimonio (${net_worth:,.2f})"
        else:
            # Default: 50% del cash disponible (no del patrimonio total) como caso seguro.
            budget = cash * 0.5
            budget_basis = "50% del efectivo disponible (default)"

        if budget <= 0:
            return (
                "❌ No hay presupuesto para invertir.\n"
                f"Efectivo disponible: ${cash:,.2f}\n"
                f"Patrimonio total: ${net_worth:,.2f}\n"
                "Sugerencia: vende alguna posición o crea una cartera nueva con más capital "
                "desde la pestaña 🧺 Mis Carteras."
            )

        # Aviso si pides más cash del que hay (la tool no bloquea, pero lo señala).
        cash_warning = ""
        if budget > cash:
            cash_warning = (
                f"\n⚠️ El presupuesto pedido (${budget:,.2f}) supera el efectivo disponible "
                f"(${cash:,.2f}). Para ejecutar la propuesta completa el usuario tendría que "
                "vender posiciones primero o reducir el importe."
            )

        # Perfil de riesgo + parámetros derivados.
        risk = (p.get("risk") or "moderado").lower()
        profile = _RISK_PROFILE.get(risk, _RISK_PROFILE["moderado"])
        picks = int(num_picks) if num_picks else profile["picks"]
        momentum_w = profile["momentum_weight"]

        # Universo: derivado de tier + asset_class. El advisor maneja varios
        # casos de uso: stocks por capitalización, ETFs, commodities, crypto y
        # apalancados. Si el universo curado es de stocks puros, también
        # podemos filtrar por marketCap real para depurar (esto puede excluir
        # algún ticker que cambió de tier desde la última curación).
        tier = (market_cap_tier or "any").strip().lower()
        ac = (asset_class or "stock").strip().lower()
        symbols = get_universe(tier=tier, asset_class=ac)
        if not symbols:
            return f"❌ No hay universo para tier='{tier}', asset_class='{ac}'."

        # Si el universo coincide con el fallback (large/any + stock), reusamos el
        # snapshot ya cacheado por la app; si no, hacemos fetch específico.
        snapshot = _fetch_quotes_for(symbols)
        if not snapshot:
            return (
                "❌ No se pudo obtener el snapshot del mercado para analizar candidatos. "
                "Reintenta en unos segundos."
            )

        # Filtro adicional por marketCap real cuando es relevante (solo stocks
        # con tier explícito small/mid/large; 'any' no filtra).
        if ac == "stock" and tier in ("small", "mid", "large"):
            snapshot = _filter_by_tier(snapshot, tier)
            if not snapshot:
                return (
                    f"❌ No quedan candidatos tras filtrar por tier='{tier}' "
                    "con datos reales de marketCap. Reintenta o cambia de tier."
                )

        # Evitamos proponer tickers que el usuario ya tenga en la cartera (para
        # diversificar). Si quiere doblar posiciones que use portfolio_buy directo.
        existing = {pos["ticker"] for pos in portfolio.get_positions(portfolio_id=pid)}
        candidates = [r for r in snapshot if r["ticker"] not in existing]

        # Filtro defensivo de overextension según riesgo (conservador no toca
        # tickers con cambio diario > 5% absoluto).
        max_change = profile["max_change_abs"]
        candidates = [r for r in candidates if abs(r.get("change_pct") or 0) <= max_change * 2]

        if not candidates:
            return (
                "❌ No hay candidatos válidos en este momento (todos los tickers del universo "
                "ya están en tu cartera o no cumplen el filtro de volatilidad)."
            )

        # Ranking por score y selección top N.
        ranked = sorted(
            candidates,
            key=lambda r: _score_candidate(r, momentum_w, horizon),
            reverse=True,
        )[:picks]

        # Reparto equiponderado del presupuesto, redondeando qty hacia abajo
        # para no pasarnos. qty entera (no fraccional) para presentar más limpio.
        per_slot = budget / len(ranked)
        proposal = []
        total_assigned = 0.0
        for r in ranked:
            price = float(r["price"])
            if price <= 0:
                continue
            qty = int(per_slot // price)
            if qty <= 0:
                # Si el ticker es demasiado caro para 1 unidad con este slot,
                # forzamos al menos 1 unidad si cabe en el presupuesto restante.
                if (budget - total_assigned) >= price:
                    qty = 1
                else:
                    continue
            cost = qty * price
            total_assigned += cost
            proposal.append({
                "ticker": r["ticker"],
                "qty": qty,
                "price": price,
                "cost": cost,
                "change_pct": r.get("change_pct"),
            })

        if not proposal:
            return (
                f"❌ El presupuesto (${budget:,.2f}) es insuficiente para comprar al menos "
                "1 unidad de cualquier candidato. Aumenta el importe o cambia el horizonte."
            )

        # Composición del texto de salida (didáctico + ejecutable).
        lines = []
        lines.append(f"📊 ANÁLISIS DE OPORTUNIDADES DE COMPRA — cartera '{p['name']}'")
        lines.append(
            f"Perfil: riesgo={risk}, mercados={p.get('markets')}, horizonte={horizon}, "
            f"tier={tier}, asset_class={ac}."
        )
        lines.append(
            f"Patrimonio: ${net_worth:,.2f} (cash ${cash:,.2f} + invertido ${invested:,.2f})."
        )
        lines.append(f"Presupuesto a desplegar: ${budget:,.2f} ({budget_basis}).")
        if ac == "leveraged":
            lines.append(
                "⚠️ ATENCIÓN: ETPs apalancados (3x bull/bear, vol). Riesgo elevado por "
                "decay diario; pensados para trading intra-día / muy corto plazo. "
                "NO son holdables a largo plazo: pueden perder valor incluso con el "
                "subyacente plano por el rebalanceo diario."
            )
        if cash_warning:
            lines.append(cash_warning.strip())
        lines.append("")
        lines.append(f"Candidatos rankeados (universo: tier={tier}, asset_class={ac}):")
        header = f"{'Ticker':<8}{'Precio':>10}{'Δ día':>10}{'Qty':>6}{'Coste':>12}"
        lines.append(header)
        lines.append("-" * len(header))
        for c in proposal:
            ch = f"{c['change_pct']:+.2f}%" if c["change_pct"] is not None else "n/d"
            lines.append(
                f"{c['ticker']:<8}{c['price']:>10.2f}{ch:>10}"
                f"{c['qty']:>6d}{c['cost']:>12.2f}"
            )
        lines.append("-" * len(header))
        lines.append(f"Coste total estimado: ${total_assigned:,.2f}")
        residual = budget - total_assigned
        if residual > 1:
            lines.append(f"Residual sin asignar: ${residual:,.2f} (no llega para 1 unidad más).")
        lines.append("")
        # Bloque marcado para que el LLM lo lea como instrucciones a ejecutar.
        lines.append("PROPUESTA EJECUTABLE (compras a ejecutar 1:1 con portfolio_buy):")
        for c in proposal:
            lines.append(f"- COMPRAR {c['qty']} {c['ticker']}  (≈ ${c['cost']:,.2f} a ${c['price']:.2f})")
        lines.append("")
        lines.append(
            "Esto es una recomendación cuantitativa simple basada en momentum + perfil de riesgo. "
            "No es asesoramiento financiero profesional."
        )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error en analyze_buy_opportunities: {e}"


@tool
def analyze_sell_candidates(
    target: str = "auto",
    pct_of_invested: float | None = None,
    num_picks: int | None = None,
) -> str:
    """Análisis automatizado para sugerir VENTAS basadas en las posiciones actuales
    de la cartera activa, su P&L y el perfil de riesgo.

    Parámetros:
    - target: criterio para elegir candidatos.
        - 'losers'         : peor P&L% (cortar pérdidas).
        - 'gainers'        : mejor P&L% (tomar beneficios).
        - 'underperformers': peor P&L% pero solo si está negativo.
        - 'reduce_exposure': vender mitad de las posiciones más grandes por valor.
        - 'auto' (default) : decide según riesgo (conservador→losers; agresivo→gainers; moderado→mixto).
    - pct_of_invested: si se pasa, se usa como cuota a liquidar en USD (% del valor invertido).
    - num_picks: número de posiciones a sugerir vender. Default según riesgo.

    Devuelve análisis + bloque PROPUESTA EJECUTABLE con líneas
    'VENDER <qty> <TICKER>' que el agente mapea 1:1 a portfolio_sell."""
    try:
        pid = get_active_portfolio_id()
        p = portfolios.get_portfolio(pid)
        if p is None:
            return "❌ No hay cartera activa configurada."

        positions = portfolio.get_positions(portfolio_id=pid)
        if not positions:
            return f"La cartera '{p['name']}' no tiene posiciones abiertas; no hay nada que vender."

        risk = (p.get("risk") or "moderado").lower()
        profile = _RISK_PROFILE.get(risk, _RISK_PROFILE["moderado"])
        picks = int(num_picks) if num_picks else min(profile["picks"], len(positions))

        # Resolver target='auto' según perfil de riesgo.
        chosen_target = target.strip().lower()
        if chosen_target == "auto":
            chosen_target = {
                "conservador": "losers",
                "moderado": "underperformers",
                "agresivo": "gainers",
            }.get(risk, "underperformers")

        # Filtrado / ordenado.
        usable = [pos for pos in positions if pos.get("pnl_pct") is not None]
        if not usable:
            return (
                "❌ Ninguna posición tiene precio actual para calcular P&L. "
                "Reintenta cuando los datos de mercado estén disponibles."
            )

        if chosen_target == "losers":
            ranked = sorted(usable, key=lambda x: x["pnl_pct"])
        elif chosen_target == "gainers":
            ranked = sorted(usable, key=lambda x: x["pnl_pct"], reverse=True)
        elif chosen_target == "underperformers":
            ranked = sorted(
                [pos for pos in usable if (pos["pnl_pct"] or 0) < 0],
                key=lambda x: x["pnl_pct"],
            )
            if not ranked:
                return (
                    f"📊 No hay posiciones en pérdidas en la cartera '{p['name']}'. "
                    "Si quieres tomar beneficios, llama de nuevo con target='gainers'."
                )
        elif chosen_target == "reduce_exposure":
            ranked = sorted(
                usable,
                key=lambda x: (x.get("market_value") or 0),
                reverse=True,
            )
        else:
            return (
                f"❌ target '{target}' no reconocido. "
                "Usa: losers, gainers, underperformers, reduce_exposure, auto."
            )

        chosen = ranked[:picks]

        # Decidir cantidad por candidato.
        # - reduce_exposure -> vender 50% de cada posición.
        # - losers/underperformers -> vender el 100% (cortar pérdidas).
        # - gainers -> vender 50% (deja correr la mitad).
        # - si pct_of_invested se pasa, repartimos ese USD entre los picks.
        proposal = []
        total_proceeds = 0.0
        invested_total = sum((pos.get("market_value") or 0.0) for pos in usable)

        if pct_of_invested is not None and pct_of_invested > 0:
            target_usd = invested_total * float(pct_of_invested) / 100.0
            per_slot = target_usd / len(chosen)
            for pos in chosen:
                price = float(pos.get("current_price") or 0)
                if price <= 0:
                    continue
                qty_to_sell = min(int(per_slot // price), int(pos["qty"]))
                if qty_to_sell <= 0:
                    qty_to_sell = 1 if pos["qty"] >= 1 else 0
                if qty_to_sell <= 0:
                    continue
                proceeds = qty_to_sell * price
                total_proceeds += proceeds
                proposal.append((pos, qty_to_sell, price, proceeds))
        else:
            for pos in chosen:
                price = float(pos.get("current_price") or 0)
                if price <= 0:
                    continue
                if chosen_target in ("losers", "underperformers"):
                    fraction = 1.0
                elif chosen_target == "gainers":
                    fraction = 0.5
                elif chosen_target == "reduce_exposure":
                    fraction = 0.5
                else:
                    fraction = 1.0
                qty_to_sell = int(pos["qty"] * fraction)
                if qty_to_sell <= 0 and pos["qty"] >= 1:
                    qty_to_sell = 1
                if qty_to_sell <= 0:
                    continue
                proceeds = qty_to_sell * price
                total_proceeds += proceeds
                proposal.append((pos, qty_to_sell, price, proceeds))

        if not proposal:
            return "❌ No se pudo construir una propuesta de venta con los parámetros dados."

        # Salida.
        lines = []
        lines.append(f"📊 ANÁLISIS DE CANDIDATOS A VENTA — cartera '{p['name']}'")
        lines.append(f"Perfil: riesgo={risk}, target={chosen_target}.")
        lines.append(f"Valor invertido total: ${invested_total:,.2f}.")
        lines.append("")
        lines.append("Posiciones seleccionadas:")
        header = f"{'Ticker':<8}{'Qty pos':>10}{'Avg':>10}{'Actual':>10}{'P&L %':>10}{'Vender':>8}{'Ingreso':>12}"
        lines.append(header)
        lines.append("-" * len(header))
        for pos, qty_sell, price, proceeds in proposal:
            pnl_pct = pos.get("pnl_pct")
            pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "n/d"
            lines.append(
                f"{pos['ticker']:<8}{pos['qty']:>10.2f}{pos['avg_price']:>10.2f}"
                f"{price:>10.2f}{pnl_str:>10}{qty_sell:>8d}{proceeds:>12.2f}"
            )
        lines.append("-" * len(header))
        lines.append(f"Ingreso total estimado: ${total_proceeds:,.2f}")
        lines.append("")
        lines.append("PROPUESTA EJECUTABLE (ventas a ejecutar 1:1 con portfolio_sell):")
        for pos, qty_sell, price, proceeds in proposal:
            lines.append(f"- VENDER {qty_sell} {pos['ticker']}  (≈ ${proceeds:,.2f} a ${price:.2f})")
        lines.append("")
        lines.append(
            "Recomendación cuantitativa basada en P&L y perfil de riesgo. "
            "No es asesoramiento financiero profesional."
        )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error en analyze_sell_candidates: {e}"
