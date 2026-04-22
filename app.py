import uuid
import streamlit as st
from dotenv import load_dotenv

from src.services.db import init_db
from src.agent.agent_builder import build_agent
from src.ui.portfolio_view import render_portfolio_tab
from src.ui.charts import price_history_chart

load_dotenv()

st.set_page_config(page_title="Bot de Inversiones", page_icon=":chart_with_upwards_trend:")
st.title("Bot de Inversiones")
st.caption("Asistente conversacional con agente de IA (LangChain + Ollama).")


@st.cache_resource(show_spinner="Inicializando agente...")
def get_agent():
    init_db()
    return build_agent()


agent = get_agent()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Cartera", "📈 Gráficos"])

with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Pregunta sobre un ticker, p. ej. '¿Cómo está AAPL?'")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            try:
                with st.spinner("Pensando..."):
                    result = agent.invoke(
                        {"input": user_input},
                        config={"configurable": {"session_id": st.session_state.session_id}},
                    )
                answer = result.get("output") if isinstance(result, dict) else str(result)
                if not answer:
                    answer = "No he podido generar una respuesta."
            except Exception as e:
                answer = (
                    "Se ha producido un error al consultar al agente. "
                    "Verifica que Ollama esté en ejecución y el modelo esté descargado.\n\n"
                    f"Detalle: {e}"
                )
            placeholder.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

with tab2:
    render_portfolio_tab()

with tab3:
    st.subheader("Histórico de precios")
    col_t, col_p, col_btn = st.columns([2, 1, 1])
    with col_t:
        chart_ticker = st.text_input("Ticker", value="AAPL", key="chart_ticker").strip().upper()
    with col_p:
        chart_period = st.selectbox(
            "Periodo",
            options=["1mo", "3mo", "6mo", "1y", "5y"],
            index=2,
            key="chart_period",
        )
    with col_btn:
        st.write("")
        show = st.button("Ver gráfico", key="chart_show")

    if show and chart_ticker:
        with st.spinner(f"Cargando {chart_ticker}..."):
            fig = price_history_chart(chart_ticker, chart_period)
        if fig is None:
            st.error(f"No se pudo obtener el histórico de '{chart_ticker}'.")
        else:
            st.plotly_chart(fig, use_container_width=True)
