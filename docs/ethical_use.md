# Privacidad, uso ético y límites de PRL-IA

## Contexto de uso

PRL-IA está pensado para ayudar a localizar documentación de prevención. Un texto convincente puede ser incorrecto, antiguo o inaplicable al centro. La calidad de una respuesta depende de los documentos y de la fidelidad del modelo. No debe usarse para autorizar una actividad de riesgo ni sustituir la revisión de profesionales y procedimientos del centro. Este documento describe decisiones técnicas y riesgos; no certifica cumplimiento normativo.

## Datos admitidos en la demo

Usar solo el ejemplo sintético incluido o documentación pública autorizada. No cargar reconocimientos médicos, datos de salud, partes nominativos de accidentes, teléfonos, DNI, firmas ni documentos internos confidenciales. Anonimizar también nombres de archivo, texto libre, tablas, pies de página y metadatos. Retirar nombres no garantiza anonimización si el contexto permite identificar a alguien.

La demo procesa y almacena localmente. No llama a un LLM, a un proveedor de embeddings ni a servicios de inferencia externos. La instalación de dependencias sí necesita acceso al repositorio de paquetes. El uso local no implica cifrado ni control de acceso: cualquier persona con acceso al directorio podría leer los datos.

## Riesgos y controles

| Riesgo | Aplicado en P5 | Pendiente/límite |
|---|---|---|
| Pérdida de procedencia | Fuente, ID, página cuando existe, hash y fechas | Procedencia editorial, versión y vigencia del corpus final |
| Contexto sin relevancia | Umbral y contexto vacío explícito | Calibración con embeddings y revisión de falsas coincidencias |
| Uso de índices incompletos | Estados y exclusión de documentos fallidos/en eliminación | Garantías distribuidas en el adaptador Chroma |
| Exposición accidental en Git | Exclusiones de originales e índices | Lo ya versionado no se desversiona por añadir `.gitignore`; revisar `git diff --cached` |
| Lectura o modificación no autorizada | Arranque local en 127.0.0.1 | Autenticación, permisos por documento y aislamiento entre organizaciones |
| Archivos maliciosos | Validación de extensión, cabecera PDF, tamaño y nombre | Antivirus, límites de petición previos, sandbox de parsing y tiempo/memoria |
| Fuga mediante errores | Errores genéricos de adaptadores, sin devolver trazas | Logging seguro, auditoría con acceso restringido |
| Retención innecesaria | Endpoint de eliminación y exclusión de recuperación | Política de retención y borrado de copias de seguridad |
| Prompt injection documental | La recuperación no ejecuta instrucciones del texto | P3 debe separar instrucciones del sistema y documentos no confiables |

El tamaño de 10 MiB se valida al leer el archivo recibido; no protege por sí solo contra peticiones enormes antes de llegar al endpoint ni contra PDF comprimidos que consuman mucha memoria. No desplegar esta demo en una red abierta.

## Si el equipo añade una API comercial

Antes de transmitir contenido, identificar qué texto y metadatos saldrán del entorno, para qué fin, hacia qué proveedor y bajo qué condiciones vigentes. Minimizar el contexto enviado y validar permisos. Para documentación sensible, valorar modelos y embeddings locales o una infraestructura autorizada. No afirmar que un proveedor es adecuado solo por ser gratuito o accesible. Revisar retención, uso de datos y condiciones reales en la integración; este módulo no las ha evaluado para un proveedor específico.

Un filtro `category` o `document_id` introducido por quien consulta no es autorización. Los permisos deben calcularse en el servidor y aplicarse a la búsqueda antes de devolver candidatos. Evitar registrar las preguntas y los fragmentos completos en logs por defecto.

## Calidad, sesgos y supervisión

El corpus puede representar solo algunos trabajos, centros o colectivos. Una ausencia documental no significa ausencia de riesgo. Registrar huecos, fuentes antiguas y contradicciones; evaluar preguntas con sinónimos, negaciones y listas. Conservar quién revisó la fuente y su vigencia en el diseño final. Un score alto mide cercanía según el índice, no validez de una medida preventiva.

La interfaz debe ofrecer las fuentes y reconocer falta de información. Ante fuentes contradictorias o insuficientes, debe permitir derivar la consulta a revisión humana. Las instrucciones incluidas en un documento no pueden cambiar las reglas del asistente ni habilitar herramientas.

## Eliminación y recuperación

`DELETE /api/v1/documents/{id}` retira entradas del índice, original y catálogo. Un fallo mantiene el documento oculto en `deleting` para reintentar. Esto no es borrado seguro de soportes ni elimina copias externas, backups, capturas o contenido ya enviado a un tercero. Los originales de cargas fallidas se conservan para reindexar: eliminarlos explícitamente cuando ya no sean necesarios.

## Casos que debe probar el equipo antes de usar datos reales

- Pregunta fuera del corpus y pregunta peligrosa sin evidencia suficiente.
- Documento con instrucciones para ignorar el sistema o revelar información.
- Dos usuarios con permisos diferentes y una consulta que intenta acceder al documento ajeno.
- Documento obsoleto frente a una versión nueva; contradicciones entre fuentes.
- Carga de archivo malicioso, intento de rutas externas y ausencia de texto extraíble.
- Eliminación y verificación de que ya no aparece en recuperación.

Los tests de P5 cubren controles técnicos locales, no una auditoría de seguridad ni validación profesional de PRL.
