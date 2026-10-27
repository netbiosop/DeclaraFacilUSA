"""Configuracion / Settings: apariencia, idioma, funciones, IA, cuenta y, para administradores, usuarios y permisos,
ajustes generales y seguridad, tablas de impuestos, respaldos y registro de actividad."""
from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import ttk, messagebox, filedialog, colorchooser

from .. import APP_NAME, accounts, data_loader, i18n
from ..accounts import ROLES, ROLE_LABELS, ROLE_HELP, PERMS
from ..i18n import _, N_, tr, reverse
from . import theme
from .theme import THEMES, ACCENTS, SIZES, icon, icon_font
from .ui import C, label, card, IconButton, user_chip
from .widgets import COLORS, font, ScrollFrame, make_tree, Tooltip
from . import layout

SECTIONS = [  # clave, titulo, icono, permiso necesario (None = todos)
    ("appearance", N_("Apariencia"), "palette", None),
    ("language", N_("Idioma"), "globe", None),
    ("features", N_("Funciones"), "settings", None),
    ("ai", N_("Asistente de IA"), "ai", "use_ai"),
    ("account", N_("Mi cuenta y contraseña"), "user", None),
    ("users", N_("Usuarios y permisos"), "users", "manage_users"),
    ("general", N_("Ajustes generales y seguridad"), "shield", "manage_users"),
    ("tables", N_("Tablas de impuestos"), "table", "tax_tables"),
    ("backups", N_("Respaldos y registro"), "history", "backups"),
    ("updates", N_("Actualizaciones"), "refresh", "updates"),
]
ADMIN_SECTIONS = {"users", "general", "tables", "backups", "updates"}


