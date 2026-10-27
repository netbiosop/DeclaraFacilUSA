"""Temas visuales / Visual themes: A (verde moderno), B (oscuro premium), C (guiado), color principal, tipo y tamano
de letra. Los colores se aplican modificando el diccionario COLORS de widgets.py (todas las pantallas lo leen) y los
estilos ttk; luego la App reconstruye la interfaz.
"""
from __future__ import annotations

import logging
import re
import sys
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import ttk

from .. import data_loader
from ..i18n import N_
from . import widgets
from . import layout

logger = logging.getLogger(__name__)

THEMES = {
    "A": {"name": N_("A · Verde moderno"), "desc": N_("Claro, con tarjetas"), "dark": False, "accent": "#0F7B5C",
          "fonts": ["Plus Jakarta Sans", "Segoe UI"], "meter": "header", "ai_docked": False,
          "bg": "#F3F6F5", "card": "#FFFFFF", "surface": "#EEF3F1", "text": "#13221C", "muted": "#5B6670",
          "border": "#DDE6E2", "header": "#FFFFFF", "header_fg": "#13221C", "header_muted": "#5B6670",
          "sidebar": "#FFFFFF", "sidebar_fg": "#2A3832", "sidebar_muted": "#5B6670", "input": "#FBFDFC",
          "input_border": "#D5DFDB", "refund": "#127A4A", "refund_bg": "#E3F4EC", "owe": "#B3261E",
          "owe_bg": "#FDECEA", "warn": "#9A5B00", "info": "#1F5FA8", "chip": "#13221C", "chip_fg": "#FFFFFF"},
    "B": {"name": N_("B · Oscuro premium"), "desc": N_("Descansa la vista de noche"), "dark": True, "accent": "#3DDC97",
          "fonts": ["Manrope", "Bahnschrift", "Segoe UI"], "meter": "panel", "ai_docked": False,
          "bg": "#0B111D", "card": "#111A2B", "surface": "#17223A", "text": "#E8ECF4", "muted": "#AEB8CC",
          "border": "#22304A", "header": "#111A2B", "header_fg": "#E8ECF4", "header_muted": "#8F9AB2",
          "sidebar": "#111A2B", "sidebar_fg": "#C9D1E0", "sidebar_muted": "#8F9AB2", "input": "#0D1524",
          "input_border": "#2C3A55", "refund": "#3DDC97", "refund_bg": "#123526", "owe": "#FF8A7A",
          "owe_bg": "#3A1E22", "warn": "#FFB547", "info": "#7DA7FF", "chip": "#E8ECF4", "chip_fg": "#0B111D"},
    "C": {"name": N_("C · Guiado"), "desc": N_("Paso a paso, IA al lado"), "dark": False, "accent": "#2457F5",
          "fonts": ["Nunito Sans", "Segoe UI"], "meter": "header", "ai_docked": True,
          "bg": "#F4F7FF", "card": "#FFFFFF", "surface": "#EEF2FB", "text": "#121A33", "muted": "#46506B",
          "border": "#E1E6F3", "header": "#FFFFFF", "header_fg": "#121A33", "header_muted": "#5F6987",
          "sidebar": "#FFFFFF", "sidebar_fg": "#26304D", "sidebar_muted": "#5F6987", "input": "#FFFFFF",
          "input_border": "#D9DFEE", "refund": "#127A4A", "refund_bg": "#E9F8F0", "owe": "#B3261E",
          "owe_bg": "#FDECEA", "warn": "#9A5B00", "info": "#1E47D1", "chip": "#121A33", "chip_fg": "#FFFFFF"},
}
ACCENTS = [(N_("Verde"), "#0F7B5C"), (N_("Azul"), "#2457F5"), (N_("Índigo"), "#4F46E5"), (N_("Violeta"), "#7A4FC4"),
           (N_("Rosa"), "#BE185D"), (N_("Naranja"), "#C2410C"), (N_("Grafito"), "#334155"), (N_("Menta"), "#3DDC97")]
SIZES = {"small": (N_("Pequeño"), 0.92), "normal": (N_("Normal"), 1.0), "large": (N_("Grande"), 1.12),
         "xlarge": (N_("Muy grande"), 1.25)}
FONT_CHOICES = ["Segoe UI", "Bahnschrift", "Calibri", "Verdana", "Trebuchet MS", "Georgia",
                "Plus Jakarta Sans", "Manrope", "Nunito Sans"]
