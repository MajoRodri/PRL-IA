"""Compara configuraciones de chunking con preguntas y evidencias verificadas.

Entrada: corpus cargado, configuraciones candidatas y preguntas de referencia
de ``data/evaluation/chunking_questions.json``. Salida: métricas agregadas y
detalle por pregunta en ``data/evaluation/chunking_results.json``.

Posición en el flujo: valida la decisión de fragmentación entre la ingesta y la
indexación vectorial. BM25 actúa como proxy léxico reproducible, pero no sustituye
la evaluación semántica posterior con los embeddings definitivos de Persona 2.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.chunking import split_documents
from src.ingestion import load_corpus


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "sources.json"
DEFAULT_QUESTIONS = PROJECT_ROOT / "data" / "evaluation" / "chunking_questions.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "evaluation" / "chunking_results.json"
CONFIGURATIONS = ((500, 50), (800, 120), (1000, 200))

# Palabras funcionales que no ayudan a distinguir el contenido preventivo.
STOPWORDS = {
    "a", "al", "ante", "como", "con", "cual", "cuales", "cuando", "de", "del",
    "debe", "deben", "el", "en", "es", "esta", "las", "lo", "los", "para", "por",
    "que", "se", "segun", "sin", "su", "sus", "un", "una", "y", "la",
}


def normalizar(texto: str) -> str:
    """Pasa a minúsculas, elimina tildes y normaliza los espacios."""

    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def tokenizar(texto: str) -> list[str]:
    """Obtiene términos alfanuméricos informativos para el índice BM25."""

    return [
        termino
        for termino in re.findall(r"[a-z0-9]+", normalizar(texto))
        if len(termino) > 1 and termino not in STOPWORDS
    ]


class IndiceBM25:
    """Índice BM25 mínimo, suficiente para comparar los mismos datos de entrada."""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks
        self.tokens = [tokenizar(chunk["text"]) for chunk in chunks]
        self.frecuencias = [Counter(tokens) for tokens in self.tokens]
        self.longitudes = [len(tokens) for tokens in self.tokens]
        self.longitud_media = sum(self.longitudes) / len(self.longitudes)
        self.frecuencia_documental: Counter[str] = Counter()
        for tokens in self.tokens:
            self.frecuencia_documental.update(set(tokens))

    def buscar(self, pregunta: str, limite: int = 10) -> list[tuple[int, float]]:
        """Devuelve índices de chunks y puntuaciones, ordenados de mayor a menor."""

        terminos = set(tokenizar(pregunta))
        cantidad = len(self.chunks)
        k1 = 1.5
        b = 0.75
        resultados: list[tuple[int, float]] = []

        for indice, frecuencias in enumerate(self.frecuencias):
            puntuacion = 0.0
            longitud = self.longitudes[indice]
            for termino in terminos:
                frecuencia = frecuencias.get(termino, 0)
                if not frecuencia:
                    continue
                documentos_con_termino = self.frecuencia_documental[termino]
                idf = math.log(1 + (cantidad - documentos_con_termino + 0.5) / (documentos_con_termino + 0.5))
                normalizador = frecuencia + k1 * (
                    1 - b + b * longitud / self.longitud_media
                )
                puntuacion += idf * frecuencia * (k1 + 1) / normalizador
            resultados.append((indice, puntuacion))

        resultados.sort(key=lambda resultado: (-resultado[1], resultado[0]))
        return resultados[:limite]


def es_chunk_esperado(chunk: dict[str, Any], pregunta: dict[str, Any]) -> bool:
    """Comprueba si un chunk pertenece a la fuente y páginas de referencia."""

    metadata = chunk["metadata"]
    return (
        metadata.get("source_id") == pregunta["expected_source_id"]
        and metadata.get("page") in pregunta["expected_pages"]
    )


def evaluar_pregunta(
    indice_bm25: IndiceBM25,
    pregunta: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    """Calcula métricas de recuperación para una pregunta de referencia."""

    ranking = indice_bm25.buscar(pregunta["question"], limite=max(10, top_k))
    primeros = ranking[:top_k]
    chunks_top = [indice_bm25.chunks[indice] for indice, _ in primeros]
    rangos_esperados = [
        posicion
        for posicion, (indice, _) in enumerate(ranking, start=1)
        if es_chunk_esperado(indice_bm25.chunks[indice], pregunta)
    ]
    primer_rango = rangos_esperados[0] if rangos_esperados else None
    chunks_esperados = [
        chunk for chunk in chunks_top if es_chunk_esperado(chunk, pregunta)
    ]
    texto_evidencia = normalizar(" ".join(chunk["text"] for chunk in chunks_esperados))
    evidencias = pregunta["evidence_terms"]
    evidencias_encontradas = [
        evidencia for evidencia in evidencias if normalizar(evidencia) in texto_evidencia
    ]

    return {
        "question_id": pregunta["id"],
        "gold_page_hit_at_k": bool(chunks_esperados),
        "first_gold_rank": primer_rango,
        "reciprocal_rank": 1 / primer_rango if primer_rango else 0.0,
        "gold_precision_at_k": len(chunks_esperados) / top_k,
        "evidence_recall_at_k": len(evidencias_encontradas) / len(evidencias),
        "evidence_found": evidencias_encontradas,
        "retrieved": [
            {
                "rank": posicion,
                "score": round(puntuacion, 6),
                "chunk_id": indice_bm25.chunks[indice]["metadata"]["chunk_id"],
                "source_id": indice_bm25.chunks[indice]["metadata"].get("source_id"),
                "page": indice_bm25.chunks[indice]["metadata"]["page"],
                "length": len(indice_bm25.chunks[indice]["text"]),
            }
            for posicion, (indice, puntuacion) in enumerate(primeros, start=1)
        ],
    }


def promedio(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def validar_preguntas(
    paginas: list[dict[str, Any]],
    preguntas: list[dict[str, Any]],
) -> None:
    """Verifica que cada referencia y cada evidencia existan en el corpus."""

    identificadores = [pregunta["id"] for pregunta in preguntas]
    if len(identificadores) != len(set(identificadores)):
        raise ValueError("Los identificadores de las preguntas deben ser únicos")

    for pregunta in preguntas:
        paginas_esperadas = [
            pagina
            for pagina in paginas
            if pagina["metadata"].get("source_id") == pregunta["expected_source_id"]
            and pagina["metadata"].get("page") in pregunta["expected_pages"]
        ]
        if not paginas_esperadas:
            raise ValueError(
                f"No existe la fuente/página esperada para {pregunta['id']}"
            )
        texto_esperado = normalizar(" ".join(pagina["text"] for pagina in paginas_esperadas))
        ausentes = [
            evidencia
            for evidencia in pregunta["evidence_terms"]
            if normalizar(evidencia) not in texto_esperado
        ]
        if ausentes:
            raise ValueError(
                f"Evidencias ausentes en la referencia de {pregunta['id']}: {ausentes}"
            )


def evaluar_configuracion(
    paginas: list[dict[str, Any]],
    preguntas: list[dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
) -> dict[str, Any]:
    """Fragmenta el corpus, crea el índice y agrega las métricas por pregunta."""

    chunks = split_documents(
        paginas,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    indice = IndiceBM25(chunks)
    resultados = [evaluar_pregunta(indice, pregunta, top_k) for pregunta in preguntas]
    caracteres_unicos = sum(len(pagina["text"]) for pagina in paginas)
    caracteres_indexados = sum(len(chunk["text"]) for chunk in chunks)

    return {
        "configuration": f"{chunk_size}/{chunk_overlap}",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "chunk_count": len(chunks),
        "average_chunk_length": round(promedio([len(chunk["text"]) for chunk in chunks]), 2),
        "indexed_character_ratio": round(caracteres_indexados / caracteres_unicos, 4),
        "gold_page_hit_at_k": round(
            promedio([float(resultado["gold_page_hit_at_k"]) for resultado in resultados]), 4
        ),
        "mean_reciprocal_rank": round(
            promedio([resultado["reciprocal_rank"] for resultado in resultados]), 4
        ),
        "gold_precision_at_k": round(
            promedio([resultado["gold_precision_at_k"] for resultado in resultados]), 4
        ),
        "evidence_recall_at_k": round(
            promedio([resultado["evidence_recall_at_k"] for resultado in resultados]), 4
        ),
        "question_results": resultados,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error("--top-k debe ser mayor que cero")

    paginas = load_corpus(args.manifest)
    preguntas = json.loads(args.questions.read_text(encoding="utf-8"))["questions"]
    validar_preguntas(paginas, preguntas)
    configuraciones = [
        evaluar_configuracion(paginas, preguntas, tamano, solapamiento, args.top_k)
        for tamano, solapamiento in CONFIGURATIONS
    ]
    salida = {
        "_about": {
            "purpose": "Resultados auditables de la comparación de estrategias de chunking.",
            "input": "Corpus oficial y preguntas de referencia validadas.",
            "output": "Métricas agregadas y resultados top-k por pregunta y configuración.",
            "flow_position": "Salida de evaluación usada para elegir el chunking antes de generar embeddings.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Proxy léxico BM25 sobre el corpus local completo",
        "limitations": [
            "La recuperación léxica no equivale a la recuperación semántica con embeddings.",
            "Las diez preguntas son una muestra dirigida y no representan todos los usos posibles.",
            "Las páginas y frases esperadas se definieron manualmente a partir de las fuentes oficiales.",
        ],
        "top_k": args.top_k,
        "source_count": len({pagina["metadata"].get("source_id") for pagina in paginas}),
        "page_count": len(paginas),
        "question_count": len(preguntas),
        "configurations": configuraciones,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    encabezados = (
        "config", "chunks", "long.media", "ratio.indice", "hit@5", "MRR", "precision@5", "evidencia@5"
    )
    print(" | ".join(encabezados))
    for resultado in configuraciones:
        print(
            " | ".join(
                [
                    resultado["configuration"],
                    str(resultado["chunk_count"]),
                    str(resultado["average_chunk_length"]),
                    str(resultado["indexed_character_ratio"]),
                    str(resultado["gold_page_hit_at_k"]),
                    str(resultado["mean_reciprocal_rank"]),
                    str(resultado["gold_precision_at_k"]),
                    str(resultado["evidence_recall_at_k"]),
                ]
            )
        )
    print(f"Resultados detallados: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
