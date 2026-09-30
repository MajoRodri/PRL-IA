"""Chroma real; vectores deterministas de prueba, sin descargar modelos.

Comprueban la integración y sus fallos, no la calidad semántica de MiniLM.
"""
from pathlib import Path
import sys
from types import SimpleNamespace

import chromadb
from chromadb import EmbeddingFunction
from fastapi.testclient import TestClient
import pytest

from src.api_documents import create_app
from src.chroma_adapter import ChromaDocumentIndex
from src.document_service import DocumentService
from src.retrieval import Chunk, Retriever


class TestEmbeddings(EmbeddingFunction):
    __test__ = False

    def __init__(self):
        pass

    def __call__(self, input):
        return [[float("altura" in text), float("electric" in text),
                 float("salarios" in text), 0.01] for text in input]

    @staticmethod
    def name():
        return "prl-test-vectors"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return TestEmbeddings()


@pytest.fixture
def collection(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    return client.get_or_create_collection(
        "prl_test", embedding_function=TestEmbeddings(),
        metadata={"hnsw:space": "cosine"},
    )


@pytest.fixture
def index(collection, tmp_path):
    return ChromaDocumentIndex(collection, tmp_path / "manifest.sqlite3", batch_size=1)


def chunk(doc="a", text="altura", *, key="0", category="demo", page=None):
    return Chunk(f"{doc}:{key}", doc, text, f"{doc}.txt", page=page, category=category)


def search(index, query="altura", **filters):
    return index.search(query, limit=4, filters=filters)


def test_roundtrip_and_score(index):
    original = chunk()
    index.replace_document("a", [original])
    hit, = search(index)
    assert hit.chunk == original
    assert hit.score == pytest.approx(1, abs=1e-5)
    assert not Retriever(index).retrieve("salarios").hits


def test_filters_apply_before_limit(index):
    index.replace_document("a", [chunk(category="otro")])
    index.replace_document("b", [chunk("b", "altura electric", category="demo", page=2)])
    hit, = index.search("altura", limit=1, filters={"category": "demo", "page": 2})
    assert hit.chunk.document_id == "b"
    assert not search(index, section="ausente")


def test_replace_removes_old_and_delete_is_scoped(index, collection):
    index.replace_document("a", [chunk(), chunk(key="1")])
    index.replace_document("b", [chunk("b")])
    index.replace_document("a", [chunk(text="electric")])
    assert collection.count() == 2
    assert search(index, "electric", document_id="a")[0].chunk.text == "electric"
    index.delete_document("a")
    index.delete_document("a")
    assert collection.count() == 1
    assert search(index)[0].chunk.document_id == "b"


class FaultyCollection:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.add_count = 0
        self.fail_add_at = None
        self.fail_delete = False

    def __getattr__(self, name):
        return getattr(self.wrapped, name)

    def add(self, **kwargs):
        self.add_count += 1
        if self.add_count == self.fail_add_at:
            raise RuntimeError("fallo simulado de escritura")
        return self.wrapped.add(**kwargs)

    def delete(self, **kwargs):
        if self.fail_delete:
            raise RuntimeError("fallo simulado de borrado")
        return self.wrapped.delete(**kwargs)


def test_partial_batch_and_cleanup_failure_preserve_old_generation(index, collection):
    index.replace_document("a", [chunk()])
    faulty = FaultyCollection(collection)
    faulty.fail_add_at = 2
    faulty.fail_delete = True
    index.collection = faulty
    with pytest.raises(RuntimeError):
        index.replace_document("a", [chunk(text="electric"), chunk(text="electric", key="1")])
    assert collection.count() == 2  # Un fragmento incompleto físico, nunca publicado.
    hit, = search(index)
    assert hit.chunk.text == "altura"
    faulty.fail_delete = False
    index.replace_document("a", [chunk(text="electric")])
    assert collection.count() == 1


def test_manifest_publication_failure_preserves_old(index, monkeypatch):
    index.replace_document("a", [chunk()])
    def fail(*args):
        raise RuntimeError("fallo simulado del catálogo")
    monkeypatch.setattr(index, "_publish", fail)
    with pytest.raises(RuntimeError):
        index.replace_document("a", [chunk(text="electric")])
    assert search(index)[0].chunk.text == "altura"


def test_cleanup_failure_after_success_does_not_revert(index, collection):
    index.replace_document("a", [chunk()])
    faulty = FaultyCollection(collection)
    faulty.fail_delete = True
    index.collection = faulty
    index.replace_document("a", [chunk(text="electric")])
    assert collection.count() == 2
    hit, = search(index, "electric")
    assert hit.chunk.text == "electric"


def test_unmanaged_records_are_excluded_and_preserved(index, collection):
    collection.add(ids=["p2-original"], documents=["altura"], metadatas=[{"source": "legacy.txt"}])
    assert not search(index)
    index.replace_document("a", [chunk()])
    assert len(search(index)) == 1
    index.delete_document("a")
    assert collection.get()["ids"] == ["p2-original"]


def test_reopen_catalogue(index, collection, tmp_path):
    index.replace_document("a", [chunk()])
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    reopened = client.get_collection("prl_test", embedding_function=TestEmbeddings())
    second = ChromaDocumentIndex(reopened, index.manifest_path)
    assert search(second)[0].chunk == chunk()


def test_reject_wrong_metric_and_collection_binding(index, tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "other"))
    l2 = client.create_collection("wrong_metric", embedding_function=TestEmbeddings())
    with pytest.raises(ValueError, match="cosine"):
        ChromaDocumentIndex(l2, tmp_path / "l2.sqlite3")
    other = client.create_collection("other_cosine", embedding_function=TestEmbeddings(),
                                     metadata={"hnsw:space": "cosine"})
    with pytest.raises(ValueError, match="otra colección"):
        ChromaDocumentIndex(other, index.manifest_path)


