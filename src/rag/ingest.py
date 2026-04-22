"""Script de ingesta RAG: PDFs -> chunks -> embeddings -> ChromaDB.

Se ejecuta OFFLINE una sola vez (o cuando cambien los PDFs) con:

    python -m src.rag.ingest

Flujo:
  1. Localiza los PDFs en ``data/rag_docs/`` (los crea vacío si no existen).
  2. Los carga con ``PyPDFLoader`` (una página = un Document con metadata).
  3. Los trocea con ``RecursiveCharacterTextSplitter(800, 120)``:
       - 800 caracteres por chunk: un compromiso entre contexto suficiente
         para responder y no saturar el prompt del LLM.
       - 120 de overlap: asegura que no partimos frases por la mitad entre
         chunks consecutivos y preserva contexto en los límites.
  4. Genera embeddings con ``nomic-embed-text`` vía Ollama (mismo modelo
     que ``rag_tool.py`` usa al consultar, CRÍTICO para que la similitud
     funcione).
  5. Persiste todo en ChromaDB en ``$CHROMA_DIR`` (default: ``chroma/``).

No es idempotente: si se ejecuta dos veces, duplica embeddings. Para
reindexar hay que borrar ``chroma/`` manualmente.
"""
# os/sys: variables de entorno y exit codes. pathlib: rutas portables.
import os
import sys
from pathlib import Path
# dotenv: leer CHROMA_DIR, OLLAMA_HOST y EMBEDDINGS_MODEL del .env.
from dotenv import load_dotenv
# LangChain — loader de PDFs, splitter, embeddings Ollama y vectorstore Chroma.
# Nota: PyPDFLoader sigue en langchain_community (los loaders aún no se han
# partido a paquetes por proveedor).
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
# Document como fallback para leer .md/.txt cuando los loaders dedicados no estén.
from langchain_core.documents import Document

# Loaders opcionales para texto plano / markdown. Si la librería opcional
# (`unstructured`) no está disponible, caemos a lectura UTF-8 plana.
try:  # pragma: no cover - depende del entorno
    from langchain_community.document_loaders import TextLoader
except Exception:  # pragma: no cover
    TextLoader = None  # type: ignore[assignment]

try:  # pragma: no cover - requiere `unstructured`
    from langchain_community.document_loaders import UnstructuredMarkdownLoader
except Exception:  # pragma: no cover
    UnstructuredMarkdownLoader = None  # type: ignore[assignment]

load_dotenv()

# Ruta relativa a la cwd: se asume que se ejecuta como `python -m src.rag.ingest`
# desde la raíz del repo (lo documenta el README). Alternativa más robusta
# sería resolverla relativa a __file__, pero añade fricción sin valor real.
DOCS_DIR = Path("data/rag_docs")


def _load_pdfs(docs_dir: Path):
    """Carga todos los .pdf del directorio indicado como Documents de LangChain.

    Devuelve (documents, loaded_files, total_files). Si un PDF está corrupto
    se salta con un print y seguimos: queremos que ingestar 4 de 5 PDFs sea
    mejor que fallar entero.
    """
    # sorted(): orden determinista (útil para logs y reproducibilidad).
    pdfs = sorted(docs_dir.glob("*.pdf"))
    documents = []
    loaded_files = 0
    for pdf in pdfs:
        try:
            loader = PyPDFLoader(str(pdf))
            # .load() devuelve una lista: un Document por página del PDF,
            # con metadata {"source": <ruta>, "page": <idx 0-based>}.
            pages = loader.load()
            # Sobrescribimos "source" con solo el nombre (sin ruta) para que
            # la cita en la respuesta del agente sea más limpia.
            for p in pages:
                p.metadata["source"] = pdf.name
            documents.extend(pages)
            loaded_files += 1
            print(f"  + {pdf.name}: {len(pages)} páginas")
        except Exception as e:
            # PDF corrupto, cifrado o con estructura rara: lo saltamos.
            print(f"  ! Saltado {pdf.name} (PDF corrupto o ilegible): {e}")
    return documents, loaded_files, len(pdfs)