class SettingsView(tk.Frame):
    def __init__(self, app, section="appearance"):
        super().__init__(app, bg=C("bg"))
        self.app = app
        c = COLORS
        head = tk.Frame(self, bg=c["header"], padx=20, pady=12)
        head.pack(fill="x")
        IconButton(head, "back", app.back_from_settings, tip=_("Volver"), bg=c["header"], fg=c["header_fg"]).pack(side="left")
        tk.Label(head, text=_("Configuración"), font=font(16, "bold"), bg=c["header"], fg=c["header_fg"]).pack(side="left", padx=14)
        user_chip(head, app, fg=c["header_fg"], bg=c["header"]).pack(side="right")
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

        body = tk.Frame(self, bg=c["bg"])
        body.pack(fill="both", expand=True)
        nav = tk.Frame(body, bg=c["sidebar"], width=layout.px(280), padx=14, pady=16)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Frame(body, bg=c["border"], width=1).pack(side="left", fill="y")
        allowed = [s for s in SECTIONS if s[3] is None or app.can(s[3])]
        if section not in [s[0] for s in allowed]:
            section = "appearance"
        self.section = section
        label(nav, _("PERSONAL"), 8, "bold", fg=c["sidebar_muted"]).pack(anchor="w", padx=10, pady=(0, 6))
        admin_header = False
        for key, title, ic, _perm in allowed:
            if key in ADMIN_SECTIONS and not admin_header:
                label(nav, icon("lock") + "  " + _("ADMINISTRACIÓN"), 8, "bold", fg=c["sidebar_muted"]).pack(
                    anchor="w", padx=10, pady=(18, 6))
                admin_header = True
            on = key == section
            bg = c["sidebar_sel"] if on else c["sidebar"]
            fg = c["sidebar_sel_fg"] if on else c["sidebar_fg"]
            r = tk.Frame(nav, bg=bg, padx=10, pady=8, cursor="hand2")
            r.pack(fill="x", pady=1)
            a = tk.Label(r, text=icon(ic), font=icon_font(11), bg=bg, fg=fg)
            a.pack(side="left")
            b = tk.Label(r, text=_(title), font=font(10, "bold" if on else "normal"), bg=bg, fg=fg)
            b.pack(side="left", padx=10)
            for w in (r, a, b):
                w.bind("<Button-1>", lambda e, k=key: app.show_settings(k))

        sf = ScrollFrame(body, bg=c["bg"])
        sf.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(sf.inner, bg=c["bg"], padx=32, pady=24)
        self.inner.pack(fill="both", expand=True)
        getattr(self, "build_" + section)(self.inner)

    # ------------------------------------------------------------------ utilidades
    def h1(self, parent, text, sub=None):
        label(parent, text, 18, "bold").pack(anchor="w")
        if sub:
            label(parent, sub, 10, fg=C("muted"), wraplength=760).pack(anchor="w", pady=(4, 0))
        tk.Frame(parent, bg=C("bg"), height=16).pack()

    def h2(self, parent, text):
        label(parent, text, 11, "bold").pack(anchor="w", pady=(18, 8))

    def prefs(self):
        return self.app.prefs

    # ------------------------------------------------------------------ apariencia
    def build_appearance(self, p):
        c = COLORS
        app = self.app
        st = accounts.settings()
        forced = st.get("force_style") and not app.can("global_style")
        self.h1(p, _("Apariencia"), _("Los cambios se ven al instante. Cada usuario puede tener su propio estilo."))
        if forced:
            note = tk.Frame(p, bg=c["surface"], padx=14, pady=10)
            note.pack(fill="x", pady=(0, 10))
            label(note, icon("lock") + "  " + _("El administrador fijó un mismo estilo para todos los usuarios."), 10,
                  bg=c["surface"]).pack(anchor="w")
        pr = self.prefs()

        self.h2(p, _("Tema"))
        row = tk.Frame(p, bg=c["bg"])
        row.pack(fill="x")
        for i, (key, t) in enumerate(THEMES.items()):
            sel = pr.get("theme") == key
            f = tk.Frame(row, bg=c["card"], padx=10, pady=10, highlightthickness=3 if sel else 1,
                         highlightbackground=c["accent"] if sel else c["border"], cursor="hand2")
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 14, 0))
            row.columnconfigure(i, weight=1, uniform="th")
            self._mini(f, key)
            label(f, _(t["name"]), 11, "bold").pack(anchor="w", pady=(8, 0))
            label(f, _(t["desc"]), 9, fg=c["muted"]).pack(anchor="w")
            if not forced:
                for w in [f] + list(f.winfo_children()):
                    w.bind("<Button-1>", lambda e, k=key: app.update_prefs(theme=k, accent="", meter="", ai_docked=None))

        self.h2(p, _("Color principal"))
        sw = tk.Frame(p, bg=c["bg"])
        sw.pack(anchor="w")
        cur = (pr.get("accent") or THEMES[pr.get("theme", "A")]["accent"]).upper()
        for name, hx in ACCENTS:
            on = hx.upper() == cur
            b = tk.Label(sw, text=icon("check") if on else " ", font=icon_font(10), width=3, pady=6, bg=hx,
                         fg="#FFFFFF" if theme.luminance(hx) < 0.4 else "#0B111D", cursor="hand2",
                         highlightthickness=3 if on else 1, highlightbackground=c["text"] if on else c["border"])
            b.pack(side="left", padx=(0, 8))
            Tooltip(b, _(name))
            if not forced:
                b.bind("<Button-1>", lambda e, h=hx: app.update_prefs(accent=h))
        if not forced:
            ttk.Button(sw, text=_("Otro…"), command=self._pick_color).pack(side="left", padx=(4, 0))

        self.h2(p, _("Tamaño de letra"))
        seg = tk.Frame(p, bg=c["surface"], padx=3, pady=3)
        seg.pack(anchor="w")
        for key, (name, scale) in SIZES.items():
            on = pr.get("size", "normal") == key
            b = tk.Label(seg, text=_(name), font=(font(10)[0], round(10 * scale), "bold" if on else "normal"),
                         bg=c["card"] if on else c["surface"], fg=c["text"] if on else c["muted"], padx=14, pady=6,
                         cursor="hand2")
            b.pack(side="left")
            if not forced:
                b.bind("<Button-1>", lambda e, k=key: app.update_prefs(size=k))

        self.h2(p, _("Tipo de letra"))
        fr = tk.Frame(p, bg=c["bg"])
        fr.pack(anchor="w")
        chosen = pr.get("font", "")
        opts = [("", _("Del tema"))] + [(f, f) for f in theme.available_fonts(self)]
        for i, (fam, name) in enumerate(opts):
            on = chosen == fam
            f = tk.Frame(fr, bg=c["card"], padx=10, pady=6, highlightthickness=2 if on else 1,
                         highlightbackground=c["accent"] if on else c["border"], cursor="hand2")
            f.grid(row=i // 5, column=i % 5, padx=(0, 8), pady=(0, 8), sticky="nsew")
            fam_show = fam or theme.resolve_font(pr.get("theme", "A"), "", self)
            a = tk.Label(f, text="Aa", font=(fam_show, 16, "bold"), bg=c["card"], fg=c["text"])
            a.pack()
            b = tk.Label(f, text=name, font=font(8), bg=c["card"], fg=c["muted"])
            b.pack()
            if not forced:
                for w in (f, a, b):
                    w.bind("<Button-1>", lambda e, x=fam: app.update_prefs(font=x))
        missing = [f for f in theme.GOOGLE_FONTS if f not in theme.families(self)]
        if missing:
            r = tk.Frame(p, bg=c["bg"])
            r.pack(anchor="w", pady=(4, 0))
            ttk.Button(r, text=_("Descargar fuentes modernas (Google Fonts)"), command=self._download_fonts).pack(side="left")
            label(r, ", ".join(missing) + " · " + _("gratis, licencia OFL"), 9, fg=C("muted")).pack(side="left", padx=10)

        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(fill="x", pady=(26, 0))
        if app.can("global_style"):
            self.force = tk.BooleanVar(value=bool(st.get("force_style")))
            cb = tk.Checkbutton(bar, text=_("Usar este estilo para todos los usuarios"), variable=self.force,
                                command=self._toggle_force, bg=c["bg"], fg=c["text"], selectcolor=c["input"],
                                activebackground=c["bg"], activeforeground=c["text"], font=font(10, "bold"))
            cb.pack(side="left")
        if not forced:
            ttk.Button(bar, text=_("Restablecer"), command=lambda: app.update_prefs(
                theme="A", accent="", font="", size="normal", meter="", ai_docked=None)).pack(side="right")

    def _mini(self, f, key):
        """Miniatura del tema."""
        p = theme.palette(key)
        box = tk.Frame(f, bg=p["bg"], height=96, highlightthickness=1, highlightbackground=p["border"])
        box.pack(fill="x")
        box.pack_propagate(False)
        if key == "C":
            tk.Frame(box, bg=p["header"], height=14).pack(fill="x")
            inner = tk.Frame(box, bg=p["bg"])
            inner.pack(fill="both", expand=True)
            tk.Frame(inner, bg=p["card"], width=48).pack(side="right", fill="y")
            col = tk.Frame(inner, bg=p["bg"], padx=8, pady=8)
            col.pack(side="left", fill="both", expand=True)
            tk.Frame(col, bg=p["accent"], height=8, width=90).pack(anchor="w")
            for _i in range(2):
                tk.Frame(col, bg=p["card"], height=12, highlightthickness=1, highlightbackground=p["border"]).pack(fill="x", pady=(5, 0))
        else:
            tk.Frame(box, bg=p["sidebar"], width=36).pack(side="left", fill="y")
            col = tk.Frame(box, bg=p["bg"], padx=8, pady=8)
            col.pack(side="left", fill="both", expand=True)
            tk.Frame(col, bg=p["accent"], height=18, width=100).pack(anchor="w")
            r = tk.Frame(col, bg=p["bg"])
            r.pack(fill="x", pady=(6, 0))
            tk.Frame(r, bg=p["card"], height=34, highlightthickness=1, highlightbackground=p["border"]).pack(side="left", fill="x", expand=True)
            tk.Frame(r, bg=p["card" if key == "A" else "surface"], height=34, width=40, highlightthickness=1,
                     highlightbackground=p["border"]).pack(side="left", padx=(5, 0))

    def _pick_color(self):
        res = colorchooser.askcolor(color=COLORS["accent"], parent=self, title=_("Color principal"))
        if res and res[1]:
            self.app.update_prefs(accent=res[1].upper())

    def _toggle_force(self):
        accounts.set_global_style(self.app.user["username"], self.force.get(), self.prefs())
        messagebox.showinfo(APP_NAME, _("Todos los usuarios verán este estilo al iniciar sesión.") if self.force.get()
                            else _("Cada usuario vuelve a usar su propio estilo."), parent=self)

    def _download_fonts(self):
        self.app.config(cursor="watch")

        def work():
            try:
                n = theme.download_fonts()
                msg = (True, tr("Fuentes instaladas para DeclaraFácil: {n} archivos.", n=n))
            except Exception as e:  # noqa: BLE001
                msg = (False, tr("No se pudieron descargar las fuentes: {e}", e=e))
            self.app.after(0, lambda: self._fonts_done(*msg))
        threading.Thread(target=work, daemon=True).start()

    def _fonts_done(self, ok, msg):
        self.app.config(cursor="")
        (messagebox.showinfo if ok else messagebox.showwarning)(APP_NAME, msg)
        if ok:
            self.app.show_settings("appearance")

    # ------------------------------------------------------------------ idioma
    def build_language(self, p):
        self.h1(p, _("Idioma"), _("Toda la aplicación, los cálculos, la revisión y los borradores PDF/HTML cambian de idioma."))
        for code, name in i18n.LANGS.items():
            on = code == i18n.get_language()
            t = card(p, padx=18, pady=14, bg=C("tint") if on else C("card"))
            t.pack(fill="x", pady=(0, 10))
            t.configure(highlightbackground=C("accent") if on else C("border"), cursor="hand2")
            a = label(t, name, 13, "bold", bg=t["bg"])
            a.pack(side="left")
            if on:
                tk.Label(t, text=icon("check"), fg=C("tint_fg"), bg=t["bg"], font=icon_font(12)).pack(side="right")
            for w in (t, a):
                w.bind("<Button-1>", lambda e, cd=code: self.app.set_language(cd))

    # ------------------------------------------------------------------ funciones
    def build_features(self, p):
        c = COLORS
        pr = self.prefs()
        th = THEMES[theme.current()]
        self.h1(p, _("Funciones"), _("Elija qué se muestra mientras prepara una declaración."))
        self.h2(p, _("Resultado en vivo"))
        meter = pr.get("meter") or th["meter"]
        self.meter = tk.StringVar(value=meter)
        for val, text in (("header", _("Arriba, en el encabezado")), ("panel", _("Panel a la derecha")),
                          ("off", _("No mostrar"))):
            ttk.Radiobutton(p, text=text, value=val, variable=self.meter, style="Bg.TRadiobutton",
                            command=lambda: self.app.update_prefs(meter=self.meter.get())).pack(anchor="w", pady=2)
        self.h2(p, _("Asistente de IA"))
        docked = pr.get("ai_docked")
        if docked is None:
            docked = th["ai_docked"]
        self.docked = tk.BooleanVar(value=bool(docked))
        cb = ttk.Checkbutton(p, text=_("Panel del asistente siempre abierto a la derecha"), variable=self.docked,
                             style="Bg.TCheckbutton", command=lambda: self.app.update_prefs(ai_docked=bool(self.docked.get())))
        cb.pack(anchor="w")
        if not self.app.can("use_ai"):
            cb.state(["disabled"])
        self.h2(p, _("Guardado automático"))
        r = tk.Frame(p, bg=c["bg"])
        r.pack(anchor="w")
        self.autosave = tk.StringVar(value=str(pr.get("autosave", 5)))
        ttk.Spinbox(r, from_=0, to=60, width=5, textvariable=self.autosave).pack(side="left")
        label(r, _("minutos (0 = desactivado). Solo guarda declaraciones que ya tienen nombre de archivo."), 10,
              fg=c["muted"]).pack(side="left", padx=10)
        ttk.Button(p, text=_("Guardar"), style="Accent.TButton", command=self._save_features).pack(anchor="w", pady=(16, 0))

    def _save_features(self):
        try:
            n = max(0, min(60, int(self.autosave.get())))
        except ValueError:
            n = 5
        self.app.update_prefs(autosave=n, rebuild=False)
        messagebox.showinfo(APP_NAME, _("Guardado."), parent=self)

    # ------------------------------------------------------------------ IA
    def build_ai(self, p):
        from .. import assistant as ai
        c = COLORS
        self.h1(p, _("Asistente de IA"), _("El asistente explica campos, revisa su declaración y busca respuestas. "
                                          "Los datos personales nunca se envían."))
        cfg = ai.load_config()
        k = card(p)
        k.pack(fill="x")
        if cfg.is_ready():
            label(k, tr("Proveedor: {p}", p=_(ai.PROVIDERS[cfg.provider]["label"])), 12, "bold").pack(anchor="w")
            label(k, tr("Modelo: {m}", m=cfg.effective_model()), 10, fg=c["muted"]).pack(anchor="w")
        else:
            label(k, _("Sin configurar"), 12, "bold", fg=c["warn"]).pack(anchor="w")
        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(anchor="w", pady=14)
        if self.app.can("ai_settings"):
            ttk.Button(bar, text=_("Configurar proveedor y clave…"), style="Accent.TButton",
                       command=self._ai_settings).pack(side="left")
        else:
            label(bar, _("Solo el administrador puede cambiar el proveedor y las claves de IA."), 10, fg=c["muted"]).pack(side="left")
        ttk.Button(bar, text=_("Abrir el asistente"), command=self.app.open_assistant).pack(side="left", padx=8)

    def _ai_settings(self):
        from .. import assistant as ai
        from .assistant import AISettingsDialog
        AISettingsDialog(self.app, ai.load_config(), lambda cfg: self.app.show_settings("ai"))

    # ------------------------------------------------------------------ mi cuenta
    def build_account(self, p):
        c = COLORS
        u = self.app.user
        self.h1(p, _("Mi cuenta y contraseña"))
        k = card(p)
        k.pack(fill="x")
        label(k, tr("Usuario: {u}", u=u["username"]), 11, "bold").pack(anchor="w")
        label(k, tr("Rol: {r}", r=_(ROLE_LABELS[u["role"]])) + " — " + _(ROLE_HELP[u["role"]]), 10, fg=c["muted"],
              wraplength=700).pack(anchor="w", pady=(4, 10))
        label(k, _("Nombre para mostrar"), 10, "bold").pack(anchor="w")
        r = tk.Frame(k, bg=c["card"])
        r.pack(anchor="w", pady=(4, 0))
        self.name = tk.StringVar(value=u.get("name", ""))
        ttk.Entry(r, textvariable=self.name, width=34).pack(side="left")
        ttk.Button(r, text=_("Guardar"), command=self._save_name).pack(side="left", padx=8)
        self.h2(p, _("Cambiar contraseña"))
        k2 = card(p)
        k2.pack(fill="x")
        self.pw = {}
        for key, t in (("cur", _("Contraseña actual")), ("new", _("Nueva contraseña")), ("new2", _("Confirmar contraseña"))):
            label(k2, t, 10, "bold").pack(anchor="w")
            v = tk.StringVar()
            ttk.Entry(k2, textvariable=v, show="•", width=34).pack(anchor="w", pady=(3, 10))
            self.pw[key] = v
        self.pw_err = label(k2, "", 9, fg=c["owe"])
        self.pw_err.pack(anchor="w")
        ttk.Button(k2, text=_("Cambiar contraseña"), style="Accent.TButton", command=self._change_pw).pack(anchor="w", pady=(6, 0))

    def _save_name(self):
        try:
            u = accounts.update_user(self.app.user["username"], self.app.user["username"], name=self.name.get())
        except accounts.AccountError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
            return
        self.app.user.update(name=u["name"])
        self.app.show_settings("account")

    def _change_pw(self):
        v = {k: x.get() for k, x in self.pw.items()}
        if v["new"] != v["new2"]:
            self.pw_err.configure(text=_("Las contraseñas no coinciden."))
            return
        try:
            accounts.set_password(self.app.user["username"], v["new"], self.app.user["username"], current=v["cur"])
        except accounts.AccountError as e:
            self.pw_err.configure(text=str(e))
            return
        messagebox.showinfo(APP_NAME, _("Contraseña actualizada."), parent=self)
        self.app.show_settings("account")

    # ------------------------------------------------------------------ usuarios y permisos
    def build_users(self, p):
        c = COLORS
        self.h1(p, _("Usuarios y permisos"), _("Cree cuentas para cada persona y elija su nivel de acceso. Debe quedar "
                                               "al menos un Administrador activo."))
        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="+  " + _("Nuevo usuario"), style="Accent.TButton", command=self._new_user).pack(side="left")
        for text, cmd in ((_("Editar"), self._edit_user), (_("Restablecer contraseña"), self._reset_pw),
                          (_("Activar / desactivar"), self._toggle_user), (_("Desbloquear"), self._unlock_user),
                          (_("Transferir declaraciones"), self._transfer), (_("Eliminar"), self._delete_user)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(6, 0))
        self.utree = make_tree(p, ("n", "u", "r", "l", "s"), (_("Nombre"), _("Usuario"), _("Rol"), _("Último acceso"),
                                                              _("Estado")), widths=(220, 150, 140, 160, 120), height=8)
        self.utree.frame.pack(fill="x")
        self.utree.bind("<Double-1>", lambda e: self._edit_user())
        self._fill_users()

        self.h2(p, _("Qué puede hacer cada rol"))
        db = accounts.load()
        grid = tk.Frame(p, bg=c["card"], padx=16, pady=12, highlightthickness=1, highlightbackground=c["border"])
        grid.pack(fill="x")
        label(grid, _("PERMISO"), 8, "bold", fg=c["muted"]).grid(row=0, column=0, sticky="w")
        for j, r in enumerate(ROLES, 1):
            h = label(grid, _(ROLE_LABELS[r]).upper(), 8, "bold", fg=c["muted"], anchor="center")
            h.grid(row=0, column=j, padx=10)
            Tooltip(h, _(ROLE_HELP[r]))
        self.mvars = {}
        for i, (k, t) in enumerate(PERMS, 1):
            label(grid, _(t), 10).grid(row=i, column=0, sticky="w", pady=3)
            for j, r in enumerate(ROLES, 1):
                v = tk.BooleanVar(value=bool(db["matrix"][r][k]))
                cb = ttk.Checkbutton(grid, variable=v)
                cb.grid(row=i, column=j)
                if r == "admin":
                    cb.state(["disabled"])
                self.mvars[(r, k)] = v
        grid.columnconfigure(0, weight=1)
        ttk.Button(p, text=_("Guardar permisos"), style="Accent.TButton", command=self._save_matrix).pack(anchor="w", pady=12)

    def _fill_users(self):
        t = self.utree
        t.delete(*t.get_children())
        self.users = accounts.load()["users"]
        for u in self.users:
            state = _("Bloqueado") if accounts.is_locked(u) else (_("Activo") if u.get("active", True) else _("Desactivado"))
            last = (u.get("last_login") or "").replace("T", " ")[:16] or _("Nunca")
            t.insert("", "end", iid=u["username"], values=(u.get("name", ""), u["username"], _(ROLE_LABELS[u["role"]]), last, state))

    def _selected(self):
        sel = self.utree.selection()
        if not sel:
            messagebox.showinfo(APP_NAME, _("Seleccione un usuario de la lista."), parent=self)
            return None
        return sel[0]

    def _by(self):
        return self.app.user["username"]

    def _new_user(self):
        UserDialog(self, None, self._after_change)

    def _edit_user(self):
        u = self._selected()
        if u:
            UserDialog(self, accounts.find(accounts.load(), u), self._after_change)

    def _after_change(self):
        self._fill_users()

    def _reset_pw(self):
        u = self._selected()
        if u:
            PasswordResetDialog(self, u, self._after_change)

    def _toggle_user(self):
        u = self._selected()
        if not u:
            return
        cur = accounts.find(accounts.load(), u)
        try:
            accounts.update_user(u, self._by(), active=not cur.get("active", True))
        except accounts.AccountError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
        self._fill_users()

    def _unlock_user(self):
        u = self._selected()
        if u:
            accounts.unlock(u, self._by())
            self._fill_users()

    def _transfer(self):
        u = self._selected()
        if u:
            TransferDialog(self, u, self._after_change)

    def _delete_user(self):
        u = self._selected()
        if not u:
            return
        n = len(list(accounts.returns_dir(u).glob("*.dfusa")))
        msg = tr("¿Eliminar al usuario '{u}'?", u=u)
        if n:
            msg += "\n\n" + tr("Sus {n} declaraciones pasarán a su carpeta ({me}).", n=n, me=self._by())
        if not messagebox.askyesno(APP_NAME, msg, parent=self):
            return
        try:
            accounts.delete_user(u, self._by(), transfer_to=self._by() if n else None)
        except accounts.AccountError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
        self._fill_users()

    def _save_matrix(self):
        m = {r: {k: self.mvars[(r, k)].get() for k, _t in PERMS} for r in ROLES}
        accounts.set_matrix(m, self._by())
        messagebox.showinfo(APP_NAME, _("Permisos guardados. Se aplican la próxima vez que cada usuario inicie sesión."),
                            parent=self)

    # ------------------------------------------------------------------ ajustes generales
    def build_general(self, p):
        c = COLORS
        s = accounts.settings()
        self.h1(p, _("Ajustes generales y seguridad"), _("Se aplican a todos los usuarios de este equipo."))
        k = card(p)
        k.pack(fill="x")
        self.gv = {}
        for key, text, lo, hi in (("max_attempts", _("Intentos fallidos antes de bloquear la cuenta"), 3, 20),
                                  ("lock_minutes", _("Minutos de bloqueo"), 1, 240),
                                  ("min_password", _("Largo mínimo de contraseña"), 6, 64),
                                  ("idle_minutes", _("Cerrar sesión tras minutos sin actividad (0 = nunca)"), 0, 480)):
            r = tk.Frame(k, bg=c["card"])
            r.pack(fill="x", pady=5)
            label(r, text, 10).pack(side="left")
            v = tk.StringVar(value=str(s.get(key)))
            ttk.Spinbox(r, from_=lo, to=hi, width=6, textvariable=v).pack(side="right")
            self.gv[key] = (v, lo, hi)
        self.remember = tk.BooleanVar(value=bool(s.get("remember_user", True)))
        ttk.Checkbutton(k, text=_("Recordar el último usuario en la pantalla de inicio de sesión"),
                        variable=self.remember).pack(anchor="w", pady=(8, 0))
        self.h2(p, _("Formularios del IRS: preparador pagado"))
        label(p, _("Si prepara declaraciones para otras personas a cambio de pago, estos datos se imprimen en la sección "
                   "'Paid Preparer Use Only' del 1040. Déjelos en blanco si cada persona prepara la suya."), 9,
              fg=c["muted"], wraplength=740, justify="left", bg=c["bg"]).pack(anchor="w", pady=(0, 6))
        k2 = card(p)
        k2.pack(fill="x")
        prep = s.get("preparer") or {}
        self.pv = {}
        for key, text, w in (("name", _("Nombre del preparador"), 34), ("ptin", _("PTIN (P + 8 dígitos)"), 14),
                             ("firm", _("Nombre de la empresa"), 34), ("firm_address", _("Dirección de la empresa"), 40),
                             ("firm_phone", _("Teléfono de la empresa"), 18), ("firm_ein", _("EIN de la empresa"), 14)):
            r = tk.Frame(k2, bg=c["card"])
            r.pack(fill="x", pady=4)
            label(r, text, 10).pack(side="left")
            v = tk.StringVar(value=str(prep.get(key, "") or ""))
            ttk.Entry(r, textvariable=v, width=w).pack(side="right")
            self.pv[key] = v
        self.prep_self = tk.BooleanVar(value=bool(prep.get("self_employed")))
        ttk.Checkbutton(k2, text=_("El preparador trabaja por cuenta propia (self-employed)"),
                        variable=self.prep_self).pack(anchor="w", pady=(6, 0))
        self.forms_editable = tk.BooleanVar(value=bool(s.get("forms_editable")))
        ttk.Checkbutton(k2, text=_("Por defecto, dejar editables los campos de los PDF generados"),
                        variable=self.forms_editable).pack(anchor="w", pady=(4, 0))
        ttk.Button(p, text=_("Guardar"), style="Accent.TButton", command=self._save_general).pack(anchor="w", pady=14)
        note = tk.Frame(p, bg=c["surface"], padx=14, pady=12)
        note.pack(fill="x")
        label(note, _("Importante: las cuentas controlan el acceso dentro de la aplicación. Quien tenga acceso a su "
                      "carpeta de Windows puede ver los archivos directamente; proteja su usuario de Windows con contraseña."),
              9, bg=c["surface"], wraplength=740).pack(anchor="w")

    def _save_general(self):
        vals = {}
        for key, (v, lo, hi) in self.gv.items():
            try:
                vals[key] = max(lo, min(hi, int(v.get())))
            except ValueError:
                messagebox.showerror(APP_NAME, _("Valor numérico inválido."), parent=self)
                return
        vals["remember_user"] = bool(self.remember.get())
        prep = {k: v.get().strip() for k, v in self.pv.items()}
        prep["self_employed"] = bool(self.prep_self.get())
        vals["preparer"] = prep
        vals["forms_editable"] = bool(self.forms_editable.get())
        accounts.update_settings(self.app.user["username"], **vals)
        self.app.reset_idle_timer()
        messagebox.showinfo(APP_NAME, _("Guardado."), parent=self)

    # ------------------------------------------------------------------ tablas
    def build_tables(self, p):
        c = COLORS
        app = self.app
        self.h1(p, _("Tablas de impuestos"), _("Las tasas y reglas de cada año están en archivos JSON editables en la "
                                               "carpeta 'data'. Después de editarlos, pulse 'Recargar tablas'."))
        k = card(p)
        k.pack(fill="x")
        for y in data_loader.SUPPORTED_YEARS:
            try:
                src = data_loader.federal(y).get("sources", [])
            except Exception:  # noqa: BLE001
                src = []
            label(k, tr("Año fiscal {y}", y=y), 11, "bold").pack(anchor="w", pady=(4, 2))
            for s in src[:4]:
                label(k, "• " + str(s), 9, fg=c["muted"], wraplength=740).pack(anchor="w")
        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(anchor="w", pady=14)
        ttk.Button(bar, text=_("Abrir carpeta de datos (tasas JSON)"),
                   command=lambda: app._open_folder(data_loader.data_dir())).pack(side="left")
        ttk.Button(bar, text=_("Recargar tablas"), command=self._reload).pack(side="left", padx=8)
        self.h2(p, _("Condados"))
        bar2 = tk.Frame(p, bg=c["bg"])
        bar2.pack(anchor="w")
        ttk.Button(bar2, text=_("Actualizar lista de condados (Censo)"), command=app.download_counties).pack(side="left")
        ttk.Button(bar2, text=_("Importar lista de condados desde archivo…"), command=app.import_counties).pack(side="left", padx=8)

    def _reload(self):
        for fn in (data_loader.federal, data_loader.states, data_loader.local, data_loader.states_info):
            fn.cache_clear()
        if self.app.ret:
            self.app.recalc_now()
        accounts.log("settings_changed", self.app.user["username"], "tables reloaded")
        messagebox.showinfo(APP_NAME, _("Tablas recargadas."), parent=self)

    # ------------------------------------------------------------------ respaldos y registro
    def build_backups(self, p):
        c = COLORS
        self.h1(p, _("Respaldos y registro"), _("Un respaldo guarda declaraciones, usuarios, configuración y registro en un "
                                                "archivo ZIP."))
        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(anchor="w")
        ttk.Button(bar, text=_("Crear respaldo ahora"), style="Accent.TButton", command=self._backup).pack(side="left")
        ttk.Button(bar, text=_("Guardar respaldo en…"), command=lambda: self._backup(ask=True)).pack(side="left", padx=8)
        ttk.Button(bar, text=_("Abrir carpeta de respaldos"),
                   command=lambda: self.app._open_folder(accounts.backups_dir())).pack(side="left")
        self.h2(p, _("Registro de actividad"))
        t = make_tree(p, ("t", "u", "e", "d"), (_("Fecha"), _("Usuario"), _("Evento"), _("Detalle")),
                      widths=(150, 120, 220, 330), height=14)
        t.frame.pack(fill="x")
        for e in accounts.read_log(400):
            t.insert("", "end", values=(e.get("time", "").replace("T", " "), e.get("user", ""),
                                        _(accounts.EVENT_LABELS.get(e.get("event"), e.get("event", ""))), e.get("detail", "")))

    def _backup(self, ask=False):
        name = f"DeclaraFacil_respaldo_{datetime.now():%Y%m%d_%H%M}.zip"
        if ask:
            dest = filedialog.asksaveasfilename(parent=self, defaultextension=".zip", initialfile=name,
                                                filetypes=[("ZIP", "*.zip")])
            if not dest:
                return
        else:
            dest = accounts.backups_dir() / name
        try:
            path = accounts.create_backup(dest, self.app.user["username"])
        except OSError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
            return
        messagebox.showinfo(APP_NAME, tr("Respaldo creado:\n{p}", p=path), parent=self)
        self.app.show_settings("backups")


    # ------------------------------------------------------------------ actualizaciones
    def build_updates(self, p):
        from .. import __version__, updater
        c = COLORS
        cfg = updater.load_config()
        self.h1(p, _("Actualizaciones"), _("La aplicación busca versiones nuevas publicadas en GitHub y se actualiza sola, "
                                           "sin perder declaraciones, usuarios ni configuración."))
        k = card(p)
        k.pack(fill="x")
        label(k, tr("Versión instalada: {v}", v=__version__), 13, "bold").pack(anchor="w")
        if updater.is_installed_app():
            label(k, tr("Programa base: {b} · las mejoras llegan archivo por archivo", b=updater.base_version()), 10,
                  fg=c["muted"]).pack(anchor="w")
        label(k, _("Programa instalado") if updater.is_installed_app() else
              _("Ejecutándose desde el código fuente: las versiones nuevas se descargan desde GitHub."), 10,
              fg=c["muted"], wraplength=740).pack(anchor="w", pady=(2, 0))
        if cfg.last_check:
            label(k, tr("Última búsqueda: {d}", d=cfg.last_check.replace("T", " ")), 9, fg=c["muted"]).pack(anchor="w", pady=(6, 0))
        bar = tk.Frame(p, bg=c["bg"])
        bar.pack(anchor="w", pady=14)
        self.upd_btn = ttk.Button(bar, text=_("Buscar actualizaciones ahora"), style="Accent.TButton", command=self._check_now)
        self.upd_btn.pack(side="left")
        ttk.Button(bar, text=_("Ver publicaciones en GitHub"),
                   command=lambda: webbrowser.open(f"https://github.com/{self.upd_repo.get().strip()}/releases")).pack(side="left", padx=8)
        self.upd_status = label(p, "", 10, fg=c["muted"], wraplength=740)
        self.upd_status.pack(anchor="w")

        self.h2(p, _("Origen de las actualizaciones"))
        k2 = card(p)
        k2.pack(fill="x")
        label(k2, _("Repositorio de GitHub (usuario/repositorio)"), 10, "bold").pack(anchor="w")
        self.upd_repo = tk.StringVar(value=cfg.repo)
        ttk.Entry(k2, textvariable=self.upd_repo, width=44).pack(anchor="w", pady=(3, 10))
        label(k2, _("Clave de acceso (solo si el repositorio es privado)"), 10, "bold").pack(anchor="w")
        self.upd_token = tk.StringVar(value="")
        ttk.Entry(k2, textvariable=self.upd_token, show="•", width=44).pack(anchor="w", pady=(3, 2))
        label(k2, _("Déjela vacía para conservar la actual. Se guarda cifrada con Windows.") if cfg.token else
              _("Use un token de GitHub de solo lectura (Contents: Read) limitado a ese repositorio."), 9,
              fg=c["muted"]).pack(anchor="w", pady=(0, 10))
        self.upd_auto = tk.BooleanVar(value=bool(cfg.auto_check))
        ttk.Checkbutton(k2, text=_("Buscar actualizaciones al iniciar sesión (administradores)"), variable=self.upd_auto).pack(anchor="w")
        ttk.Button(p, text=_("Guardar"), command=self._save_updates).pack(anchor="w", pady=12)

    def _save_updates(self):
        from .. import updater
        cfg = updater.load_config()
        cfg.repo = self.upd_repo.get().strip()
        if self.upd_token.get().strip():
            cfg.set_token(self.upd_token.get())
        cfg.auto_check = bool(self.upd_auto.get())
        cfg.skipped = ""
        try:
            updater.save_config(cfg)
        except OSError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
            return
        accounts.log("settings_changed", self.app.user["username"], "updates")
        messagebox.showinfo(APP_NAME, _("Guardado."), parent=self)

    def _check_now(self):
        self.upd_btn.state(["disabled"])
        self.upd_status.configure(text=_("Buscando…"), fg=C("muted"))

        def done(msg, found):
            try:
                self.upd_btn.state(["!disabled"])
                self.upd_status.configure(text=msg, fg=C("refund") if found else C("muted"))
            except tk.TclError:
                pass
        self.app.check_updates_now(done)


