"""
JARVIS - RAG sobre los documentos del cliente (carpeta docs/)

Cada instalación de Jarvis es independiente: solo conoce los documentos
que están en docs/ de esa instalación. Para darle documentos a un
cliente nuevo, copia el proyecto, reemplaza docs/ y corre ingest.py.

Los documentos dentro de docs/sensible/ nunca se indexan ni se recuperan,
así que su contenido nunca se manda a Anthropic/OpenAI como contexto.
"""
import logging
from pathlib import Path

import chromadb
from pypdf import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).parent / "docs"
SENSITIVE_DIR = DOCS_DIR / "sensible"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "jarvis_docs"
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500  # palabras por trozo
CHUNK_OVERLAP = 50  # palabras que se repiten entre trozos

_chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection():
    return _chroma_client.get_or_create_collection(COLLECTION_NAME)


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


READERS = {
    ".txt": _read_txt,
    ".md": _read_txt,
    ".pdf": _read_pdf,
    ".docx": _read_docx,
}


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = end - overlap
    return chunks


def _embed(openai_client, texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def ingest_docs(openai_client) -> int:
    """
    Lee todos los documentos soportados en docs/, los trocea, genera
    embeddings y los guarda en Chroma. Reemplaza lo que hubiera indexado
    antes. Devuelve el número de trozos indexados.
    """
    collection = get_collection()

    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    total_chunks = 0
    skipped_sensitive = 0
    for path in sorted(DOCS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in READERS:
            continue
        if SENSITIVE_DIR in path.parents:
            skipped_sensitive += 1
            continue
        try:
            text = READERS[path.suffix.lower()](path)
        except Exception as e:
            logger.error(f"No se pudo leer {path.name}: {e}")
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        embeddings = _embed(openai_client, chunks)
        ids = [f"{path.name}-{i}" for i in range(len(chunks))]
        metadatas = [{"source": path.name, "chunk": i} for i in range(len(chunks))]

        collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        total_chunks += len(chunks)
        logger.info(f"Indexado {path.name}: {len(chunks)} trozos")

    if skipped_sensitive:
        logger.info(f"{skipped_sensitive} documento(s) en docs/sensible/ NO indexados (nunca se envían a Claude/OpenAI)")

    return total_chunks


def retrieve_context(openai_client, question: str, k: int = 4) -> str:
    """
    Busca los k trozos más relevantes para la pregunta en los documentos
    ya indexados y los devuelve como texto listo para meter en el prompt.
    Devuelve "" si no hay documentos indexados o si falla la búsqueda
    (por ejemplo, si no hay OPENAI_API_KEY configurada).
    """
    try:
        collection = get_collection()
        if collection.count() == 0:
            return ""

        query_embedding = _embed(openai_client, [question])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, collection.count()),
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        if not docs:
            return ""

        parts = [f"[{meta.get('source', 'documento')}]\n{doc}" for doc, meta in zip(docs, metas)]
        return "\n\n---\n\n".join(parts)

    except Exception as e:
        logger.error(f"Error recuperando contexto RAG: {e}")
        return ""
