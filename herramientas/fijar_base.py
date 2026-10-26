"""Marca la version actual como 'programa base' (__base__ = __version__) antes de publicar un instalador completo."""
import re
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "taxapp" / "__init__.py"
s = p.read_text(encoding="utf-8")
ver = re.search(r'__version__\s*=\s*"([^"]+)"', s).group(1)
s = re.sub(r'__base__\s*=\s*"[^"]*"', f'__base__ = "{ver}"', s)
p.write_bytes(s.encode("utf-8"))
print(f"Base = {ver}")
