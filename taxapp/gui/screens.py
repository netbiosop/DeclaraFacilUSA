"""Pantallas de la entrevista (estilo TurboTax) / Interview screens: una por seccion de la declaracion."""
from __future__ import annotations

import copy
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from .. import data_loader, counties
from ..engine import fmt_money, balance_text
from ..i18n import _, N_, tr, reverse
from ..local import localities_for_state, county_tax_info
from ..models import (FILING_STATUSES, Dependent, W2, CustomLocalTax, age_at_year_end)
from .lists import ListEditor
from .widgets import (COLORS, Form, ScrollFrame, Dialog, make_tree, font)

NONE_LOC = N_("(ninguna)")
RELATIONSHIPS = [N_("Hijo(a)"), N_("Hijastro(a)"), N_("Hijo(a) de crianza"), N_("Nieto(a)"), N_("Hermano(a)"),
                 N_("Sobrino(a)"), N_("Padre / Madre"), N_("Otro pariente"), N_("Otra persona del hogar")]
STATUS_HELP = {
    "single": N_("No casado(a) al 31 de diciembre y sin dependientes que le permitan ser cabeza de familia."),
    "mfj": N_("Casados que combinan ingresos y deducciones en una sola declaracion. Suele ser lo mas conveniente."),
    "mfs": N_("Cada conyuge declara por su cuenta. Pierde varios creditos (EITC, educativos) y deducciones nuevas."),
    "hoh": N_("No casado(a), pago mas de la mitad del costo del hogar donde vivio una persona calificada > 6 meses."),
    "qss": N_("Su conyuge fallecio en uno de los 2 anos anteriores y tiene un hijo dependiente que vive con usted."),
}
STATE_KINDS = {"none": N_("Sin impuesto estatal sobre la renta"), "flat": N_("Impuesto de tasa única"),
               "graduated": N_("Impuesto progresivo por tramos"), "capgains_only": N_("Solo ganancias de capital")}


def loc_from_model(key: str) -> str:
    return _(key) if key else _(NONE_LOC)


def loc_to_model(display: str, keys) -> str:
    if not display or display == _(NONE_LOC):
        return ""
    return reverse(display, keys)


class Screen:
    key = ""
    title = ""
    subtitle = ""

    def __init__(self, app, parent):
        self.app = app
        self.frame = ttk.Frame(parent, style="Card.TFrame")
        head = ttk.Frame(self.frame, style="Card.TFrame", padding=(20, 16, 20, 4))
        head.pack(fill="x")
        if self.app.can("use_ai"):
            ttk.Button(head, text="✦ " + _("Explicar esta sección con IA"), style="Soft.TButton",
                       command=lambda: self.app.ask_ai_action(0)).pack(side="right", anchor="n")
        ttk.Label(head, text=_(self.title), style="CardTitle.TLabel").pack(anchor="w")
        if self.subtitle:
            ttk.Label(head, text=_(self.subtitle), style="CardMuted.TLabel", wraplength=820, justify="left").pack(anchor="w", pady=(2, 0))
        ttk.Separator(self.frame).pack(fill="x", padx=20, pady=(8, 0))
        self.body = ttk.Frame(self.frame, style="Card.TFrame")
        self.body.pack(fill="both", expand=True)
        self.build()

    @property
    def ret(self):
        return self.app.ret

    def changed(self):
        self.app.mark_changed()

    def scroll(self, parent=None, padding=(20, 8)):
        sf = ScrollFrame(parent or self.body)
        sf.pack(fill="both", expand=True)
        inner = ttk.Frame(sf.inner, style="Card.TFrame", padding=padding)
        inner.pack(fill="both", expand=True)
        return inner

    def _tab(self, nb, title):
        holder = ttk.Frame(nb, style="Card.TFrame")
        nb.add(holder, text=title)
        sf = ScrollFrame(holder)
        sf.pack(fill="both", expand=True)
        inner = ttk.Frame(sf.inner, style="Card.TFrame", padding=(12, 8))
        inner.pack(fill="both", expand=True)
        return inner

    def build(self):
        pass

    def on_show(self):
        pass

    def on_result(self, res):
        pass


def result_tree(parent, height=12):
    return make_tree(parent, ("c", "v"), (_("Concepto"), _("Monto")), widths=(470, 140), height=height, anchors=("w", "e"))


def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for name, val in rows:
        tree.insert("", "end", values=(name, val if isinstance(val, str) else fmt_money(val)))


def yes_no(b: bool) -> str:
    return _("Sí") if b else _("No")


# ============================================================================ 1. Informacion personal
class PersonalScreen(Screen):
    key, title = "personal", N_("Información personal")
    subtitle = N_("Empecemos con usted. Esta información identifica su declaración y define su estado civil para impuestos.")

    def build(self):
        p = self.scroll()
        y = self.ret.tax_year
        f = Form(p, lambda: self.ret, self.changed)
        f.section(tr("Año fiscal {y}", y=y),
                  tr("Declaración del año {y}, que se presenta en {y2}. Para cambiar de año, cree una nueva declaración "
                     "desde el menú principal.", y=y, y2=y + 1))
        f.section(_("¿Cuál es su estado civil para efectos de impuestos?"))
        self.status_var = tk.StringVar(value=self.ret.filing_status)
        for code, label in FILING_STATUSES.items():
            rb = ttk.Radiobutton(p, text=_(label), value=code, variable=self.status_var, command=self._status_changed)
            rb.grid(row=f.row, column=0, sticky="w", padx=8, pady=1)
            ttk.Label(p, text=_(STATUS_HELP[code]), style="CardMuted.TLabel", wraplength=460).grid(
                row=f.row, column=1, columnspan=2, sticky="w", padx=(4, 0))
            f.row += 1

        tp = Form(p, lambda: self.ret.taxpayer, self._person_changed)
        tp.row = f.row
        tp.section(_("Sus datos (contribuyente principal)"))
        tp.text(_("Nombre"), "first_name")
        tp.text(_("Apellido(s)"), "last_name")
        tp.text(_("Número de Seguro Social (SSN) o ITIN"), "ssn", _("Formato ###-##-####. Se guarda solo en su computadora."), width=16)
        tp.text(_("Fecha de nacimiento (AAAA-MM-DD)"), "dob", _("Se usa para la deducción estándar adicional y la nueva "
                                                               "deducción de $6,000 para mayores de 65."), width=14)
        self.tp_age = tp.note("")
        tp.text(_("Ocupación"), "occupation")
        tp.check(_("Soy legalmente ciego(a)"), "blind", _("Da derecho a una deducción estándar adicional."))
        tp.check(_("Tengo un SSN válido para trabajar"), "valid_ssn_for_work",
                 _("Requerido (OBBBA) para el EITC, el crédito por hijos y las deducciones de propinas, horas extra y mayores."))
        tp.check(_("Otra persona puede declararme como dependiente"), "can_be_claimed",
                 _("Limita su deducción estándar y le impide reclamar ciertos créditos."))
        tp.text(_("PIN de Protección de Identidad del IRS (si tiene)"), "ip_pin",
                _("6 dígitos que el IRS le envía cada año por carta o en su cuenta en línea."), width=10)
        tp.check(_("Destinar $3 al Fondo de Campaña Presidencial"), "presidential_fund",
                 _("No cambia su impuesto ni su reembolso."))

        self.sp_frame = ttk.Frame(p, style="Card.TFrame")
        self.sp_frame.grid(row=tp.row, column=0, columnspan=3, sticky="ew")
        sp = Form(self.sp_frame, lambda: self.ret.spouse, self._person_changed)
        sp.section(_("Datos de su cónyuge"))
        sp.text(_("Nombre"), "first_name")
        sp.text(_("Apellido(s)"), "last_name")
        sp.text(_("SSN o ITIN del cónyuge"), "ssn", width=16)
        sp.text(_("Fecha de nacimiento (AAAA-MM-DD)"), "dob", width=14)
        self.sp_age = sp.note("")
        sp.text(_("Ocupación"), "occupation")
        sp.check(_("Mi cónyuge es legalmente ciego(a)"), "blind")
        sp.check(_("Mi cónyuge tiene SSN válido para trabajar"), "valid_ssn_for_work")
        sp.text(_("PIN de Protección de Identidad del cónyuge (si tiene)"), "ip_pin", width=10)
        sp.check(_("Mi cónyuge desea destinar $3 al Fondo de Campaña Presidencial"), "presidential_fund")
        self._status_changed(initial=True)
        self._person_changed(notify=False)

    def _status_changed(self, initial=False):
        self.ret.filing_status = self.status_var.get()
        if self.ret.has_spouse():
            self.sp_frame.grid()
        else:
            self.sp_frame.grid_remove()
        if not initial:
            self.changed()

    def _person_changed(self, notify=True):
        y = self.ret.tax_year
        for lbl, person in ((self.tp_age, self.ret.taxpayer), (self.sp_age, self.ret.spouse)):
            a = age_at_year_end(person.dob, y)
            if a is None:
                lbl.configure(text=_("Edad al cierre del año: (ingrese la fecha AAAA-MM-DD)"))
            else:
                extra = _(" — califica para la deducción adicional por edad (65+)") if a >= 65 else ""
                lbl.configure(text=tr("Edad al 31 de diciembre de {y}: {a} años", y=y, a=a) + extra)
        if notify:
            self.changed()


