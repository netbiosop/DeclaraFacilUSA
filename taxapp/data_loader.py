"""Carga de los archivos de datos (JSON) con tasas y reglas por ano.

Los JSON estan en la carpeta `data/` junto a la aplicacion. El usuario puede editarlos para actualizar tasas.
Las listas de condados descargadas del Censo se guardan en la carpeta de usuario.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

SUPPORTED_YEARS = (2025, 2026)


def app_dir() -> Path:
    root = os.environ.get("DECLARAFACIL_CODE_ROOT")
    if root and Path(root).is_dir():
        return Path(root)          # codigo actualizado desde GitHub (ver main.py)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # ejecutable PyInstaller
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return app_dir() / "data"


def user_dir() -> Path:
    base = Path(os.environ.get("USERPROFILE") or Path.home())
    docs = base / "Documents"
    d = (docs if docs.exists() else base) / "DeclaraFacilUSA"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path.home() / ".declarafacilusa"
        d.mkdir(parents=True, exist_ok=True)
    return d


def _load(name: str) -> dict:
    with open(data_dir() / name, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def federal(year: int) -> dict:
    return _load(f"federal_{year}.json")


@lru_cache(maxsize=None)
def states(year: int) -> dict:
    return _load(f"states_{year}.json")["states"]


@lru_cache(maxsize=None)
def local(year: int) -> dict:
    return _load(f"local_{year}.json")


@lru_cache(maxsize=None)
def states_info() -> dict:
    return _load("states_info.json")


def state_codes_sorted() -> list:
    info = states_info()
    return sorted(info, key=lambda c: info[c]["name"])


def state_label(code: str) -> str:
    info = states_info().get(code)
    return f"{info['name']} ({code})" if info else code


def code_from_label(label: str) -> str:
    if not label:
        return ""
    label = label.strip()
    if label.endswith(")") and "(" in label:
        return label[label.rfind("(") + 1:-1].strip().upper()
    up = label.upper()
    if up in states_info():
        return up
    for c, i in states_info().items():
        if i["name"].lower() == label.lower():
            return c
    return ""


def reload_all():
    for fn in (federal, states, local, states_info):
        fn.cache_clear()
