"""Tool RAG: búsqueda semántica sobre los PDFs financieros ingestados.

Flujo del RAG en este proyecto:
  1. Offline (una vez): ``python -m src.rag.ingest`` lee los PDFs de
     ``data/rag_docs/``, los trocea con ``RecursiveCharacterTextSplitter``
     (chunks de 800 chars, overlap 120), genera embeddings con
     ``nomic-embed-text`` vía Ollama y persiste todo en ChromaDB.
  2. Online (en cada pregunta del usuario): esta tool abre el vectorstore
     persistido en modo lazy (singleton de módulo) y hace
     ``similarity_search(query, k=4)`` devolviendo los 4 fragmentos más
     relevantes con su fuente (nombre del PDF + página).

Importante para la exposición:
  - El vectorstore se cachea a nivel de módulo (``_vectorstore``). Así no
    reabrimos Chroma ni reinstanciamos los embeddings en cada invocación
    de la tool, que es lo que más tarda (cargar el modelo en Ollama).
  - También cacheamos ``_init_error``: si no hay vectorstore porque aún no
    se ha ingerido, no reintentamos abrir Chroma 50 veces; devolvemos un
    mensaje accionable al primer intento y lo memorizamos.
"""
# os/Path: leer variables de entorno y comprobar si existe el directorio Chroma.
import os
from pathlib import Path
# dotenv: defaults del proyecto (CHROMA_DIR, EMBEDDINGS_MODEL) vienen del .env.
from dotenv import load_dotenv
# LangChain — decorador @tool y adaptadores de Ollama + Chroma.
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

load_dotenv()

# Singleton module-level: la primera llamada crea el vectorstore, las
# siguientes lo reutilizan. Si la inicialización falla guardamos el motivo
# en _init_error para no reintentar (y para devolver un mensaje útil al LLM).
_vectorstore = None
_init_error: str | None = None


def _get_vectorstore():
    """Abre (o devuelve cacheado) el vectorstore Chroma persistido.

    Devuelve None y fija ``_init_error`` si la base aún no está creada o si
    hay un problema al abrirla. No lanza excepciones para que la tool que la
    llama pueda devolver un mensaje claro al agente.
    """
    global _vectorstore, _init_error
    # Cortocircuito: ya inicializado o ya marcado como fallido definitivamente.
    if _vectorstore is not None or _init_error is not None:
        return _vectorstore

    # Ubicación del Chroma persistido: mismo default que ingest.py para evitar drift.
    chroma_dir = os.getenv("CHROMA_DIR", "chroma")
    persist_path = Path(chroma_dir)
    # Si el directorio no existe o está vacío, el usuario no ha corrido la ingesta.
    # Devolvemos un mensaje accionable en lugar de reventar con un stacktrace.
    if not persist_path.exists() or not any(persist_path.iterdir()):
        _init_error = "Base de conocimiento no inicializada. Ejecuta `python -m src.rag.ingest` primero."
        return None

    try:
        # Los embeddings DEBEN ser los mismos (modelo + host) que se usaron en
        # la ingesta; si no, los vectores viven en espacios distintos y la
        # similitud no tiene sentido.
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        embeddings_model = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")
        embeddings = OllamaEmbeddings(model=embeddings_model, base_url=host)
        # Abrimos el vectorstore apuntando al mismo persist_directory que escribió ingest.
        _vectorstore = Chroma(
            persist_directory=str(persist_path),
            embedding_function=embeddings,
        )
        # Sanity check: que el collection tenga al menos un embedding. Accede
        # a API privada (_collection) — aceptable como guardarraíl; si la API
        # cambia, el try/except la silencia y seguimos usando el vectorstore.
        try:
            if _vectorstore._collection.count() == 0:
                _init_error = "Base de conocimiento vacía. Ejecuta `python -m src.rag.ingest` primero."
                _vectorstore = None
                return None
        except Exception:
            pass
        return _vectorstore
    except Exception as e:
        # Memorizamos el error para no volver a intentarlo en esta sesión.
        _init_error = f"Error abriendo la base de conocimiento: {e}"
        return None


@tool
def search_finance_knowledge(query: str) -> str:
    """Busca en la base de conocimiento financiera (PDFs indexados) información sobre
    conceptos, glosario, análisis técnico/fundamental, estrategias de inversión a largo
    plazo (value, growth, dividendos) y educación bursátil general.
    Parámetro: query (pregunta o concepto en lenguaje natural).
    Usa esta herramienta para preguntas educativas o conceptuales, NO para precios en vivo."""
    # Obtenemos (o inicializamos) el vectorstore; si no hay, devolvemos el motivo.
    vs = _get_vectorstore()
    if vs is None:
        return _init_error or "Base de conocimiento no disponible."

    try:
        # k=4 es un compromiso típico: suficiente contexto para responder sin
        # saturar el context window del LLM ni ensuciar con fragmentos poco relevantes.
        docs = vs.similarity_search(query, k=4)
    except Exception as e:
        return f"Error consultando la base de conocimiento: {e}"

    if not docs:
        return "No se encontró información relevante en la base de conocimiento."

    # Formateamos cada chunk con su fuente: el LLM debe citar el PDF en su
    # respuesta final (regla #6 del system prompt). La página se guarda en
    # metadata por PyPDFLoader; la convertimos a 1-indexed para el humano.
    parts = []
    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "desconocido")
        page = d.metadata.get("page")
        ref = f"{source}" + (f" (pág. {page + 1})" if isinstance(page, int) else "")
        # Colapsamos saltos de línea: los chunks de PDF vienen con muchos \n
        # que confunden al LLM pequeño al parsear la respuesta.
        text = d.page_content.strip().replace("\n", " ")
        parts.append(f"[{i}] Fuente: {ref}\n{text}")
    # Doble salto entre chunks para que sean visualmente separables.
    return "\n\n".join(parts)