# ============================================================================ 2. Direccion y residencia
class AddressScreen(Screen):
    key, title = "address", N_("Dirección, estado y condado")
    subtitle = N_("Su estado y condado de residencia determinan los impuestos estatales y locales. "
                  "Elija primero el estado; luego el condado y, si aplica, la ciudad con impuesto local.")

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame")
        outer.pack(fill="both", expand=True)
        left = ttk.Frame(outer, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(outer, style="Card.TFrame", padding=(10, 12, 20, 12))
        right.pack(side="right", fill="y")
        p = self.scroll(left)
        a = lambda: self.ret.address  # noqa: E731
        f = Form(p, a, self._changed)
        f.section(_("Domicilio"))
        f.text(_("Calle y número"), "street", width=40)
        f.text(_("Apartamento / unidad"), "apt", width=12)
        f.text(_("Ciudad"), "city", width=28)
        labels = [data_loader.state_label(c) for c in data_loader.state_codes_sorted()]
        self.state_cb = f.combo(_("Estado"), "state", labels, width=32,
                                to_model=data_loader.code_from_label,
                                from_model=lambda c: data_loader.state_label(c) if c else "",
                                on_select=self._state_selected)
        f.text(_("Código postal (ZIP)"), "zip", width=12)
        self.county_cb = f.combo(_("Condado"), "county", [], readonly=False, width=32,
                                 help_text=_("Escriba o elija su condado. En Maryland e Indiana el condado define el impuesto local."),
                                 on_select=self._refresh_info)
        self.loc_cb = f.combo(_("Ciudad/jurisdicción con impuesto local (residencia)"), "locality", [], width=36,
                              to_model=lambda v: loc_to_model(v, self._loc_keys()),
                              from_model=loc_from_model, on_select=self._refresh_info,
                              help_text=_("Solo algunas ciudades cobran impuesto sobre la renta (NYC, Filadelfia, Detroit, Columbus...)."))
        self.work_cb = f.combo(_("Jurisdicción donde trabaja (si es distinta)"), "work_locality", [], width=36,
                               to_model=lambda v: loc_to_model(v, self._loc_keys()),
                               from_model=loc_from_model, on_select=self._refresh_info,
                               help_text=_("Algunas ciudades cobran a quienes trabajan allí sin vivir allí (Filadelfia, Denver, Birmingham)."))
        f.integer(_("Meses viviendo en este estado durante el año"), "months_in_state",
                  _("Si se mudó de estado, indique los meses aquí (cálculo aproximado de residente parcial)."), 1, 12)
        f.section(_("Contacto (opcional)"))
        f.text(_("Teléfono"), "phone", width=18)
        f.text(_("Correo electrónico"), "email", width=32)
        self.dl_note = f.note("")
        self.dl_btn = ttk.Button(p, text=_("Descargar lista oficial de condados (Censo de EE.UU.)"), command=self.app.download_counties)
        self.dl_btn.grid(row=f.row, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        ttk.Label(right, text=_("Impuestos en su zona"), style="Section.TLabel").pack(anchor="w")
        self.info = tk.Text(right, width=46, height=30, wrap="word", relief="flat", background=COLORS["accent_light"],
                            font=font(9), padx=10, pady=8, borderwidth=0)
        self.info.pack(fill="y", expand=True, pady=(6, 0))
        self.info.tag_configure("h", font=font(10, "bold"), foreground=COLORS["primary"])
        self._state_selected(init=True)

    def _loc_keys(self):
        return localities_for_state(self.ret.tax_year, self.ret.address.state)

    def _changed(self):
        self.changed()

    def _state_selected(self, init=False):
        code = self.ret.address.state
        cl = counties.counties_for(code)
        self.county_cb.configure(values=cl)
        keys = self._loc_keys()
        locs = [_(NONE_LOC)] + [_(k) for k in keys]
        self.loc_cb.configure(values=locs)
        self.work_cb.configure(values=locs)
        if not init:
            if self.ret.address.locality and self.ret.address.locality not in keys:
                self.loc_cb.set(_(NONE_LOC))
            if self.ret.address.work_locality and self.ret.address.work_locality not in keys:
                self.work_cb.set(_(NONE_LOC))
            if cl and self.ret.address.county and self.ret.address.county not in cl:
                self.county_cb.set("")
        if counties.has_full_list():
            self.dl_note.configure(text=_("Lista completa de condados disponible."))
            self.dl_btn.grid_remove()
        else:
            self.dl_note.configure(text=_("Lista de condados incluida: Maryland e Indiana. Para los demás estados puede "
                                          "escribir el condado o descargar la lista oficial del Censo (requiere internet)."))
            self.dl_btn.grid()
        self._refresh_info()

    def _refresh_info(self):
        t = self.info
        t.configure(state="normal")
        t.delete("1.0", "end")
        code = self.ret.address.state
        if not code:
            t.insert("end", _("Seleccione un estado para ver sus impuestos."))
            t.configure(state="disabled")
            return
        y = self.ret.tax_year
        sd = data_loader.states(y)[code]
        info = data_loader.states_info()[code]
        t.insert("end", f"{info['name']} — {y}\n", "h")
        t.insert("end", _(STATE_KINDS[sd["type"]]) + "\n")
        if sd.get("brackets"):
            rates = [b[1] for b in sd["brackets"]["single"] if b[1] > 0]
            if rates:
                t.insert("end", tr("Tasas: {a}% a {b}%", a=f"{min(rates) * 100:.2f}", b=f"{max(rates) * 100:.2f}") + "\n")
        std = sd.get("std_deduction") or {}
        if sd.get("uses_federal_deduction") or sd.get("std_from_federal"):
            t.insert("end", _("Deducción: igual a la federal") + "\n")
        elif std.get("single"):
            t.insert("end", tr("Deducción estándar: ${a} (soltero) / ${b} (casados)", a=f"{std['single']:,}",
                               b=f"{std.get('mfj', 0):,}") + "\n")
        if info.get("form"):
            t.insert("end", tr("Formulario: {f}\nAgencia: {a}\nSitio: {u}", f=info["form"], a=info["agency"], u=info["url"]) + "\n")
        t.insert("end", tr("Fecha límite: {d}", d=f"{y + 1}-{info['deadline_mmdd']}") + "\n")
        stx = info["sales_tax"]
        t.insert("end", "\n" + _("Impuesto a las ventas") + "\n", "h")
        t.insert("end", tr("Estatal {a}% + local promedio {b}% = {c}%", a=stx["state"], b=stx["avg_local"], c=stx["combined"]) + "\n")
        t.insert("end", "\n" + _("Condado y ciudad") + "\n", "h")
        t.insert("end", county_tax_info(y, code, self.ret.address.county) + "\n")
        ld = data_loader.local(y)["states"].get(code, {})
        for nm, j in ld.get("localities", {}).items():
            mark = "► " if nm in (self.ret.address.locality, self.ret.address.work_locality) else "• "
            t.insert("end", f"{mark}{_(nm)}: {_(j.get('note', ''))}\n")
        if sd.get("notes"):
            t.insert("end", "\n" + _("Notas") + "\n", "h")
            for n in sd["notes"]:
                t.insert("end", f"• {_(n)}\n")
        t.configure(state="disabled")

    def on_show(self):
        self._state_selected(init=True)


# ============================================================================ 3. Dependientes
class DependentsScreen(Screen):
    key, title = "dependents", N_("Dependientes")
    subtitle = N_("Agregue a sus hijos u otras personas que dependen de usted. Determinan el crédito por hijos ($2,200 por "
                  "hijo menor de 17), el EITC, el crédito por cuidado y el estado de cabeza de familia.")

    def build(self):
        p = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 10))
        p.pack(fill="both", expand=True)
        self.tree = make_tree(p, ("n", "r", "d", "a", "ctc", "eic", "care"),
                              (_("Nombre"), _("Relación"), _("Nacimiento"), _("Edad"), _("Crédito hijos"), _("EITC"), _("Cuidado")),
                              widths=(200, 120, 100, 50, 100, 60, 70), height=10)
        self.tree.frame.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        bar = ttk.Frame(p, style="Card.TFrame")
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text=_("+ Agregar dependiente"), style="Accent.TButton", command=self.add).pack(side="left")
        ttk.Button(bar, text=_("Editar"), command=self.edit).pack(side="left", padx=6)
        ttk.Button(bar, text=_("Eliminar"), command=self.remove).pack(side="left")
        ttk.Label(p, text=_("Crédito por hijos: menor de 17 al 31-dic con SSN. EITC: menor de 19 (24 si estudiante) o "
                            "discapacitado. Cuidado: menor de 13."), style="CardMuted.TLabel", wraplength=800).pack(anchor="w")
        self.refresh()

    def refresh(self):
        y = self.ret.tax_year
        self.tree.delete(*self.tree.get_children())
        for i, d in enumerate(self.ret.dependents):
            a = d.age(y)
            ctc = "$2,200" if d.qualifies_ctc(y) else "$500 (ODC)"
            self.tree.insert("", "end", iid=str(i), values=(d.full_name(), _(d.relationship), d.dob, "" if a is None else a,
                                                           ctc, yes_no(d.qualifies_eitc(y)), yes_no(d.qualifies_care(y))))

    def _dialog(self, dep, on_ok):
        def build(f):
            f.text(_("Nombre"), "first_name")
            f.text(_("Apellido(s)"), "last_name")
            f.combo(_("Relación con usted"), "relationship", [_(r) for r in RELATIONSHIPS],
                    to_model=lambda v: reverse(v, RELATIONSHIPS), from_model=lambda k: _(k) if k else "")
            f.text(_("Fecha de nacimiento (AAAA-MM-DD)"), "dob", width=14)
            f.text(_("SSN"), "ssn", width=16)
            f.check(_("Tiene SSN válido"), "has_ssn")
            f.integer(_("Meses que vivió con usted en el año"), "months_lived", frm=0, to=12)
            f.check(_("Estudiante de tiempo completo"), "full_time_student")
            f.check(_("Total y permanentemente discapacitado(a)"), "disabled")
            f.check(_("Vivió con usted en los Estados Unidos"), "lived_in_us")
        Dialog(self.app, _("Dependiente"), dep, build, on_ok, height=500)

    def add(self):
        def ok(d):
            self.ret.dependents.append(d)
            self.refresh()
            self.changed()
        self._dialog(Dependent(last_name=self.ret.taxpayer.last_name), ok)

    def edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        i = int(sel[0])

        def ok(d):
            self.ret.dependents[i] = d
            self.refresh()
            self.changed()
        self._dialog(copy.deepcopy(self.ret.dependents[i]), ok)

    def remove(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno(_("Eliminar"), _("¿Eliminar el dependiente seleccionado?"), parent=self.app):
            del self.ret.dependents[int(sel[0])]
            self.refresh()
            self.changed()


# ============================================================================ 4. Ingresos
class IncomeScreen(Screen):
    key, title = "income", N_("Ingresos")
    subtitle = N_("Ingrese sus formularios W-2 y 1099. Cada pestaña corresponde a un tipo de ingreso; complete solo los que apliquen.")

    def build(self):
        nb = ttk.Notebook(self.body)
        nb.pack(fill="both", expand=True, padx=16, pady=10)
        self.nb = nb
        self._w2_tab(nb)
        inc = lambda: self.ret.income  # noqa: E731

        p = self._tab(nb, _("Intereses y dividendos"))
        f = Form(p, inc, self.changed)
        f.section(_("Formularios 1099-INT y 1099-DIV"))
        f.money(_("Intereses tributables (1099-INT casilla 1)"), "taxable_interest")
        f.money(_("Intereses exentos (casilla 8)"), "tax_exempt_interest", _("Bonos municipales. No pagan impuesto federal pero "
                                                                           "cuentan para la tributación del Seguro Social."))
        f.money(_("Dividendos ordinarios (1099-DIV casilla 1a)"), "ordinary_dividends")
        f.money(_("Dividendos calificados (casilla 1b)"), "qualified_dividends", _("Tributan a 0%, 15% o 20%."))
        f.money(_("Impuesto federal retenido (casilla 4)"), "investment_withheld")
        f.section(_("Pagadores (para el Anexo B)"),
                  _("Si sus intereses o dividendos pasan de $1,500, el Anexo B pide el nombre de cada pagador."))
        f.note(_("Intereses:"))
        self._grid_list(p, f, "interest_payers")
        f.note(_("Dividendos:"))
        self._grid_list(p, f, "dividend_payers")

        p = self._tab(nb, _("Inversiones (1099-B)"))
        f = Form(p, inc, self.changed)
        f.section(_("Ventas de acciones, fondos, criptomonedas y otros activos"),
                  _("Agregue cada venta de su 1099-B (o el total por categoría). Con el detalle se llenan el Anexo D "
                    "y el Formulario 8949."))
        self._grid_list(p, f, "sales", height=6)
        f.section(_("Ganancia neta sin detalle (opcional)"))
        f.money(_("Ganancia/pérdida neta a corto plazo (≤ 1 año)"), "short_term_gain",
                _("Solo si NO agregó las ventas arriba. Use número negativo para pérdidas: -1500"))
        f.money(_("Ganancia/pérdida neta a largo plazo (> 1 año)"), "long_term_gain", _("Tasas preferenciales 0/15/20%."))
        f.money(_("Distribuciones de ganancias de capital (1099-DIV 2a)"), "capital_gain_distributions")
        f.money(_("Pérdida de capital arrastrada de años anteriores"), "capital_loss_carryover")
        f.note(_("Las pérdidas netas se deducen hasta $3,000 al año ($1,500 casados por separado)."))

        p = self._tab(nb, _("Negocio propio (Anexo C)"))
        f = Form(p, inc, self._biz_changed)
        f.section(_("Trabajo independiente, 1099-NEC / 1099-K, contratista, gig economy"))
        f.text(_("Nombre comercial del negocio"), "business_name", width=34)
        f.text(_("Actividad principal (producto o servicio)"), "business_activity", width=34,
               help_text=_("Ej.: House cleaning, Rideshare driver, Painting. De preferencia en inglés."))
        f.text(_("Código de actividad (6 dígitos)"), "business_code", width=10,
               help_text=_("Del listado de las instrucciones del Anexo C. Ej.: 485310 taxi/rideshare, 561720 limpieza."))
        f.text(_("EIN del negocio (si tiene)"), "business_ein", width=14)
        f.text(_("Dirección del negocio (si es distinta a su casa)"), "business_address", width=34)
        f.text(_("Ciudad, estado y ZIP del negocio"), "business_city", width=34)
        f.money(_("Ingresos brutos (incluye 1099-NEC/1099-K)"), "business_gross")
        f.money(_("Devoluciones y descuentos"), "business_returns")
        f.money(_("Costo de mercancía vendida"), "business_cogs")
        f.section(_("Gastos del negocio"))
        for lbl, attr in ((N_("Publicidad"), "exp_advertising"), (N_("Vehículo (millaje o gastos reales)"), "exp_car"),
                          (N_("Seguros"), "exp_insurance"), (N_("Oficina y software"), "exp_office"),
                          (N_("Suministros"), "exp_supplies"),
                          (N_("Teléfono e internet (parte de negocio)"), "exp_phone_internet"),
                          (N_("Viajes de negocio (pasajes, hotel)"), "exp_travel"),
                          (N_("Comidas de negocio (se deducen al 50%)"), "exp_travel_meals"),
                          (N_("Contratistas"), "exp_contract_labor"), (N_("Alquiler"), "exp_rent"),
                          (N_("Otros gastos"), "exp_other")):
            f.money(_(lbl), attr)
        f.note(_("Si detalla 'otros gastos' abajo, el detalle reemplaza el monto de 'Otros gastos'."))
        self._grid_list(p, f, "other_expenses", height=3, on_change=self._biz_changed)
        f.money(_("Oficina en casa: pies cuadrados (método simplificado $5/pie², máx. 300)"), "home_office_sqft")
        f.money(_("Pies cuadrados totales de la vivienda"), "home_total_sqft")
        f.money(_("Impuesto federal retenido (1099)"), "business_withheld")
        f.section(_("Vehículo (si dedujo gastos de auto)"))
        f.text(_("Fecha en que empezó a usarlo para el negocio (MM/DD/AAAA)"), "vehicle_in_service", width=14)
        f.money(_("Millas de negocio"), "miles_business")
        f.money(_("Millas de ida y vuelta al trabajo"), "miles_commuting")
        f.money(_("Otras millas (personales)"), "miles_other")
        f.section(_("Preguntas del Anexo C"))
        f.combo(_("Método de contabilidad"), "accounting_method", [_("Efectivo (cash)"), _("Acumulación (accrual)")],
                to_model=lambda v: "accrual" if v == _("Acumulación (accrual)") else "cash",
                from_model=lambda v: _("Acumulación (accrual)") if v == "accrual" else _("Efectivo (cash)"))
        f.check(_("Participé materialmente en el negocio"), "material_participation")
        f.check(_("Empecé o compré el negocio este año"), "business_started")
        f.check(_("Hice pagos que requieren formularios 1099"), "made_1099_payments")
        f.check(_("Presenté (o presentaré) esos formularios 1099"), "filed_1099s")
        self.biz_lbl = f.note("", COLORS["primary"])
        self._biz_changed(notify=False)

        p = self._tab(nb, _("Jubilación y Seguro Social"))
        f = Form(p, inc, self.changed)
        f.section(_("Pensiones y anualidades (1099-R)"))
        f.money(_("Monto bruto (casilla 1)"), "pension_gross")
        f.money(_("Monto tributable (casilla 2a)"), "pension_taxable")
        f.money(_("Impuesto retenido (casilla 4)"), "pension_withheld")
        f.section(_("Distribuciones de IRA (1099-R)"))
        f.money(_("Monto bruto"), "ira_gross")
        f.money(_("Monto tributable"), "ira_taxable", _("Retiros de Roth calificados no tributan."))
        f.money(_("Impuesto retenido"), "ira_withheld")
        f.section(_("Seguro Social (SSA-1099)"))
        f.money(_("Beneficios netos (casilla 5)"), "social_security", _("Se calcula automáticamente la porción tributable (0%, 50% u 85%)."))
        f.money(_("Impuesto retenido (casilla 6)"), "ss_withheld")

        p = self._tab(nb, _("Desempleo y otros"))
        f = Form(p, inc, self.changed)
        f.section(_("Desempleo (1099-G)"))
        f.money(_("Compensación por desempleo (casilla 1)"), "unemployment")
        f.money(_("Impuesto retenido (casilla 4)"), "unemployment_withheld")
        f.money(_("Reembolso estatal tributable (solo si itemizó el año anterior)"), "state_refund_taxable")
        f.section(_("Otros"))
        f.money(_("Premios de juegos y loterías (W-2G)"), "gambling")
        f.money(_("Otros ingresos"), "other_income")
        f.text(_("Descripción de otros ingresos"), "other_income_desc", width=34)

        p = self._tab(nb, _("Propinas y horas extra (nuevo)"))
        f = Form(p, inc, self.changed)
        f.section(_("Deducciones 'sin impuesto' sobre propinas y horas extra (2025-2028)"),
                  _("Ley OBBBA. Estos montos YA están incluidos en sus salarios W-2; aquí se indican para deducirlos "
                    "en el Anexo 1-A. Requieren SSN válido y, si está casado, declarar en conjunto."))
        f.money(_("Propinas calificadas (máx. $25,000)"), "qualified_tips",
                _("Propinas voluntarias en ocupaciones que tradicionalmente las reciben. Se reduce con MAGI > $150k ($300k MFJ)."))
        f.money(_("Horas extra calificadas: solo la PRIMA (máx. $12,500 / $25,000 MFJ)"), "qualified_overtime",
                _("Solo la parte extra del pago 'tiempo y medio' exigido por la ley FLSA. Ej.: $30/h normal, $45/h extra → $15/h."))

    def _grid_list(self, parent, form, kind, height=4, on_change=None):
        ed = ListEditor(parent, self.app, kind, on_change or self.changed, height=height)
        ed.grid(row=form.row, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 8))
        form.row += 1
        return ed

    def _biz_changed(self, notify=True):
        inc = self.ret.income
        profit = inc.schedule_c_profit()
        self.biz_lbl.configure(text=tr("Ganancia neta del negocio: {p}  •  Gastos: {g}  •  Impuesto de trabajo independiente "
                                       "estimado: {s}", p=fmt_money(profit), g=fmt_money(inc.schedule_c_expenses()),
                                       s=fmt_money(max(0, profit) * 0.9235 * 0.153)))
        if notify:
            self.changed()

    # ---------------------------------------------------------------- W-2
    def _w2_tab(self, nb):
        holder = ttk.Frame(nb, style="Card.TFrame", padding=(12, 8))
        nb.add(holder, text=_("Salarios (W-2)"))
        ttk.Label(holder, text=_("Agregue un W-2 por cada empleo (suyo o de su cónyuge)."), style="CardMuted.TLabel").pack(anchor="w")
        self.w2tree = make_tree(holder, ("e", "o", "w", "f", "s", "sw"),
                                (_("Empleador"), _("De"), _("Salario (1)"), _("Ret. federal (2)"), _("Estado"), _("Ret. estatal (17)")),
                                widths=(220, 100, 110, 110, 60, 110), height=9, anchors=("w", "w", "e", "e", "center", "e"))
        self.w2tree.frame.pack(fill="both", expand=True, pady=6)
        self.w2tree.bind("<Double-1>", lambda e: self.edit_w2())
        bar = ttk.Frame(holder, style="Card.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text=_("+ Agregar W-2"), style="Accent.TButton", command=self.add_w2).pack(side="left")
        ttk.Button(bar, text=_("Editar"), command=self.edit_w2).pack(side="left", padx=6)
        ttk.Button(bar, text=_("Eliminar"), command=self.remove_w2).pack(side="left")
        self.refresh_w2()

    def refresh_w2(self):
        t = self.w2tree
        t.delete(*t.get_children())
        for i, w in enumerate(self.ret.w2s):
            t.insert("", "end", iid=str(i), values=(w.employer, _("Cónyuge") if w.owner == "conyuge" else _("Usted"),
                                                    fmt_money(w.box1_wages), fmt_money(w.box2_fed_withheld), w.state,
                                                    fmt_money(w.box17_state_withheld)))

    def _w2_dialog(self, w2, on_ok):
        codes = data_loader.state_codes_sorted()

        def build(f):
            f.section(_("Empleador"))
            f.text(_("Nombre del empleador"), "employer")
            f.text(_("EIN del empleador (casilla b)"), "ein", width=14)
            f.combo(_("Este W-2 pertenece a"), "owner", [_("Usted"), _("Cónyuge")],
                    to_model=lambda v: "conyuge" if v == _("Cónyuge") else "contribuyente",
                    from_model=lambda v: _("Cónyuge") if v == "conyuge" else _("Usted"))
            f.section(_("Federal"))
            f.money(_("1 - Salarios, propinas, otra compensación"), "box1_wages")
            f.money(_("2 - Impuesto federal retenido"), "box2_fed_withheld")
            f.money(_("3 - Salarios del Seguro Social"), "box3_ss_wages")
            f.money(_("4 - Impuesto del Seguro Social retenido"), "box4_ss_withheld")
            f.money(_("5 - Salarios de Medicare"), "box5_medicare_wages")
            f.money(_("6 - Impuesto de Medicare retenido"), "box6_medicare_withheld")
            f.money(_("7 - Propinas sujetas al Seguro Social"), "box7_ss_tips")
            f.money(_("12 - Contribuciones 401(k)/403(b) (código D/E, informativo)"), "box12_401k")
            f.section(_("Estatal y local"))
            f.combo(_("15 - Estado"), "state", codes, width=8)
            f.money(_("16 - Salarios estatales"), "box16_state_wages")
            f.money(_("17 - Impuesto estatal retenido"), "box17_state_withheld")
            f.money(_("18 - Salarios locales"), "box18_local_wages")
            f.money(_("19 - Impuesto local retenido"), "box19_local_withheld")
            f.text(_("20 - Nombre de la localidad"), "box20_locality", width=20)
        Dialog(self.app, _("Formulario W-2"), w2, build, on_ok, width=600, height=640)

    def add_w2(self):
        def ok(w):
            if not w.box3_ss_wages:
                w.box3_ss_wages = w.box1_wages + w.box12_401k
            if not w.box5_medicare_wages:
                w.box5_medicare_wages = w.box3_ss_wages
            self.ret.w2s.append(w)
            self.refresh_w2()
            self.changed()
        self._w2_dialog(W2(state=self.ret.address.state), ok)

    def edit_w2(self):
        sel = self.w2tree.selection()
        if not sel:
            return
        i = int(sel[0])

        def ok(w):
            self.ret.w2s[i] = w
            self.refresh_w2()
            self.changed()
        self._w2_dialog(copy.deepcopy(self.ret.w2s[i]), ok)

    def remove_w2(self):
        sel = self.w2tree.selection()
        if sel and messagebox.askyesno(_("Eliminar"), _("¿Eliminar el W-2 seleccionado?"), parent=self.app):
            del self.ret.w2s[int(sel[0])]
            self.refresh_w2()
            self.changed()


# ============================================================================ 5. Deducciones
class DeductionsScreen(Screen):
    key, title = "deductions", N_("Deducciones")
    subtitle = N_("Ajustes al ingreso, las nuevas deducciones 2025-2028 y la comparación entre deducción estándar e "
                  "itemizada. La aplicación elige automáticamente la que más le conviene.")

    def build(self):
        top = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 8))
        top.pack(fill="x")
        self.cmp = ttk.Label(top, text="", style="Big.TLabel")
        self.cmp.pack(anchor="w")
        modes = ttk.Frame(top, style="Card.TFrame")
        modes.pack(anchor="w", pady=4)
        self.mode = tk.StringVar(value=self.ret.deductions.mode)
        for v, t in (("auto", _("Elegir la mejor automáticamente")), ("standard", _("Usar deducción estándar")),
                     ("itemized", _("Itemizar (Anexo A)"))):
            ttk.Radiobutton(modes, text=t, value=v, variable=self.mode, command=self._mode).pack(side="left", padx=(0, 14))
        nb = ttk.Notebook(self.body)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        d = lambda: self.ret.deductions  # noqa: E731

        p = self._tab(nb, _("Ajustes (Anexo 1)"))
        f = Form(p, d, self.changed)
        f.section(_("Se restan antes de calcular el AGI"))
        f.money(_("Gastos de educador (K-12)"), "educator_expenses", _("Hasta $300 (2025) / $350 (2026) por educador."))
        f.money(_("Aportes suyos a la cuenta HSA (Form 8889)"), "hsa_deduction",
                _("Lo que usted aportó (no incluya lo que aportó su empleador por nómina)."))
        f.combo(_("Cobertura HDHP de la HSA"), "hsa_coverage", ["", _("Individual (self-only)"), _("Familiar (family)")],
                to_model=lambda v: {"": "", _("Individual (self-only)"): "self", _("Familiar (family)"): "family"}.get(v, ""),
                from_model=lambda v: {"self": _("Individual (self-only)"), "family": _("Familiar (family)")}.get(v, ""),
                help_text=_("Con la cobertura se aplica el tope anual del IRS ($4,300 / $8,550 en 2025)."))
        f.money(_("Aportes del empleador a la HSA (W-2 casilla 12, código W)"), "hsa_employer")
        f.money(_("Deducción por IRA tradicional"), "ira_deduction", _("Solo la parte deducible según su plan de retiro e ingresos."))
        f.money(_("Seguro médico de trabajador independiente"), "se_health_insurance")
        f.money(_("Interés de préstamos estudiantiles (1098-E)"), "student_loan_interest", _("Máximo $2,500; se reduce con ingresos altos."))
        f.money(_("Otros ajustes"), "other_adjustments")

        p = self._tab(nb, _("Nuevas deducciones (Anexo 1-A)"))
        f = Form(p, d, self.changed)
        f.section(_("Deducciones 2025-2028 de la ley OBBBA (se toman aunque no itemice)"))
        f.money(_("Interés de préstamo de auto nuevo (1098-VLI)"), "car_loan_interest",
                _("Hasta $10,000. Vehículo nuevo de uso personal con ensamblaje final en EE.UU., préstamo originado después "
                  "del 31-dic-2024 y garantizado por el vehículo. Se reduce si MAGI > $100k ($200k MFJ)."))
        f.text(_("VIN del vehículo (17 caracteres)"), "car_vin", width=24)
        f.note(_("Propinas y horas extra: se ingresan en Ingresos → 'Propinas y horas extra'.\n"
                 "Deducción de $6,000 para mayores de 65: se aplica automáticamente según su fecha de nacimiento "
                 "(se reduce si MAGI > $75k / $150k MFJ)."))

        p = self._tab(nb, _("Itemizadas (Anexo A)"))
        f = Form(p, d, self.changed)
        f.section(_("Médicos"))
        f.money(_("Gastos médicos y dentales no reembolsados"), "medical", _("Solo se deduce lo que exceda 7.5% de su AGI."))
        f.section(_("Impuestos estatales y locales (SALT) — tope $40,000 (2025) / $40,400 (2026)"))
        f.check(_("Deducir impuesto a las ventas en lugar del impuesto estatal sobre la renta"), "salt_use_sales_tax",
                _("Útil en estados sin impuesto sobre la renta (TX, FL, WA...)."))
        f.money(_("Impuesto estatal/local pagado aparte de su W-2 (saldo del año anterior)"), "state_income_tax_paid_extra",
                _("Las retenciones del W-2 (casillas 17 y 19) y los pagos estimados se suman automáticamente."))
        f.money(_("Impuesto a las ventas pagado"), "sales_tax_paid")
        f.money(_("Impuesto a la propiedad (casa)"), "real_estate_tax")
        f.money(_("Impuesto a la propiedad personal (vehículo, según valor)"), "personal_property_tax")
        f.section(_("Intereses"))
        f.money(_("Interés hipotecario (1098)"), "mortgage_interest", _("Deuda de hasta $750,000."))
        f.money(_("Puntos pagados"), "mortgage_points")
        f.money(_("Interés de inversión"), "investment_interest")
        f.section(_("Donaciones"))
        f.money(_("Donaciones en efectivo"), "charity_cash", _("Desde 2026, si no itemiza puede deducir hasta $1,000 ($2,000 MFJ)."))
        f.money(_("Donaciones en especie (ropa, artículos)"), "charity_noncash")
        f.section(_("Otras"))
        f.money(_("Pérdidas por desastre declarado federalmente"), "casualty_loss")
        f.money(_("Otras deducciones itemizadas"), "other_itemized")

    def _mode(self):
        self.ret.deductions.mode = self.mode.get()
        self.changed()

    def on_result(self, res):
        f = res["federal"]
        used = _("itemizada") if f["itemize"] else _("estándar")
        self.cmp.configure(text=tr("Estándar: {a}   •   Itemizada: {b}   →   Se usa la deducción {u}: {c}",
                                   a=fmt_money(f["standard_deduction"]), b=fmt_money(f["itemized_net"]), u=used,
                                   c=fmt_money(f["deduction"])))


