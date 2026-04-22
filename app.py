"""Punto de entrada de la aplicación Streamlit del bot de inversiones.

Este fichero es el orquestador de la UI. NO contiene lógica de negocio:
delega en el agente (``src/agent/agent_builder.py``), los servicios
(``src/services/*``) y los renderers de la UI (``src/ui/*``).

Estructura de la página:
  - Cabecera (título + caption).
  - Tres pestañas con ``st.tabs``:
      * 💬 Chat: conversación con el agente.
      * 📊 Cartera: tabla de posiciones + gráficos + transacciones.
      * 📈 Gráficos: histórico de un ticker seleccionable.

Puntos didácticos:

1. ``@st.cache_resource`` sobre ``get_agent``: Streamlit re-ejecuta este
   script ENTERO en cada interacción del usuario (cada click, cada tecla
   en el chat_input, etc.). Si construyéramos el agente fuera del cache,
   cargaríamos el modelo Ollama y compilaríamos el grafo cada vez —
   latencia insoportable. ``cache_resource`` cachea el objeto a nivel de
   proceso; ``init_db()`` también se ejecuta solo en la primera llamada.

2. ``session_id`` con ``uuid.uuid4()`` guardado en ``st.session_state``:
   cada pestaña del navegador recibe un uuid distinto la primera vez que
   se carga. Ese id se pasa al agente vía ``config.configurable`` para
   que ``RunnableWithMessageHistory`` recupere (o cree) SU historial
   propio — aísla el chat de sesiones concurrentes.

3. ``st.session_state.messages``: lista de {role, content} que
   SOLO sirve para REPINTAR los mensajes en el chat al rerun. La memoria
   real del agente vive dentro de ``RunnableWithMessageHistory``, no aquí.

4. Manejo de errores: cualquier fallo del agente (Ollama caído, timeout,
   etc.) se captura con try/except y se muestra un mensaje amigable.
   Nunca se expone un stacktrace en la UI.
"""
# uuid: identificador único por sesión de navegador.
# streamlit: framework de la UI.
# dotenv: cargar variables de entorno al arrancar.
import uuid
import streamlit as st
from dotenv import load_dotenv

# Piezas del proyecto: BD, agente, renderer de la cartera, gráfico histórico.
from src.services.db import init_db
from src.agent.agent_builder import build_agent
from src.ui.portfolio_view import render_portfolio_tab
from src.ui.charts import price_history_chart

# Cargamos .env a nivel top-level para que las variables estén disponibles
# antes de construir el agente (que las lee con os.getenv).
load_dotenv()

# Configuración global de la página (debe ir antes de cualquier otro st.*).
st.set_page_config(page_title="Bot de Inversiones", page_icon=":chart_with_upwards_trend:")
st.title("Bot de Inversiones")
st.caption("Asistente conversacional con agente de IA (LangChain + Ollama).")


# Inicialización pesada cacheada. show_spinner muestra "Inicializando agente..."
# mientras se descarga/arranca el modelo Ollama la primera vez.
@st.cache_resource(show_spinner="Inicializando agente...")
def get_agent():
    """Inicializa la BD (idempotente) y construye el agente.

    Se ejecuta UNA sola vez por proceso de Streamlit gracias a cache_resource.
    En reruns posteriores, Streamlit devuelve la instancia cacheada sin
    volver a ejecutar el cuerpo.
    """
    init_db()
    return build_agent()


# Obtenemos el agente (cacheado). La primera vez tarda; las siguientes es instantáneo.
agent = get_agent()

# Id único por sesión: uuid4 la primera vez, persistido en session_state
# para que sobreviva a reruns dentro de la misma pestaña del navegador.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Tres pestañas en la parte superior. Los emojis son decorativos (no los
# lee el LLM, son solo UI).
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Cartera", "📈 Gráficos"])

