"""Pruebas del segundo tramo del pipeline: fragmentación y trazabilidad.

Comprueba límites de tamaño, overlap, secciones, índices e identificadores de
los chunks, además de fijar la configuración elegida por el benchmark.

Posición en el flujo: valida ``src.chunking`` después de la ingesta y antes de
que los fragmentos sean enviados al modelo de embeddings y al vector store.
"""

from __future__ import annotations

import unittest

from src.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, split_documents


class SplitDocumentsTests(unittest.TestCase):
    def test_configuracion_por_defecto_procede_del_benchmark(self) -> None:
        self.assertEqual(1000, DEFAULT_CHUNK_SIZE)
        self.assertEqual(200, DEFAULT_CHUNK_OVERLAP)

    def test_splits_long_text_and_preserves_traceability(self) -> None:
        text = "SECCION 1. MEDIDAS PREVENTIVAS\n\n" + " ".join(
            f"Medida preventiva numero {number}." for number in range(40)
        )
        documents = [
            {
                "text": text,
                "metadata": {
                    "document": "guia-electrica.pdf",
                    "source": "data/raw/guia-electrica.pdf",
                    "page": 7,
                    "file_type": "pdf",
                },
            }
        ]

        chunks = split_documents(documents, chunk_size=220, chunk_overlap=40)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk["text"]) <= 220 for chunk in chunks))
        self.assertEqual(
            list(range(1, len(chunks) + 1)),
            [chunk["metadata"]["chunk_index"] for chunk in chunks],
        )
        for chunk in chunks:
            metadata = chunk["metadata"]
            self.assertEqual("guia-electrica.pdf", metadata["document"])
            self.assertEqual(7, metadata["page"])
            self.assertEqual(len(chunks), metadata["chunk_total"])
            self.assertIn("chunk_id", metadata)
            self.assertIn("char_start", metadata)
            self.assertIn("char_end", metadata)
        self.assertEqual("SECCION 1. MEDIDAS PREVENTIVAS", chunks[0]["metadata"]["section"])

    def test_overlap_keeps_context_between_adjacent_chunks(self) -> None:
        text = " ".join(f"palabra{number:02d}" for number in range(60))
        chunks = split_documents(
            [{"text": text, "metadata": {"document": "prueba.txt", "page": 1}}],
            chunk_size=120,
            chunk_overlap=30,
        )

        first = chunks[0]["metadata"]
        second = chunks[1]["metadata"]
        self.assertLess(second["char_start"], first["char_end"])
        shared_start = second["char_start"]
        shared_end = first["char_end"]
        self.assertEqual(text[shared_start:shared_end], chunks[0]["text"][-(shared_end-shared_start):])
        self.assertTrue(chunks[1]["text"].startswith(text[shared_start:shared_end]))

    def test_rejects_invalid_configuration_and_contract(self) -> None:
        valid = [{"text": "Texto", "metadata": {"document": "a.txt", "page": 1}}]
        with self.assertRaises(ValueError):
            split_documents(valid, chunk_size=100, chunk_overlap=100)
        with self.assertRaises(ValueError):
            split_documents([{"text": "Texto", "metadata": {"document": "a.txt"}}])


if __name__ == "__main__":
    unittest.main()
