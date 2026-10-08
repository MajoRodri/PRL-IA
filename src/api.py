import asyncio
import logging
from time import perf_counter
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.rag_chain import answer_query

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

app = FastAPI(title="PRL Assistant")

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend" / "static"),
    name="static",
)

templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")


# ── Frontend ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ── Models ───────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=8, ge=1, le=20)


# ── Helpers ──────────────────────────────────────────────────
def _index_document(path: Path) -> int:
    """Carga, fragmenta e indexa un documento en ChromaDB. Devuelve nº de chunks.

    Si ya existían chunks del mismo archivo, los reemplaza de forma atómica:
    borra los anteriores e inserta los nuevos. Si la inserción falla, restaura
    los chunks originales antes de propagar la excepción.
    """
    from src.ingestion import load_document, EmptyDocumentError
    from src.chunking import split_documents
    from src.vector_store import get_collection

    try:
        pages = load_document(path)
    except EmptyDocumentError:
        return 0

    try:
        chunks = split_documents(pages)
    except ValueError:
        return 0

    if not chunks:
        return 0

    filename = path.name
    ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]
    texts = [chunk["text"] for chunk in chunks]

    # Pass through all scalar metadata; use document name as source (not full path).
    _SCALAR = (str, int, float, bool)
    metadatas = []
    for chunk in chunks:
        meta = {k: v for k, v in chunk["metadata"].items()
                if k != "source" and isinstance(v, _SCALAR)}
        meta["source"] = chunk["metadata"].get("document", filename)
        metadatas.append(meta)

    collection = get_collection()

    # Guardar versión anterior para poder hacer rollback si la inserción falla.
    old = collection.get(where={"source": filename})
    old_ids, old_texts, old_metas = old["ids"], old["documents"], old["metadatas"]

    if old_ids:
        collection.delete(ids=old_ids)

    try:
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
    except Exception:
        if old_ids:
            collection.upsert(ids=old_ids, documents=old_texts, metadatas=old_metas)
        raise

    return len(chunks)


# ── API endpoints ─────────────────────────────────────────────
@app.post("/api/query")
async def query(body: QueryRequest):
    started = perf_counter()
    try:
        result = answer_query(body.question, k=body.k)
        result = dict(result)
        result["metrics"] = {
            **(result.get("metrics") or {}),
            "server_latency_ms": round((perf_counter() - started) * 1000, 2),
        }
        return JSONResponse(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="No se ha podido generar la respuesta.",
        ) from exc


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    allowed = {".pdf", ".txt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        return JSONResponse(
            {"error": "Formato no admitido. Solo se permiten archivos PDF y TXT."},
            status_code=400,
        )

    content = await file.read()
    dest = RAW_DIR / Path(file.filename).name
    dest.write_bytes(content)

    try:
        loop = asyncio.get_running_loop()
        n_chunks = await loop.run_in_executor(None, _index_document, dest)
        if n_chunks == 0:
            dest.unlink(missing_ok=True)
            return JSONResponse(
                {"error": "El archivo está vacío o no contiene texto procesable."},
                status_code=422,
            )
        return JSONResponse({
            "filename": file.filename,
            "message": f'"{file.filename}" indexado correctamente ({n_chunks} fragmentos).',
            "chunks": n_chunks,
        })
    except Exception as exc:
        dest.unlink(missing_ok=True)
        return JSONResponse(
            {"error": f"Error al procesar el documento: {exc}"},
            status_code=500,
        )
