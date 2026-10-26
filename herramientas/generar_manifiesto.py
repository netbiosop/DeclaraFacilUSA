"""Genera actualizacion.json (manifiesto de la actualizacion por archivos) en la raiz del proyecto.

Uso: python herramientas/generar_manifiesto.py
Lo ejecuta publicar_actualizacion.bat antes de subir el codigo a GitHub.
"""
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = ("taxapp", "data", "docs", "assets")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIX = {".pyc", ".pyo", ".tmp"}


def build(root: Path = ROOT) -> dict:
    init = (root / "taxapp" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1)
    base = (re.search(r'__base__\s*=\s*"([^"]+)"', init) or re.search(r'__version__\s*=\s*"([^"]+)"', init)).group(1)
    notes_file = root / "instalador" / "NOTAS_VERSION.md"
    notes = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""
    files = {}
    for d in CODE_DIRS:
        for p in sorted((root / d).rglob("*")):
            if p.is_file() and not (SKIP_DIRS & set(p.parts)) and p.suffix.lower() not in SKIP_SUFFIX:
                data = p.read_bytes()
                files[p.relative_to(root).as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    return {"app": "DeclaraFacilUSA", "version": version, "base": base, "published": date.today().isoformat(),
            "notes": notes, "files": files}


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    out = root / "actualizacion.json"
    prev = None
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8")).get("version")
        except ValueError:
            prev = None
    man = build(root)
    if "--check-new" in sys.argv and prev == man["version"]:
        print(f"ERROR: la version {prev} ya fue publicada. Suba el numero en taxapp\\__init__.py.")
        sys.exit(2)
    out.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Manifiesto: version {man['version']} (base {man['base']}), {len(man['files'])} archivos")


if __name__ == "__main__":
    main()