# ============================================================================ 6. Creditos
class CreditsScreen(Screen):
    key, title = "credits", N_("Créditos")
    subtitle = N_("Los créditos reducen su impuesto dólar por dólar. El crédito por hijos y el EITC se calculan "
                  "automáticamente con sus dependientes; aquí agregue gastos de cuidado, educación y ahorro para el retiro.")

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame")
        outer.pack(fill="both", expand=True)
        right = ttk.Frame(outer, style="Card.TFrame", padding=(8, 12, 20, 12))
        right.pack(side="right", fill="y")
        left = ttk.Frame(outer, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True)
        p = self.scroll(left)
        c = lambda: self.ret.credits  # noqa: E731
        f = Form(p, c, self.changed)
        f.section(_("Cuidado de hijos y dependientes (Formulario 2441)"),
                  _("Guardería, campamento de día, niñera, cuidado de adulto dependiente, para que usted pueda trabajar."))
        f.money(_("Gastos de cuidado pagados"), "care_expenses", _("Límite $3,000 (1 persona) o $6,000 (2+)."))
        f.integer(_("Personas cuidadas (0 = calcular con dependientes)"), "care_persons", frm=0, to=6)
        f.money(_("Beneficios de cuidado del empleador (W-2 casilla 10)"), "dependent_care_benefits")
        f.note(_("Proveedores de cuidado (obligatorio para el Formulario 2441):"))
        ed = ListEditor(p, self.app, "care_providers", self.changed, height=3)
        ed.grid(row=f.row, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 8))
        f.row += 1
        f.section(_("Ahorro para la jubilación (crédito del ahorrador, Form 8880)"))
        f.money(_("Sus aportes a IRA/401(k)"), "retirement_contrib_taxpayer")
        f.money(_("Aportes de su cónyuge"), "retirement_contrib_spouse")
        f.section(_("Otros"))
        f.money(_("Impuestos extranjeros pagados (1099-DIV/INT)"), "foreign_tax_paid")
        f.money(_("Otros créditos no reembolsables"), "other_nonrefundable")
        f.money(_("Otros créditos reembolsables"), "other_refundable")
        f.check(_("Reclamar el Crédito por Ingreso del Trabajo (EITC) si califico"), "claim_eitc")

        f.section(_("Educación universitaria (Formulario 8863)"),
                  _("AOTC: hasta $2,500 por estudiante en los primeros 4 años (40% reembolsable). LLC: 20% de hasta $10,000."))
        self.students = ListEditor(p, self.app, "students", self.changed, height=4)
        self.students.grid(row=f.row, column=0, columnspan=3, sticky="ew", padx=4)
        f.row += 1

        ttk.Label(right, text=_("Créditos calculados"), style="Section.TLabel").pack(anchor="w")
        self.tree = result_tree(right, height=14)
        self.tree.frame.pack(fill="y", expand=True, pady=6)

    def on_result(self, res):
        c = res["federal"]["credits"]
        fill_tree(self.tree, [
            (tr("Crédito por hijos ({a}) y otros dependientes ({b})", a=c["n_ctc"], b=c["n_odc"]), c["ctc_nonref"]),
            (_("Crédito adicional por hijos (reembolsable)"), c["actc"]),
            (tr("EITC ({n} hijos calificados)", n=c["n_eitc"]), c["eitc"]),
            (tr("Cuidado de dependientes ({n} personas)", n=c["n_care"]), c["cdcc"]),
            (_("Educación (no reembolsable)"), c["education_nonref"]),
            (_("AOTC reembolsable"), c["aotc_refundable"]),
            (_("Crédito del ahorrador"), c["savers"]),
            (_("Impuestos extranjeros"), c["foreign"]),
            (_("Otros"), c["other_nonref"] + c["other_refundable"]),
        ])


