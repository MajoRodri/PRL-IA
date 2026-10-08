"""
vector_store.py
Módulo responsable del almacenamiento y recuperación semántica de fragmentos
de documentos de Prevención de Riesgos Laborales (PRL Assistant).

Responsable: Persona 2 - Embeddings y base de datos vectorial

Modelo de embeddings elegido: all-MiniLM-L6-v2 (sentence-transformers)
Justificación: modelo ligero, gratuito y ejecutable en local (sin depender de
APIs externas de pago), con muy buen equilibrio entre velocidad y calidad
semántica para colecciones de tamaño pequeño/medio como la de este proyecto.
Al ejecutarse localmente, evita enviar contenido documental a terceros,
lo cual refuerza la privacidad de la información de la empresa.
"""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PERSIST_DIR = str(_PROJECT_ROOT / "chroma_db")
COLLECTION_NAME = "prl_documentos"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL_NAME
)


_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


def get_client():
    """Devuelve el cliente de ChromaDB (instancia única, creada al importar el módulo)."""
    return _client


def get_collection():
    """
    Obtiene la colección 'prl_documentos', creándola si no existe todavía.
    Reutiliza el cliente único del módulo en lugar de abrir una conexión nueva
    en cada llamada, evitando el coste de inicialización repetido.
    """
    collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_function,
        metadata={"hnsw:space": "cosine"}
    )
    return collection

def add_fragments(fragments):
    """
    Guarda una lista de fragmentos de texto en la colección vectorial.

    Cada fragmento debe ser un diccionario con esta estructura:
        {
            "id": "identificador_unico_del_fragmento",
            "text": "contenido del fragmento",
            "metadata": {
                "source": "nombre_del_documento.pdf",
                "page": 3,
                "section": "Equipos de protección individual"
            }
        }

    Esta es la interfaz que debe respetar el módulo de ingesta (Persona 1)
    para que sus fragmentos se puedan indexar aquí sin cambios.
    """
    if not fragments:
        raise ValueError("La lista de fragmentos está vacía, no hay nada que guardar.")

    ids = [f["id"] for f in fragments]
    texts = [f["text"] for f in fragments]
    metadatas = [f["metadata"] for f in fragments]

    collection = get_collection()
    collection.add(ids=ids, documents=texts, metadatas=metadatas)

    return len(fragments)

def search(query, k=4):
    """
    Busca los k fragmentos más relevantes semánticamente para una consulta.

    Args:
        query (str): la pregunta o texto de búsqueda en lenguaje natural.
        k (int): número de fragmentos a recuperar (por defecto 4).

    Returns:
        list[dict]: lista de resultados, cada uno con esta forma:
            {
                "text": "contenido del fragmento",
                "metadata": {"source": ..., "page": ..., "section": ...},
                "distance": 0.1234
            }
        La lista puede venir vacía si la colección no tiene documentos.
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[query], n_results=k)

    fragments = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for text, metadata, distance in zip(documents, metadatas, distances):
        fragments.append({
            "text": text,
            "metadata": metadata,
            "distance": distance
        })

    return fragments