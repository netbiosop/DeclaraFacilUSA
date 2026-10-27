"""Formularios oficiales del IRS: preguntas guiadas, borrador y formularios finales / Official IRS forms screen."""
from __future__ import annotations

import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, messagebox

from .. import APP_NAME, accounts, forms, storage
from ..engine import fmt_money
from ..forms import catalog, questions as qmod
from ..i18n import _, N_, tr
from .lists import ListEditor
from .screens import Screen
from .ui import C, label, open_path
from .widgets import COLORS, font, make_tree, money_str, parse_money, ScrollFrame
from . import layout


def preparer_info() -> dict:
    p = accounts.settings().get("preparer") or {}
    return {k: p.get(k, "") for k in accounts.PREPARER_FIELDS}


# ==================================================================================================== pantalla
class FormsScreen(Screen):
    key, title = "forms", N_("Formularios oficiales del IRS")
    subtitle = N_("Con sus respuestas llenamos el Formulario 1040 y todos los anexos que su declaración necesita, en "
                  "los PDF oficiales del IRS. Primero puede generar un borrador para revisarlo; luego los formularios "
                  "finales para firmar y enviar por correo.")

    def build(self):
        p = self.scroll()
        self.p = p
        self.use_sr = tk.BooleanVar(value=True)
        self.editable = tk.BooleanVar(value=bool(accounts.settings().get("forms_editable")))
        # --- estado
        self.status_lbl = ttk.Label(p, text="", style="Big.TLabel", wraplength=860, justify="left")
        self.status_lbl.pack(anchor="w")
        self.status_sub = ttk.Label(p, text="", style="CardMuted.TLabel", wraplength=860, justify="left")
        self.status_sub.pack(anchor="w", pady=(2, 8))
        cols = ttk.Frame(p, style="Card.TFrame")
        cols.pack(fill="both", expand=True)
        left = ttk.Frame(cols, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(cols, style="Card.TFrame", padding=(16, 0, 0, 0))
        right.pack(side="right", fill="y")
        # --- formularios necesarios
        ttk.Label(left, text=_("Formularios que necesita su declaración"), style="Section.TLabel").pack(anchor="w")
        self.tree = make_tree(left, ("f", "t", "l", "n"), (_("Formulario"), _("Descripción"), _("Idioma"), _("Copias")),
                              widths=(120, 380, 80, 60), height=10, anchors=("w", "w", "center", "center"))
        self.tree.frame.pack(fill="both", expand=True, pady=6)
        ttk.Label(left, text=_("Revise antes de firmar"), style="Section.TLabel").pack(anchor="w", pady=(8, 0))
        self.warn_txt = tk.Text(left, height=6, wrap="word", relief="flat", background=COLORS["accent_light"],
                                foreground=COLORS["text"], font=font(9), padx=8, pady=6, borderwidth=0)
        self.warn_txt.pack(fill="x", pady=(4, 0))
        # --- preguntas
        box = tk.Frame(right, bg=C("tint"), padx=14, pady=12)
        box.pack(fill="x")
        label(box, _("Preguntas para los formularios"), 11, "bold", bg=C("tint"), fg=C("tint_fg")).pack(anchor="w")
        self.q_lbl = label(box, "", 10, bg=C("tint"), fg=C("tint_fg"), wraplength=300, justify="left")
        self.q_lbl.pack(anchor="w", pady=(4, 8))
        self.q_btn = ttk.Button(box, text=_("Responder preguntas (guiado)"), style="Accent.TButton",
                                command=lambda: self.open_wizard(only_missing=True))
        self.q_btn.pack(fill="x")
        ttk.Button(box, text=_("Revisar todas las respuestas"), command=lambda: self.open_wizard(only_missing=False)).pack(
            fill="x", pady=(6, 0))
        # --- opciones
        opt = ttk.Frame(right, style="Card.TFrame")
        opt.pack(fill="x", pady=(14, 0))
        ttk.Label(opt, text=_("Opciones"), style="Section.TLabel").pack(anchor="w")
        label(opt, _("Idioma de los formularios"), 10, "bold", bg=C("card")).pack(anchor="w", pady=(2, 0))
        self.lang_var = tk.StringVar(value=forms.forms_language(self.ret))
        self.lang_es = ttk.Radiobutton(opt, text=_("Español (versiones oficiales del IRS donde existen)"),
                                       value="es", variable=self.lang_var, command=self._lang_changed)
        self.lang_es.pack(anchor="w", pady=1)
        ttk.Radiobutton(opt, text=_("Inglés"), value="en", variable=self.lang_var,
                        command=self._lang_changed).pack(anchor="w", pady=1)
        self.lang_note = label(opt, "", 9, fg=C("muted"), bg=C("card"), wraplength=300, justify="left")
        self.lang_note.pack(anchor="w", pady=(0, 6))
        self.sr_cb = ttk.Checkbutton(opt, text=_("Usar el Formulario 1040-SR (letra grande, 65 años o más)"),
                                     variable=self.use_sr, command=self.refresh)
        self.sr_cb.pack(anchor="w", pady=2)
        self.prep_var = tk.BooleanVar(value=self.ret.filing.use_preparer)
        self.prep_cb = ttk.Checkbutton(opt, text="", variable=self.prep_var, command=self._prep_toggle)
        self.prep_cb.pack(anchor="w", pady=2)
        ttk.Checkbutton(opt, text=_("Dejar los campos del PDF editables (para corregir a mano)"),
                        variable=self.editable).pack(anchor="w", pady=2)
        # --- acciones
        act = ttk.Frame(right, style="Card.TFrame")
        act.pack(fill="x", pady=(16, 0))
        self.draft_btn = ttk.Button(act, text=_("Generar borrador (con marca de agua)"), command=lambda: self.generate(True))
        self.draft_btn.pack(fill="x")
        self.final_btn = ttk.Button(act, text=_("Generar formularios finales"), style="Accent.TButton",
                                    command=self.generate_final)
        self.final_btn.pack(fill="x", pady=(8, 0))
        self.last_lbl = label(right, "", 9, fg=C("muted"), wraplength=300, justify="left", bg=C("card"))
        self.last_lbl.pack(anchor="w", pady=(10, 0))
        self.open_last_btn = ttk.Button(right, text=_("Ver últimos formularios generados"), command=self._show_last)
        self.last = None
        if not self.app.can("export"):
            for b in (self.draft_btn, self.final_btn, self.q_btn):
                b.state(["disabled"])

    # ------------------------------------------------------------------ estado
    def on_show(self):
        self.refresh()

    def on_result(self, res):
        self.refresh()

    def _lang_changed(self):
        self.ret.filing.forms_language = self.lang_var.get()
        self.changed()
        self.refresh()

    def _prep_toggle(self):
        self.ret.filing.use_preparer = bool(self.prep_var.get())
        self.changed()

    def _plan(self):
        res = self.app.result
        if not res:
            self.app.recalc_now()
            res = self.app.result
        return forms.plan(self.ret, res, preparer_info(), use_sr=self.use_sr.get(), lang=self.lang_var.get())

    def refresh(self):
        y = self.ret.tax_year
        ok_year = forms.available(y)
        ok_lib = forms.pdf_support()
        for b in (self.draft_btn, self.final_btn):
            b.state(["!disabled"] if ok_year and ok_lib and self.app.can("export") else ["disabled"])
        if not ok_lib:
            self.status_lbl.configure(text=_("Falta el componente para llenar PDF (pypdf)."))
            self.status_sub.configure(text=_("Instale la versión más reciente del programa, o desde el código fuente "
                                             "ejecute: pip install pypdf"))
        elif not ok_year:
            self.status_lbl.configure(text=tr("Los formularios oficiales de {y} aún no están disponibles.", y=y))
            self.status_sub.configure(text=tr("El IRS publica los formularios definitivos de {y} entre diciembre y enero. "
                                              "Llegarán en una actualización; mientras tanto puede preparar y revisar "
                                              "su declaración.", y=y))
        else:
            self.status_lbl.configure(text=tr("Formularios oficiales del IRS {y} listos para llenar", y=y))
            self.status_sub.configure(text=_("Se usan los PDF oficiales publicados por el IRS. Usted firma y envía por "
                                             "correo; la aplicación no envía nada al IRS."))
        res = self.app.result
        if not res:
            return
        tp_age = self.ret.taxpayer_age()
        sp_age = self.ret.spouse_age() if self.ret.is_joint() else None
        sr_ok = (tp_age or 0) >= 65 or (sp_age or 0) >= 65
        self.sr_cb.state(["!disabled"] if sr_ok else ["disabled"])
        prep = preparer_info()
        if prep.get("name"):
            self.prep_cb.configure(text=tr("Incluir preparador pagado: {n}", n=prep["name"]))
            self.prep_cb.pack(anchor="w", pady=2)
            self.prep_var.set(self.ret.filing.use_preparer)
        else:
            self.prep_cb.pack_forget()
        plan = self._plan()
        self.tree.delete(*self.tree.get_children())
        counts = {}
        for inst in plan.instances:
            counts[inst.form] = counts.get(inst.form, 0) + 1
        es = self.lang_var.get() == "es"
        n_es = 0
        for fid in plan.forms():
            in_es = es and ok_year and catalog.has_spanish(y, fid)
            n_es += in_es
            self.tree.insert("", "end", values=(catalog.short(fid) + (" (SP)" if in_es else ""),
                                                catalog.title(y, fid) if ok_year else "",
                                                _("Español") if in_es else _("Inglés"), counts[fid]))
        if plan.statements:
            self.tree.insert("", "end", values=("—", tr("Hojas adicionales: {n}", n=len(plan.statements)), "", ""))
        if not es:
            self.lang_note.configure(text="")
        elif ok_year and not catalog.spanish_available(y):
            self.lang_note.configure(text=_("Las versiones en español aún no están incluidas en esta instalación; "
                                            "por ahora se generan en inglés."))
        else:
            self.lang_note.configure(text=tr("{n} de {t} formularios en español. El IRS solo publica en español el "
                                             "1040, 1040-SR y los Anexos 1, 1-A, 2, 3, 8812, C, EIC y SE; los demás "
                                             "van en inglés y se aceptan juntos.", n=n_es, t=len(plan.forms())))
        allq = qmod.questions(self.ret, res)
        miss = [q for q in allq if q.is_missing(self.ret)]
        req = [q for q in miss if q.required]
        if not miss:
            self.q_lbl.configure(text=tr("{n} preguntas — todas respondidas.", n=len(allq)))
            self.q_btn.configure(text=_("Revisar respuestas"))
        else:
            self.q_lbl.configure(text=tr("{n} preguntas para sus formularios; faltan {m} ({r} obligatorias para los "
                                         "formularios finales).", n=len(allq), m=len(miss), r=len(req)))
            self.q_btn.configure(text=_("Responder preguntas (guiado)"))
        warns = list(plan.warnings)
        for q in req:
            warns.insert(0, tr("Falta: {q}", q=_q(q)))
        self.warn_txt.configure(state="normal")
        self.warn_txt.delete("1.0", "end")
        self.warn_txt.insert("end", "\n".join(f"• {w}" for w in warns) if warns else _("Sin observaciones."))
        self.warn_txt.configure(state="disabled")

    # ------------------------------------------------------------------ acciones
    def open_wizard(self, only_missing=True):
        if self.app.readonly:
            return self.app._deny(_("Su rol no permite modificar la declaración."))
        self.app.recalc_now()
        GuidedQuestions(self.app, only_missing=only_missing, on_close=self.refresh)

    def generate_final(self):
        self.app.recalc_now()
        res = self.app.result
        missing = qmod.missing(self.ret, res, required_only=True)
        if missing:
            lst = "\n".join(f"• {_q(q)}" for q in missing[:12])
            if messagebox.askyesno(APP_NAME, tr("Faltan datos obligatorios para los formularios finales:\n\n{l}\n\n"
                                                "¿Desea responder las preguntas ahora?", l=lst), parent=self.app):
                self.open_wizard(only_missing=True)
            return
        fnd = self.app.findings()
        errs = [f for f in fnd if f["severity"] == "error"]
        if errs and not messagebox.askyesno(APP_NAME, tr("La revisión encontró {n} error(es). ¿Generar de todos modos?",
                                                         n=len(errs)), parent=self.app):
            self.app.workspace.show("review")
            return
        ans = messagebox.askyesnocancel(APP_NAME, _("¿Desea generar primero un BORRADOR para revisarlo antes de llenar "
                                                    "los formularios finales?\n\nSí: borrador con marca de agua.\n"
                                                    "No: formularios finales para firmar."), parent=self.app)
        if ans is None:
            return
        self.generate(draft=bool(ans))

    def generate(self, draft: bool):
        if not self.app.can("export"):
            return self.app._deny(_("Su rol no permite exportar."))
        self.app.recalc_now()
        base = self.app.path.parent if self.app.path else storage.returns_dir()
        folder = forms.default_folder(self.ret, Path(base), draft)
        self.app.config(cursor="watch")
        for b in (self.draft_btn, self.final_btn):
            b.state(["disabled"])
        self.last_lbl.configure(text=_("Generando formularios…"))
        ret, res = self.ret, self.app.result
        prep = preparer_info()
        opts = dict(draft=draft, editable=self.editable.get(), preparer=prep, use_sr=self.use_sr.get(),
                    lang=self.lang_var.get())

        def work():
            try:
                out = forms.generate(ret, res, folder, **opts)
                self.app.after(0, lambda: self._done(out))
            except Exception as e:  # noqa: BLE001
                self.app.after(0, lambda: self._failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _restore(self):
        try:
            self.app.config(cursor="")
        except tk.TclError:
            pass
        self.refresh()

    def _failed(self, e):
        self._restore()
        self.last_lbl.configure(text="")
        if isinstance(e, forms.MissingDependency):
            messagebox.showerror(APP_NAME, _("Falta el componente pypdf para llenar los PDF."), parent=self.app)
        else:
            messagebox.showerror(APP_NAME, tr("No se pudieron generar los formularios:\n{e}", e=e), parent=self.app)

    def _done(self, out):
        self._restore()
        self.last = out
        kind = _("Borrador") if out.draft else _("Formularios finales")
        self.last_lbl.configure(text=tr("{k}: {n} páginas en {f}", k=kind, n=out.pages, f=out.folder))
        self.open_last_btn.pack(anchor="w", pady=(4, 0))
        accounts.log("forms_generated", self.app.user["username"],
                     f"{'draft' if out.draft else 'final'} {self.ret.tax_year} {out.folder.name}")
        PackageDialog(self.app, out, on_final=lambda: self.generate(False))

    def _show_last(self):
        if self.last:
            PackageDialog(self.app, self.last, on_final=lambda: self.generate(False))


def _q(q) -> str:
    return tr(q.text, **q.params) if q.params else _(q.text)


# ==================================================================================================== preguntas
class GuidedQuestions(tk.Toplevel):
    """Una pregunta a la vez; las preguntas dependen de las respuestas (p. ej. depósito directo → número de cuenta)."""

    def __init__(self, app, only_missing=True, on_close=None):
        super().__init__(app)
        self.app = app
        self.on_close = on_close
        self.only_missing = only_missing
        self.title(_("Preguntas para los formularios"))
        self.configure(bg=C("card"))
        self.transient(app)
        layout.fit_window(self, 760, 560, 620, 460)
        res = app.result
        allq = qmod.questions(app.ret, res)
        self.pending = {q.key for q in allq if q.is_missing(app.ret)} if only_missing else {q.key for q in allq}
        self.seen = {q.key for q in allq}
        self.history = []
        self.cur = None
        self.var = None
        # --- encabezado
        top = tk.Frame(self, bg=C("card"), padx=22, pady=14)
        top.pack(fill="x")
        self.step_lbl = label(top, "", 9, "bold", fg=C("muted"))
        self.step_lbl.pack(anchor="w")
        self.group_lbl = label(top, "", 10, "bold", fg=C("primary"))
        self.group_lbl.pack(anchor="w", pady=(2, 0))
        tk.Frame(self, bg=C("border"), height=1).pack(fill="x")
        self.body = tk.Frame(self, bg=C("card"), padx=22, pady=16)
        self.body.pack(fill="both", expand=True)
        tk.Frame(self, bg=C("border"), height=1).pack(fill="x")
        bar = tk.Frame(self, bg=C("card"), padx=22, pady=12)
        bar.pack(fill="x")
        self.back_btn = ttk.Button(bar, text=_("‹ Anterior"), command=self.back)
        self.back_btn.pack(side="left")
        ttk.Button(bar, text=_("Cerrar"), command=self.close).pack(side="left", padx=8)
        self.next_btn = ttk.Button(bar, text=_("Siguiente ›"), style="Accent.TButton", command=self.next)
        self.next_btn.pack(side="right")
        self.skip_btn = ttk.Button(bar, text=_("Omitir"), command=self.skip)
        self.skip_btn.pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", lambda e: self.next() if self.cur and self.cur.kind != "list" else None)
        self.bind("<Escape>", lambda e: self.close())
        self._goto_next(None)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ navegación
    def _questions(self):
        self.app.recalc_now()
        return qmod.questions(self.app.ret, self.app.result)

    def _goto_next(self, after_key):
        qs = self._questions()
        keys = [q.key for q in qs]
        start = keys.index(after_key) + 1 if after_key in keys else 0
        # Preguntas que aparecen por una respuesta (p. ej. número de cuenta) se agregan a las pendientes.
        for q in qs:
            if q.key not in self.seen:
                self.seen.add(q.key)
                if not self.only_missing or q.is_missing(self.app.ret):
                    self.pending.add(q.key)
        for q in qs[start:]:
            if q.key in self.pending:
                return self._show(q, qs)
        self._finish()

    def _show(self, q, qs):
        self.cur = q
        for w in self.body.winfo_children():
            w.destroy()
        todo = [x for x in qs if x.key in self.pending]
        pos = todo.index(q) + 1 if q in todo else 1
        self.step_lbl.configure(text=tr("PREGUNTA {i} DE {n}", i=pos, n=len(todo)))
        self.group_lbl.configure(text=_(q.group))
        self.back_btn.state(["!disabled"] if self.history else ["disabled"])
        label(self.body, _q(q), 13, "bold", wraplength=690, justify="left").pack(anchor="w")
        if q.help:
            label(self.body, _(q.help), 9, fg=C("muted"), wraplength=690, justify="left").pack(anchor="w", pady=(4, 0))
        holder = tk.Frame(self.body, bg=C("card"))
        holder.pack(fill="both", expand=True, pady=(14, 0))
        cur = q.value(self.app.ret)
        self.var = None
        if q.kind == "text":
            self.var = tk.StringVar(value=str(cur or ""))
            e = ttk.Entry(holder, textvariable=self.var, width=q.width, font=font(12))
            e.pack(anchor="w")
            e.focus_set()
            e.icursor("end")
        elif q.kind == "money":
            self.var = tk.StringVar(value=money_str(cur or 0))
            e = ttk.Entry(holder, textvariable=self.var, width=18, justify="right", font=font(12))
            e.pack(anchor="w")
            e.focus_set()
        elif q.kind == "yesno":
            self.var = tk.StringVar(value="1" if cur else "0")
            for v, t in (("1", _("Sí")), ("0", _("No"))):
                ttk.Radiobutton(holder, text=t, value=v, variable=self.var).pack(anchor="w", pady=3)
        elif q.kind == "choice":
            vals = [v for v, _t in q.choices]
            self.var = tk.StringVar(value=cur if cur in vals else "")
            for v, t in q.choices:
                ttk.Radiobutton(holder, text=_(t), value=v, variable=self.var).pack(anchor="w", pady=3)
        elif q.kind == "list":
            ListEditor(holder, self.app, q.list_kind, self.app.mark_changed, height=7).pack(fill="both", expand=True)
        self.err = label(self.body, "", 9, fg=C("owe"), wraplength=690, justify="left")
        self.err.pack(anchor="w", pady=(6, 0))
        last = not any(x.key in self.pending for x in qs[qs.index(q) + 1:])
        self.next_btn.configure(text=_("Terminar") if last else _("Siguiente ›"))

    def _apply(self) -> bool:
        q = self.cur
        if q is None:
            return True
        ret = self.app.ret
        if q.kind == "list":
            if q.list_kind == "sales" and ret.income.sales and (ret.income.short_term_gain or ret.income.long_term_gain):
                if messagebox.askyesno(APP_NAME, _("Ya agregó el detalle de las ventas. ¿Poner en 0 la ganancia neta que "
                                                   "había ingresado sin detalle, para no contarla dos veces?"), parent=self):
                    ret.income.short_term_gain = 0.0
                    ret.income.long_term_gain = 0.0
                    self.app.mark_changed()
            return True
        obj = q.obj(ret)
        raw = self.var.get() if self.var is not None else None
        if q.kind == "text":
            val = (raw or "").strip()
        elif q.kind == "money":
            val = parse_money(raw or "0")
            if val is None:
                self.err.configure(text=_("Escriba un número válido."))
                return False
        elif q.kind == "yesno":
            val = raw == "1"
        else:
            val = raw
        if q.check and q.kind != "list" and not q.check(val) and (val or q.required):
            self.err.configure(text=_("El valor no tiene el formato esperado. Corríjalo o use 'Omitir'."))
            return False
        if getattr(obj, q.attr) != val:
            setattr(obj, q.attr, val)
            self.app.mark_changed()
        return True

    def next(self):
        if not self._apply():
            return
        q = self.cur
        if q and q.key not in self.app.ret.filing.answered:
            self.app.ret.filing.answered.append(q.key)
            self.app.mark_changed()
        self._advance()

    def skip(self):
        self._advance()

    def _advance(self):
        q = self.cur
        if q:
            self.history.append(q.key)
            self.pending.discard(q.key)
        self._goto_next(q.key if q else None)

    def back(self):
        if not self.history:
            return
        key = self.history.pop()
        self.pending.add(key)
        qs = self._questions()
        for q in qs:
            if q.key == key:
                return self._show(q, qs)

    def _finish(self):
        self.cur = None
        for w in self.body.winfo_children():
            w.destroy()
        self.step_lbl.configure(text="")
        self.group_lbl.configure(text="")
        label(self.body, _("¡Listo! Ya respondió las preguntas."), 14, "bold").pack(anchor="w")
        miss = qmod.missing(self.app.ret, self.app.result, required_only=True)
        if miss:
            label(self.body, _("Todavía faltan estos datos obligatorios para los formularios finales:"), 10,
                  fg=C("owe")).pack(anchor="w", pady=(10, 4))
            for q in miss:
                label(self.body, "• " + _q(q), 10, wraplength=690, justify="left").pack(anchor="w")
        else:
            label(self.body, _("Ahora puede generar un borrador para revisarlo o los formularios finales."), 10,
                  fg=C("muted")).pack(anchor="w", pady=(8, 0))
        self.next_btn.configure(text=_("Cerrar"), command=self.close)
        self.skip_btn.pack_forget()
        self.back_btn.state(["disabled"])

    def close(self):
        if self.cur is not None and self.var is not None:
            try:
                self._apply()
            except tk.TclError:
                pass
        self.destroy()
        if self.on_close:
            self.on_close()


# ==================================================================================================== resultado
class PackageDialog(tk.Toplevel):
    """Resultado: archivos generados, dirección de envío y lista de verificación."""

    def __init__(self, app, out, on_final=None):
        super().__init__(app)
        self.app, self.out = app, out
        self.title(_("Borrador generado") if out.draft else _("Formularios listos para firmar"))
        self.configure(bg=C("card"))
        self.transient(app)
        layout.fit_window(self, 820, 640, 680, 520)
        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        b = tk.Frame(sf.inner, bg=C("card"), padx=24, pady=18)
        b.pack(fill="both", expand=True)
        fed = app.result["federal"]["lines"]
        if out.draft:
            label(b, _("Borrador generado"), 16, "bold").pack(anchor="w")
            label(b, _("Revise cada página. El borrador lleva la marca de agua 'BORRADOR - NO PRESENTAR': no lo firme ni lo "
                       "envíe. Cuando todo esté correcto, genere los formularios finales."), 10, fg=C("muted"),
                  wraplength=740, justify="left").pack(anchor="w", pady=(4, 10))
        else:
            label(b, _("Sus formularios están listos para firmar y enviar"), 16, "bold").pack(anchor="w")
            label(b, tr("{n} páginas • {r}", n=out.pages,
                        r=tr("Reembolso {a}", a=fmt_money(fed.get("34", 0))) if fed.get("34", 0) >= 1 else
                        tr("A pagar {a}", a=fmt_money(fed.get("37", 0))) if fed.get("37", 0) >= 1 else _("Saldo $0")),
                  10, fg=C("muted")).pack(anchor="w", pady=(4, 10))
        row = tk.Frame(b, bg=C("card"))
        row.pack(fill="x")
        ttk.Button(row, text=_("Abrir declaración completa"), style="Accent.TButton",
                   command=lambda: open_path(out.package)).pack(side="left")
        ttk.Button(row, text=_("Instrucciones de envío"), command=lambda: open_path(out.instructions)).pack(side="left", padx=6)
        if not out.draft and sys.platform.startswith("win"):
            ttk.Button(row, text=_("Imprimir"), command=self._print).pack(side="left")
        ttk.Button(row, text=_("Abrir carpeta"), command=lambda: open_path(out.folder)).pack(side="left", padx=6)
        if out.draft and on_final:
            ttk.Button(row, text=_("Todo correcto: generar finales"),
                       command=lambda: (self.destroy(), on_final())).pack(side="right")
        if not out.draft:
            label(b, _("Envíe por correo a:"), 11, "bold", fg=C("primary")).pack(anchor="w", pady=(16, 4))
            addr = tk.Frame(b, bg=C("tint"), padx=16, pady=10)
            addr.pack(anchor="w")
            for ln in out.mailing.get("address", []):
                label(addr, ln, 12, "bold", bg=C("tint"), fg=C("tint_fg")).pack(anchor="w")
            lk = label(b, _("Confirmar dirección en IRS.gov"), 9, fg=C("info"), cursor="hand2")
            lk.pack(anchor="w", pady=(4, 0))
            lk.bind("<Button-1>", lambda e: webbrowser.open(out.mailing.get("url")))
            label(b, _("Antes de enviar"), 11, "bold", fg=C("primary")).pack(anchor="w", pady=(16, 4))
            main = "1040-SR" if "1040sr" in out.forms else "1040"
            checks = [tr("Firmar y fechar el Formulario {f}{j}.", f=main,
                         j=_(" (ambos cónyuges)") if app.ret.is_joint() else ""),
                      _("Adjuntar la Copia B de cada W-2 (y 1099-R / W-2G con retención) en la página 1."),
                      _("Mantener las hojas en el orden del archivo completo.")]
            if out.voucher:
                checks.append(tr("Pagar {a}: en IRS.gov/payments o con cheque a \"United States Treasury\" junto con el "
                                 "Formulario 1040-V, sin grapas.", a=fmt_money(fed.get("37", 0))))
            checks.append(_("Enviar por correo certificado y guardar una copia completa."))
            for c in checks:
                ttk.Checkbutton(b, text=c).pack(anchor="w", pady=1)
            if out.voucher:
                ttk.Button(b, text=_("Abrir comprobante de pago 1040-V"), command=lambda: open_path(out.voucher)).pack(
                    anchor="w", pady=(8, 0))
        if out.warnings:
            label(b, _("Revise antes de firmar"), 11, "bold", fg=C("warn")).pack(anchor="w", pady=(16, 4))
            for w in out.warnings:
                label(b, "• " + w, 9, wraplength=740, justify="left").pack(anchor="w", pady=1)
        label(b, _("Archivos generados"), 11, "bold", fg=C("primary")).pack(anchor="w", pady=(16, 4))
        label(b, str(out.folder), 9, fg=C("muted"), wraplength=740, justify="left").pack(anchor="w")
        for f in [out.instructions, out.package] + list(out.files) + ([out.voucher] if out.voucher else []):
            lk = label(b, "▸ " + f.name, 9, fg=C("info"), cursor="hand2")
            lk.pack(anchor="w")
            lk.bind("<Button-1>", lambda e, p=f: open_path(p))
        bar = tk.Frame(self, bg=C("card"), padx=20, pady=10)
        bar.pack(fill="x")
        ttk.Button(bar, text=_("Cerrar"), command=self.destroy).pack(side="right")

    def _print(self):
        if not open_path(self.out.package, "print"):
            messagebox.showinfo(APP_NAME, _("Abra el archivo completo e imprímalo desde su visor de PDF."), parent=self)
