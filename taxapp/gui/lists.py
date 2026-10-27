"""Editores de listas (pagadores, ventas, proveedores de cuidado, estudiantes, otros gastos).

ListEditor muestra una tabla con botones Agregar / Editar / Eliminar; cada fila se edita en un diálogo (Dialog).
Se usa en las pantallas de la entrevista y en las preguntas guiadas de los formularios.
"""
from __future__ import annotations

import copy
from tkinter import ttk, messagebox
from typing import Callable

from ..engine import fmt_money
from ..i18n import _, N_
from ..models import CareProvider, OtherExpense, Payer, Sale, Student
from .widgets import Dialog, make_tree


def _sale_dialog(f):
    f.text(_("Descripción (p. ej. 100 sh. XYZ Co.)"), "description", width=34)
    f.text(_("Fecha de compra (MM/DD/AAAA o VARIOUS)"), "acquired", width=14)
    f.text(_("Fecha de venta (MM/DD/AAAA)"), "sold", width=14)
    f.money(_("Precio de venta (casilla 1d)"), "proceeds")
    f.money(_("Costo o base (casilla 1e)"), "cost")
    f.combo(_("Plazo"), "term", [_("Corto plazo (1 año o menos)"), _("Largo plazo (más de 1 año)")],
            to_model=lambda v: "short" if v == _("Corto plazo (1 año o menos)") else "long",
            from_model=lambda v: _("Corto plazo (1 año o menos)") if v == "short" else _("Largo plazo (más de 1 año)"))
    f.check(_("Recibí un 1099-B (o 1099-DA) por esta venta"), "form_1099")
    f.check(_("El 1099 indica que la base (costo) se informó al IRS"), "basis_reported",
            _("Casilla 12 del 1099-B marcada / 'covered security'."))
    f.check(_("Es un activo digital (criptomoneda, NFT)"), "digital")
    f.section(_("Ajustes (solo si aplica)"))
    f.text(_("Código de ajuste (columna f, p. ej. W)"), "code", width=6)
    f.money(_("Monto del ajuste (columna g)"), "adjustment", _("Ej.: pérdida no permitida por venta ficticia (wash sale, código W)."))


def _payer_dialog(f):
    f.text(_("Nombre del pagador (banco, empresa, fondo)"), "name", width=34)
    f.money(_("Monto"), "amount")


def _provider_dialog(f):
    f.text(_("Nombre del proveedor o guardería"), "name", width=34)
    f.text(_("Dirección completa (calle, ciudad, estado, ZIP)"), "address", width=40)
    f.text(_("SSN o EIN del proveedor"), "tin", width=14, help_text=_("Pídalo con el formulario W-10."))
    f.money(_("Monto pagado en el año"), "amount")
    f.check(_("Era su empleado(a) doméstico(a) (niñera en su casa)"), "household_employee")


def _other_dialog(f):
    f.text(_("Tipo de gasto (p. ej. Licencias, Uniformes)"), "description", width=34)
    f.money(_("Monto"), "amount")


def _student_dialog(f):
    f.text(_("Nombre del estudiante"), "name")
    f.text(_("SSN del estudiante"), "ssn", width=16)
    f.combo(_("Crédito"), "credit", ["AOTC", "LLC"],
            help_text=_("AOTC: primeros 4 años de universidad, al menos medio tiempo. LLC: cualquier curso."))
    f.money(_("Matrícula y gastos calificados (1098-T)"), "expenses")
    f.section(_("Institución educativa (del 1098-T)"))
    f.text(_("Nombre de la institución"), "school", width=34)
    f.text(_("Dirección de la institución"), "school_address", width=40)
    f.text(_("EIN de la institución"), "school_ein", width=14)
    f.check(_("Recibió el formulario 1098-T de esta institución"), "got_1098t")
    f.check(_("Estudió al menos medio tiempo un período del año"), "half_time")
    f.check(_("Aún no había completado 4 años de estudios universitarios al empezar el año"), "first_four_years")


