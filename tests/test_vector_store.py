"""Pruebas del modulo de almacenamiento y recuperacion vectorial.

Verifica que el cliente de ChromaDB se reutiliza como instancia unica (sin
reconexiones por llamada), que la coleccion se crea con la configuracion
esperada, y que ``add_fragments``/``search`` respetan el contrato de datos
acordado con el modulo de ingesta (Persona 1) y con el orquestador RAG.

Posicion en el flujo: valida ``src.vector_store`` como frontera entre los
fragmentos ya troceados (``src.chunking``) y la recuperacion semantica que
consume el resto de la aplicacion; no ejecuta ChromaDB real, todo se mockea.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src import vector_store


class GetClientTests(unittest.TestCase):
    def test_returns_same_instance_on_repeated_calls(self) -> None:
        first = vector_store.get_client()
        second = vector_store.get_client()

        self.assertIs(first, second)

    @patch("src.vector_store.chromadb.PersistentClient")
    def test_module_does_not_create_a_new_client_per_call(self, mock_persistent_client) -> None:
        vector_store.get_client()
        vector_store.get_client()
        vector_store.get_client()

        mock_persistent_client.assert_not_called()


class GetCollectionTests(unittest.TestCase):
    @patch("src.vector_store._client")
    def test_creates_collection_with_expected_configuration(self, mock_client) -> None:
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        collection = vector_store.get_collection()

        mock_client.get_or_create_collection.assert_called_once_with(
            name=vector_store.COLLECTION_NAME,
            embedding_function=vector_store._embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        self.assertIs(collection, mock_collection)

    @patch("src.vector_store._client")
    def test_reuses_single_client_instance_across_calls(self, mock_client) -> None:
        vector_store.get_collection()
        vector_store.get_collection()

        self.assertEqual(2, mock_client.get_or_create_collection.call_count)


class AddFragmentsTests(unittest.TestCase):
    def test_rejects_empty_fragment_list(self) -> None:
        with self.assertRaises(ValueError):
            vector_store.add_fragments([])

    @patch("src.vector_store.get_collection")
    def test_adds_fragments_with_expected_shape(self, mock_get_collection) -> None:
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        fragments = [
            {
                "id": "frag-1",
                "text": "Uso obligatorio de casco.",
                "metadata": {"source": "epi.pdf", "page": 1, "section": "EPI"},
            },
            {
                "id": "frag-2",
                "text": "Proteccion colectiva frente a caidas.",
                "metadata": {"source": "epi.pdf", "page": 2, "section": "Caidas"},
            },
        ]

        count = vector_store.add_fragments(fragments)

        mock_collection.add.assert_called_once_with(
            ids=["frag-1", "frag-2"],
            documents=["Uso obligatorio de casco.", "Proteccion colectiva frente a caidas."],
            metadatas=[
                {"source": "epi.pdf", "page": 1, "section": "EPI"},
                {"source": "epi.pdf", "page": 2, "section": "Caidas"},
            ],
        )
        self.assertEqual(2, count)


class SearchTests(unittest.TestCase):
    @patch("src.vector_store.get_collection")
    def test_returns_empty_list_when_collection_has_no_documents(self, mock_get_collection) -> None:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_get_collection.return_value = mock_collection

        results = vector_store.search("como usar el casco")

        self.assertEqual([], results)
        mock_collection.query.assert_not_called()

    @patch("src.vector_store.get_collection")
    def test_transforms_chroma_results_into_expected_fragments(self, mock_get_collection) -> None:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "documents": [["Texto A", "Texto B"]],
            "metadatas": [[{"source": "a.pdf", "page": 1}, {"source": "b.pdf", "page": 5}]],
            "distances": [[0.12, 0.34]],
        }
        mock_get_collection.return_value = mock_collection

        results = vector_store.search("consulta de prueba", k=2)

        mock_collection.query.assert_called_once_with(query_texts=["consulta de prueba"], n_results=2)
        self.assertEqual(2, len(results))
        self.assertEqual("Texto A", results[0]["text"])
        self.assertEqual({"source": "a.pdf", "page": 1}, results[0]["metadata"])
        self.assertEqual(0.12, results[0]["distance"])
        self.assertEqual("Texto B", results[1]["text"])

    @patch("src.vector_store.get_collection")
    def test_uses_default_k_of_four_when_not_specified(self, mock_get_collection) -> None:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 4
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_get_collection.return_value = mock_collection

        vector_store.search("consulta")

        mock_collection.query.assert_called_once_with(query_texts=["consulta"], n_results=4)


if __name__ == "__main__":
    unittest.main()