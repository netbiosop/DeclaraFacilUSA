"""Ventana principal / Main window: inicio de sesion, menu principal (3 estilos), espacio de trabajo, configuracion,
herramientas y cambio de idioma ES/EN. Cada usuario tiene rol, permisos, carpeta y preferencias de apariencia."""
from __future__ import annotations

import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from .. import APP_NAME, __version__, accounts, data_loader, storage, counties, reports, i18n
from ..engine import compute_all
from ..i18n import _, N_, tr
from ..models import TaxReturn
from ..review import review
from . import theme
from .widgets import Form
from .workspace import Workspace, SECTIONS

__all__ = ["App", "SECTIONS", "main"]


def other_language() -> str:
    return "en" if i18n.get_language() == "es" else "es"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        i18n.load_saved_language()
        self.title(APP_NAME)
        ico = data_loader.app_dir() / "assets" / "DeclaraFacilUSA.ico"
        if sys.platform.startswith("win") and ico.exists():
            try:
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass
        self.geometry("1320x840")
        self.minsize(1120, 700)
        theme.register_fonts()
        self.user = None
        self.prefs = dict(accounts.DEFAULT_PREFS)
        self.ret: TaxReturn | None = None
        self.path: Path | None = None
        self.dirty = False
        self.result = None
        self.readonly = False
        self._after = None
        self.view = "login"
        self.view_frame = None
        self.workspace = None
        self.assistant_win = None
        self.settings_section = "appearance"
        self.settings_return = "home"
        self._last_activity = time.time()
        self._last_save = time.time()
        self._apply_login_style()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind_all("<Control-s>", lambda e: self.save() if self.user else None)
        self.bind_all("<Control-o>", lambda e: self.open_file() if self.user else None)
        self.bind_all("<Control-n>", lambda e: self.new_return(2025) if self.user else None)
        self.bind_all("<Control-i>", lambda e: self.open_assistant() if self.user else None)
        for ev in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self.bind_all(ev, self._activity, add="+")
        self.after(30_000, self._tick)
        self._show_start()
        self.after(5000, self._startup_update_checks)

    # ================================================================ permisos y sesion
    def can(self, perm: str) -> bool:
        return accounts.can(self.user, perm)

    def _apply_login_style(self):
        s = accounts.settings()
        p = dict(accounts.DEFAULT_PREFS)
        if s.get("force_style") and s.get("global_prefs"):
            p.update(s["global_prefs"])
        self.prefs = p
        theme.apply(self, p)
        Form.ai_hook = None

    def _show_start(self):
        self._show_view("setup" if not accounts.has_users() else "login")

    def login_ok(self, user):
        self.user = dict(user)
        storage.current_user = user["username"]
        self.readonly = not self.can("edit")
        self.prefs = accounts.prefs_for(user["username"])
        if self.prefs.get("language") in i18n.LANGS:
            i18n.set_language(self.prefs["language"])
        theme.apply(self, self.prefs)
        Form.ai_hook = self.ask_ai_field if self.can("use_ai") else None
        self._last_activity = time.time()
        self._rebuild("home")
        db = accounts.find(accounts.load(), user["username"]) or {}
        if db.get("must_change"):
            from .login import ChangePasswordDialog
            ChangePasswordDialog(self, self.user, forced=True)
        elif self.can("updates"):
            self.after(2000, self.check_updates_background)

    def logout(self, reason="logout"):
        if self.user and not self._confirm_discard():
            return
        if self.user:
            accounts.log(reason, self.user["username"])
        self.user = None
        storage.current_user = ""
        self.ret, self.path, self.result, self.dirty = None, None, None, False
        self.workspace = None
        self._apply_login_style()
        self._rebuild("login")

    # ================================================================ vistas
    def _destroy_views(self):
        for w in list(self.winfo_children()):
            if isinstance(w, tk.Toplevel):
                w.destroy()
        if self.view_frame is not None:
            self.view_frame.destroy()
            self.view_frame = None
        if self.workspace is not None:
            self.workspace.destroy()
            self.workspace = None
        self.assistant_win = None

    def _show_view(self, view, **kw):
        """Muestra una vista: setup | login | home | settings | workspace."""
        if self.view_frame is not None:
            self.view_frame.destroy()
            self.view_frame = None
        if self.workspace is not None:
            self.workspace.pack_forget()
        self.view = view
        if view in ("setup", "login"):
            from .login import LoginView
            self.config(menu="")
            self.view_frame = LoginView(self, "setup" if view == "setup" else "login")
        elif view == "home":
            from .home import build_home
            self.view_frame = build_home(self)
        elif view == "settings":
            from .settings import SettingsView
            self.view_frame = SettingsView(self, kw.get("section", self.settings_section))
        elif view == "workspace":
            if self.workspace is None:
                self.workspace = Workspace(self)
            self.workspace.pack(fill="both", expand=True)
            self.recalc_now()
            self.workspace.show(kw.get("section") or self.workspace.current or "personal")
            return
        self.view_frame.pack(fill="both", expand=True)

    def _rebuild(self, view=None, **kw):
        """Reconstruye toda la interfaz (cambio de idioma, tema, usuario) conservando la declaracion abierta."""
        view = view or self.view
        section = self.workspace.current if self.workspace else None
        visited = set(self.workspace.visited) if self.workspace else set()
        self._destroy_views()
        if self.user:
            self._build_menu()
        if self.ret:
            self.recalc_now()
        if view == "workspace" and self.ret and self.user:
            self.workspace = Workspace(self)
            self.workspace.visited = visited
            self._show_view("workspace", section=kw.get("section") or section)
        else:
            self._show_view(view if self.user or view in ("login", "setup") else "login", **kw)

    def show_home(self):
        if self.user:
            self._show_view("home")

    def show_workspace(self, section="personal"):
        self._show_view("workspace", section=section)

    def show_settings(self, section=None):
        if not self.user:
            return
        if self.view in ("home", "workspace"):
            self.settings_return = self.view
        self.settings_section = section or self.settings_section
        self._show_view("settings", section=self.settings_section)

    def back_from_settings(self):
        if self.settings_return == "workspace" and self.ret:
            self.show_workspace(self.workspace.current if self.workspace else "personal")
        else:
            self.show_home()

    def update_prefs(self, rebuild=True, **kw):
        """Guarda preferencias del usuario (y las globales si el administrador impuso su estilo) y redibuja."""
        if not self.user:
            return
        accounts.save_prefs(self.user["username"], **kw)
        s = accounts.settings()
        if s.get("force_style") and self.can("global_style"):
            merged = accounts.prefs_for(self.user["username"])
            merged.update(kw)
            accounts.set_global_style(self.user["username"], True, merged)
        self.prefs = accounts.prefs_for(self.user["username"])
        if rebuild:
            theme.apply(self, self.prefs)
            if self.view == "settings":
                self._rebuild("settings", section=self.settings_section)
            else:
                self._rebuild()

    def section_name(self) -> str:
        if self.view == "workspace" and self.workspace and self.workspace.current:
            return _(dict(SECTIONS)[self.workspace.current])
        return _("Menú principal")

    # ================================================================ idioma
    def set_language(self, lang: str):
        if lang == i18n.get_language():
            return
        i18n.set_language(lang)
        if self.user:
            accounts.save_prefs(self.user["username"], language=lang)
            self.prefs["language"] = lang
        self._rebuild(section=self.settings_section)

    def toggle_language(self):
        self.set_language(other_language())

    # ================================================================ menus
    def _build_menu(self):
        m = tk.Menu(self)
        a = tk.Menu(m, tearoff=False)
        if self.can("edit"):
            a.add_command(label=_("Nueva declaración 2025"), command=lambda: self.new_return(2025), accelerator="Ctrl+N")
            a.add_command(label=_("Nueva declaración 2026"), command=lambda: self.new_return(2026))
        a.add_command(label=_("Abrir…"), command=self.open_file, accelerator="Ctrl+O")
        a.add_command(label=_("Mis declaraciones"), command=self.open_returns)
        if self.can("edit"):
            a.add_command(label=_("Guardar"), command=self.save, accelerator="Ctrl+S")
            a.add_command(label=_("Guardar como…"), command=self.save_as)
        if self.can("export"):
            a.add_separator()
            a.add_command(label=_("Formularios oficiales del IRS…"), command=lambda: self._goto("forms"))
            a.add_command(label=_("Exportar borrador PDF…"), command=self.export_pdf)
            a.add_command(label=_("Exportar HTML (imprimible)…"), command=self.export_html)
        a.add_separator()
        a.add_command(label=_("Menú principal"), command=self.show_home)
        a.add_command(label=_("Cerrar sesión"), command=self.logout)
        a.add_command(label=_("Salir"), command=self.quit_app)
        m.add_cascade(label=_("Archivo"), menu=a)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label=_("Explorar impuestos por estado y condado"), command=self.open_explorer)
        h.add_command(label=_("Calculadora rápida"), command=self.open_quick_calc)
        h.add_command(label=_("Revisar declaración"), command=lambda: self._goto("review"))
        if self.can("use_ai"):
            h.add_separator()
            h.add_command(label=_("Asistente de IA…"), command=self.open_assistant, accelerator="Ctrl+I")
        if self.can("ai_settings"):
            h.add_command(label=_("Configurar IA (proveedor y clave)…"), command=self.open_ai_settings)
        h.add_separator()
        h.add_command(label=_("Configuración"), command=self.show_settings)
        if self.can("tax_tables"):
            h.add_command(label=_("Actualizar lista de condados (Censo)"), command=self.download_counties)
            h.add_command(label=_("Importar lista de condados desde archivo…"), command=self.import_counties)
            h.add_command(label=_("Abrir carpeta de datos (tasas JSON)"), command=lambda: self._open_folder(data_loader.data_dir()))
        h.add_command(label=_("Abrir carpeta de mis declaraciones"), command=lambda: self._open_folder(storage.returns_dir()))
        m.add_cascade(label=_("Herramientas"), menu=h)
        lg = tk.Menu(m, tearoff=False)
        self._lang_var = tk.StringVar(value=i18n.get_language())
        for code, name in i18n.LANGS.items():
            lg.add_radiobutton(label=name, value=code, variable=self._lang_var, command=lambda c=code: self.set_language(c))
        m.add_cascade(label="Idioma / Language", menu=lg)
        y = tk.Menu(m, tearoff=False)
        y.add_command(label=_("Guía de impuestos"), command=self.open_guide)
        y.add_command(label=_("IRS.gov en español"), command=lambda: webbrowser.open(_("https://www.irs.gov/es")))
        y.add_command(label=_("Acerca de"), command=self.about)
        m.add_cascade(label=_("Ayuda"), menu=y)
        self.config(menu=m)

    def _goto(self, key):
        if not self.ret:
            messagebox.showinfo(APP_NAME, _("Primero cree o abra una declaración."))
            return
        self.show_workspace(key)

    def _deny(self, msg=None):
        messagebox.showwarning(APP_NAME, msg or _("Su rol no tiene permiso para esta acción."))

    # ================================================================ archivo
    def _confirm_discard(self) -> bool:
        if self.ret and self.dirty and not self.readonly:
            ans = messagebox.askyesnocancel(APP_NAME, _("Hay cambios sin guardar. ¿Desea guardarlos?"))
            if ans is None:
                return False
            if ans:
                return self.save()
        return True

    def _filetypes(self):
        return [(_("Declaración DeclaraFacil"), "*.dfusa")]

    def new_return(self, year: int):
        if not self.can("edit"):
            return self._deny(_("Su rol no permite crear declaraciones."))
        if not self._confirm_discard():
            return
        self.ret = TaxReturn(tax_year=year)
        self.path = None
        self.dirty = False
        self.readonly = False
        if self.workspace:
            self.workspace.reset()
        self.show_workspace("personal")

    def continue_return(self):
        if self.ret:
            self.show_workspace(self.workspace.current if self.workspace and self.workspace.current else "personal")

    def open_returns(self):
        from .home import ReturnsWindow
        ReturnsWindow(self)

    def open_file(self, path=None):
        if not self.can("view_own"):
            return self._deny()
        if not self._confirm_discard():
            return
        if not path:
            init = accounts.returns_root() if self.can("view_all") else storage.returns_dir()
            path = filedialog.askopenfilename(title=_("Abrir declaración"), initialdir=str(init),
                                              filetypes=self._filetypes() + [("JSON", "*.json"), (_("Todos"), "*.*")])
        if not path:
            return
        if not accounts.can_access_path(self.user, path):
            return self._deny(_("Solo puede abrir declaraciones de su propia carpeta."))
        try:
            self.ret = storage.load(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, tr("No se pudo abrir el archivo:\n{e}", e=e))
            return
        if self.ret.tax_year not in data_loader.SUPPORTED_YEARS:
            messagebox.showwarning(APP_NAME, tr("El año {y} no está soportado; se usará 2025.", y=self.ret.tax_year))
            self.ret.tax_year = 2025
        self.path = Path(path)
        self.dirty = False
        self.readonly = not self.can("edit")
        accounts.log("return_opened", self.user["username"], self.path.name)
        if self.workspace:
            self.workspace.destroy()
            self.workspace = None
        self.show_workspace("summary")

    def save(self) -> bool:
        if not self.ret:
            return False
        if self.readonly or not self.can("edit"):
            self._deny(_("Su rol no permite guardar cambios."))
            return False
        if not self.path:
            return self.save_as()
        storage.save(self.ret, self.path)
        self._saved()
        return True

    def save_as(self) -> bool:
        if not self.ret or self.readonly:
            return False
        p = filedialog.asksaveasfilename(title=_("Guardar declaración"), defaultextension=storage.EXT,
                                         initialdir=str(storage.returns_dir()),
                                         initialfile=storage.default_filename(self.ret), filetypes=self._filetypes())
        if not p:
            return False
        if not accounts.can_access_path(self.user, p):
            self._deny(_("Solo puede guardar en su propia carpeta."))
            return False
        self.path = storage.save(self.ret, p)
        self._saved()
        return True

    def _saved(self):
        self.dirty = False
        self._last_save = time.time()
        accounts.log("return_saved", self.user["username"], self.path.name)
        if self.workspace:
            self.workspace.status.configure(text=tr("Guardado: {p}", p=self.path))

    def quit_app(self):
        if self._confirm_discard():
            if self.user:
                accounts.log("logout", self.user["username"])
            self.destroy()

    # ================================================================ calculo
    def mark_changed(self):
        if self.readonly:
            return
        self.dirty = True
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(300, self.recalc_now)

    def recalc_now(self):
        self._after = None
        if not self.ret:
            return
        try:
            self.result = compute_all(self.ret)
        except Exception as e:  # noqa: BLE001 - mostrar sin cerrar la app
            if self.workspace:
                self.workspace.status.configure(text=tr("Error de cálculo: {e}", e=e))
            return
        ws = self.workspace
        if not ws:
            return
        ws.update_meter(self.result)
        cur = ws.current
        if cur and cur in ws.screens:
            ws.screens[cur].on_result(self.result)
        ws.refresh_nav()
        ws.status.configure(text=(_("Solo lectura") if self.readonly else
                                  _("Cambios sin guardar") if self.dirty else _("Todo guardado"))
                            + (f"  •  {self.path.name}" if self.path else ""))

    def findings(self):
        if not self.result:
            self.recalc_now()
        return review(self.ret, self.result)

    # ================================================================ inactividad y autoguardado
    def _activity(self, _e=None):
        self._last_activity = time.time()

    def reset_idle_timer(self):
        self._last_activity = time.time()

    def _tick(self):
        try:
            if self.user:
                idle = int(accounts.settings().get("idle_minutes", 0) or 0)
                if idle and time.time() - self._last_activity > idle * 60:
                    if self.ret and self.dirty and self.path and not self.readonly:
                        storage.save(self.ret, self.path)
                        self.dirty = False
                    if not self.dirty:
                        self.logout("idle_logout")
                auto = int(self.prefs.get("autosave", 0) or 0)
                if auto and self.ret and self.dirty and self.path and not self.readonly \
                        and time.time() - self._last_save > auto * 60:
                    self.save()
        finally:
            try:
                self.after(30_000, self._tick)
            except tk.TclError:
                pass

    # ================================================================ exportar
    def _export(self, kind):
        if not self.ret:
            messagebox.showinfo(APP_NAME, _("Primero cree o abra una declaración."))
            return
        if not self.can("export"):
            return self._deny(_("Su rol no permite exportar."))
        self.recalc_now()
        fnd = self.findings()
        errs = [f for f in fnd if f["severity"] == "error"]
        if errs and not messagebox.askyesno(APP_NAME, tr("La revisión encontró {n} error(es). ¿Exportar de todos modos?", n=len(errs))):
            self.show_workspace("review")
            return
        base = Path(storage.default_filename(self.ret)).stem
        if kind == "pdf" and not reports.reportlab_available():
            if messagebox.askyesno(APP_NAME, _("Para PDF instale 'reportlab' (pip install reportlab).\n"
                                               "¿Exportar como HTML imprimible en su lugar?")):
                kind = "html"
            else:
                return
        ext = ".pdf" if kind == "pdf" else ".html"
        p = filedialog.asksaveasfilename(title=_("Exportar borrador"), defaultextension=ext, initialdir=str(storage.returns_dir()),
                                         initialfile=f"{base}_{_('borrador')}{ext}", filetypes=[(ext.upper()[1:], f"*{ext}")])
        if not p:
            return
        try:
            if kind == "pdf":
                reports.to_pdf(self.ret, self.result, fnd, p)
            else:
                Path(p).write_text(reports.to_html(self.ret, self.result, fnd), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, tr("No se pudo exportar:\n{e}", e=e))
            return
        accounts.log("return_exported", self.user["username"], Path(p).name)
        if messagebox.askyesno(APP_NAME, tr("Borrador exportado:\n{p}\n\n¿Abrirlo ahora?", p=p)):
            self._open_path(p)

    def export_pdf(self):
        self._export("pdf")

    def export_html(self):
        self._export("html")

    # ================================================================ utilidades
    def _open_path(self, p):
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            else:
                webbrowser.open(Path(p).resolve().as_uri())
        except Exception:  # noqa: BLE001
            pass

    def _open_folder(self, p):
        self._open_path(str(p))

    def download_counties(self):
        if not self.can("tax_tables"):
            return self._deny()
        if not messagebox.askyesno(APP_NAME, _("Se descargará la lista oficial de condados del Censo de EE.UU. "
                                               "(census.gov, ~250 KB). ¿Continuar?")):
            return
        self.config(cursor="watch")

        def work():
            try:
                n = counties.download_from_census()
                msg = (True, tr("Lista de condados actualizada: {n} estados y territorios.", n=n))
            except Exception as e:  # noqa: BLE001
                msg = (False, tr("{e}\n\nPuede escribir el condado manualmente o importar el archivo "
                                 "national_county2020.txt desde Herramientas.", e=e))
            self.after(0, lambda: self._download_done(*msg))
        threading.Thread(target=work, daemon=True).start()

    def _download_done(self, ok, msg):
        self.config(cursor="")
        (messagebox.showinfo if ok else messagebox.showwarning)(APP_NAME, msg)
        if ok and self.workspace and "address" in self.workspace.screens:
            self.workspace.screens["address"].on_show()

    def import_counties(self):
        if not self.can("tax_tables"):
            return self._deny()
        p = filedialog.askopenfilename(title=_("Archivo del Censo (national_county2020.txt)"),
                                       filetypes=[(_("Texto"), "*.txt *.csv"), (_("Todos"), "*.*")])
        if p:
            try:
                n = counties.import_file(p)
                messagebox.showinfo(APP_NAME, tr("Importados condados de {n} estados.", n=n))
            except Exception as e:  # noqa: BLE001
                messagebox.showerror(APP_NAME, str(e))

    def about(self):
        messagebox.showinfo(APP_NAME, f"{APP_NAME} v{__version__}\n\n" + _(
            "Preparador y estimador de impuestos federales, estatales y locales de EE.UU. (años fiscales 2025 y 2026).\n\n"
            "No es asesoría fiscal ni un servicio de presentación electrónica autorizado por el IRS. "
            "Verifique sus resultados con los formularios oficiales."))

    def open_explorer(self):
        from .tools import ExplorerWindow
        ExplorerWindow(self)

    def open_quick_calc(self):
        from .tools import QuickCalcWindow
        QuickCalcWindow(self)

    def open_guide(self):
        from .tools import GuideWindow
        GuideWindow(self)

    # ================================================================ actualizaciones
    def check_updates_background(self):
        """Al iniciar sesion (administrador): busca en GitHub sin bloquear la ventana."""
        from .. import updater
        cfg = updater.load_config()
        if not cfg.auto_check or not self.user:
            return

        def work():
            try:
                found = updater.check_any(cfg)
            except Exception:  # noqa: BLE001 - sin conexion: no molestar al usuario
                return
            if found and found[1].version != cfg.skipped:
                self.after(0, lambda: self._offer_update(*found))
        threading.Thread(target=work, daemon=True).start()

    def check_updates_now(self, on_done=None):
        """Busqueda manual (Configuracion > Actualizaciones). on_done(texto, hay_actualizacion)."""
        from .. import updater

        def work():
            try:
                found = updater.check_any()
                if found:
                    msg = (tr("Versión {v} disponible.", v=found[1].version), True)
                    self.after(0, lambda: self._offer_update(*found))
                else:
                    msg = (tr("Ya tiene la versión más reciente ({v}).", v=__version__), False)
            except Exception as e:  # noqa: BLE001
                msg = (str(e), False)
            if on_done:
                self.after(0, lambda: on_done(*msg))
        threading.Thread(target=work, daemon=True).start()

    def _offer_update(self, kind, upd):
        if not self.user or not self.can("updates"):
            return
        from .updates import UpdateDialog
        UpdateDialog(self, upd, kind)

    def _startup_update_checks(self):
        """Confirma que el codigo actual arranco bien y avisa si se volvio a una version anterior."""
        from .. import updater
        updater.confirm_code_ok()
        bad = updater.rolled_back_version()
        if bad:
            messagebox.showwarning(APP_NAME, tr("La versión {v} no pudo iniciar correctamente; se volvió a la versión "
                                                "anterior.", v=bad))

    # ================================================================ asistente de IA
    def _dock(self):
        ws = self.workspace
        if ws and ws.dock and self.view == "workspace":
            return ws.dock
        return None

    def open_assistant(self):
        if not self.can("use_ai"):
            return self._deny(_("Su rol no incluye el asistente de IA."))
        dock = self._dock()
        if dock:
            dock.entry.focus_set()
            return dock
        from .assistant import AssistantWindow
        w = self.assistant_win
        try:
            alive = bool(w and w.winfo_exists())
        except tk.TclError:
            alive = False
        if not alive:
            self.assistant_win = w = AssistantWindow(self)
        else:
            w.deiconify()
        w.lift()
        w.focus_force()
        return w

    def open_ai_settings(self):
        if not self.can("ai_settings"):
            return self._deny(_("Solo el administrador puede cambiar el proveedor y las claves de IA."))
        w = self.open_assistant()
        if w:
            w.open_settings()

    def ask_ai(self, question: str):
        if not self.can("use_ai"):
            return
        g = self.grab_current()
        if g is not None:          # un dialogo modal (p. ej. W-2) bloquearia la ventana del asistente
            g.grab_release()
        w = self.open_assistant()
        if w:
            w.ask(question)

    def ask_ai_action(self, n: int):
        w = self.open_assistant()
        if w:
            w.quick(n)

    def ask_ai_field(self, label: str, help_text: str = "", widget=None):
        from .. import assistant as ai
        sec = self.section_name() if self.view == "workspace" else ""
        self.ask_ai(ai.field_question(label.rstrip(" :"), help_text, sec))


def main():
    app = App()
    app.mainloop()
