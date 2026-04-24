"""Pestaña de ayuda: explica qué puedes preguntar al bot y cómo usarlo.

Función única ``render_help_tab()`` invocada desde ``app.py``. Todo el
contenido es estático: no consulta el agente ni yfinance, por lo que es
rápida y útil como onboarding para usuarios que abren la app por primera vez.
"""
import streamlit as st


def render_help_tab() -> None:
    """Renderiza el contenido educativo de la pestaña ❓ Ayuda."""
    st.subheader("❓ ¿Cómo usar el bot?")
    st.caption(
        "Este asistente combina datos de mercado en vivo, una cartera simulada y "
        "una base de conocimiento financiera (PDFs oficiales de CNMV y SEC). "
        "Aquí te enseño qué puedes preguntarle y cómo sacarle partido."
    )

    st.markdown("### 🎯 Qué puedes preguntarme")

    # 4 expanders en 2x2 para que queden todos visibles y expandibles a demanda.
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("💹 Precios y mercado", expanded=True):
            st.markdown(
                "- *¿Cómo está AAPL?*\n"
                "- *Dame el histórico de TSLA a 6 meses*\n"
                "- *¿Cuáles son los tickers más calientes hoy?*\n"
                "- *Muéstrame los que más bajan en el S&P hoy*\n"
                "- *¿Cuál es la capitalización de MSFT?*"
            )
        with st.expander("💼 Cartera simulada"):
            st.markdown(
                "- *Compra 10 acciones de MSFT*\n"
                "- *Vende 5 acciones de AAPL*\n"
                "- *Muéstrame mi cartera*\n"
                "- *Enséñame mis últimas transacciones*\n"
                "- *¿Cuánto vale mi cartera ahora?*"
            )
        with st.expander("🧺 Multi-cartera"):
            st.markdown(
                "Ahora puedes tener **varias carteras** con perfiles distintos. "
                "Créalas desde la pestaña 🧺 **Carteras** (nombre, cash inicial, "
                "riesgo y mercados objetivo). Las operaciones del agente se "
                "ejecutan siempre sobre la cartera **activa**.\n\n"
                "Interacciones útiles con el agente:\n"
                "- *Lista mis carteras*\n"
                "- *Cambia el riesgo de mi cartera a agresivo*\n"
                "- *Cambia los mercados a USA y Europa*\n\n"
                "ℹ️ El **dinero inicial** de una cartera **no** se puede modificar "
                "desde el agente: crea una nueva cartera si necesitas otro importe."
            )
    with col2:
        with st.expander("📚 Educación financiera", expanded=True):
            st.markdown(
                "- *¿Qué es el ratio P/E?*\n"
                "- *Explícame qué es un ETF*\n"
                "- *Diferencia entre value y growth investing*\n"
                "- *¿Qué es el DCA (dollar-cost averaging)?*\n"
                "- *¿Cómo tributan las plusvalías en España?*"
            )
        with st.expander("📰 Noticias y contexto"):
            st.markdown(
                "- *¿Qué noticias hay de NVDA?*\n"
                "- *Últimos titulares de Amazon*\n"
                "- *Compárame AAPL y MSFT*\n"
                "- *¿Es buen momento para entrar en tecnología?* (opinión educativa, "
                "no consejo de inversión)"
            )

    st.divider()

    st.markdown("### 💡 Consejos para mejores respuestas")
    st.markdown(
        "- **Usa el ticker en mayúsculas** (`AAPL`, `MSFT`) en vez del nombre "
        "completo: las herramientas de mercado lo esperan así.\n"
        "- **Sé específico con el periodo** (`1mo`, `3mo`, `6mo`, `1y`, `5y`) "
        "si quieres un histórico concreto.\n"
        "- **Si la respuesta no te convence, reformula** la pregunta o pide "
        "aclaraciones — el agente mantiene el contexto de la conversación.\n"
        "- **Para conceptos educativos**, el bot busca en los PDFs oficiales "
        "de CNMV y SEC y te cita la fuente.\n"
        "- **La cartera es simulada**: no hay dinero real ni broker; es para "
        "practicar sin riesgo."
    )

    st.divider()

    st.markdown("### 🚫 Qué NO puede hacer")
    st.markdown(
        "- **Datos en tiempo real tick a tick**: los precios vienen de Yahoo "
        "Finance con un pequeño retraso.\n"
        "- **Asesoramiento financiero personalizado**: esta herramienta es "
        "educativa; no te dice qué comprar con tu dinero real.\n"
        "- **Operar en un broker real**: todas las compras/ventas son "
        "simuladas y sólo viven en una base de datos local.\n"
        "- **Predecir el futuro**: ningún modelo, ni siquiera el mejor, sabe "
        "si una acción subirá mañana."
    )

    st.info(
        "ℹ️ Este bot es un proyecto educativo (Práctica IX - Agentes de IA). "
        "La información que ofrece es orientativa y no constituye asesoramiento "
        "financiero, fiscal ni legal."
    )
