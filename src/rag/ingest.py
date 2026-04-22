import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

load_dotenv()

DOCS_DIR = Path("data/rag_docs")


def _load_pdfs(docs_dir: Path):
    pdfs = sorted(docs_dir.glob("*.pdf"))
    documents = []
    loaded_files = 0
    for pdf in pdfs:
        try:
            loader = PyPDFLoader(str(pdf))
            pages = loader.load()
            for p in pages:
                p.metadata["source"] = pdf.name
            documents.extend(pages)
            loaded_files += 1
            print(f"  + {pdf.name}: {len(pages)} paginas")
        except Exception as e:
            print(f"  ! Saltado {pdf.name} (PDF corrupto o ilegible): {e}")
    return documents, loaded_files, len(pdfs)


def main() -> int:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    chroma_dir = os.getenv("CHROMA_DIR", "chroma")
    embeddings_model = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")

    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Buscando PDFs en {DOCS_DIR.resolve()}")
    documents, loaded, total = _load_pdfs(DOCS_DIR)

    if total == 0:
        print("No se encontraron PDFs. Coloca documentos en data/rag_docs/ y vuelve a ejecutar.")
        return 0
    if not documents:
        print("No se pudo cargar ningun PDF (todos fallaron).")
        return 1

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(documents)
    print(f"Chunks generados: {len(chunks)} (de {loaded}/{total} PDFs)")

    embeddings = OllamaEmbeddings(model=embeddings_model, base_url=host)

    persist_path = Path(chroma_dir).resolve()
    persist_path.mkdir(parents=True, exist_ok=True)

    print(f"Generando embeddings con '{embeddings_model}' y persistiendo en {persist_path}...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_path),
    )
    print("Ingesta completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
