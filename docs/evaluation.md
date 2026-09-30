# Evaluación: primero recuperación, después generación

## Qué se evalúa ahora

Esta entrega separa tres preguntas:

1. ¿Funciona el software? Tests de entradas, estados, persistencia y errores.
2. ¿Recupera los fragmentos esperados? Comparación con referencias conocidas.
3. ¿El LLM responde de forma fiel? Pendiente de la integración RAG.

Una prueba de API aprobada no implica calidad semántica, y disponer de fuentes no demuestra fidelidad del modelo.

## Evidencia ejecutada el 29/09/2026

Entorno aislado Linux, Python 3.12; versiones directas en `requirements-persona5.txt` y entorno resuelto en `requirements-persona5-lock.txt`. No se ha ejecutado todavía en el ordenador WSL de María.

```bash
python -m pytest tests/test_retrieval.py tests/test_documents_api.py -q
# 49 passed, 1 warning
python -m scripts.evaluate_retrieval
```

Aviso observado: `StarletteDeprecationWarning` indica que el uso de `httpx` por `TestClient` está deprecado y recomienda `httpx2`. No impide ejecutar los tests con las versiones fijadas. Al actualizar el stack del equipo, revisar juntos cliente de pruebas y framework. No se oculta el aviso.

Los tests comprueban ranking, umbral, filtros, duplicados, scores inválidos, fuentes, sustitución atómica del índice demo, ciclo de API, persistencia al reiniciar, errores de lectura, tamaño, rutas, carga PDF con página, falta de OCR, fallos de adaptadores, exclusión de contextos fallidos y reintentos de eliminación/reindexación. El parser multipart normaliza ciertas rutas de archivo Windows; hay una prueba específica de ese comportamiento y otra de rechazo directo en el servicio.

## Microevaluación reproducible

Corpus: `tests/fixtures_retrieval.json`. Cinco fragmentos sintéticos, seis consultas que deberían encontrar fuente y dos fuera de alcance. Referencias definidas manualmente para probar software, sin revisión profesional de PRL. No representan una muestra real ni constituyen un conjunto independiente de test para ajustar parámetros.

Configuración: `k=3`, `min_score=0.25`, normalización de palabras y acentos; un caso incluye filtro de categoría. La puntuación es cobertura de términos de la consulta, no similitud semántica.

| Métrica | Resultado observado | Denominador |
|---|---:|---|
| Recall@3 medio | 0,8333 | 6 consultas con fuente |
| Precision@3 media | 0,2778 | 6 consultas, denominador fijo de 3 posiciones |
| MRR@3 | 0,8333 | 6 consultas con fuente |
| Contexto vacío correcto | 1,0000 | 2 consultas sin fuente |

Definiciones:

- Recall@k = número de fragmentos relevantes recuperados / total de fragmentos relevantes de la pregunta.
- Precision@k = número de fragmentos relevantes recuperados / k, aun devolviendo menos de k. Por eso esta cifra es baja en un corpus con una única referencia relevante por consulta; no equivale al porcentaje de resultados devueltos que son correctos.
- MRR@k = media de 1/rango del primer resultado relevante; cero si no aparece.
- Contexto vacío correcto = consultas sin referencias que devuelven cero fragmentos / consultas sin referencias. No mide la abstención de un LLM.

Q1-Q5 recuperan su fragmento en primera posición. Q6, «salida urgente del edificio», no encuentra el fragmento sobre evacuación: la demo no reconoce sinónimos. Q7-Q8 no devuelven resultados. Esta limitación motivará comparar el índice semántico, sin dar por hecho que lo solucionará siempre.

## Plan para evaluar la versión integrada

Propuesta: preparar al menos 30 preguntas con fuentes identificadas por personas revisoras: 20 respondibles, 5 fuera de alcance y 5 difíciles (paráfrasis, negaciones, contradicciones o fuente insuficiente). Es un mínimo práctico propuesto para el bootcamp, no una muestra que valide un producto real.

Guardar por caso: ID, pregunta, documento/versiones autorizadas, fragmentos relevantes, elementos esperados de la respuesta, necesidad de abstención, nivel de riesgo y revisión humana. Evitar datos personales. Separar casos de desarrollo para ajustar `k`, chunking, overlap y umbral de casos reservados para evaluación final. Fijar el corpus y registrar modelo de embeddings, métrica del índice, configuración, versión del prompt y commit.

Comparar lexical demo y Chroma sobre la misma referencia; medir Recall@k/MRR, latencia y errores por categoría. El umbral de la demo no se transfiere automáticamente a Chroma. Para filtros, añadir casos donde el resultado más similar pertenece a una categoría/documento excluido.

## Fidelidad del RAG: pendiente

Revisión humana por pregunta, sobre afirmaciones de la respuesta:

| Criterio | Registro sugerido |
|---|---|
| Afirmaciones sustentadas por las fuentes | Sustentadas / afirmaciones verificables |
| Cobertura de puntos esperados | Puntos cubiertos / puntos esperados |
| Citas correctas | Citas que soportan la afirmación / citas revisadas |
| Abstención cuando falta evidencia | Casos correctos / casos que requieren abstención |
| Respuestas peligrosas o inventadas | Conteo, ejemplo y severidad |

No equiparar acuerdo entre modelos con corrección. Registrar denominadores, casos pendientes y ejemplos de fallo. Cuando una pregunta carece de evidencia suficiente, no premiar una respuesta convincente. Una instrucción preventiva inventada obliga a revisar el sistema antes de mostrarlo como válido.

## Criterios de cierre propuestos

- Tests de P5 y tests reales P1/P2 aprobados en el entorno integrado.
- Fuentes visibles y verificables en interfaz.
- Consulta fuera de alcance sin respuesta inventada.
- Revisión de casos de riesgo y errores de mayor severidad.
- Resultados de recuperación y generación separados, con muestra y límites.
- Ningún requisito del briefing marcado como terminado solo por estar documentado.
