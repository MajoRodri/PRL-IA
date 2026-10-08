"""Ejecutar desde raíz: python -m scripts.evaluate_retrieval. Solo corpus sintético."""
from collections import defaultdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.document_service import SQLiteDemoIndex
from src.retrieval import Chunk, Retriever


def evaluate():
    dataset = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures_retrieval.json").read_text())
    with TemporaryDirectory() as directory:
        index = SQLiteDemoIndex(Path(directory) / "evaluation.sqlite3")
        grouped = defaultdict(list)
        for item in dataset["chunks"]:
            chunk = Chunk(**item)
            grouped[chunk.document_id].append(chunk)
        for doc_id, chunks in grouped.items():
            index.replace_document(doc_id, chunks)
        retriever = Retriever(index)
        rows, recalls, reciprocal_ranks, precisions, abstentions = [], [], [], [], []
        for case in dataset["cases"]:
            hits = retriever.retrieve(case["query"], k=3, min_score=.25, filters=case.get("filters")).hits
            obtained = [h.chunk.chunk_id for h in hits]
            relevant = set(case["relevant_ids"])
            if relevant:
                recalls.append(len(set(obtained) & relevant) / len(relevant))
                precisions.append(len(set(obtained) & relevant) / 3)
                reciprocal_ranks.append(next((1 / rank for rank, item in enumerate(obtained, 1) if item in relevant), 0))
            else:
                abstentions.append(not obtained)
            rows.append({"id": case["id"], "expected": sorted(relevant), "retrieved": obtained})
        return {
            "mode": "synthetic_lexical_demo", "k": 3, "min_score": .25,
            "answerable_cases": len(recalls), "unanswerable_cases": len(abstentions),
            "recall_at_3": sum(recalls) / len(recalls),
            "precision_at_3_fixed_denominator": sum(precisions) / len(precisions),
            "mrr_at_3": sum(reciprocal_ranks) / len(reciprocal_ranks),
            "correct_empty_context_rate": sum(abstentions) / len(abstentions), "cases": rows,
        }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
