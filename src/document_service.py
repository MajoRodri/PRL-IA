"""Servicio documental y adaptadores de demostración. No requiere LLM ni Chroma."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Mapping, Protocol, Sequence
from uuid import uuid4

from src.retrieval import Chunk, DocumentIndex, Hit, Retriever, tokens

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DocumentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class DocumentProcessor(Protocol):
    """P1 adapta sus funciones de lectura y chunking a esta firma."""

    def process(self, path: Path, *, document_id: str, source: str,
                category: str) -> Sequence[Chunk]: ...


class DemoProcessor:
    """Baseline sustituible: PDF con texto/TXT UTF-8, 180 palabras, overlap 30."""

    def __init__(self, chunk_size: int = 180, overlap: int = 30):
        if not 0 <= overlap < chunk_size:
            raise ValueError("Se requiere 0 <= overlap < chunk_size.")
        self.chunk_size, self.overlap = chunk_size, overlap

    def process(self, path: Path, *, document_id: str, source: str,
                category: str) -> list[Chunk]:
        if path.suffix.lower() == ".txt":
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeError as exc:
                raise DocumentError("El TXT debe estar codificado en UTF-8.", 422) from exc
            if "\x00" in text:
                raise DocumentError("El TXT contiene caracteres binarios.", 422)
            pages = [(None, text)]
        else:
            from pypdf import PdfReader
            try:
                reader = PdfReader(path)
                if reader.is_encrypted:
                    raise DocumentError("No se admiten PDF cifrados.", 422)
                if len(reader.pages) > 300:
                    raise DocumentError("La demo admite como máximo 300 páginas.", 422)
                pages = [(n, page.extract_text() or "") for n, page in enumerate(reader.pages, 1)]
            except DocumentError:
                raise
            except Exception as exc:
                raise DocumentError("No se pudo leer el PDF.", 422) from exc
        chunks = []
        for page, text in pages:
            words = text.split()
            for start in range(0, len(words), self.chunk_size - self.overlap):
                part = words[start:start + self.chunk_size]
                chunks.append(Chunk(f"{document_id}:{len(chunks)}", document_id,
                                    " ".join(part), source, page=page, category=category))
                if start + self.chunk_size >= len(words):
                    break
        if not chunks:
            raise DocumentError("Documento sin texto extraíble; la demo no incluye OCR.", 422)
        return chunks


class SQLiteDemoIndex:
    """Índice léxico persistente para probar contratos; NO es búsqueda semántica."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS demo_chunks (chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, payload TEXT NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS demo_document ON demo_chunks(document_id)")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def replace_document(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        chunks = list(chunks)
        if not chunks or any(c.document_id != document_id for c in chunks):
            raise ValueError("Los fragmentos deben pertenecer al documento y no estar vacíos.")
        with self._connect() as conn:
            conn.execute("DELETE FROM demo_chunks WHERE document_id = ?", (document_id,))
            conn.executemany("INSERT INTO demo_chunks VALUES (?, ?, ?)",
                             [(c.chunk_id, c.document_id, json.dumps(asdict(c), ensure_ascii=False)) for c in chunks])

    def delete_document(self, document_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM demo_chunks WHERE document_id = ?", (document_id,))

    def search(self, query: str, *, limit: int, filters: Mapping[str, str | int]) -> list[Hit]:
        query_tokens = tokens(query)
        if not query_tokens:
            return []
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM demo_chunks").fetchall()
        matches = []
        for (payload,) in rows:
            chunk = Chunk(**json.loads(payload))
            if any(getattr(chunk, key) != value for key, value in filters.items()):
                continue
            score = len(query_tokens & tokens(chunk.text)) / len(query_tokens)
            if score > 0:
                matches.append(Hit(chunk, score))
        return sorted(matches, key=lambda h: (-h.score, h.chunk.chunk_id))[:limit]


class DocumentService:
    """Catálogo SQLite + originales locales + procesador e índice intercambiables.

    MVP de un proceso. Estados no indexados nunca aportan contexto al recuperador.
    Si hay un corte entre sistemas, reindexar o eliminar permite recuperar el estado.
    """

    def __init__(self, storage_dir: Path, *, processor: DocumentProcessor | None = None,
                 index: DocumentIndex | None = None, max_bytes: int = MAX_UPLOAD_BYTES):
        self.storage_dir = Path(storage_dir).resolve()
        self.raw_dir = self.storage_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "documents.sqlite3"
        self.processor = processor or DemoProcessor()
        self.index = index or SQLiteDemoIndex(self.db_path)
        self.max_bytes = max_bytes
        self._lock = RLock()
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored_name TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE, category TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL, chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT)""")
            # Recuperación tras un cierre inesperado. No anunciar como indexado algo incierto.
            conn.execute("UPDATE documents SET status='failed', error='Proceso interrumpido; reindexa el documento.' WHERE status='processing'")
        self.retriever = Retriever(self.index, is_visible=self.is_visible)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _public(row) -> dict:
        return {k: row[k] for k in row.keys() if k != "stored_name"}

    def get(self, document_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if row is None:
            raise DocumentError("Documento no encontrado.", 404)
        return self._public(row)

    def list(self) -> list[dict]:
        with self._connect() as conn:
            return [self._public(row) for row in conn.execute("SELECT * FROM documents ORDER BY created_at, document_id")]

    def is_visible(self, document_id: str) -> bool:
        try:
            return self.get(document_id)["status"] == "indexed"
        except DocumentError:
            return False

    def _set_status(self, document_id: str, status: str, *, count: int = 0, error: str | None = None):
        with self._connect() as conn:
            conn.execute("UPDATE documents SET status=?, chunk_count=?, error=?, updated_at=? WHERE document_id=?",
                         (status, count, error, self._now(), document_id))

    def upload(self, filename: str, content: bytes, *, category: str = "general") -> dict:
        if not filename or len(filename) > 180 or any(c in filename for c in ('/', '\\', '\x00')) or any(ord(c) < 32 for c in filename):
            raise DocumentError("Nombre de archivo no válido.")
        extension = Path(filename).suffix.lower()
        if extension not in {".pdf", ".txt"}:
            raise DocumentError("Solo se admiten PDF y TXT.", 415)
        if not content:
            raise DocumentError("El archivo está vacío.", 422)
        if len(content) > self.max_bytes:
            raise DocumentError("El archivo supera el tamaño permitido.", 413)
        if extension == ".pdf" and not content.startswith(b"%PDF-"):
            raise DocumentError("El archivo no tiene una cabecera PDF válida.", 422)
        category = category.strip()
        if not category or len(category) > 80:
            raise DocumentError("La categoría debe tener entre 1 y 80 caracteres.", 422)
        digest = hashlib.sha256(content).hexdigest()
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute("SELECT document_id FROM documents WHERE sha256=?", (digest,)).fetchone()
            if existing:
                raise DocumentError(f"Contenido ya registrado: {existing['document_id']}. Consulta su estado o reindexa.", 409)
            document_id = uuid4().hex
            stored_name = document_id + extension
            path = self.raw_dir / stored_name
            path.write_bytes(content)
            now = self._now()
            try:
                with self._connect() as conn:
                    conn.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, 'processing', 0, ?, ?, NULL)",
                                 (document_id, filename, stored_name, digest, category, len(content), now, now))
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return self._process(document_id, path)

    def _process(self, document_id: str, path: Path) -> dict:
        record = self.get(document_id)
        try:
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise DocumentError("El original no está disponible o ha cambiado.", 409)
            chunks = list(self.processor.process(path, document_id=document_id,
                                                source=record["filename"], category=record["category"]))
            if not chunks or len({c.chunk_id for c in chunks}) != len(chunks):
                raise ValueError("Fragmentos vacíos o identificadores repetidos.")
            if any(c.document_id != document_id or c.source != record["filename"] or c.category != record["category"] for c in chunks):
                raise ValueError("El procesador no conserva los metadatos acordados.")
            self.index.replace_document(document_id, chunks)
            self._set_status(document_id, "indexed", count=len(chunks))
        except Exception as exc:
            message = str(exc) if isinstance(exc, DocumentError) else "Fallo de procesamiento o indexación; revisa el adaptador y reintenta."
            self._set_status(document_id, "failed", error=message)
            # Se conserva el original para poder reintentar sin una nueva carga.
        return self.get(document_id)

    def reindex(self, document_id: str) -> dict:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
            if row is None:
                raise DocumentError("Documento no encontrado.", 404)
            if row["status"] == "deleting":
                raise DocumentError("La eliminación está pendiente; vuelve a eliminar.", 409)
            self._set_status(document_id, "processing")
            return self._process(document_id, self.raw_dir / row["stored_name"])

    def delete(self, document_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
            if row is None:
                raise DocumentError("Documento no encontrado.", 404)
            self._set_status(document_id, "deleting")
            try:
                self.index.delete_document(document_id)
                (self.raw_dir / row["stored_name"]).unlink(missing_ok=True)
                with self._connect() as conn:
                    conn.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
            except Exception as exc:
                raise DocumentError("Eliminación incompleta; el documento queda oculto. Reintenta.", 503) from exc

    def search(self, query: str, **kwargs):
        with self._lock:
            return self.retriever.retrieve(query, **kwargs)
