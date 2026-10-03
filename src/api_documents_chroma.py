"""Arranque P2+P5: uvicorn src.api_documents_chroma:create_app --factory.

Importar este módulo no descarga modelos; la inicialización ocurre al arrancar.
P2 sigue cargando Sentence Transformers al importar vector_store.
"""
from pathlib import Path
import os

from src.api_documents import create_app as create_document_app
from src.chroma_adapter import ChromaDocumentIndex
from src.document_service import DocumentService


def create_app():
    root = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != root:
        raise RuntimeError("Arranca desde la raíz de PRL-IA para respetar ./chroma_db de P2.")
    from src import vector_store
    if not callable(getattr(vector_store, "get_collection", None)):
        raise RuntimeError("Falta la implementación de P2 en src/vector_store.py; integra su versión antes de arrancar.")
    collection = vector_store.get_collection()
    configured = Path(os.getenv("PRL_CHROMA_DOCUMENTS_DIR", "data/persona5/chroma_integration"))
    directory = configured if configured.is_absolute() else root / configured
    index = ChromaDocumentIndex(collection, directory / "active_generations.sqlite3")
    service = DocumentService(directory, index=index)
    application = create_document_app(service=service)
    application.title = "PRL-IA | Documentos con Chroma (P2 + P5)"
    application.description = (
        "Índice Chroma y embeddings de P2 conectados al servicio P5. "
        "Procesador demo PDF/TXT; no incluye LLM. Un único proceso/worker."
    )
    return application