GOOGLE_FONTS = {"Plus Jakarta Sans": "Plus+Jakarta+Sans", "Manrope": "Manrope", "Nunito Sans": "Nunito+Sans"}

# Iconos de "Segoe MDL2 Assets" (Windows 10/11) con alternativa de texto en otros sistemas.
ICON_FONT = "Segoe MDL2 Assets"
ICONS = {
    "add": ("", "+"), "open": ("", "▤"), "folder": ("", "▤"), "next": ("", "→"),
    "back": ("", "←"), "home": ("", "⌂"), "map": ("", "◉"), "calc": ("", "▦"),
    "book": ("", "▥"), "ai": ("", "✦"), "download": ("", "↓"), "globe": ("", "◍"),
    "settings": ("", "⚙"), "user": ("", "●"), "users": ("", "●"), "calendar": ("", "▣"),
    "check": ("", "✓"), "lock": ("", "■"), "logout": ("", "⏻"), "search": ("", "⌕"),
    "save": ("", "▾"), "doc": ("", "▯"), "info": ("", "i"), "help": ("", "?"),
    "shield": ("", "◆"), "history": ("", "↺"), "palette": ("", "◐"), "send": ("", "➤"),
    "refresh": ("", "↻"), "close": ("", "✕"), "more": ("", "⋯"), "money": ("", "$"),
    "exit": ("", "✕"), "edit": ("", "✎"), "table": ("", "▦"),
}

_state = {"families": None, "theme": "A"}


# ---------------------------------------------------------------------------- utilidades de color
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(color: str, bg: str, ratio: float = 4.5) -> str:
    """Oscurece (fondo claro) o aclara (fondo oscuro) el color hasta alcanzar el contraste pedido."""
    target = "#000000" if luminance(bg) > 0.4 else "#FFFFFF"
    c = color
    for i in range(1, 21):
        if contrast(c, bg) >= ratio:
            return c
        c = mix(color, target, i * 0.05)
    return c


def valid_hex(h: str) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", h or ""))


def palette(theme: str = "A", accent: str = "") -> dict:
    t = dict(THEMES.get(theme, THEMES["A"]))
    acc = accent if valid_hex(accent) else t["accent"]
    dark = t["dark"]
    on_accent = "#FFFFFF" if contrast("#FFFFFF", acc) >= contrast("#0B111D", acc) else "#0B111D"
    tint = mix(t["card"], acc, 0.20 if dark else 0.12)
    p = {k: v for k, v in t.items() if isinstance(v, str) and k not in ("name", "desc")}
    p.update({
        "accent": acc,
        "accent_dark": mix(acc, "#FFFFFF" if dark else "#000000", 0.18),
        "on_accent": on_accent,
        "tint": tint,
        "tint_fg": ensure_contrast(acc, tint, 4.5),
        "primary": ensure_contrast(acc, t["card"], 4.5),
        "sidebar_sel": tint,
        "sidebar_sel_fg": ensure_contrast(acc, tint, 4.5),
        "hover": mix(t["card"], t["text"], 0.06),
        "tooltip": "#FFFDE7" if not dark else "#22304A",
        "tooltip_fg": "#333333" if not dark else "#E8ECF4",
        "disabled": mix(t["card"], t["muted"], 0.35),
        "dark": "1" if dark else "",
    })
    # nombres antiguos usados por pantallas existentes
    p["primary_dark"] = p["accent_dark"]
    p["accent_light"] = tint
    return p


# ---------------------------------------------------------------------------- fuentes
def families(root=None) -> set:
    if _state["families"] is None:
        try:
            from tkinter import font as tkfont
            _state["families"] = set(tkfont.families(root))
        except Exception:  # noqa: BLE001
            _state["families"] = set()
    return _state["families"]


def reset_font_cache():
    _state["families"] = None


def available_fonts(root=None):
    fam = families(root)
    return [f for f in FONT_CHOICES if f in fam] or ["Segoe UI"]


def resolve_font(theme: str, chosen: str, root=None) -> str:
    fam = families(root)
    if chosen and (chosen in fam or not fam):
        return chosen
    for f in THEMES.get(theme, THEMES["A"])["fonts"]:
        if f in fam:
            return f
    return "Segoe UI"