# list_kind: (obtener lista, clase, columnas [(título, función, ancho, alineación)], diálogo, título, alto del diálogo)
SPECS = {
    "interest_payers": (lambda r: r.income.interest_payers, Payer,
                        [(N_("Pagador"), lambda x: x.name, 300, "w"), (N_("Monto"), lambda x: fmt_money(x.amount), 120, "e")],
                        _payer_dialog, N_("Pagador de intereses"), 230),
    "dividend_payers": (lambda r: r.income.dividend_payers, Payer,
                        [(N_("Pagador"), lambda x: x.name, 300, "w"), (N_("Monto"), lambda x: fmt_money(x.amount), 120, "e")],
                        _payer_dialog, N_("Pagador de dividendos"), 230),
    "sales": (lambda r: r.income.sales, Sale,
              [(N_("Descripción"), lambda x: x.description, 170, "w"), (N_("Venta"), lambda x: x.sold, 80, "center"),
               (N_("Precio"), lambda x: fmt_money(x.proceeds), 95, "e"), (N_("Costo"), lambda x: fmt_money(x.cost), 95, "e"),
               (N_("Ganancia"), lambda x: fmt_money(x.gain()), 95, "e"),
               (N_("Plazo"), lambda x: _("Corto") if x.term == "short" else _("Largo"), 60, "center"),
               (N_("Casilla"), lambda x: x.box(), 55, "center")],
              _sale_dialog, N_("Venta de inversión"), 560),
    "care_providers": (lambda r: r.credits.care_providers, CareProvider,
                       [(N_("Proveedor"), lambda x: x.name, 200, "w"), (N_("Dirección"), lambda x: x.address, 220, "w"),
                        (N_("SSN/EIN"), lambda x: x.tin, 100, "center"), (N_("Monto"), lambda x: fmt_money(x.amount), 95, "e")],
                       _provider_dialog, N_("Proveedor de cuidado"), 340),
    "other_expenses": (lambda r: r.income.other_expenses, OtherExpense,
                       [(N_("Tipo de gasto"), lambda x: x.description, 300, "w"),
                        (N_("Monto"), lambda x: fmt_money(x.amount), 120, "e")],
                       _other_dialog, N_("Otro gasto del negocio"), 230),
    "students": (lambda r: r.credits.students, Student,
                 [(N_("Estudiante"), lambda x: x.name, 170, "w"), (N_("Crédito"), lambda x: x.credit, 60, "center"),
                  (N_("Gastos"), lambda x: fmt_money(x.expenses), 95, "e"), (N_("Institución"), lambda x: x.school, 200, "w")],
                 _student_dialog, N_("Estudiante"), 560),
}


class ListEditor(ttk.Frame):
    def __init__(self, parent, app, kind: str, on_change: Callable = None, height=5, factory: Callable = None):
        super().__init__(parent, style="Card.TFrame")
        self.app = app
        self.kind = kind
        self.getlist, self.cls, self.cols, self.build, self.title, self.dlg_h = SPECS[kind]
        self.on_change = on_change or (lambda: None)
        self.factory = factory or self.cls
        self.tree = make_tree(self, tuple(f"c{i}" for i in range(len(self.cols))), tuple(_(c[0]) for c in self.cols),
                              widths=tuple(c[2] for c in self.cols), height=height, anchors=tuple(c[3] for c in self.cols))
        self.tree.frame.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", pady=(4, 0))
        self.buttons = [ttk.Button(bar, text=_("+ Agregar"), command=self.add),
                        ttk.Button(bar, text=_("Editar"), command=self.edit),
                        ttk.Button(bar, text=_("Eliminar"), command=self.remove)]
        for i, b in enumerate(self.buttons):
            b.pack(side="left", padx=(0 if i == 0 else 6, 0))
        if getattr(app, "readonly", False):
            for b in self.buttons:
                b.state(["disabled"])
        self.refresh()

    def items(self):
        return self.getlist(self.app.ret)

    def refresh(self):
        t = self.tree
        t.delete(*t.get_children())
        for i, x in enumerate(self.items()):
            t.insert("", "end", iid=str(i), values=tuple(fn(x) for _h, fn, _w, _a in self.cols))

    def _changed(self):
        self.refresh()
        self.on_change()

    def add(self):
        def ok(x):
            self.items().append(x)
            self._changed()
        Dialog(self.app, _(self.title), self.factory(), self.build, ok, height=self.dlg_h)

    def edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        i = int(sel[0])

        def ok(x):
            self.items()[i] = x
            self._changed()
        Dialog(self.app, _(self.title), copy.deepcopy(self.items()[i]), self.build, ok, height=self.dlg_h)

    def remove(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno(_("Eliminar"), _("¿Eliminar la fila seleccionada?"), parent=self):
            del self.items()[int(sel[0])]
            self._changed()