def test_api_lifecycle_and_restart(index, tmp_path):
    directory = tmp_path / "documents"
    def app():
        return create_app(service=DocumentService(directory, index=index))
    with TestClient(app()) as client:
        response = client.post("/api/v1/documents", files={"file": ("demo.txt", b"altura")}, data={"category": "demo"})
        assert response.status_code == 201
        doc_id = response.json()["document_id"]
        assert client.get("/health").json()["index"] == "ChromaDocumentIndex"
        assert client.post(f"/api/v1/documents/{doc_id}/reindex").status_code == 200
    with TestClient(app()) as client:
        response = client.post("/api/v1/retrieval/query", json={"query": "altura", "filters": {"category": "demo"}})
        assert response.json()["sources"][0]["document_id"] == doc_id
        assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 204
        assert not client.post("/api/v1/retrieval/query", json={"query": "altura"}).json()["has_context"]


def test_failed_delete_is_hidden_and_retryable(index, collection, tmp_path):
    service = DocumentService(tmp_path / "documents", index=index)
    with TestClient(create_app(service=service)) as client:
        doc_id = client.post("/api/v1/documents", files={"file": ("demo.txt", b"altura")}).json()["document_id"]
        faulty = FaultyCollection(collection)
        faulty.fail_delete = True
        index.collection = faulty
        assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 503
        assert not client.post("/api/v1/retrieval/query", json={"query": "altura"}).json()["has_context"]
        faulty.fail_delete = False
        assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 204


def test_factory_connects_p2_collection(collection, tmp_path, monkeypatch):
    from src import api_documents_chroma
    import src
    p2 = SimpleNamespace(get_collection=lambda: collection)
    monkeypatch.setitem(sys.modules, "src.vector_store", p2)
    monkeypatch.setattr(src, "vector_store", p2, raising=False)
    monkeypatch.setenv("PRL_CHROMA_DOCUMENTS_DIR", str(tmp_path / "factory"))
    monkeypatch.chdir(Path(api_documents_chroma.__file__).resolve().parents[1])
    with TestClient(api_documents_chroma.create_app()) as client:
        assert client.get("/health").json()["index"] == "ChromaDocumentIndex"
        assert client.post("/api/v1/documents", files={"file": ("demo.txt", b"altura")}).status_code == 201
    assert collection.count() == 1
