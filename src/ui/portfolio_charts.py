"""Gráficos de evolución del patrimonio de la cartera completa.

Este módulo expone:
  - ``compute_portfolio_value_series``: función pura (sin Streamlit) que
    reconstruye la serie temporal del patrimonio total de una cartera
    (posiciones + cash) sobre un periodo dado.
  - ``build_portfolio_pnl_figure``: construye una figura Plotly con el
    patrimonio total + coste base (capital invertido neto).
  - ``render_portfolio_pnl_chart``: wrapper Streamlit con selector de
    timeline (1D, 5D, 1M, 3M, 6M, YTD, 1A, 5A, MAX) y métricas resumen.

Estrategia:
  Para cada fecha del rango pedido reconstruimos las posiciones a partir
  del histórico de transacciones (BUY suma, SELL resta) y multiplicamos
  por el precio de cierre histórico bajado de yfinance. El cash a esa
  fecha es ``initial_cash - acum(BUY) + acum(SELL)``.

Sin dependencias nuevas: pandas, yfinance y plotly ya están en el stack.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from src.services import portfolio as portfolio_svc  # noqa: F401  (uso futuro)
from src.services import portfolios as portfolios_svc
from src.services.db import get_conn
from src.ui.components import (
    COLOR_ACCENT,
    COLOR_ACCENT_2,
    COLOR_DOWN,
    COLOR_MUTED,
    COLOR_NEUTRAL,
    COLOR_UP,
    fmt_money,
    fmt_pct,
)


# Timelines soportados y su mapeo a periodos / intervalos de yfinance.
# Para 1D usamos intradía (intervalo 5m) para obtener una curva con detalle;
# YTD se calcula con start=1-enero-año-actual porque yfinance no tiene "ytd"
# nativo. El resto van directo al parámetro ``period``.
TIMELINES: dict[str, dict] = {
    "1D": {"period": "1d", "interval": "5m"},
    "5D": {"period": "5d", "interval": "30m"},
    "1M": {"period": "1mo", "interval": "1d"},
    "3M": {"period": "3mo", "interval": "1d"},
    "6M": {"period": "6mo", "interval": "1d"},
    "YTD": {"period": "ytd", "interval": "1d"},
    "1A": {"period": "1y", "interval": "1d"},
    "5A": {"period": "5y", "interval": "1wk"},
    "MAX": {"period": "max", "interval": "1mo"},
}


def _get_transactions(portfolio_id: int) -> list[dict]:
    """Lee TODAS las transacciones de la cartera ordenadas por fecha asc."""
    pid = int(portfolio_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT ticker, side, qty, price, ts FROM transactions "
            "WHERE portfolio_id = ? ORDER BY ts ASC, id ASC",
            (pid,),
        )
        rows = cur.fetchall()
    return [
        {
            "ticker": r["ticker"],
            "side": r["side"],
            "qty": float(r["qty"]) if r["qty"] is not None else 0.0,
            "price": float(r["price"]) if r["price"] is not None else 0.0,
            "ts": r["ts"],
        }
        for r in rows
    ]


def _resolve_period(timeline: str) -> tuple[str | None, str | None, str]:
    """Convierte el timeline lógico al (period, start, interval) de yfinance.

    Si timeline == "YTD" devolvemos (None, "YYYY-01-01", interval) para que
    yf.download use ``start`` en vez de ``period``.
    """
    if timeline not in TIMELINES:
        timeline = "1M"
    cfg = TIMELINES[timeline]
    interval = cfg["interval"]
    if cfg["period"] == "ytd":
        year = datetime.now(timezone.utc).year
        return None, f"{year}-01-01", interval
    return cfg["period"], None, interval


def _download_closes(
    tickers: Iterable[str], period: str | None, start: str | None, interval: str
) -> pd.DataFrame:
    """Descarga precios de cierre históricos para una lista de tickers.

    Devuelve un DataFrame con índice DatetimeIndex y una columna por ticker.
    Si yfinance falla o no devuelve datos, devuelve DataFrame vacío.
    """
    tickers = list(tickers)
    if not tickers:
        return pd.DataFrame()
    try:
        kwargs = {
            "tickers": tickers,
            "interval": interval,
            "auto_adjust": False,
            "progress": False,
            "group_by": "ticker",
            "threads": True,
        }
        if period is not None:
            kwargs["period"] = period
        if start is not None:
            kwargs["start"] = start
        data = yf.download(**kwargs)
    except Exception:
        return pd.DataFrame()

    if data is None or data.empty:
        return pd.DataFrame()

    # yfinance devuelve estructura distinta según 1 vs N tickers. Normalizamos:
    closes = pd.DataFrame()
    if len(tickers) == 1:
        # MultiIndex con un solo ticker o columnas planas.
        col_close = None
        if isinstance(data.columns, pd.MultiIndex):
            try:
                col_close = data[(tickers[0], "Close")]
            except Exception:
                col_close = None
        if col_close is None and "Close" in data.columns:
            col_close = data["Close"]
        if col_close is not None:
            closes[tickers[0]] = col_close
    else:
        for t in tickers:
            try:
                closes[t] = data[t]["Close"]
            except Exception:
                # Ticker que yfinance no supo resolver: lo dejamos fuera.
                continue

    # Eliminamos zona horaria para poder comparar con timestamps "naive".
    if not closes.empty:
        try:
            closes.index = closes.index.tz_localize(None)
        except (AttributeError, TypeError):
            pass
    return closes.sort_index()


def _build_holdings_timeline(
    transactions: list[dict], dates: pd.DatetimeIndex
) -> tuple[pd.DataFrame, pd.Series]:
    """Reconstruye, para cada fecha del índice, las qty por ticker y el cash neto.

    - ``holdings``: DataFrame [fechas x tickers] con qty acumulada en cada fecha.
    - ``cash_flow``: Serie alineada al índice con ``-acumBuy + acumSell`` (lo
      que falta sumar al ``initial_cash`` para tener el cash a cada fecha).

    Las transacciones se aplican en orden cronológico: una transacción cuyo
    timestamp <= fecha t cuenta en el snapshot de t.
    """
    if not transactions:
        return pd.DataFrame(index=dates), pd.Series(0.0, index=dates)

    # Pasamos timestamps a datetime naive (sin tz) para poder comparar con el
    # índice descargado de yfinance (que tampoco tiene tz tras tz_localize).
    txs = []
    for t in transactions:
        try:
            ts = pd.to_datetime(t["ts"])
        except Exception:
            continue
        # Si tiene tz, la quitamos (convertimos a UTC y luego strip); si ya
        # es naive, lo dejamos tal cual.
        try:
            if getattr(ts, "tzinfo", None) is not None:
                ts = ts.tz_convert("UTC").tz_localize(None)
        except Exception:
            pass
        txs.append({**t, "_ts": ts})
    txs.sort(key=lambda x: x["_ts"])

    tickers = sorted({t["ticker"] for t in txs})
    holdings = pd.DataFrame(0.0, index=dates, columns=tickers)
    cash_flow = pd.Series(0.0, index=dates)

    # Para cada ticker, vamos acumulando qty a medida que avanzan las fechas.
    # Usamos un puntero que avanza por la lista ordenada de transacciones
    # cuando la fecha del índice supera el timestamp de la siguiente tx.
    qty_running: dict[str, float] = {t: 0.0 for t in tickers}
    cash_running = 0.0
    idx_tx = 0
    n = len(txs)
    for date in dates:
        # Aplicamos todas las txs cuyo ts <= date.
        while idx_tx < n and txs[idx_tx]["_ts"] <= date:
            tx = txs[idx_tx]
            sign = 1.0 if tx["side"] == "BUY" else -1.0
            qty_running[tx["ticker"]] = qty_running.get(tx["ticker"], 0.0) + sign * tx["qty"]
            # cash_flow: BUY resta, SELL suma.
            cash_running += -sign * tx["qty"] * tx["price"]
            idx_tx += 1
        for t in tickers:
            holdings.at[date, t] = qty_running.get(t, 0.0)
        cash_flow.at[date] = cash_running
    return holdings, cash_flow


def compute_portfolio_value_series(
    portfolio_id: int, timeline: str = "1M", benchmark: str | None = None,
) -> pd.DataFrame:
    """Calcula la serie temporal del patrimonio total de la cartera.

    Devuelve un DataFrame con columnas:
      - ``total_value``: valor total (posiciones a precio de mercado + cash).
      - ``cost_basis``: capital invertido neto a esa fecha (initial_cash - cash).
      - ``cash``: cash disponible a esa fecha.
      - ``positions_value``: solo el valor de las posiciones.
      - ``pnl``: total_value - initial_cash (P&L absoluto desde el inicio).
      - ``benchmark_value`` (opcional): valor simulado de invertir el initial_cash
        en el ticker de benchmark al inicio del periodo, mantenido hasta el final.
        Permite comparar visualmente alpha vs SPY/QQQ.

    Si no hay transacciones todavía, devuelve DataFrame vacío.
    Si yfinance falla para todos los tickers, devuelve DataFrame vacío.
    """
    pid = int(portfolio_id)
    p = portfolios_svc.get_portfolio(pid)
    if p is None:
        return pd.DataFrame()

    txs = _get_transactions(pid)
    if not txs:
        return pd.DataFrame()

    period, start, interval = _resolve_period(timeline)
    tickers_universe = sorted({t["ticker"] for t in txs})
    closes = _download_closes(tickers_universe, period, start, interval)
    if closes.empty:
        return pd.DataFrame()

    # Reconstruimos qty por ticker en cada timestamp del índice descargado.
    holdings, cash_flow = _build_holdings_timeline(txs, closes.index)

    # Alineamos: solo multiplicamos columnas presentes en ambos.
    common = [c for c in holdings.columns if c in closes.columns]
    if not common:
        # Si yfinance no nos dio precios de NINGÚN ticker, no podemos graficar.
        return pd.DataFrame()
    positions_value = (holdings[common] * closes[common]).sum(axis=1)
    # Forward-fill por si yfinance dejó huecos puntuales.
    positions_value = positions_value.ffill().fillna(0.0)

    initial_cash = float(p["initial_cash"])
    cash = initial_cash + cash_flow
    total_value = positions_value + cash
    cost_basis = initial_cash - cash  # Capital neto invertido (BUY - SELL acumulado)
    pnl = total_value - initial_cash

    df = pd.DataFrame(
        {
            "total_value": total_value,
            "positions_value": positions_value,
            "cash": cash,
            "cost_basis": cost_basis,
            "pnl": pnl,
        }
    )

    # Benchmark simulado: si el usuario hubiera puesto initial_cash en SPY/QQQ
    # al primer timestamp y mantenido hasta cada timestamp posterior, ¿cuánto
    # tendría? -> initial_cash * (precio_t / precio_t0).
    if benchmark:
        try:
            bench_closes = _download_closes([benchmark], period, start, interval)
            if not bench_closes.empty and benchmark in bench_closes.columns:
                bs = bench_closes[benchmark].ffill()
                # Alineamos con el índice de la serie principal.
                bs = bs.reindex(df.index, method="ffill")
                base = float(bs.iloc[0]) if len(bs) and bs.iloc[0] else None
                if base:
                    df["benchmark_value"] = initial_cash * (bs / base)
                    df["benchmark_ticker"] = benchmark
        except Exception:
            # Cualquier fallo del benchmark no debe romper la serie principal.
            pass

    return df.dropna(how="all")


@st.cache_data(ttl=300, show_spinner=False)
def _compute_series_cached(
    portfolio_id: int, timeline: str, benchmark: str | None = None,
) -> pd.DataFrame:
    """Versión cacheada (5 min) de la serie. El cache key es (pid, timeline, benchmark)."""
    return compute_portfolio_value_series(portfolio_id, timeline, benchmark=benchmark)


def build_portfolio_pnl_figure(df: pd.DataFrame, currency: str = "USD") -> go.Figure:
    """Construye la figura Plotly con patrimonio total y coste base.

    El color de la línea principal va en verde si el P&L final es positivo,
    rojo si es negativo (mismo criterio semántico que el resto de la UI).
    """
    if df is None or df.empty:
        return go.Figure()

    pnl_final = float(df["pnl"].iloc[-1]) if "pnl" in df else 0.0
    line_color = COLOR_UP if pnl_final >= 0 else COLOR_DOWN

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["total_value"],
            mode="lines",
            name="Patrimonio total",
            line=dict(color=line_color, width=2.5),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Patrimonio: %{y:,.2f}<extra></extra>",
        )
    )
    if "cost_basis" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["cost_basis"],
                mode="lines",
                name="Coste base (capital invertido)",
                line=dict(color=COLOR_NEUTRAL, width=1.5, dash="dot"),
                hovertemplate="%{x|%Y-%m-%d}<br>Coste base: %{y:,.2f}<extra></extra>",
            )
        )
    if "benchmark_value" in df.columns:
        bench_label = df.get("benchmark_ticker", pd.Series(["Benchmark"])).iloc[0]
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["benchmark_value"],
                mode="lines",
                name=f"Benchmark {bench_label}",
                line=dict(color=COLOR_ACCENT, width=1.8, dash="dash"),
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{bench_label}: %{{y:,.2f}}<extra></extra>",
            )
        )
    from src.ui.components import COLOR_BG, COLOR_BORDER, COLOR_MUTED, COLOR_TEXT
    fig.update_layout(
        title=dict(text=f"Evolución del patrimonio ({currency})", font=dict(color=COLOR_TEXT, size=15)),
        xaxis_title="Fecha",
        yaxis_title=f"Valor ({currency})",
        template="plotly_dark",
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        font=dict(family="Inter, system-ui, sans-serif", color=COLOR_TEXT, size=12),
        margin=dict(l=12, r=12, t=44, b=12),
        xaxis=dict(showgrid=False, linecolor=COLOR_BORDER, tickcolor=COLOR_BORDER, color=COLOR_MUTED),
        yaxis=dict(gridcolor=COLOR_BORDER, zerolinecolor=COLOR_BORDER, linecolor=COLOR_BORDER, color=COLOR_MUTED),
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=COLOR_MUTED)),
    )
    return fig


def _summary_metrics(df: pd.DataFrame) -> dict:
    """Calcula métricas resumen del periodo: P&L, %, drawdown y extremos."""
    if df is None or df.empty:
        return {}
    series = df["total_value"]
    start_val = float(series.iloc[0])
    end_val = float(series.iloc[-1])
    delta = end_val - start_val
    delta_pct = (delta / start_val * 100.0) if start_val else 0.0
    # Max drawdown: mayor caída desde un máximo previo. Útil como medida de
    # riesgo histórico realizado.
    running_max = series.cummax()
    dd = (series - running_max) / running_max.replace(0, pd.NA)
    max_dd = float(dd.min() * 100.0) if not dd.dropna().empty else 0.0
    return {
        "start_val": start_val,
        "end_val": end_val,
        "delta": delta,
        "delta_pct": delta_pct,
        "max_dd": max_dd,
    }


def render_portfolio_pnl_chart(portfolio_id: int) -> None:
    """Renderiza el bloque completo (selector + métricas + gráfico) en Streamlit."""
    pid = int(portfolio_id)
    p = portfolios_svc.get_portfolio(pid)
    if p is None:
        st.error(f"La cartera con id={pid} no existe.")
        return

    currency = p.get("currency", "USD")

    st.subheader("📈 Evolución del patrimonio")
    st.caption(
        "Cómo ha cambiado el valor TOTAL de tu cartera (posiciones + cash) "
        "a lo largo del tiempo."
    )

    # Selector de timeline. ``segmented_control`` está en Streamlit >=1.40;
    # si no existe, caemos a un radio horizontal con la misma UX visual.
    timelines = list(TIMELINES.keys())
    default_tl = "1M"
    state_key = f"pnl_timeline_pid_{pid}"
    if hasattr(st, "segmented_control"):
        timeline = st.segmented_control(
            "Periodo",
            options=timelines,
            default=default_tl,
            key=state_key,
        )
    else:
        timeline = st.radio(
            "Periodo",
            options=timelines,
            index=timelines.index(default_tl),
            horizontal=True,
            key=state_key,
        )
    if not timeline:
        timeline = default_tl

    # Selector de benchmark: simula invertir el initial_cash en SPY/QQQ y
    # superpone esa línea para comparar alpha (mi cartera vs índice).
    bench_options = ["Ninguno", "SPY", "QQQ"]
    bench_choice = st.selectbox(
        "Benchmark (línea comparativa)",
        options=bench_options,
        index=0,
        key=f"pnl_bench_pid_{pid}",
        help="Compara tu cartera con el ETF índice elegido (mismo capital inicial).",
    )
    benchmark = None if bench_choice == "Ninguno" else bench_choice

    # Edge case 1: cartera sin transacciones todavía.
    txs = _get_transactions(pid)
    if not txs:
        st.info("Aún no hay transacciones para graficar. Compra algo desde el chat o desde la pestaña de mercado.")
        return

    with st.spinner(f"Calculando evolución ({timeline})..."):
        try:
            df = _compute_series_cached(pid, timeline, benchmark)
        except Exception as e:
            st.warning(f"No se pudo calcular la evolución del patrimonio: {e}")
            return

    if df is None or df.empty:
        # Caso típico: yfinance se quedó sin datos para los tickers de la cartera.
        st.warning(
            "No se han podido obtener precios históricos para construir la serie. "
            "Intenta con otro periodo o vuelve a probar en unos minutos."
        )
        return

    # Métricas resumen alineadas en columnas (didáctico de un vistazo).
    # Si hay benchmark, añadimos una métrica extra con alpha (return_cartera -
    # return_benchmark): positivo = ganamos al índice, negativo = nos gana.
    m = _summary_metrics(df)
    if m:
        has_bench = "benchmark_value" in df.columns
        cols = st.columns(5 if has_bench else 4)
        cols[0].metric("Valor inicial", fmt_money(m["start_val"], currency))
        cols[1].metric(
            "Valor final",
            fmt_money(m["end_val"], currency),
            delta=fmt_pct(m["delta_pct"]),
        )
        cols[2].metric("P&L del periodo", fmt_money(m["delta"], currency))
        cols[3].metric("Max drawdown", fmt_pct(m["max_dd"], with_sign=False))
        if has_bench:
            try:
                bv0 = float(df["benchmark_value"].iloc[0])
                bv1 = float(df["benchmark_value"].iloc[-1])
                bench_pct = ((bv1 - bv0) / bv0 * 100.0) if bv0 else 0.0
                alpha_pct = m["delta_pct"] - bench_pct
                cols[4].metric(
                    "Alpha vs " + (benchmark or "?"),
                    fmt_pct(alpha_pct),
                    help="Diferencia entre el % ganado por tu cartera y el % del índice. "
                         "Positivo = bates al mercado.",
                )
            except Exception:
                pass

    fig = build_portfolio_pnl_figure(df, currency=currency)

    # Overlay sesión extendida (after-hours): si hay datos AH a nivel global,
    # extendemos la última observación con un punto/segmento punteado para que
    # se vea el "movimiento fuera de horario" del patrimonio total.
    ah_total = None
    ah_delta_pct = None
    try:
        pv = portfolio_svc.get_portfolio_value(pid)
        ah_total = pv.get("total_value_after_hours")
        ah_delta_pct = pv.get("after_hours_delta_pct")
    except Exception:
        ah_total = None
        ah_delta_pct = None

    if ah_total is not None and not df.empty:
        last_ts = df.index[-1]
        last_val = float(df["total_value"].iloc[-1])
        # Calculamos un "siguiente paso" estimado para colocar el punto AH a la
        # derecha del último timestamp del histórico. Si solo hay una muestra,
        # caemos a 1 día como aproximación razonable.
        try:
            if len(df.index) >= 2:
                step = df.index[-1] - df.index[-2]
            else:
                step = pd.Timedelta(days=1)
        except Exception:
            step = pd.Timedelta(days=1)
        ah_ts = last_ts + step

        delta_sign = (ah_delta_pct or 0.0)
        if delta_sign > 0:
            ah_color = COLOR_UP
        elif delta_sign < 0:
            ah_color = COLOR_DOWN
        else:
            ah_color = COLOR_ACCENT_2

        ah_label = "After hours"
        fig.add_trace(
            go.Scatter(
                x=[last_ts, ah_ts],
                y=[last_val, float(ah_total)],
                mode="lines+markers",
                name=ah_label,
                line=dict(color=ah_color, width=2, dash="dot"),
                marker=dict(color=ah_color, size=8, symbol="circle-open"),
                hovertemplate=(
                    f"{ah_label}<br>%{{x|%Y-%m-%d %H:%M}}<br>"
                    "Patrimonio AH: %{y:,.2f}<extra></extra>"
                ),
            )
        )
        try:
            fig.add_annotation(
                x=ah_ts,
                y=float(ah_total),
                text=f"AH {fmt_pct(ah_delta_pct) if ah_delta_pct is not None else ''}".strip(),
                showarrow=True,
                arrowhead=0,
                arrowcolor=ah_color,
                font=dict(color=ah_color, size=11),
                bgcolor="rgba(0,0,0,0)",
                xanchor="left",
                yshift=6,
            )
        except Exception:
            pass

    st.plotly_chart(fig, use_container_width=True)

    # Caption discreto bajo el chart con el valor AH global, solo si existe.
    if ah_total is not None:
        ah_pct_str = fmt_pct(ah_delta_pct) if ah_delta_pct is not None else "—"
        st.caption(
            f"Sesión extendida USA · {fmt_money(ah_total, currency)} ({ah_pct_str})"
        )