# ============================================================================ dialogos de usuarios
class _Modal(tk.Toplevel):
    def __init__(self, view, title):
        super().__init__(view.app)
        self.view = view
        self.title(title)
        self.configure(bg=C("card"))
        self.transient(view.app)
        self.resizable(False, False)
        self.body = tk.Frame(self, bg=C("card"), padx=24, pady=20)
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda e: self.destroy())

    def finish(self):
        bar = tk.Frame(self.body, bg=C("card"))
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text=_("Guardar"), style="Accent.TButton", command=self.ok).pack(side="right")
        ttk.Button(bar, text=_("Cancelar"), command=self.destroy).pack(side="right", padx=6)
        self.err = label(self.body, "", 9, fg=C("owe"), wraplength=400)
        self.err.pack(anchor="w")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def field(self, text, value="", secret=False, width=36):
        label(self.body, text, 10, "bold").pack(anchor="w")
        v = tk.StringVar(value=value)
        e = ttk.Entry(self.body, textvariable=v, width=width, show="•" if secret else "")
        e.pack(fill="x", pady=(3, 10))
        return v, e


class UserDialog(_Modal):
    def __init__(self, view, user, on_done):
        super().__init__(view, _("Editar usuario") if user else _("Nuevo usuario"))
        self.user, self.on_done = user, on_done
        self.name, _e = self.field(_("Nombre"), (user or {}).get("name", ""))
        if user:
            label(self.body, tr("Usuario: {u}", u=user["username"]), 10, fg=C("muted")).pack(anchor="w", pady=(0, 10))
        else:
            self.username, _e = self.field(_("Usuario (para iniciar sesión)"))
        label(self.body, _("Rol"), 10, "bold").pack(anchor="w")
        labels = [_(ROLE_LABELS[r]) for r in ROLES]
        self.role = tk.StringVar(value=_(ROLE_LABELS[(user or {}).get("role", "preparer")]))
        cb = ttk.Combobox(self.body, textvariable=self.role, values=labels, state="readonly", width=34)
        cb.pack(fill="x", pady=(3, 4))
        self.help = label(self.body, "", 9, fg=C("muted"), wraplength=400)
        self.help.pack(anchor="w", pady=(0, 10))
        self.role.trace_add("write", lambda *a: self._help())
        self._help()
        if not user:
            self.pw, _e = self.field(_("Contraseña temporal"), secret=True)
            self.pw2, _e = self.field(_("Confirmar contraseña"), secret=True)
            self.must = tk.BooleanVar(value=True)
            ttk.Checkbutton(self.body, text=_("Pedir que la cambie al iniciar sesión"), variable=self.must).pack(anchor="w")
        self.finish()

    def _role_key(self):
        key = reverse(self.role.get(), list(ROLE_LABELS.values()))
        return {v: k for k, v in ROLE_LABELS.items()}.get(key, "preparer")

    def _help(self):
        self.help.configure(text=_(ROLE_HELP[self._role_key()]))

    def ok(self):
        by = self.view.app.user["username"]
        try:
            if self.user:
                accounts.update_user(self.user["username"], by, name=self.name.get(), role=self._role_key())
                if self.user["username"] == by:
                    self.view.app.user.update(name=self.name.get().strip() or by, role=self._role_key())
            else:
                if self.pw.get() != self.pw2.get():
                    self.err.configure(text=_("Las contraseñas no coinciden."))
                    return
                u = accounts.create_user(self.username.get(), self.name.get(), self._role_key(), self.pw.get(), by=by)
                if self.must.get():
                    db = accounts.load()
                    accounts.find(db, u["username"])["must_change"] = True
                    accounts.save(db)
        except accounts.AccountError as e:
            self.err.configure(text=str(e))
            return
        self.destroy()
        self.on_done()