# ============================================================================ 7. Pagos
class PaymentsScreen(Screen):
    key, title = "payments", N_("Pagos y retenciones")
    subtitle = N_("Las retenciones de sus W-2 y 1099 ya están incluidas. Agregue aquí los pagos estimados y otros pagos.")

    def build(self):
        p = self.scroll()
        f = Form(p, lambda: self.ret.payments, self.changed)
        f.section(_("Federal"))
        f.money(_("Pagos estimados al IRS (Form 1040-ES)"), "federal_estimated")
        f.money(_("Pago con la solicitud de prórroga (Form 4868)"), "federal_extension")
        f.money(_("Reembolso del año anterior aplicado a este año"), "federal_prior_overpayment")
        f.section(_("Estatal"))
        f.money(_("Pagos estimados al estado"), "state_estimated")
        f.money(_("Pago con prórroga estatal"), "state_extension")
        f.section(_("Local"))
        f.money(_("Pagos estimados de impuestos locales"), "local_estimated")
        self.sum = f.note("", COLORS["primary"])

    def on_result(self, res):
        p = res["federal"]["payments"]
        self.sum.configure(text=tr("Retención federal total: {a}   •   Retención estatal: {b}   •   Retención local: {c}",
                                   a=fmt_money(p["withholding"]), b=fmt_money(res["state"]["withholding"]),
                                   c=fmt_money(res["local"]["withholding"])))


