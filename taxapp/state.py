"""Calculo del impuesto estatal sobre la renta para los 50 estados + DC.

Motor generico basado en datos (data/states_YYYY.json) con reglas especiales por estado. Parte del AGI federal
(o del ingreso tributable federal en los estados que asi lo hacen), aplica restas/sumas comunes (Seguro Social,
jubilacion), deduccion estandar, exenciones o creditos personales, tramos por estado civil y creditos.
"""
from __future__ import annotations

import math

from . import data_loader
from .federal import bracket_tax, marginal_rate, r2
from .i18n import _, tr
from .models import TaxReturn


def _select_brackets(sd: dict, status: str):
    b = sd["brackets"]
    if status in ("mfj", "qss"):
        return b["mfj"]
    if status == "hoh":
        if sd.get("brackets_hoh"):
            return sd["brackets_hoh"]
        return b["mfj"] if sd.get("hoh_uses") == "mfj" else b["single"]
    return b["single"]


def _std(sd: dict, status: str) -> float:
    s = sd.get("std_deduction") or {}
    if status in ("mfj", "qss"):
        return s.get("mfj", 0)
    if status == "hoh":
        if "hoh" in s:
            return s["hoh"]
        return s.get("mfj", 0) if sd.get("hoh_uses") == "mfj" else s.get("single", 0)
    if status == "mfs":
        return s.get("mfs", s.get("mfj", 0) / 2 if s.get("mfj") else s.get("single", 0))
    return s.get("single", 0)


def _ss_subtraction(rule: str, taxable_ss: float, agi: float, status: str, tp_age, sp_age) -> float:
    """Cantidad de Seguro Social (ya incluida en el AGI federal) que el estado excluye."""
    if taxable_ss <= 0:
        return 0.0
    joint = status in ("mfj", "qss")
    if rule == "exempt":
        return taxable_ss
    if rule == "taxable":
        return 0.0
    if rule == "CO":
        ages = [a for a in (tp_age, sp_age) if a is not None]
        if any(a >= 65 for a in ages):
            return taxable_ss
        if any(a >= 55 for a in ages):
            return min(taxable_ss, 20000.0)
        return 0.0
    if rule == "CT":
        return taxable_ss if agi < (100000 if joint else 75000) else 0.75 * taxable_ss
    if rule == "MN":
        return taxable_ss if agi < (105000 if joint else 82000) else 0.0
    if rule == "NM":
        return taxable_ss if agi <= (150000 if joint else 100000) else 0.0
    if rule == "RI":
        return taxable_ss if agi <= (130000 if joint else 104000) else 0.0
    if rule == "VT":
        lo, hi = (65000, 75000) if joint else (50000, 60000)
        if agi <= lo:
            return taxable_ss
        if agi >= hi:
            return 0.0
        return taxable_ss * (hi - agi) / (hi - lo)
    if rule == "WV2025":
        return taxable_ss if agi <= (100000 if joint else 50000) else 0.65 * taxable_ss
    return taxable_ss


