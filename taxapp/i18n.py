"""Idioma de la aplicacion / Application language (Espanol / English).

The Spanish text is the translation key. `_()` returns the English text from the catalogs when the language is
English; any missing key falls back to the Spanish original. `tr()` translates and then applies str.format().

    _("Ingresos")                          -> "Income"
    tr("Edad: {n} anos", n=40)             -> "Age: 40 years"
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

LANGS = {"es": "Español", "en": "English"}
_lang = "es"
_catalog: dict = {}


def _load_catalog():
    global _catalog
    if not _catalog:
        from .lang_en import EN
        from .lang_en_data import EN_DATA
        _catalog = {**EN_DATA, **EN}
    return _catalog


def _config_file() -> Path:
    from .data_loader import user_dir
    return user_dir() / "config.json"


def system_language() -> str:
    """'es' si Windows/el sistema esta en espanol; si no, 'en'."""
    import locale
    try:
        if sys.platform.startswith("win"):
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "es" if (lang_id & 0x3FF) == 0x0A else "en"
        loc = (locale.getlocale()[0] or os.environ.get("LANG", "")).lower()
        return "es" if loc.startswith("es") else "en"
    except (AttributeError, OSError, ValueError) as e:
        logger.warning("No se pudo detectar el idioma del sistema, se usa español: %s", e)
        return "es"


def load_saved_language() -> str:
    """Idioma guardado; la primera vez se usa el idioma del sistema."""
    global _lang
    from .data_loader import read_json
    saved = read_json(_config_file(), {}).get("language")
    _lang = saved if saved in LANGS else system_language()   # la primera vez, el idioma del sistema
    return _lang


def set_language(lang: str, save: bool = True):
    global _lang
    if lang not in LANGS:
        return
    _lang = lang
    if save:
        from .data_loader import read_json
        p = _config_file()
        cfg = read_json(p, {})
        cfg["language"] = lang
        try:
            p.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        except OSError as e:
            logger.warning("No se pudo guardar el idioma elegido: %s", e)


def get_language() -> str:
    return _lang


def is_en() -> bool:
    return _lang == "en"


def N_(text: str) -> str:
    """Marca un texto para traducir mas tarde (se traduce al mostrarlo con _())."""
    return text


def _(text: str) -> str:
    if _lang == "es" or not text:
        return text
    return _load_catalog().get(text, text)


def tr(text: str, **kw) -> str:
    s = _(text)
    try:
        return s.format(**kw)
    except (KeyError, IndexError, ValueError):
        return text.format(**kw)


def reverse(display: str, keys) -> str:
    """Return the key (Spanish original) whose translation matches the displayed text."""
    for k in keys:
        if _(k) == display or k == display:
            return k
    return display