def fonts_dir() -> Path:
    d = data_loader.user_dir() / "fuentes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def register_fonts():
    """Registra (solo para este programa) las fuentes descargadas. Solo Windows."""
    if not sys.platform.startswith("win"):
        return 0
    n = 0
    try:
        import ctypes
        for f in fonts_dir().glob("*.ttf"):
            if ctypes.windll.gdi32.AddFontResourceExW(str(f), 0x10, 0):
                n += 1
    except (OSError, AttributeError) as e:
        logger.warning("No se pudieron registrar las fuentes incluidas: %s", e)
    reset_font_cache()
    return n


def download_fonts(timeout=30) -> int:
    """Descarga Plus Jakarta Sans, Manrope y Nunito Sans (Google Fonts, licencia OFL) en formato TTF."""
    n = 0
    for family, q in GOOGLE_FONTS.items():
        url = f"https://fonts.googleapis.com/css2?family={q}:wght@400;700&display=swap"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})   # agente simple -> enlaces .ttf
        with urllib.request.urlopen(req, timeout=timeout) as r:
            css = r.read().decode("utf-8", "replace")
        for weight, link in re.findall(r"font-weight:\s*(\d+);[^}]*?url\((https://[^)]+?\.ttf)\)", css, re.S):
            dest = fonts_dir() / f"{family.replace(' ', '')}-{weight}.ttf"
            with urllib.request.urlopen(link, timeout=timeout) as r:
                dest.write_bytes(r.read())
            n += 1
    if not n:
        raise OSError("No TTF files found")
    register_fonts()
    return n


# ---------------------------------------------------------------------------- iconos
def icon(name: str) -> str:
    glyph, alt = ICONS.get(name, ("", "•"))
    return glyph if ICON_FONT in families() else alt


def icon_font(size=12):
    return (ICON_FONT, round(size * widgets.STYLE["scale"])) if ICON_FONT in families() else widgets.font(size, "bold")


# ---------------------------------------------------------------------------- aplicar
def current() -> str:
    return _state["theme"]


def apply(root, prefs: dict):
    """Aplica tema, color, fuente y tamano: actualiza COLORS, STYLE y los estilos ttk (sin reconstruir)."""
    theme = prefs.get("theme") if prefs.get("theme") in THEMES else "A"
    _state["theme"] = theme
    pal = palette(theme, prefs.get("accent", ""))
    widgets.COLORS.clear()
    widgets.COLORS.update(pal)
    widgets.STYLE["family"] = resolve_font(theme, prefs.get("font", ""), root)
    widgets.STYLE["scale"] = SIZES.get(prefs.get("size"), SIZES["normal"])[1]
    style_ttk(root)


