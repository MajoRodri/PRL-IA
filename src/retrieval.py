"""Recuperación independiente de LangChain y del proveedor vectorial (persona 5)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Callable, Mapping, Protocol, Sequence
import unicodedata


FILTER_KEYS = {"document_id", "source", "page", "section", "category"}
STOPWORDS = set("a al algo como con cual de del el en es esta este la las lo los para por que se sin su un una y o debo debe cuales".split())


def tokens(text: str) -> set[str]:
    """Normalización solo para búsqueda demo; el fragmento original se conserva."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]+", normalized)) - STOPWORDS


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    source: str
    page: int | None = None
    section: str | None = None
    category: str = "general"

    def __post_init__(self) -> None:
        for value in (self.chunk_id, self.document_id, self.text, self.source, self.category):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("El fragmento requiere identificadores, texto, fuente y categoría.")
        if self.page is not None and (type(self.page) is not int or self.page < 1):
            raise ValueError("La página debe ser un entero positivo o None.")


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("El adaptador debe devolver relevancia finita entre 0 y 1.")


class SearchIndex(Protocol):
    """Contrato P2: mayor score = más relevante; filtros antes de truncar."""

    def search(self, query: str, *, limit: int, filters: Mapping[str, str | int]) -> Sequence[Hit]: ...


class DocumentIndex(SearchIndex, Protocol):
    """replace_document debe ser atómico: éxito completo o índice anterior intacto."""

    def replace_document(self, document_id: str, chunks: Sequence[Chunk]) -> None: ...
    def delete_document(self, document_id: str) -> None: ...


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    hits: tuple[Hit, ...]
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "sources": [{**asdict(hit.chunk), "score": hit.score} for hit in self.hits],
            "has_context": bool(self.hits),
            "reason": self.reason,
        }


def validate_filters(filters: Mapping[str, str | int] | None) -> dict[str, str | int]:
    result = dict(filters or {})
    if result.keys() - FILTER_KEYS:
        raise ValueError("Filtro no permitido. Usa document_id, source, page, section o category.")
    for key, value in result.items():
        if key == "page":
            if type(value) is not int or value < 1:
                raise ValueError("page debe ser un entero positivo.")
        elif not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError("Los filtros de texto deben tener entre 1 y 200 caracteres.")
    return result


class Retriever:
    """Filtra, ordena, elimina duplicados y conserva las fuentes de los resultados."""

    def __init__(self, index: SearchIndex, *, is_visible: Callable[[str], bool] | None = None):
        self.index = index
        self.is_visible = is_visible or (lambda document_id: True)

    def retrieve(self, query: str, *, k: int = 4, min_score: float = 0.25,
                 filters: Mapping[str, str | int] | None = None) -> RetrievalResult:
        query = query.strip()
        if not query or len(query) > 2000:
            raise ValueError("La consulta debe tener entre 1 y 2000 caracteres.")
        if type(k) is not int or not 1 <= k <= 20:
            raise ValueError("k debe ser un entero entre 1 y 20.")
        if not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise ValueError("min_score debe estar entre 0 y 1.")
        filters = validate_filters(filters)
        # Sobremuestreo acotado: puede haber duplicados o documentos no visibles.
        candidates = self.index.search(query, limit=min(100, k * 5), filters=filters)
        selected: list[Hit] = []
        seen: set[tuple] = set()
        for hit in sorted(candidates, key=lambda h: (-h.score, h.chunk.chunk_id)):
            c = hit.chunk
            if hit.score <= 0 or hit.score < min_score or not self.is_visible(c.document_id):
                continue
            # Defensa ante adaptadores que incumplan el filtro solicitado.
            if any(getattr(c, key) != value for key, value in filters.items()):
                continue
            identity = (c.document_id, c.page, " ".join(c.text.casefold().split()))
            if identity in seen:
                continue
            seen.add(identity)
            selected.append(hit)
            if len(selected) == k:
                break
        return RetrievalResult(query, tuple(selected), None if selected else "no_relevant_context")
