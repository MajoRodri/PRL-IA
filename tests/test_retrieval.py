"""Pruebas del contrato de recuperación, sin redes ni modelos descargados."""
import pytest

from src.document_service import SQLiteDemoIndex
from src.retrieval import Chunk, Hit, Retriever


@pytest.fixture
def index(tmp_path):
    store = SQLiteDemoIndex(tmp_path / "index.sqlite3")
    store.replace_document("a", [
        Chunk("a:0", "a", "Protección frente a riesgos eléctricos", "electricidad.pdf", page=1, category="electricidad"),
        Chunk("a:1", "a", "Plan de evacuación de emergencia", "electricidad.pdf", page=2),
    ])
    store.replace_document("b", [Chunk("b:0", "b", "Trabajos en altura y revisión de protección", "altura.txt", category="altura")])
    return store


def test_ranking_and_traceability(index):
    result = Retriever(index).retrieve("riesgos eléctricos", k=1)
    assert result.hits[0].chunk.chunk_id == "a:0"
    assert result.hits[0].score == 1
    assert result.to_dict()["sources"][0]["page"] == 1


@pytest.mark.parametrize("filters, expected", [
    ({"document_id": "b"}, "b:0"), ({"category": "altura"}, "b:0"),
    ({"source": "electricidad.pdf", "page": 1}, "a:0"),
])
def test_metadata_filters(index, filters, expected):
    result = Retriever(index).retrieve("protección", filters=filters)
    assert [h.chunk.chunk_id for h in result.hits] == [expected]


def test_no_context_and_threshold(index):
    assert not Retriever(index).retrieve("salarios vacaciones").hits
    assert Retriever(index).retrieve("riesgos vacaciones", min_score=0.6).reason == "no_relevant_context"
    assert Retriever(index).retrieve("riesgos vacaciones", min_score=0.5).hits
    assert not Retriever(index).retrieve("el de la").hits


@pytest.mark.parametrize("kwargs", [
    {"query": " "}, {"query": "x" * 2001}, {"query": "a", "k": 0},
    {"query": "a", "k": True}, {"query": "a", "k": 21},
    {"query": "a", "min_score": float("nan")}, {"query": "a", "min_score": 1.1},
    {"query": "a", "filters": {"private": "x"}},
    {"query": "a", "filters": {"page": "1"}}, {"query": "a", "filters": {"page": True}},
])
def test_invalid_requests(index, kwargs):
    with pytest.raises(ValueError):
        Retriever(index).retrieve(**kwargs)


def test_defensive_filter_deduplication_and_visibility():
    class Provider:
        def search(self, *args, **kwargs):
            return [
                Hit(Chunk("a1", "a", "Texto idéntico", "a.pdf", page=1), .9),
                Hit(Chunk("a2", "a", "Texto idéntico", "a.pdf", page=1), .8),
                Hit(Chunk("b1", "b", "Otra fuente", "b.pdf"), 1),
            ]
    result = Retriever(Provider()).retrieve("texto", filters={"document_id": "a"})
    assert len(result.hits) == 1
    assert not Retriever(Provider(), is_visible=lambda _: False).retrieve("texto").hits


def test_replace_is_atomic_and_persistent(index):
    original = list(index.search("riesgos", limit=10, filters={}))
    duplicate = Chunk("same", "a", "nuevo", "a.txt")
    with pytest.raises(Exception):
        index.replace_document("a", [duplicate, duplicate])
    reopened = SQLiteDemoIndex(index.db_path)
    assert reopened.search("riesgos", limit=10, filters={}) == original
    reopened.replace_document("a", [Chunk("a:new", "a", "contenido nuevo", "a.txt")])
    assert not reopened.search("riesgos", limit=10, filters={})
    reopened.delete_document("a")
    assert not reopened.search("nuevo", limit=10, filters={})


@pytest.mark.parametrize("score", [-1, 1.01, float("inf"), float("nan")])
def test_provider_score_contract(score):
    with pytest.raises(ValueError):
        Hit(Chunk("1", "a", "texto", "a.txt"), score)
