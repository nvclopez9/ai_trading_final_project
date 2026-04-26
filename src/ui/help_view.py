"""Pestaña de ayuda: explica qué puede hacer el bot y cómo usarlo.

Render reorganizado en 3 secciones (Qué puedo hacer, Cómo interpretar
respuestas, Qué NO hace) con estética dark fintech basada en
``src/ui/components/__init__.py``.
"""
from __future__ import annotations

import streamlit as st

from src.ui.components import (
    COLOR_ACCENT,
    COLOR_DIM,
    COLOR_MUTED,
    COLOR_TEXT,
    COLOR_WARNING,
    section_title,
)


# Bloques de ejemplos: (categoría, título, descripción, [(label_ejemplo, prompt)]).
_CAPABILITIES = [
    {
        "title": "Mercado",
        "subtitle": "Precios, fundamentales y comparativas en vivo.",
        "examples": [
            ("¿Cómo está AAPL?", "¿Cómo está AAPL?"),
            ("Histórico de TSLA a 6 meses", "Dame el histórico de TSLA a 6 meses"),
            ("Tickers más calientes hoy", "¿Cuáles son los tickers más calientes hoy?"),
            ("Comparar AAPL y MSFT", "Compárame AAPL y MSFT"),
        ],
    },
    {
        "title": "Cartera",
        "subtitle": "Operativa simulada sobre tu cartera activa.",
        "examples": [
            ("Comprar 10 MSFT", "Compra 10 acciones de MSFT"),
            ("Vender 5 AAPL", "Vende 5 acciones de AAPL"),
            ("Ver mi cartera", "Muéstrame mi cartera"),
            ("Últimas transacciones", "Enséñame mis últimas transacciones"),
        ],
    },
    {
        "title": "Educación",
        "subtitle": "Conceptos financieros explicados con fuentes oficiales.",
        "examples": [
            ("¿Qué es el ratio P/E?", "¿Qué es el ratio P/E?"),
            ("¿Qué es un ETF?", "Explícame qué es un ETF"),
            ("Value vs growth", "Diferencia entre value y growth investing"),
            ("¿Qué es DCA?", "¿Qué es el DCA (dollar-cost averaging)?"),
        ],
    },
]


def _capability_card(idx: int, block: dict) -> None:
    """Pinta una card con título, subtítulo y botones de ejemplo clickables."""
    st.markdown(
        f"""
        <div class="pill-card" style="padding:20px;height:100%;">
          <div style="font-size:14px;font-weight:700;color:{COLOR_TEXT};
                      letter-spacing:-0.01em;margin-bottom:4px;">{block['title']}</div>
          <div style="font-size:12px;color:{COLOR_MUTED};margin-bottom:14px;
                      line-height:1.5;">{block['subtitle']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for j, (label, prompt) in enumerate(block["examples"]):
        if st.button(label, key=f"help_ex_{idx}_{j}", use_container_width=True):
            st.session_state["prefill_prompt"] = prompt
            st.switch_page("pages/1_Chat.py")


def render_help_tab() -> None:
    """Renderiza el contenido educativo de la pestaña Ayuda."""

    # ── Sección 1: Qué puedo hacer ──────────────────────────────────────────
    section_title(
        "Qué puedo hacer",
        "Tres áreas principales: mercado en vivo, cartera simulada y educación financiera.",
    )

    cols = st.columns(3)
    for i, block in enumerate(_CAPABILITIES):
        with cols[i]:
            _capability_card(i, block)

    # ── Sección 2: Cómo interpretar respuestas ──────────────────────────────
    section_title(
        "Cómo interpretar respuestas",
        "Convenciones y consejos para sacar el máximo partido al agente.",
    )

    st.markdown(
        f"""
        <div class="pill-card" style="padding:22px;">
          <ul style="margin:0;padding-left:18px;color:{COLOR_TEXT};
                     font-size:14px;line-height:1.75;">
            <li><b>Tickers en mayúsculas</b> (<code>AAPL</code>, <code>MSFT</code>):
                las herramientas de mercado los esperan así.</li>
            <li><b>Periodos válidos</b>: <code>1mo</code>, <code>3mo</code>,
                <code>6mo</code>, <code>1y</code>, <code>5y</code>.</li>
            <li><b>El agente mantiene contexto</b>: si una respuesta no convence,
                reformula o pide aclaración en el mismo chat.</li>
            <li><b>Educación financiera</b>: las respuestas se basan en PDFs
                oficiales de CNMV y SEC y citan la fuente.</li>
            <li><b>La cartera es simulada</b>: no hay broker real ni dinero real;
                sirve para practicar sin riesgo.</li>
          </ul>
          <div style="margin-top:14px;color:{COLOR_DIM};font-size:12px;">
            Tip: el badge LLM activo en la Home te indica qué motor (Ollama local
            u OpenRouter cloud) está respondiendo.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sección 3: Qué NO hace ──────────────────────────────────────────────
    section_title(
        "Qué NO hace",
        "Limitaciones que conviene tener en cuenta antes de pedir.",
    )

    st.markdown(
        f"""
        <div class="pill-card" style="padding:22px;border-color:{COLOR_WARNING};
                     box-shadow:0 0 0 1px {COLOR_WARNING}33 inset;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;
                      color:{COLOR_WARNING};font-weight:600;margin-bottom:10px;">
            Disclaimers
          </div>
          <ul style="margin:0;padding-left:18px;color:{COLOR_TEXT};
                     font-size:14px;line-height:1.75;">
            <li><b>No es asesoramiento financiero</b> personalizado: es una
                herramienta educativa.</li>
            <li><b>No opera en un broker real</b>: todas las compras y ventas
                viven en una base de datos local.</li>
            <li><b>No predice el futuro</b>: ningún modelo sabe si una acción
                subirá mañana.</li>
            <li><b>Datos con retraso</b>: los precios vienen de Yahoo Finance
                con un pequeño delay, no son tick a tick.</li>
            <li><b>No realiza operaciones fiscales o legales</b> en tu nombre.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
