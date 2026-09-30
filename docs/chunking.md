# Estrategia de ingesta y chunking

## Papel de este documento en el flujo

Este archivo explica las decisiones técnicas de la parte de Persona 1: cómo se cargan y limpian los documentos, cómo se dividen y qué metadatos se entregan a la siguiente capa.

Su posición es transversal al flujo `corpus → ingesta → chunking → embeddings → vector store`: documenta el contrato de salida de la ingesta y justifica experimentalmente la configuración de chunking que recibirá Persona 2. También conserva el método, los resultados y las limitaciones necesarias para defender la decisión técnica durante la presentación.

## Objetivo y contrato

El módulo de ingesta recibe rutas a documentos PDF, TXT o Markdown y entrega una lista de diccionarios con este contrato:

```python
{
    "text": "fragmento limpio",
    "metadata": {
        "document": "nombre.pdf",
        "source": "ruta/al/documento.pdf",
        "page": 8,
        "file_type": "pdf",
        "source_id": "ley-31-1995-prl",
        "title": "Ley 31/1995, de Prevención de Riesgos Laborales",
        "publisher": "BOE",
        "document_type": "legislation",
        "legal_status": "Texto consolidado informativo...",
        "source_url": "https://www.boe.es/...",
        "chunk_id": "nombre_p0008_c0012",
        "chunk_index": 12,
        "chunk_total": 84,
        "char_start": 120,
        "char_end": 1080,
        "section": "Artículo 15. Principios de la acción preventiva"
    }
}
```

`document`, `page` y `chunk_id` permiten que las capas de recuperación e interfaz muestren una fuente auditable. `section` solo se incluye cuando puede inferirse de forma conservadora; no se inventa si el formato no permite detectarla.

Cuando se usa `load_corpus("data/sources.json")`, la ingesta añade también título, organismo, URL oficial, tipo de documento y estatus. Esto permite que la respuesta distinga normas de obligado cumplimiento de guías técnicas no vinculantes.

## Limpieza

La limpieza corrige espacios repetidos, caracteres invisibles, saltos excesivos y palabras partidas por guiones de fin de línea. Conserva títulos, artículos, numeraciones y listas porque aportan contexto jurídico y preventivo. Las páginas sin texto se omiten; si todo el PDF carece de texto extraíble se informa de que puede requerir OCR.

## Estrategia elegida

La configuración seleccionada después de la comparación experimental es:

- Tamaño máximo: **1000 caracteres**.
- Solapamiento: **200 caracteres** (20 % del tamaño máximo).
- Unidad de trazabilidad: una página; ningún chunk mezcla páginas distintas.
- Puntos de corte preferidos: párrafo, final de frase y espacio, por ese orden.

Los documentos del corpus combinan legislación, artículos, anexos, listas y explicaciones técnicas. Un límite por caracteres mantiene el pipeline independiente del tokenizador del futuro modelo de embeddings. Los cortes semánticos reducen frases truncadas y el solapamiento conserva contexto en definiciones o medidas que cruzan el límite. Mantener cada chunk dentro de una página simplifica la cita de fuentes y evita intervalos de página ambiguos.

## Comparación experimental

### Datos y método

La comparación se ejecutó sobre las **9 fuentes oficiales** del corpus, que contienen **750 páginas con texto**. Se prepararon **10 preguntas de referencia** que cubren las nueve fuentes. Cada pregunta declara:

- la fuente oficial esperada;
- una o varias páginas de referencia;
- las frases de evidencia que debería contener el contexto recuperado.

Las preguntas están en `data/evaluation/chunking_questions.json`. Antes de ejecutar el benchmark, el script verifica que todas las fuentes, páginas y frases de evidencia existan realmente en el corpus.

Para aislar el efecto del chunking de la implementación futura de Persona 2, se utilizó recuperación léxica BM25 y `top_k=5`. Las tres configuraciones se evaluaron sobre las mismas páginas y preguntas mediante `scripts/evaluate_chunking.py`.

### Métricas

