# Instalar la entrega y subirla a GitHub desde Ubuntu/WSL

## Qué se ha hecho y qué falta en tu ordenador

Los archivos se han desarrollado y probado en un entorno independiente sobre una copia de `dev` del repositorio `https://github.com/MajoRodri/PRL-IA.git`, commit `84825054735f0843c46bec058456415781d29c95`. No se ha escrito en tu disco C: ni se ha enviado un commit a GitHub.

Tu destino indicado es:

```text
C:\Users\EVO\Desktop\BOOTCAMP\MODULO V\Proyecto PRL-IA\PRL-IA
```

En Ubuntu/WSL corresponde a:

```text
/mnt/c/Users/EVO/Desktop/BOOTCAMP/MODULO V/Proyecto PRL-IA/PRL-IA
```

El ZIP contiene `archivos/` con los archivos completos y `cambios.patch` para aplicarlos de forma comprobable. Usa el parche para preservar la base Git y detectar conflictos. No copies `archivos/` por encima de una carpeta con trabajo del equipo sin revisar diferencias.

## 1. Descargar y extraer

Guarda `PRL-IA-persona5.zip` en `C:\Users\EVO\Downloads`. En Ubuntu:

```bash
python3 -m zipfile -e "/mnt/c/Users/EVO/Downloads/PRL-IA-persona5.zip" "/mnt/c/Users/EVO/Downloads"
```

Quedará la carpeta `/mnt/c/Users/EVO/Downloads/PRL-IA-persona5`. Si el navegador lo descargó en otra ubicación, utiliza esa ruta.

## 2. Entrar en el repositorio

Si **ya tienes el repositorio clonado** en la ruta indicada:

```bash
cd "/mnt/c/Users/EVO/Desktop/BOOTCAMP/MODULO V/Proyecto PRL-IA/PRL-IA"
git rev-parse --show-toplevel
git remote -v
git status --short
```

Comprueba que la raíz sea esa carpeta y que `origin` sea `https://github.com/MajoRodri/PRL-IA.git` (o su equivalente SSH). Si `git status --short` muestra cambios, consérvalos en su rama/commit o revisa conmigo la salida antes de continuar. No uses `reset --hard`, ni borres la carpeta para limpiarla.

Si **todavía no lo has clonado** y la carpeta final `PRL-IA` no existe:

```bash
mkdir -p "/mnt/c/Users/EVO/Desktop/BOOTCAMP/MODULO V/Proyecto PRL-IA"
cd "/mnt/c/Users/EVO/Desktop/BOOTCAMP/MODULO V/Proyecto PRL-IA"
git clone https://github.com/MajoRodri/PRL-IA.git PRL-IA
cd PRL-IA
```

Si la carpeta existe pero no es un repositorio, no ejecutes el clone sobre ella ni inicialices otro repositorio a ciegas: conserva su contenido y revisa primero qué archivos tienes.

## 3. Actualizar la base y crear tu rama

La rama `dev` existe en el remoto revisado y contiene la estructura; `main` todavía no la contiene en esa revisión. Proponemos PR hacia `dev`, sujeto a las normas que acuerde el equipo. No se han verificado reglas de protección de GitHub.

Con el árbol de trabajo limpio, ejecuta línea por línea:

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c feature/retrieval-documents
```

Si `git switch dev` indica que no existe localmente y no la crea automáticamente:

```bash
git switch --track origin/dev
```

Luego continúa con `git pull --ff-only origin dev` y la creación de tu rama. Si la rama `feature/retrieval-documents` ya existe, revisa su contenido en vez de borrarla. Si falla cualquier paso, no continúes aplicando cambios a una rama distinta por accidente.

## 4. Aplicar tu entrega

```bash
git apply --check "/mnt/c/Users/EVO/Downloads/PRL-IA-persona5/cambios.patch"
```

**Si no aparece ningún error**, aplica:

```bash
git apply "/mnt/c/Users/EVO/Downloads/PRL-IA-persona5/cambios.patch"
git status --short
git diff --stat
```

El chequeo no cambia archivos. Si falla, puede que alguien haya modificado el README o añadido algún archivo desde la base revisada. No fuerces el parche ni sobrescribas archivos: comparte la salida para adaptar el cambio a la versión actual. Los archivos completos están en `archivos/` para comparar.

La entrega añade módulos propios y documentación, desarrolla el README inicial y amplía las exclusiones de datos privados en `.gitignore`. No modifica `src/api.py`, `src/ingestion.py`, `src/chunking.py`, `src/vector_store.py`, `src/rag_chain.py`, `frontend/`, `.env.example` ni `requirements.txt`.

## 5. Crear entorno y comprobar

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-persona5-lock.txt
python -m pytest tests/test_retrieval.py tests/test_documents_api.py -q
python -m scripts.evaluate_retrieval
python -m uvicorn src.api_documents:create_app --factory --host 127.0.0.1 --port 8005
```

