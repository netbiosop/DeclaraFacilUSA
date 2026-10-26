"""Calculo del impuesto federal (Formulario 1040 y anexos principales).

Cubre: salarios, intereses, dividendos (tasas preferenciales), ganancias de capital, jubilacion, Seguro Social
(porcion tributable), desempleo, trabajo independiente (Schedule C + Schedule SE), ajustes (Schedule 1),
nuevas deducciones OBBBA (Schedule 1-A: propinas, horas extra, intereses de auto, deduccion para mayores),
deduccion estandar vs. itemizada (Schedule A con tope SALT), QBI, AMT simplificado, creditos (CTC/ODC/ACTC,
EITC, cuidado de dependientes, educativos, ahorrador), Medicare adicional, NIIT y pagos.

Es un ESTIMADOR: no reemplaza los formularios oficiales del IRS.
"""
from __future__ import annotations

import math
from typing import Dict, List

from . import data_loader
from .i18n import _, tr
from .models import TaxReturn

INF = float("inf")


# ---------------------------------------------------------------------------- utilidades
def sk(status: str) -> str:
    """Clave de tabla: el conyuge sobreviviente usa las tablas de casados en conjunto."""
    return "mfj" if status in ("mfj", "qss") else status


def pick(d: dict, status: str):
    s = sk(status)
    if s in d:
        return d[s]
    if s == "mfj" and "mfj" in d:
        return d["mfj"]
    return d.get("other", d.get("single"))


def bracket_tax(amount: float, brackets: List[list]) -> float:
    """Impuesto por tramos. Cada tramo es [piso, tasa] o [piso, tasa, monto_base] (tablas con cuota fija, p. ej. Ohio:
    impuesto = monto_base + tasa x (ingreso - piso))."""
    if amount <= 0:
        return 0.0
    if any(len(b) > 2 for b in brackets):
        sel = brackets[0]
        for b in brackets:
            if amount > b[0]:
                sel = b
        base = sel[2] if len(sel) > 2 else 0.0
        return base + sel[1] * (amount - sel[0])
    tax = 0.0
    for i, b in enumerate(brackets):
        floor, rate = b[0], b[1]
        top = brackets[i + 1][0] if i + 1 < len(brackets) else INF
        if amount > floor:
            tax += (min(amount, top) - floor) * rate
        else:
            break
    return tax


def marginal_rate(amount: float, brackets: List[list]) -> float:
    rate = brackets[0][1]
    for b in brackets:
        if amount >= b[0]:
            rate = b[1]
    return rate


def phase_factor(magi: float, rng) -> float:
    lo, hi = rng
    if magi <= lo:
        return 1.0
    if magi >= hi:
        return 0.0
    return (hi - magi) / (hi - lo)


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def qdcg_tax(ti: float, pref_income: float, status: str, fed: dict) -> Dict[str, float]:
    """Hoja de calculo 'Qualified Dividends and Capital Gain Tax Worksheet'."""
    brackets = fed["brackets"][sk(status)]
    pref = max(0.0, min(ti, pref_income))
    ordinary = ti - pref
    z = fed["capital_gains"]["zero_max"][sk(status)]
    f = fed["capital_gains"]["fifteen_max"][sk(status)]
    a = min(ti, z)
    zero_amt = max(0.0, a - min(a, ordinary))
    c = pref - zero_amt
    g = max(0.0, min(ti, f) - (ordinary + zero_amt))
    fifteen_amt = min(c, g)
    twenty_amt = max(0.0, pref - zero_amt - fifteen_amt)
    tax = bracket_tax(ordinary, brackets) + 0.15 * fifteen_amt + 0.20 * twenty_amt
    regular = bracket_tax(ti, brackets)
    return {"tax": min(tax, regular), "ordinary": ordinary, "zero": zero_amt, "fifteen": fifteen_amt, "twenty": twenty_amt}


