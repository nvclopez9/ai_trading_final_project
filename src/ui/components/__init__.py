"""Sistema de diseño de la app: paleta, formateo y componentes HTML.

Inspiración visual: Linear / Robinhood / Bloomberg dark.

Cómo se usa:
- Cada página llama ``inject_app_styles()`` UNA VEZ tras ``set_page_config``.
- Para los bloques visuales se usan los helpers que devuelven HTML
  (``hero``, ``stat_strip``, ``holding_card``, ``news_card``,
  ``trade_row``, ``empty_state``) y se pintan con ``st.markdown(html,
  unsafe_allow_html=True)``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import streamlit as st


# ─── Paleta ─────────────────────────────────────────────────────────────────
COLOR_BG = "#0B0F1A"
COLOR_SURFACE = "#141925"
COLOR_SURFACE_2 = "#1B2230"
COLOR_BORDER = "#252D3D"
COLOR_BORDER_STRONG = "#374151"
COLOR_TEXT = "#F5F7FA"
COLOR_MUTED = "#9AA3B2"
COLOR_DIM = "#5E6675"
COLOR_ACCENT = "#3B82F6"
COLOR_ACCENT_2 = "#60A5FA"
COLOR_UP = "#10B981"
COLOR_DOWN = "#EF4444"
COLOR_NEUTRAL = "#6B7280"
COLOR_WARNING = "#F59E0B"


_MONO = (
    "'JetBrains Mono','SF Mono','Menlo','Roboto Mono',"
    "'Consolas','Liberation Mono',monospace"
)
_SANS = (
    "'Inter','SF Pro Text','-apple-system','Segoe UI',"
    "'Helvetica Neue',Arial,sans-serif"
)


# ─── Formato es_ES ──────────────────────────────────────────────────────────
def _to_es_number(x: float, decimals: int = 2) -> str:
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_money(x: float | None, currency: str = "USD") -> str:
    if x is None:
        return "—"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency)
    return f"{_to_es_number(x)} {symbol}"


def fmt_pct(x: float | None, with_sign: bool = True) -> str:
    if x is None:
        return "—"
    sign = "+" if with_sign and x >= 0 else ("-" if x < 0 else "")
    return f"{sign}{_to_es_number(abs(x))}%"


def fmt_qty(x: float | None) -> str:
    if x is None:
        return "—"
    if x == int(x):
        return _to_es_number(x, decimals=0)
    return _to_es_number(x, decimals=4)


def fmt_market_cap(x: float | None) -> str:
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
    if x is None:
        return COLOR_NEUTRAL
    if x > 0:
        return COLOR_UP
    if x < 0:
        return COLOR_DOWN
    return COLOR_NEUTRAL


def fmt_relative_time(ts: str | datetime | None) -> str:
    """Devuelve "hace 5 min", "hace 2 h", "ayer", o fecha si más antiguo."""
    if ts is None:
        return ""
    try:
        dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "ahora"
        if secs < 3600:
            return f"hace {secs // 60} min"
        if secs < 86400:
            return f"hace {secs // 3600} h"
        if secs < 172800:
            return "ayer"
        if secs < 604800:
            return f"hace {secs // 86400} días"
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(ts)[:10]


# ─── Helpers HTML ───────────────────────────────────────────────────────────
def delta_badge(x: float | None, big: bool = False) -> str:
    color = color_for_delta(x)
    label = fmt_pct(x)
    fz = "14px" if big else "12px"
    pad = "4px 10px" if big else "3px 9px"
    return (
        f"<span style='display:inline-block;padding:{pad};border-radius:6px;"
        f"font-family:{_MONO};font-size:{fz};font-weight:600;"
        f"color:{color};background:{color}1F;border:1px solid {color}40;'>"
        f"{label}</span>"
    )


def side_badge(side: str) -> str:
    side = side.upper()
    color = COLOR_UP if side == "BUY" else COLOR_DOWN
    return (
        f"<span style='display:inline-block;padding:2px 8px;border-radius:4px;"
        f"font-family:{_MONO};font-size:11px;font-weight:700;letter-spacing:0.06em;"
        f"color:{color};background:{color}1A;border:1px solid {color}33;'>{side}</span>"
    )


def hero(title: str, subtitle: str, badge_html: str | None = None) -> None:
    """Encabezado de página: título grande + subtítulo + opcional badge."""
    badge_block = f"<div style='margin-top:16px;'>{badge_html}</div>" if badge_html else ""
    st.markdown(
        f"""
        <div style="margin: 18px 0 32px 0;">
          <h1 style="margin:0;font-size:2.1rem;font-weight:700;
                     letter-spacing:-0.024em;color:{COLOR_TEXT};line-height:1.15;">
            {title}
          </h1>
          <p style="margin:10px 0 0 0;color:{COLOR_MUTED};font-size:15px;
                    max-width:780px;line-height:1.6;">
            {subtitle}
          </p>
          {badge_block}
        </div>
        """,
        unsafe_allow_html=True,
    )


_NAV_PAGES: list[tuple[str, str]] = [
    ("Inicio", "app.py"),
    ("Chat", "pages/1_Chat.py"),
    ("Cartera", "pages/2_Mi_Cartera.py"),
    ("Carteras", "pages/3_Mis_Carteras.py"),
    ("Mercado", "pages/4_Mercado.py"),
    ("Top", "pages/5_Top_del_Dia.py"),
    ("Noticias", "pages/6_Noticias.py"),
    ("Ayuda", "pages/7_Ayuda.py"),
]


def render_topbar(active: str | None = None) -> None:
    """Top nav horizontal estilo pelositracker.

    El sidebar nativo se oculta por CSS (ver ``inject_app_styles``); este
    helper se llama al inicio de cada página para mostrar la barra de
    navegación. ``active`` es la etiqueta que debe resaltarse (p. ej.
    ``"Inicio"``); si es ``None`` no se marca ninguna.

    La topbar se envuelve en un ``<div class='topbar-wrapper'>`` para que el
    CSS la haga ``position: sticky`` arriba con su propio fondo y borde.
    """
    # Apertura del wrapper sticky.
    st.markdown("<div class='topbar-wrapper'>", unsafe_allow_html=True)
    cols = st.columns([1.6] + [1] * len(_NAV_PAGES))
    with cols[0]:
        st.markdown(
            f"<div class='topbar-brand'>"
            f"<span style='font-size:18px;'>📈</span>"
            f"<span style='font-weight:700;letter-spacing:-0.015em;font-size:15px;"
            f"color:{COLOR_TEXT};'>Bot de Inversiones</span></div>",
            unsafe_allow_html=True,
        )
    for col, (label, path) in zip(cols[1:], _NAV_PAGES):
        with col:
            if label == active:
                # Píldora "activa" — botón deshabilitado con look de seleccionado.
                st.markdown(
                    f"<div class='nav-pill nav-pill-active'>{label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(path, label=label)
    # Cierre del wrapper sticky.
    st.markdown("</div>", unsafe_allow_html=True)


def llm_badge(provider_label: str, model: str) -> str:
    return (
        f"<div class='hero-badge'>"
        f"<span class='dot'></span>LLM activo "
        f"<span style='color:{COLOR_TEXT};font-weight:600;'>{provider_label}</span>"
        f"<span style='color:{COLOR_DIM};'>·</span>"
        f"<code style='background:transparent;padding:0;border:none;color:{COLOR_TEXT};'>{model}</code>"
        f"</div>"
    )


def stat_tile(label: str, value: str, delta: float | None = None, hint: str | None = None) -> str:
    """HTML de un tile de estadística (KPI grande con label en mayúsculas pequeñas)."""
    delta_html = ""
    if delta is not None:
        delta_html = f"<div style='margin-top:8px;'>{delta_badge(delta)}</div>"
    hint_html = ""
    if hint:
        hint_html = (
            f"<div style='color:{COLOR_DIM};font-size:11px;margin-top:6px;'>{hint}</div>"
        )
    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
        f"border-radius:14px;padding:20px 22px;height:100%;min-height:108px;"
        f"box-sizing:border-box;display:flex;flex-direction:column;justify-content:flex-start;'>"
        f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.1em;"
        f"color:{COLOR_MUTED};font-weight:500;margin-bottom:12px;'>{label}</div>"
        f"<div style='font-family:{_MONO};font-size:1.7rem;font-weight:600;"
        f"color:{COLOR_TEXT};letter-spacing:-0.01em;line-height:1.15;'>{value}</div>"
        f"{delta_html}{hint_html}"
        f"</div>"
    )


def stat_strip(tiles: Iterable[str]) -> None:
    """Pinta una fila horizontal de stat_tile, con margen vertical propio
    para que la franja de KPIs respire por encima y por debajo."""
    tiles = list(tiles)
    if not tiles:
        return
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    cols = st.columns(len(tiles), gap="small")
    for col, html in zip(cols, tiles):
        col.markdown(html, unsafe_allow_html=True)
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)


def section_eyebrow(label: str) -> str:
    return (
        f"<div class='section-eyebrow'>{label}</div>"
    )


def section_title(title: str, subtitle: str | None = None, action_html: str | None = None) -> None:
    sub = (
        f"<p style='margin:6px 0 0 0;color:{COLOR_MUTED};font-size:13px;line-height:1.5;'>{subtitle}</p>"
        if subtitle else ""
    )
    action = f"<div>{action_html}</div>" if action_html else ""
    st.markdown(
        f"""
        <div style='display:flex;justify-content:space-between;align-items:flex-end;
                    margin:36px 0 18px 0;gap:16px;'>
          <div>
            <h2 style='margin:0;font-weight:600;letter-spacing:-0.018em;line-height:1.2;'>{title}</h2>
            {sub}
          </div>
          {action}
        </div>
        """,
        unsafe_allow_html=True,
    )


def holding_card(ticker: str, qty: float, value: float | None,
                 pnl_pct: float | None, currency: str = "USD",
                 avg_price: float | None = None,
                 after_hours_price: float | None = None,
                 after_hours_change_pct: float | None = None) -> str:
    val_str = fmt_money(value, currency) if value is not None else "—"
    avg_html = (
        f"<div style='color:{COLOR_DIM};font-size:11px;margin-top:4px;font-family:{_MONO};'>"
        f"avg {fmt_money(avg_price, currency)}</div>"
    ) if avg_price is not None else ""
    ah_html = ""
    if after_hours_price is not None:
        ah_color = color_for_delta(after_hours_change_pct)
        sign = "+" if (after_hours_change_pct or 0) >= 0 else ""
        ah_pct_str = (
            f"{sign}{after_hours_change_pct:.2f}%"
            if after_hours_change_pct is not None else ""
        )
        ah_html = (
            f"<div style='display:flex;align-items:center;gap:6px;margin-top:6px;"
            f"font-family:{_MONO};font-size:11px;'>"
            f"<span style='color:{COLOR_MUTED};letter-spacing:0.06em;text-transform:uppercase;'>AH</span>"
            f"<span style='color:{COLOR_TEXT};'>{fmt_money(after_hours_price, currency)}</span>"
            f"<span style='color:{ah_color};font-weight:600;'>{ah_pct_str}</span>"
            f"</div>"
        )
    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
        f"border-radius:14px;padding:18px 18px 20px;display:flex;flex-direction:column;gap:4px;"
        f"transition:border-color 140ms ease;height:100%;min-height:152px;box-sizing:border-box;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:8px;'>"
        f"<div style='min-width:0;'>"
        f"<div style='font-family:{_MONO};font-weight:700;letter-spacing:0.4px;"
        f"font-size:1rem;color:{COLOR_TEXT};'>{ticker}</div>"
        f"<div style='color:{COLOR_MUTED};font-size:12px;margin-top:3px;'>{fmt_qty(qty)} uds</div>"
        f"</div>"
        f"{delta_badge(pnl_pct)}"
        f"</div>"
        f"<div style='font-family:{_MONO};font-size:1.25rem;font-weight:600;color:{COLOR_TEXT};margin-top:10px;'>"
        f"{val_str}</div>"
        f"{avg_html}{ah_html}"
        f"</div>"
    )


def market_row(ticker: str, price: float | None, change_pct: float | None,
               volume: float | None = None) -> str:
    pct = change_pct if change_pct is not None else 0.0
    color = COLOR_UP if pct >= 0 else COLOR_DOWN
    sign = "+" if pct >= 0 else ""
    pct_html = f"<span style='color:{color};font-weight:600;'>{sign}{pct:.2f}%</span>"
    price_html = (
        f"<span style='font-family:{_MONO};color:{COLOR_MUTED};'>{price:.2f}</span>"
        if price is not None else ""
    )
    vol_html = (
        f"<span style='font-family:{_MONO};color:{COLOR_DIM};font-size:12px;'>"
        f"{(volume / 1e6 if volume else 0):.1f} M</span>"
        if volume is not None else ""
    )
    return (
        f"<div class='ticker-row'>"
        f"<span class='sym'>{ticker}</span>"
        f"<div style='display:flex;gap:14px;align-items:center;'>"
        f"{vol_html}{price_html}{pct_html}"
        f"</div>"
        f"</div>"
    )


def trade_row(ts: str, ticker: str, side: str, qty: float, price: float,
              currency: str = "USD") -> str:
    rel = fmt_relative_time(ts)
    total = qty * price
    return (
        f"<div class='ticker-row'>"
        f"<div style='display:flex;gap:12px;align-items:center;'>"
        f"{side_badge(side)}"
        f"<span class='sym'>{ticker}</span>"
        f"<span class='meta'>{fmt_qty(qty)} × {fmt_money(price, currency)}</span>"
        f"</div>"
        f"<div style='display:flex;gap:14px;align-items:center;'>"
        f"<span style='font-family:{_MONO};color:{COLOR_TEXT};'>{fmt_money(total, currency)}</span>"
        f"<span class='meta' style='min-width:90px;text-align:right;'>{rel}</span>"
        f"</div>"
        f"</div>"
    )


def news_card(title: str, source: str, ts: str | None,
              ticker: str | None = None, url: str | None = None) -> str:
    rel = fmt_relative_time(ts) if ts else ""
    ticker_pill = ""
    if ticker:
        ticker_pill = (
            f"<span style='font-family:{_MONO};font-size:11px;font-weight:700;"
            f"color:{COLOR_ACCENT};background:{COLOR_ACCENT}1A;border:1px solid {COLOR_ACCENT}40;"
            f"padding:2px 8px;border-radius:4px;'>{ticker}</span>"
        )
    headline = (
        f"<a href='{url}' target='_blank' rel='noopener' "
        f"style='color:{COLOR_TEXT};text-decoration:none;font-weight:600;font-size:15px;line-height:1.4;'>"
        f"{title}</a>"
    ) if url else (
        f"<div style='color:{COLOR_TEXT};font-weight:600;font-size:15px;line-height:1.4;'>{title}</div>"
    )
    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
        f"border-radius:12px;padding:18px 20px;display:flex;flex-direction:column;gap:12px;"
        f"height:100%;min-height:124px;box-sizing:border-box;'>"
        f"<div style='display:flex;gap:8px;align-items:center;justify-content:space-between;'>"
        f"<div style='display:flex;gap:8px;align-items:center;'>"
        f"{ticker_pill}"
        f"<span style='color:{COLOR_MUTED};font-size:12px;'>{source}</span>"
        f"</div>"
        f"<span style='color:{COLOR_DIM};font-size:11px;white-space:nowrap;'>{rel}</span>"
        f"</div>"
        f"{headline}"
        f"</div>"
    )


def empty_state(title: str, subtitle: str = "", icon: str = "📭") -> None:
    st.markdown(
        f"""
        <div style="background:{COLOR_SURFACE};border:1px dashed {COLOR_BORDER};
                    border-radius:14px;padding:48px 24px;text-align:center;">
          <div style='font-size:32px;margin-bottom:10px;'>{icon}</div>
          <div style='color:{COLOR_TEXT};font-weight:600;font-size:15px;'>{title}</div>
          <div style='color:{COLOR_MUTED};font-size:13px;margin-top:6px;max-width:480px;
                      margin-left:auto;margin-right:auto;'>{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_open(padding: str = "20px") -> str:
    """Devuelve la apertura de una card. Cierre con ``</div>``."""
    return (
        f"<div style='background:{COLOR_SURFACE};border:1px solid {COLOR_BORDER};"
        f"border-radius:14px;padding:{padding};'>"
    )


