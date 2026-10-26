"""Inicio de sesion y creacion de la primera cuenta (Administrador) / Login and first-run admin setup."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .. import APP_NAME, __version__, accounts
from ..i18n import _, tr
from .theme import icon, icon_font, mix
from .ui import C, label, lang_toggle
from .widgets import COLORS, font


class LoginView(tk.Frame):
    """mode: 'login' o 'setup' (primera vez, crea el Administrador)."""

    def __init__(self, app, mode="login"):
        super().__init__(app, bg=C("card"))
        self.app = app
        self.mode = mode
        c = COLORS
        left = tk.Frame(self, bg=c["accent"], width=500, padx=48, pady=48)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        on, soft = c["on_accent"], mix(c["on_accent"], c["accent"], 0.22)
        lg = tk.Frame(left, bg=c["accent"])
        lg.pack(anchor="w")
        tk.Label(lg, text=icon("check"), font=icon_font(15), bg=on, fg=c["accent"], width=3, pady=6).pack(side="left")
        tk.Label(lg, text=APP_NAME, font=font(17, "bold"), bg=c["accent"], fg=on).pack(side="left", padx=12)
        tk.Label(left, text=_("Impuestos de EE.UU., sin complicaciones."), font=font(26, "bold"), bg=c["accent"], fg=on,
                 wraplength=400, justify="left").pack(anchor="w", pady=(70, 26))
        for t in (_("Federal, 50 estados + DC, condados y ciudades"), _("Asistente de IA que explica cada campo"),
                  _("Cada usuario con su acceso y sus declaraciones")):
            r = tk.Frame(left, bg=c["accent"])
            r.pack(anchor="w", pady=6)
            tk.Label(r, text=icon("check"), font=icon_font(11), bg=c["accent"], fg=on).pack(side="left")
            tk.Label(r, text=t, font=font(11), bg=c["accent"], fg=soft).pack(side="left", padx=10)
        tk.Label(left, text=_("Sus datos se guardan solo en este equipo."), font=font(9), bg=c["accent"],
                 fg=soft).pack(side="bottom", anchor="w")

        right = tk.Frame(self, bg=c["card"], padx=40, pady=24)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=c["card"])
        top.pack(fill="x")
        lang_toggle(top, app).pack(side="right")
        foot = tk.Frame(right, bg=c["card"])
        foot.pack(side="bottom", fill="x")
        label(foot, tr("Versión {v}", v=__version__), 9, fg=c["muted"]).pack(side="left")
        s = accounts.settings()
        label(foot, tr("Tras {n} intentos fallidos la cuenta se bloquea {m} minutos", n=s["max_attempts"],
                       m=s["lock_minutes"]), 9, fg=c["muted"]).pack(side="right")

        form = tk.Frame(right, bg=c["card"], width=420)
        form.place(relx=0.5, rely=0.5, anchor="center")
        self.vars = {}
        self.entries = {}
        if mode == "setup":
            label(form, _("Bienvenido"), 24, "bold").pack(anchor="w")
            label(form, _("Cree la cuenta de Administrador. Con ella podrá crear otros usuarios y asignarles permisos."),
                  11, fg=c["muted"], wraplength=420).pack(anchor="w", pady=(4, 18))
            self._field(form, "name", _("Su nombre"), "")
            self._field(form, "user", _("Usuario"), "admin")
            self._field(form, "pw", _("Contraseña"), "", secret=True)
            self._field(form, "pw2", _("Confirmar contraseña"), "", secret=True)
            label(form, tr("Mínimo {n} caracteres, con letras y números o símbolos.", n=s["min_password"]), 9,
                  fg=c["muted"]).pack(anchor="w", pady=(0, 6))
            if list(accounts.returns_root().glob("*.dfusa")):
                label(form, _("Sus declaraciones anteriores pasarán a la carpeta de esta cuenta."), 9,
                      fg=c["info"], wraplength=420).pack(anchor="w")
            btn_text = _("Crear cuenta y entrar")
        else:
            label(form, _("Iniciar sesión"), 24, "bold").pack(anchor="w")
            label(form, _("Entre con el usuario que le dio su administrador."), 11, fg=c["muted"]).pack(anchor="w", pady=(4, 18))
            self._field(form, "user", _("Usuario"), s.get("last_user", "") if s.get("remember_user", True) else "")
            self._field(form, "pw", _("Contraseña"), "", secret=True)
            row = tk.Frame(form, bg=c["card"])
            row.pack(fill="x")
            self.remember = tk.BooleanVar(value=bool(s.get("remember_user", True)))
            ttk.Checkbutton(row, text=_("Recordar usuario"), variable=self.remember).pack(side="left")
            self.caps = label(row, "", 9, fg=c["warn"])
            self.caps.pack(side="right")
            btn_text = _("Entrar")
        self.err = label(form, "", 10, fg=c["owe"], wraplength=420)
        self.err.pack(anchor="w", pady=(8, 0))
        self.btn = ttk.Button(form, text=btn_text, style="Accent.TButton", command=self.submit)
        self.btn.pack(fill="x", pady=(8, 0), ipady=4)
        if mode == "login":
            info = tk.Frame(form, bg=c["surface"], padx=14, pady=12)
            info.pack(fill="x", pady=(16, 0))
            tk.Label(info, text=icon("info"), font=icon_font(12), bg=c["surface"], fg=c["info"]).pack(side="left", anchor="n")
            tk.Label(info, text=_("¿Olvidó su contraseña? El administrador puede restablecerla desde Configuración › Usuarios."),
                     font=font(9), bg=c["surface"], fg=c["text"], wraplength=340, justify="left").pack(side="left", padx=10)
        first = self.entries.get("user") if mode == "login" and not self.vars["user"].get() else \
            self.entries.get("pw") if mode == "login" else self.entries.get("name")
        if first:
            self.after(50, first.focus_set)

    def _field(self, parent, key, text, value, secret=False):
        c = COLORS
        label(parent, text, 10, "bold").pack(anchor="w")
        box = tk.Frame(parent, bg=c["input"], highlightthickness=1, highlightbackground=c["input_border"],
                       highlightcolor=c["accent"])
        box.pack(fill="x", pady=(4, 12))
        var = tk.StringVar(value=value)
        ent = tk.Entry(box, textvariable=var, font=font(12), relief="flat", bg=c["input"], fg=c["text"],
                       insertbackground=c["text"], highlightthickness=0, width=34, show="•" if secret else "")
        ent.pack(side="left", fill="x", expand=True, padx=12, ipady=8)
        ent.bind("<Return>", lambda e: self.submit())
        ent.bind("<KeyPress>", self._caps, add="+")
        if secret:
            eye = tk.Label(box, text=_("Mostrar"), font=font(9, "bold"), bg=c["input"],
                           fg=c["muted"], padx=10, cursor="hand2")
            eye.pack(side="right")

            def toggle(_e=None, e=ent, lb=eye):
                hidden = e.cget("show") != ""
                e.configure(show="" if hidden else "•")
                lb.configure(text=_("Ocultar") if hidden else _("Mostrar"))
            eye.bind("<Button-1>", toggle)
        self.vars[key] = var
        self.entries[key] = ent
        return ent

    def _caps(self, e):
        if hasattr(self, "caps"):
            try:
                on = bool(int(e.state) & 0x2)
            except (TypeError, ValueError):
                on = False
            self.caps.configure(text=_("Bloq Mayús activado") if on else "")

    def submit(self):
        v = {k: var.get() for k, var in self.vars.items()}
        self.err.configure(text="")
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            if self.mode == "setup":
                if v["pw"] != v["pw2"]:
                    self.err.configure(text=_("Las contraseñas no coinciden."))
                    return
                try:
                    accounts.create_user(v["user"], v["name"] or _("Administrador"), "admin", v["pw"])
                except accounts.AccountError as e:
                    self.err.configure(text=str(e))
                    return
                user, err = accounts.authenticate(v["user"], v["pw"])
            else:
                accounts.update_settings("", remember_user=bool(self.remember.get()))
                user, err = accounts.authenticate(v["user"], v["pw"])
            if not user:
                self.err.configure(text=err)
                if "pw" in self.entries:
                    self.vars["pw"].set("")
                    self.entries["pw"].focus_set()
                return
        finally:
            try:
                self.configure(cursor="")
            except tk.TclError:
                pass
        self.app.login_ok(user)


class ChangePasswordDialog(tk.Toplevel):
    """Cambio de contrasena (obligatorio si el administrador la restablecio)."""

    def __init__(self, app, user, forced=False, on_done=None):
        super().__init__(app)
        self.app, self.user, self.on_done = app, user, on_done
        c = COLORS
        self.title(_("Cambiar contraseña"))
        self.configure(bg=c["card"])
        self.transient(app)
        self.resizable(False, False)
        f = tk.Frame(self, bg=c["card"], padx=24, pady=20)
        f.pack(fill="both", expand=True)
        if forced:
            label(f, _("El administrador restableció su contraseña. Elija una nueva para continuar."), 10,
                  fg=c["warn"], wraplength=380).pack(anchor="w", pady=(0, 10))
        self.vars = {}
        for k, t in (("cur", _("Contraseña actual")), ("new", _("Nueva contraseña")), ("new2", _("Confirmar contraseña"))):
            label(f, t, 10, "bold").pack(anchor="w")
            var = tk.StringVar()
            ttk.Entry(f, textvariable=var, show="•", width=36).pack(fill="x", pady=(3, 10))
            self.vars[k] = var
        self.err = label(f, "", 9, fg=c["owe"], wraplength=380)
        self.err.pack(anchor="w")
        bar = tk.Frame(f, bg=c["card"])
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text=_("Guardar"), style="Accent.TButton", command=self.ok).pack(side="right")
        if not forced:
            ttk.Button(bar, text=_("Cancelar"), command=self.destroy).pack(side="right", padx=6)
        else:
            self.protocol("WM_DELETE_WINDOW", lambda: None)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def ok(self):
        v = {k: x.get() for k, x in self.vars.items()}
        if v["new"] != v["new2"]:
            self.err.configure(text=_("Las contraseñas no coinciden."))
            return
        try:
            accounts.set_password(self.user["username"], v["new"], self.user["username"], current=v["cur"])
        except accounts.AccountError as e:
            self.err.configure(text=str(e))
            return
        messagebox.showinfo(APP_NAME, _("Contraseña actualizada."), parent=self)
        self.destroy()
        if self.on_done:
            self.on_done()
