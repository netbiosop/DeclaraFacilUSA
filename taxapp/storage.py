"""Guardar y abrir declaraciones (.dfusa = JSON) y lista de archivos recientes."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from . import data_loader
from .models import TaxReturn

EXT = ".dfusa"
MAGIC = "DeclaraFacilUSA"


def dumps(ret: TaxReturn) -> str:
    payload = {"format": MAGIC, "version": 1, "saved": datetime.now().isoformat(timespec="seconds"),
               "return": ret.to_dict()}
    return json.dumps(payload, indent=2, ensure_ascii=False)


def loads(text: str) -> TaxReturn:
    d = json.loads(text)
    if isinstance(d, dict) and d.get("format") == MAGIC:
        d = d["return"]
    return TaxReturn.from_dict(d)


def save(ret: TaxReturn, path) -> Path:
    p = Path(path)
    if p.suffix.lower() != EXT:
        p = p.with_suffix(EXT)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(dumps(ret), encoding="utf-8")
    tmp.replace(p)
    add_recent(p)
    return p


def load(path) -> TaxReturn:
    p = Path(path)
    ret = loads(p.read_text(encoding="utf-8"))
    add_recent(p)
    return ret


# Usuario con sesion iniciada (lo asigna la App); cada usuario tiene su carpeta y su lista de recientes.
current_user = ""


def returns_dir() -> Path:
    d = data_loader.user_dir() / "Declaraciones"
    if current_user:
        d = d / current_user
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recent_file() -> Path:
    suffix = f"_{current_user}" if current_user else ""
    return data_loader.user_dir() / f"recientes{suffix}.json"


def recent() -> List[str]:
    try:
        items = json.loads(_recent_file().read_text(encoding="utf-8"))
        return [x for x in items if Path(x).exists()][:8]
    except (OSError, ValueError):
        return []


def add_recent(p: Path):
    items = [str(Path(p).resolve())] + [x for x in recent() if x != str(Path(p).resolve())]
    try:
        _recent_file().write_text(json.dumps(items[:8], indent=1), encoding="utf-8")
    except OSError:
        pass


def default_filename(ret: TaxReturn) -> str:
    name = (ret.taxpayer.last_name or "declaracion").strip().replace(" ", "_")
    return f"{name}_{ret.tax_year}{EXT}"
