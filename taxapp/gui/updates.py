"""Aviso y descarga de actualizaciones / Update notice and download dialog.

kind = "code": solo se descargan los archivos que cambiaron y la app se reinicia (segundos).
kind = "installer": cambio el programa base; se descarga e instala el instalador completo en silencio.
"""
from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from .. import APP_NAME, __version__, accounts, updater
from ..i18n import _, tr
from .theme import icon, icon_font
from .ui import C, label
from .widgets import COLORS, font


class UpdateDialog(tk.Toplevel):
    def __init__(self, app, upd, kind="installer"):
        super().__init__(app)
        self.app, self.upd, self.kind = app, upd, kind
        c = COLORS
        self.title(_("Actualización disponible"))
        self.configure(bg=c["card"])
        self.transient(app)
        self.geometry("620x560")
        self.minsize(520, 440)
        body = tk.Frame(self, bg=c["card"], padx=24, pady=20)
        body.pack(fill="both", expand=True)
        top = tk.Frame(body, bg=c["card"])
        top.pack(fill="x")
        tk.Label(top, text=icon("download"), font=icon_font(18), bg=c["tint"], fg=c["tint_fg"], width=3, pady=8).pack(side="left")
        t = tk.Frame(top, bg=c["card"])
        t.pack(side="left", padx=14)
        label(t, tr("Versión {v} disponible", v=upd.version), 16, "bold").pack(anchor="w")
        label(t, tr("Usted tiene la versión {c}", c=__version__) + (f" · {upd.published}" if upd.published else ""),
              10, fg=c["muted"]).pack(anchor="w")

        label(body, _("Novedades"), 11, "bold").pack(anchor="w", pady=(18, 6))
        box = tk.Frame(body, bg=c["border"], padx=1, pady=1)
        box.pack(fill="both", expand=True)
        txt = tk.Text(box, wrap="word", relief="flat", height=10, font=font(10), padx=12, pady=10,
                      background=c["bg"], foreground=c["text"], highlightthickness=0, borderwidth=0)
        txt.pack(fill="both", expand=True)
        txt.insert("end", updater.notes_text(upd) or _("(sin notas)"))
        txt.configure(state="disabled")

        self.installed = updater.is_installed_app()
        if not self.installed:
            note = _("Está usando el código fuente (no el programa instalado): descargue la versión nueva desde GitHub.")
        elif kind == "code":
            note = tr("Se descargarán solo los {n} archivos que cambiaron. La aplicación se reiniciará en segundos; "
                      "sus declaraciones, usuarios y configuración se conservan.", n=len(upd.changed))
        else:
            note = _("Esta versión cambia el programa base y necesita el instalador completo. Sus declaraciones, "
                     "usuarios y configuración se conservan. La aplicación se cerrará, se actualizará y se abrirá sola.")
        label(body, note, 9, fg=c["muted"], wraplength=560).pack(anchor="w", pady=(10, 0))
        self.prog = ttk.Progressbar(body, mode="determinate", maximum=100)
        self.status = label(body, "", 9, fg=c["muted"])

        bar = tk.Frame(body, bg=c["card"])
        bar.pack(fill="x", pady=(14, 0))
        if self.installed:
            self.go = ttk.Button(bar, text=_("Actualizar ahora"), style="Accent.TButton", command=self.start)
        else:
            self.go = ttk.Button(bar, text=_("Descargar desde GitHub"), style="Accent.TButton",
                                 command=lambda: webbrowser.open(upd.page_url))
        self.go.pack(side="right")
        self.later = ttk.Button(bar, text=_("Más tarde"), command=self.destroy)
        self.later.pack(side="right", padx=8)
        self.skip = ttk.Button(bar, text=_("Omitir esta versión"), command=self.skip_version)
        self.skip.pack(side="left")
        lk = label(bar, _("Ver en GitHub"), 9, fg=c["info"], cursor="hand2")
        lk.pack(side="left", padx=12)
        lk.bind("<Button-1>", lambda e: webbrowser.open(upd.page_url))

    def skip_version(self):
        cfg = updater.load_config()
        cfg.skipped = self.upd.version
        try:
            updater.save_config(cfg)
        except OSError:
            pass
        self.destroy()

    def start(self):
        if not self.app.can("updates"):
            messagebox.showwarning(APP_NAME, _("Solo el administrador puede instalar actualizaciones."), parent=self)
            return
        for b in (self.go, self.later, self.skip):
            b.state(["disabled"])
        self.prog.pack(fill="x", pady=(12, 0))
        self.status.pack(anchor="w", pady=(4, 0))
        self.status.configure(text=_("Descargando…"))

        def progress(got, total):
            pct = got * 100 / total if total else 0
            self.app.after(0, lambda: self._progress(pct, got, total))

        def work():
            try:
                if self.kind == "code":
                    res = updater.apply_code(self.upd, progress=progress)
                else:
                    res = updater.download(self.upd, progress=progress)
                self.app.after(0, lambda: self._ready(res))
            except Exception as e:  # noqa: BLE001
                self.app.after(0, lambda: self._failed(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, pct, got, total):
        try:
            self.prog.configure(value=pct)
            if self.kind == "code":
                self.status.configure(text=tr("Preparando archivos… {a} de {b}", a=got, b=total))
            else:
                self.status.configure(text=tr("Descargando… {a} de {b} MB", a=f"{got / 1e6:.1f}",
                                              b=f"{total / 1e6:.1f}" if total else "?"))
        except tk.TclError:
            pass

    def _failed(self, msg):
        try:
            self.status.configure(text="⚠ " + msg, fg=C("owe"))
            for b in (self.go, self.later, self.skip):
                b.state(["!disabled"])
        except tk.TclError:
            pass

    def _ready(self, res):
        self.status.configure(text=_("Listo. Reiniciando…") if self.kind == "code" else _("Descarga verificada. Instalando…"))
        if not self.app._confirm_discard():
            self._failed(_("Actualización cancelada: guarde o descarte los cambios y vuelva a intentarlo."))
            return
        try:
            if self.kind == "code":
                updater.restart()
            else:
                updater.install(res)
        except Exception as e:  # noqa: BLE001
            self._failed(str(e))
            return
        if self.app.user:
            accounts.log("update_installed", self.app.user["username"], self.upd.version)
        self.app.dirty = False
        self.app.destroy()
