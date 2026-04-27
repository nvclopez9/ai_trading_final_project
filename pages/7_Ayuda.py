"""Página Ayuda: thin wrapper sobre ``render_help_tab``."""
import streamlit as st

from src.ui.components import COLOR_DIM, hero, inject_app_styles
from src.ui.help_view import render_help_tab

st.set_page_config(page_title="Ayuda · Bot de Inversiones", page_icon="?", layout="wide", initial_sidebar_state="expanded")
inject_app_styles()

hero(
    "Ayuda",
    "Cómo usar el bot, qué puede hacer y qué NO hace.",
)

render_help_tab()

st.markdown(
    f"<p style='color:{COLOR_DIM};font-size:11px;margin-top:32px;'>"
    "Este bot es un proyecto educativo (Práctica IX - Agentes de IA). "
    "No constituye asesoramiento financiero, fiscal ni legal."
    "</p>",
    unsafe_allow_html=True,
)
