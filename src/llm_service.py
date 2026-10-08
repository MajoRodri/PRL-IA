"""
llm_service.py

Servicio de conexión con el modelo de lenguaje de Groq.
Responsable: Persona 3 - RAG y API.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# Cargar las variables del .env situado en la raíz del proyecto.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

TEMPERATURE = 0.2
MAX_TOKENS = 1024


def get_llm() -> ChatGroq:
    """
    Inicializa y devuelve el modelo de lenguaje de Groq.

    La API key se obtiene de la variable de entorno GROQ_API_KEY.
    La temperatura baja favorece respuestas más consistentes.
    """
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key or not api_key.strip():
        raise ValueError(
            "Falta GROQ_API_KEY. Configúrala en el archivo .env."
        )

    try:
        return ChatGroq(
            model=GROQ_MODEL,
            api_key=api_key,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            timeout=30,
            max_retries=2,
        )
    except Exception as exc:
        raise RuntimeError(
            "No se ha podido inicializar el modelo de Groq."
        ) from exc


def generate_response_with_metrics(prompt: str) -> dict:
    """
    Envía un prompt al modelo y devuelve texto y consumo comunicado.

    Args:
        prompt: Texto que se enviará al modelo.

    Returns:
        Diccionario con answer y metrics.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("El prompt no puede estar vacío.")

    llm = get_llm()

    try:
        response = llm.invoke(prompt)
        return {"answer": response.content, "metrics": _token_usage(response)}
    except Exception as exc:
        raise RuntimeError(
            "Error al solicitar una respuesta a Groq."
        ) from exc


def _token_usage(response) -> dict:
    """Uso comunicado por el proveedor; None significa dato no disponible."""
    usage = getattr(response, "usage_metadata", None)
    metadata = getattr(response, "response_metadata", None)
    usage = usage if isinstance(usage, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    fallback = metadata.get("token_usage") or {}
    fallback = fallback if isinstance(fallback, dict) else {}

    def count(primary, legacy):
        for value in (usage.get(primary), fallback.get(legacy)):
            if type(value) is int and value >= 0:
                return value
        return None

    return {
        "input_tokens": count("input_tokens", "prompt_tokens"),
        "output_tokens": count("output_tokens", "completion_tokens"),
        "total_tokens": count("total_tokens", "total_tokens"),
    }


def generate_response(prompt: str) -> str:
    """Interfaz original: devuelve solo texto para los consumidores existentes."""
    return generate_response_with_metrics(prompt)["answer"]
