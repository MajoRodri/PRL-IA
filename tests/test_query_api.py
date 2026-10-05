from fastapi.testclient import TestClient

from src.api import app
import src.api as api


client = TestClient(app)


def test_query_success(monkeypatch):
    """La API devuelve la respuesta y sus fuentes."""
    expected = {
        "answer": "Utiliza los equipos de protección adecuados.",
        "sources": [
            {
                "text": "El uso de casco es obligatorio en esta zona.",
                "metadata": {"source": "manual.pdf", "page": 3},
            }
        ],
    }

    def fake_answer_question(question, k=4):
        assert question == "¿Qué EPI debo utilizar?"
        assert k == 4
        return expected

    monkeypatch.setattr(api, "answer_question", fake_answer_question)

    response = client.post(
        "/api/query",
        json={"question": "¿Qué EPI debo utilizar?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": expected["answer"],
        "sources": expected["sources"],
        "abstained": False,
    }


def test_query_abstains_without_sources(monkeypatch):
    """La API se abstiene si no hay fuentes relevantes."""

    def fake_answer_question(question, k=4):
        return {
            "answer": "No hay información suficiente en la documentación.",
            "sources": [],
        }

    monkeypatch.setattr(api, "answer_question", fake_answer_question)

    response = client.post(
        "/api/query",
        json={"question": "Pregunta sin documentación"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "No hay información suficiente en la documentación.",
        "sources": [],
        "abstained": True,
    }


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

    def fake_answer_question(question, k=4):
        raise RuntimeError("Error interno del servicio RAG")

    monkeypatch.setattr(api, "answer_question", fake_answer_question)

    response = client.post(
        "/api/query",
        json={"question": "¿Qué EPI necesito?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "No se ha podido generar la respuesta."
    }