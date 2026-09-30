from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

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


# ── Mock data ────────────────────────────────────────────────
MOCK_RESPONSES = [
    {
        "keywords": ["altura", "caída", "andamio"],
        "answer": (
            "Para trabajos en altura, la Ley 31/1995 y el Real Decreto 1627/1997 establecen "
            "las siguientes medidas de protección obligatorias:\n\n"
            "1. Uso de arnés de seguridad homologado con punto de anclaje certificado.\n"
            "2. Instalación de redes de seguridad o plataformas de trabajo con barandillas "
            "de al menos 90 cm de altura, rodapié y barra intermedia.\n"
            "3. Señalización de la zona de trabajo y delimitación del área de exclusión bajo el punto de trabajo.\n"
            "4. Formación específica del trabajador en trabajos en altura antes de iniciar la tarea.\n\n"
            "El empresario está obligado a evaluar el riesgo de caída antes de comenzar cualquier trabajo "
            "en altura superior a 2 metros."
        ),
        "sources": [
            {"document": "Ley 31/1995 de Prevención de Riesgos Laborales", "page": 12, "chunk": "Artículo 15 — Principios de la acción preventiva: adoptar medidas que antepongan la protección colectiva a la individual."},
            {"document": "Real Decreto 1627/1997 — Obras de construcción", "page": 8, "chunk": "Anexo IV — Disposiciones mínimas de seguridad: protección frente al riesgo de caída de altura mediante barandillas, redes o arnés."},
        ],
    },
    {
        "keywords": ["epi", "equipo de protección", "individual", "guante", "casco", "gafa"],
        "answer": (
            "Según la Guía Técnica del INSST para la utilización de Equipos de Protección Individual (EPI), "
            "el empresario está obligado a:\n\n"
            "1. Proporcionar gratuitamente los EPIs adecuados al riesgo evaluado.\n"
            "2. Asegurarse de que los EPIs cuentan con marcado CE y declaración de conformidad.\n"
            "3. Informar y formar al trabajador sobre el uso correcto, mantenimiento y limitaciones del EPI.\n"
            "4. Sustituir los EPIs deteriorados o caducados sin coste para el trabajador.\n\n"
            "Los EPIs son la última barrera de protección y solo deben usarse cuando no sea posible "
            "eliminar o reducir el riesgo por medios colectivos."
        ),
        "sources": [
            {"document": "Guía Técnica para la utilización de EPIs — INSST", "page": 5, "chunk": "Capítulo 2 — Obligaciones del empresario: suministro gratuito, formación e información sobre el uso de EPIs."},
            {"document": "Ley 31/1995 de Prevención de Riesgos Laborales", "page": 22, "chunk": "Artículo 17 — Equipos de trabajo y medios de protección: el empresario adoptará las medidas necesarias para que los equipos sean adecuados."},
        ],
    },
    {
        "keywords": ["eléctrico", "electricidad", "tensión", "corriente"],
        "answer": (
            "La Guía Técnica del INSST para la protección frente al Riesgo Eléctrico establece que "
            "antes de iniciar cualquier trabajo en instalaciones eléctricas deben aplicarse las "
            "Cinco Reglas de Oro:\n\n"
            "1. Desconectar la instalación de todas las fuentes de tensión.\n"
            "2. Prevenir cualquier posible realimentación (bloqueo y enclavamiento).\n"
            "3. Verificar la ausencia de tensión con equipo de medida homologado.\n"
            "4. Poner a tierra y en cortocircuito todas las posibles fuentes de tensión.\n"
            "5. Proteger frente a elementos en tensión próximos y señalizar la zona.\n\n"
            "El incumplimiento de estas reglas es la causa más frecuente de accidentes eléctricos graves."
        ),
        "sources": [
            {"document": "Guía Técnica para la protección frente al Riesgo Eléctrico — INSST", "page": 34, "chunk": "Capítulo 5 — Trabajos en instalaciones eléctricas: las cinco reglas de oro como procedimiento obligatorio en trabajos sin tensión."},
            {"document": "Real Decreto 39/1997 — Reglamento de Servicios de Prevención", "page": 17, "chunk": "Artículo 7 — Contenido de la evaluación de riesgos: identificación de riesgos específicos como el riesgo eléctrico."},
        ],
    },
    {
        "keywords": ["empresario", "obligación", "deber", "responsabilidad"],
        "answer": (
            "La Ley 31/1995 de Prevención de Riesgos Laborales establece las siguientes obligaciones "
            "fundamentales del empresario:\n\n"
            "1. Garantizar la seguridad y salud de los trabajadores a su servicio en todos los aspectos "
            "relacionados con el trabajo (Art. 14).\n"
            "2. Realizar una evaluación inicial de los riesgos para la seguridad y salud de los "
            "trabajadores (Art. 16).\n"
            "3. Adoptar medidas preventivas con arreglo a los principios de la acción preventiva (Art. 15).\n"
            "4. Proporcionar a los trabajadores información, formación, consulta y participación en materia "
            "preventiva (Arts. 18 y 19).\n"
            "5. Garantizar la vigilancia periódica del estado de salud de los trabajadores (Art. 22)."
        ),
        "sources": [
            {"document": "Ley 31/1995 de Prevención de Riesgos Laborales", "page": 9, "chunk": "Artículo 14 — Derecho a la protección frente a los riesgos laborales: el empresario deberá garantizar la seguridad y la salud de los trabajadores."},
            {"document": "Ley 31/1995 de Prevención de Riesgos Laborales", "page": 11, "chunk": "Artículo 16 — Plan de prevención, evaluación de riesgos y planificación de la actividad preventiva."},
        ],
    },
    {
        "keywords": ["señal", "señalización", "emergencia", "evacuación", "salida"],
        "answer": (
            "La Guía Técnica del INSST sobre Señalización de Seguridad y Salud en el Trabajo indica que "
            "la señalización debe:\n\n"
            "1. Atraer la atención sobre la existencia de determinados riesgos, prohibiciones u obligaciones.\n"
            "2. Alertar a los trabajadores cuando se produzca una determinada situación de emergencia.\n"
            "3. Facilitar la localización e identificación de medios de protección, evacuación y primeros auxilios.\n\n"
            "Las señales de evacuación y emergencia deben ser de color verde con pictograma blanco, "
            "estar siempre iluminadas o ser fotoluminiscentes, y ubicarse de forma visible en todas "
            "las vías de evacuación y salidas de emergencia."
        ),
        "sources": [
            {"document": "Guía Técnica sobre Señalización de Seguridad y Salud — INSST", "page": 22, "chunk": "Capítulo 4 — Señales de salvamento o socorro: características, colores y ubicación de señales de evacuación y emergencia."},
        ],
    },
]

ABSTAIN_RESPONSE = {
    "answer": "",
    "sources": [],
    "abstained": True,
}


class QueryRequest(BaseModel):
    question: str


# ── API endpoints (mock) ────────────────────────────────────
@app.post("/api/query")
async def query(body: QueryRequest):
    q = body.question.lower()

    for entry in MOCK_RESPONSES:
        if any(kw in q for kw in entry["keywords"]):
            return JSONResponse({
                "answer": entry["answer"],
                "sources": entry["sources"],
                "abstained": False,
            })

    return JSONResponse(ABSTAIN_RESPONSE)


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
