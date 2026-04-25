"""Catálogo de sugerencias de prompts para el Chat.

Centraliza un set amplio (>=50) de prompts predefinidos organizados por temas
para que el usuario pueda explorar rápidamente lo que el agente sabe hacer.

Diseño:
- ``SUGGESTIONS`` es un dict {categoria_emoji: [prompt, ...]}.
- ``render_suggestions_panel`` pinta un expander con tabs de categorías y un
  botón por prompt que rellena ``st.session_state[prefill_state_key]``.
- Cada categoría se mapea 1:1 con una o varias tools del agente (ver
  ``src/tools/``), de forma que las sugerencias siempre tengan respuesta real.

El panel es **resiliente**: si la red/yfinance está caída no rompe el render,
sólo cae al catálogo estático.
"""
from __future__ import annotations

from typing import Dict, List

import streamlit as st


# ---------------------------------------------------------------------------
# Catálogo estático de sugerencias.
# Orden de categorías intencional: primero análisis (lo más usado), luego
# educación y, al final, las acciones sobre cartera (más avanzadas).
# ---------------------------------------------------------------------------
SUGGESTIONS: Dict[str, List[str]] = {
    # Tool: get_ticker_status — datos puntuales de un ticker.
    "🔍 Análisis de tickers": [
        "¿Cómo está AAPL?",
        "Dame el estado actual de MSFT",
        "Precio y P/E de NVDA hoy",
        "¿Cuál es la capitalización de mercado de TSLA?",
        "Resumen rápido de GOOGL",
        "Compara el estado de AMZN y META",
        "¿Está caro AAPL según su P/E?",
    ],
    # Tool: get_ticker_history — series temporales y rendimiento.
    "📊 Datos históricos": [
        "Histórico de SPY en el último año",
        "Muéstrame la evolución de AAPL en 5 años",
        "¿Cuánto ha subido NVDA en los últimos 3 meses?",
        "Dame el histórico de TSLA del último mes",
        "Gráfico de MSFT en 1 día",
        "¿Cuál ha sido el peor drawdown de META en 1 año?",
        "Rendimiento de AMZN a 5 años",
    ],
    # Tool: get_hot_tickers — gainers / losers / actives.
    "🔥 Mercado en caliente": [
        "Dame los tickers más calientes",
        "¿Quiénes son los top gainers de hoy?",
        "Muéstrame los principales losers del día",
        "¿Qué tickers tienen más volumen hoy?",
        "Top 10 acciones que más suben",
        "¿Cómo va el mercado hoy en general?",
    ],
    # Tool: get_ticker_news — titulares recientes.
    "📰 Noticias y sentimiento": [
        "¿Qué noticias hay de NVDA?",
        "Últimos titulares sobre TSLA",
        "Dame las noticias recientes de AAPL",
        "¿Qué se está diciendo de META esta semana?",
        "Noticias relevantes del sector tech",
        "¿Hay alguna novedad sobre MSFT?",
    ],
    # Tool: search_finance_knowledge — RAG sobre el corpus educativo.
    "📚 Educación financiera": [
        "¿Qué es el P/E ratio?",
        "Explícame qué es un ETF",
        "Diferencia entre acciones value y growth",
        "¿Qué es el dollar cost averaging (DCA)?",
        "¿Cómo funcionan los dividendos?",
        "Bonos vs acciones: ¿en qué se diferencian?",
        "¿Qué es la diversificación y por qué importa?",
        "Explícame qué es un índice bursátil",
    ],
    # Tool: search_finance_knowledge (corpus macro + fiscalidad ES).
    "🌍 Macroeconomía y mercados": [
        "¿Qué es el S&P 500?",
        "¿Qué sectores se consideran defensivos?",
        "Explícame los ciclos económicos",
        "¿Cómo tributan las plusvalías en España?",
        "¿Qué impacto tienen los tipos de interés en bolsa?",
        "Diferencia entre inflación y deflación",
        "¿Qué es la psicología del inversor?",
    ],
    # Tool: portfolio_view / portfolio_transactions — lectura de cartera activa.
    "💼 Mi cartera": [
        "Muéstrame mi cartera",
        "Resumen de mi cartera",
        "¿Cuál es mi P&L actual?",
        "Lista mis transacciones recientes",
        "¿Cuánto efectivo tengo disponible?",
        "Valor total de mi patrimonio",
        "¿Qué posición tengo en AAPL?",
    ],
    # Tools: portfolio_buy / portfolio_sell / portfolio_set_risk / portfolio_set_markets.
    "🎯 Operativa": [
        "Compra 10 acciones de AAPL",
        "Vende 5 acciones de TSLA",
        "Compra 2 acciones de MSFT a precio de mercado",
        "Quiero vender la mitad de mi posición en NVDA",
        "Cambia mi perfil de riesgo a moderado",
        "Configura mis mercados preferidos a US y EU",
    ],
    # Sugerencias que combinan varias tools (educación + análisis).
    "🧪 Estrategias": [
        "Dame 3 ideas de inversión a largo plazo",
        "¿Qué acciones pagan buenos dividendos?",
        "Sugiéreme tickers value para revisar",
        "¿Qué estrategia conviene en un mercado lateral?",
        "Ideas de inversión defensiva ahora mismo",
        "¿Cómo construyo una cartera diversificada?",
    ],
    # Tools: portfolio_list / portfolio_set_risk / portfolio_set_markets.
    "🔄 Multi-cartera": [
        "Lista todas mis carteras",
        "¿Qué carteras tengo creadas?",
        "Compara el rendimiento de mis carteras",
        "Cambia el riesgo de mi cartera activa a agresivo",
        "Configura los mercados de mi cartera a Europa",
    ],
}


