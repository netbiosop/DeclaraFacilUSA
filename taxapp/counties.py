"""Lista de condados por estado.

- Incluidos: Maryland (24) e Indiana (92), donde el condado determina el impuesto local.
- Todos los demas: se descargan del archivo oficial del Censo de EE.UU. (national_county2020.txt) y se guardan en
  la carpeta del usuario. Tambien se puede escribir el condado a mano o importar un CSV/TXT con el mismo formato.
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from . import data_loader

CENSUS_URLS = [
    "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
    "https://www2.census.gov/geo/docs/reference/codes/files/national_county.txt",
]


def _cache_file() -> Path:
    return data_loader.user_dir() / "counties_census.json"


@lru_cache(maxsize=1)
def _all() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    try:
        with open(data_loader.data_dir() / "counties_builtin.json", encoding="utf-8") as f:
            out.update(json.load(f)["states"])
    except (OSError, ValueError, KeyError):
        pass
    try:
        cached = json.loads(_cache_file().read_text(encoding="utf-8"))
        for k, v in cached.items():
            if k not in out or len(v) > len(out[k]):
                out[k] = v
    except (OSError, ValueError):
        pass
    return out


def counties_for(code: str) -> List[str]:
    return list(_all().get((code or "").upper(), []))


def has_full_list() -> bool:
    return len(_all()) >= 50


def parse_census(text: str) -> Dict[str, List[str]]:
    """Formato 2020: STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME|CLASSFP|FUNCSTAT
    Formato 2010: STATE,STATEFP,COUNTYFP,COUNTYNAME,CLASSFP"""
    res: Dict[str, set] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        sep = "|" if "|" in line else ","
        parts = [p.strip() for p in line.split(sep)]
        if parts[0].upper() == "STATE" or len(parts) < 4:
            continue
        st = parts[0].upper()
        name = parts[4] if sep == "|" and len(parts) > 4 else parts[3]
        if len(st) == 2 and name:
            res.setdefault(st, set()).add(name)
    return {k: sorted(v) for k, v in res.items()}


def save_lists(lists: Dict[str, List[str]]):
    _cache_file().write_text(json.dumps(lists, indent=1, ensure_ascii=False), encoding="utf-8")
    _all.cache_clear()


def download_from_census(timeout: int = 30) -> int:
    """Descarga la lista oficial de condados. Devuelve el numero de estados cargados."""
    last_err = None
    for url in CENSUS_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DeclaraFacilUSA/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
                raw = r.read()
            text = raw.decode("utf-8", errors="replace")
            lists = parse_census(text)
            if len(lists) >= 50:
                save_lists(lists)
                return len(lists)
        except Exception as e:  # noqa: BLE001 - se informa al usuario
            last_err = e
    raise RuntimeError(f"No se pudo descargar la lista del Censo: {last_err}")


def import_file(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lists = parse_census(text)
    if not lists:
        raise ValueError("El archivo no tiene el formato del Censo (STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME...).")
    merged = dict(_all())
    merged.update(lists)
    save_lists(merged)
    return len(lists)
