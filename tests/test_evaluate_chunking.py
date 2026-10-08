"""Pruebas del benchmark que justifica la estrategia de fragmentación.

Valida normalización, tokenización, recuperación BM25 y detección de referencias
o evidencias inexistentes en el conjunto de preguntas de evaluación.

Posición en el flujo: comprueba ``scripts.evaluate_chunking`` antes de aceptar
una configuración de chunking para la futura indexación vectorial.
"""

from __future__ import annotations

import unittest

from scripts.evaluate_chunking import (
    IndiceBM25,
    evaluar_pregunta,
    normalizar,
    tokenizar,
    validar_preguntas,
)


class NormalizacionTests(unittest.TestCase):
    def test_normaliza_tildes_y_elimina_stopwords(self) -> None:
        self.assertEqual("proteccion electrica", normalizar("  Protección   ELÉCTRICA "))
        self.assertEqual(["proteccion", "electrica"], tokenizar("La protección eléctrica"))


class EvaluacionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = [
            {
                "text": "El casco protege la cabeza frente a impactos.",
                "metadata": {
                    "chunk_id": "epi_p0002_c0001",
                    "source_id": "guia-epi",
                    "page": 2,
                },
            },
            {
                "text": "La instalación sin tensión se debe poner a tierra y en cortocircuito.",
                "metadata": {
                    "chunk_id": "electrico_p0007_c0001",
                    "source_id": "guia-electrica",
                    "page": 7,
                },
            },
        ]
        self.pregunta = {
            "id": "puesta_tierra",
            "question": "¿Qué debe hacerse con una instalación sin tensión?",
            "expected_source_id": "guia-electrica",
            "expected_pages": [7],
            "evidence_terms": ["poner a tierra", "en cortocircuito"],
        }

    def test_bm25_recupera_el_chunk_esperado(self) -> None:
        resultado = evaluar_pregunta(IndiceBM25(self.chunks), self.pregunta, top_k=1)

        self.assertTrue(resultado["gold_page_hit_at_k"])
        self.assertEqual(1, resultado["first_gold_rank"])
        self.assertEqual(1.0, resultado["evidence_recall_at_k"])

    def test_validacion_detecta_evidencia_ausente(self) -> None:
        paginas = [
            {
                "text": self.chunks[1]["text"],
                "metadata": {"source_id": "guia-electrica", "page": 7},
            }
        ]
        pregunta_invalida = dict(self.pregunta)
        pregunta_invalida["evidence_terms"] = ["frase inexistente"]

        with self.assertRaises(ValueError):
            validar_preguntas(paginas, [pregunta_invalida])


if __name__ == "__main__":
    unittest.main()
