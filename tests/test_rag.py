from unittest.mock import Mock

import pytest

from src import rag_chain


@pytest.fixture
def fragments():
    """Fragmentos de documentación simulados."""
    return [
        {
            "text": "El uso del casco es obligatorio en esta zona.",
            "metadata": {
                "source": "manual_prl.pdf",
                "page": 5,
                "section": "Equipos de protección"
            },
            "distance": 0.12,
        },
        {
            "text": "Los trabajadores deben utilizar calzado de seguridad.",
            "metadata": {
                "source": "manual_prl.pdf",
                "page": 6,
                "section": "Protección individual"
            },
            "distance": 0.18,
        },
    ]


def test_answer_question_success(fragments):
    """Recupera documentos y genera una respuesta."""
    retriever = Mock(return_value=fragments)
    generator = Mock(return_value="Es obligatorio utilizar casco.")

    result = rag_chain.answer_question(
        "¿Qué protección debo utilizar?",
        retriever=retriever,
        generator=generator,
    )

    assert result["answer"] == "Es obligatorio utilizar casco."
    assert result["sources"] == fragments
    retriever.assert_called_once_with(
        "¿Qué protección debo utilizar?",
        k=4,
    )
    generator.assert_called_once()


def test_answer_question_includes_context_in_prompt(fragments):
    """Comprueba que el prompt incluye la pregunta y los documentos."""
    retriever = Mock(return_value=fragments)
    generator = Mock(return_value="Debes utilizar casco.")

    rag_chain.answer_question(
        "¿Es obligatorio el casco?",
        retriever=retriever,
        generator=generator,
    )

    prompt = generator.call_args.args[0]

    assert "¿Es obligatorio el casco?" in prompt
    assert "El uso del casco es obligatorio" in prompt
    assert "manual_prl.pdf" in prompt
    assert "Página: 5" in prompt
    assert "normativa PRL" in prompt


def test_answer_question_empty_retrieval():
    """No llama al modelo cuando no encuentra documentos."""
    retriever = Mock(return_value=[])
    generator = Mock()

    result = rag_chain.answer_question(
        "¿Qué dice el manual?",
        retriever=retriever,
        generator=generator,
    )

    assert result["answer"] == rag_chain.NO_CONTEXT_ANSWER
    assert result["sources"] == []
    generator.assert_not_called()


@pytest.mark.parametrize("question", ["", "   ", None, 123])
def test_answer_question_invalid_question(question):
    """Rechaza preguntas vacías o de tipo incorrecto."""
    with pytest.raises(ValueError, match="La pregunta no puede estar vacía"):
        rag_chain.answer_question(question)


@pytest.mark.parametrize("k", [0, -1, 1.5, "4", True])
def test_answer_question_invalid_k(k):
    """Rechaza valores no válidos para k."""
    with pytest.raises(ValueError, match="k debe ser un entero"):
        rag_chain.answer_question("¿Qué es la PRL?", k=k)


def test_answer_question_custom_k(fragments):
    """Permite personalizar el número de fragmentos."""
    retriever = Mock(return_value=fragments)
    generator = Mock(return_value="Respuesta.")

    rag_chain.answer_question(
        "¿Qué protecciones hay?",
        k=2,
        retriever=retriever,
        generator=generator,
    )

    retriever.assert_called_once_with(
        "¿Qué protecciones hay?",
        k=2,
    )


def test_answer_question_retrieval_error():
    """Gestiona los errores de recuperación."""
    retriever = Mock(side_effect=Exception("Error de Chroma"))

    with pytest.raises(
        RuntimeError,
        match="Error al recuperar la documentación",
    ):
        rag_chain.answer_question(
            "¿Qué es la PRL?",
            retriever=retriever,
        )


def test_answer_question_generation_error(fragments):
    """Gestiona los errores del modelo."""
    retriever = Mock(return_value=fragments)
    generator = Mock(side_effect=Exception("Error de Groq"))

    with pytest.raises(
        RuntimeError,
        match="Error al generar la respuesta",
    ):
        rag_chain.answer_question(
            "¿Qué es la PRL?",
            retriever=retriever,
            generator=generator,
        )


@pytest.mark.parametrize("response", ["", "   ", None, 123])
def test_answer_question_invalid_generation(fragments, response):
    """Rechaza las respuestas vacías o de tipo incorrecto."""
    retriever = Mock(return_value=fragments)
    generator = Mock(return_value=response)

    with pytest.raises(
        RuntimeError,
        match="El modelo no ha generado una respuesta válida",
    ):
        rag_chain.answer_question(
            "¿Qué es la PRL?",
            retriever=retriever,
            generator=generator,
        )