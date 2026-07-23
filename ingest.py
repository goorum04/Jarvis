"""
Script de ingesta de documentos para el RAG de Jarvis.

Mete tus PDF/Word/TXT/MD en la carpeta docs/ y corre:

    python ingest.py

Cada vez que agregues o cambies documentos, vuelve a correrlo para
reindexar. Requiere OPENAI_API_KEY en el .env (se usa solo para generar
los embeddings, no para responder).
"""
import logging
import os

from dotenv import load_dotenv
import openai

from rag import ingest_docs, DOCS_DIR

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    if not DOCS_DIR.exists():
        DOCS_DIR.mkdir(parents=True)
        logger.warning(f"Cree la carpeta {DOCS_DIR}. Mete ahi tus documentos y vuelve a correr este script.")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("Falta OPENAI_API_KEY en el .env (se necesita para generar los embeddings).")
        return

    client_openai = openai.OpenAI(api_key=api_key)
    total = ingest_docs(client_openai)

    if total == 0:
        logger.warning(f"No se indexo nada. Revisa que docs/ tenga archivos .pdf, .docx, .txt o .md")
    else:
        logger.info(f"Listo: {total} trozos indexados desde {DOCS_DIR}")


if __name__ == "__main__":
    main()
