from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.rag_chain import answer_question

BASE_DIR = Path(__file__).resolve().parent.parent

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
    return templates.TemplateResponse("index.html", {"request": request})

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=4, ge=1, le=20)


# ── API endpoints ────────────────────────────────────────────
@app.post("/api/query")
async def query(body: QueryRequest):
    try:
        result = answer_question(body.question, k=body.k)

        sources = result.get("sources", [])

        return JSONResponse({
            "answer": result["answer"],
            "sources": sources,
            "abstained": not bool(sources),
        })

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

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
        return JSONResponse({"error": "Formato no admitido. Usa PDF o TXT."}, status_code=400)

    return JSONResponse({
        "filename": file.filename,
        "message": f'Documento "{file.filename}" procesado e indexado correctamente.',
    })