# -----------------------------------------------------------------------------
# TAB 1 — Chat con el agente
# -----------------------------------------------------------------------------
with tab1:
    # Historial VISUAL (no es la memoria del agente): sirve para repintar la
    # conversación cuando Streamlit re-ejecuta el script.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Re-render de todos los mensajes previos en su burbuja correspondiente.
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input de chat anclado al fondo de la página.
    user_input = st.chat_input("Pregunta sobre un ticker, p. ej. '¿Cómo está AAPL?'")

    # Si el usuario envió algo este rerun, lo procesamos.
    if user_input:
        # 1. Guardamos y pintamos el mensaje del usuario.
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. Pintamos la respuesta del asistente. placeholder permite
        # sustituir el texto cuando llega la respuesta real (en lugar de
        # usar un spinner externo y luego añadir un st.markdown aparte).
        with st.chat_message("assistant"):
            placeholder = st.empty()
            try:
                with st.spinner("Pensando..."):
                    # Aquí ocurre la magia: invocamos el RunnableWithMessageHistory
                    # pasándole el input y el session_id. Por detrás:
                    #  - Se recupera el historial de esta sesión.
                    #  - Se compone el prompt completo.
                    #  - El LLM decide qué tool invocar (o responder directamente).
                    #  - AgentExecutor ejecuta el bucle hasta AgentFinish.
                    #  - El historial se actualiza automáticamente.
                    result = agent.invoke(
                        {"input": user_input},
                        config={"configurable": {"session_id": st.session_state.session_id}},
                    )
                # El resultado es un dict con "output" (respuesta final) y
                # opcionalmente "intermediate_steps". Nos quedamos con output.
                answer = result.get("output") if isinstance(result, dict) else str(result)
                if not answer:
                    # Fallback por si el agente devuelve cadena vacía (raro).
                    answer = "No he podido generar una respuesta."
            except Exception as e:
                # Error típico: Ollama apagado, modelo no descargado, timeout.
                # Damos instrucciones claras al usuario en vez de un stacktrace.
                answer = (
                    "Se ha producido un error al consultar al agente. "
                    "Verifica que Ollama esté en ejecución y el modelo esté descargado.\n\n"
                    f"Detalle: {e}"
                )
            # Renderizamos la respuesta en la burbuja del asistente.
            placeholder.markdown(answer)
            # Y la guardamos en el historial visual para futuros reruns.
            st.session_state.messages.append({"role": "assistant", "content": answer})

# -----------------------------------------------------------------------------
# TAB 2 — Cartera simulada
# -----------------------------------------------------------------------------
with tab2:
    # Toda la lógica vive en src/ui/portfolio_view.py para que app.py quede delgado.
    render_portfolio_tab()

# -----------------------------------------------------------------------------
# TAB 3 — Gráficos de histórico
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Histórico de precios")
    # Layout en tres columnas: ticker (grande), periodo (medio), botón (pequeño).
    col_t, col_p, col_btn = st.columns([2, 1, 1])
    with col_t:
        # Input de ticker con default AAPL y normalización upper.
        chart_ticker = st.text_input("Ticker", value="AAPL", key="chart_ticker").strip().upper()
    with col_p:
        # Selectbox con los periodos soportados por yfinance más usuales.
        # index=2 pre-selecciona "6mo" (tercer elemento) como default sensato.
        chart_period = st.selectbox(
            "Periodo",
            options=["1mo", "3mo", "6mo", "1y", "5y"],
            index=2,
            key="chart_period",
        )
    with col_btn:
        # st.write("") reserva espacio vertical para alinear el botón con
        # los inputs de arriba (truco visual típico en Streamlit).
        st.write("")
        show = st.button("Ver gráfico", key="chart_show")

    # Solo pedimos el histórico cuando el usuario pulsa el botón (evita
    # llamadas a yfinance innecesarias en cada rerun).
    if show and chart_ticker:
        with st.spinner(f"Cargando {chart_ticker}..."):
            fig = price_history_chart(chart_ticker, chart_period)
        # La función devuelve None si falla (ticker inválido, sin red, etc.):
        # entonces mostramos un error controlado en lugar de petar.
        if fig is None:
            st.error(f"No se pudo obtener el histórico de '{chart_ticker}'.")
        else:
            st.plotly_chart(fig, use_container_width=True)
