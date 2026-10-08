# Almacenamiento y recuperacion vectorial

## Papel de este documento en el flujo

Este archivo explica las decisiones tecnicas de como se
generan los embeddings, como se persisten en la base vectorial y como se
resuelve la busqueda semantica sobre los fragmentos ya troceados.

Su posicion es transversal al flujo `corpus -> ingesta -> chunking ->
embeddings -> vector store`: documenta el contrato de entrada que recibe de
Persona 1 (los fragmentos con metadatos) y el contrato de salida que
consumira el orquestador RAG (los resultados de busqueda semantica).

## Objetivo y contrato

El modulo `src/vector_store.py` recibe fragmentos ya troceados y enriquecidos
con metadatos, y entrega busqueda semantica sobre ellos. La entrada que
acepta `add_fragments` sigue este contrato:

```python
{
    "id": "identificador_unico_del_fragmento",
    "text": "contenido del fragmento",
    "metadata": {
        "source": "nombre_del_documento.pdf",
        "page": 3,
        "section": "Equipos de proteccion individual"
    }
}
```

La salida de `search(query, k=4)` sigue este contrato:

```python
{
    "text": "contenido del fragmento",
    "metadata": {"source": "...", "page": 3, "section": "..."},
    "distance": 0.1234
}
```

`metadata` viaja intacta desde la ingesta hasta el resultado de busqueda, lo
que permite que la capa de interfaz muestre una fuente auditable (documento,
pagina, seccion) junto a cada fragmento recuperado.

## Decisiones tecnicas

### Motor de base vectorial: ChromaDB

Se eligio ChromaDB en modo `PersistentClient`, con los datos guardados en
`./chroma_db`. Es open-source, se ejecuta en local sin infraestructura
adicional (no requiere levantar un servidor aparte) y ofrece una API sencilla
para colecciones y busqueda por similitud, adecuada para el alcance de este
MVP.

### Modelo de embeddings: all-MiniLM-L6-v2

Se eligio `all-MiniLM-L6-v2` (sentence-transformers) porque es un modelo
ligero, gratuito y ejecutable en local, con buen equilibrio entre velocidad y
calidad semantica para una coleccion de tamano pequeno/medio como la de este
proyecto. Al ejecutarse localmente, evita enviar contenido documental a APIs
externas de pago, lo que refuerza la privacidad de la informacion de la
empresa.

### Metrica de distancia: similitud coseno

La coleccion se configura con `metadata={"hnsw:space": "cosine"}`, la metrica
estandar para comparar embeddings de texto normalizados y la que mejor
resultado da en la practica con `sentence-transformers`.

### Cliente unico (singleton)

El `PersistentClient` de ChromaDB se crea una sola vez al importar el modulo
(`_client`) y se reutiliza en todas las llamadas a `get_collection`. La
version inicial creaba una instancia nueva de `PersistentClient` en cada
llamada, lo que anadia coste de inicializacion repetido y podia generar
conflictos de acceso al mismo directorio de persistencia si se invocaba desde
varios puntos del pipeline. `get_client()` expone esta instancia unica para
quien necesite acceder al cliente directamente.

## Interfaz publica

| Funcion | Entrada | Salida | Descripcion |
|---|---|---|---|
| `get_client()` | - | `PersistentClient` | Devuelve la instancia unica del cliente de ChromaDB. |
| `get_collection()` | - | `Collection` | Obtiene o crea la coleccion `prl_documentos` con la funcion de embeddings y metrica configuradas. |
| `add_fragments(fragments)` | Lista de `{"id", "text", "metadata"}` | `int` (cantidad guardada) | Indexa fragmentos en la coleccion vectorial. Lanza `ValueError` si la lista esta vacia. |
| `search(query, k=4)` | `query: str`, `k: int` | Lista de `{"text", "metadata", "distance"}` | Devuelve los `k` fragmentos mas relevantes semanticamente. Devuelve `[]` si la coleccion no tiene documentos. |

## Verificacion automatizada

Las pruebas cubren, mediante mocks (sin ChromaDB real ni descarga del modelo
de embeddings):

- Reutilizacion del cliente unico: `get_client()` devuelve siempre la misma
  instancia y no crea clientes nuevos en llamadas repetidas.
- Configuracion de la coleccion: nombre, funcion de embeddings y metrica de
  distancia correctos al crearla.
- `add_fragments`: transformacion correcta de la lista de fragmentos al
  formato de ChromaDB y rechazo de listas vacias con `ValueError`.
- `search`: lista vacia sin consultar la coleccion cuando no hay documentos,
  transformacion correcta de la respuesta de ChromaDB al formato de salida, y
  uso de `k=4` por defecto.

Se ejecutan con:

```bash
python -m unittest tests.test_vector_store -v
```

## Limitaciones conocidas

- El indice vectorial se persiste en disco local (`./chroma_db`); no esta
  pensado para escalar a multiples instancias concurrentes sin coordinacion
  adicional.
- La calidad de la busqueda depende del modelo de embeddings elegido; no se
  ha comparado `all-MiniLM-L6-v2` frente a otros modelos multilingues o mas
  grandes, algo que podria revisarse si la calidad de recuperacion semantica
  no iguala a la evaluacion lexica (BM25) realizada en la fase de chunking.
- `search` no aplica ningun filtro por metadatos (por ejemplo, restringir a
  un `document_type` concreto); toda la logica de filtrado queda delegada al
  orquestador RAG si se necesita en el futuro.