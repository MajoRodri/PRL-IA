# Integración de ChromaDB (persona 2) con gestión documental (persona 5)

## Qué conecta

`api_documents_chroma.create_app()` obtiene la colección mediante
`src.vector_store.get_collection()` y entrega un `ChromaDocumentIndex` al
`DocumentService` existente. El adaptador cumple el contrato de `retrieval.py`.

El archivo de la persona 2 se conserva. El adaptador usa su colección y su
función de embeddings; no utiliza sus funciones `search()` y `add_fragments()`
porque esas interfaces no cubren el borrado, la sustitución ni los filtros de P5.

Archivos nuevos:

- `src/chroma_adapter.py`: búsquedas filtradas, puntuaciones, sustitución y borrado.
- `src/api_documents_chroma.py`: arranque de la API con el índice de P2.
- `tests/test_chroma_adapter.py`: doce pruebas de integración.
- Este documento.

Se mantiene el procesador demo PDF/TXT de P5. La integración definitiva con la
ingesta de P1 requiere adaptar su procesador al contrato `DocumentProcessor`.
Tampoco se incorpora el LLM ni la cadena RAG de P3.

## Antes de arrancar

1. Trabaja desde la raíz del repositorio, con `venv` activado.
2. Comprueba que tu copia de `src/vector_store.py` contiene la implementación
   de P2, incluida `get_collection()`. Si está vacía, aún falta integrar su rama.
   Que el archivo exista en GitHub en otra rama no significa que esté en la tuya.
3. Se requieren las dependencias de P5 y las que ya instalaste para P2:
   `chromadb==1.5.9`, `sentence-transformers==6.1.0` y PyTorch compatible.
   Este parche no modifica `requirements.txt` ni exige reinstalar paquetes.
4. Comprueba que `.gitignore` contiene `chroma_db/` y `data/persona5/`.
   Los documentos subidos y los índices son datos locales, no código para Git.

## Pruebas

```bash
python -m pytest tests/test_retrieval.py tests/test_documents_api.py tests/test_chroma_adapter.py -q
```

Resultado de validación del paquete: **61 pruebas correctas** (49 existentes y
12 nuevas), con Python 3.12 y ChromaDB 1.5.9. Puede aparecer el aviso ya conocido
sobre `httpx` en Starlette; un aviso no equivale a una prueba fallida.

Las nuevas pruebas utilizan **ChromaDB real con vectores deterministas de
prueba**. No descargan MiniLM ni miden su calidad semántica. Comprueban filtros
antes del ranking, conservación de metadatos, puntuaciones, reindexación,
borrado, reapertura del catálogo, API, arranque y recuperación ante fallos.
El arranque se comprueba inyectando la colección de prueba en la interfaz P2;
la descarga y ejecución del modelo real deben verificarse en el equipo local.

## Arranque y comprobación manual

Detén con Ctrl+C la API anterior si ocupa el puerto 8005. Desde la raíz:

```bash
python -m uvicorn src.api_documents_chroma:create_app --factory --host 127.0.0.1 --port 8005
```

Usa **un solo proceso/worker**, sin `--workers` adicional. Abre:

- `http://127.0.0.1:8005/health`: debe mostrar `"index": "ChromaDocumentIndex"`.
- `http://127.0.0.1:8005/docs`: interfaz para probar la API.

La primera ejecución del modelo puede descargar archivos y tardar. Después,
los embeddings se calculan localmente. El modelo y la colección siguen siendo
los definidos por P2: `all-MiniLM-L6-v2` y `prl_documentos`.

En Swagger:

1. Sube `data/examples/prevencion_demo.txt` mediante `POST /api/v1/documents`,
   con categoría `demo`. Debe devolver 201 y estado `indexed`.
2. Prueba `POST /api/v1/retrieval/query`:

   ```json
   {"query": "trabajos en altura", "k": 4, "min_score": 0.25, "filters": {"category": "demo"}}
   ```

3. Observa la fuente, el identificador y la puntuación obtenida. Anota el
   resultado real: este paquete no garantiza de antemano que supere el umbral.
4. Repite con un filtro `{"category": "categoria_inexistente"}`: debe devolver
   fuentes vacías y `has_context: false`.
5. Reindexa el documento usando su nuevo `document_id`, vuelve a consultar,
   bórralo y comprueba que ya no aparece.