# ---------------------------------------------------------------------------- calculo principal
def compute_federal(ret: TaxReturn) -> dict:
    fed = data_loader.federal(ret.tax_year)
    st = ret.filing_status
    s = sk(st)
    inc = ret.income
    ded = ret.deductions
    cr = ret.credits
    notes: List[str] = []
    L: Dict[str, float] = {}

    tp_age = ret.taxpayer_age()
    sp_age = ret.spouse_age() if ret.is_joint() else None

    # ---------------- Ingresos
    wages = sum(w.box1_wages for w in ret.w2s)
    wages_tp = sum(w.box1_wages for w in ret.w2s if w.owner != "conyuge")
    wages_sp = wages - wages_tp
    ss_wages_by_owner = {"contribuyente": 0.0, "conyuge": 0.0}
    ss_withheld_by_owner = {"contribuyente": 0.0, "conyuge": 0.0}
    for w in ret.w2s:
        key = "conyuge" if w.owner == "conyuge" else "contribuyente"
        ss_wages_by_owner[key] += (w.box3_ss_wages or w.box1_wages) + w.box7_ss_tips
        ss_withheld_by_owner[key] += w.box4_ss_withheld
    medicare_wages = sum((w.box5_medicare_wages or w.box1_wages) for w in ret.w2s)
    medicare_withheld = sum(w.box6_medicare_withheld for w in ret.w2s)

    profit = inc.schedule_c_profit()

    # Ganancias de capital (Schedule D simplificado)
    st_net = inc.short_term_gain - inc.capital_loss_carryover
    lt_net = inc.long_term_gain + inc.capital_gain_distributions
    net_cap = st_net + lt_net
    loss_limit = fed["capital_loss_limit"]["mfs" if st == "mfs" else "other"]
    cap_line7 = net_cap if net_cap >= 0 else max(net_cap, -loss_limit)
    if net_cap < -loss_limit:
        notes.append(tr("Perdida de capital limitada a ${a}; el resto (${b}) se arrastra al proximo ano.", a=f"{loss_limit:,.0f}", b=f"{-net_cap - loss_limit:,.0f}"))
    net_capital_gain = max(0.0, min(lt_net, net_cap)) if net_cap > 0 else 0.0
    qualified_div = min(inc.qualified_dividends, inc.ordinary_dividends)

    # ---------------- Schedule SE
    se = fed["se"]
    se_net = profit * se["net_factor"] if profit * se["net_factor"] >= 400 else 0.0
    ss_room = max(0.0, se["ss_wage_base"] - ss_wages_by_owner["contribuyente"])
    se_ss = min(se_net, ss_room) * se["ss_rate"]
    se_med = se_net * se["medicare_rate"]
    se_tax = se_ss + se_med
    half_se = se_tax / 2

    # ---------------- Ajustes (Schedule 1, parte II)
    educator = min(ded.educator_expenses, fed["educator_max"] * ret.num_people())
    se_health = max(0.0, min(ded.se_health_insurance, profit - half_se))
    adj_wo_sli = half_se + se_health + ded.hsa_deduction + ded.ira_deduction + educator + ded.other_adjustments

    other_income = inc.unemployment + inc.state_refund_taxable + inc.gambling + inc.other_income
    sched1_additional = profit + other_income
    income_ex_ss = (wages + inc.taxable_interest + inc.ordinary_dividends + inc.ira_taxable + inc.pension_taxable
                    + cap_line7 + sched1_additional)

    # Seguro Social tributable (Worksheet 1040 linea 6)
    ssb = inc.social_security
    taxable_ss = 0.0
    if ssb > 0:
        base1 = pick(fed["ss_benefits"]["base1"], st)
        base2 = pick(fed["ss_benefits"]["base2"], st)
        provisional = income_ex_ss - adj_wo_sli + inc.tax_exempt_interest + ssb / 2
        if provisional <= base1:
            taxable_ss = 0.0
        elif provisional <= base2:
            taxable_ss = min(0.5 * (provisional - base1), 0.5 * ssb)
        else:
            taxable_ss = min(0.85 * (provisional - base2) + min(0.5 * ssb, 0.5 * (base2 - base1)), 0.85 * ssb)
        taxable_ss = max(0.0, taxable_ss)

    total_income = income_ex_ss + taxable_ss

    # Interes de prestamos estudiantiles (con eliminacion gradual por MAGI)
    sli = 0.0
    if ded.student_loan_interest > 0:
        if st == "mfs":
            notes.append(_("El interes de prestamos estudiantiles no se permite al declarar casado por separado."))
        else:
            magi = total_income - adj_wo_sli
            sli = min(ded.student_loan_interest, fed["student_loan"]["max"]) * phase_factor(magi, pick(fed["student_loan"]["phaseout"], st))
    adjustments = adj_wo_sli + sli
    agi = total_income - adjustments
    magi = agi  # sin exclusiones extranjeras

    # ---------------- Schedule 1-A (OBBBA)
    def reduce(amount, start, per1000):
        return max(0.0, amount - max(0.0, magi - start) * per1000 / 1000.0)

    tips_ded = overtime_ded = car_ded = senior_ded = 0.0
    has_ssn = ret.taxpayer.valid_ssn_for_work or (ret.is_joint() and ret.spouse.valid_ssn_for_work)
    if inc.qualified_tips > 0:
        if st == "mfs":
            notes.append(_("Deduccion por propinas: los casados deben declarar en conjunto para reclamarla."))
        elif not has_ssn:
            notes.append(_("Deduccion por propinas requiere un SSN valido para trabajar."))
        else:
            t = fed["tips"]
            tips_ded = reduce(min(inc.qualified_tips, t["max"]), pick(t["phaseout_start"], st), t["reduce_per_1000"])
    if inc.qualified_overtime > 0:
        if st == "mfs":
            notes.append(_("Deduccion por horas extra: los casados deben declarar en conjunto para reclamarla."))
        elif not has_ssn:
            notes.append(_("Deduccion por horas extra requiere un SSN valido para trabajar."))
        else:
            o = fed["overtime"]
            overtime_ded = reduce(min(inc.qualified_overtime, pick(o["max"], st)), pick(o["phaseout_start"], st), o["reduce_per_1000"])
    if ded.car_loan_interest > 0:
        c = fed["car_loan"]
        car_ded = reduce(min(ded.car_loan_interest, c["max"]), pick(c["phaseout_start"], st), c["reduce_per_1000"])
    seniors = 0
    if tp_age is not None and tp_age >= 65 and ret.taxpayer.valid_ssn_for_work:
        seniors += 1
    if sp_age is not None and sp_age >= 65 and ret.spouse.valid_ssn_for_work:
        seniors += 1
    if seniors:
        if st == "mfs":
            notes.append(_("Deduccion para mayores de 65: los casados deben declarar en conjunto."))
        else:
            sd = fed["senior"]
            per = max(0.0, sd["amount"] - max(0.0, magi - pick(sd["phaseout_start"], st)) * sd["rate"])
            senior_ded = per * seniors
    sched1a_total = tips_ded + overtime_ded + car_ded + senior_ded

    # ---------------- Deduccion estandar
    std = fed["standard_deduction"][st]
    earned_income = wages + max(0.0, profit - half_se)
    if ret.taxpayer.can_be_claimed:
        dep = fed["dependent_std"]
        std = min(std, max(dep["min"], earned_income + dep["earned_plus"]))
    boxes = 0
    if tp_age is not None and tp_age >= 65:
        boxes += 1
    if ret.taxpayer.blind:
        boxes += 1
    if ret.is_joint():
        if sp_age is not None and sp_age >= 65:
            boxes += 1
        if ret.spouse.blind:
            boxes += 1
    add_amt = fed["additional_std"]["married" if st in ("mfj", "mfs", "qss") else "unmarried"]
    std_total = std + boxes * add_amt

    # ---------------- Itemizadas (Schedule A)
    medical = max(0.0, ded.medical - fed["medical_floor"] * agi)
    state_local_income = (sum(w.box17_state_withheld + w.box19_local_withheld for w in ret.w2s)
                          + ded.state_income_tax_paid_extra + ret.payments.state_estimated + ret.payments.local_estimated)
    salt_first = ded.sales_tax_paid if ded.salt_use_sales_tax else state_local_income
    salt_raw = salt_first + ded.real_estate_tax + ded.personal_property_tax
    sl = fed["salt"]
    cap = sl["cap_mfs"] if st == "mfs" else sl["cap"]
    start = sl["phaseout_start_mfs"] if st == "mfs" else sl["phaseout_start"]
    floor = sl["floor_mfs"] if st == "mfs" else sl["floor"]
    salt_cap = max(floor, cap - sl["phaseout_rate"] * max(0.0, magi - start))
    salt = min(salt_raw, salt_cap)
    interest = ded.mortgage_interest + ded.mortgage_points + ded.investment_interest
    charity = min(ded.charity_cash, 0.6 * agi) + min(ded.charity_noncash, 0.3 * agi)
    if fed["charitable_floor_pct"]:
        charity = max(0.0, charity - fed["charitable_floor_pct"] * agi)
    itemized = medical + salt + interest + charity + ded.casualty_loss + ded.other_itemized
    itemized_limit_red = 0.0
    if fed.get("itemized_37_limit") and itemized > 0:
        top_start = fed["brackets"][s][-1][0]
        base_ti = agi - sched1a_total
        itemized_limit_red = (2.0 / 37.0) * min(itemized, max(0.0, base_ti - top_start))
    itemized_net = itemized - itemized_limit_red

    nonitem_charity = 0.0
    nic = fed["charitable_nonitemizer"]
    if nic.get("single") or nic.get("mfj"):
        nonitem_charity = min(ded.charity_cash, nic["mfj"] if st == "mfj" else nic["single"])

    if ded.mode == "itemized":
        itemize = True
    elif ded.mode == "standard":
        itemize = False
    else:
        itemize = itemized_net > std_total + nonitem_charity
    if st == "mfs" and ded.mode != "standard":
        notes.append(_("Casados por separado: si su conyuge itemiza, usted tambien debe itemizar."))
    deduction = itemized_net if itemize else std_total
    charity_extra = 0.0 if itemize else nonitem_charity

    # ---------------- QBI (seccion 199A)
    qbi_ded = 0.0
    qbi = profit - half_se - se_health
    ti_before_qbi = max(0.0, agi - deduction - charity_extra - sched1a_total)
    if qbi > 0:
        q = fed["qbi"]
        tentative = q["rate"] * qbi
        thr = pick(q["threshold"], st)
        rng = pick(q["phase_range"], st)
        if ti_before_qbi > thr:
            frac = min(1.0, (ti_before_qbi - thr) / rng)
            tentative *= (1 - frac)
            notes.append(_("QBI: ingreso sobre el umbral; se aplico la reduccion gradual asumiendo negocio sin salarios W-2 "
                           "ni bienes calificados (los servicios especificos SSTB no se distinguen)."))
        if q.get("min_deduction") and qbi >= q.get("min_qbi", 0):
            tentative = max(tentative, q["min_deduction"])
        qbi_ded = max(0.0, min(tentative, q["rate"] * max(0.0, ti_before_qbi - net_capital_gain - qualified_div)))

    taxable_income = max(0.0, agi - deduction - charity_extra - sched1a_total - qbi_ded)

    # ---------------- Impuesto
    pref_income = qualified_div + net_capital_gain
    q = qdcg_tax(taxable_income, pref_income, st, fed)
    tax = q["tax"]

    # ---------------- AMT simplificado (Formulario 6251)
    amt = 0.0
    a = fed["amt"]
    amti = taxable_income + (salt if itemize else std_total + charity_extra)
    exemption = max(0.0, a["exemption"][st] - a["phaseout_rate"] * max(0.0, amti - a["phaseout_start"][st]))
    amt_base = max(0.0, amti - exemption)
    if amt_base > 0:
        thr28 = a["rate28_threshold"]["mfs" if st == "mfs" else "other"]
        pref_amt = min(amt_base, pref_income)
        ord_amt = amt_base - pref_amt

        def tmt_ord(x):
            return 0.26 * x if x <= thr28 else 0.26 * thr28 + 0.28 * (x - thr28)

        qa = qdcg_tax(amt_base, pref_amt, st, fed)
        tmt = tmt_ord(ord_amt) + 0.15 * qa["fifteen"] + 0.20 * qa["twenty"]
        tmt = min(tmt, tmt_ord(amt_base))
        amt = max(0.0, tmt - tax)
        if amt > 0:
            notes.append(_("Se calculo Impuesto Minimo Alternativo (AMT) simplificado; revise el Formulario 6251."))

    tax_before_credits = tax + amt

    # ---------------- Creditos no reembolsables
    year = ret.tax_year
    deps = ret.dependents
    remaining = tax_before_credits

    # Credito por cuidado de hijos y dependientes (Form 2441)
    cdcc = 0.0
    n_care = cr.care_persons or sum(1 for d in deps if d.qualifies_care(year))
    if cr.care_expenses > 0 and n_care > 0:
        if st == "mfs":
            notes.append(_("Credito por cuidado de dependientes: generalmente no disponible para casados por separado."))
        else:
            c = fed["cdcc"]
            limit = c["expense_limit_one"] if n_care == 1 else c["expense_limit_two"]
            exp = max(0.0, min(cr.care_expenses, limit) - cr.dependent_care_benefits)
            earned_tp = wages_tp + max(0.0, profit - half_se)
            earned_lowest = min(earned_tp, wages_sp) if ret.is_joint() else earned_tp
            exp = min(exp, earned_lowest)
            rate = max(c["first_floor"], c["max_rate"] - 0.01 * math.ceil(max(0.0, agi - c["first_start"]) / c["first_step"]))
            if c.get("second_start"):
                s2 = pick(c["second_start"], st)
                if agi > s2:
                    rate = max(c["min_rate"], c["first_floor"] - 0.01 * math.ceil((agi - s2) / pick(c["second_step"], st)))
            rate = max(rate, c["min_rate"])
            cdcc = min(remaining, exp * rate)
    remaining -= cdcc

    # Creditos educativos (Form 8863)
    aotc_total = llc = 0.0
    if cr.students and st != "mfs":
        ao = fed["aotc"]
        factor = phase_factor(magi, pick(ao["phaseout"], st))
        for stu in cr.students:
            if stu.credit.upper() == "AOTC":
                e = stu.expenses
                aotc_total += min(e, 2000) + 0.25 * max(0.0, min(e, 4000) - 2000)
        aotc_total *= factor
        lc = fed["llc"]
        llc_exp = sum(stu.expenses for stu in cr.students if stu.credit.upper() == "LLC")
        llc = lc["rate"] * min(llc_exp, lc["max_expenses"]) * phase_factor(magi, pick(lc["phaseout"], st))
    elif cr.students:
        notes.append(_("Creditos educativos no disponibles para casados declarando por separado."))
    aotc_refundable = aotc_total * fed["aotc"]["refundable_pct"]
    edu_nonref = min(remaining, aotc_total - aotc_refundable + llc)
    remaining -= edu_nonref

    # Credito del ahorrador (Form 8880)
    savers = 0.0
    if (cr.retirement_contrib_taxpayer or cr.retirement_contrib_spouse) and not ret.taxpayer.can_be_claimed:
        tiers = pick(fed["savers"]["tiers"], st if st in ("mfj", "hoh") else "other")
        rate = 0.0
        for limit, r in tiers:
            if agi <= limit:
                rate = r
                break
        mx = fed["savers"]["contrib_max"]
        contrib = min(cr.retirement_contrib_taxpayer, mx) + (min(cr.retirement_contrib_spouse, mx) if ret.is_joint() else 0)
        savers = min(remaining, contrib * rate)
    remaining -= savers

    foreign = min(remaining, cr.foreign_tax_paid)
    remaining -= foreign
    other_nonref = min(remaining, cr.other_nonrefundable)
    remaining -= other_nonref
    sched3_nonref = cdcc + edu_nonref + savers + foreign + other_nonref

    # Credito tributario por hijos y otros dependientes
    ctc_data = fed["ctc"]
    n_ctc = sum(1 for d in deps if d.qualifies_ctc(year))
    n_odc = len(deps) - n_ctc
    ctc_allowed = ret.taxpayer.valid_ssn_for_work or (ret.is_joint() and ret.spouse.valid_ssn_for_work)
    if n_ctc and not ctc_allowed:
        notes.append(_("CTC requiere que al menos un contribuyente tenga SSN valido (OBBBA); se aplica solo ODC."))
        n_odc += n_ctc
        n_ctc = 0
    ctc_gross = n_ctc * ctc_data["per_child"] + n_odc * ctc_data["odc"]
    ctc_red = 50.0 * math.ceil(max(0.0, magi - pick(ctc_data["phaseout_start"], st)) / 1000.0)
    ctc_after = max(0.0, ctc_gross - ctc_red)
    ctc_nonref = min(remaining, ctc_after)
    remaining -= ctc_nonref
    # Porcion reembolsable (ACTC) solo para hijos calificados
    child_portion = max(0.0, min(ctc_after, n_ctc * ctc_data["per_child"]) - ctc_nonref)
    actc = 0.0
    if n_ctc:
        actc = min(child_portion, n_ctc * ctc_data["refundable_max"],
                   ctc_data["refund_rate"] * max(0.0, earned_income - ctc_data["earned_threshold"]))

    total_nonref = sched3_nonref + ctc_nonref
    tax_after_credits = max(0.0, tax_before_credits - total_nonref)

    # ---------------- Otros impuestos (Schedule 2)
    am = fed["addl_medicare"]
    thr = pick(am["threshold"], st)
    addl_med = am["rate"] * max(0.0, medicare_wages - thr) + am["rate"] * max(0.0, se_net - max(0.0, thr - medicare_wages))
    ni = fed["niit"]
    nii = inc.taxable_interest + inc.ordinary_dividends + max(0.0, cap_line7)
    niit = ni["rate"] * min(nii, max(0.0, magi - pick(ni["threshold"], st))) if nii > 0 else 0.0
    other_taxes = se_tax + addl_med + niit
    total_tax = tax_after_credits + other_taxes

    # ---------------- EITC
    eitc = 0.0
    e = fed["eitc"]
    n_eic = min(3, sum(1 for d in deps if d.qualifies_eitc(year)))
    eitc_ok = cr.claim_eitc and st != "mfs" and not ret.taxpayer.can_be_claimed
    if eitc_ok and not ret.taxpayer.valid_ssn_for_work:
        eitc_ok = False
        notes.append(_("EITC requiere SSN valido para trabajar."))
    inv_income = inc.taxable_interest + inc.tax_exempt_interest + inc.ordinary_dividends + max(0.0, cap_line7)
    if eitc_ok and inv_income > e["investment_limit"]:
        eitc_ok = False
        notes.append(tr("EITC no disponible: ingresos de inversion mayores a ${n}.", n=f"{e['investment_limit']:,}"))
    if eitc_ok and n_eic == 0:
        ages = [x for x in (tp_age, sp_age) if x is not None]
        if not any(25 <= x < 65 for x in ages):
            eitc_ok = False
    if eitc_ok and earned_income > 0:
        p = e[str(n_eic)]
        credit = min(p["max"], earned_income * p["phasein_rate"])
        start = p["phaseout_start_mfj"] if s == "mfj" else p["phaseout_start"]
        income_for_phase = max(agi, earned_income)
        eitc = max(0.0, min(credit, p["max"] - p["phaseout_rate"] * max(0.0, income_for_phase - start)))

    # ---------------- Pagos
    w2_withheld = sum(w.box2_fed_withheld for w in ret.w2s)
    other_withheld = (inc.investment_withheld + inc.pension_withheld + inc.ira_withheld + inc.ss_withheld
                      + inc.unemployment_withheld + inc.business_withheld)
    withholding = w2_withheld + other_withheld
    ss_max = se["ss_wage_base"] * 0.062
    excess_ss = 0.0
    for owner, withheld_ss in ss_withheld_by_owner.items():
        n_jobs = sum(1 for w in ret.w2s if ("conyuge" if w.owner == "conyuge" else "contribuyente") == owner)
        if n_jobs > 1:  # solo hay exceso reembolsable si hubo mas de un empleador
            excess_ss += max(0.0, withheld_ss - ss_max)
    addl_med_withheld = max(0.0, medicare_withheld - 0.0145 * medicare_wages)
    estimated = ret.payments.federal_estimated + ret.payments.federal_prior_overpayment
    refundable = eitc + actc + aotc_refundable + cr.other_refundable
    total_payments = (withholding + estimated + ret.payments.federal_extension + excess_ss + addl_med_withheld
                      + refundable)
    balance = total_payments - total_tax

    # ---------------- Lineas del 1040 (numeracion aproximada 2025)
    L.update({
        "1a": wages, "1z": wages, "2a": inc.tax_exempt_interest, "2b": inc.taxable_interest,
        "3a": qualified_div, "3b": inc.ordinary_dividends, "4a": inc.ira_gross, "4b": inc.ira_taxable,
        "5a": inc.pension_gross, "5b": inc.pension_taxable, "6a": ssb, "6b": taxable_ss, "7": cap_line7,
        "8": sched1_additional, "9": total_income, "10": adjustments, "11": agi,
        "12": deduction + charity_extra, "13a": qbi_ded, "13b": sched1a_total,
        "14": deduction + charity_extra + qbi_ded + sched1a_total, "15": taxable_income,
        "16": tax, "17": amt, "18": tax_before_credits, "19": ctc_nonref, "20": sched3_nonref,
        "21": total_nonref, "22": tax_after_credits, "23": other_taxes, "24": total_tax,
        "25a": w2_withheld, "25b": other_withheld, "25d": withholding, "26": estimated + ret.payments.federal_extension,
        "27": eitc, "28": actc, "29": aotc_refundable, "31": excess_ss + addl_med_withheld + cr.other_refundable,
        "32": eitc + actc + aotc_refundable + excess_ss + addl_med_withheld + cr.other_refundable,
        "33": total_payments, "34": max(0.0, balance), "37": max(0.0, -balance),
    })
    L = {k: r2(v) for k, v in L.items()}

    ordinary_brackets = fed["brackets"][s]
    result = {
        "year": ret.tax_year, "status": st, "lines": L,
        "wages": wages, "profit": profit, "se_tax": se_tax, "half_se": half_se, "se_net": se_net,
        "taxable_ss": taxable_ss, "net_cap_gain_line7": cap_line7, "net_capital_gain": net_capital_gain,
        "long_term_net": lt_net, "qualified_div": qualified_div,
        "total_income": total_income, "adjustments": adjustments, "agi": agi, "magi": magi,
        "educator": educator, "se_health": se_health, "student_loan": sli,
        "sched1a": {"tips": tips_ded, "overtime": overtime_ded, "car_loan": car_ded, "senior": senior_ded, "total": sched1a_total},
        "standard_deduction": std_total, "std_boxes": boxes, "itemized": itemized, "itemized_net": itemized_net,
        "itemized_detail": {"medical": medical, "salt": salt, "salt_raw": salt_raw, "salt_cap": salt_cap,
                            "interest": interest, "charity": charity, "other": ded.casualty_loss + ded.other_itemized,
                            "limit_37": itemized_limit_red},
        "itemize": itemize, "deduction": deduction, "nonitemizer_charity": charity_extra,
        "qbi": qbi_ded, "taxable_income": taxable_income,
        "tax": tax, "tax_detail": q, "amt": amt, "tax_before_credits": tax_before_credits,
        "credits": {"cdcc": cdcc, "education_nonref": edu_nonref, "aotc_refundable": aotc_refundable, "llc": llc,
                    "savers": savers, "foreign": foreign, "other_nonref": other_nonref,
                    "ctc_nonref": ctc_nonref, "actc": actc, "eitc": eitc, "other_refundable": cr.other_refundable,
                    "n_ctc": n_ctc, "n_odc": n_odc, "n_eitc": n_eic, "n_care": n_care},
        "total_nonrefundable": total_nonref, "tax_after_credits": tax_after_credits,
        "other_taxes": {"se_tax": se_tax, "addl_medicare": addl_med, "niit": niit, "total": other_taxes},
        "total_tax": total_tax,
        "payments": {"withholding": withholding, "w2_withholding": w2_withheld, "other_withholding": other_withheld,
                     "estimated": estimated, "extension": ret.payments.federal_extension, "excess_ss": excess_ss,
                     "addl_medicare_withheld": addl_med_withheld, "refundable_credits": refundable,
                     "total": total_payments},
        "refund": max(0.0, balance), "owed": max(0.0, -balance), "balance": balance,
        "marginal_rate": marginal_rate(taxable_income, ordinary_brackets),
        "effective_rate": (total_tax / total_income) if total_income > 0 else 0.0,
        "earned_income": earned_income, "deadline": fed["deadline"], "notes": notes,
        "income_tax_liability": tax_after_credits,
    }
    return result