class PasswordResetDialog(_Modal):
    def __init__(self, view, username, on_done):
        super().__init__(view, _("Restablecer contraseña"))
        self.username, self.on_done = username, on_done
        label(self.body, tr("Nueva contraseña temporal para '{u}'.", u=username), 10, wraplength=400).pack(anchor="w", pady=(0, 10))
        self.pw, _e = self.field(_("Contraseña temporal"), secret=True)
        self.pw2, _e = self.field(_("Confirmar contraseña"), secret=True)
        self.must = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.body, text=_("Pedir que la cambie al iniciar sesión"), variable=self.must).pack(anchor="w")
        self.finish()

    def ok(self):
        if self.pw.get() != self.pw2.get():
            self.err.configure(text=_("Las contraseñas no coinciden."))
            return
        try:
            accounts.set_password(self.username, self.pw.get(), self.view.app.user["username"], must_change=self.must.get())
        except accounts.AccountError as e:
            self.err.configure(text=str(e))
            return
        self.destroy()
        messagebox.showinfo(APP_NAME, _("Contraseña restablecida."))
        self.on_done()


class TransferDialog(_Modal):
    def __init__(self, view, username, on_done):
        super().__init__(view, _("Transferir declaraciones"))
        self.username, self.on_done = username, on_done
        n = len(list(accounts.returns_dir(username).glob("*.dfusa")))
        label(self.body, tr("Mover las {n} declaraciones de '{u}' a:", n=n, u=username), 10, wraplength=400).pack(anchor="w")
        others = [u["username"] for u in accounts.load()["users"] if u["username"] != username]
        self.dest = tk.StringVar(value=others[0] if others else "")
        ttk.Combobox(self.body, textvariable=self.dest, values=others, state="readonly", width=34).pack(fill="x", pady=8)
        self.finish()

    def ok(self):
        if not self.dest.get():
            return
        n = accounts.transfer_returns(self.username, self.dest.get(), self.view.app.user["username"])
        self.destroy()
        messagebox.showinfo(APP_NAME, tr("{n} declaraciones transferidas.", n=n))
        self.on_done()
