"""Ajuste automático del diseño / Automatic layout fitting.

- px(): convierte medidas en píxeles de diseño (pensadas para 96 ppp y letra normal) a píxeles reales, según la
  escala de Windows (125 %, 150 %...) y el tamaño de letra elegido en Configuración.
- fit_window(): tamaño inicial de ventanas y diálogos escalado y limitado a la pantalla (nunca más grande que ella).
- Textos que se ajustan solos: toda etiqueta con 'wraplength' que ocupa el ancho de su contenedor recalcula su ancho
  de línea cuando cambia el tamaño de la ventana, para que el texto nunca quede cortado ni haya que agrandar la ventana.
"""
from __future__ import annotations

import tkinter as tk

from . import widgets

_state = {"dpi": 1.0, "installed": False}


# ------------------------------------------------------------------------------------------------ escala
def init(root) -> float:
    """Calcula la escala de la pantalla (1.0 = 96 ppp) e instala el ajuste automático de textos."""
    try:
        ppi = float(root.winfo_fpixels("1i"))
        _state["dpi"] = max(1.0, min(3.0, ppi / 96.0))
    except (tk.TclError, TypeError, ValueError, AttributeError):
        _state["dpi"] = 1.0
    if not _state["installed"]:
        for cls in ("Label", "TLabel"):
            try:
                root.bind_class(cls, "<Map>", _on_map, add="+")
            except (tk.TclError, AttributeError):
                pass
        _state["installed"] = True
    return _state["dpi"]


def factor(font_scale: bool = True) -> float:
    f = _state["dpi"]
    if font_scale:
        f *= widgets.STYLE.get("scale", 1.0)
    return f


def px(n, font_scale: bool = True) -> int:
    """Píxeles de diseño -> píxeles reales."""
    return int(round(n * factor(font_scale)))


def screen(win):
    try:
        return int(win.winfo_screenwidth()), int(win.winfo_screenheight())
    except (tk.TclError, TypeError, ValueError, AttributeError):
        return 1920, 1080


def fit_window(win, w, h, minw=None, minh=None):
    """Tamaño escalado y limitado a la pantalla; si la pantalla es más chica que el diseño, la ventana principal se
    maximiza. Devuelve (ancho, alto) aplicados."""
    sw, sh = screen(win)
    maxw, maxh = int(sw * 0.94), int(sh * 0.88)
    W, H = min(px(w), maxw), min(px(h), maxh)
    try:
        win.geometry(f"{W}x{H}")
        if minw or minh:
            win.minsize(min(px(minw or 0), maxw, W), min(px(minh or 0), maxh, H))
    except tk.TclError:
        pass
    return W, H


def maximize_if_small(win, w, h):
    """La ventana principal se abre maximizada cuando la pantalla no alcanza para el tamaño de diseño."""
    sw, sh = screen(win)
    if px(w) > sw * 0.94 or px(h) > sh * 0.88:
        try:
            win.state("zoomed")
        except tk.TclError:
            try:
                win.attributes("-zoomed", True)
            except tk.TclError:
                pass


# ------------------------------------------------------------------------------------------------ textos que se ajustan
def _num(v) -> int:
    try:
        return int(float(str(v).split()[-1])) if str(v).strip() else 0
    except (ValueError, IndexError):
        return 0


def _right_pad(info) -> int:
    pad = str(info.get("padx", 0)).split()
    try:
        return int(float(pad[-1])) if pad else 0
    except ValueError:
        return 0


def _eligible(lbl, parent) -> bool:
    """Solo las etiquetas que ocupan el ancho del contenedor (no las que están al lado de un campo)."""
    try:
        mgr = lbl.winfo_manager()
        if mgr == "pack":
            return str(lbl.pack_info().get("side", "top")) in ("top", "bottom")
        if mgr == "grid":
            span = _num(lbl.grid_info().get("columnspan", 1)) or 1
            cols = parent.grid_size()[0]
            return span >= max(2, cols) or cols <= 1
    except (tk.TclError, AttributeError, TypeError):
        pass
    return False


def _on_map(event):
    lbl = event.widget
    if getattr(lbl, "_aw", None) is not None:
        return
    try:
        wl = _num(lbl.cget("wraplength"))
    except (tk.TclError, AttributeError):
        return
    if wl <= 0:
        lbl._aw = False
        return
    try:
        parent = lbl.nametowidget(lbl.winfo_parent())
    except (tk.TclError, KeyError, AttributeError):
        return
    if not _eligible(lbl, parent):   # etiqueta al lado de un campo: conserva su ancho
        lbl._aw = False
        return
    lbl._aw = True
    group = getattr(parent, "_aw_labels", None)
    if group is None:
        parent._aw_labels = group = []
        parent._aw_job = None
        parent.bind("<Configure>", lambda e, p=parent: _schedule(p), add="+")
    group.append(lbl)
    try:   # si el texto cambia y la etiqueta crece, también se vuelve a ajustar
        lbl.bind("<Configure>", lambda e, p=parent: _schedule(p), add="+")
    except (tk.TclError, AttributeError):
        pass
    _schedule(parent)


def _schedule(parent):
    if getattr(parent, "_aw_job", None):
        return
    try:
        parent._aw_job = parent.after_idle(lambda: _reflow(parent))
    except (tk.TclError, AttributeError):
        parent._aw_job = None


def _reflow(parent):
    parent._aw_job = None
    try:
        width = parent.winfo_width()
        slack = width - parent.winfo_reqwidth()
    except tk.TclError:
        return
    if width < 60:
        return
    alive = []
    for lbl in parent._aw_labels:
        try:
            if not lbl.winfo_exists():
                continue
        except tk.TclError:
            continue
        alive.append(lbl)
        try:
            mgr = lbl.winfo_manager()
            info = lbl.pack_info() if mgr == "pack" else lbl.grid_info() if mgr == "grid" else {}
            room = width - lbl.winfo_x() - _right_pad(info) - lbl.winfo_reqwidth()
            wl = _num(lbl.cget("wraplength"))
            if room < -1:                       # el texto se sale: se acorta la línea lo justo
                new = max(80, wl + room - 2)
            elif room > 8 and slack > 4 and lbl.winfo_reqwidth() + 24 >= wl:
                # sobra espacio y el texto está cortado en varias líneas: la línea se alarga hasta el borde
                new = wl + room - 2
            else:
                continue
            if abs(new - wl) >= 3:
                lbl.configure(wraplength=new)
        except (tk.TclError, AttributeError, TypeError, ValueError):
            continue
    parent._aw_labels = alive
