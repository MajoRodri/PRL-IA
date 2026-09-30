"""Pruebas del primer tramo del pipeline: carga, limpieza y metadatos.

Construye documentos temporales y comprueba PDF multipágina, TXT, Markdown,
manifiesto, errores de formato y ausencia de texto extraíble.

Posición en el flujo: valida ``src.ingestion`` antes de entregar sus documentos
a la fase de chunking; no utiliza todavía embeddings ni base vectorial.
"""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.ingestion import (
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    clean_text,
    load_corpus,
    load_document,
)


def _write_text_pdf(path: Path, page_texts: list[str]) -> None:
    """Crea un PDF mínimo con texto para probar la extracción real de pypdf."""

    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)

    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_reference}
                )
            }
        )
        content = DecodedStreamObject()
        safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.set_data(f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)

    with path.open("wb") as stream:
        writer.write(stream)


class CleanTextTests(unittest.TestCase):
    def test_normalizes_noise_without_removing_structure(self) -> None:
        source = "ARTICULO 1\n\nEl trabaja-\ndor   usara casco.\n\n- Primer punto\n- Segundo punto"
        cleaned = clean_text(source)

        self.assertIn("ARTICULO 1", cleaned)
        self.assertIn("El trabajador usara casco.", cleaned)
        self.assertIn("- Primer punto", cleaned)
        self.assertNotIn("  ", cleaned)


class LoadDocumentTests(unittest.TestCase):
    def test_loads_pdf_and_keeps_one_based_page_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normativa.pdf"
            _write_text_pdf(path, ["Texto pagina uno", "Texto pagina dos"])

            documents = load_document(path)

        self.assertEqual(2, len(documents))
        self.assertEqual([1, 2], [item["metadata"]["page"] for item in documents])
        self.assertEqual("normativa.pdf", documents[0]["metadata"]["document"])
        self.assertIn("Texto pagina dos", documents[1]["text"])

    def test_loads_utf8_text_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            txt_path = Path(directory) / "medidas.txt"
            md_path = Path(directory) / "guia.md"
            txt_path.write_text("Proteccion colectiva.\n", encoding="utf-8")
            md_path.write_text("# EPI\n\nUso obligatorio.", encoding="utf-8")

            txt = load_document(txt_path)
            markdown = load_document(md_path)

        self.assertEqual("txt", txt[0]["metadata"]["file_type"])
        self.assertEqual("markdown", markdown[0]["metadata"]["file_type"])
        self.assertEqual(1, markdown[0]["metadata"]["page"])

    def test_rejects_missing_and_unsupported_files(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_document("no-existe.pdf")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "imagen.jpg"
            path.write_bytes(b"not an image")
            with self.assertRaises(UnsupportedDocumentTypeError):
                load_document(path)

    def test_rejects_empty_text_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vacio.txt"
            path.write_text(" \n\t", encoding="utf-8")
            with self.assertRaises(EmptyDocumentError):
                load_document(path)

    def test_loads_manifest_and_enriches_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_directory = Path(directory)
            raw_directory = data_directory / "raw"
            raw_directory.mkdir()
            (raw_directory / "norma.txt").write_text("Contenido preventivo", encoding="utf-8")
            manifest = {
                "corpus": "Corpus de prueba",
                "documents": [
                    {
                        "id": "norma-1",
                        "filename": "norma.txt",
                        "title": "Norma de prueba",
                        "publisher": "Organismo oficial",
                        "document_type": "legislation",
                        "legal_status": "Texto oficial",
                        "landing_page": "https://example.test/norma",
                    }
                ],
            }
            manifest_path = data_directory / "sources.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            documents = load_corpus(manifest_path)

        metadata = documents[0]["metadata"]
        self.assertEqual("norma-1", metadata["source_id"])
        self.assertEqual("Norma de prueba", metadata["title"])
        self.assertEqual("Corpus de prueba", metadata["corpus"])
        self.assertEqual("https://example.test/norma", metadata["source_url"])


if __name__ == "__main__":
    unittest.main()
