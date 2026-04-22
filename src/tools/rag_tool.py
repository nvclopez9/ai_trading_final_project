import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

load_dotenv()

_vectorstore = None
_init_error: str | None = None


def _get_vectorstore():
    global _vectorstore, _init_error
    if _vectorstore is not None or _init_error is not None:
        return _vectorstore

    chroma_dir = os.getenv("CHROMA_DIR", "chroma")
    persist_path = Path(chroma_dir)
    if not persist_path.exists() or not any(persist_path.iterdir()):
        _init_error = "Base de conocimiento no inicializada. Ejecuta `python -m src.rag.ingest` primero."
        return None

    try:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        embeddings_model = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")
        embeddings = OllamaEmbeddings(model=embeddings_model, base_url=host)
        _vectorstore = Chroma(
            persist_directory=str(persist_path),
            embedding_function=embeddings,
        )
        try:
            if _vectorstore._collection.count() == 0:
                _init_error = "Base de conocimiento vacía. Ejecuta `python -m src.rag.ingest` primero."
                _vectorstore = None
                return None
        except Exception:
            pass
        return _vectorstore
    except Exception as e:
        _init_error = f"Error abriendo la base de conocimiento: {e}"
        return None


@tool
def search_finance_knowledge(query: str) -> str:
    """Busca en la base de conocimiento financiera (PDFs indexados) información sobre
    conceptos, glosario, análisis técnico/fundamental, estrategias de inversión a largo
    plazo (value, growth, dividendos) y educación bursátil general.
    Parámetro: query (pregunta o concepto en lenguaje natural).
    Usa esta herramienta para preguntas educativas o conceptuales, NO para precios en vivo."""
    vs = _get_vectorstore()
    if vs is None:
        return _init_error or "Base de conocimiento no disponible."

    try:
        docs = vs.similarity_search(query, k=4)
    except Exception as e:
        return f"Error consultando la base de conocimiento: {e}"

    if not docs:
        return "No se encontro informacion relevante en la base de conocimiento."

    parts = []
    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "desconocido")
        page = d.metadata.get("page")
        ref = f"{source}" + (f" (pag. {page + 1})" if isinstance(page, int) else "")
        text = d.page_content.strip().replace("\n", " ")
        parts.append(f"[{i}] Fuente: {ref}\n{text}")
    return "\n\n".join(parts)
