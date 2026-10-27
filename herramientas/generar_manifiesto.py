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


def published_version(root: Path):
    """Version publicada en GitHub (actualizacion.json de la rama main), o None si no se puede consultar."""
    import urllib.request
    try:
        repo = json.loads((root / "data" / "actualizaciones.json").read_text(encoding="utf-8")).get("repo", "")
    except (OSError, ValueError):
        repo = ""
    if not repo:
        return None
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/contents/actualizacion.json?ref=main",
                                 headers={"Accept": "application/vnd.github.raw", "User-Agent": "DeclaraFacilUSA"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")).get("version")
    except Exception:  # noqa: BLE001 - sin conexion: no se bloquea la publicacion
        return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(args[0]).resolve() if args else ROOT
    out = root / "actualizacion.json"
    man = build(root)
    if "--check-new" in sys.argv:
        pub = published_version(root)
        if pub == man["version"]:
            print(f"ERROR: la version {pub} ya esta publicada en GitHub. Suba el numero en taxapp\\__init__.py "
                  f"(por ejemplo {_next(pub)}) y anote las novedades en instalador\\NOTAS_VERSION.md.")
            sys.exit(2)
    out.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Manifiesto: version {man['version']} (base {man['base']}), {len(man['files'])} archivos")


def _next(v: str) -> str:
    parts = (v or "0").split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        return v
    return ".".join(parts)


if __name__ == "__main__":
    main()
