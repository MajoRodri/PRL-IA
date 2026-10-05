import asyncio
import logging
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
    k: int = Field(default=4, ge=1, le=20)


# ── Helpers ──────────────────────────────────────────────────
def _index_document(path: Path) -> int:
    """Carga, fragmenta e indexa un documento en ChromaDB. Devuelve nº de chunks."""
    from src.ingestion import load_document
    from src.chunking import split_documents
    from src.vector_store import get_collection

    pages = load_document(path)
    chunks = split_documents(pages)

    if not chunks:
        return 0

    ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]
    texts = [chunk["text"] for chunk in chunks]
    metadatas = [
        {
            "source": chunk["metadata"]["document"],
            "page": int(chunk["metadata"]["page"]),
            "section": chunk["metadata"].get("section") or "",
        }
        for chunk in chunks
    ]

    collection = get_collection()
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
    return len(chunks)


# ── API endpoints ─────────────────────────────────────────────
@app.post("/api/query")
async def query(body: QueryRequest):
    try:
        result = answer_query(body.question, k=body.k)
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
            {"error": "Formato no admitido. Usa PDF o TXT."},
            status_code=400,
        )

    content = await file.read()
    dest = RAW_DIR / Path(file.filename).name
    dest.write_bytes(content)

    try:
        loop = asyncio.get_running_loop()
        n_chunks = await loop.run_in_executor(None, _index_document, dest)
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
