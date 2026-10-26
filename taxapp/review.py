"""Revision de la declaracion (similar a 'CompleteCheck' de TurboTax) / Return review.

Devuelve hallazgos con severidad: 'error' (debe corregirse), 'aviso' (revise), 'info' (sugerencia), 'ok';
y la seccion de la aplicacion donde se corrige.
"""
from __future__ import annotations

import re
from typing import List

from . import data_loader
from .i18n import _, tr
from .local import find_county
from .models import TaxReturn

SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _f(sev, section, msg):
    return {"severity": sev, "section": section, "message": msg}


def valid_ssn(s: str) -> bool:
    if not s or not SSN_RE.match(s.strip()):
        return False
    d = re.sub(r"\D", "", s)
    return not (d[:3] in ("000", "666") or d[0] == "9" or d[3:5] == "00" or d[5:] == "0000")


def money0(v) -> str:
    return f"{v:,.0f}"


def review(ret: TaxReturn, res: dict) -> List[dict]:
    out: List[dict] = []
    fed, st, loc = res["federal"], res["state"], res["local"]
    y = ret.tax_year
    tp = ret.taxpayer

    # ---- Informacion personal
    if not tp.first_name or not tp.last_name:
        out.append(_f("error", "personal", _("Falta el nombre completo del contribuyente.")))
    if not valid_ssn(tp.ssn):
        out.append(_f("error", "personal", _("El SSN/ITIN del contribuyente falta o no tiene formato valido (###-##-####).")))
    if tp.dob and not DATE_RE.match(tp.dob):
        out.append(_f("error", "personal", _("Fecha de nacimiento del contribuyente: use el formato AAAA-MM-DD.")))
    if not tp.dob:
        out.append(_f("aviso", "personal", _("Ingrese la fecha de nacimiento: se usa para la deduccion de mayores de 65 y el EITC.")))
    if ret.has_spouse():
        if not ret.spouse.first_name:
            out.append(_f("error", "personal", _("Falta el nombre del conyuge.")))
        if not valid_ssn(ret.spouse.ssn):
            out.append(_f("error", "personal", _("El SSN/ITIN del conyuge falta o no es valido.")))
    if ret.filing_status == "hoh" and not ret.dependents:
        out.append(_f("error", "personal", _("Cabeza de familia requiere una persona calificada (normalmente un dependiente).")))
    if ret.filing_status == "qss" and not ret.dependents:
        out.append(_f("error", "personal", _("Conyuge sobreviviente calificado requiere un hijo dependiente.")))
    if ret.filing_status == "mfs":
        out.append(_f("info", "personal", _("Casado por separado suele pagar mas (pierde EITC, creditos educativos y nuevas "
                                            "deducciones OBBBA). Compare con 'en conjunto'.")))

    # ---- Direccion
    a = ret.address
    if not a.state:
        out.append(_f("error", "address", _("Seleccione el estado de residencia.")))
    if not a.street or not a.city:
        out.append(_f("aviso", "address", _("La direccion (calle y ciudad) esta incompleta.")))
    if a.zip and not ZIP_RE.match(a.zip.strip()):
        out.append(_f("error", "address", _("Codigo postal (ZIP) invalido: use 12345 o 12345-6789.")))
    if not a.zip:
        out.append(_f("aviso", "address", _("Falta el codigo postal (ZIP).")))
    ld = data_loader.local(y)["states"].get(a.state, {})
    if ld.get("county_tax") and not find_county(ld["counties"], a.county):
        out.append(_f("error", "address", tr("En {st} todos los condados cobran impuesto local: seleccione su condado.", st=a.state)))
    if not a.county:
        out.append(_f("info", "address", _("Indique su condado (se usa para impuestos locales y la informacion de su zona).")))

    # ---- Dependientes
    for d in ret.dependents:
        n = d.full_name() or _("(sin nombre)")
        if not d.dob or not DATE_RE.match(d.dob):
            out.append(_f("error", "dependents", tr("Dependiente {n}: fecha de nacimiento faltante o invalida.", n=n)))
        if d.has_ssn and not valid_ssn(d.ssn):
            out.append(_f("aviso", "dependents", tr("Dependiente {n}: SSN faltante o con formato invalido.", n=n)))
        if not d.has_ssn:
            out.append(_f("info", "dependents", tr("Dependiente {n}: sin SSN no califica para CTC ni EITC (solo $500 ODC).", n=n)))
        if d.months_lived <= 6 and d.is_child_relation():
            out.append(_f("aviso", "dependents", tr("Dependiente {n}: vivio 6 meses o menos con usted; puede no calificar.", n=n)))

    # ---- Ingresos
    for w in ret.w2s:
        if w.box2_fed_withheld > w.box1_wages > 0:
            out.append(_f("error", "income", tr("W-2 {e}: la retencion federal (casilla 2) supera el salario (casilla 1).", e=w.employer)))
        if w.box1_wages > 0 and w.box2_fed_withheld == 0:
            out.append(_f("info", "income", tr("W-2 {e}: sin retencion federal. Verifique la casilla 2.", e=w.employer)))
        if w.state and a.state and w.state.upper() != a.state.upper() and w.box17_state_withheld:
            out.append(_f("aviso", "state", tr("W-2 {e} tiene retencion de {s}: puede necesitar una declaracion de no residente "
                                               "en {s} y el credito por impuestos pagados a otro estado.", e=w.employer, s=w.state)))
        if not w.employer:
            out.append(_f("aviso", "income", _("Hay un W-2 sin nombre de empleador.")))
    inc = ret.income
    if inc.qualified_dividends > inc.ordinary_dividends:
        out.append(_f("error", "income", _("Los dividendos calificados no pueden superar los dividendos ordinarios.")))
    if inc.ira_taxable > inc.ira_gross > 0 or inc.pension_taxable > inc.pension_gross > 0:
        out.append(_f("error", "income", _("La parte tributable de jubilacion supera el monto bruto.")))
    tp_age = ret.taxpayer_age()
    if inc.ira_taxable > 0 and tp_age is not None and tp_age < 59:
        out.append(_f("aviso", "income", _("Retiro de IRA antes de los 59 1/2: puede aplicar una multa del 10% (Formulario 5329) "
                                           "que no esta incluida en el calculo.")))
    if inc.qualified_overtime > fed["wages"] * 0.5 and inc.qualified_overtime > 0:
        out.append(_f("aviso", "income", _("Horas extra: solo se deduce la 'prima' (la mitad extra del pago 1.5x), no el total.")))
    if inc.qualified_tips and not any(w.box7_ss_tips for w in ret.w2s) and not inc.business_gross:
        out.append(_f("info", "income", _("Propinas: deben estar incluidas en sus salarios (W-2) o ingresos de negocio.")))
    if fed["profit"] > 0 and not ret.payments.federal_estimated:
        out.append(_f("info", "payments", _("Tiene ingresos de trabajo independiente sin pagos estimados: podria aplicar "
                                            "una multa por pago insuficiente (Formulario 2210, no calculada).")))
    if fed["profit"] < 0:
        out.append(_f("info", "income", _("El negocio muestra perdida; asegurese de tener registros que la respalden.")))

    # ---- Deducciones
    if ret.deductions.mode == "itemized" and fed["itemized_net"] < fed["standard_deduction"]:
        out.append(_f("aviso", "deductions", tr("Eligio itemizar pero la deduccion estandar (${a}) es mayor que sus itemizadas (${b}).",
                                                a=money0(fed["standard_deduction"]), b=money0(fed["itemized_net"]))))
    if fed["itemized_detail"]["salt_raw"] > fed["itemized_detail"]["salt_cap"] and fed["itemize"]:
        out.append(_f("info", "deductions", tr("SALT limitado a ${a}.", a=money0(fed["itemized_detail"]["salt_cap"]))))
    if ret.deductions.car_loan_interest:
        out.append(_f("info", "deductions", _("Interes de auto: solo vehiculos nuevos de uso personal, ensamblados en EE.UU., "
                                              "con prestamo originado despues del 31-dic-2024. Necesita el VIN.")))
    if ret.deductions.ira_deduction > 7500:
        out.append(_f("aviso", "deductions", _("La deduccion de IRA supera el limite anual habitual.")))

    # ---- Pagos y saldo
    if fed["owed"] > 1000 and fed["payments"]["withholding"] < 0.9 * fed["total_tax"]:
        out.append(_f("aviso", "payments", _("Debe mas de $1,000: podria aplicar multa por pago estimado insuficiente. "
                                             "Considere ajustar su W-4.")))
    if st.get("type") not in ("none", None) and st.get("withholding", 0) == 0 and st.get("tax", 0) > 0:
        out.append(_f("info", "state", _("No hay retencion estatal en sus W-2; verifique la casilla 17.")))

    # ---- Notas de los motores de calculo (ya traducidas)
    for n in fed.get("notes", []):
        out.append(_f("info", "federal", n))
    for n in loc.get("notes", []):
        out.append(_f("info", "local", n))

    if not [x for x in out if x["severity"] == "error"]:
        out.insert(0, _f("ok", "review", _("No se encontraron errores que impidan generar la declaracion.")))
    return out