# ─── CSS global ─────────────────────────────────────────────────────────────
def inject_app_styles() -> None:
    """CSS global dark fintech. Llamar una vez por página tras set_page_config."""
    st.markdown(
        f"""
        <style>
            html, body, [class*="css"], .stApp {{
                font-family: {_SANS};
                color: {COLOR_TEXT};
                background: {COLOR_BG};
            }}
            .stApp {{ background: {COLOR_BG}; }}
            .block-container {{
                padding-top: 2.2rem;
                padding-bottom: 4rem;
                max-width: 1320px;
            }}
            /* Espaciado vertical por defecto entre bloques verticales del layout
               para que el flujo respire sin perder densidad. */
            .block-container [data-testid="stVerticalBlock"] {{
                gap: 0.6rem;
            }}
            /* Dentro de columnas, no inflamos el gap (ya viene del padre). */
            [data-testid="column"] [data-testid="stVerticalBlock"] {{
                gap: 0.45rem;
            }}
            /* Gap horizontal entre columnas — Streamlit pone muy poco por defecto. */
            .block-container [data-testid="stHorizontalBlock"] {{
                gap: 0.85rem;
            }}
            /* La topbar es horizontal pero la queremos compacta — el override
               específico vive en la regla .topbar-wrapper [data-testid=...]. */
            h1, h2, h3, h4, h5 {{
                font-weight: 600;
                letter-spacing: -0.018em;
                color: {COLOR_TEXT};
            }}
            h1 {{ font-size: 2rem; }}
            h2 {{ font-size: 1.4rem; }}
            h3 {{ font-size: 1.1rem; }}
            code, pre, kbd, samp {{
                font-family: {_MONO};
                font-size: 0.92em;
                background: {COLOR_SURFACE_2};
                color: {COLOR_TEXT};
                padding: 1px 6px;
                border-radius: 4px;
                border: 1px solid {COLOR_BORDER};
            }}
            a {{ color: {COLOR_ACCENT}; text-decoration: none; }}
            a:hover {{ color: {COLOR_ACCENT_2}; text-decoration: underline; }}

            /* Métricas de Streamlit (st.metric) */
            [data-testid="stMetric"] {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 14px;
                padding: 16px 18px;
                box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset,
                            0 1px 3px rgba(0,0,0,0.4);
                transition: border-color 140ms ease;
            }}
            [data-testid="stMetric"]:hover {{ border-color: {COLOR_BORDER_STRONG}; }}
            [data-testid="stMetricValue"] {{
                font-family: {_MONO};
                font-size: 1.6rem;
                font-weight: 600;
                color: {COLOR_TEXT};
                letter-spacing: -0.01em;
            }}
            [data-testid="stMetricLabel"] {{
                color: {COLOR_MUTED};
                font-size: 0.74rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 500;
            }}
            [data-testid="stMetricDelta"] {{
                font-family: {_MONO};
                font-weight: 600;
                font-size: 0.85rem;
            }}

            /* Tabs */
            .stTabs {{ margin-top: 8px; }}
            .stTabs [data-baseweb="tab-list"] {{
                gap: 0;
                background: transparent;
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            .stTabs [data-baseweb="tab"] {{
                background: transparent;
                color: {COLOR_MUTED};
                font-weight: 500;
                padding: 12px 18px;
                border: none;
                border-bottom: 2px solid transparent;
            }}
            .stTabs [data-baseweb="tab"]:hover {{ color: {COLOR_TEXT}; }}
            .stTabs [aria-selected="true"] {{
                color: {COLOR_ACCENT};
                border-bottom-color: {COLOR_ACCENT};
            }}
            /* Aire dentro del panel de cada tab para que el contenido no quede
               pegado a la barra superior de tabs. */
            .stTabs [data-baseweb="tab-panel"] {{
                padding-top: 22px;
            }}

            /* Botones */
            .stButton button, .stDownloadButton button {{
                border-radius: 8px;
                border: 1px solid {COLOR_BORDER};
                font-weight: 500;
                background: {COLOR_SURFACE};
                color: {COLOR_TEXT};
                transition: all 140ms ease;
                padding: 7px 14px;
            }}
            .stButton button:hover, .stDownloadButton button:hover {{
                border-color: {COLOR_ACCENT};
                color: {COLOR_ACCENT};
                background: {COLOR_SURFACE_2};
            }}
            .stButton button[kind="primary"] {{
                background: {COLOR_ACCENT};
                border-color: {COLOR_ACCENT};
                color: white;
            }}
            .stButton button[kind="primary"]:hover {{
                background: #2563EB;
                border-color: #2563EB;
                color: white;
            }}

            /* Inputs */
            .stTextInput input, .stNumberInput input, .stTextArea textarea,
            div[data-baseweb="select"] > div, div[data-baseweb="input"] {{
                background: {COLOR_SURFACE} !important;
                border: 1px solid {COLOR_BORDER} !important;
                color: {COLOR_TEXT} !important;
                border-radius: 8px !important;
            }}
            .stTextInput input:focus, .stNumberInput input:focus {{
                border-color: {COLOR_ACCENT} !important;
            }}

            /* Expanders */
            div[data-testid="stExpander"] {{
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
                background: {COLOR_SURFACE};
                overflow: hidden;
            }}
            div[data-testid="stExpander"] summary {{ color: {COLOR_TEXT}; font-weight: 500; }}

            /* Dataframes */
            div[data-testid="stDataFrame"] {{
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
                overflow: hidden;
                background: {COLOR_SURFACE};
            }}

            /* Chat */
            [data-testid="stChatMessage"] {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
                padding: 14px 18px;
                margin: 6px 0;
            }}
            .stChatInput textarea, [data-baseweb="textarea"] textarea {{
                background: {COLOR_SURFACE} !important;
                color: {COLOR_TEXT} !important;
                border: 1px solid {COLOR_BORDER} !important;
            }}

            /* Alerts */
            div[data-testid="stAlert"] {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
                color: {COLOR_TEXT};
                margin: 10px 0;
                padding: 14px 16px;
            }}

            /* Divider con más aire alrededor */
            hr, div[data-testid="stDivider"] {{
                margin: 28px 0 !important;
            }}

            /* Forms y expanders: más respiración */
            div[data-testid="stForm"] {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
                padding: 18px 20px;
            }}
            div[data-testid="stForm"] [data-testid="stHorizontalBlock"] {{
                gap: 14px !important;
            }}
            div[data-testid="stExpander"] + div[data-testid="stExpander"],
            div[data-testid="stExpander"] {{
                margin-top: 12px;
            }}

            /* Plotly chart respira por arriba */
            div[data-testid="stPlotlyChart"] {{
                margin-top: 8px;
                margin-bottom: 8px;
            }}

            /* Caption discreto bajo títulos / acciones */
            div[data-testid="stCaptionContainer"], .stCaption {{
                color: {COLOR_DIM};
            }}

            /* Sidebar oculta — la navegación es topbar */
            [data-testid="stSidebar"],
            [data-testid="stSidebarNav"],
            [data-testid="stSidebarNavItems"],
            [data-testid="stSidebarContent"],
            [data-testid="collapsedControl"],
            [data-testid="stSidebarCollapsedControl"],
            [data-testid="stSidebarCollapseButton"],
            [data-testid="stSidebarUserContent"],
            section[data-testid="stSidebar"],
            div[data-testid="stSidebar"] {{
                display: none !important;
                width: 0 !important;
                min-width: 0 !important;
                visibility: hidden !important;
            }}
            section[data-testid="stMain"] {{ margin-left: 0 !important; padding-left: 0 !important; }}
            section[data-testid="stMain"] > div {{ padding-left: 1rem; padding-right: 1rem; }}
            .stAppViewContainer > section:first-child {{ display: none !important; }}

            /* Topbar sticky: se queda fija arriba al hacer scroll, con su propio
               fondo y un divisor inferior. El padding-top se aplica con un
               negativo que compensa el del block-container para que pegue al borde. */
            .topbar-wrapper {{
                position: sticky;
                top: 0;
                z-index: 1000;
                background: {COLOR_BG};
                margin: -2.2rem -1rem 1.5rem -1rem;
                padding: 14px 1rem 12px 1rem;
                border-bottom: 1px solid {COLOR_BORDER};
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
            }}
            .topbar-wrapper [data-testid="stHorizontalBlock"] {{
                gap: 6px !important;
                align-items: center !important;
            }}
            .topbar-wrapper [data-testid="stVerticalBlock"] {{
                gap: 0 !important;
            }}
            .topbar-wrapper [data-testid="column"] {{
                display: flex;
                align-items: center;
                min-width: 0;
            }}
            .topbar-brand {{
                display: flex;
                align-items: center;
                gap: 10px;
                white-space: nowrap;
                padding-left: 4px;
            }}

            /* Topbar nav: estiliza st.page_link como pill */
            [data-testid="stPageLink"] a, a[data-testid="stPageLink-NavLink"] {{
                display: flex;
                align-items: center;
                justify-content: center;
                height: 38px;
                padding: 0 14px;
                border-radius: 8px;
                border: 1px solid transparent;
                color: {COLOR_MUTED} !important;
                font-weight: 500;
                font-size: 14px;
                background: transparent;
                transition: all 140ms ease;
                text-decoration: none !important;
            }}
            [data-testid="stPageLink"] a:hover, a[data-testid="stPageLink-NavLink"]:hover {{
                color: {COLOR_TEXT} !important;
                background: {COLOR_SURFACE_2};
                border-color: {COLOR_BORDER};
            }}
            [data-testid="stPageLink"] a span, a[data-testid="stPageLink-NavLink"] span {{
                color: inherit !important;
                font-weight: 500 !important;
            }}
            .nav-pill {{
                display: flex;
                align-items: center;
                justify-content: center;
                height: 38px;
                padding: 0 14px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                border: 1px solid {COLOR_ACCENT}66;
                background: {COLOR_ACCENT}1A;
                color: {COLOR_ACCENT};
            }}

            hr {{
                border: none;
                border-top: 1px solid {COLOR_BORDER};
            }}

            /* Componentes propios */
            .pill-card {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 14px;
                padding: 0;
                overflow: hidden;
            }}
            .pill-card + .pill-card {{ margin-top: 14px; }}
            .ticker-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 14px 18px;
                border-bottom: 1px solid {COLOR_BORDER};
                font-family: {_MONO};
                transition: background 120ms ease;
                gap: 12px;
            }}
            .ticker-row:last-child {{ border-bottom: none; }}
            .ticker-row:hover {{ background: {COLOR_SURFACE_2}; }}
            .ticker-row .sym {{
                font-weight: 700;
                letter-spacing: 0.4px;
                color: {COLOR_TEXT};
                min-width: 70px;
            }}
            .ticker-row .meta {{ color: {COLOR_MUTED}; font-size: 0.85rem; }}

            .hero-badge {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 12px;
                border: 1px solid {COLOR_BORDER};
                border-radius: 999px;
                background: {COLOR_SURFACE};
                font-size: 12px;
                color: {COLOR_MUTED};
            }}
            .hero-badge .dot {{
                width: 7px; height: 7px; border-radius: 50%;
                background: {COLOR_UP};
                box-shadow: 0 0 8px {COLOR_UP}80;
            }}
            .section-eyebrow {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: {COLOR_MUTED};
                margin-bottom: 10px;
                font-weight: 500;
            }}

            /* Oculta toolbar nativa de Streamlit */
            #MainMenu {{ visibility: hidden; }}
            footer {{ visibility: hidden; }}
            [data-testid="stToolbar"] {{ display: none; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
