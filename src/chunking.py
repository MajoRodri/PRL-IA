"""Divide en fragmentos trazables los documentos ya cargados y limpiados.

Entrada: documentos por página producidos por ``src.ingestion``. Salida: chunks
con solapamiento, posiciones, sección, página e identificador único, listos para
que Persona 2 genere embeddings y los almacene en la base vectorial.

Posición en el flujo: se ejecuta después de la ingesta y antes del vector store.
Sus valores por defecto proceden del benchmark de ``scripts/evaluate_chunking``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, TypeAlias


Document: TypeAlias = dict[str, Any]
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Detecta posibles encabezados: títulos Markdown con 1 a 6 almohadillas,
# títulos en mayúsculas con numeración opcional y líneas que comienzan
# por capítulo, sección, artículo, anexo o apéndice.
_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+|(?:\d+(?:\.\d+)*\.?\s+)?[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00dc\u00d1][A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00dc\u00d1\s,;:()/-]{3,}|"
    r"(?i:(?:cap[i\u00ed]tulo|secci[o\u00f3]n|art[i\u00ed]culo|anexo|ap[e\u00e9]ndice)\b.*))$"
)


def _validate_settings(chunk_size: int, chunk_overlap: int) -> None:
    """Comprueba que el tamaño y el solapamiento formen una ventana válida."""

    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap no puede ser negativo")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap debe ser menor que chunk_size")


def _find_boundary(text: str, start: int, maximum_end: int) -> int:
    """Prioriza un corte semántico cercano al límite o corta en el máximo."""

    if maximum_end >= len(text):
        return len(text)

    minimum_end = start + max(1, int((maximum_end - start) * 0.55))
    window = text[minimum_end:maximum_end]
    # Se intenta cortar por párrafo, frase y espacio, en ese orden.
    boundary_patterns = (
        re.compile(r"\n\n+"),
        re.compile(r"(?<=[.!?;:])\s+"),
        re.compile(r"\s+"),
    )
    for pattern in boundary_patterns:
        matches = list(pattern.finditer(window))
        if matches:
            return minimum_end + matches[-1].end()
    return maximum_end


def _heading_positions(text: str) -> list[tuple[int, str]]:
    """Localiza encabezados probables junto con su posición en el texto."""

    headings: list[tuple[int, str]] = []
    position = 0
    for block in text.split("\n\n"):
        stripped = block.strip()
        if stripped and len(stripped) <= 160 and _HEADING_RE.match(stripped):
            headings.append((position, stripped.lstrip("# ").strip()))
        position += len(block) + 2
    return headings


def _section_at(headings: list[tuple[int, str]], position: int) -> str | None:
    """Devuelve el último encabezado anterior a una posición del texto."""

    section: str | None = None
    for heading_position, heading in headings:
        if heading_position > position:
            break
        section = heading
    return section


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[dict[str, Any]]:
    """Divide un texto y conserva las posiciones originales de cada fragmento."""

    chunks: list[dict[str, Any]] = []
    headings = _heading_positions(text)
    start = 0

    while start < len(text):
        maximum_end = min(len(text), start + chunk_size)
        end = _find_boundary(text, start, maximum_end)
        raw = text[start:end]
        leading_spaces = len(raw) - len(raw.lstrip())
        trailing_spaces = len(raw) - len(raw.rstrip())
        content_start = start + leading_spaces
        content_end = end - trailing_spaces
        content = text[content_start:content_end]
        if content:
            chunks.append(
                {
                    "text": content,
                    "char_start": content_start,
                    "char_end": content_end,
                    "section": _section_at(headings, content_start),
                }
            )
        if end >= len(text):
            break
        # Retrocede el solapamiento configurado para conservar contexto entre chunks.
        next_start = end - chunk_overlap
        start = max(start + 1, next_start)

    return chunks


def _document_slug(document_name: str) -> str:
    """Genera una parte legible y estable para el identificador del chunk."""

    stem = Path(document_name).stem
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_stem).strip("_").lower()
    return slug or "documento"


def split_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Fragmenta documentos por página y añade metadatos auditables y estables.

    Formato de entrada requerido::

        {"text": "...", "metadata": {"document": "file.pdf", "page": 1}}
    """

    _validate_settings(chunk_size, chunk_overlap)
    chunks: list[Document] = []

    for document in documents:
        text = document.get("text")
        metadata = document.get("metadata")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Cada documento debe contener un campo 'text' no vacio")
        if not isinstance(metadata, dict):
            raise ValueError("Cada documento debe contener un diccionario 'metadata'")
        if "document" not in metadata or "page" not in metadata:
            raise ValueError("Los metadatos deben incluir 'document' y 'page'")

        for part in _split_text(text, chunk_size, chunk_overlap):
            chunk_metadata = dict(metadata)
            chunk_metadata.update(
                {
                    "char_start": part["char_start"],
                    "char_end": part["char_end"],
                }
            )
            if part["section"]:
                chunk_metadata["section"] = part["section"]
            chunks.append({"text": part["text"], "metadata": chunk_metadata})

    totals: dict[str, int] = {}
    positions: dict[str, int] = {}
    # Primero se calcula el total para poder incluirlo en todos los metadatos.
    for chunk in chunks:
        document_name = str(chunk["metadata"]["document"])
        totals[document_name] = totals.get(document_name, 0) + 1

    # Después se asignan índices correlativos e identificadores únicos por documento.
    for chunk in chunks:
        metadata = chunk["metadata"]
        document_name = str(metadata["document"])
        positions[document_name] = positions.get(document_name, 0) + 1
        index = positions[document_name]
        page = int(metadata["page"])
        metadata.update(
            {
                "chunk_id": f"{_document_slug(document_name)}_p{page:04d}_c{index:04d}",
                "chunk_index": index,
                "chunk_total": totals[document_name],
            }
        )

    return chunks