# ============================================================================ 8. Estatal
class StateScreen(Screen):
    key, title = "state", N_("Declaración estatal")
    subtitle = N_("Cálculo de su impuesto estatal a partir de los datos federales. Agregue ajustes propios del estado si aplican.")

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 8))
        outer.pack(fill="both", expand=True)
        self.head = ttk.Label(outer, text="", style="Big.TLabel")
        self.head.pack(anchor="w")
        self.link = ttk.Label(outer, text="", style="CardMuted.TLabel", cursor="hand2", foreground=COLORS["info"])
        self.link.pack(anchor="w")
        self.link.bind("<Button-1>", lambda e: self._open())
        cols = ttk.Frame(outer, style="Card.TFrame")
        cols.pack(fill="both", expand=True, pady=8)
        self.tree = result_tree(cols, height=16)
        self.tree.frame.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(cols, style="Card.TFrame", padding=(14, 0, 0, 0))
        right.pack(side="right", fill="y")
        f = Form(right, lambda: self.ret.state_extras, self.changed, label_width=28)
        f.section(_("Ajustes estatales (opcional)"))
        f.money(_("Sumas al ingreso estatal"), "additions", _("Ej.: intereses de bonos de otros estados."))
        f.money(_("Restas al ingreso estatal"), "subtractions", _("Ej.: intereses de bonos del Tesoro, exclusiones de jubilación."))
        f.money(_("Deducciones itemizadas estatales"), "itemized_override", _("Se usan si superan la deducción estándar estatal."))
        f.money(_("Crédito por impuestos pagados a otro estado"), "other_state_credit")
        f.money(_("Otros créditos estatales"), "other_credits", _("Ej.: EITC estatal, créditos por renta o propiedad."))
        f.money(_("Créditos estatales reembolsables"), "refundable_credits")
        self.notes = tk.Text(outer, height=6, wrap="word", relief="flat", background=COLORS["accent_light"], font=font(9),
                             padx=8, pady=6)
        self.notes.pack(fill="x")

    def _open(self):
        url = (self.app.result or {}).get("state", {}).get("url")
        if url:
            webbrowser.open(url)

    def on_result(self, res):
        s = res["state"]
        if not s.get("name"):
            self.head.configure(text=_("Seleccione su estado en 'Dirección y residencia'."))
            fill_tree(self.tree, [])
            return
        self.head.configure(text=tr("{n} — {b}   (impuesto {t})", n=s["name"], b=balance_text(s["balance"]), t=fmt_money(s["tax"])))
        self.link.configure(text=tr("Formulario: {f}   •   {a}   •   {u}", f=s.get("form") or _("no aplica"),
                                    a=s.get("agency") or "", u=s.get("url") or ""))
        rows = list(s.get("lines", []))
        rows += [(_("Retención estatal (W-2 casilla 17)"), s["withholding"]), (_("Pagos y créditos reembolsables"), s["payments"]),
                 (_("RESULTADO"), balance_text(s["balance"]))]
        if s.get("marginal_rate"):
            rows.append((_("Tasa marginal estatal"), f"{s['marginal_rate'] * 100:.2f}%"))
        fill_tree(self.tree, rows)
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("end", "\n".join(f"• {n}" for n in s.get("notes", [])) or _("Sin notas."))
        self.notes.configure(state="disabled")


