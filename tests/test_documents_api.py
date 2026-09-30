"""API real con índice local; sin Chroma ni llamadas a un LLM."""
from io import BytesIO
import sqlite3

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import pytest

from src.api_documents import create_app
from src.document_service import DemoProcessor, DocumentService


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def upload(client, content=b"riesgos electricos y proteccion", filename="manual.txt", category="general"):
    return client.post("/api/v1/documents", files={"file": (filename, content)}, data={"category": category})


def test_full_lifecycle_and_no_duplicate_chunks(client):
    response = upload(client)
    assert response.status_code == 201
    record = response.json()
    document_id = record["document_id"]
    assert record["status"] == "indexed" and record["chunk_count"] == 1
    assert "stored_name" not in record
    assert client.get(f"/api/v1/documents/{document_id}").json() == record
    found = client.post("/api/v1/retrieval/query", json={"query": "riesgos eléctricos"}).json()
    assert found["has_context"] and found["sources"][0]["source"] == "manual.txt"
    assert client.post(f"/api/v1/documents/{document_id}/reindex").json()["chunk_count"] == 1
    assert len(client.post("/api/v1/retrieval/query", json={"query": "riesgos"}).json()["sources"]) == 1
    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 204
    assert client.get("/api/v1/documents").json() == {"documents": []}
    assert not client.post("/api/v1/retrieval/query", json={"query": "riesgos"}).json()["has_context"]
    assert not list(client.app.state.document_service.raw_dir.iterdir())
    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404


def test_duplicate_content(client):
    assert upload(client).status_code == 201
    assert upload(client, filename="otro.txt").status_code == 409
    assert len(client.get("/api/v1/documents").json()["documents"]) == 1


@pytest.mark.parametrize("filename,content,code", [
    ("../escape.txt", b"abc", 400),
    ("virus.exe", b"abc", 415), ("empty.txt", b"", 422),
    ("fake.pdf", b"not pdf", 422), ("binary.txt", b"abc\x00", 422),
    ("latin.txt", b"\xff", 422), ("blank.txt", b"   ", 422),
    ("broken.pdf", b"%PDF-1.4\nbroken", 422),
])
def test_bad_uploads(client, filename, content, code):
    assert upload(client, filename=filename, content=content).status_code == code


def test_size_limit_and_category(client):
    client.app.state.document_service.max_bytes = 8
    assert upload(client, content=b"x" * 9).status_code == 413
    assert upload(client, content=b"abc", category=" ").status_code == 422


def test_persistence_after_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as first:
        doc_id = upload(first).json()["document_id"]
    with TestClient(create_app(tmp_path)) as second:
        assert second.get(f"/api/v1/documents/{doc_id}").json()["status"] == "indexed"
        assert second.post("/api/v1/retrieval/query", json={"query": "riesgos"}).json()["has_context"]


def test_processor_failure_and_retry(client):
    service = client.app.state.document_service
    class BrokenProcessor:
        def process(self, *args, **kwargs):
            raise RuntimeError("sensitive internal path or token")
    service.processor = BrokenProcessor()
    response = upload(client)
    assert response.status_code == 422
    assert "sensitive" not in response.text
    doc_id = response.json()["document_id"]
    assert response.json()["status"] == "failed"
    service.processor = DemoProcessor()
    assert client.post(f"/api/v1/documents/{doc_id}/reindex").json()["status"] == "indexed"


def test_index_failure_hides_stale_chunks_and_recovers(client):
    service = client.app.state.document_service
    doc_id = upload(client).json()["document_id"]
    original = service.index.replace_document
    def broken(*args):
        raise RuntimeError("index offline")
    service.index.replace_document = broken
    assert client.post(f"/api/v1/documents/{doc_id}/reindex").status_code == 422
    assert not client.post("/api/v1/retrieval/query", json={"query": "riesgos"}).json()["has_context"]
    service.index.replace_document = original
    assert client.post(f"/api/v1/documents/{doc_id}/reindex").json()["status"] == "indexed"


def test_delete_failure_hides_document_and_is_retryable(client):
    service = client.app.state.document_service
    doc_id = upload(client).json()["document_id"]
    original = service.index.delete_document
    def broken(*args):
        raise RuntimeError("delete offline")
    service.index.delete_document = broken
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 503
    assert not client.post("/api/v1/retrieval/query", json={"query": "riesgos"}).json()["has_context"]
    assert client.post(f"/api/v1/documents/{doc_id}/reindex").status_code == 409
    service.index.delete_document = original
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 204


def test_interrupted_processing_is_not_searchable(tmp_path):
    service = DocumentService(tmp_path)
    doc_id = service.upload("a.txt", b"riesgos")["document_id"]
    with sqlite3.connect(service.db_path) as db:
        db.execute("UPDATE documents SET status='processing' WHERE document_id=?", (doc_id,))
    restarted = DocumentService(tmp_path)
    assert restarted.get(doc_id)["status"] == "failed"
    assert not restarted.search("riesgos").hits
    assert restarted.reindex(doc_id)["status"] == "indexed"


def pdf_bytes(text="riesgos electricos", blank=False):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    if not blank:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_page_traceability(client):
    assert upload(client, filename="manual.pdf", content=pdf_bytes()).status_code == 201
    found = client.post("/api/v1/retrieval/query", json={"query": "electricos", "filters": {"page": 1}}).json()
    assert found["sources"][0]["page"] == 1
    assert found["sources"][0]["source"] == "manual.pdf"


def test_scanned_or_empty_pdf_rejected(client):
    response = upload(client, filename="scan.pdf", content=pdf_bytes(blank=True))
    assert response.status_code == 422
    assert "OCR" in response.json()["error"]


@pytest.mark.parametrize("payload", [
    {"query": " "}, {"query": "riesgos", "k": 0},
    {"query": "riesgos", "filters": {"unknown": "x"}},
    {"query": "riesgos", "filters": {"page": True}},
    {"query": "riesgos", "unexpected": 1},
])
def test_search_validation(client, payload):
    assert client.post("/api/v1/retrieval/query", json=payload).status_code == 422


def test_missing_document_routes(client):
    assert client.get("/api/v1/documents/missing").status_code == 404
    assert client.post("/api/v1/documents/missing/reindex").status_code == 404
    assert client.delete("/api/v1/documents/missing").status_code == 404


def test_chunk_overlap_and_metadata(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("uno dos tres cuatro cinco seis siete ocho", encoding="utf-8")
    chunks = DemoProcessor(5, 2).process(source, document_id="a", source="a.txt", category="demo")
    assert [c.text for c in chunks] == ["uno dos tres cuatro cinco", "cuatro cinco seis siete ocho"]
    assert all(c.page is None and c.category == "demo" for c in chunks)


def test_original_tampering_is_detected(client):
    service = client.app.state.document_service
    doc_id = upload(client).json()["document_id"]
    (service.raw_dir / f"{doc_id}.txt").write_text("contenido alterado")
    response = client.post(f"/api/v1/documents/{doc_id}/reindex")
    assert response.status_code == 422
    assert response.json()["status"] == "failed"


def test_service_rejects_windows_path(client):
    from src.document_service import DocumentError
    with pytest.raises(DocumentError):
        client.app.state.document_service.upload("C:\\escape.txt", b"abc")


def test_multipart_normalizes_windows_filename(client):
    # El parser multipart elimina la ruta Windows antes de entregarla al endpoint.
    response = upload(client, filename="C:\\escape.txt", content=b"abc")
    assert response.status_code == 201
    assert response.json()["filename"] == "escape.txt"
