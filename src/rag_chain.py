"""
rag_chain.py

Orquestación del pipeline RAG: recuperación semántica + generación de respuesta.
Responsable: Persona 3 — RAG y API.
"""

from src.vector_store import search
from src.llm_service import generate_response

_SYSTEM = (
    "Eres un asistente experto en Prevención de Riesgos Laborales (PRL) en España. "
    "Usa los fragmentos de documentos para responder de forma directa, clara y estructurada. "
    "Responde siempre en español. Nunca inventes ni extrapoles datos que no estén en los fragmentos. "
    "No incluyas frases introductorias como 'Basándome en los fragmentos...' — ve directo al punto. "
    "Si los fragmentos no contienen suficiente información, dilo brevemente y ofrece lo que sí tienes."
)

_PROMPT_TEMPLATE = """{system}

Fragmentos de la normativa PRL:

{context}

---
Pregunta: {question}

Responde de forma directa. Usa listas numeradas si hay varios puntos."""

_NO_CONTEXT_PROMPT = (
    "Eres PRL Assistant, un asistente conversacional especializado en Prevención de Riesgos "
    "Laborales (PRL) en España. Responde siempre en español y de forma amigable.\n\n"
    "El usuario ha enviado este mensaje: \"{question}\"\n\n"
    "Si es un saludo o mensaje casual, salúdale con naturalidad y explícale brevemente qué puedes "
    "hacer: resolver dudas sobre normativa PRL, EPIs, obligaciones del empresario, evaluación de "
    "riesgos y documentación oficial. Anímale a hacer una consulta concreta.\n"
    "Si pregunta algo fuera del ámbito PRL, indícale amablemente que estás especializado en PRL "
    "y redirigele hacia ese tema.\n"
    "Sé breve y cercano."
)


def answer_query(question: str, k: int = 4) -> dict:
    """
    Ejecuta el pipeline RAG completo para una pregunta.

    Pasos:
      1. Busca los k fragmentos más relevantes en ChromaDB.
      2. Si hay contexto: genera respuesta fundamentada en los documentos.
         Si no hay contexto: responde de forma conversacional (saludo, ayuda, redirección).
      3. Genera la respuesta con el LLM de Groq.

    Returns:
        {
            "answer":    str,
            "sources":   list[dict],
            "abstained": bool
        }
    """
    # Umbral: distancia coseno > 0.5 → fragmentos no relevantes → flujo conversacional
    _RELEVANCE_THRESHOLD = 0.5

    hits = search(question, k=k)
    relevant_hits = [h for h in hits if h["distance"] <= _RELEVANCE_THRESHOLD]

    if not relevant_hits:
        answer = generate_response(_NO_CONTEXT_PROMPT.format(question=question))
        return {"answer": answer, "sources": [], "abstained": False}

    context_parts = []
    for i, hit in enumerate(relevant_hits, 1):
        meta = hit["metadata"]
        source = meta.get("source", "Documento desconocido")
        page = meta.get("page", "?")
        section = meta.get("section", "")
        header = f"[{i}] {source}, pág. {page}"
        if section:
            header += f" — {section}"
        context_parts.append(f"{header}\n{hit['text']}")

    context = "\n\n".join(context_parts)
    prompt = _PROMPT_TEMPLATE.format(
        system=_SYSTEM,
        context=context,
        question=question,
    )

    answer = generate_response(prompt)

    sources = [
        {
            "document": hit["metadata"].get("source", "Documento desconocido"),
            "page": hit["metadata"].get("page", 0),
            "chunk": hit["text"][:300],
        }
        for hit in relevant_hits
    ]

    return {"answer": answer, "sources": sources, "abstained": False}