# ============================================================================ 9. Local
class LocalScreen(Screen):
    key, title = "local", N_("Impuestos locales (condado y ciudad)")
    subtitle = N_("Maryland e Indiana cobran impuesto por condado; varias ciudades (NYC, Filadelfia, Detroit, Columbus, "
                  "Kansas City...) cobran impuesto sobre la renta. Agregue cualquier otro impuesto local aquí.")
    BASES = {"earned": N_("Salarios + negocio"), "agi": N_("AGI federal"), "state_taxable": N_("Ingreso tributable estatal"),
             "state_tax": N_("% del impuesto estatal")}

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 8))
        outer.pack(fill="both", expand=True)
        self.head = ttk.Label(outer, text="", style="Big.TLabel")
        self.head.pack(anchor="w")
        self.tree = make_tree(outer, ("j", "b", "r", "t"), (_("Jurisdicción"), _("Base"), _("Tasa"), _("Impuesto")),
                              widths=(300, 120, 160, 120), height=6, anchors=("w", "e", "center", "e"))
        self.tree.frame.pack(fill="x", pady=6)
        frm = ttk.Frame(outer, style="Card.TFrame")
        frm.pack(fill="x")
        f = Form(frm, lambda: self.ret.state_extras, self.changed)
        f.money(_("Tasa propia para jurisdicción editable (%, ej. 1.25)"), "locality_rate_override",
                _("Para 'Otro municipio de PA' o el recargo escolar de Iowa: escriba su tasa exacta."))
        ttk.Label(outer, text=_("Impuestos locales personalizados"), style="Section.TLabel").pack(anchor="w", pady=(10, 0))
        self.ctree = make_tree(outer, ("n", "b", "r", "w"), (_("Nombre"), _("Base"), _("Tasa %"), _("Retenido")),
                               widths=(260, 200, 80, 100), height=4, anchors=("w", "w", "e", "e"))
        self.ctree.frame.pack(fill="x", pady=4)
        bar = ttk.Frame(outer, style="Card.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text=_("+ Agregar impuesto local"), command=self.add_custom).pack(side="left")
        ttk.Button(bar, text=_("Eliminar"), command=self.remove_custom).pack(side="left", padx=6)
        self.notes = ttk.Label(outer, text="", style="CardMuted.TLabel", wraplength=820, justify="left")
        self.notes.pack(anchor="w", pady=8)
        self.refresh_custom()

    def refresh_custom(self):
        self.ctree.delete(*self.ctree.get_children())
        for i, c in enumerate(self.ret.state_extras.custom_local):
            self.ctree.insert("", "end", iid=str(i), values=(c.name, _(self.BASES.get(c.base, c.base)), c.rate, fmt_money(c.withheld)))

    def add_custom(self):
        inv = {_(v): k for k, v in self.BASES.items()}

        def build(f):
            f.text(_("Nombre (ciudad, distrito escolar...)"), "name")
            f.combo(_("Base del impuesto"), "base", [_(v) for v in self.BASES.values()], to_model=lambda v: inv.get(v, "earned"),
                    from_model=lambda k: _(self.BASES.get(k, self.BASES["earned"])))
            f.money(_("Tasa (%)"), "rate")
            f.money(_("Impuesto retenido o pagado"), "withheld")

        def ok(c):
            self.ret.state_extras.custom_local.append(c)
            self.refresh_custom()
            self.changed()
        Dialog(self.app, _("Impuesto local"), CustomLocalTax(), build, ok, height=300)

    def remove_custom(self):
        sel = self.ctree.selection()
        if sel:
            del self.ret.state_extras.custom_local[int(sel[0])]
            self.refresh_custom()
            self.changed()

    def on_result(self, res):
        loc = res["local"]
        self.head.configure(text=tr("Total local: {a}   •   Retenido: {b}   •   {c}", a=fmt_money(loc["total"]),
                                    b=fmt_money(loc["withholding"]), c=balance_text(loc["balance"])))
        self.tree.delete(*self.tree.get_children())
        for it in loc["items"]:
            base = tr("{n} meses", n=int(it["base"])) if it.get("monthly") else fmt_money(it["base"])
            self.tree.insert("", "end", values=(it["name"], base, it["rate"], fmt_money(it["tax"])))
        a = self.ret.address
        txt = tr("Estado: {s}   Condado: {c}   Jurisdicción: {j}", s=a.state or "-", c=a.county or "-",
                 j=_(a.locality) if a.locality else "-") + "\n"
        txt += "\n".join(f"• {n}" for n in loc.get("notes", []))
        self.notes.configure(text=txt)


# ============================================================================ 10. Revision
class ReviewScreen(Screen):
    key, title = "review", N_("Revisión de la declaración")
    subtitle = N_("Revisamos su declaración en busca de errores, datos faltantes y oportunidades. "
                  "Haga doble clic en un hallazgo para ir a la sección correspondiente.")
    SEV = {"error": N_("ERROR"), "aviso": N_("REVISE"), "info": N_("Nota"), "ok": N_("Listo")}
    SECTIONS = {"personal": "personal", "address": "address", "dependents": "dependents", "income": "income",
                "deductions": "deductions", "payments": "payments", "state": "state", "local": "local",
                "federal": "summary", "review": "review"}
    SECTION_NAMES = {"personal": N_("Personal"), "address": N_("Dirección"), "dependents": N_("Dependientes"),
                     "income": N_("Ingresos"), "deductions": N_("Deducciones"), "payments": N_("Pagos"),
                     "state": N_("Estatal"), "local": N_("Local"), "federal": N_("Federal"), "review": N_("Revisión")}

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 8))
        outer.pack(fill="both", expand=True)
        self.count = ttk.Label(outer, text="", style="Big.TLabel")
        self.count.pack(anchor="w")
        self.tree = make_tree(outer, ("s", "sec", "m"), (_("Tipo"), _("Sección"), _("Detalle")), widths=(90, 110, 700), height=18)
        self.tree.frame.pack(fill="both", expand=True, pady=6)
        self.tree.tag_configure("error", foreground=COLORS["owe"])
        self.tree.tag_configure("aviso", foreground=COLORS["warn"])
        self.tree.tag_configure("ok", foreground=COLORS["refund"])
        self.tree.bind("<Double-1>", self._go)
        self.items = []
        if self.app.can("use_ai"):
            bar = ttk.Frame(outer, style="Card.TFrame")
            bar.pack(fill="x")
            ttk.Button(bar, text="✦ " + _("Revisar con IA"), style="Accent.TButton",
                       command=lambda: self.app.ask_ai_action(1)).pack(side="left")
            ttk.Button(bar, text="✦ " + _("¿Qué me falta para ahorrar?"),
                       command=lambda: self.app.ask_ai_action(3)).pack(side="left", padx=6)
            ttk.Label(bar, text=_("La IA complementa esta revisión automática; no la reemplaza."),
                      style="CardMuted.TLabel").pack(side="left", padx=6)

    def on_show(self):
        self.on_result(self.app.result)

    def on_result(self, res):
        if not res:
            return
        self.items = self.app.findings()
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i),
                             values=(_(self.SEV.get(f["severity"], f["severity"])),
                                     _(self.SECTION_NAMES.get(f["section"], f["section"])), f["message"]),
                             tags=(f["severity"],))
        n_err = sum(1 for f in self.items if f["severity"] == "error")
        n_warn = sum(1 for f in self.items if f["severity"] == "aviso")
        self.count.configure(text=tr("{e} errores  •  {w} avisos  •  {n} notas", e=n_err, w=n_warn,
                                     n=len(self.items) - n_err - n_warn))

    def _go(self, _e=None):
        sel = self.tree.selection()
        if sel:
            sec = self.items[int(sel[0])]["section"]
            self.app.workspace.show(self.SECTIONS.get(sec, "summary"))


