from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src import llm_service


def test_get_llm_initializes_model(monkeypatch):
    """Comprueba que el modelo se inicializa correctamente."""
    monkeypatch.setenv("GROQ_API_KEY", "test_api_key")

    with patch("src.llm_service.ChatGroq") as mock_chat:
        llm_service.get_llm()

        mock_chat.assert_called_once_with(
            model=llm_service.GROQ_MODEL,
            api_key="test_api_key",
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
            max_retries=2,
        )


def test_get_llm_without_api_key(monkeypatch):
    """Comprueba que se detecta la ausencia de la clave."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Falta GROQ_API_KEY"):
        llm_service.get_llm()


def test_generate_response_success():
    """Comprueba que se devuelve la respuesta del modelo."""
    mock_llm = SimpleNamespace(
        invoke=lambda prompt: SimpleNamespace(
            content="La PRL protege la salud laboral."
        )
    )

    with patch("src.llm_service.get_llm", return_value=mock_llm):
        response = llm_service.generate_response("¿Qué es la PRL?")

    assert response == "La PRL protege la salud laboral."


@pytest.mark.parametrize("prompt", ["", "   ", None, 123])
def test_generate_response_invalid_prompt(prompt):
    """Comprueba que se rechazan los prompts no válidos."""
    with pytest.raises(ValueError, match="El prompt no puede estar vacío"):
        llm_service.generate_response(prompt)


def test_generate_response_groq_error():
    """Comprueba que los errores de Groq se gestionan."""
    mock_llm = SimpleNamespace(
        invoke=lambda prompt: (_ for _ in ()).throw(
            Exception("Error simulado")
        )
    )

    with patch("src.llm_service.get_llm", return_value=mock_llm):
        with pytest.raises(
            RuntimeError,
            match="Error al solicitar una respuesta a Groq"
        ) as error:
            llm_service.generate_response("¿Qué es la PRL?")

    assert isinstance(error.value.__cause__, Exception)