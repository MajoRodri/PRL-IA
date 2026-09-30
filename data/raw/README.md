# Corpus local

## Posición en el flujo

Esta carpeta contiene las entradas originales del pipeline: los PDF, TXT o Markdown que posteriormente procesa `src/ingestion.py`. Se encuentra después del manifiesto y del descargador, y antes de la limpieza, el chunking y la generación de embeddings.

Los documentos oficiales no se versionan en Git por su tamaño. La selección y sus URL verificadas están en `data/sources.json`, lo que permite reconstruir el corpus sin guardar los archivos pesados en el repositorio.

Para descargar las nueve fuentes en esta carpeta:

```bash
python scripts/download_corpus.py
```

El descargador no sobrescribe archivos existentes salvo que se use `--force` y comprueba que cada respuesta empiece por la firma `%PDF`.