# ============================================================================ 11. Resumen y presentar
class SummaryScreen(Screen):
    key, title = "summary", N_("Resumen y presentación")
    subtitle = N_("Resultado final, Formulario 1040 línea por línea y opciones para exportar el borrador y presentar su "
                  "declaración.")

    def build(self):
        outer = ttk.Frame(self.body, style="Card.TFrame", padding=(20, 8))
        outer.pack(fill="both", expand=True)
        cards = ttk.Frame(outer, style="Card.TFrame")
        cards.pack(fill="x")
        self.cards = {}
        for i, (k, t) in enumerate((("federal", _("Federal")), ("state", _("Estatal")), ("local", _("Local")), ("total", _("TOTAL")))):
            c = tk.Frame(cards, bg=COLORS["accent_light"], padx=14, pady=10)
            c.grid(row=0, column=i, sticky="ew", padx=(0, 10))
            cards.columnconfigure(i, weight=1)
            tk.Label(c, text=t, bg=COLORS["accent_light"], fg=COLORS["muted"], font=font(10)).pack(anchor="w")
            v = tk.Label(c, text="-", bg=COLORS["accent_light"], fg=COLORS["text"], font=font(14, "bold"))
            v.pack(anchor="w")
            self.cards[k] = v
        self.rates = ttk.Label(outer, text="", style="CardMuted.TLabel")
        self.rates.pack(anchor="w", pady=(8, 0))
        self.tree = make_tree(outer, ("l", "d", "v"), (_("Línea"), _("Descripción (Formulario 1040)"), _("Monto")),
                              widths=(60, 520, 140), height=14, anchors=("center", "w", "e"))
        self.tree.frame.pack(fill="both", expand=True, pady=8)
        bar = ttk.Frame(outer, style="Card.TFrame")
        bar.pack(fill="x")
        if self.app.can("export"):
            ttk.Button(bar, text=_("Llenar formularios oficiales del IRS  ›"), style="Accent.TButton",
                       command=lambda: self.app.workspace.show("forms")).pack(side="left")
            ttk.Button(bar, text=_("Resumen PDF"), command=self.app.export_pdf).pack(side="left", padx=6)
            ttk.Button(bar, text=_("Exportar HTML / imprimir"), command=self.app.export_html).pack(side="left", padx=(0, 6))
        if not self.app.readonly:
            ttk.Button(bar, text=_("Guardar declaración"), command=self.app.save).pack(side="left")
        if self.app.can("use_ai"):
            ttk.Button(bar, text="✦ " + _("Explicar mi resultado"), style="Soft.TButton",
                       command=lambda: self.app.ask_ai_action(2)).pack(side="left", padx=6)
        links = ttk.Frame(outer, style="Card.TFrame")
        links.pack(fill="x", pady=(10, 0))
        ttk.Label(links, text=_("Presentar y pagar:"), style="Section.TLabel").pack(side="left", padx=(0, 8))
        for text, url in ((_("IRS Free File"), "https://www.irs.gov/filing/free-file-do-your-federal-taxes-for-free"),
                          (_("Dónde enviar el 1040 en papel"), "https://www.irs.gov/filing/where-to-file-tax-returns-addresses-listed-by-return-type"),
                          (_("IRS Direct Pay"), "https://www.irs.gov/payments/direct-pay-with-bank-account"),
                          (_("¿Dónde está mi reembolso?"), "https://www.irs.gov/refunds")):
            lb = ttk.Label(links, text=text, foreground=COLORS["info"], cursor="hand2", style="Card.TLabel")
            lb.pack(side="left", padx=8)
            lb.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        self.state_link = ttk.Label(links, text="", foreground=COLORS["info"], cursor="hand2", style="Card.TLabel")
        self.state_link.pack(side="left", padx=8)
        self.state_link.bind("<Button-1>", lambda e: webbrowser.open(self.app.result["state"]["url"])
                             if self.app.result and self.app.result["state"].get("url") else None)
        ttk.Label(outer, text=_("Nota: esta aplicación no presenta electrónicamente. En 'Formularios oficiales del IRS' "
                                "genera el 1040 y sus anexos llenos en PDF para firmar y enviar por correo, o puede usar un "
                                "proveedor de e-file autorizado."), style="CardMuted.TLabel", wraplength=860).pack(anchor="w", pady=6)

    def on_result(self, res):
        from ..reports import LINE_LABELS
        fed, st, loc = res["federal"], res["state"], res["local"]
        for k, bal in (("federal", fed["balance"]), ("state", st["balance"]), ("local", loc["balance"]),
                       ("total", res["summary"]["total_balance"])):
            self.cards[k].configure(text=balance_text(bal), fg=COLORS["refund"] if bal >= 0 else COLORS["owe"])
        self.rates.configure(text=tr("AGI {a}  •  Ingreso tributable {t}  •  Tasa marginal {m}%  •  Tasa efectiva {e}%  •  "
                                     "Fecha límite {d}", a=fmt_money(fed["agi"]), t=fmt_money(fed["taxable_income"]),
                                     m=f"{fed['marginal_rate'] * 100:.0f}", e=f"{fed['effective_rate'] * 100:.2f}",
                                     d=fed["deadline"]))
        self.tree.delete(*self.tree.get_children())
        for k, lbl in LINE_LABELS:
            self.tree.insert("", "end", values=(k, _(lbl), fmt_money(fed["lines"].get(k, 0))))
        self.state_link.configure(text=tr("Sitio de {s}", s=st["name"]) if st.get("url") else "")


SCREENS = [PersonalScreen, AddressScreen, DependentsScreen, IncomeScreen, DeductionsScreen, CreditsScreen,
           PaymentsScreen, StateScreen, LocalScreen, ReviewScreen, SummaryScreen]
