"""Componentes visuales modernos sobre tkinter / Modern tkinter building blocks (tarjetas, mosaicos, pildoras,
barras de progreso, boton de usuario). Todos leen los colores del tema activo (widgets.COLORS)."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta

from ..i18n import _, tr, N_
from .theme import icon, icon_font, mix
from .widgets import COLORS, font, Tooltip


def C(key):
    return COLORS[key]


def card(parent, bg=None, border=True, padx=18, pady=16, **kw):
    bg = bg or C("card")
    return tk.Frame(parent, bg=bg, padx=padx, pady=pady, highlightthickness=1 if border else 0,
                    highlightbackground=C("border"), highlightcolor=C("border"), **kw)


def label(parent, text, size=10, weight="normal", fg=None, bg=None, **kw):
    return tk.Label(parent, text=text, font=font(size, weight), fg=fg or C("text"), bg=bg or parent["bg"],
                    anchor=kw.pop("anchor", "w"), justify=kw.pop("justify", "left"), **kw)


def _all_children(w):
    out = [w]
    for c in w.winfo_children():
        out.extend(_all_children(c))
    return out


class Clickable:
    """Hace que un marco y todos sus hijos respondan a clic, teclado (Enter/espacio) y paso del mouse."""

    def make_clickable(self, command, hover_bg, base_bg, keep=()):
        self._cmd, self._hover, self._base, self._keep = command, hover_bg, base_bg, keep
        for w in _all_children(self):
            w.bind("<Button-1>", self._click, add="+")
            w.bind("<Enter>", lambda e: self._paint(self._hover), add="+")
            w.bind("<Leave>", lambda e: self._paint(self._base), add="+")
            try:
                w.configure(cursor="hand2")
            except tk.TclError:
                pass
        self.configure(takefocus=1)
        self.bind("<Return>", self._click)
        self.bind("<space>", self._click)
        self.bind("<FocusIn>", lambda e: self.configure(highlightthickness=2, highlightbackground=C("accent")))
        self.bind("<FocusOut>", lambda e: self.configure(highlightthickness=1, highlightbackground=self._border))

    def _click(self, _e=None):
        if self._cmd:
            self._cmd()
        return "break"

    def _paint(self, bg):
        for w in _all_children(self):
            if w in self._keep:
                continue
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass


class Tile(tk.Frame, Clickable):
    """Mosaico/tarjeta clicable con icono, titulo y descripcion. variant: card | accent | outline."""

    def __init__(self, parent, title, desc="", icon_name=None, command=None, variant="card", badge=None,
                 enabled=True, tip=None, title_size=13, padx=18, pady=16, wrap=220, horizontal=False):
        c = COLORS
        if variant == "accent":
            bg, fg, sub, border = c["accent"], c["on_accent"], mix(c["on_accent"], c["accent"], 0.22), c["accent"]
            ibg, ifg = mix(c["accent"], c["on_accent"], 0.18), c["on_accent"]
            hover = c["accent_dark"]
        elif variant == "outline":
            bg, fg, sub, border = c["tint"], c["text"], c["muted"], c["accent"]
            ibg, ifg, hover = c["card"], c["tint_fg"], mix(c["tint"], c["accent"], 0.10)
        else:
            bg, fg, sub, border = c["card"], c["text"], c["muted"], c["border"]
            ibg, ifg, hover = c["tint"], c["tint_fg"], c["hover"]
        if not enabled:
            fg, sub, ifg, hover = c["muted"], c["muted"], c["muted"], bg
        super().__init__(parent, bg=bg, padx=padx, pady=pady, highlightthickness=1, highlightbackground=border,
                         highlightcolor=c["accent"])
        self._border = border
        keep = []
        top = tk.Frame(self, bg=bg)
        top.pack(side="left" if horizontal else "top", fill="y" if horizontal else "x", anchor="n")
        if icon_name:
            ic = tk.Label(top, text=icon(icon_name), font=icon_font(15), bg=ibg, fg=ifg, width=3, pady=6)
            ic.pack(side="left", anchor="n")
            keep.append(ic)
        if badge:
            b = tk.Label(top, text=badge, font=font(8, "bold"), bg=c["accent"], fg=c["on_accent"], padx=8, pady=2)
            b.pack(side="right", anchor="n")
            keep.append(b)
        body = tk.Frame(self, bg=bg)
        body.pack(side="left" if horizontal else "top", fill="both", expand=True,
                  padx=(14, 0) if horizontal else 0, pady=(0 if horizontal else 12, 0))
        tk.Label(body, text=title, font=font(title_size, "bold"), bg=bg, fg=fg, anchor="w", justify="left",
                 wraplength=wrap + 60).pack(anchor="w")
        if desc:
            tk.Label(body, text=desc, font=font(9), bg=bg, fg=sub, anchor="w", justify="left",
                     wraplength=wrap).pack(anchor="w", pady=(3, 0))
        self.make_clickable(command if enabled else None, hover, bg, keep=keep)
        if tip:
            Tooltip(self, tip)


class Pill(tk.Frame):
    """Indicador de resultado (Federal / Estatal / Total) con fondo verde o rojo segun el signo."""

    def __init__(self, parent, title, dark=False):
        super().__init__(parent, bg=C("refund_bg"), padx=12, pady=5)
        self.dark = dark
        self.t = tk.Label(self, text=title, font=font(8, "bold"), bg=C("refund_bg"), fg=C("refund"), anchor="w")
        self.t.pack(anchor="w")
        self.v = tk.Label(self, text="—", font=font(13, "bold"), bg=C("refund_bg"), fg=C("refund"), anchor="w")
        self.v.pack(anchor="w")
        self.title = title

    def set(self, value: float, text: str):
        if self.dark:
            bg, fg = C("chip"), C("chip_fg")
        elif value >= 0:
            bg, fg = C("refund_bg"), C("refund")
        else:
            bg, fg = C("owe_bg"), C("owe")
        for w in (self, self.t, self.v):
            w.configure(bg=bg)
        self.t.configure(fg=fg)
        self.v.configure(fg=fg, text=text)


class Progress(tk.Frame):
    def __init__(self, parent, pct=0.0, height=6, bg=None):
        super().__init__(parent, bg=bg or C("surface"), height=height)
        self.pack_propagate(False)
        self.bar = tk.Frame(self, bg=C("accent"), height=height)
        self.set(pct)

    def set(self, pct):
        self.bar.place(x=0, y=0, relheight=1, relwidth=max(0.0, min(1.0, pct)))


class IconButton(tk.Label):
    def __init__(self, parent, name, command, tip=None, size=13, bg=None, fg=None, padx=10, pady=6, border=True):
        bg = bg or parent["bg"]
        super().__init__(parent, text=icon(name), font=icon_font(size), bg=bg, fg=fg or C("text"), padx=padx, pady=pady,
                         cursor="hand2", highlightthickness=1 if border else 0, highlightbackground=C("border"),
                         takefocus=1)
        self._bg = bg
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Return>", lambda e: command())
        self.bind("<Enter>", lambda e: self.configure(bg=C("hover") if not C("dark") else C("surface")))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))
        if tip:
            Tooltip(self, tip)


def flat_button(parent, text, command, kind="ghost", size=10, icon_name=None, padx=14, pady=7):
    """Boton plano (tk.Label) para barras: kind = accent | chip | ghost | soft."""
    c = COLORS
    bg_parent = parent["bg"]
    bg, fg, hover = {
        "accent": (c["accent"], c["on_accent"], c["accent_dark"]),
        "chip": (c["chip"], c["chip_fg"], mix(c["chip"], c["chip_fg"], 0.15)),
        "soft": (c["tint"], c["tint_fg"], mix(c["tint"], c["accent"], 0.12)),
        "ghost": (bg_parent, c["text"], c["hover"] if not c["dark"] else c["surface"]),
    }[kind]
    f = tk.Frame(parent, bg=bg, padx=padx, pady=pady, cursor="hand2", takefocus=1)
    parts = []
    if icon_name:
        il = tk.Label(f, text=icon(icon_name), font=icon_font(size + 1), bg=bg, fg=fg)
        il.pack(side="left", padx=(0, 8))
        parts.append(il)
    tl = tk.Label(f, text=text, font=font(size, "bold"), bg=bg, fg=fg)
    tl.pack(side="left")
    parts.append(tl)
    for w in [f] + parts:
        w.bind("<Button-1>", lambda e: command())
        w.bind("<Enter>", lambda e: [x.configure(bg=hover) for x in [f] + parts])
        w.bind("<Leave>", lambda e: [x.configure(bg=bg) for x in [f] + parts])
    f.bind("<Return>", lambda e: command())
    f.bind("<space>", lambda e: command())
    return f


def initials(name: str) -> str:
    parts = [p for p in (name or "?").replace(".", " ").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def user_chip(parent, app, fg=None, bg=None):
    """Circulo con iniciales + nombre y rol; al hacer clic muestra el menu de la cuenta."""
    from ..accounts import ROLE_LABELS
    u = app.user or {}
    bg = bg or parent["bg"]
    f = tk.Frame(parent, bg=bg, cursor="hand2", padx=6, pady=2)
    av = tk.Label(f, text=initials(u.get("name") or u.get("username", "")), font=font(9, "bold"), bg=C("chip"),
                  fg=C("chip_fg"), width=3, pady=4)
    av.pack(side="left")
    t = tk.Frame(f, bg=bg)
    t.pack(side="left", padx=(8, 0))
    tk.Label(t, text=u.get("username", ""), font=font(10, "bold"), bg=bg, fg=fg or C("text")).pack(anchor="w")
    tk.Label(t, text=_(ROLE_LABELS.get(u.get("role"), "")), font=font(8), bg=bg, fg=C("muted")).pack(anchor="w")
    menu = tk.Menu(f, tearoff=False)
    menu.add_command(label=_("Configuración"), command=app.show_settings)
    menu.add_command(label=_("Mi cuenta y contraseña"), command=lambda: app.show_settings("account"))
    menu.add_separator()
    menu.add_command(label=_("Cerrar sesión"), command=app.logout)

    def post(e):
        try:
            menu.tk_popup(e.x_root, e.y_root + 10)
        finally:
            menu.grab_release()
    for w in _all_children(f):
        w.bind("<Button-1>", post)
    Tooltip(f, _("Su cuenta: configuración y cerrar sesión"))
    return f


def lang_toggle(parent, app, bg=None):
    """Selector Español | English con el idioma activo resaltado."""
    from .. import i18n
    bg = bg or parent["bg"]
    f = tk.Frame(parent, bg=C("surface"), padx=3, pady=3)
    for code, name in i18n.LANGS.items():
        on = code == i18n.get_language()
        b = tk.Label(f, text=name, font=font(9, "bold"), padx=10, pady=4, cursor="hand2",
                     bg=C("card") if on else C("surface"), fg=C("text") if on else C("muted"))
        b.pack(side="left")
        b.bind("<Button-1>", lambda e, c=code: app.set_language(c))
    return f


# ---------------------------------------------------------------------------- fechas clave
def _weekday_roll(d: date) -> date:
    while d.weekday() >= 5:   # sabado/domingo -> lunes
        d += timedelta(days=1)
    return d


MONTHS = [N_("ene"), N_("feb"), N_("mar"), N_("abr"), N_("may"), N_("jun"), N_("jul"), N_("ago"), N_("sep"),
          N_("oct"), N_("nov"), N_("dic")]


def fmt_date(d: date) -> str:
    return tr("{d} {m} {y}", d=d.day, m=_(MONTHS[d.month - 1]), y=d.year)


def key_dates(today: date = None):
    """Fechas proximas del IRS: [(fecha, texto, es_vencimiento_de_declaracion)] ordenadas (12 meses)."""
    today = today or date.today()
    out = []
    for y in (today.year, today.year + 1):
        out += [
            (_weekday_roll(date(y, 1, 15)), tr("4.º pago estimado de {y}", y=y - 1), False),
            (_weekday_roll(date(y, 4, 15)), tr("Vence la declaración {y} (y 1.er pago estimado de {z})", y=y - 1, z=y), True),
            (_weekday_roll(date(y, 6, 15)), tr("2.º pago estimado de {y}", y=y), False),
            (_weekday_roll(date(y, 9, 15)), tr("3.er pago estimado de {y}", y=y), False),
            (_weekday_roll(date(y, 10, 15)), tr("Límite con prórroga (Formulario 4868) para {y}", y=y - 1), False),
        ]
    return sorted([x for x in out if x[0] >= today and (x[0] - today).days <= 400])


def next_filing_deadline(today: date = None):
    today = today or date.today()
    for d, txt, main in key_dates(today):
        if main:
            return d, d.year - 1, (d - today).days
    d = _weekday_roll(date(today.year + 1, 4, 15))
    return d, today.year, (d - today).days


def year_status(tax_year: int, today: date = None) -> str:
    today = today or date.today()
    due = _weekday_roll(date(tax_year + 1, 4, 15))
    ext = _weekday_roll(date(tax_year + 1, 10, 15))
    if today <= due:
        return tr("Vence el {d}", d=fmt_date(due))
    if today <= ext:
        return tr("Con prórroga: hasta el {d}", d=fmt_date(ext))
    return _("Plazo vencido · aún puede presentar")
