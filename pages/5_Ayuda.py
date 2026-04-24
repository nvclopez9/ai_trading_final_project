"""Página Ayuda: thin wrapper sobre ``render_help_tab``."""
import streamlit as st

from src.ui.help_view import render_help_tab

st.set_page_config(page_title="Ayuda · Bot de Inversiones", page_icon="❓")
st.title("❓ Ayuda y guía de uso")

render_help_tab()

st.divider()
st.caption(
    "⚠️ Este bot es un proyecto educativo (Práctica IX - Agentes de IA). "
    "No constituye asesoramiento financiero, fiscal ni legal."
)
