from fastapi.testclient import TestClient

from src.api import app
import src.api as api


client = TestClient(app)


def test_query_success(monkeypatch):
    """La API devuelve la respuesta y sus fuentes."""
    expected = {
        "answer": "Utiliza los equipos de protección adecuados.",
        "sources": [
            {"document": "manual.pdf", "page": 3, "chunk": "El uso de casco es obligatorio en esta zona."}
        ],
        "abstained": False,
    }

    def fake_answer_query(question, k=4):
        assert question == "¿Qué EPI debo utilizar?"
        assert k == 4
        return expected

    monkeypatch.setattr(api, "answer_query", fake_answer_query)

    response = client.post(
        "/api/query",
        json={"question": "¿Qué EPI debo utilizar?"},
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_query_no_relevant_docs(monkeypatch):
    """La API responde conversacionalmente cuando no hay fuentes relevantes."""

    def fake_answer_query(question, k=4):
        return {
            "answer": "Hola, soy Paco. Puedo ayudarte con dudas sobre PRL.",
            "sources": [],
            "abstained": False,
        }

    monkeypatch.setattr(api, "answer_query", fake_answer_query)

    response = client.post(
        "/api/query",
        json={"question": "Hola, ¿qué puedes hacer?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert data["abstained"] is False
    assert data["answer"]


def test_query_invalid_question():
    """La API rechaza preguntas vacías."""

    response = client.post(
        "/api/query",
        json={"question": ""},
    )

    assert response.status_code == 422


def test_query_invalid_k():
    """La API rechaza un número de fragmentos fuera del rango."""

    response = client.post(
        "/api/query",
        json={"question": "¿Qué EPI necesito?", "k": 0},
    )

    assert response.status_code == 422


def test_query_rag_error(monkeypatch):
    """La API devuelve 503 si falla el servicio RAG."""

    def fake_answer_query(question, k=4):
        raise RuntimeError("Error interno del servicio RAG")

    monkeypatch.setattr(api, "answer_query", fake_answer_query)

    response = client.post(
        "/api/query",
        json={"question": "¿Qué EPI necesito?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "No se ha podido generar la respuesta."
    }