# ---------------------------------------------------------------------------
# Sugerencias dinámicas (ligeras): inyectan tickers reales del día.
# ---------------------------------------------------------------------------
def _dynamic_suggestions() -> List[str]:
    """Genera 2-3 sugerencias usando el snapshot real del mercado.

    Si yfinance falla devolvemos lista vacía: el panel sigue funcionando con
    el catálogo estático. No queremos bloquear el render del Chat por una
    integración externa.
    """
    try:
        # Import perezoso: evita coste de import si la función nunca se llama.
        from src.tools.market_tools import _fetch_fallback_quotes  # type: ignore

        rows = _fetch_fallback_quotes()
    except Exception:
        return []

    if not rows:
        return []

    # Tomamos el mayor gainer, mayor loser y el más activo de hoy.
    try:
        top_gainer = max(rows, key=lambda r: r.get("change_pct", 0))["ticker"]
        top_loser = min(rows, key=lambda r: r.get("change_pct", 0))["ticker"]
        top_active = max(rows, key=lambda r: r.get("volume", 0))["ticker"]
    except (ValueError, KeyError):
        return []

    # Variamos la formulación para que no parezcan plantillas idénticas.
    return [
        f"¿Cómo está {top_gainer} hoy?",
        f"¿Por qué cae {top_loser}?",
        f"Dame noticias de {top_active}",
    ]


# ---------------------------------------------------------------------------
# Render del panel.
# ---------------------------------------------------------------------------
def render_suggestions_panel(prefill_state_key: str = "prefill_prompt") -> None:
    """Pinta un panel plegable con todas las sugerencias del catálogo.

    Args:
        prefill_state_key: clave de ``st.session_state`` donde se almacena el
            prompt seleccionado. ``pages/1_Chat.py`` consume ``prefill_prompt``
            y ``pending_prompt`` indistintamente.

    UX:
    - Por defecto el expander está cerrado para no saturar la pantalla en
      conversaciones activas. Si no hay mensajes aún, lo abrimos.
    - Las categorías se distribuyen en ``st.tabs`` (más compacto que un
      acordeón de expanders anidados).
    - Cada prompt es un botón a ancho completo: al pulsarlo guardamos el
      texto y lanzamos ``st.rerun`` para que la página lo procese.
    """
    # Si el chat está vacío, abrimos el panel proactivamente.
    is_chat_empty = not st.session_state.get("messages")

    total_prompts = sum(len(v) for v in SUGGESTIONS.values())
    with st.expander(
        f"💡 Sugerencias de prompts ({total_prompts}+)",
        expanded=is_chat_empty,
    ):
        st.caption(
            "Pulsa cualquier sugerencia para enviarla al chat. "
            "Se agrupan por temas para que encuentres rápido lo que buscas."
        )

        # Sugerencias dinámicas arriba del todo cuando estén disponibles.
        dyn = _dynamic_suggestions()
        if dyn:
            st.markdown("**✨ Basadas en el mercado de hoy**")
            cols = st.columns(len(dyn))
            for col, text in zip(cols, dyn):
                with col:
                    # key con prefijo dyn_ para no colisionar con las estáticas.
                    if st.button(text, key=f"dyn_{text}", use_container_width=True):
                        st.session_state[prefill_state_key] = text
                        st.rerun()
            st.markdown("---")

        # Tabs: una por categoría. Streamlit recorta automáticamente con scroll.
        categories = list(SUGGESTIONS.keys())
        tabs = st.tabs(categories)
        for tab, category in zip(tabs, categories):
            with tab:
                prompts = SUGGESTIONS[category]
                # Distribuimos en 2 columnas para aprovechar ancho de pantalla.
                col_left, col_right = st.columns(2)
                for idx, prompt in enumerate(prompts):
                    target_col = col_left if idx % 2 == 0 else col_right
                    with target_col:
                        # key incluye categoría + idx para garantizar unicidad
                        # incluso si dos categorías comparten el mismo texto.
                        btn_key = f"sugg_{category}_{idx}"
                        if st.button(prompt, key=btn_key, use_container_width=True):
                            st.session_state[prefill_state_key] = prompt
                            st.rerun()
