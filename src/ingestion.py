"""Carga, valida y limpia los documentos que forman el corpus de PRL.

Entrada: rutas individuales o el manifiesto ``data/sources.json`` con los PDF,
TXT o Markdown descargados en ``data/raw``. Salida: documentos separados por
página, con texto limpio y metadatos de trazabilidad.

Posición en el flujo: es la primera transformación de datos. Se ejecuta después
de descargar el corpus y antes de ``src/chunking.py``. El contrato utiliza
diccionarios simples para no acoplar la ingesta a LangChain o ChromaDB.
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any, Iterable, TypeAlias

from pypdf import PdfReader
from pypdf.errors import PdfReadError


Document: TypeAlias = dict[str, Any]
SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt", ".md", ".markdown"})


class IngestionError(RuntimeError):
    """Excepción base para errores que impiden cargar un documento."""


class UnsupportedDocumentTypeError(IngestionError):
    """Indica que la extensión de entrada no es compatible con el pipeline."""


class EmptyDocumentError(IngestionError):
    """Indica que un documento no contiene texto que se pueda extraer."""

# Detecta líneas que empiezan con una viñeta (-, *, +, •, ▪, ●)
# o con una enumeración (1., 2), a., b)), seguida de un espacio.
_BULLET_RE = re.compile(r"^(?:[-*+\u2022\u25aa\u25cf]|\d+[.)]|[a-zA-Z][.)])\s+")


# Detecta posibles encabezados que comienzan por capítulo, sección,
# artículo, anexo o apéndice, con o sin tilde y sin distinguir mayúsculas.
_HEADING_RE = re.compile(
    r"^(?:cap[i\u00ed]tulo|secci[o\u00f3]n|art[i\u00ed]culo|anexo|ap[e\u00e9]ndice)\b",
    re.IGNORECASE,
)


def _looks_like_heading(line: str) -> bool:
    """Determina si una línea corta parece un encabezado estructural."""

    if len(line) > 140:
        return False
    letters = [character for character in line if character.isalpha()]
    mostly_uppercase = bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.8
    return mostly_uppercase or bool(_HEADING_RE.match(line))


def clean_text(text: str) -> str:
    """Normaliza el ruido de extracción conservando títulos, listas y párrafos.

    La limpieza no elimina encabezados, números de artículo ni marcadores de
    lista porque esos elementos aportan significado en normas y guías técnicas.
    """

    if not text:
        return ""

# Normaliza el texto: unifica los saltos de línea, convierte los espacios
# de no separación en espacios normales y elimina guiones opcionales
# y espacios de ancho cero.

    normalized = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\f", "\n")
        .replace("\u00a0", " ")
        .replace("\u00ad", "")
        .replace("\u200b", "")
    )
    # Une palabras partidas únicamente porque una línea del PDF acaba en guion.
    normalized = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", normalized)

    blocks: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        # Agrupa las líneas consecutivas de un mismo párrafo y evita saltos
        # artificiales generados por la maquetación del PDF.
        if paragraph_lines:
            blocks.append(" ".join(paragraph_lines))
            paragraph_lines.clear()

    for raw_line in normalized.split("\n"):
        line = re.sub(r"[\t\v ]+", " ", raw_line).strip()
        if not line:
            flush_paragraph()
            continue
        if _BULLET_RE.match(line) or _looks_like_heading(line):
            flush_paragraph()
            blocks.append(line)
        else:
            paragraph_lines.append(line)

    flush_paragraph()
    return "\n\n".join(blocks).strip()


def _base_metadata(path: Path, *, page: int, file_type: str) -> dict[str, Any]:
    return {
        "document": path.name,
        "source": str(path.resolve()),
        "page": page,
        "file_type": file_type,
    }


def _load_pdf(path: Path) -> list[Document]:
    """Extrae el texto de un PDF y crea un documento por página con contenido."""

    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestionError(f"El PDF está cifrado y requiere contraseña: {path}")
    except (OSError, PdfReadError, ValueError) as exc:
        raise IngestionError(f"No se pudo leer el PDF '{path}': {exc}") from exc

    documents: list[Document] = []
    # La numeración empieza en uno para que coincida con la página visible al usuario.
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = clean_text(page.extract_text() or "")
        except Exception as exc:  # pypdf puede exponer errores de flujos PDF mal formados.
            raise IngestionError(
                f"No se pudo extraer la página {page_number} de '{path}': {exc}"
            ) from exc
        if not text:
            continue
        documents.append(
            {
                "text": text,
                "metadata": _base_metadata(path, page=page_number, file_type="pdf"),
            }
        )

    if not documents:
        raise EmptyDocumentError(
            f"El PDF no contiene texto extraible (puede ser un escaneo sin OCR): {path}"
        )
    return documents


def _read_text_file(path: Path) -> str:
    """Lee texto probando las codificaciones más habituales en documentos españoles."""

    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 puede decodificar cualquier byte; esta salida es solo defensiva.
    raise IngestionError(f"No se pudo detectar la codificación de '{path}'")


def _load_text(path: Path) -> list[Document]:
    """Carga un TXT o Markdown como un único documento equivalente a la página 1."""

    try:
        text = clean_text(_read_text_file(path))
    except OSError as exc:
        raise IngestionError(f"No se pudo leer el archivo '{path}': {exc}") from exc
    if not text:
        raise EmptyDocumentError(f"El documento está vacío: {path}")
    return [
        {
            "text": text,
            "metadata": _base_metadata(
                path,
                page=1,
                file_type="markdown" if path.suffix.lower() in {".md", ".markdown"} else "txt",
            ),
        }
    ]


def load_document(path: str | Path) -> list[Document]:
    """Carga un PDF, TXT o Markdown en documentos separados por página.

    Las páginas PDF empiezan en uno. Los formatos de texto usan la página 1 para
    mantener metadatos escalares y compatibles con bases de datos vectoriales.
    """

    document_path = Path(path).expanduser()
    if not document_path.exists():
        raise FileNotFoundError(f"No existe el documento: {document_path}")
    if not document_path.is_file():
        raise IngestionError(f"La ruta no es un archivo: {document_path}")

    extension = document_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedDocumentTypeError(
            f"Formato no compatible '{extension or '<sin extension>'}'. Admitidos: {supported}"
        )
    if extension == ".pdf":
        return _load_pdf(document_path)
    return _load_text(document_path)


def load_documents(paths: Iterable[str | Path]) -> list[Document]:
    """Carga varios documentos conservando el orden recibido."""

    loaded: list[Document] = []
    for path in paths:
        loaded.extend(load_document(path))
    return loaded


def load_corpus(
    manifest_path: str | Path,
    documents_dir: str | Path | None = None,
) -> list[Document]:
    """Carga el manifiesto completo y enriquece los metadatos de cada página.

    Por defecto, busca los archivos en una carpeta ``raw`` situada junto al
    manifiesto JSON (por ejemplo, ``data/sources.json`` -> ``data/raw``).
    """

    manifest = Path(manifest_path).expanduser()
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(f"No se pudo leer el manifiesto '{manifest}': {exc}") from exc

    entries = payload.get("documents")
    if not isinstance(entries, list):
        raise IngestionError("El manifiesto debe contener una lista 'documents'")

    raw_directory = Path(documents_dir) if documents_dir is not None else manifest.parent / "raw"
    corpus_name = payload.get("corpus")
    loaded: list[Document] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
            raise IngestionError("Cada entrada del manifiesto debe incluir 'filename'")
        pages = load_document(raw_directory / entry["filename"])
        # Solo se propagan campos declarados y útiles para la trazabilidad.
        extra_metadata = {
            key: entry[key]
            for key in (
                "id",
                "title",
                "publisher",
                "document_type",
                "legal_status",
                "landing_page",
            )
            if entry.get(key) is not None
        }
        if "id" in extra_metadata:
            extra_metadata["source_id"] = extra_metadata.pop("id")
        if "landing_page" in extra_metadata:
            extra_metadata["source_url"] = extra_metadata.pop("landing_page")
        if corpus_name:
            extra_metadata["corpus"] = corpus_name
        # Cada página hereda la información oficial de su fuente antes del chunking.
        for page in pages:
            page["metadata"].update(extra_metadata)
        loaded.extend(pages)
    return loaded
