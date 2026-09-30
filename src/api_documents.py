"""API de persona 5. Arranque independiente: uvicorn src.api_documents:app --factory."""
from pathlib import Path
from typing import Annotated
import os

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from src.document_service import DocumentError, DocumentService


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=4, ge=1, le=20, strict=True)
    min_score: float = Field(default=0.25, ge=0, le=1)
    filters: dict[str, StrictStr | StrictInt] = Field(default_factory=dict)


def create_documents_router(service: DocumentService) -> APIRouter:
    """La persona 3 puede incluir este router en su FastAPI sin crear otra API."""
    router = APIRouter(prefix="/api/v1", tags=["documents-persona5"])

    def run(action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except DocumentError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Servicio documental temporalmente no disponible.") from exc

    @router.post("/documents", status_code=201)
    def upload_document(file: Annotated[UploadFile, File()], category: Annotated[str, Form()] = "general"):
        try:
            content = file.file.read(service.max_bytes + 1)
        finally:
            file.file.close()
        record = run(service.upload, file.filename or "", content, category=category)
        # Registro creado pero no indexado: devuelve ID y estado para reintentar.
        return JSONResponse(status_code=201 if record["status"] == "indexed" else 422, content=record)

    @router.get("/documents")
    def list_documents():
        return {"documents": run(service.list)}

    @router.get("/documents/{document_id}")
    def get_document(document_id: str):
        return run(service.get, document_id)

    @router.post("/documents/{document_id}/reindex")
    def reindex_document(document_id: str):
        record = run(service.reindex, document_id)
        return JSONResponse(status_code=200 if record["status"] == "indexed" else 422, content=record)

    @router.delete("/documents/{document_id}", status_code=204)
    def delete_document(document_id: str):
        run(service.delete, document_id)

    @router.post("/retrieval/query")
    def retrieve(body: SearchRequest):
        return run(service.search, **body.model_dump()).to_dict()

    return router


def create_app(storage_dir: Path | None = None, *, service: DocumentService | None = None) -> FastAPI:
    service = service or DocumentService(storage_dir or Path(os.getenv("PRL_P5_DATA_DIR", "data/persona5")))
    app = FastAPI(title="PRL-IA | Documentos y recuperación", version="0.1.0",
                  description="Módulo P5. La configuración predeterminada utiliza búsqueda léxica demo, sin LLM.")
    app.state.document_service = service
    app.include_router(create_documents_router(service))

    @app.get("/health")
    def health():
        return {"status": "ok", "component": "persona5", "index": type(service.index).__name__,
                "processor": type(service.processor).__name__}

    return app


# Factory sin escrituras al importar. Uvicorn ejecuta la creación explícitamente con --factory.
def app():
    return create_app()