def _load_text_file(path: Path) -> list[Document]:
    """Carga un fichero de texto/markdown como lista de Documents.

    Estrategia (de más rica a más básica):
      1. ``UnstructuredMarkdownLoader`` si el fichero es .md y la dependencia
         ``unstructured`` está instalada (preserva estructura de headers).
      2. ``TextLoader`` de langchain_community con encoding utf-8.
      3. Fallback manual: ``path.read_text("utf-8")`` envuelto en Document.

    Siempre normalizamos ``metadata["source"]`` al nombre del fichero (sin
    ruta) y añadimos ``page=0`` para homogeneizar con los PDFs.
    """
    is_markdown = path.suffix.lower() == ".md"
    docs: list[Document] | None = None

    if is_markdown and UnstructuredMarkdownLoader is not None:
        try:
            docs = UnstructuredMarkdownLoader(str(path)).load()
        except Exception:
            docs = None

    if docs is None and TextLoader is not None:
        try:
            docs = TextLoader(str(path), encoding="utf-8").load()
        except Exception:
            docs = None

    if docs is None:
        # Fallback mínimo sin dependencias: leemos como UTF-8 a pelo.
        text = path.read_text(encoding="utf-8")
        docs = [Document(page_content=text, metadata={})]

    for d in docs:
        d.metadata["source"] = path.name
        d.metadata.setdefault("page", 0)
    return docs


def _load_text_docs(docs_dir: Path):
    """Carga todos los .md y .txt del directorio como Documents.

    Devuelve (documents, loaded_files, total_files). Mismo contrato que
    ``_load_pdfs`` para que el resto del pipeline sea uniforme.
    """
    paths = sorted(
        [p for p in docs_dir.iterdir() if p.suffix.lower() in {".md", ".txt"}]
    )
    documents: list[Document] = []
    loaded_files = 0
    for path in paths:
        try:
            loaded = _load_text_file(path)
            documents.extend(loaded)
            loaded_files += 1
            print(f"  + {path.name}: {len(loaded)} bloque(s) de texto")
        except Exception as e:
            print(f"  ! Saltado {path.name} (no se pudo leer): {e}")
    return documents, loaded_files, len(paths)


def main() -> int:
    """Pipeline principal: descubrir PDFs, trocear, embedding y persistir.

    Return codes: 0 = éxito o no hay PDFs (no-op), 1 = todos los PDFs fallaron.
    """
    # Configuración desde .env con defaults razonables.
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    chroma_dir = os.getenv("CHROMA_DIR", "chroma")
    embeddings_model = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")

    # Si la carpeta no existe la creamos para dar mensaje guiado al usuario.
    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Buscando documentos en {DOCS_DIR.resolve()}")
    pdf_docs, pdf_loaded, pdf_total = _load_pdfs(DOCS_DIR)
    text_docs, text_loaded, text_total = _load_text_docs(DOCS_DIR)

    documents = pdf_docs + text_docs
    loaded = pdf_loaded + text_loaded
    total = pdf_total + text_total

    # Casos de salida temprana con códigos distintos:
    #  - total == 0: carpeta vacía, no es error (el usuario aún no puso docs).
    #  - documents vacío pero total > 0: todos los ficheros fallaron al cargar.
    if total == 0:
        print("No se encontraron documentos (.pdf/.md/.txt). Coloca contenido en data/rag_docs/ y vuelve a ejecutar.")
        return 0
    if not documents:
        print("No se pudo cargar ningún documento (todos fallaron).")
        return 1

    # Chunking. 800/120 son los valores acordados en el plan de Fase 2.
    # RecursiveCharacterTextSplitter intenta partir por párrafo, luego por
    # frase, luego por palabra, etc. — mantiene la semántica mejor que un
    # split ciego por longitud.
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(documents)
    print(f"Chunks generados: {len(chunks)} (de {loaded}/{total} documentos)")

    # Instanciamos los embeddings apuntando al Ollama local. El modelo debe
    # estar descargado con `ollama pull nomic-embed-text` antes de correr esto.
    embeddings = OllamaEmbeddings(model=embeddings_model, base_url=host)

    # Chroma persistirá aquí: si ya existe el directorio, añade los nuevos
    # embeddings (no los reemplaza — por eso no es idempotente).
    persist_path = Path(chroma_dir).resolve()
    persist_path.mkdir(parents=True, exist_ok=True)

    print(f"Generando embeddings con '{embeddings_model}' y persistiendo en {persist_path}...")
    # Chroma.from_documents: genera embeddings para cada chunk, crea la
    # colección y la guarda en disco. Esta es la parte más lenta del pipeline
    # (1-2 segundos por chunk con nomic-embed-text en CPU).
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_path),
    )
    print("Ingesta completada.")
    return 0


# Entry point estándar: sys.exit devuelve el código a la shell, útil para CI.
if __name__ == "__main__":
    sys.exit(main())
