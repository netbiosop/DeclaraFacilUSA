"""Convierte una declaración calculada en los valores de cada formulario oficial.

Cada constructor recibe la declaración (TaxReturn) y el resultado del motor federal, y devuelve una o más "instancias"
(formulario + valores + páginas). Las claves de los valores son las del mapa data/formularios/<año>.json.
Los montos se escriben en dólares enteros (el IRS lo permite si se redondean todos; los totales se calculan con
centavos y solo se redondea el resultado).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .. import data_loader
from ..federal import pick
from ..i18n import _, tr
from ..models import TaxReturn, age_at_year_end


# ------------------------------------------------------------------------------------------------- utilidades
def whole(v: float) -> int:
    """Redondeo al dólar más cercano (0.50 hacia arriba, como pide el IRS)."""
    return int(math.floor(abs(v) + 0.5)) * (1 if v >= 0 else -1)


def m(v, zero: bool = False) -> str:
    """Monto en dólares enteros: 1,234 ; negativo entre paréntesis (1,234); vacío si es 0 (salvo zero=True)."""
    if v is None:
        return ""
    w = whole(float(v))
    if w == 0:
        return "0" if zero else ""
    return f"{w:,}" if w > 0 else f"({-w:,})"


def mpos(v, zero: bool = False) -> str:
    """Monto positivo para casillas que ya traen paréntesis impresos en el formulario."""
    return m(abs(v or 0.0), zero)


def digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def upper(s: str) -> str:
    return (s or "").strip().upper()


@dataclass
class Instance:
    form: str
    values: Dict[str, object]
    pages: Optional[List[int]] = None      # páginas del PDF a conservar (None = todas)
    label: str = ""                        # p. ej. "Box A (1/2)" o el nombre del estudiante


@dataclass
class Plan:
    instances: List[Instance] = field(default_factory=list)
    statements: List[dict] = field(default_factory=list)   # hojas adicionales: {"title", "lines"}
    warnings: List[str] = field(default_factory=list)
    main_form: str = "1040"

    def forms(self) -> List[str]:
        out = []
        for inst in self.instances:
            if inst.form not in out:
                out.append(inst.form)
        return out


class Builder:
    def __init__(self, ret: TaxReturn, res: dict, preparer: Optional[dict] = None, use_sr: Optional[bool] = None,
                 lang: str = "en"):
        self.lang = lang          # idioma de los formularios: "es" usa las versiones oficiales en español
        self.ret = ret
        self.res = res
        self.fed = res["federal"]
        self.L = self.fed["lines"]
        self.d = self.fed.get("detail", {})
        self.data = data_loader.federal(ret.tax_year)
        self.preparer = preparer or {}
        self.year = ret.tax_year
        st = ret.filing_status
        self.status = st
        self.other = "mfj" if st in ("mfj", "qss") else "other"
        tp_age = ret.taxpayer_age()
        sp_age = age_at_year_end(ret.spouse.dob, self.year) if ret.has_spouse() else None
        self.tp65 = tp_age is not None and tp_age >= 65
        self.sp65 = ret.is_joint() and sp_age is not None and sp_age >= 65
        sr_ok = self.tp65 or self.sp65
        self.main = "1040sr" if (sr_ok if use_sr is None else (use_sr and sr_ok)) else "1040"
        self.plan = Plan(main_form=self.main)

    # ------------------------------------------------------------------ comunes
    def names(self) -> str:
        r = self.ret
        tp = f"{r.taxpayer.first_name} {r.taxpayer.last_name}".strip()
        if r.is_joint():
            sp = f"{r.spouse.first_name} {r.spouse.last_name}".strip()
            if sp:
                if r.spouse.last_name and r.spouse.last_name == r.taxpayer.last_name:
                    return upper(f"{r.taxpayer.first_name} & {r.spouse.first_name} {r.taxpayer.last_name}")
                return upper(f"{tp} & {sp}")
        return upper(tp)

    def ssn(self) -> str:
        return digits(self.ret.taxpayer.ssn)

    def header(self, name_key="name", ssn_key="ssn") -> dict:
        return {name_key: self.names(), ssn_key: self.ssn()}

    def add(self, form, values, pages=None, label=""):
        self.plan.instances.append(Instance(form, {k: v for k, v in values.items() if v not in (None, "", False)},
                                            pages, label))

    def warn(self, msg):
        if msg not in self.plan.warnings:
            self.plan.warnings.append(msg)

    def form_lang(self, fid: str) -> str:
        """Idioma real de un formulario: español solo si el IRS publica esa versión y está incluida."""
        from . import catalog
        return "es" if self.lang == "es" and catalog.has_spanish(self.year, fid) else "en"

    def rel(self, relationship: str, fid: str) -> str:
        """Parentesco en el idioma del formulario (inglés en los formularios en inglés)."""
        if self.form_lang(fid) == "es" and relationship:
            return relationship
        return _rel_en(relationship)

    def t(self, en: str, es: str) -> str:
        return es if self.lang == "es" else en

    def statement(self, title, lines):
        self.plan.statements.append({"title": title, "lines": lines})

    # ------------------------------------------------------------------ qué formularios hacen falta
    def build(self) -> Plan:
        f, ret, inc = self.fed, self.ret, self.ret.income
        need = {
            "s1": abs(self.L.get("8", 0)) >= 0.5 or self.L.get("10", 0) >= 0.5,
            "s1a": f["sched1a"]["total"] >= 0.5,
            "s2": f["amt"] >= 0.5 or f["other_taxes"]["total"] >= 0.5,
            "sa": f["itemize"],
            "sb": inc.taxable_interest > 1500 or inc.ordinary_dividends > 1500 or ret.filing.foreign_account
                  or ret.filing.foreign_trust,
            "sc": bool(inc.business_gross or inc.schedule_c_expenses()),
            "sd": self._needs_sched_d(),
            "sse": f["se_tax"] >= 0.5,
            "2441": f["credits"]["cdcc"] >= 0.5 or ret.credits.dependent_care_benefits > 0,
            "6251": f["amt"] >= 0.5,
            "sei": f["credits"]["eitc"] >= 0.5 and f["credits"]["n_eitc"] > 0,
            "s8812": (f["credits"]["ctc_nonref"] + f["credits"]["actc"]) >= 0.5,
            "8863": (f["credits"]["education_nonref"] + f["credits"]["aotc_refundable"]) >= 0.5,
            "8889": f.get("hsa", 0) >= 0.5 or ret.deductions.hsa_employer > 0,
            "8880": f["credits"]["savers"] >= 0.5,
            "8995": f["qbi"] >= 0.5,
            "8959": f["other_taxes"]["addl_medicare"] >= 0.5 or f["payments"]["addl_medicare_withheld"] >= 1,
            "8960": f["other_taxes"]["niit"] >= 0.5,
        }
        sched3 = (self.L.get("20", 0) >= 0.5 or self.L.get("31", 0) >= 0.5)
        self.form_1040()
        builders = [("s1", self.s1), ("s1a", self.s1a), ("s2", self.s2), ("s3", self.s3), ("sa", self.sa),
                    ("sb", self.sb), ("sc", self.sc), ("sd", self.sd), ("sse", self.sse), ("2441", self.f2441),
                    ("6251", self.f6251), ("sei", self.sei), ("s8812", self.s8812), ("8863", self.f8863),
                    ("8889", self.f8889), ("8880", self.f8880), ("8995", self.f8995), ("8959", self.f8959),
                    ("8960", self.f8960)]
        for fid, fn in builders:
            if fid == "s3":
                if sched3:
                    fn()
            elif need.get(fid):
                fn()
        if self.L.get("37", 0) >= 1:
            self.f1040v()
        return self.plan

    def _needs_sched_d(self) -> bool:
        inc = self.ret.income
        detail = bool(inc.sales) or inc.short_term_gain or inc.long_term_gain or inc.capital_loss_carryover
        return bool(detail)

    # ------------------------------------------------------------------ 1040 / 1040-SR
    def form_1040(self):
        r, L, fed = self.ret, self.L, self.fed
        tp, sp, a, fi = r.taxpayer, r.spouse, r.address, r.filing
        v = {
            "first": upper(tp.first_name), "last": upper(tp.last_name), "ssn": digits(tp.ssn),
            "street": upper(a.street), "apt": upper(a.apt), "city": upper(a.city), "state": upper(a.state),
            "zip": a.zip.strip(), "home_us": True,
            "pec_you": tp.presidential_fund, "pec_spouse": r.is_joint() and sp.presidential_fund,
            "fs_" + self.status: True,
            "digital_yes": fi.digital_assets, "digital_no": not fi.digital_assets,
        }
        if r.is_joint():
            v.update({"sp_first": upper(sp.first_name), "sp_last": upper(sp.last_name), "sp_ssn": digits(sp.ssn)})
        elif self.status == "mfs":
            v.update({"sp_ssn": digits(sp.ssn), "mfs_spouse_name": upper(sp.full_name())})
        if self.status in ("hoh", "qss") and fi.hoh_qualifying_name:
            v["hoh_child"] = upper(fi.hoh_qualifying_name)
        if self.status in ("mfs", "hoh") and fi.lived_apart:
            v["lived_apart"] = True
        # Dependientes
        deps = r.dependents
        n_ctc_allowed = fed["credits"]["n_ctc"] > 0
        for i, d in enumerate(deps[:4]):
            ctc = d.qualifies_ctc(self.year) and n_ctc_allowed
            v.update({f"dep{i}_first": upper(d.first_name), f"dep{i}_last": upper(d.last_name),
                      f"dep{i}_ssn": digits(d.ssn), f"dep{i}_rel": upper(self.rel(d.relationship, self.main)),
                      f"dep{i}_lived": d.months_lived > 6, f"dep{i}_us": d.months_lived > 6 and d.lived_in_us,
                      f"dep{i}_student": d.full_time_student, f"dep{i}_disabled": d.disabled,
                      f"dep{i}_ctc": ctc, f"dep{i}_odc": not ctc})
        if len(deps) > 4:
            v["dep_more"] = True
            lines = []
            for d in deps[4:]:
                ctc = d.qualifies_ctc(self.year) and n_ctc_allowed
                lines.append(f"{upper(d.full_name())}  SSN {_fmt_ssn(d.ssn)}  {upper(self.rel(d.relationship, self.main))}  "
                             f"{'CTC' if ctc else 'ODC'}")
            self.statement(self.t("Form 1040 - Dependents (continued)", "Formulario 1040 - Dependientes (continuacion)"), lines)
        # Ingresos
        v.update({"L1a": m(L["1a"]), "L1z": m(L["1z"]), "L2a": m(L["2a"]), "L2b": m(L["2b"]), "L3a": m(L["3a"]),
                  "L3b": m(L["3b"]), "L4a": m(L["4a"]), "L4b": m(L["4b"]), "L5a": m(L["5a"]), "L5b": m(L["5b"]),
                  "L6a": m(L["6a"]), "L6b": m(L["6b"]), "L7a": m(L["7"]), "L8": m(L["8"]), "L9": m(L["9"], True),
                  "L10": m(L["10"]), "L11a": m(L["11"], True), "L11b": m(L["11"], True)})
        inc = r.income
        if inc.capital_gain_distributions and not self._needs_sched_d():
            v["L7b_nosd"] = True
        # Deducción
        v.update({"L12a_you": tp.can_be_claimed, "L12d_you65": self.tp65, "L12d_youblind": tp.blind})
        if r.is_joint():
            v.update({"L12d_sp65": self.sp65, "L12d_spblind": sp.blind})
        v.update({"L12e": m(L["12"], True), "L13a": m(L["13a"]), "L13b": m(L["13b"]), "L14": m(L["14"], True),
                  "L15": m(L["15"], True), "L16": m(L["16"], True), "L17": m(L["17"]), "L18": m(L["18"], True),
                  "L19": m(L["19"]), "L20": m(L["20"]), "L21": m(L["21"]), "L22": m(L["22"], True),
                  "L23": m(L["23"]), "L24": m(L["24"], True)})
        # Pagos
        v.update({"L25a": m(L["25a"]), "L25b": m(L["25b"]), "L25c": m(L.get("25c", 0)), "L25d": m(L["25d"], True),
                  "L26": m(L["26"]), "L27a": m(L["27"]), "L28": m(L["28"]), "L29": m(L["29"]), "L31": m(L["31"]),
                  "L32": m(L["32"]), "L33": m(L["33"], True)})
        if not r.credits.claim_eitc:
            v["L27c_noeic"] = True
        refund = L["34"]
        if refund >= 0.5:
            next_year = min(fi.apply_to_next_year, refund)
            v.update({"L34": m(refund), "L35a": m(refund - next_year, True), "L36": m(next_year)})
            if fi.direct_deposit and refund - next_year >= 0.5:
                v.update({"routing": digits(fi.routing), "account": fi.account.replace(" ", "").replace("-", ""),
                          "acct_checking": fi.account_type != "savings", "acct_savings": fi.account_type == "savings"})
        if L["37"] >= 0.5:
            v["L37"] = m(L["37"])
        # Tercero designado y firma
        if fi.designee and fi.designee_name:
            v.update({"designee_yes": True, "designee_name": upper(fi.designee_name),
                      "designee_phone": fi.designee_phone, "designee_pin": digits(fi.designee_pin)})
        else:
            v["designee_no"] = True
        v.update({"occupation": upper(tp.occupation), "ippin": digits(tp.ip_pin), "phone": a.phone, "email": a.email})
        if r.is_joint():
            v.update({"sp_occupation": upper(sp.occupation), "sp_ippin": digits(sp.ip_pin)})
        p = self.preparer
        if fi.use_preparer and p.get("name"):
            v.update({"prep_name": upper(p.get("name")), "prep_ptin": upper(p.get("ptin")),
                      "prep_self": bool(p.get("self_employed")), "prep_firm": upper(p.get("firm")),
                      "prep_phone": p.get("firm_phone", ""), "prep_address": upper(p.get("firm_address")),
                      "prep_ein": _fmt_ein(p.get("firm_ein"))})
        if L["37"] >= 1000:
            self.warn(_("Debe más de $1,000: el IRS puede cobrar una multa por pagos estimados insuficientes (línea 38, "
                        "Formulario 2210). La aplicación no la calcula; el IRS le enviará la factura si corresponde."))
        # El 1040-SR tiene una 4.ª página (tabla de deducción estándar) que no se presenta.
        self.add(self.main, v, pages=[0, 1, 2] if self.main == "1040sr" else None)

    # ------------------------------------------------------------------ Anexo 1
    def s1(self):
        f, inc, ded = self.fed, self.ret.income, self.ret.deductions
        v = self.header()
        other8 = inc.gambling + inc.other_income
        v.update({"L1": m(inc.state_refund_taxable), "L3": m(f["profit"]), "L7": m(inc.unemployment),
                  "L8b": m(inc.gambling), "L8z": m(inc.other_income),
                  "L8z_type": upper(inc.other_income_desc or ("OTHER INCOME" if inc.other_income else "")),
                  "L9": m(other8), "L10": m(self.L["8"], True),
                  "L11": m(f["educator"]), "L13": m(f.get("hsa", 0)), "L15": m(f["half_se"]),
                  "L17": m(f["se_health"]), "L20": m(ded.ira_deduction), "L21": m(f["student_loan"]),
                  "L24z": m(ded.other_adjustments), "L24z_type": "OTHER ADJUSTMENTS" if ded.other_adjustments else "",
                  "L25": m(ded.other_adjustments), "L26": m(self.L["10"], True)})
        self.add("s1", v)

    # ------------------------------------------------------------------ Anexo 1-A
    def s1a(self):
        f, inc, ded, d = self.fed, self.ret.income, self.ret.deductions, self.d
        magi = f["magi"]
        v = self.header()
        v.update({"L1": m(magi, True), "L3": m(magi, True)})
        if inc.qualified_tips > 0 and self.status != "mfs":
            t = self.data["tips"]
            l7 = min(inc.qualified_tips, t["max"])
            start = pick(t["phaseout_start"], self.status)
            v.update({"L4a": m(inc.qualified_tips), "L4c": m(inc.qualified_tips), "L6": m(inc.qualified_tips),
                      "L7": m(l7), "L8": m(magi, True), "L9": m(start)})
            excess = max(0.0, magi - start)
            if excess > 0:
                steps = math.floor(excess / 1000)
                v.update({"L10": m(excess), "L11": str(steps), "L12": m(steps * t["reduce_per_1000"], True)})
            v["L13"] = m(d.get("tips", 0), True)
        if inc.qualified_overtime > 0 and self.status != "mfs":
            o = self.data["overtime"]
            l15 = min(inc.qualified_overtime, pick(o["max"], self.status))
            start = pick(o["phaseout_start"], self.status)
            v.update({"L14a": m(inc.qualified_overtime), "L14c": m(inc.qualified_overtime), "L15": m(l15),
                      "L16": m(magi, True), "L17": m(start)})
            excess = max(0.0, magi - start)
            if excess > 0:
                steps = math.floor(excess / 1000)
                v.update({"L18": m(excess), "L19": str(steps), "L20": m(steps * o["reduce_per_1000"], True)})
            v["L21"] = m(d.get("overtime", 0), True)
        if ded.car_loan_interest > 0:
            c = self.data["car_loan"]
            start = pick(c["phaseout_start"], self.status)
            v.update({"L22a_vin": upper(ded.car_vin).replace(" ", ""), "L22a_iii": m(ded.car_loan_interest),
                      "L23": m(ded.car_loan_interest), "L24": m(min(ded.car_loan_interest, c["max"])),
                      "L25": m(magi, True), "L26": m(start)})
            excess = max(0.0, magi - start)
            if excess > 0:
                steps = math.ceil(excess / 1000)
                v.update({"L27": m(excess), "L28": str(steps), "L29": m(steps * c["reduce_per_1000"], True)})
            v["L30"] = m(d.get("car", 0), True)
        if d.get("senior", 0) > 0:
            s = self.data["senior"]
            start = pick(s["phaseout_start"], self.status)
            excess = max(0.0, magi - start)
            per = max(0.0, s["amount"] - excess * s["rate"])
            v.update({"L31": m(magi, True), "L32": m(start), "L33": m(excess, True),
                      "L34": m(excess * s["rate"]) if excess > 0 else "", "L35": m(per, True)})
            tp_ok = self.tp65 and self.ret.taxpayer.valid_ssn_for_work
            sp_ok = self.sp65 and self.ret.spouse.valid_ssn_for_work
            v.update({"L36a": m(per) if tp_ok else "", "L36b": m(per) if sp_ok else "",
                      "L37": m(d.get("senior", 0), True)})
        v["L38"] = m(f["sched1a"]["total"], True)
        self.add("s1a", v)

    # ------------------------------------------------------------------ Anexo 2
    def s2(self):
        f = self.fed
        o = f["other_taxes"]
        v = self.header()
        v.update({"L2": m(f["amt"]), "L3": m(f["amt"]), "L4": m(o["se_tax"]), "L11": m(o["addl_medicare"]),
                  "L12": m(o["niit"]), "L21": m(o["total"])})
        self.add("s2", v)

    # ------------------------------------------------------------------ Anexo 3
    def s3(self):
        c, cr, d = self.fed["credits"], self.ret.credits, self.d
        v = self.header()
        v.update({"L1": m(c["foreign"]), "L2": m(c["cdcc"]), "L3": m(c["education_nonref"]), "L4": m(c["savers"]),
                  "L6z": m(c["other_nonref"]), "L6z_type": "OTHER CREDITS" if c["other_nonref"] >= 0.5 else "",
                  "L7": m(c["other_nonref"]), "L8": m(self.L["20"], True),
                  "L10": m(d.get("extension", 0)), "L11": m(d.get("excess_ss", 0)),
                  "L13z": m(cr.other_refundable), "L13z_type": "OTHER" if cr.other_refundable else "",
                  "L14": m(cr.other_refundable), "L15": m(self.L["31"])})
        if c["foreign"] > (600 if self.ret.is_joint() else 300):
            self.warn(_("Crédito por impuestos extranjeros mayor de $300 ($600 en conjunto): puede requerir el "
                        "Formulario 1116, que no se genera aquí."))
        self.add("s3", v)

    # ------------------------------------------------------------------ Anexo A
    def sa(self):
        f, ded = self.fed, self.ret.deductions
        it = f["itemized_detail"]
        agi = f["agi"]
        v = self.header()
        floor = self.data["medical_floor"] * agi
        v.update({"L1": m(ded.medical), "L2": m(agi, True), "L3": m(floor), "L4": m(it["medical"], True)})
        salt_first = it["salt_raw"] - ded.real_estate_tax - ded.personal_property_tax
        v.update({"L5a_sales": ded.salt_use_sales_tax, "L5a": m(salt_first), "L5b": m(ded.real_estate_tax),
                  "L5c": m(ded.personal_property_tax), "L5d": m(it["salt_raw"]), "L5e": m(it["salt"]),
                  "L7": m(it["salt"], True)})
        mort = ded.mortgage_interest + ded.mortgage_points
        v.update({"L8a": m(mort), "L8e": m(mort), "L9": m(ded.investment_interest), "L10": m(it["interest"], True)})
        v.update({"L11": m(ded.charity_cash), "L12": m(ded.charity_noncash), "L14": m(it["charity"], True)})
        if abs(it["charity"] - ded.charity_cash - ded.charity_noncash) >= 1:
            self.warn(_("Las donaciones superan el límite por AGI; el Anexo A línea 14 muestra el monto permitido "
                        "(el resto se arrastra al año siguiente)."))
        v.update({"L15": m(ded.casualty_loss), "L16": m(ded.other_itemized),
                  "L16_type": "OTHER" if ded.other_itemized else "", "L17": m(f["itemized_net"], True)})
        if ded.mode == "itemized" and f["itemized_net"] < f["standard_deduction"]:
            v["L18"] = True
        if ded.charity_noncash > 500:
            self.warn(_("Donaciones en especie de más de $500: adjunte el Formulario 8283 (no se genera aquí)."))
        self.add("sa", v)

    # ------------------------------------------------------------------ Anexo B
    def sb(self):
        inc, fi = self.ret.income, self.ret.filing
        v = self.header()

        def payers(lst, total, n_max, key, what):
            rows = [(upper(p.name), p.amount) for p in lst if p.name or p.amount]
            if not rows and total:
                rows = [(what, total)]
                self.warn(tr("Anexo B: falta la lista de pagadores de {w}; se escribió una sola línea con el total.",
                             w=_("intereses") if key == "int" else _("dividendos")))
            elif rows and abs(sum(a for _n, a in rows) - total) >= 1:
                self.warn(tr("Anexo B: la suma de los pagadores ({a}) no coincide con el total declarado ({b}).",
                             a=m(sum(a for _n, a in rows), True), b=m(total, True)))
            if len(rows) > n_max:
                extra = rows[n_max - 1:]
                rows = rows[:n_max - 1] + [("SEE ATTACHED STATEMENT", sum(a for _n, a in extra))]
                self.statement(self.t(f"Schedule B - {'Interest' if key == 'int' else 'Dividends'} (continued)",
                                      f"Anexo B - {'Intereses' if key == 'int' else 'Dividendos'} (continuacion)"),
                               [f"{n:<50} {m(a, True):>12}" for n, a in extra])
            for i, (n, a) in enumerate(rows):
                v[f"{key}{i}_name"] = n
                v[f"{key}{i}_amt"] = m(a, True)

        if inc.taxable_interest:
            payers(inc.interest_payers, inc.taxable_interest, 14, "int", "VARIOUS (SEE FORMS 1099-INT)")
            v.update({"L2": m(inc.taxable_interest, True), "L4": m(inc.taxable_interest, True)})
        if inc.ordinary_dividends:
            payers(inc.dividend_payers, inc.ordinary_dividends, 15, "div", "VARIOUS (SEE FORMS 1099-DIV)")
            v["L6"] = m(inc.ordinary_dividends, True)
        v.update({"L7a_yes": fi.foreign_account, "L7a_no": not fi.foreign_account,
                  "L8_yes": fi.foreign_trust, "L8_no": not fi.foreign_trust})
        if fi.foreign_account:
            v.update({"fbar_yes": fi.fbar_required, "fbar_no": not fi.fbar_required,
                      "L7b": upper(fi.foreign_countries) if fi.fbar_required else ""})
        self.add("sb", v)

    # ------------------------------------------------------------------ Anexo C
    def sc(self):
        inc = self.ret.income
        tp = self.ret.taxpayer
        v = {"name": upper(tp.full_name()), "ssn": digits(tp.ssn),
             "A": upper(inc.business_activity or inc.business_name), "B": digits(inc.business_code),
             "C": upper(inc.business_name) if inc.business_activity else "", "D": digits(inc.business_ein),
             "E_addr": upper(inc.business_address), "E_city": upper(inc.business_city),
             "F_cash": inc.accounting_method != "accrual", "F_accrual": inc.accounting_method == "accrual",
             "G_yes": inc.material_participation, "G_no": not inc.material_participation, "H": inc.business_started,
             "I_yes": inc.made_1099_payments, "I_no": not inc.made_1099_payments}
        if inc.made_1099_payments:
            v.update({"J_yes": inc.filed_1099s, "J_no": not inc.filed_1099s})
        l3 = inc.business_gross - inc.business_returns
        l5 = l3 - inc.business_cogs
        other = inc.other_expenses_total()
        meals = inc.exp_travel_meals * 0.5
        l28 = (inc.exp_advertising + inc.exp_car + inc.exp_contract_labor + inc.exp_insurance + inc.exp_office
               + inc.exp_rent + inc.exp_supplies + inc.exp_travel + meals + inc.exp_phone_internet + other)
        l29 = l5 - l28
        home = inc.home_office_deduction()
        l31 = l29 - home
        v.update({"L1": m(inc.business_gross, True), "L2": m(inc.business_returns), "L3": m(l3, True),
                  "L4": m(inc.business_cogs), "L5": m(l5, True), "L7": m(l5, True),
                  "L8": m(inc.exp_advertising), "L9": m(inc.exp_car), "L11": m(inc.exp_contract_labor),
                  "L15": m(inc.exp_insurance), "L18": m(inc.exp_office), "L20b": m(inc.exp_rent),
                  "L22": m(inc.exp_supplies), "L24a": m(inc.exp_travel), "L24b": m(meals),
                  "L25": m(inc.exp_phone_internet), "L27b": m(other), "L28": m(l28, True), "L29": m(l29, True),
                  "L30": m(home), "L31": m(l31, True)})
        if home:
            v.update({"L30a": m(inc.home_total_sqft), "L30b": m(min(inc.home_office_sqft, 300))})
        if l31 < 0:
            v["L32a"] = True
        if abs(l31 - self.fed["profit"]) >= 1:
            self.warn(_("Anexo C: la ganancia del formulario no coincide con el cálculo; revise los gastos."))
        if inc.business_cogs:
            v.update({"L33a": True, "L34_no": True, "L36": m(inc.business_cogs), "L40": m(inc.business_cogs),
                      "L42": m(inc.business_cogs)})
            self.warn(_("Anexo C Parte III: el costo de mercancía se anotó como compras (línea 36) sin inventario "
                        "inicial ni final; corríjalo si tiene inventario."))
        if inc.exp_car:
            mm, dd, yy = _split_date(inc.vehicle_in_service)
            v.update({"L43_mm": mm, "L43_dd": dd, "L43_yyyy": yy, "L44a": m(inc.miles_business, True),
                      "L44b": m(inc.miles_commuting, True), "L44c": m(inc.miles_other, True),
                      "L45_yes": inc.vehicle_personal_use, "L45_no": not inc.vehicle_personal_use,
                      "L46_yes": inc.other_vehicle, "L46_no": not inc.other_vehicle,
                      "L47a_yes": inc.vehicle_evidence, "L47a_no": not inc.vehicle_evidence})
            if inc.vehicle_evidence:
                v.update({"L47b_yes": inc.vehicle_evidence_written, "L47b_no": not inc.vehicle_evidence_written})
        rows = [(upper(x.description), x.amount) for x in inc.other_expenses if x.amount]
        if not rows and inc.exp_other:
            rows = [("OTHER BUSINESS EXPENSES", inc.exp_other)]
            self.warn(_("Anexo C Parte V: describa los 'otros gastos' (tipo y monto) para que el IRS los acepte."))
        if len(rows) > 9:
            extra = rows[8:]
            rows = rows[:8] + [("SEE ATTACHED STATEMENT", sum(a for _n, a in extra))]
            self.statement(self.t("Schedule C - Part V Other expenses (continued)",
                                      "Anexo C - Parte V Otros gastos (continuacion)"),
                           [f"{n:<50} {m(a, True):>12}" for n, a in extra])
        for i, (n, a) in enumerate(rows):
            v[f"oth{i}_desc"] = n
            v[f"oth{i}_amt"] = m(a, True)
        if rows:
            v["L48"] = m(other, True)
        self.add("sc", v)

    # ------------------------------------------------------------------ Anexo D y 8949
    def sd(self):
        inc, d = self.ret.income, self.d
        v = self.header()
        v["qof_no"] = True
        # Agrupar ventas por casilla del 8949
        groups: Dict[str, list] = {}
        direct = {"1a": [0.0, 0.0, 0.0], "8a": [0.0, 0.0, 0.0]}  # ventas con base informada y sin ajustes
        for s in inc.sales:
            box = s.box()
            if box in "ADGJ" and not s.adjustment and not s.code:
                k = "1a" if s.term == "short" else "8a"
                direct[k][0] += s.proceeds
                direct[k][1] += s.cost
                direct[k][2] += s.gain()
            else:
                groups.setdefault(box, []).append(s)
        for k, (pr, co, g) in direct.items():
            if pr or co:
                v.update({f"L{k}d": m(pr, True), f"L{k}e": m(co, True), f"L{k}h": m(g, True)})
        # Montos netos sin detalle: solo columna (h)
        if inc.short_term_gain:
            v["L1ah"] = m(whole(_num(v.get("L1ah"))) + inc.short_term_gain, True)
            self.warn(_("Anexo D: la ganancia neta a corto plazo se ingresó sin detalle; agregue las ventas (precio y "
                        "costo) en Ingresos → Inversiones para completar las columnas (d) y (e)."))
        if inc.long_term_gain:
            v["L8ah"] = m(whole(_num(v.get("L8ah"))) + inc.long_term_gain, True)
            self.warn(_("Anexo D: la ganancia neta a largo plazo se ingresó sin detalle; agregue las ventas (precio y "
                        "costo) en Ingresos → Inversiones para completar las columnas (d) y (e)."))
        line_of = {"A": "1b", "G": "1b", "B": "2", "H": "2", "C": "3", "I": "3",
                   "D": "8b", "J": "8b", "E": "9", "K": "9", "F": "10", "L": "10"}
        totals: Dict[str, List[float]] = {}
        for box in "ABCGHIDEFJKL":
            sales = groups.get(box)
            if not sales:
                continue
            self.f8949(box, sales)
            t = totals.setdefault(line_of[box], [0.0, 0.0, 0.0, 0.0])
            for s in sales:
                t[0] += s.proceeds
                t[1] += s.cost
                t[2] += s.adjustment
                t[3] += s.gain()
        for line, (pr, co, adj, g) in totals.items():
            v.update({f"L{line}d": m(pr, True), f"L{line}e": m(co, True), f"L{line}g": m(adj), f"L{line}h": m(g, True)})
        st_net, lt_net, net = d.get("st_net", 0.0), d.get("lt_net", 0.0), d.get("net_cap", 0.0)
        v.update({"L6": mpos(inc.capital_loss_carryover), "L7": m(st_net, True), "L13": m(inc.capital_gain_distributions),
                  "L15": m(lt_net, True), "L16": m(net, True)})
        if net > 0:
            both = lt_net > 0
            v.update({"L17_yes": both, "L17_no": not both})
            if both:
                v.update({"L20_yes": True})
            else:
                v.update({"L22_yes": self.fed["qualified_div"] > 0, "L22_no": self.fed["qualified_div"] <= 0})
        elif net < 0:
            v.update({"L21": mpos(self.fed["net_cap_gain_line7"]),
                      "L22_yes": self.fed["qualified_div"] > 0, "L22_no": self.fed["qualified_div"] <= 0})
        self.add("sd", v)

    def f8949(self, box: str, sales):
        short = box in "ABCGHI"
        part, page = (1, 0) if short else (2, 1)
        for start in range(0, len(sales), 11):
            chunk = sales[start:start + 11]
            v = {"name" if short else "name2": self.names(), "ssn" if short else "ssn2": self.ssn(), f"box{box}": True}
            for r, s in enumerate(chunk):
                p = f"p{part}r{r}"
                v.update({p + "a": upper(s.description)[:40], p + "b": upper(s.acquired), p + "c": upper(s.sold),
                          p + "d": m(s.proceeds, True), p + "e": m(s.cost, True), p + "f": upper(s.code),
                          p + "g": m(s.adjustment), p + "h": m(s.gain(), True)})
            t = f"p{part}tot"
            v.update({t + "d": m(sum(s.proceeds for s in chunk), True), t + "e": m(sum(s.cost for s in chunk), True),
                      t + "g": m(sum(s.adjustment for s in chunk)), t + "h": m(sum(s.gain() for s in chunk), True)})
            n = (len(sales) + 10) // 11
            label = f"Box {box}" + (f" ({start // 11 + 1}/{n})" if n > 1 else "")
            self.add("8949", v, pages=[page], label=label)

    # ------------------------------------------------------------------ Anexo SE
    def sse(self):
        f, d = self.fed, self.d
        tp = self.ret.taxpayer
        profit = f["profit"]
        se = self.data["se"]
        l4a = profit * se["net_factor"] if profit > 0 else profit
        l6 = f["se_net"]
        l8a = d.get("ss_wages_tp", 0.0)
        l9 = max(0.0, se["ss_wage_base"] - l8a)
        v = {"name": upper(tp.full_name()), "ssn": digits(tp.ssn), "L2": m(profit, True), "L3": m(profit, True),
             "L4a": m(l4a, True), "L4c": m(l4a, True), "L6": m(l6, True), "L7": m(se["ss_wage_base"]),
             "L8a": m(l8a), "L8d": m(l8a), "L9": m(l9, True), "L10": m(min(l6, l9) * se["ss_rate"], True),
             "L11": m(l6 * se["medicare_rate"], True), "L12": m(f["se_tax"], True), "L13": m(f["half_se"], True)}
        self.add("sse", v)

    # ------------------------------------------------------------------ Formulario 2441
    def f2441(self):
        r, f, d, cr = self.ret, self.fed, self.d, self.ret.credits
        v = self.header()
        provs = [p for p in cr.care_providers if p.name or p.amount]
        if not provs:
            self.warn(_("Formulario 2441: falta el proveedor de cuidado (nombre, dirección e identificación)."))
        for i, p in enumerate(provs[:3]):
            v.update({f"prov{i}_name": upper(p.name), f"prov{i}_addr": upper(p.address), f"prov{i}_tin": digits(p.tin),
                      f"prov{i}_hh_yes": p.household_employee, f"prov{i}_hh_no": not p.household_employee,
                      f"prov{i}_amt": m(p.amount, True)})
        if len(provs) > 3:
            self.statement(self.t("Form 2441 - Part I Care providers (continued)",
                                      "Formulario 2441 - Parte I Proveedores de cuidado (continuacion)"),
                           [f"{upper(p.name)}  {upper(p.address)}  TIN {p.tin}  {m(p.amount, True)}" for p in provs[3:]])
        qual = [dep for dep in r.dependents if dep.qualifies_care(self.year)]
        n = len(qual) or cr.care_persons
        limit = self.data["cdcc"]["expense_limit_one"] if n <= 1 else self.data["cdcc"]["expense_limit_two"]
        share = cr.care_expenses / len(qual) if qual else 0.0
        for i, dep in enumerate(qual[:3]):
            a = dep.age(self.year)
            v.update({f"q{i}_first": upper(dep.first_name), f"q{i}_last": upper(dep.last_name),
                      f"q{i}_ssn": digits(dep.ssn), f"q{i}_disabled": dep.disabled and (a is None or a >= 13),
                      f"q{i}_exp": m(share, True)})
        earned_tp = sum(w.box1_wages for w in r.w2s if w.owner != "conyuge") + max(0.0, f["profit"] - f["half_se"])
        earned_sp = sum(w.box1_wages for w in r.w2s if w.owner == "conyuge") if r.is_joint() else earned_tp
        benefits = cr.dependent_care_benefits
        if benefits > 0:
            excl_cap = 2500 if self.status == "mfs" else 5000
            l15 = benefits
            l17 = min(l15, cr.care_expenses)
            l20 = min(l17, earned_tp, earned_sp)
            l21 = excl_cap
            l25 = min(l20, l21)
            l26 = max(0.0, l15 - l25)
            l29 = max(0.0, limit - l25)
            l31 = min(l29, cr.care_expenses)
            v.update({"L12": m(benefits, True), "L15": m(l15, True), "L16": m(cr.care_expenses, True),
                      "L17": m(l17, True), "L18": m(earned_tp, True), "L19": m(earned_sp, True), "L20": m(l20, True),
                      "L21": m(l21), "L22_no": True, "L23": m(l15, True), "L24": "0", "L25": m(l25, True),
                      "L26": m(l26, True), "L27": m(limit), "L28": m(l25, True), "L29": m(l29, True),
                      "L30": m(cr.care_expenses, True), "L31": m(l31, True)})
            l3 = l31
            if l26 >= 1:
                self.warn(_("Formulario 2441: parte de los beneficios de cuidado del empleador es tributable (línea 26); "
                            "inclúyala en el 1040 línea 1e si no está en su W-2 casilla 1."))
        else:
            l3 = min(cr.care_expenses, limit)
        l6 = min(l3, earned_tp, earned_sp)
        rate = d.get("cdcc_rate", 0.0)
        if f["credits"]["cdcc"] >= 0.5 or l3 > 0:
            v.update({"L3": m(l3, True), "L4": m(earned_tp, True), "L5": m(earned_sp, True), "L6": m(l6, True),
                      "L7": m(f["agi"], True), "L8": f"{round(rate * 100):02d}" if rate else "",
                      "L9a": m(l6 * rate, True), "L9c": m(l6 * rate, True), "L10": m(d.get("cdcc_limit", 0), True),
                      "L11": m(f["credits"]["cdcc"], True)})
        self.add("2441", v)

    # ------------------------------------------------------------------ Formulario 6251
    def f6251(self):
        f, d = self.fed, self.d
        L = self.L
        senior = d.get("senior", 0.0)
        l1a = L["14"] - senior
        l2a = f["itemized_detail"]["salt"] if f["itemize"] else L["12"]
        v = self.header()
        v.update({"L1a": m(l1a, True), "L1b": m(f["agi"] - l1a, True), "L2a": m(l2a, True),
                  "L4": m(d.get("amti", 0), True), "L5": m(d.get("amt_exemption", 0), True),
                  "L6": m(d.get("amt_base", 0), True), "L7": m(d.get("tmt", 0), True), "L9": m(d.get("tmt", 0), True),
                  "L10": m(f["tax"], True), "L11": m(f["amt"], True)})
        if d.get("pref_income", 0) > 0:
            self.warn(_("Formulario 6251: con dividendos calificados o ganancias de capital, complete también la Parte III "
                        "(página 2); el impuesto mínimo de la línea 7 ya usa esas tasas."))
        self.add("6251", v)

    # ------------------------------------------------------------------ Anexo EIC
    def sei(self):
        v = self.header()
        kids = [dep for dep in self.ret.dependents if dep.qualifies_eitc(self.year)][:3]
        for i, dep in enumerate(kids):
            yr = (dep.dob or "")[:4]
            a = dep.age(self.year)
            v.update({f"c{i}_name": upper(dep.full_name()), f"c{i}_ssn": digits(dep.ssn),
                      f"c{i}_rel": upper(self.rel(dep.relationship, "sei")), f"c{i}_months": str(min(12, dep.months_lived))})
            for k, ch in enumerate(yr):
                v[f"c{i}_y{k}"] = ch
            if a is not None and a >= 19:
                student = a < 24 and dep.full_time_student
                v[f"c{i}_4a_yes" if student else f"c{i}_4a_no"] = True
                if not student:
                    v[f"c{i}_4b_yes" if dep.disabled else f"c{i}_4b_no"] = True
        self.add("sei", v)

    # ------------------------------------------------------------------ Anexo 8812
    def s8812(self):
        f, d, c = self.fed, self.d, self.fed["credits"]
        ctc = self.data["ctc"]
        agi = f["agi"]
        thr = pick(ctc["phaseout_start"], self.status)
        over = max(0.0, agi - thr)
        l10 = math.ceil(over / 1000) * 1000 if over > 0 else 0
        l11 = l10 * ctc["reduce_per_1000"] / 1000
        l8 = d.get("ctc_gross", 0.0)
        v = self.header()
        v.update({"L1": m(agi, True), "L3": m(agi, True), "L4": str(c["n_ctc"]), "L5": m(c["n_ctc"] * ctc["per_child"], True),
                  "L6": str(c["n_odc"]), "L7": m(c["n_odc"] * ctc["odc"], True), "L8": m(l8, True), "L9": m(thr),
                  "L10": m(l10, True), "L11": m(l11, True)})
        if l8 <= l11:
            v["L12_no"] = True
            self.add("s8812", v)
            return
        l12 = l8 - l11
        l14 = c["ctc_nonref"]
        v.update({"L12_yes": True, "L12": m(l12, True), "L13": m(d.get("ctc_limit", 0), True), "L14": m(l14, True)})
        if c["n_ctc"] and l12 - l14 >= 0.5:
            l16a = l12 - l14
            l16b = c["n_ctc"] * ctc["refundable_max"]
            l17 = min(l16a, l16b)
            earned = f["earned_income"]
            v.update({"L16a": m(l16a, True), "L16b_n": str(c["n_ctc"]), "L16b": m(l16b, True), "L17": m(l17, True),
                      "L18a": m(earned, True)})
            if earned > ctc["earned_threshold"]:
                l19 = earned - ctc["earned_threshold"]
                v.update({"L19_yes": True, "L19": m(l19, True), "L20": m(l19 * ctc["refund_rate"], True)})
            else:
                v.update({"L19_no": True, "L20": "0"})
            three = l16b >= 3 * ctc["refundable_max"]
            v["L20_yes" if three else "L20_no"] = True
            p2b = d.get("actc_part2b")
            if three and p2b:
                v.update({f"L{k}": m(val, True) for k, val in p2b.items()})
            v["L27"] = m(c["actc"], True)
        self.add("s8812", v)

    # ------------------------------------------------------------------ Formulario 8863
    def f8863(self):
        f, d, c = self.fed, self.d, self.fed["credits"]
        students = [s for s in self.ret.credits.students if s.expenses > 0]
        agi = f["agi"]
        # Solo "mfj" usa el límite alto; QSS usa el de "other" (el cálculo federal no: ver REVISIONES.md)
        lo, top = self.data["aotc"]["phaseout"]["mfj" if self.status == "mfj" else "other"]
        rng = top - lo
        ed = self.data["aotc"]
        l4 = max(0.0, top - agi)
        aotc = [s for s in students if s.credit.upper() == "AOTC"]
        llc = [s for s in students if s.credit.upper() == "LLC"]

        def l30(s):
            l27 = min(s.expenses, ed["max_expenses"])
            l28 = max(0.0, l27 - ed["full_expenses"])
            return l27, l28, l28 * ed["excess_rate"], (l27 if l28 == 0 else ed["full_expenses"] + l28 * ed["excess_rate"])

        def split_ssn(s):
            dg = digits(s)
            return (dg[:3], dg[3:5], dg[5:9]) if len(dg) == 9 else ("", "", "")

        v = {"name": self.names(), "name2": self.names()}
        a, b, cc = split_ssn(self.ret.taxpayer.ssn)
        v.update({"ssn_a": a, "ssn_b": b, "ssn_c": cc, "ssn2_a": a, "ssn2_b": b, "ssn2_c": cc})
        if aotc:
            l1 = sum(l30(s)[3] for s in aotc)
            fac = d.get("aotc_factor", 1.0)
            v.update({"L1": m(l1, True), "L2": m(top), "L3": m(agi, True), "L4": m(l4, True), "L5": m(rng),
                      "L6_int": "1" if fac >= 1 else "0", "L6_dec": "000" if fac >= 1 else f"{round(fac * 1000):03d}",
                      "L7": m(d.get("aotc_gross", 0) * fac, True), "L8": m(c["aotc_refundable"], True),
                      "L9": m(d.get("aotc_gross", 0) * fac - c["aotc_refundable"], True)})
        if llc:
            l10 = sum(s.expenses for s in llc)
            l11 = min(l10, self.data["llc"]["max_expenses"])
            fac = d.get("llc_factor", 1.0)
            l15 = max(0.0, top - agi)
            v.update({"L10": m(l10, True), "L11": m(l11, True), "L12": m(l11 * self.data["llc"]["rate"], True), "L13": m(top),
                      "L14": m(agi, True), "L15": m(l15, True)})
            if l15 > 0:
                v.update({"L16": m(rng), "L17_int": "1" if fac >= 1 else "0",
                          "L17_dec": "000" if fac >= 1 else f"{round(fac * 1000):03d}"})
            v["L18"] = m(c["llc"], True)
        v["L19"] = m(c["education_nonref"], True)
        for i, s in enumerate(students):
            sv = dict(v) if i == 0 else {"name2": self.names(), "ssn2_a": a, "ssn2_b": b, "ssn2_c": cc}
            x, y, z = split_ssn(s.ssn)
            ein = digits(s.school_ein)
            sv.update({"L20": upper(s.name), "L21_a": x, "L21_b": y, "L21_c": z, "L22a_name": upper(s.school),
                       "L22a_addr": upper(s.school_address), "L22a_1098_yes": s.got_1098t, "L22a_1098_no": not s.got_1098t,
                       "L22a_prev_no": True})
            if len(ein) == 9:
                for k, ch in enumerate(ein):
                    sv[f"L22a_ein{k}"] = ch
            if s.credit.upper() == "AOTC":
                l27, l28, l29, l30v = l30(s)
                sv.update({"L23_no": True, "L24_yes" if s.half_time else "L24_no": True,
                           "L25_no" if s.first_four_years else "L25_yes": True, "L26_no": True,
                           "L27": m(l27, True), "L28": m(l28, True), "L29": m(l29, True), "L30": m(l30v, True)})
                if not s.half_time or not s.first_four_years:
                    self.warn(tr("Formulario 8863: {n} no cumple los requisitos del AOTC (medio tiempo / primeros 4 años); "
                                 "considere el crédito LLC.", n=s.name or _("estudiante")))
            else:
                sv["L31"] = m(s.expenses, True)
            self.add("8863", sv, pages=None if i == 0 else [1], label=s.name)

    # ------------------------------------------------------------------ Formulario 8889
    def f8889(self):
        ded = self.ret.deductions
        h = self.data.get("hsa", {})
        v = self.header()
        cov = ded.hsa_coverage
        tp_age = self.ret.taxpayer_age()
        v.update({"cov_self": cov == "self", "cov_family": cov == "family", "L2": m(ded.hsa_deduction, True)})
        if cov in ("self", "family") and h:
            catchup = h["catchup"] if tp_age is not None and tp_age >= 55 else 0
            # El aporte adicional de 55+ va en la línea 3 (hoja de trabajo), salvo casados con cobertura familiar (línea 7)
            married_family = self.ret.has_spouse() and cov == "family"
            l3 = h[cov] + (0 if married_family else catchup)
            l7 = catchup if married_family else 0
            l8 = l3 + l7
            l12 = max(0.0, l8 - ded.hsa_employer)
            v.update({"L3": m(l3), "L5": m(l3), "L6": m(l3), "L7": m(l7), "L8": m(l8), "L9": m(ded.hsa_employer),
                      "L11": m(ded.hsa_employer), "L12": m(l12, True), "L13": m(self.fed.get("hsa", 0), True)})
        else:
            v["L13"] = m(self.fed.get("hsa", 0), True)
            self.warn(_("Formulario 8889: indique si su cobertura HDHP es individual o familiar (Deducciones → Ajustes)."))
        self.add("8889", v)

    # ------------------------------------------------------------------ Formulario 8880
    def f8880(self):
        r, d, cr = self.ret, self.d, self.ret.credits
        v = self.header()

        def split(contrib, owner):
            elective = sum(w.box12_401k for w in r.w2s if (w.owner == "conyuge") == (owner == "conyuge"))
            l2 = min(contrib, elective)
            return contrib - l2, l2

        cols = [("a", cr.retirement_contrib_taxpayer, "contribuyente")]
        if r.is_joint():
            cols.append(("b", cr.retirement_contrib_spouse, "conyuge"))
        l7 = 0.0
        for col, contrib, owner in cols:
            l1, l2 = split(contrib, owner)
            l6 = min(contrib, self.data["savers"]["contrib_max"])
            l7 += l6
            v.update({f"L1{col}": m(l1), f"L2{col}": m(l2), f"L3{col}": m(contrib, True), f"L5{col}": m(contrib, True),
                      f"L6{col}": m(l6, True)})
        rate = d.get("savers_rate", 0.0)
        v.update({"L7": m(l7, True), "L8": m(self.fed["agi"], True), "L9": str(int(round(rate * 10))),
                  "L10": m(l7 * rate, True), "L11": m(d.get("savers_limit", 0), True),
                  "L12": m(self.fed["credits"]["savers"], True)})
        self.add("8880", v)

    # ------------------------------------------------------------------ Formulario 8995
    def f8995(self):
        f, d, inc = self.fed, self.d, self.ret.income
        thr = pick(self.data["qbi"]["threshold"], self.status)
        if d.get("ti_before_qbi", 0) > thr:
            self.warn(_("Su ingreso supera el umbral del QBI: corresponde el Formulario 8995-A (no se genera aquí); "
                        "el Formulario 8995 se llenó como referencia."))
        qbi = d.get("qbi_income", 0.0)
        pref = f["net_capital_gain"] + f["qualified_div"]
        ti = d.get("ti_before_qbi", 0.0)
        l13 = max(0.0, ti - pref)
        rate = self.data["qbi"]["rate"]
        v = self.header()
        v.update({"b0_name": upper(inc.business_name or inc.business_activity or "SCHEDULE C"),
                  "b0_tin": digits(inc.business_ein) or self.ssn(), "b0_qbi": m(qbi, True), "L2": m(qbi, True),
                  "L4": m(qbi, True), "L5": m(qbi * rate, True), "L10": m(qbi * rate, True), "L11": m(ti, True),
                  "L12": m(pref, True), "L13": m(l13, True), "L14": m(l13 * rate, True), "L15": m(f["qbi"], True)})
        self.add("8995", v)

    # ------------------------------------------------------------------ Formulario 8959
    def f8959(self):
        f, d = self.fed, self.d
        wages = d.get("medicare_wages", 0.0)
        thr = d.get("addl_med_threshold", 0.0)
        rate = self.data["addl_medicare"]["rate"]
        l6 = max(0.0, wages - thr)
        v = self.header()
        v.update({"L1": m(wages, True), "L4": m(wages, True), "L5": m(thr), "L6": m(l6, True), "L7": m(l6 * rate, True)})
        se_net = f["se_net"]
        if se_net > 0:
            l11 = max(0.0, thr - wages)
            l12 = max(0.0, se_net - l11)
            v.update({"L8": m(se_net, True), "L9": m(thr), "L10": m(wages, True), "L11": m(l11, True),
                      "L12": m(l12, True), "L13": m(l12 * rate, True)})
        withheld = d.get("medicare_withheld", 0.0)
        reg = wages * self.data["se"]["medicare_rate"] / 2   # parte del empleado de la tasa de Medicare
        v.update({"L18": m(f["other_taxes"]["addl_medicare"], True), "L19": m(withheld, True), "L20": m(wages, True),
                  "L21": m(reg, True), "L22": m(max(0.0, withheld - reg), True),
                  "L24": m(f["payments"]["addl_medicare_withheld"], True)})
        self.add("8959", v)

    # ------------------------------------------------------------------ Formulario 8960
    def f8960(self):
        f, d, inc = self.fed, self.d, self.ret.income
        gain = max(0.0, f["net_cap_gain_line7"])
        thr = d.get("niit_threshold", 0.0)
        magi = f["magi"]
        nii = d.get("nii", 0.0)
        v = self.header()
        v.update({"L1": m(inc.taxable_interest), "L2": m(inc.ordinary_dividends), "L5a": m(gain), "L5d": m(gain),
                  "L8": m(nii, True), "L11": "0", "L12": m(nii, True), "L13": m(magi, True), "L14": m(thr),
                  "L15": m(max(0.0, magi - thr), True), "L16": m(min(nii, max(0.0, magi - thr)), True),
                  "L17": m(f["other_taxes"]["niit"], True)})
        self.add("8960", v)

    # ------------------------------------------------------------------ 1040-V
    def f1040v(self):
        r, a = self.ret, self.ret.address
        v = {"ssn": digits(r.taxpayer.ssn), "amount": m(self.L["37"], True),
             "first": upper(r.taxpayer.first_name), "last": upper(r.taxpayer.last_name),
             "street": upper(a.street), "apt": upper(a.apt), "city": upper(a.city), "state": upper(a.state),
             "zip": a.zip.strip()}
        if r.is_joint():
            v.update({"sp_ssn": digits(r.spouse.ssn), "sp_first": upper(r.spouse.first_name),
                      "sp_last": upper(r.spouse.last_name)})
        self.add("1040v", v)


# ------------------------------------------------------------------------------------------------- auxiliares
_REL_EN = {"hijo(a)": "Child", "hijastro(a)": "Stepchild", "hijo(a) de crianza": "Foster child", "nieto(a)": "Grandchild",
           "hermano(a)": "Sibling", "sobrino(a)": "Niece/Nephew", "padre / madre": "Parent", "otro pariente": "Other relative",
           "otra persona del hogar": "Other"}


def _rel_en(rel: str) -> str:
    """El IRS espera el parentesco en inglés (Child, Son, Daughter, Parent...)."""
    return _REL_EN.get((rel or "").strip().lower(), rel or "")


def _fmt_ssn(s: str) -> str:
    dg = digits(s)
    return f"{dg[:3]}-{dg[3:5]}-{dg[5:]}" if len(dg) == 9 else s


def _split_date(s: str):
    s = (s or "").strip().replace("-", "/")
    parts = s.split("/")
    if len(parts) == 3:
        if len(parts[0]) == 4:  # AAAA/MM/DD
            return parts[1].zfill(2), parts[2].zfill(2), parts[0]
        return parts[0].zfill(2), parts[1].zfill(2), parts[2]
    return "", "", ""


def _num(s) -> float:
    if not s:
        return 0.0
    s = str(s).replace(",", "")
    neg = s.startswith("(")
    try:
        x = float(s.strip("()"))
    except ValueError:
        return 0.0
    return -x if neg else x


def build(ret: TaxReturn, res: dict, preparer: Optional[dict] = None, use_sr: Optional[bool] = None,
          lang: str = "en") -> Plan:
    return Builder(ret, res, preparer, use_sr, lang).build()


def _fmt_ein(s: str) -> str:
    dg = digits(s)
    return f"{dg[:2]}-{dg[2:]}" if len(dg) == 9 else dg
