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


def pdf_path(year: int, fid: str) -> Path:
    return forms_dir(year) / forms(year)[fid]["file"]


def clear_cache():
    _load.cache_clear()
