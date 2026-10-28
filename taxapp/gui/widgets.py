"""Widgets y utilidades de la interfaz (tkinter/ttk)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from ..i18n import _
from ..models import clean_money_text

# ----------------------------------------------------------------------------- paleta y fuentes
COLORS = {
    "primary": "#0B5D3B", "primary_dark": "#08442B", "accent": "#1F8A5B", "accent_light": "#E7F4EC",
    "sidebar": "#12302A", "sidebar_fg": "#CFE3DA", "sidebar_sel": "#1F8A5B",
    "bg": "#F4F7F5", "card": "#FFFFFF", "text": "#1D2733", "muted": "#5B6775", "border": "#D9E0E7",
    "refund": "#1E9E5A", "owe": "#C0392B", "warn": "#B9770E", "info": "#2471A3",
}  # se reemplaza por la paleta del tema activo (theme.apply)
STYLE = {"family": "Segoe UI", "scale": 1.0}


def font(size=10, weight="normal"):
    return (STYLE["family"], max(7, round(size * STYLE["scale"])), weight)


def parse_money(text: str) -> Optional[float]:
    t = clean_money_text(text or "")
    if t in ("", "-", "."):
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def money_str(v) -> str:
    if v in (None, "") or float(v) == 0:
        return ""
    v = float(v)
    return f"{v:,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"


# ----------------------------------------------------------------------------- tooltip
class Tooltip:
    def __init__(self, widget, text: str, wrap=360):
        self.widget, self.text, self.wrap, self.tip = widget, text, wrap, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _e=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", wraplength=self.wrap, background=COLORS.get("tooltip", "#FFFDE7"),
                 foreground=COLORS.get("tooltip_fg", "#333333"),
                 relief="solid", borderwidth=1, font=font(9), padx=8, pady=6).pack()

    def hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ----------------------------------------------------------------------------- marco desplazable
class ScrollFrame(ttk.Frame):
    """Marco con barra de desplazamiento vertical; agregue contenido a .inner"""
    _wheel_bound = False

    def __init__(self, parent, bg=None, **kw):
        super().__init__(parent, **kw)
        bg = bg or COLORS["card"]
        self.canvas = tk.Canvas(self, highlightthickness=0, background=bg, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Card.TFrame")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas._sf = self
        if not ScrollFrame._wheel_bound:
            # Un solo manejador global: desplaza el ScrollFrame que esta bajo el puntero.
            self.bind_all("<MouseWheel>", ScrollFrame._route, add="+")
            self.bind_all("<Button-4>", ScrollFrame._route, add="+")
            self.bind_all("<Button-5>", ScrollFrame._route, add="+")
            ScrollFrame._wheel_bound = True

    @staticmethod
    def _route(e):
        try:
            w = e.widget.winfo_containing(e.x_root, e.y_root)
        except (AttributeError, KeyError, tk.TclError):
            return
        while w is not None:
            if w.winfo_class() in ("Treeview", "Text", "TCombobox", "Listbox"):
                return  # estos widgets tienen su propio desplazamiento
            sf = getattr(w, "_sf", None)
            if sf is not None:
                if getattr(e, "num", None) == 4:
                    step = -2
                elif getattr(e, "num", None) == 5:
                    step = 2
                else:
                    step = int(-e.delta / 120) or (-1 if e.delta > 0 else 1)
                sf.canvas.yview_scroll(step, "units")
                return
            w = w.master


# ----------------------------------------------------------------------------- formulario enlazado
class Form:
    """Construye filas etiqueta / campo / ayuda enlazadas a atributos de un objeto del modelo.

    getobj: funcion que devuelve el objeto (asi el formulario siempre escribe en la declaracion actual).
    on_change: se llama despues de cada cambio valido.
    """

    def __init__(self, parent, getobj: Callable, on_change: Callable = None, label_width=34):
        self.parent = parent
        self.getobj = getobj
        self.on_change = on_change or (lambda: None)
        self.row = 0
        self.label_width = label_width
        self.vars = {}
        parent.columnconfigure(1, weight=1)

    # -- utilidades
    # Funcion global (la asigna la App) para preguntar a la IA sobre un campo: ai_hook(etiqueta, ayuda, widget)
    ai_hook: Optional[Callable] = None

    def _help_icon(self, text, help_text, column=2):
        """'?' con la ayuda; al hacer clic pregunta a la IA sobre el campo (si esta habilitado)."""
        if not help_text and not Form.ai_hook:
            return None
        q = ttk.Label(self.parent, text=" ? ", style="CardMuted.TLabel", cursor="hand2" if Form.ai_hook else "question_arrow")
        q.grid(row=self.row, column=column, sticky="w", padx=4)
        tip = help_text or ""
        if Form.ai_hook:
            q.configure(foreground=COLORS["info"])
            tip = (tip + "\n\n" if tip else "") + "✦ " + _("Clic: preguntar a la IA sobre este campo")
            q.bind("<Button-1>", lambda e, t=text, h=help_text: Form.ai_hook(t, h or "", q))
        Tooltip(q, tip)
        return q

    def _label(self, text, help_text=None):
        from . import layout
        # Ancho mínimo (no fijo) para que el texto nunca quede cortado; la línea se parte a ~38 caracteres.
        lbl = ttk.Label(self.parent, text=text, style="Card.TLabel", width=-self.label_width, anchor="w",
                        wraplength=layout.px(max(300, self.label_width * 9)))
        lbl.grid(row=self.row, column=0, sticky="w", padx=(4, 8), pady=3)
        if help_text:
            Tooltip(lbl, help_text)
        self._help_icon(text, help_text)
        return lbl

    def _set(self, attr, value):
        obj = self.getobj()
        if obj is not None:
            setattr(obj, attr, value)
            self.on_change()

    def section(self, title: str, subtitle: str = None):
        ttk.Label(self.parent, text=title, style="Section.TLabel").grid(row=self.row, column=0, columnspan=3,
                                                                        sticky="w", padx=4, pady=(14, 2))
        self.row += 1
        if subtitle:
            ttk.Label(self.parent, text=subtitle, style="CardMuted.TLabel", wraplength=640, justify="left").grid(
                row=self.row, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 4))
            self.row += 1

    def note(self, text: str, color=None):
        lbl = ttk.Label(self.parent, text=text, style="CardMuted.TLabel", wraplength=640, justify="left")
        if color:
            lbl.configure(foreground=color)
        lbl.grid(row=self.row, column=0, columnspan=3, sticky="w", padx=4, pady=(2, 6))
        self.row += 1
        return lbl

    def money(self, label, attr, help_text=None, width=16):
        self._label(label, help_text)
        var = tk.StringVar(value=money_str(getattr(self.getobj(), attr, 0)))
        ent = ttk.Entry(self.parent, textvariable=var, width=width, justify="right")
        ent.grid(row=self.row, column=1, sticky="w", pady=3)

        def changed(*_):
            v = parse_money(var.get())
            if v is None:
                ent.configure(style="Invalid.TEntry")
                return
            ent.configure(style="TEntry")
            self._set(attr, v)

        def reformat(_e=None):
            v = parse_money(var.get())
            if v is not None:
                var.set(money_str(v))

        var.trace_add("write", changed)
        ent.bind("<FocusOut>", reformat)
        self.vars[attr] = var
        self.row += 1
        return ent

    def text(self, label, attr, help_text=None, width=32, upper=False, show=None):
        self._label(label, help_text)
        var = tk.StringVar(value=str(getattr(self.getobj(), attr, "") or ""))
        ent = ttk.Entry(self.parent, textvariable=var, width=width, show=show or "")
        ent.grid(row=self.row, column=1, sticky="w", pady=3)

        def changed(*_):
            v = var.get()
            if upper and v != v.upper():
                var.set(v.upper())
                return
            self._set(attr, v.strip())

        var.trace_add("write", changed)
        self.vars[attr] = var
        self.row += 1
        return ent

    def integer(self, label, attr, help_text=None, frm=0, to=12):
        self._label(label, help_text)
        var = tk.StringVar(value=str(getattr(self.getobj(), attr, 0) or 0))
        sp = ttk.Spinbox(self.parent, from_=frm, to=to, textvariable=var, width=6)
        sp.grid(row=self.row, column=1, sticky="w", pady=3)

        def changed(*_):
            try:
                self._set(attr, int(var.get() or 0))
            except ValueError:
                pass  # el número está a medio escribir; se guarda en la próxima tecla válida

        var.trace_add("write", changed)
        self.vars[attr] = var
        self.row += 1
        return sp

    def check(self, label, attr, help_text=None, on_toggle=None):
        var = tk.BooleanVar(value=bool(getattr(self.getobj(), attr, False)))
        cb = ttk.Checkbutton(self.parent, text=label, variable=var)
        cb.grid(row=self.row, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        if help_text:
            Tooltip(cb, help_text)
        self._help_icon(label, help_text)

        def changed(*_):
            self._set(attr, bool(var.get()))
            if on_toggle:
                on_toggle()

        var.trace_add("write", changed)
        self.vars[attr] = var
        self.row += 1
        return cb

    def combo(self, label, attr, values: List[str], help_text=None, width=34, readonly=True,
              to_model=None, from_model=None, on_select=None):
        """to_model/from_model convierten entre el texto mostrado y el valor guardado."""
        self._label(label, help_text)
        cur = getattr(self.getobj(), attr, "")
        var = tk.StringVar(value=from_model(cur) if from_model else (cur or ""))
        cb = ttk.Combobox(self.parent, textvariable=var, values=values, width=width,
                          state="readonly" if readonly else "normal")
        cb.grid(row=self.row, column=1, sticky="w", pady=3)

        def changed(*_):
            v = var.get()
            self._set(attr, to_model(v) if to_model else v)
            if on_select:
                on_select()

        var.trace_add("write", changed)
        self.vars[attr] = var
        self.row += 1
        return cb


def make_tree(parent, columns, headings, widths=None, height=8, anchors=None) -> ttk.Treeview:
    frame = ttk.Frame(parent, style="Card.TFrame")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for i, (c, h) in enumerate(zip(columns, headings)):
        tree.heading(c, text=h)
        from . import layout
        tree.column(c, width=layout.px(widths[i] if widths else 120), anchor=(anchors[i] if anchors else "w"),
                    stretch=True, minwidth=layout.px(40))
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    tree.frame = frame
    return tree


class Dialog(tk.Toplevel):
    """Dialogo modal con un formulario sobre un objeto temporal; on_ok(obj) al aceptar."""

    def __init__(self, master, title, obj, build: Callable, on_ok: Callable, width=560, height=560):
        super().__init__(master)
        self.title(title)
        self.configure(bg=COLORS["card"])
        self.transient(master)
        from . import layout
        layout.fit_window(self, width, height, 460, 360)
        self.obj = obj
        self.on_ok = on_ok
        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        inner = ttk.Frame(sf.inner, style="Card.TFrame", padding=10)
        inner.pack(fill="both", expand=True)
        self.form = Form(inner, lambda: self.obj, label_width=30)
        build(self.form)
        bar = ttk.Frame(self, style="Card.TFrame", padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text=_("Cancelar"), command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text=_("Aceptar"), style="Accent.TButton", command=self._ok).pack(side="right", padx=4)
        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def _ok(self):
        self.on_ok(self.obj)
        self.destroy()