def style_ttk(root):
    c = widgets.COLORS
    f = widgets.font
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    root.configure(bg=c["bg"])
    for opt, val in (("*Text.background", c["card"]), ("*Text.foreground", c["text"]),
                     ("*Text.insertBackground", c["text"]), ("*Text.selectBackground", c["tint"]),
                     ("*Text.selectForeground", c["text"]), ("*Toplevel.background", c["bg"]),
                     ("*Listbox.background", c["card"]), ("*Listbox.foreground", c["text"]),
                     ("*TCombobox*Listbox.background", c["card"]), ("*TCombobox*Listbox.foreground", c["text"]),
                     ("*TCombobox*Listbox.selectBackground", c["tint"]),
                     ("*TCombobox*Listbox.selectForeground", c["tint_fg"]),
                     ("*Menu.background", c["card"]), ("*Menu.foreground", c["text"]),
                     ("*Menu.activeBackground", c["tint"]), ("*Menu.activeForeground", c["tint_fg"])):
        root.option_add(opt, val)
    st.configure(".", font=f(10), background=c["bg"], foreground=c["text"], bordercolor=c["border"],
                 lightcolor=c["border"], darkcolor=c["border"], troughcolor=c["surface"], focuscolor=c["accent"],
                 selectbackground=c["tint"], selectforeground=c["tint_fg"], insertcolor=c["text"])
    st.configure("TFrame", background=c["bg"])
    st.configure("Card.TFrame", background=c["card"], relief="flat")
    st.configure("Surface.TFrame", background=c["surface"])
    st.configure("TLabel", background=c["bg"], foreground=c["text"])
    st.configure("Card.TLabel", background=c["card"], foreground=c["text"])
    st.configure("Muted.TLabel", foreground=c["muted"])
    st.configure("CardMuted.TLabel", background=c["card"], foreground=c["muted"])
    st.configure("Title.TLabel", font=f(20, "bold"), foreground=c["text"])
    st.configure("CardTitle.TLabel", font=f(18, "bold"), foreground=c["text"], background=c["card"])
    st.configure("Section.TLabel", font=f(11, "bold"), foreground=c["primary"], background=c["card"])
    st.configure("Big.TLabel", font=f(13, "bold"), background=c["card"], foreground=c["text"])
    st.configure("TButton", font=f(10), padding=(12, 7), background=c["card"], foreground=c["text"],
                 bordercolor=c["input_border"], lightcolor=c["card"], darkcolor=c["card"], relief="flat")
    st.map("TButton", background=[("disabled", c["surface"]), ("pressed", c["tint"]), ("active", c["hover"])],
           foreground=[("disabled", c["muted"])], bordercolor=[("focus", c["accent"])])
    st.configure("Accent.TButton", font=f(10, "bold"), foreground=c["on_accent"], background=c["accent"],
                 bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"], padding=(14, 8))
    st.map("Accent.TButton", background=[("disabled", c["disabled"]), ("pressed", c["accent_dark"]),
                                         ("active", c["accent_dark"])],
           foreground=[("disabled", c["card"])], bordercolor=[("active", c["accent_dark"])])
    st.configure("Soft.TButton", font=f(10, "bold"), foreground=c["tint_fg"], background=c["tint"], bordercolor=c["tint"],
                 lightcolor=c["tint"], darkcolor=c["tint"], padding=(12, 7))
    st.map("Soft.TButton", background=[("active", mix(c["tint"], c["accent"], 0.15))])
    st.configure("Menu.TButton", font=f(11), padding=(14, 10), anchor="w")
    for s in ("TEntry", "TCombobox", "TSpinbox"):
        st.configure(s, fieldbackground=c["input"], foreground=c["text"], bordercolor=c["input_border"],
                     lightcolor=c["input"], darkcolor=c["input"], insertcolor=c["text"], arrowcolor=c["muted"],
                     background=c["card"], padding=5)
        st.map(s, bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["accent"])],
               fieldbackground=[("readonly", c["input"]), ("disabled", c["surface"])],
               foreground=[("disabled", c["muted"])], selectbackground=[("readonly", c["input"])],
               selectforeground=[("readonly", c["text"])])
    st.configure("Invalid.TEntry", fieldbackground=c["owe_bg"], bordercolor=c["owe"])
    for s in ("TCheckbutton", "TRadiobutton"):
        st.configure(s, background=c["card"], foreground=c["text"], indicatorbackground=c["input"],
                     indicatorforeground=c["accent"], indicatormargin=(0, 0, 6, 0))
        st.map(s, background=[("active", c["card"])], indicatorbackground=[("selected", c["input"])],
               foreground=[("disabled", c["muted"])])
    for s in ("Bg.TCheckbutton", "Bg.TRadiobutton"):
        st.configure(s, background=c["bg"], foreground=c["text"])
        st.map(s, background=[("active", c["bg"])])
    st.configure("TNotebook", background=c["card"], borderwidth=0, bordercolor=c["border"])
    st.configure("TNotebook.Tab", padding=(14, 7), font=f(10), background=c["surface"], foreground=c["muted"],
                 bordercolor=c["border"], lightcolor=c["surface"])
    st.map("TNotebook.Tab", background=[("selected", c["card"])], foreground=[("selected", c["primary"])],
           lightcolor=[("selected", c["card"])])
    st.configure("Treeview", rowheight=layout.px(28), font=f(10), fieldbackground=c["card"],
                 background=c["card"], foreground=c["text"], bordercolor=c["border"])
    st.map("Treeview", background=[("selected", c["tint"])], foreground=[("selected", c["tint_fg"])])
    st.configure("Treeview.Heading", font=f(10, "bold"), background=c["surface"], foreground=c["muted"],
                 bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"], relief="flat")
    st.map("Treeview.Heading", background=[("active", c["tint"])])
    st.configure("TScrollbar", background=c["surface"], troughcolor=c["bg"], bordercolor=c["bg"],
                 arrowcolor=c["muted"], lightcolor=c["surface"], darkcolor=c["surface"])
    st.map("TScrollbar", background=[("active", c["tint"])])
    st.configure("TLabelframe", background=c["card"], bordercolor=c["border"])
    st.configure("TLabelframe.Label", background=c["card"], foreground=c["primary"], font=f(10, "bold"))
    st.configure("TSeparator", background=c["border"])
    st.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["surface"], bordercolor=c["surface"],
                 lightcolor=c["accent"], darkcolor=c["accent"], thickness=6)
