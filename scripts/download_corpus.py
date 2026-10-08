"""Descarga y valida las fuentes oficiales que componen el corpus de PRL.

Entrada: las URL y nombres de archivo declarados en ``data/sources.json``.
Salida: PDF verificados mediante su firma binaria y guardados en ``data/raw``;
los archivos descargados son locales y están excluidos de Git.

Posición en el flujo: es el punto de entrada del corpus. Se ejecuta antes de
``src.ingestion``, que extrae y limpia el contenido de los documentos.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "sources.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw"


def download(url: str, destination: Path, *, force: bool = False) -> str:
    """Descarga un PDF de forma segura sin sobrescribirlo salvo indicación expresa."""

    if destination.exists() and not force:
        return "omitido (ya existe)"

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PRL-Assistant-MVP/1.0 (educational project)"},
    )
    temporary_path: Path | None = None
    try:
        # Se escribe primero en un temporal para no dejar descargas incompletas.
        with urllib.request.urlopen(request, timeout=120) as response:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                while block := response.read(1024 * 1024):
                    temporary.write(block)

        # La firma inicial evita guardar como PDF una página de error HTML.
        if not temporary_path.read_bytes()[:5] == b"%PDF-":
            raise ValueError("la respuesta no contiene un PDF valido")
        temporary_path.replace(destination)
        return f"descargado ({destination.stat().st_size / 1024 / 1024:.1f} MiB)"
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    """Procesa el manifiesto y devuelve un código distinto de cero si hay fallos."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    failures = 0
    for document in manifest["documents"]:
        destination = args.output / document["filename"]
        try:
            result = download(document["download_url"], destination, force=args.force)
            print(f"[{document['id']}] {result}")
        except Exception as exc:
            failures += 1
            print(f"[{document['id']}] ERROR: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