Resultado esperado de tests: 49 aprobados con las versiones proporcionadas. Abre <http://127.0.0.1:8005/docs> para la demo. El aviso de `TestClient` está explicado en `docs/evaluation.md`. Detén el servidor con `Ctrl+C` antes de continuar en esa terminal. Si el puerto está ocupado, usa `--port 8006` y abre ese mismo puerto.

Si ya existe `.venv` con dependencias de otros compañeros, acuerda antes las versiones para no romper su entorno; puedes probar esta entrega en un entorno aislado fuera de la carpeta del repositorio. El bloqueo de P5 es evidencia de un entorno probado, no impone las versiones del equipo completo.

## 6. Revisar y hacer commit

Selecciona solo los archivos de esta entrega (no se usa `git add .`):

```bash
git add .gitignore README.md requirements-persona5.txt requirements-persona5-lock.txt \
  src/retrieval.py src/document_service.py src/api_documents.py \
  tests/test_retrieval.py tests/test_documents_api.py tests/fixtures_retrieval.json \
  scripts/evaluate_retrieval.py data/examples/prevencion_demo.txt \
  docs/evaluation.md docs/ethical_use.md docs/integration.md docs/guia_maria.md docs/github_wsl.md
git diff --cached --stat
git diff --cached --check
git diff --cached
```

Revisa que no haya originales reales, claves, datos personales ni modificaciones ajenas. Pulsa `q` para salir del visor de `git diff`. Después:

```bash
git commit -m "feat: add document management and retrieval module for persona 5"
git push -u origin feature/retrieval-documents
```

No uses `--force`. Si Git solicita autenticación, utiliza el acceso autorizado de GitHub en tu equipo, sin pegar tokens en el chat ni añadirlos a archivos. Si rechaza el push por permisos, necesitarás acceso de colaboración al repositorio o el flujo de fork que acuerde el equipo.

## 7. Abrir el Pull Request

En <https://github.com/MajoRodri/PRL-IA>, pulsa «Compare & pull request» tras el push. Verifica:

- Base: `dev`.
- Compare: `feature/retrieval-documents`.
- Título: `feat: recuperación y gestión documental de persona 5`.

Descripción sugerida:

```text
Problema
Necesitamos desarrollar y probar la gestión documental y la recuperación sin esperar a los módulos de ingesta, Chroma y RAG.

Cambios
- Servicio documental con catálogo SQLite, carga PDF/TXT, reindexación y eliminación.
- Recuperación con metadatos, umbral, deduplicación y trazabilidad.
- API independiente y router reutilizable para la API general.
- Contratos de integración con P1/P2 y baseline léxico explícitamente identificado.
- Tests, evaluación sintética y documentación de privacidad, ejecución e integración.

Validación
- 49 tests aprobados en el entorno de preparación con Python 3.12.
- Añadir aquí el resultado de ejecutar los tests en mi WSL.
- Evaluación sintética reproducible; no mide la calidad final del RAG.

Pendiente
Integrar los módulos reales P1/P2, conectar P3/P4 y evaluar embeddings y respuestas con fuentes revisadas. Prototipo local sin autenticación.
```

Solicita revisión a un compañero. No marques todo el proyecto como terminado ni hagas merge automático: el equipo debe revisar especialmente los contratos, el README y las dependencias. El paquete prepara tu aportación; la revisión y el push real quedan en tus manos.