def compute_state(ret: TaxReturn, fedres: dict, code: str = None) -> dict:
    code = (code or ret.address.state or "").upper()
    year = ret.tax_year
    status = ret.filing_status
    joint = status in ("mfj", "qss")
    result = {"code": code, "name": "", "type": "none", "tax": 0.0, "lines": [], "notes": [], "withholding": 0.0,
              "payments": 0.0, "refund": 0.0, "owed": 0.0, "balance": 0.0, "taxable_income": 0.0,
              "marginal_rate": 0.0, "effective_rate": 0.0, "state_agi": 0.0, "form": None, "url": None}
    if not code:
        result["notes"].append(_("Seleccione su estado de residencia en 'Direccion y residencia'."))
        return result
    all_states = data_loader.states(year)
    sd = all_states.get(code)
    info = data_loader.states_info().get(code, {})
    if not sd:
        result["notes"].append(tr("No hay datos para el estado {code}.", code=code))
        return result
    result.update(name=sd["name"], type=sd["type"], form=info.get("form"), url=info.get("url"),
                  agency=info.get("agency"))
    result["notes"].extend(_(n) for n in sd.get("notes", []) if n)
    lines = result["lines"]
    ex = ret.state_extras
    inc = ret.income

    withholding = sum(w.box17_state_withheld for w in ret.w2s if (w.state or code).upper() == code)
    payments = withholding + ret.payments.state_estimated + ret.payments.state_extension
    result["withholding"] = withholding

    if sd["type"] == "none":
        result["payments"] = payments
        result["refund"] = payments
        result["balance"] = payments
        if withholding:
            result["notes"].append(_("Tiene retenciones estatales en un estado sin impuesto: verifique sus W-2."))
        lines.append((_("Impuesto estatal sobre la renta"), 0.0))
        return result

    tp_age = ret.taxpayer_age()
    sp_age = ret.spouse_age() if ret.is_joint() else None
    special = set(sd.get("special", []))
    agi = fedres["agi"]
    n_persons = 2 if joint else 1
    n_deps = len(ret.dependents)

    # ---------------------------------------------------------------- Washington (solo ganancias de capital)
    if sd["type"] == "capgains_only":
        base = max(0.0, max(0.0, fedres["long_term_net"]) - sd["deduction"])
        tax = bracket_tax(base, sd["brackets"]["single"])
        lines += [(_("Ganancias de capital a largo plazo"), max(0.0, fedres["long_term_net"])),
                  (_("Deduccion estandar del estado"), sd["deduction"]), (_("Base gravable"), base), (_("Impuesto"), tax)]
        tax = max(0.0, tax - ex.other_credits)
        result.update(tax=tax, taxable_income=base, payments=payments, balance=payments - tax,
                      refund=max(0.0, payments - tax), owed=max(0.0, tax - payments))
        return result

    # ---------------------------------------------------------------- Base de ingreso
    if "PA_base" in special:
        state_agi = (fedres["wages"] + inc.taxable_interest + inc.ordinary_dividends + max(0.0, fedres["net_cap_gain_line7"])
                     + max(0.0, fedres["profit"]) + inc.gambling + inc.other_income)
        lines.append((_("Ingreso gravable de PA (salarios, intereses, dividendos, ganancias, negocio)"), state_agi))
    else:
        state_agi = agi
        lines.append((_("AGI federal (punto de partida)"), agi))
        ss_sub = _ss_subtraction(sd.get("ss_rule", "exempt"), fedres["taxable_ss"], agi, status, tp_age, sp_age)
        if ss_sub:
            state_agi -= ss_sub
            lines.append((_("Resta: Seguro Social exento"), -ss_sub))
        if sd.get("exempts_retirement"):
            ret_sub = inc.pension_taxable + inc.ira_taxable
            if ret_sub:
                state_agi -= ret_sub
                lines.append((_("Resta: jubilacion/pensiones exentas"), -ret_sub))
        if "MO_capgains_exempt" in special and fedres["net_cap_gain_line7"] > 0:
            state_agi -= fedres["net_cap_gain_line7"]
            lines.append((_("Resta: ganancias de capital exentas (MO)"), -fedres["net_cap_gain_line7"]))
    if ex.additions:
        state_agi += ex.additions
        lines.append((_("Sumas estatales (usuario)"), ex.additions))
    if ex.subtractions:
        state_agi -= ex.subtractions
        lines.append((_("Restas estatales (usuario)"), -ex.subtractions))
    result["state_agi"] = state_agi

    # Deduccion del impuesto federal (AL, MO, OR)
    fed_tax = fedres["income_tax_liability"]
    if "AL_fed_tax_deduction" in special and fed_tax:
        state_agi -= fed_tax
        lines.append((_("Resta: impuesto federal pagado (AL)"), -fed_tax))
    if "MO_fed_tax_deduction" in special and fed_tax:
        pct = 0.35 if agi <= 25000 else 0.25 if agi <= 50000 else 0.15 if agi <= 100000 else 0.05 if agi <= 125000 else 0.0
        mo = min(fed_tax * pct, 10000 if joint else 5000)
        if mo:
            state_agi -= mo
            lines.append((tr("Resta: {p}% del impuesto federal (MO)", p=int(pct * 100)), -mo))
    if "OR_fed_tax_subtraction" in special and fed_tax:
        cap = sd.get("fed_tax_cap", 8500)
        lo, hi = (250000, 290000) if joint else (125000, 145000)
        if agi >= hi:
            cap = 0.0
        elif agi > lo:
            cap = cap * (hi - agi) / (hi - lo)
        orsub = min(fed_tax, cap)
        if orsub:
            state_agi -= orsub
            lines.append((_("Resta: impuesto federal (OR, con tope)"), -orsub))

    # ---------------------------------------------------------------- Deduccion
    if "PA_base" in special:
        deduction = 0.0
    elif sd.get("uses_federal_deduction"):
        deduction = fedres["deduction"] + fedres["nonitemizer_charity"] + fedres["qbi"] + fedres["sched1a"]["total"]
        lines.append((_("Deduccion (igual a la federal: estandar/itemizada, QBI y Schedule 1-A)"), -deduction))
        result["notes"].append(_("Algunos estados que parten del ingreso federal agregan de vuelta las deducciones OBBBA "
                                 "(propinas, horas extra); verifique las instrucciones estatales."))
    elif sd.get("std_from_federal"):
        deduction = fedres["deduction"] + fedres["nonitemizer_charity"]
        lines.append((_("Deduccion (igual a la federal)"), -deduction))
    else:
        deduction = _std(sd, status)
        if "AL_std_phase" in special:
            if status in ("mfj", "qss"):
                deduction = max(5000, 8500 - 175 * math.ceil(max(0, agi - 25999) / 500))
            elif status == "hoh":
                deduction = max(2600, 5200 - 135 * math.ceil(max(0, agi - 25999) / 500))
            elif status == "mfs":
                deduction = max(2500, 4250 - 88 * math.ceil(max(0, agi - 12999) / 500))
            else:
                deduction = max(2500, 3000 - 25 * math.ceil(max(0, agi - 25999) / 500))
        if "MN_std_phaseout" in special and deduction:
            p = sd["std_phaseout"]
            s1 = p["start_mfs"] if status == "mfs" else p["start"]
            s2 = p["second_mfs"] if status == "mfs" else p["second"]
            red = 0.03 * max(0.0, min(agi, s2) - s1) + 0.10 * max(0.0, agi - s2)
            deduction = max(deduction * 0.2, deduction - red)
        if "WI_std_sliding" in special and deduction:
            lo, hi = sd["wi_std_phase"]["mfj" if joint else "single"]
            if agi >= hi:
                deduction = 0.0
            elif agi > lo:
                deduction = deduction * (hi - agi) / (hi - lo)
        if sd.get("extra_std_65_blind"):
            deduction += sd["extra_std_65_blind"] * fedres["std_boxes"]
        if ex.itemized_override > deduction:
            deduction = ex.itemized_override
            lines.append((_("Deducciones itemizadas estatales (usuario)"), -deduction))
        elif deduction:
            lines.append((_("Deduccion estandar estatal"), -deduction))

    # ---------------------------------------------------------------- Exenciones
    exm = sd.get("exemption") or {}
    per_person = exm.get("per_person", 0)
    if status == "hoh" and exm.get("hoh_person"):
        persons_amount = exm["hoh_person"]
    else:
        persons_amount = per_person * n_persons
    dep_amount = exm.get("dependent", 0) * n_deps
    if "CT_exemption" in special:
        base, start = {"mfj": (24000, 48000), "qss": (24000, 48000), "hoh": (19000, 38000), "mfs": (12000, 24000)}.get(status, (15000, 30000))
        persons_amount = max(0.0, base - 1000 * math.ceil(max(0.0, agi - start) / 1000))
        dep_amount = 0.0
    if "IL_exemption_limit" in special and agi > (500000 if joint else 250000):
        persons_amount = dep_amount = 0.0
    if "OH_exemption" in special:
        each = 2400 if agi <= 40000 else 2150 if agi <= 80000 else (1900 if (agi < 500000 or year == 2025) else 0)
        persons_amount = each * n_persons
        dep_amount = each * n_deps
    if "MD_exemption_phaseout" in special:
        if joint or status == "hoh":
            each = 3200 if agi <= 150000 else 1600 if agi <= 175000 else 800 if agi <= 200000 else 0
        else:
            each = 3200 if agi <= 100000 else 1600 if agi <= 125000 else 800 if agi <= 150000 else 0
        persons_amount = each * n_persons
        dep_amount = each * n_deps
    if "AL_dependent_phase" in special:
        dep_amount = n_deps * (1000 if agi <= 50000 else 500 if agi <= 100000 else 300)
    if "NM_dependent_deduction" in special:
        dep_amount = 4000 * max(0, n_deps - 1)
    if "AZ_dependent_credit" in special:
        dep_amount = sum(100 if (d.age(year) or 0) < 17 else 25 for d in ret.dependents)
    if "RI_phaseout" in special:
        lo, hi = sd["phaseout_range"]
        if agi >= hi:
            factor = 0.0
        elif agi > lo:
            factor = (hi - agi) / (hi - lo)
        else:
            factor = 1.0
        if factor < 1.0:
            deduction *= factor
            persons_amount *= factor
            dep_amount *= factor
            lines.append((_("Reduccion por ingresos altos (RI)"), 0.0))
    if "OR_credit_limit" in special and agi > (200000 if joint else 100000):
        persons_amount = dep_amount = 0.0

    exemption_credit = 0.0
    if sd.get("exemption_is_credit"):
        exemption_credit = persons_amount + dep_amount
        if "CA_exemption_phaseout" in special:
            thr = 504411 if joint else 252203
            n_credits = n_persons + n_deps
            red = 6 * math.ceil(max(0.0, agi - thr) / 2500) * n_credits
            exemption_credit = max(0.0, exemption_credit - red)
        exemption_deduction = 0.0
    else:
        exemption_deduction = persons_amount + dep_amount
        if exemption_deduction:
            lines.append((_("Exenciones personales/dependientes"), -exemption_deduction))

    taxable = max(0.0, state_agi - deduction - exemption_deduction)
    lines.append((_("Ingreso tributable estatal"), taxable))

    # ---------------------------------------------------------------- Impuesto
    brackets = _select_brackets(sd, status)
    tax = bracket_tax(taxable, brackets)
    lines.append((_("Impuesto segun tabla"), tax))

    if "MD_capgains_surtax" in special and agi > 350000 and fedres["net_cap_gain_line7"] > 0:
        sur = 0.02 * fedres["net_cap_gain_line7"]
        tax += sur
        lines.append((_("Recargo 2% ganancias de capital (MD)"), sur))
    if "VT_min_tax" in special and agi > 150000 and tax < 0.03 * agi:
        lines.append((_("Ajuste a impuesto minimo (3% del AGI, VT)"), 0.03 * agi - tax))
        tax = 0.03 * agi
    credits = 0.0
    if exemption_credit:
        credits += exemption_credit
        lines.append((_("Credito por exencion personal/dependientes"), -exemption_credit))
    if "UT_taxpayer_credit" in special:
        fed_ded = fedres["deduction"] if not fedres["itemize"] else max(0.0, fedres["itemized_net"] - fedres["itemized_detail"]["salt"])
        base_credit = 0.06 * (fed_ded + exm.get("dependent", 0) * n_deps)
        phase_base = sd["ut_phase_base"]["mfj" if joint else "single"]
        utc = max(0.0, base_credit - 0.013 * max(0.0, state_agi - phase_base))
        credits += utc
        lines.append((_("Credito del contribuyente (UT)"), -utc))
    if ex.other_state_credit:
        credits += ex.other_state_credit
        lines.append((_("Credito por impuestos pagados a otro estado"), -ex.other_state_credit))
    if ex.other_credits:
        credits += ex.other_credits
        lines.append((_("Otros creditos estatales (usuario)"), -ex.other_credits))
    tax_after = max(0.0, tax - credits)

    months = max(1, min(12, int(ret.address.months_in_state or 12)))
    if months < 12:
        tax_after *= months / 12.0
        lines.append((tr("Prorrateo por residencia parcial ({m}/12 meses)", m=months), 0.0))
        result["notes"].append(_("Residente parcial: el impuesto se prorrateo por meses (aproximacion; los estados usan "
                                 "el ingreso de la parte del ano como residente)."))
    lines.append((_("Impuesto estatal neto"), tax_after))

    refundable = ex.refundable_credits
    total_pay = payments + refundable
    balance = total_pay - tax_after
    result.update(tax=tax_after, gross_tax=tax, credits=credits, taxable_income=taxable, deduction=deduction,
                  payments=total_pay, refundable=refundable, balance=balance,
                  refund=max(0.0, balance), owed=max(0.0, -balance),
                  marginal_rate=marginal_rate(taxable, brackets) if taxable > 0 else 0.0,
                  effective_rate=(tax_after / agi) if agi > 0 else 0.0,
                  lines=[(n, r2(v)) for n, v in lines])
    return result