- **Hit@5:** proporción de preguntas para las que aparece al menos un chunk de la fuente y página esperadas entre los cinco primeros resultados.
- **MRR:** media del inverso de la posición del primer chunk correcto. Un valor mayor indica que la página esperada aparece antes.
- **Precisión@5:** proporción media de los cinco resultados que pertenecen a la fuente y página esperadas.
- **Evidencia@5:** proporción media de frases de evidencia presentes en los chunks correctos recuperados.
- **Ratio del índice:** caracteres totales indexados divididos por caracteres originales. Mide la duplicación introducida por el overlap.

### Resultados

| Configuración | Chunks | Longitud media | Ratio del índice | Hit@5 | MRR | Precisión@5 | Evidencia@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 500 / 50 | 7540 | 411,17 | 1,1188 | 90 % | **0,7333** | 30 % | 50,67 % |
| 800 / 120 | 4956 | 659,62 | 1,1797 | 90 % | 0,7000 | 30 % | 70,00 % |
| **1000 / 200** | **4170** | 827,21 | 1,2448 | 90 % | 0,6833 | **34 %** | **80,00 %** |

Los resultados detallados por pregunta y los cinco chunks recuperados se conservan en `data/evaluation/chunking_results.json`.

### Decisión

Se elige **1000/200** porque:

1. Mantiene el mismo Hit@5 del 90 % que las otras configuraciones.
2. Recupera el 80 % de las evidencias esperadas, frente al 70 % de `800/120` y el 50,67 % de `500/50`.
3. Obtiene la mejor precisión dentro del top‑5, un 34 %.
4. Genera 4170 chunks, un 44,7 % menos que `500/50`, lo que reduce el número de embeddings y el tamaño de la colección vectorial.
5. Aunque su MRR es menor, en las preguntas acertadas la página correcta aparece entre las tres primeras posiciones. Para el RAG se recuperarán varios chunks, por lo que la cobertura de evidencia es más importante que una diferencia pequeña dentro del top‑5.

El coste de esta elección es un ratio de índice mayor, 1,2448, debido al overlap de 200 caracteres. Se acepta porque mejora de forma clara la continuidad y la cobertura de evidencia.

La pregunta sobre los principios de la acción preventiva no recuperó la página de referencia dentro del top‑10 en ninguna configuración. El corpus contiene reproducciones y comentarios de la misma normativa dentro de varias guías, por lo que una búsqueda léxica puede priorizar otra fuente que contenga términos similares. Este caso deberá revisarse durante la evaluación del retriever semántico.

## Reproducción del experimento

Con los PDF descargados en `data/raw/`, ejecutar:

```bash
python scripts/evaluate_chunking.py
```

El script vuelve a validar las referencias, procesa las tres configuraciones y actualiza `data/evaluation/chunking_results.json`. No necesita librerías adicionales aparte de las dependencias del proyecto.

## Metadatos y secciones

Los números de página PDF son de base uno. TXT y Markdown usan página 1 para conservar un esquema escalar compatible con ChromaDB. La detección de secciones reconoce encabezados Markdown, texto corto en mayúsculas y rótulos habituales como capítulo, sección, artículo, anexo o apéndice. La ruta original se conserva en `source`.

## Limitaciones conocidas

- BM25 es un proxy léxico reproducible; no sustituye la evaluación con el modelo de embeddings definitivo.
- Las diez preguntas son una muestra dirigida y no representan todas las consultas posibles.
- Las fuentes oficiales repiten parte de la legislación, lo que puede reducir la métrica de página exacta aunque el contenido recuperado sea correcto.
- Los PDF escaneados sin capa de texto necesitan OCR, fuera del alcance del MVP inicial.
- Las tablas complejas y maquetaciones a varias columnas pueden perder parte de su estructura al extraerse con `pypdf`.
- Los encabezados y pies repetidos se conservan por defecto: eliminarlos sin comparar páginas puede borrar contenido legal válido.
- La detección de secciones es heurística y debe considerarse metadato opcional.

Cuando Persona 2 tenga disponible el modelo de embeddings y ChromaDB, debe repetirse el mismo conjunto de preguntas con el retriever semántico. La configuración solo debería cambiar si esa evaluación contradice de forma clara estos resultados.

## Verificación automatizada

Las pruebas cubren PDF multipágina, TXT, Markdown, limpieza, formatos no admitidos, documentos vacíos, división en varios chunks, overlap, límites de tamaño y metadatos obligatorios. Se ejecutan con:

```bash
python -m unittest discover -s tests -v
```
