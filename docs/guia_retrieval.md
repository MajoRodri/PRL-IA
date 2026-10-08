## La idea

Imagina una biblioteca. Los documentos son libros; el procesamiento los divide en fichas; el índice ayuda a encontrarlas; el recuperador elige las fichas útiles para una pregunta. El LLM del equipo redactará después usando esas fichas. Tu parte decide qué entra en esa biblioteca, mantiene su estado y entrega contexto con procedencia.

## Qué hace cada archivo

1. `retrieval.py`: define `Chunk` (fragmento), `Hit` (fragmento con puntuación) y `Retriever` (selección). Los `Protocol` son contratos: dicen qué métodos necesita tu código sin obligarte a conocer la implementación de Chroma.
2. `document_service.py`: valida el archivo, le asigna un ID, conserva el original, registra metadatos y llama al procesador y al índice. También permite reindexar y eliminar.
3. `api_documents.py`: publica estas operaciones mediante HTTP. FastAPI crea `/docs` para probarlas sin construir una pantalla propia.
4. Los dos archivos de tests comprueban comportamientos observables, incluidos los fallos. Cada test usa almacenamiento temporal para no tocar tus datos de demo.
5. `evaluation.md` distingue software correcto de recuperación útil y respuesta fiel. `ethical_use.md` explica los riesgos concretos.

## Sigue una carga en el código

- La API recibe `file` y `category`.
- `upload` verifica formato, tamaño y duplicados por SHA-256.
- Se guarda el original con un nombre UUID y se crea un registro `processing`.
- `processor.process` produce `Chunk` con fuente y página.
- `index.replace_document` guarda los fragmentos completos.
- El catálogo pasa a `indexed`; solo entonces se permite recuperarlos.

Si algo falla después de registrar: `failed`, original conservado y opción de reindexar. Si falla una eliminación: `deleting`, contexto oculto y opción de repetir. Se distingue «archivo recibido» de «documento disponible para buscar».

## Sigue una pregunta

`service.search` llama a `Retriever.retrieve`. El índice devuelve candidatos; el recuperador descarta scores bajos, documentos no visibles y duplicados. Conserva como máximo k y devuelve sus fuentes. Si no queda ninguno, informa `no_relevant_context`.

La recuperación demo busca palabras. Chroma buscará semejanza mediante embeddings. Tu lógica trabaja con el mismo contrato y podrá permanecer estable aunque cambie el buscador.

## Cuatro conceptos para defender

- **k:** máximo de fragmentos que entregas. Más no siempre es mejor: puede añadir ruido.
- **Umbral:** puntuación mínima que aceptas. Debe calibrarse; no es garantía de verdad.
- **Metadatos:** datos sobre el texto, como documento y página, para filtrar y citar.
- **Inyección de dependencias:** entregar al servicio un procesador/índice concreto. Como cambiar la impresora sin reescribir el documento que imprimes.

## Demo de cinco minutos

1. Arranca con el comando del README y abre `/docs`.
2. En `POST /api/v1/documents`, pulsa «Try it out», selecciona `data/examples/prevencion_demo.txt`, escribe categoría `demo` y ejecuta.
3. Explica `document_id`, `status` y `chunk_count` de la respuesta.
4. En `POST /api/v1/retrieval/query`, usa `{"query":"trabajos en altura","k":3,"filters":{"category":"demo"}}`.
5. Enseña el texto y la fuente. Aclara que no es una respuesta de un LLM.
6. Prueba `{"query":"salarios vacaciones"}` y explica la ausencia de contexto.
7. Ejecuta reindexación con el ID; el número de fragmentos no se duplica.
8. Elimina el documento y comprueba que deja de aparecer.

Si ya lo cargaste antes, el 409 es esperado. Consulta `GET /api/v1/documents` para recuperar su ID y reutilizarlo.

## Cómo contar el resultado con honestidad

Hemos desarrollado la gestión documental y la selección de contexto de forma independiente. Puede cargar, listar, reindexar y eliminar documentos, y recuperar fragmentos con fuentes y filtros. Hemos probado los fallos y la persistencia. El buscador actual es un baseline léxico; la integración con los embeddings del equipo se hace mediante un contrato. La evaluación sintética detecta que los sinónimos son una limitación. La fidelidad del LLM se evaluará cuando integremos el RAG.
