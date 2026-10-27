"""Catálogo de formularios oficiales por año / Official forms catalog per year.

Los PDF en blanco del IRS y el mapa de campos están en data/formularios/<año>/ y data/formularios/<año>.json
(generado y validado con herramientas/mapear_formularios.py).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from .. import data_loader
from ..i18n import is_en

# Orden en que se arma el paquete: 1040 primero y luego por número de secuencia de adjunto (esquina superior derecha).
ORDER = ["1040", "1040sr", "s1", "s1a", "s2", "s3", "sa", "sb", "sc", "sd", "8949", "sse", "2441", "6251", "sei",
         "s8812", "8863", "8889", "8880", "8995", "8959", "8960"]
SHORT = {"1040": "1040", "1040sr": "1040-SR", "s1": "Schedule 1", "s1a": "Schedule 1-A", "s2": "Schedule 2",
         "s3": "Schedule 3", "sa": "Schedule A", "sb": "Schedule B", "sc": "Schedule C", "sd": "Schedule D",
         "8949": "Form 8949", "sse": "Schedule SE", "2441": "Form 2441", "6251": "Form 6251", "sei": "Schedule EIC",
         "s8812": "Schedule 8812", "8863": "Form 8863", "8889": "Form 8889", "8880": "Form 8880", "8995": "Form 8995",
         "8959": "Form 8959", "8960": "Form 8960", "1040v": "Form 1040-V"}
FILE_NAMES = {"1040": "1040", "1040sr": "1040-SR", "s1": "Anexo_1", "s1a": "Anexo_1-A", "s2": "Anexo_2",
              "s3": "Anexo_3", "sa": "Anexo_A", "sb": "Anexo_B", "sc": "Anexo_C", "sd": "Anexo_D", "8949": "8949",
              "sse": "Anexo_SE", "2441": "2441", "6251": "6251", "sei": "Anexo_EIC", "s8812": "Anexo_8812",
              "8863": "8863", "8889": "8889", "8880": "8880", "8995": "8995", "8959": "8959", "8960": "8960",
              "1040v": "1040-V"}
FILE_NAMES_EN = {k: v.replace("Anexo_", "Schedule_") for k, v in FILE_NAMES.items()}
SHORT_ES = {k: v.replace("Schedule ", "Anexo ").replace("Form ", "Formulario ") for k, v in SHORT.items()}


def short(fid: str) -> str:
    """Nombre corto del formulario en el idioma de la aplicación (Schedule C / Anexo C)."""
    return (SHORT if is_en() else SHORT_ES).get(fid, fid)


def file_name(fid: str) -> str:
    return (FILE_NAMES_EN if is_en() else FILE_NAMES).get(fid, fid)


def forms_dir(year: int) -> Path:
    return data_loader.data_dir() / "formularios" / str(year)


@lru_cache(maxsize=None)
def _load(year: int) -> Optional[dict]:
    p = data_loader.data_dir() / "formularios" / f"{year}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def available(year: int) -> bool:
    """True si hay formularios oficiales (mapa + PDF) para ese año."""
    data = _load(year)
    if not data:
        return False
    d = forms_dir(year)
    return all((d / f["file"]).exists() for f in data["forms"].values())


def forms(year: int) -> Dict[str, dict]:
    data = _load(year)
    return data["forms"] if data else {}


def title(year: int, fid: str) -> str:
    f = forms(year).get(fid)
    if not f:
        return SHORT.get(fid, fid)
    return f["title"][1] if is_en() else f["title"][0]


def has_spanish(year: int, fid: str) -> bool:
    """True si el IRS publica una versión oficial en español de este formulario y está incluida."""
    f = forms(year).get(fid) or {}
    return "es" in f and (forms_dir(year) / f["es"]["file"]).exists()


def spanish_available(year: int) -> bool:
    return any(has_spanish(year, fid) for fid in forms(year))


def variant(year: int, fid: str, lang: str = "en") -> dict:
    """Edición del formulario a usar: {'file', 'fields', 'pages', 'lang'}. Si no hay versión en el idioma pedido,
    se usa la oficial en inglés."""
    f = forms(year)[fid]
    if lang == "es" and has_spanish(year, fid):
        v = f["es"]
        return {"file": v["file"], "fields": v["fields"], "pages": v.get("pages"), "lang": "es"}
    return {"file": f["file"], "fields": f["fields"], "pages": f.get("pages"), "lang": "en"}


def pdf_path(year: int, fid: str, lang: str = "en") -> Path:
    return forms_dir(year) / variant(year, fid, lang)["file"]


def clear_cache():
    _load.cache_clear()
