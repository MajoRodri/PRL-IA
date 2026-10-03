# Contratos de integración de persona 5

Base revisada el 29/09/2026: rama `dev`, commit `84825054735f0843c46bec058456415781d29c95`. En esa base `ingestion.py`, `chunking.py`, `vector_store.py`, `rag_chain.py` y `api.py` están vacíos. Por eso no se inventan nombres de sus funciones. Los contratos siguientes son una propuesta ejecutable que el equipo debe acordar.

## P1: procesamiento

El objeto inyectado en `DocumentService(processor=...)` debe implementar:

```python
process(path: Path, *, document_id: str, source: str, category: str) -> Sequence[Chunk]
```

`path` es un original local guardado por el servicio. La salida usa `src.retrieval.Chunk`, con identificadores únicos, `document_id` conservado, texto no vacío, `source` igual al nombre original, `category` conservada, página desde 1 o `None` y sección opcional. Nunca inventar una página de un TXT ni perder la procedencia del PDF.

El adaptador de P1 debe llamar a sus funciones reales de ingesta y chunking y convertir sus resultados a `Chunk`. Si no hay texto o hay un formato ilegible, debe fallar de forma explícita. El servicio registra `failed` y mantiene el original para reintento. No se permite devolver una lista vacía como éxito.

La demo realiza limpieza de espacios y fragmentación por palabras, sin atravesar páginas de PDF: 180 palabras y 30 de overlap. Así conserva página y da una unidad manejable para probar. No cuenta tokens, no extrae estructura, tablas ni OCR. P1 deberá evaluar la estrategia definitiva en los documentos PRL reales; tablas, listas y negaciones deben conservar sentido. Al cambiar el procesador, reindexar los documentos afectados y versionar la configuración.

## P2: índice

El objeto inyectado en `DocumentService(index=...)` cumple `DocumentIndex`:

```python
replace_document(document_id: str, chunks: Sequence[Chunk]) -> None
search(query: str, *, limit: int, filters: Mapping[str, str | int]) -> Sequence[Hit]
delete_document(document_id: str) -> None
```

Obligaciones:

1. `replace_document` reemplaza todos los fragmentos de ese documento sin duplicarlos. Debe ser atómico o restaurar el estado anterior si falla. No basta con un `delete` seguido de varios `add` sin recuperación. El adaptador real puede usar generaciones de índice y activación controlada; esa estrategia corresponde a P2.
2. `delete_document` elimina todos sus fragmentos; repetir la operación debe ser seguro aunque ya no existan.
3. `search` aplica todos los filtros exactos antes de truncar candidatos y devuelve hasta `limit`, con puntuaciones descendentes.
4. `Hit.score` es finito y pertenece a [0, 1]; un valor mayor significa más relevancia. No pasar directamente una distancia de Chroma, donde menor distancia suele significar más cercanía. Elegir y documentar la conversión según la métrica concreta de la colección; calibrar el umbral en un conjunto de desarrollo. Los scores de la demo y del índice vectorial no son intercambiables.
5. Conservar `document_id`, `chunk_id`, texto, fuente, página y sección. Omitir metadatos nulos en Chroma si su versión/configuración no los admite y reconstruirlos como `None` al leer.
6. Si se usa E5, acordar prefijos de query/passage, normalización, dimensión y modelo exacto entre indexación y consulta. No mezclar embeddings de modelos distintos.

El contrato puede comprobarse con dobles en los tests actuales. La conexión a una colección Chroma real y su persistencia deben probarse una vez esté disponible P2. No se han anunciado esas pruebas como ejecutadas.

## Conectar los componentes disponibles

La inyección ya funciona. Este ejemplo usa los componentes demo existentes y puede ejecutarse tal cual; reemplazar ambos objetos por los adaptadores del equipo cuando existan:

```python
from pathlib import Path
from src.document_service import DocumentService, DemoProcessor, SQLiteDemoIndex

root = Path("data/persona5")
service = DocumentService(
    root,
    processor=DemoProcessor(),
    index=SQLiteDemoIndex(root / "documents.sqlite3"),
)
result = service.search("trabajos en altura", k=4)
```

Compartir **la misma instancia `service`** entre el router y la recuperación del RAG. No consultar el índice directamente desde el RAG: se saltaría el filtro de estados del catálogo. No crear múltiples servicios sobre el mismo directorio durante solicitudes. El MVP usa un worker; más workers requieren coordinación entre procesos y recuperación transaccional diseñada para ello.

## P3: incluir router en FastAPI

La persona 3 integra estas líneas en su creación de aplicación, sin reemplazar el resto de `src/api.py`:

```python
from pathlib import Path
from fastapi import FastAPI
from src.api_documents import create_documents_router
from src.document_service import DocumentService

app = FastAPI(title="PRL-IA")
service = DocumentService(Path("data/persona5"))  # inyectar aquí P1/P2 al integrarlos
app.include_router(create_documents_router(service))
```

Para crear contexto, usar `service.search(question, k=4, min_score=umbral_calibrado)`. El `RetrievalResult` contiene `hits`; cada uno aporta `chunk` y `score`.

Si no hay hits: devolver `answer` indicando falta de información, `sources: []` y `abstained: true`, sin pedir al modelo que complete la respuesta con conocimiento propio. Si hay hits, pasar solo los fragmentos autorizados al prompt, citarlos y verificar la fidelidad de la respuesta. `has_context=true` no demuestra que el modelo vaya a responder correctamente.

Si LangChain/LlamaIndex necesita su propio tipo de documento, P3 transforma cada `Chunk` al tipo de su versión instalada. La recuperación P5 no depende del framework y no necesita heredar una clase para probarse.

## P4: consumo de API

- Envío de documentos: `multipart/form-data`, clave `file`, categoría opcional `category`. No JSON para el binario.
- Mostrar `status`, `error` y `document_id`. Una respuesta 422 que contiene `document_id` significa que existe un registro fallido recuperable, no que se haya perdido la carga.
- Reindexar desde una acción explícita; no recargar el mismo archivo en bucle ante un 409.
- La API de recuperación devuelve `sources[].text` y `source`. El contrato sugerido para la respuesta RAG final usa `chunk` y `document`: P3 debe realizar esa conversión explícita, sin asumir que los nombres coinciden.
- Presentar texto como texto escapado; nunca ejecutar HTML o instrucciones del documento.
- Acordar mismo origen/proxy o política CORS concreta al conectar un navegador. No habilitar acceso público indiscriminado.

## Revisión antes del PR de integración

- Con P1: PDF multipágina, TXT, caracteres españoles, documentos sin texto y metadatos.
- Con P2: sustitución completa, borrado, filtros, conversión de score, persistencia y fallos parciales.
- Con P3: ausencia de contexto, fuentes reales, documentos maliciosos y abstención.
- Con P4: carga válida, duplicada, fallida, estado del procesamiento y representación de fuentes.
- Después: ejecutar la evaluación con documentos revisados por una persona competente en PRL.

Fuentes técnicas consultadas: [FastAPI: archivos](https://fastapi.tiangolo.com/tutorial/request-files/) y [Chroma: filtros de metadatos](https://docs.trychroma.com/docs/querying-collections/metadata-filtering). Consultadas el 29/09/2026; los contratos locales son decisiones de este módulo, no interfaces atribuidas al código aún vacío del equipo.
