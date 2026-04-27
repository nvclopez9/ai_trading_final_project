"""Página Ayuda: índice de capacidades del bot + disclaimer educativo."""
import streamlit as st

from src.ui.components import (
    footer_disclaimer,
    hero,
    inject_app_styles,
    sidebar_kpi,
)
from src.ui.help_view import render_help_tab

st.set_page_config(page_title="Ayuda · Bot de Inversiones", page_icon="?",
                   layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

hero("Ayuda", "Cómo usar el bot, qué puede hacer y qué NO hace.")


# ─── Sidebar contextual: índice + meta ─────────────────────────────────────
with st.sidebar:
    st.markdown("<div class='section-eyebrow'>Índice</div>", unsafe_allow_html=True)
    if st.button("Mercado", key="help_sb_market", use_container_width=True):
        st.switch_page("pages/4_Mercado.py")
    if st.button("Cartera", key="help_sb_portfolio", use_container_width=True):
        st.switch_page("pages/2_Mi_Cartera.py")
    if st.button("Chat con IA", key="help_sb_chat", use_container_width=True):
        st.switch_page("pages/1_Chat.py")
    if st.button("Top del día", key="help_sb_top", use_container_width=True):
        st.switch_page("pages/5_Top_del_Dia.py")
    if st.button("Noticias", key="help_sb_news", use_container_width=True):
        st.switch_page("pages/6_Noticias.py")

    st.markdown("<div class='section-eyebrow' style='margin-top:14px;'>Meta</div>",
                unsafe_allow_html=True)
    st.markdown(sidebar_kpi("Versión", "MVP"), unsafe_allow_html=True)
    st.markdown(sidebar_kpi("Stack", "Streamlit",
                hint="LangChain + Ollama / OpenRouter"),
                unsafe_allow_html=True)


render_help_tab()

footer_disclaimer()