**Los resultados semánticos pueden diferir de los de la demo léxica.** El umbral
0.25 es un valor inicial sin calibrar. Una pregunta ajena al documento puede
superarlo: hay que evaluar consultas pertinentes y no pertinentes en español
antes de decidir el umbral definitivo. `score` es similitud, no una probabilidad
ni una medida de veracidad. MiniLM es el modelo elegido por P2; esta integración
no demuestra que sea la mejor opción para el corpus español.

## Datos e independencia de la demo

- La colección P2 se guarda en `./chroma_db`, como en su archivo original.
- El catálogo, originales y registro de versiones activas de esta integración
  van en `data/persona5/chroma_integration/`.
- La demo léxica conserva sus datos anteriores; no se realiza una migración.
  Sube de nuevo los documentos que quieras probar con Chroma.
- Se puede cambiar el directorio del catálogo con `PRL_CHROMA_DOCUMENTS_DIR`.
  Conserva juntos ese directorio y `chroma_db` al mover o respaldar los datos.
- Arrancar desde otra carpeta se rechaza para evitar que la ruta relativa de
  P2 cree accidentalmente una base distinta.

No se cambia automáticamente el modelo ni la métrica de una colección existente.
Si el adaptador detecta una métrica distinta de `cosine` o un catálogo vinculado
a otra colección, detiene el arranque para que se revisen las rutas.

## Contrato y decisiones de implementación

Cada fragmento guarda `chunk_id`, `document_id`, `source`, `category`, y `page`
/ `section` cuando tienen valor. Los valores ausentes se reconstruyen como
`None` al devolver el resultado. La distancia coseno de Chroma se convierte en:

```text
score = max(0, min(1, 1 - distancia))
```

Los filtros se aplican en Chroma **antes** de limitar los resultados. El
`Retriever` existente aplica después el umbral, la visibilidad del documento y
la eliminación de duplicados. Su sobremuestreo acotado puede devolver menos de
`k` fuentes cuando hay muchos duplicados o documentos no visibles.

Para reindexar sin exponer un documento a medio escribir:

1. Se escriben los nuevos fragmentos con un identificador de versión único.
2. Solo cuando todos están escritos, SQLite publica esa versión como activa.
3. Se eliminan las versiones anteriores.

Si falla la escritura, sigue activa la versión anterior en el adaptador. El
servicio P5 marca el intento fallido y lo oculta hasta una reindexación correcta.
Si falla la limpieza después de publicar, la versión nueva sigue disponible;
las anteriores pueden ocupar espacio, pero quedan fuera de las búsquedas.
Reindexar o eliminar vuelve a intentar limpiarlas. Un cierre durante la
escritura puede dejar fragmentos no publicados; también quedan fuera de búsqueda.
No hay un recolector global automático de esos fragmentos.

Al borrar, primero se desactiva el documento y después se eliminan sus vectores.
Si Chroma falla, la API conserva el estado `deleting` y admite reintentar el
borrado. No se afirma que SQLite y Chroma formen una transacción distribuida.

**Todas las búsquedas del flujo P5/RAG deben pasar por `DocumentService.search`
o por su endpoint.** La función original `vector_store.search()` no conoce las
versiones activas y puede incluir datos antiguos o incompletos. Los fragmentos
insertados directamente por P2 sin los metadatos del adaptador no se adoptan ni
se borran: vuelve a subir esos documentos mediante el servicio para gestionarlos.

## Alcance de uso

MVP local, un solo proceso que gestiona documentos y un solo catálogo por
colección. No iniciar varias instancias escritoras sobre la misma colección ni
combinar distintos catálogos para gestionarla. La API de demo no añade
identidades de usuario ni aislamiento por empresa. Mantén el servidor en
`127.0.0.1` para estas pruebas locales.

La evidencia de evaluación y las precauciones de privacidad siguen en
`docs/evaluation.md` y `docs/ethical_use.md`. No utilizar el documento sintético
como instrucciones reales de prevención.

## Enlace para el README

Añade al final del apartado de instalación/ejecución, después del modo demo:

```markdown
### Integración documental con ChromaDB (personas 2 y 5)

El arranque con Chroma, las pruebas y los límites de la integración se describen
en [docs/chroma_integration.md](docs/chroma_integration.md).
```
