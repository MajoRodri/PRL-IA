"""
rag_chain.py

Orquestación del pipeline RAG: recuperación semántica + generación de respuesta.
Responsable: Persona 3 — RAG y API.
"""

from typing import Callable

from src import vector_store
from src.llm_service import generate_response


# Respuesta estática cuando no hay documentación relevante (usada en tests).
NO_CONTEXT_ANSWER = (
    "No he encontrado información en la documentación disponible "
    "para responder a esta pregunta. Consulta con el responsable "
    "de prevención de riesgos laborales."
)

# Prompt conversacional para saludos y preguntas fuera de tema (usado en la API).
_NO_CONTEXT_PROMPT = (
    "Eres Paco, un asistente conversacional especializado en Prevención de Riesgos "
    "Laborales (PRL) en España. Responde siempre en español y de forma amigable.\n\n"
    "El usuario ha enviado este mensaje: \"{question}\"\n\n"
    "Si es un saludo o mensaje casual, salúdale con naturalidad y explícale brevemente qué puedes "
    "hacer: resolver dudas sobre normativa PRL, EPIs, obligaciones del empresario, evaluación de "
    "riesgos y documentación oficial. Anímale a hacer una consulta concreta.\n"
    "Si pregunta algo fuera del ámbito PRL, indícale amablemente que estás especializado en PRL "
    "y redirigele hacia ese tema. Sé breve y cercano."
)

_RELEVANCE_THRESHOLD = 0.72


def _format_context(fragments: list[dict]) -> str:
    """Prepara los fragmentos recuperados para el prompt."""
    sections = []
    for index, fragment in enumerate(fragments, start=1):
        metadata = fragment.get("metadata") or {}
        source = metadata.get("source", "Fuente desconocida")
        page = metadata.get("page", "No disponible")
        section = metadata.get("section", "Sin sección")
        content = fragment.get("text", "")
        sections.append(
            f"[{index}]\n"
            f"Documento: {source}\n"
            f"Página: {page}\n"
            f"Sección: {section}\n"
            f"Contenido:\n{content}"
        )
    return "\n\n".join(sections)


def _build_prompt(question: str, context: str) -> str:
    """Construye el prompt con instrucciones de respuesta fundamentada."""
    return f"""
Eres Paco, un asistente especializado en Prevención de Riesgos Laborales (PRL) para el mercado español.

Tu objetivo es dar una respuesta útil y fundamentada. Usa el contexto documental como fuente principal.
Si el contexto no cubre completamente la pregunta, complétala con tu conocimiento de la normativa PRL
española (LPRL, RGPRL, RD específicos, guías técnicas del INSST) indicándolo brevemente.

INSTRUCCIONES:
1. Responde en español, de forma clara y estructurada.
2. Prioriza la información del contexto documental y cita las fuentes con [1], [2], etc.
3. Si completas con conocimiento PRL general, señálalo con "Según la normativa PRL...".
4. No inventes artículos, páginas ni títulos de documentos que no aparezcan en el contexto.
5. Si las fuentes ofrecen información contradictoria, indícalo.
6. Ve directo al punto — sin frases introductorias como "Basándome en los fragmentos...".

CONTEXTO DOCUMENTAL:
{context}

PREGUNTA:
{question}

RESPUESTA:
""".strip()


def answer_question(
    question: str,
    k: int = 4,
    *,
    retriever: Callable | None = None,
    generator: Callable | None = None,
) -> dict:
    """
    Recupera documentación y genera una respuesta fundamentada.
    Implementación de Persona 3 — compatible con los tests.

    Returns:
        {"answer": str, "sources": list[dict]}  ← fragmentos crudos
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero mayor o igual que 1.")

    search_fn = retriever or vector_store.search
    generate_fn = generator or generate_response

    try:
        fragments = search_fn(question.strip(), k=k)
    except Exception as exc:
        raise RuntimeError("Error al recuperar la documentación.") from exc

    if not fragments:
        return {"answer": NO_CONTEXT_ANSWER, "sources": []}

    context = _format_context(fragments)
    prompt = _build_prompt(question.strip(), context)

    try:
        answer = generate_fn(prompt)
    except Exception as exc:
        raise RuntimeError("Error al generar la respuesta del asistente.") from exc

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("El modelo no ha generado una respuesta válida.")

    return {"answer": answer.strip(), "sources": fragments}


def answer_query(question: str, k: int = 8) -> dict:
    """
    Versión de la API: añade umbral de relevancia y flujo conversacional.
    Devuelve el formato que espera el frontend.

    Returns:
        {"answer": str, "sources": list[dict], "abstained": bool}
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    try:
        hits = vector_store.search(question.strip(), k=k)
    except Exception as exc:
        raise RuntimeError("Error al recuperar la documentación.") from exc

    relevant_hits = [h for h in hits if h.get("distance", 1) <= _RELEVANCE_THRESHOLD]

    # No hits at all → pure conversational (empty collection or off-topic greeting)
    if not hits:
        answer = generate_response(_NO_CONTEXT_PROMPT.format(question=question.strip()))
        return {"answer": answer, "sources": [], "abstained": False}

    # Some hits exist but none crossed the threshold → use best k=4 anyway so RAG
    # can still answer PRL questions that were diluted by a greeting prefix.
    rag_hits = relevant_hits if relevant_hits else hits[:4]

    context = _format_context(rag_hits)
    prompt = _build_prompt(question.strip(), context)

    try:
        answer = generate_response(prompt)
    except Exception as exc:
        raise RuntimeError("Error al generar la respuesta del asistente.") from exc

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("El modelo no ha generado una respuesta válida.")

    sources = [
        {
            "document": h["metadata"].get("source", "Documento desconocido"),
            "page": h["metadata"].get("page", 0),
            "chunk": h["text"][:300],
        }
        for h in rag_hits
    ]

    return {"answer": answer.strip(), "sources": sources, "abstained": False}
