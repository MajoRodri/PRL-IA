"""Puente entre la colección Chroma de P2 y el contrato documental de P5.

MVP local de un proceso. SQLite publica la generación activa después de que
Chroma termine de escribirla. Todas las búsquedas deben pasar por este adaptador.
"""
from contextlib import contextmanager
import logging
import math
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Mapping, Sequence
from uuid import uuid4

from src.retrieval import Chunk, Hit, validate_filters

log = logging.getLogger(__name__)


def _and(conditions: list[dict]) -> dict:
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


class ChromaDocumentIndex:
    """Implementa DocumentIndex con relevancia = max(0, min(1, 1-distancia_coseno))."""

    def __init__(self, collection, manifest_path: Path, *, batch_size: int = 128):
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError("batch_size debe estar entre 1 y 1000.")
        # No asumir que una colección existente tiene la métrica solicitada al crearla.
        configuration = collection.configuration
        if (configuration.get("hnsw") or {}).get("space") != "cosine":
            raise ValueError("La colección debe usar distancia cosine; no se modifica automáticamente.")
        self.collection = collection
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self._lock = RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS binding (singleton INTEGER PRIMARY KEY CHECK(singleton=1), collection_id TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS active_generations (document_id TEXT PRIMARY KEY, generation TEXT NOT NULL)")
            bound = db.execute("SELECT collection_id FROM binding WHERE singleton=1").fetchone()
            if bound and bound[0] != str(collection.id):
                raise ValueError("Este catálogo corresponde a otra colección Chroma. Revisa las rutas.")
            db.execute("INSERT OR IGNORE INTO binding VALUES (1, ?)", (str(collection.id),))

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.manifest_path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _publish(self, document_id: str, generation: str) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO active_generations VALUES (?, ?) ON CONFLICT(document_id) DO UPDATE SET generation=excluded.generation", (document_id, generation))

    @staticmethod
    def _document_filter(document_id: str) -> dict:
        return _and([{"_p5_managed": True}, {"document_id": document_id}])

    def replace_document(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        chunks = list(chunks)
        if not chunks or any(c.document_id != document_id for c in chunks):
            raise ValueError("Se requieren fragmentos del mismo documento.")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Los identificadores de fragmento deben ser únicos.")
        generation = uuid4().hex
        with self._lock:
            try:
                for start in range(0, len(chunks), self.batch_size):
                    batch = chunks[start:start + self.batch_size]
                    metadatas = []
                    for chunk in batch:
                        metadata = {
                            "_p5_managed": True, "_p5_generation": generation,
                            "chunk_id": chunk.chunk_id, "document_id": document_id,
                            "source": chunk.source, "category": chunk.category,
                        }
                        # Chroma no necesita recibir claves sin valor. Se reconstruyen al leer.
                        if chunk.page is not None:
                            metadata["page"] = chunk.page
                        if chunk.section is not None:
                            metadata["section"] = chunk.section
                        metadatas.append(metadata)
                    self.collection.add(
                        ids=[f"p5:{generation}:{c.chunk_id}" for c in batch],
                        documents=[c.text for c in batch], metadatas=metadatas,
                    )
                self._publish(document_id, generation)
            except Exception:
                # La generación anterior sigue activa, aunque la limpieza también falle.
                try:
                    self.collection.delete(where={"_p5_generation": generation})
                except Exception:
                    log.warning("No se pudo limpiar una generación incompleta; permanece invisible.")
                raise
            # Una vez publicado, un fallo de limpieza NO revierte la nueva versión válida.
            self._prune(document_id, generation)

    def _prune(self, document_id: str, active_generation: str) -> None:
        try:
            self.collection.delete(where=_and([
                {"_p5_managed": True}, {"document_id": document_id},
                {"_p5_generation": {"$ne": active_generation}},
            ]))
        except Exception:
            log.warning("Quedan generaciones antiguas invisibles; reindexar o eliminar reintentará su limpieza.")

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            with self._connect() as db:
                db.execute("DELETE FROM active_generations WHERE document_id=?", (document_id,))
            # Si falla, el servicio mantiene estado deleting y permite volver a eliminar.
            self.collection.delete(where=self._document_filter(document_id))

    def search(self, query: str, *, limit: int, filters: Mapping[str, str | int]) -> list[Hit]:
        query = query.strip()
        if not query or len(query) > 2000:
            raise ValueError("Consulta vacía o demasiado larga.")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100.")
        filters = validate_filters(filters)
        with self._lock:
            with self._connect() as db:
                generations = [row[0] for row in db.execute("SELECT generation FROM active_generations")]
            if not generations:
                return []
            where = _and([
                {"_p5_managed": True}, {"_p5_generation": {"$in": generations}},
                *[{key: value} for key, value in filters.items()],
            ])
            # El count global limita n_results; where filtra ANTES del ranking.
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.query(query_texts=[query], n_results=min(limit, count),
                                            where=where, include=["documents", "metadatas", "distances"])
            hits = []
            for text, metadata, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0], strict=True):
                distance = float(distance)
                if not math.isfinite(distance) or not -1e-5 <= distance <= 2.00001:
                    raise ValueError("Distancia coseno inválida recibida del índice.")
                chunk = Chunk(
                    chunk_id=metadata["chunk_id"], document_id=metadata["document_id"],
                    text=text, source=metadata["source"], category=metadata["category"],
                    page=metadata.get("page"), section=metadata.get("section"),
                )
                hits.append(Hit(chunk, max(0.0, min(1.0, 1.0 - distance))))
            return sorted(hits, key=lambda h: (-h.score, h.chunk.chunk_id))
