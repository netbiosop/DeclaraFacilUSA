"""Menu principal en tres estilos / Main menu in three styles (A tarjetas, B oscuro con barra lateral, C guiado) y la
ventana 'Mis declaraciones'."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import ttk

from .. import APP_NAME, __version__, accounts, storage
from ..i18n import _, N_, tr
from . import theme
from .theme import icon, icon_font, mix
from .ui import (C, Tile, Progress, IconButton, flat_button, user_chip, lang_toggle, label, card, fmt_date,
                 key_dates, next_filing_deadline, year_status)
from .widgets import COLORS, font, Tooltip, make_tree
from . import layout


def _actions(app):
    """Acciones del menu principal con su permiso."""
    edit, ai, tables = app.can("edit"), app.can("use_ai"), app.can("tax_tables")
    no_edit = _("Su rol no permite crear declaraciones.")
    return {
        "new2025": dict(title=_("Nueva declaración 2025"), desc=_("Se presenta en 2026"), icon="add",
                        cmd=lambda: app.new_return(2025), enabled=edit, tip=None if edit else no_edit),
        "new2026": dict(title=_("Nueva declaración 2026"), desc=_("Se presenta en 2027"), icon="add",
                        cmd=lambda: app.new_return(2026), enabled=edit, tip=None if edit else no_edit),
        "open": dict(title=_("Abrir guardada"), desc=_("Archivos .dfusa · Ctrl+O"), icon="open", cmd=app.open_file),
        "mine": dict(title=_("Mis declaraciones"), desc=_("Todas sus declaraciones guardadas"), icon="folder",
                     cmd=app.open_returns),
        "explorer": dict(title=_("Estados y condados"), desc=_("Tasas y reglas de los 50 estados y DC"), icon="map",
                         cmd=app.open_explorer),
        "calc": dict(title=_("Calculadora rápida"), desc=_("Estimado en 1 minuto"), icon="calc", cmd=app.open_quick_calc),
        "ai": dict(title=_("Asistente de IA"), desc=_("Claude, ChatGPT, Gemini u Ollama"), icon="ai",
                   cmd=app.open_assistant, enabled=ai, tip=None if ai else _("Su rol no incluye el asistente de IA.")),
        "guide": dict(title=_("Guía de impuestos"), desc=_("Cómo funciona todo"), icon="book", cmd=app.open_guide),
        "counties": dict(title=_("Actualizar lista de condados (Censo)"), icon="download", cmd=app.download_counties,
                         enabled=tables),
        "settings": dict(title=_("Configuración"), icon="settings", cmd=app.show_settings),
    }


def _tile(parent, a, **kw):
    return Tile(parent, a["title"], kw.pop("desc", a.get("desc", "")), a["icon"], a["cmd"],
                enabled=a.get("enabled", True), tip=a.get("tip"), **kw)


def _continue_info(app):
    """(texto, porcentaje, comando) para 'continuar donde quedo'."""
    if app.ret:
        pct = app.workspace.refresh_nav() if app.workspace else 0
        name = app.path.name if app.path else tr("Declaración {y} (sin guardar)", y=app.ret.tax_year)
        return name, pct, app.continue_return
    rec = storage.recent()
    if rec:
        p = rec[0]
        return Path(p).name, None, lambda: app.open_file(p)
    return None, None, None


# ============================================================================ Opcion A
class HomeA(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C("bg"))
        self.app = app
        c = COLORS
        acts = _actions(app)
        head = tk.Frame(self, bg=c["header"], padx=28, pady=12)
        head.pack(fill="x")
        logo = tk.Label(head, text=icon("doc"), font=icon_font(16), bg=c["accent"], fg=c["on_accent"], width=3, pady=6)
        logo.pack(side="left")
        t = tk.Frame(head, bg=c["header"])
        t.pack(side="left", padx=12)
        tk.Label(t, text=APP_NAME, font=font(15, "bold"), bg=c["header"], fg=c["header_fg"]).pack(anchor="w")
        tk.Label(t, text=_("Impuestos federales, estatales y locales · 2025–2026"), font=font(9), bg=c["header"],
                 fg=c["header_muted"]).pack(anchor="w")
        user_chip(head, app, fg=c["header_fg"], bg=c["header"]).pack(side="right", padx=(12, 0))
        IconButton(head, "settings", app.show_settings, tip=_("Configuración"), bg=c["header"], fg=c["header_fg"]).pack(side="right", padx=(8, 0))
        if acts["ai"]["enabled"]:
            flat_button(head, _("Asistente IA") + "   Ctrl+I", app.open_assistant, kind="chip", icon_name="ai").pack(side="right", padx=(8, 0))
        lang_toggle(head, app).pack(side="right")
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

        body = tk.Frame(self, bg=c["bg"], padx=32, pady=26)
        body.pack(fill="both", expand=True)
        aside = tk.Frame(body, bg=c["bg"], width=layout.px(340))
        aside.pack(side="right", fill="y", padx=(26, 0))
        aside.pack_propagate(False)
        main = tk.Frame(body, bg=c["bg"])
        main.pack(side="left", fill="both", expand=True)

        label(main, _("¿Qué quiere hacer hoy?"), 22, "bold").pack(anchor="w")
        label(main, tr("Hola, {n}. Empiece una declaración nueva o siga donde la dejó.",
                       n=(app.user or {}).get("name", "")), 11, fg=c["muted"]).pack(anchor="w", pady=(4, 16))
        row = tk.Frame(main, bg=c["bg"])
        row.pack(fill="x")
        for i, (k, v) in enumerate((("new2025", "accent"), ("new2026", "card"), ("open", "card"))):
            _tile(row, acts[k], variant=v if acts[k].get("enabled", True) else "card", title_size=14).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 14, 0))
            row.columnconfigure(i, weight=1, uniform="a")

        name, pct, cmd = _continue_info(app)
        if name:
            cont = card(main, padx=20, pady=14)
            cont.pack(fill="x", pady=16)
            tk.Label(cont, text=icon("doc"), font=icon_font(15), bg=c["refund_bg"], fg=c["refund"], width=3, pady=6).pack(side="left")
            mid = tk.Frame(cont, bg=c["card"])
            mid.pack(side="left", fill="x", expand=True, padx=14)
            label(mid, tr("Continuar: {n}", n=name), 11, "bold").pack(anchor="w")
            if pct is not None:
                Progress(mid, pct, height=7).pack(fill="x", pady=(8, 0))
                label(mid, tr("{p}% completo", p=f"{pct * 100:.0f}"), 9, fg=c["muted"]).pack(anchor="w", pady=(4, 0))
            else:
                label(mid, _("Abrir la declaración más reciente"), 9, fg=c["muted"]).pack(anchor="w")
            ttk.Button(cont, text=_("Continuar") + "  ›", style="Soft.TButton", command=cmd).pack(side="right")
        else:
            tk.Frame(main, bg=c["bg"], height=16).pack()

        label(main, _("HERRAMIENTAS"), 9, "bold", fg=c["muted"]).pack(anchor="w", pady=(6, 10))
        tools = tk.Frame(main, bg=c["bg"])
        tools.pack(fill="x")
        for i, k in enumerate(("explorer", "calc", "ai", "guide")):
            a = acts[k]
            v = "outline" if k == "ai" and a.get("enabled", True) else "card"
            _tile(tools, a, variant=v, title_size=11, padx=14, pady=14, wrap=150,
                  badge=_("NUEVO") if k == "ai" and a.get("enabled", True) else None).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            tools.columnconfigure(i, weight=1, uniform="t")
        _tile(main, acts["mine"], horizontal=True, title_size=11, padx=14, pady=12, wrap=420).pack(fill="x", pady=(12, 0))

        # lateral: fecha limite, recientes, utilidades
        d, y, days = next_filing_deadline()
        dl = tk.Frame(aside, bg=c["chip"], padx=20, pady=18)
        dl.pack(fill="x")
        sub = mix(c["chip_fg"], c["chip"], 0.35)
        tk.Label(dl, text=icon("calendar") + "  " + _("Próxima fecha límite"), font=font(9, "bold"), bg=c["chip"],
                 fg=sub).pack(anchor="w")
        tk.Label(dl, text=tr("{n} días", n=days), font=font(28, "bold"), bg=c["chip"], fg=c["chip_fg"]).pack(anchor="w", pady=(6, 0))
        tk.Label(dl, text=tr("Declaración {y} · {d}", y=y, d=fmt_date(d)), font=font(10), bg=c["chip"],
                 fg=c["chip_fg"]).pack(anchor="w")
        others = [x for x in key_dates() if not x[2]][:2]
        if others:
            tk.Frame(dl, bg=mix(c["chip"], c["chip_fg"], 0.2), height=1).pack(fill="x", pady=10)
            for dd, txt, _m in others:
                tk.Label(dl, text=f"{fmt_date(dd)} · {txt}", font=font(9), bg=c["chip"], fg=sub, wraplength=290,
                         justify="left").pack(anchor="w")

        rc = card(aside, padx=16, pady=14)
        rc.pack(fill="x", pady=14)
        label(rc, _("RECIENTES"), 9, "bold", fg=c["muted"]).pack(anchor="w", pady=(0, 6))
        rec = storage.recent()[:5]
        if not rec:
            label(rc, _("(ninguna todavía)"), 10, fg=c["muted"]).pack(anchor="w")
        for p in rec:
            lb = label(rc, "  " + Path(p).name, 10, fg=c["info"], cursor="hand2")
            lb.pack(anchor="w", pady=2)
            lb.bind("<Button-1>", lambda e, path=p: app.open_file(path))

        bottom = tk.Frame(aside, bg=c["bg"])
        bottom.pack(side="bottom", fill="x")
        if acts["counties"]["enabled"]:
            ttk.Button(bottom, text=acts["counties"]["title"], command=acts["counties"]["cmd"]).pack(fill="x")
        b2 = tk.Frame(bottom, bg=c["bg"])
        b2.pack(fill="x", pady=(10, 0))
        label(b2, tr("Versión {v}", v=__version__), 9, fg=c["muted"]).pack(side="left")
        flat_button(b2, _("Salir"), app.quit_app, kind="ghost", icon_name="logout", size=9).pack(side="right")


# ============================================================================ Opcion B
class HomeB(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C("bg"))
        self.app = app
        c = COLORS
        acts = _actions(app)
        nav = tk.Frame(self, bg=c["sidebar"], width=layout.px(250), padx=14, pady=20)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Frame(self, bg=c["border"], width=1).pack(side="left", fill="y")
        lg = tk.Frame(nav, bg=c["sidebar"], padx=8)
        lg.pack(fill="x", pady=(0, 22))
        tk.Label(lg, text=icon("doc"), font=icon_font(14), bg=c["accent"], fg=c["on_accent"], width=3, pady=5).pack(side="left")
        tk.Label(lg, text="DeclaraFácil", font=font(14, "bold"), bg=c["sidebar"], fg=c["text"]).pack(side="left", padx=10)

        def item(parent, ic, text, cmd, active=False, enabled=True):
            bg = c["sidebar_sel"] if active else c["sidebar"]
            fg = c["sidebar_sel_fg"] if active else (c["sidebar_fg"] if enabled else c["disabled"])
            f = tk.Frame(parent, bg=bg, padx=12, pady=9, cursor="hand2" if enabled else "arrow")
            f.pack(fill="x", pady=1)
            a = tk.Label(f, text=icon(ic), font=icon_font(12), bg=bg, fg=c["accent"] if active else fg)
            a.pack(side="left")
            b = tk.Label(f, text=text, font=font(10, "bold" if active else "normal"), bg=bg, fg=fg)
            b.pack(side="left", padx=12)
            if enabled:
                for w in (f, a, b):
                    w.bind("<Button-1>", lambda e: cmd())
                    if not active:
                        w.bind("<Enter>", lambda e: [x.configure(bg=c["surface"]) for x in (f, a, b)])
                        w.bind("<Leave>", lambda e: [x.configure(bg=bg) for x in (f, a, b)])
            return f
        item(nav, "home", _("Inicio"), lambda: None, active=True)
        for k in ("mine", "explorer", "calc", "ai", "guide", "settings"):
            a = acts[k]
            item(nav, a["icon"], a["title"], a["cmd"], enabled=a.get("enabled", True))
        bottom = tk.Frame(nav, bg=c["sidebar"])
        bottom.pack(side="bottom", fill="x")
        tk.Frame(bottom, bg=c["border"], height=1).pack(fill="x", pady=(0, 10))
        from .. import i18n
        other = "en" if i18n.get_language() == "es" else "es"
        item(bottom, "globe", i18n.LANGS[other], lambda: app.set_language(other))
        if acts["counties"]["enabled"]:
            item(bottom, "download", _("Actualizar condados"), acts["counties"]["cmd"])
        item(bottom, "logout", _("Cerrar sesión"), app.logout)
        item(bottom, "exit", _("Salir"), app.quit_app)

        main = tk.Frame(self, bg=c["bg"], padx=32, pady=28)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=c["bg"])
        top.pack(fill="x")
        user_chip(top, app).pack(side="right")
        label(top, tr("Hola, {n}", n=(app.user or {}).get("name", "")), 11, fg=c["muted"]).pack(side="left")

        row = tk.Frame(main, bg=c["bg"])
        row.pack(fill="x", pady=(14, 0))
        hero = card(row, padx=28, pady=26)
        hero.pack(side="left", fill="both", expand=True)
        label(hero, _("TEMPORADA DE IMPUESTOS"), 9, "bold", fg=c["primary"]).pack(anchor="w")
        label(hero, _("Su declaración, clara de principio a fin."), 22, "bold", wraplength=520).pack(anchor="w", pady=(8, 4))
        label(hero, _("Federal, estatal y local en un solo lugar. Vea su reembolso cambiar mientras escribe."), 11,
              fg=c["muted"], wraplength=520).pack(anchor="w")
        btns = tk.Frame(hero, bg=c["card"])
        btns.pack(anchor="w", pady=(20, 0))
        if acts["new2025"]["enabled"]:
            ttk.Button(btns, text="+  " + acts["new2025"]["title"], style="Accent.TButton", command=acts["new2025"]["cmd"]).pack(side="left")
            ttk.Button(btns, text=_("Nueva 2026"), command=acts["new2026"]["cmd"]).pack(side="left", padx=8)
        ttk.Button(btns, text=_("Abrir…"), command=app.open_file).pack(side="left")

        cont = card(row, padx=22, pady=20, bg=c["surface"])
        cont.pack(side="left", fill="y", padx=(18, 0))
        cont.configure(width=layout.px(300))
        label(cont, _("Continuar donde quedó"), 10, "bold", fg=c["muted"]).pack(anchor="w")
        name, pct, cmd = _continue_info(app)
        ring = tk.Canvas(cont, width=96, height=96, bg=c["surface"], highlightthickness=0)
        ring.pack(anchor="w", pady=10)
        ring.create_oval(8, 8, 88, 88, outline=c["border"], width=9)
        if pct is not None:
            ring.create_arc(8, 8, 88, 88, start=90, extent=-359.9 * pct, style="arc", outline=c["accent"], width=9)
        ring.create_text(48, 48, text=f"{(pct or 0) * 100:.0f}%" if pct is not None else "—", fill=c["text"],
                         font=font(14, "bold"))
        label(cont, name or _("No hay declaraciones abiertas"), 10, "bold", wraplength=250).pack(anchor="w")
        if app.ret and app.result:
            tot = app.result["summary"]["total_balance"]
            label(cont, (_("Reembolso estimado") if tot >= 0 else _("Estimado a pagar")), 9, fg=c["muted"]).pack(anchor="w", pady=(8, 0))
            label(cont, f"${abs(tot):,.0f}", 20, "bold", fg=c["refund"] if tot >= 0 else c["owe"]).pack(anchor="w")
        if cmd:
            ttk.Button(cont, text=_("Continuar"), style="Accent.TButton", command=cmd).pack(fill="x", pady=(10, 0))

        tiles = tk.Frame(main, bg=c["bg"])
        tiles.pack(fill="x", pady=18)
        for i, k in enumerate(("ai", "explorer", "calc")):
            _tile(tiles, acts[k], horizontal=True, title_size=11, padx=16, pady=16, wrap=200).grid(
                row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 14, 0))
            tiles.columnconfigure(i, weight=1, uniform="b")

        dates = card(main, padx=22, pady=18)
        dates.pack(fill="x")
        label(dates, _("Fechas clave"), 10, "bold", fg=c["muted"]).pack(anchor="w", pady=(0, 10))
        grid = tk.Frame(dates, bg=c["card"])
        grid.pack(fill="x")
        today = date.today()
        colors = [c["warn"], c["accent"], c["border"]]
        for i, (d, txt, _m) in enumerate(key_dates()[:3]):
            col = tk.Frame(grid, bg=c["card"])
            col.grid(row=0, column=i, sticky="nsew", padx=(0, 12))
            grid.columnconfigure(i, weight=1, uniform="d")
            tk.Frame(col, bg=colors[i], width=3).pack(side="left", fill="y")
            inner = tk.Frame(col, bg=c["card"], padx=12)
            inner.pack(side="left", fill="both")
            label(inner, fmt_date(d) + (tr(" · faltan {n} días", n=(d - today).days) if i == 0 else ""), 11, "bold").pack(anchor="w")
            label(inner, txt, 9, fg=c["muted"], wraplength=230).pack(anchor="w")


# ============================================================================ Opcion C
class HomeC(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C("bg"))
        self.app = app
        c = COLORS
        acts = _actions(app)
        head = tk.Frame(self, bg=c["header"], padx=36, pady=12)
        head.pack(fill="x")
        tk.Label(head, text=icon("check"), font=icon_font(13), bg=c["accent"], fg=c["on_accent"], width=3, pady=6).pack(side="left")
        tk.Label(head, text="DeclaraFácil", font=font(15, "bold"), bg=c["header"], fg=c["header_fg"]).pack(side="left", padx=(10, 0))
        tk.Label(head, text=" USA", font=font(15, "bold"), bg=c["header"], fg=c["primary"]).pack(side="left")
        user_chip(head, app, fg=c["header_fg"], bg=c["header"]).pack(side="right", padx=(14, 0))
        lang_toggle(head, app).pack(side="right", padx=(14, 0))
        for k in ("settings", "guide", "explorer", "mine"):
            a = acts[k]
            lk = tk.Label(head, text=a["title"], font=font(10, "bold"), bg=c["header"], fg=c["header_muted"], padx=10, cursor="hand2")
            lk.pack(side="right")
            lk.bind("<Button-1>", lambda e, f=a["cmd"]: f())
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

        body = tk.Frame(self, bg=c["bg"], pady=34)
        body.pack(fill="both", expand=True)
        center = tk.Frame(body, bg=c["bg"])
        center.pack()
        h = tk.Frame(center, bg=c["bg"])
        h.pack()
        label(h, _("Hagamos sus impuestos,"), 26, "bold").pack(side="left")
        label(h, " " + _("paso a paso."), 26, "bold", fg=c["primary"]).pack(side="left")
        label(center, _("Le preguntamos lo necesario, calculamos todo y la IA le explica cada detalle."), 12,
              fg=c["muted"]).pack(pady=(8, 24))

        years = tk.Frame(center, bg=c["bg"])
        years.pack(fill="x")
        for i, y in enumerate((2025, 2026)):
            a = acts[f"new{y}"]
            primary = i == 0
            f = tk.Frame(years, bg=c["card"], padx=24, pady=20, highlightthickness=2,
                         highlightbackground=c["accent"] if primary else c["border"])
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 20, 0))
            years.columnconfigure(i, weight=1, uniform="y")
            top = tk.Frame(f, bg=c["card"])
            top.pack(fill="x")
            label(top, str(y), 30, "bold", fg=c["primary"] if primary else c["text"]).pack(side="left")
            label(top, year_status(y).upper(), 8, "bold", fg=c["tint_fg"], bg=c["tint"], padx=10, pady=3).pack(side="right", anchor="n")
            label(f, tr("Declaración del año {y}", y=y), 13, "bold").pack(anchor="w", pady=(10, 2))
            label(f, tr("Se presenta en {z}.", z=y + 1) + " " + (
                _("Incluye propinas, horas extra y la nueva deducción para mayores de 65.") if y == 2025 else
                _("Prepárela con tiempo o planifique sus retenciones.")), 10, fg=c["muted"], wraplength=360).pack(anchor="w")
            btn = ttk.Button(f, text=tr("Empezar {y}", y=y) + "  ›", style="Accent.TButton" if primary else "Soft.TButton",
                             command=a["cmd"])
            btn.pack(fill="x", pady=(14, 0))
            if not a.get("enabled", True):
                btn.state(["disabled"])
                Tooltip(btn, a.get("tip") or "")

        if acts["ai"]["enabled"]:
            bar = tk.Frame(center, bg=c["input"], highlightthickness=1, highlightbackground=c["input_border"],
                           highlightcolor=c["accent"], padx=14, pady=8)
            bar.pack(fill="x", pady=(22, 0))
            tk.Label(bar, text=icon("ai"), font=icon_font(15), bg=c["input"], fg=c["warn"]).pack(side="left")
            self.q = tk.StringVar()
            ent = tk.Entry(bar, textvariable=self.q, font=font(11), relief="flat", bg=c["input"], fg=c["text"],
                           insertbackground=c["text"], highlightthickness=0)
            ent.pack(side="left", fill="x", expand=True, padx=10, ipady=6)
            hint = _("Pregúntele a la IA… por ejemplo: ¿puedo deducir mis propinas?")
            ent.insert(0, hint)
            ent.configure(fg=c["muted"])

            def focus_in(_e):
                if self.q.get() == hint:
                    ent.delete(0, "end")
                    ent.configure(fg=c["text"])
            ent.bind("<FocusIn>", focus_in)

            def ask(_e=None):
                q = self.q.get().strip()
                if q and q != hint:
                    app.ask_ai(q)
                    self.q.set("")
            ent.bind("<Return>", ask)
            flat_button(bar, _("Preguntar"), ask, kind="chip").pack(side="right")

        chips = tk.Frame(center, bg=c["bg"])
        chips.pack(pady=(18, 0))
        name, pct, cmd = _continue_info(app)
        items = []
        if cmd:
            items.append((("next"), tr("Continuar ({p}%)", p=f"{pct * 100:.0f}") if pct is not None else _("Continuar"), cmd))
        items += [("open", _("Abrir guardada"), app.open_file), ("calc", _("Calculadora rápida"), app.open_quick_calc)]
        if acts["counties"]["enabled"]:
            items.append(("download", _("Actualizar condados"), app.download_counties))
        items += [("logout", _("Cerrar sesión"), app.logout), ("exit", _("Salir"), app.quit_app)]
        for ic, text, cm in items:
            b = flat_button(chips, text, cm, kind="ghost", icon_name=ic, size=10, padx=14, pady=8)
            b.configure(highlightthickness=1, highlightbackground=c["border"])
            b.pack(side="left", padx=4)

        foot = tk.Frame(self, bg=c["bg"], pady=14)
        foot.pack(side="bottom", fill="x")
        label(foot, _("Federal · 50 estados + DC · condados y ciudades") + "      " + _("Sus datos se quedan en su PC")
              + "      " + tr("Versión {v}", v=__version__), 9, fg=c["muted"], anchor="center").pack()


HOMES = {"A": HomeA, "B": HomeB, "C": HomeC}


def build_home(app):
    return HOMES.get(theme.current(), HomeA)(app)


# ============================================================================ Mis declaraciones
class ReturnsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(_("Mis declaraciones"))
        layout.fit_window(self, 860, 520)
        self.configure(bg=C("card"))
        top = tk.Frame(self, bg=C("card"), padx=16, pady=12)
        top.pack(fill="x")
        label(top, _("Mis declaraciones"), 15, "bold").pack(side="left")
        ttk.Button(top, text=_("Abrir carpeta"), command=lambda: app._open_folder(storage.returns_dir())).pack(side="right")
        ttk.Button(top, text=_("Abrir"), style="Accent.TButton", command=self.open_sel).pack(side="right", padx=8)
        self.items = accounts.list_returns(app.user)
        show_owner = app.can("view_all")
        cols = ("n", "o", "m") if show_owner else ("n", "m")
        heads = (_("Archivo"), _("Usuario"), _("Modificado")) if show_owner else (_("Archivo"), _("Modificado"))
        widths = (420, 140, 180) if show_owner else (520, 200)
        body = tk.Frame(self, bg=C("card"), padx=16)
        body.pack(fill="both", expand=True, pady=(0, 16))
        self.tree = make_tree(body, cols, heads, widths=widths, height=16)
        self.tree.frame.pack(fill="both", expand=True)
        for i, it in enumerate(self.items):
            vals = [it["name"]] + ([it["owner"]] if show_owner else []) + [it["modified"].strftime("%Y-%m-%d %H:%M")]
            self.tree.insert("", "end", iid=str(i), values=vals)
        if not self.items:
            label(body, _("(ninguna todavía)"), 10, fg=C("muted")).pack(anchor="w", pady=6)
        self.tree.bind("<Double-1>", lambda e: self.open_sel())

    def open_sel(self):
        sel = self.tree.selection()
        if sel:
            path = self.items[int(sel[0])]["path"]
            self.destroy()
            self.app.open_file(path)
