"""📰 Página de Noticias.

Muestra las últimas noticias de un ticker, con la posibilidad de pedir
opinión al agente sobre cualquier noticia individualmente o un resumen
global de todas.
"""
import hashlib

import streamlit as st

from src.agent.singleton import get_agent, ensure_session_id
from src.tools.market_tools import fetch_ticker_news

st.set_page_config(page_title="Noticias · Bot de Inversiones", page_icon="📰")
st.title("📰 Noticias")

agent = get_agent()
session_id = ensure_session_id()

default_ticker = st.session_state.get("active_ticker", "AAPL")
ticker = st.text_input(
    "Ticker",
    value=default_ticker,
    help="Símbolo bursátil, p. ej. AAPL, MSFT, NVDA",
).strip().upper()

col_l, _ = st.columns([1, 4])
load_btn = col_l.button("Cargar", type="primary", key="news_load_btn")

# Guardamos la última carga en session_state para sobrevivir a reruns.
news_key = f"news_items_{ticker}"
if load_btn and ticker:
    with st.spinner("Cargando noticias..."):
        items = fetch_ticker_news(ticker, limit=10)
    st.session_state[news_key] = items

items = st.session_state.get(news_key, [])

if not items:
    st.info("Introduce un ticker y pulsa **Cargar** para ver sus últimas noticias.")
    st.stop()


def _news_hash(n: dict) -> str:
    """Hash estable por noticia para usar en keys de widgets y session_state."""
    raw = (n.get("link") or n.get("title", "")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:10]


def _ask_agent(prompt: str) -> str:
    try:
        result = agent.invoke(
            {"input": prompt},
            config={"configurable": {"session_id": session_id}},
        )
        return result.get("output") if isinstance(result, dict) else str(result)
    except Exception as e:
        return f"No pude obtener respuesta del agente: {e}"


st.subheader(f"Últimas noticias de {ticker}")
for n in items:
    h = _news_hash(n)
    title = n["title"]
    if n["link"]:
        st.markdown(f"**[{title}]({n['link']})**")
    else:
        st.markdown(f"**{title}**")
    st.caption(f"{n['date']} · {n['source']}")

    btn_key = f"news_opinion_btn_{h}"
    state_key = f"news_comment_{h}"

    if st.button("💬 Pedir opinión al agente", key=btn_key):
        prompt = (
            f"Analiza brevemente esta noticia sobre {ticker} y coméntala en 3-4 frases:\n"
            f"Titular: {n['title']}\n"
            f"Fuente: {n['source']}\n"
            f"Fecha: {n['date']}\n"
            f"URL: {n.get('link', '')}\n"
            "Considera: relevancia para la empresa, posible impacto en el precio, y un disclaimer."
        )
        with st.spinner("El agente está leyendo..."):
            st.session_state[state_key] = _ask_agent(prompt)

    if state_key in st.session_state:
        st.info(st.session_state[state_key])

    st.divider()

# Expander de resumen global.
with st.expander("💡 Pedir un resumen del agente sobre todas las noticias"):
    summary_key = f"news_summary_{ticker}"
    if st.button("Generar resumen", key=f"news_summary_btn_{ticker}"):
        bullet_list = "\n".join(
            f"- [{n['date']}] {n['title']} ({n['source']})" for n in items
        )
        prompt = (
            f"A continuación tienes los titulares más recientes sobre {ticker}. "
            "Haz un resumen ejecutivo en 5-6 bullets destacando temas recurrentes, "
            "posibles catalizadores y riesgos. No inventes cifras. Añade disclaimer.\n\n"
            f"{bullet_list}"
        )
        with st.spinner("Resumiendo..."):
            st.session_state[summary_key] = _ask_agent(prompt)
    if summary_key in st.session_state:
        st.markdown(st.session_state[summary_key])
