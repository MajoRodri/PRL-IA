"""Tests de sustitución de documentos en _index_document."""
import src.api as api


def _make_store():
    """Devuelve (collection_mock, store_dict). El dict refleja el estado de ChromaDB."""
    store: dict[str, tuple[str, dict]] = {}

    class _Col:
        def get(self, where=None):
            if where and "source" in where:
                src = where["source"]
                matched = {k: v for k, v in store.items() if v[1].get("source") == src}
            else:
                matched = dict(store)
            return {
                "ids":       list(matched.keys()),
                "documents": [v[0] for v in matched.values()],
                "metadatas": [v[1] for v in matched.values()],
            }

        def delete(self, ids):
            for i in ids:
                store.pop(i, None)

        def upsert(self, ids, documents, metadatas):
            for i, d, m in zip(ids, documents, metadatas):
                store[i] = (d, m)

    return _Col(), store


def _pages(name: str, n: int) -> list[dict]:
    return [
        {"text": f"Contenido de prueba para la página {p}.", "metadata": {"document": name, "page": p}}
        for p in range(1, n + 1)
    ]


def test_replace_removes_old_chunks(tmp_path, monkeypatch):
    """Sustituir un PDF de 2 páginas por uno de 1 debe eliminar los chunks de la página 2."""
    col, store = _make_store()
    monkeypatch.setattr("src.vector_store.get_collection", lambda: col)

    fake_path = tmp_path / "doc.pdf"
    fake_path.write_bytes(b"fake")

    # Primera subida: 2 páginas
    monkeypatch.setattr("src.ingestion.load_document", lambda p: _pages("doc.pdf", 2))
    n1 = api._index_document(fake_path)
    assert n1 == 2
    assert {v[1]["page"] for v in store.values()} == {1, 2}

    # Segunda subida: solo 1 página
    monkeypatch.setattr("src.ingestion.load_document", lambda p: _pages("doc.pdf", 1))
    n2 = api._index_document(fake_path)
    assert n2 == 1

    pages_after = {v[1]["page"] for v in store.values()}
    assert pages_after == {1}, "La página 2 debe desaparecer tras la sustitución"


def test_replace_rollback_on_failure(tmp_path, monkeypatch):
    """Si falla la inserción del nuevo documento, se restauran los chunks anteriores."""
    col, store = _make_store()
    call_count = [0]
    original_upsert = col.upsert

    def failing_upsert(ids, documents, metadatas):
        call_count[0] += 1
        if call_count[0] == 2:  # segunda llamada = inserción del documento nuevo
            raise RuntimeError("Error simulado de ChromaDB")
        original_upsert(ids, documents, metadatas)

    col.upsert = failing_upsert
    monkeypatch.setattr("src.vector_store.get_collection", lambda: col)

    fake_path = tmp_path / "doc.pdf"
    fake_path.write_bytes(b"fake")

    # Primera subida: 2 páginas — OK
    monkeypatch.setattr("src.ingestion.load_document", lambda p: _pages("doc.pdf", 2))
    api._index_document(fake_path)
    ids_before = set(store.keys())
    assert len(ids_before) == 2

    # Segunda subida falla → debe restaurar la versión anterior
    monkeypatch.setattr("src.ingestion.load_document", lambda p: _pages("doc.pdf", 1))
    try:
        api._index_document(fake_path)
    except RuntimeError:
        pass

    assert set(store.keys()) == ids_before, "Los chunks originales deben restaurarse tras el fallo"
    assert {v[1]["page"] for v in store.values()} == {1, 2}
