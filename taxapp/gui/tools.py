"""Herramientas / Tools: explorador por estado y condado, calculadora rapida y guia."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import data_loader, counties
from ..engine import compute_all, fmt_money
from .. import i18n
from ..i18n import _, tr, reverse
from ..local import localities_for_state, county_tax_info
from ..models import TaxReturn, Person, W2, Dependent, FILING_STATUSES
from .screens import STATE_KINDS, NONE_LOC, loc_from_model, loc_to_model
from .widgets import COLORS, font, make_tree, Form


# ============================================================================ Explorador estado/condado
class ExplorerWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(_("Explorador de impuestos por estado y condado"))
        self.geometry("980x680")
        self.configure(bg=COLORS["card"])
        top = ttk.Frame(self, style="Card.TFrame", padding=12)
        top.pack(fill="x")
        ttk.Label(top, text=_("Año"), style="Card.TLabel").pack(side="left")
        self.year = tk.StringVar(value=str(app.ret.tax_year if app.ret else 2026))
        ttk.Combobox(top, textvariable=self.year, values=["2025", "2026"], width=6, state="readonly").pack(side="left", padx=6)
        ttk.Label(top, text=_("Estado"), style="Card.TLabel").pack(side="left", padx=(12, 0))
        labels = [data_loader.state_label(c) for c in data_loader.state_codes_sorted()]
        self.state = tk.StringVar(value=data_loader.state_label(app.ret.address.state) if app.ret and app.ret.address.state else labels[0])
        ttk.Combobox(top, textvariable=self.state, values=labels, width=28, state="readonly").pack(side="left", padx=6)
        ttk.Label(top, text=_("Condado"), style="Card.TLabel").pack(side="left", padx=(12, 0))
        self.county = tk.StringVar()
        self.county_cb = ttk.Combobox(top, textvariable=self.county, width=26)
        self.county_cb.pack(side="left", padx=6)
        for v in (self.year, self.state, self.county):
            v.trace_add("write", lambda *_a: self.refresh())

        body = ttk.Frame(self, style="Card.TFrame", padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)
        self.tree = make_tree(body, ("s", "r", "m"), (_("Desde (soltero)"), _("Tasa"), _("Desde (casados conjunto)")),
                              widths=(160, 90, 180), height=14, anchors=("e", "center", "e"))
        self.tree.frame.pack(side="left", fill="y")
        self.text = tk.Text(body, wrap="word", relief="flat", background=COLORS["accent_light"], font=font(10), padx=12, pady=10)
        self.text.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.text.tag_configure("h", font=font(11, "bold"), foreground=COLORS["primary"])
        self.refresh()

    def refresh(self):
        y = int(self.year.get())
        code = data_loader.code_from_label(self.state.get())
        cl = counties.counties_for(code)
        self.county_cb.configure(values=cl)
        sd = data_loader.states(y)[code]
        info = data_loader.states_info()[code]
        self.tree.delete(*self.tree.get_children())
        if sd.get("brackets"):
            s, m = sd["brackets"]["single"], sd["brackets"]["mfj"]
            for i in range(max(len(s), len(m))):
                a = s[i] if i < len(s) else None
                b = m[i] if i < len(m) else None
                rate = (a or b)[1]
                self.tree.insert("", "end", values=(f"${a[0]:,.0f}" if a else "", f"{rate * 100:.3g}%", f"${b[0]:,.0f}" if b else ""))
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", tr("{n} ({c}) — año fiscal {y}", n=info["name"], c=code, y=y) + "\n", "h")
        t.insert("end", _(STATE_KINDS[sd["type"]]) + ".\n")
        std = sd.get("std_deduction") or {}
        if sd.get("uses_federal_deduction"):
            t.insert("end", _("Parte del ingreso tributable federal (usa la deducción federal).") + "\n")
        elif sd.get("std_from_federal"):
            t.insert("end", _("Deducción estándar igual a la federal.") + "\n")
        elif std.get("single") or std.get("mfj"):
            t.insert("end", tr("Deducción estándar: ${a} soltero • ${b} casados", a=f"{std.get('single', 0):,}",
                               b=f"{std.get('mfj', 0):,}")
                     + (tr(" • ${h} cabeza de familia", h=f"{std['hoh']:,}") if 'hoh' in std else "") + "\n")
        ex = sd.get("exemption") or {}
        if ex.get("per_person") or ex.get("dependent"):
            kind = _("Crédito personal") if sd.get("exemption_is_credit") else _("Exención personal")
            t.insert("end", tr("{k}: ${a} por persona • ${b} por dependiente", k=kind, a=f"{ex.get('per_person', 0):,}",
                               b=f"{ex.get('dependent', 0):,}") + "\n")
        if info.get("form"):
            t.insert("end", tr("Formulario: {f} • {a}", f=info["form"], a=info["agency"]) + f"\n{info['url']}\n")
        t.insert("end", tr("Fecha límite: {d}", d=f"{y + 1}-{info['deadline_mmdd']}") + "\n")
        stx = info["sales_tax"]
        t.insert("end", "\n" + _("Impuesto a las ventas") + "\n", "h")
        t.insert("end", tr("Estatal {a}% • local promedio {b}% • combinado {c}%", a=stx["state"], b=stx["avg_local"],
                           c=stx["combined"]) + "\n")
        t.insert("end", "\n" + _("Condado") + "\n", "h")
        t.insert("end", county_tax_info(y, code, self.county.get()) + "\n")
        if not cl:
            t.insert("end", _("(Lista de condados no descargada para este estado: use Herramientas > Actualizar lista de condados)") + "\n")
        ld = data_loader.local(y)["states"].get(code, {})
        if ld.get("localities"):
            t.insert("end", "\n" + _("Ciudades / jurisdicciones con impuesto local") + "\n", "h")
            for nm, j in ld["localities"].items():
                t.insert("end", f"• {_(nm)}: {_(j.get('note', ''))}\n")
        if sd.get("notes"):
            t.insert("end", "\n" + _("Notas") + "\n", "h")
            for n in sd["notes"]:
                t.insert("end", f"• {_(n)}\n")
        t.configure(state="disabled")


# ============================================================================ Calculadora rapida
class QuickCalcWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title(_("Calculadora rápida"))
        self.geometry("880x620")
        self.configure(bg=COLORS["card"])
        self.r = TaxReturn(tax_year=2026)
        self.r.taxpayer = Person(first_name="Estimado", dob="1990-01-01")
        self.r.w2s = [W2(employer="Empleo")]
        self.kids = tk.StringVar(value="0")
        self.senior = tk.BooleanVar(value=False)
        left = ttk.Frame(self, style="Card.TFrame", padding=16)
        left.pack(side="left", fill="y")
        f = Form(left, lambda: self.r, self.calc, label_width=22)
        f.section(_("Estimado rápido"))
        f.combo(_("Año fiscal"), "tax_year", ["2025", "2026"], to_model=int, from_model=str)
        status_keys = list(FILING_STATUSES.values())
        f.combo(_("Estado civil"), "filing_status", [_(v) for v in status_keys],
                to_model=lambda v: {b: a for a, b in FILING_STATUSES.items()}[reverse(v, status_keys)],
                from_model=lambda k: _(FILING_STATUSES[k]))
        fa = Form(left, lambda: self.r.address, self.calc, label_width=22)
        fa.row = f.row
        labels = [data_loader.state_label(c) for c in data_loader.state_codes_sorted()]
        fa.combo(_("Estado"), "state", labels, to_model=data_loader.code_from_label,
                 from_model=lambda c: data_loader.state_label(c) if c else "", on_select=self._state)
        self.county_cb = fa.combo(_("Condado"), "county", [], readonly=False)
        self.loc_cb = fa.combo(_("Ciudad con impuesto"), "locality", [],
                               to_model=lambda v: loc_to_model(v, localities_for_state(self.r.tax_year, self.r.address.state)),
                               from_model=loc_from_model)
        fw = Form(left, lambda: self.r.w2s[0], self.calc, label_width=22)
        fw.row = fa.row
        fw.money(_("Salario anual (W-2)"), "box1_wages")
        fw.money(_("Retención federal"), "box2_fed_withheld")
        fi = Form(left, lambda: self.r.income, self.calc, label_width=22)
        fi.row = fw.row
        fi.money(_("Ingreso de negocio propio"), "business_gross")
        ttk.Label(left, text=_("Hijos menores de 17"), style="Card.TLabel").grid(row=fi.row, column=0, sticky="w", padx=4)
        ttk.Spinbox(left, from_=0, to=8, textvariable=self.kids, width=5).grid(row=fi.row, column=1, sticky="w")
        ttk.Checkbutton(left, text=_("Tengo 65 años o más"), variable=self.senior).grid(row=fi.row + 1, column=0, columnspan=2, sticky="w", padx=4)
        self.kids.trace_add("write", lambda *_a: self.calc())
        self.senior.trace_add("write", lambda *_a: self.calc())
        right = ttk.Frame(self, style="Card.TFrame", padding=16)
        right.pack(side="left", fill="both", expand=True)
        self.tree = make_tree(right, ("c", "v"), (_("Concepto"), _("Monto")), widths=(300, 140), height=20, anchors=("w", "e"))
        self.tree.frame.pack(fill="both", expand=True)
        self.calc()

    def _state(self):
        code = self.r.address.state
        self.county_cb.configure(values=counties.counties_for(code))
        self.loc_cb.configure(values=[_(NONE_LOC)] + [_(k) for k in localities_for_state(self.r.tax_year, code)])

    def calc(self):
        try:
            n = int(self.kids.get() or 0)
        except ValueError:
            n = 0
        self.r.dependents = [Dependent(first_name=f"K{i + 1}", dob=f"{self.r.tax_year - 8}-06-01", ssn="000-00-0000",
                                       has_ssn=True) for i in range(n)]
        self.r.taxpayer.dob = "1955-01-01" if self.senior.get() else "1990-01-01"
        if self.r.filing_status in ("mfj", "mfs"):
            self.r.spouse = Person(first_name="Conyuge", dob=self.r.taxpayer.dob)
        res = compute_all(self.r)
        fed, st, loc = res["federal"], res["state"], res["local"]
        wages = self.r.w2s[0].box1_wages
        fica = min(wages, data_loader.federal(self.r.tax_year)["se"]["ss_wage_base"]) * 0.062 + wages * 0.0145
        gross = wages + self.r.income.schedule_c_profit()
        net = gross - fed["total_tax"] - st["tax"] - loc["total"] - fica
        rows = [(_("Ingreso bruto"), gross), (_("AGI"), fed["agi"]), (_("Deducción"), fed["deduction"] + fed["sched1a"]["total"]),
                (_("Ingreso tributable federal"), fed["taxable_income"]),
                (_("Impuesto federal (después de créditos)"), fed["tax_after_credits"]),
                (_("Créditos reembolsables (EITC/ACTC)"), fed["credits"]["eitc"] + fed["credits"]["actc"]),
                (_("Impuesto de trabajo independiente"), fed["other_taxes"]["se_tax"]),
                (_("Impuesto estatal"), st["tax"]), (_("Impuestos locales"), loc["total"]),
                (_("Seguro Social + Medicare (empleado)"), fica),
                (_("Ingreso neto estimado"), net),
                (_("Federal: reembolso(+)/a pagar(-)"), fed["balance"])]
        self.tree.delete(*self.tree.get_children())
        for k, v in rows:
            self.tree.insert("", "end", values=(k, fmt_money(v)))
        self.tree.insert("", "end", values=(_("Tasa marginal federal"), f"{fed['marginal_rate'] * 100:.0f}%"))
        self.tree.insert("", "end", values=(_("Tasa efectiva total"), f"{(gross - net) / gross * 100:.1f}%" if gross else "-"))


# ============================================================================ Guia
class GuideWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title(_("Guía de impuestos de EE.UU."))
        self.geometry("900x720")
        txt = tk.Text(self, wrap="word", font=font(10), padx=18, pady=14, relief="flat")
        vsb = ttk.Scrollbar(self, command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h1", font=font(16, "bold"), foreground=COLORS["primary"], spacing3=6)
        txt.tag_configure("h2", font=font(12, "bold"), foreground=COLORS["primary"], spacing1=10, spacing3=4)
        name = "RESEARCH_EN.md" if i18n.is_en() else "INVESTIGACION.md"
        path = data_loader.app_dir() / "docs" / name
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = [tr("No se encontró docs/{n}", n=name)]
        for ln in lines:
            if ln.startswith("# "):
                txt.insert("end", ln[2:] + "\n", "h1")
            elif ln.startswith("## ") or ln.startswith("### "):
                txt.insert("end", ln.lstrip("#").strip() + "\n", "h2")
            elif ln.startswith("|") and set(ln.replace("|", "").strip()) <= set("-: "):
                continue
            else:
                txt.insert("end", ln.replace("**", "").replace("`", "") + "\n")
        txt.configure(state="disabled")
