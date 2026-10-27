"""Preguntas guiadas para completar los formularios oficiales / Guided questions to complete the official forms.

El cálculo solo necesita montos; los formularios del IRS piden además datos de identificación (SSN, dirección,
ocupación), respuestas de sí/no (activos digitales, cuentas en el extranjero) y detalles (pagadores, proveedores de
cuidado, datos del negocio). Este módulo decide qué preguntas aplican a la declaración y cuáles faltan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from ..i18n import N_
from ..models import TaxReturn

SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")


@dataclass
class Question:
    key: str
    group: str                     # título del grupo (clave de traducción)
    text: str                      # pregunta (clave de traducción) o texto ya traducido si fmt=False
    kind: str                      # text | money | yesno | choice | list
    target: Callable[[TaxReturn], object] = None
    attr: str = ""
    help: str = ""
    choices: List[Tuple[str, str]] = field(default_factory=list)   # (valor, etiqueta)
    required: bool = False         # impide generar los formularios finales si falta
    list_kind: str = ""            # para kind == "list"
    check: Optional[Callable[[object], bool]] = None   # True si el valor actual es aceptable
    width: int = 34
    params: dict = field(default_factory=dict)          # valores para tr() del texto

    def obj(self, ret):
        return self.target(ret) if self.target else None

    def value(self, ret):
        o = self.obj(ret)
        return getattr(o, self.attr) if (o is not None and self.attr) else None

    def is_missing(self, ret) -> bool:
        if self.kind == "list":
            return bool(self.check and not self.check(ret))
        v = self.value(ret)
        if self.check:
            return not self.check(v)
        if self.kind in ("text",):
            return not str(v or "").strip()
        # Sí/No, opciones y montos opcionales: falta mientras no se haya respondido en las preguntas guiadas
        return self.key not in ret.filing.answered


def _ssn_ok(v) -> bool:
    return bool(SSN_RE.match((v or "").strip()))


def _digits(v, n) -> bool:
    d = "".join(ch for ch in (v or "") if ch.isdigit())
    return len(d) == n


def questions(ret: TaxReturn, res: dict) -> List[Question]:
    """Lista de preguntas que aplican a esta declaración (en orden)."""
    fed = res["federal"]
    L = fed["lines"]
    inc, ded, cr, fi = ret.income, ret.deductions, ret.credits, ret.filing
    Q: List[Question] = []
    G1 = N_("Identificación")
    tp = lambda r: r.taxpayer  # noqa: E731
    sp = lambda r: r.spouse  # noqa: E731
    Q.append(Question("tp_ssn", G1, N_("Su número de Seguro Social (SSN) o ITIN"), "text", tp, "ssn", required=True,
                      check=_ssn_ok, width=16, help=N_("9 dígitos, formato ###-##-####. Debe coincidir con su tarjeta.")))
    Q.append(Question("tp_occ", G1, N_("Su ocupación"), "text", tp, "occupation",
                      help=N_("Se imprime junto a su firma. Escríbala de preferencia en inglés (p. ej. COOK, DRIVER).")))
    if ret.has_spouse():
        Q.append(Question("sp_name", G1, N_("Nombre de su cónyuge"), "text", sp, "first_name", required=True))
        Q.append(Question("sp_last", G1, N_("Apellido(s) de su cónyuge"), "text", sp, "last_name", required=True))
        Q.append(Question("sp_ssn", G1, N_("SSN o ITIN de su cónyuge"), "text", sp, "ssn", required=True,
                          check=_ssn_ok, width=16))
    if ret.is_joint():
        Q.append(Question("sp_occ", G1, N_("Ocupación de su cónyuge"), "text", sp, "occupation"))
    for i, d in enumerate(ret.dependents):
        Q.append(Question(f"dep_ssn{i}", G1, N_("SSN del dependiente {n}"), "text", lambda r, i=i: r.dependents[i],
                          "ssn", required=True, check=_ssn_ok, width=16, params={"n": d.full_name() or i + 1}))
    a = lambda r: r.address  # noqa: E731
    G2 = N_("Dirección postal")
    Q.append(Question("street", G2, N_("Calle y número (o apartado postal)"), "text", a, "street", required=True, width=40))
    Q.append(Question("city", G2, N_("Ciudad"), "text", a, "city", required=True, width=28))
    Q.append(Question("zip", G2, N_("Código postal (ZIP)"), "text", a, "zip", required=True, width=12,
                      check=lambda v: bool(re.match(r"^\d{5}(-\d{4})?$", (v or "").strip()))))
    if not ret.address.state:
        Q.append(Question("state", G2, N_("Estado (2 letras, p. ej. TX)"), "text", a, "state", required=True, width=6,
                          check=lambda v: bool(re.match(r"^[A-Za-z]{2}$", (v or "").strip()))))
    G3 = N_("Preguntas del Formulario 1040")
    f = lambda r: r.filing  # noqa: E731
    Q.append(Question("digital", G3, N_("En el año, ¿recibió, vendió, intercambió o transfirió activos digitales "
                                        "(criptomonedas, NFT, stablecoins)?"), "yesno", f, "digital_assets",
                      help=N_("Responda Sí aunque haya sido como pago por trabajo. Comprar con dinero y solo guardar "
                              "no cuenta como Sí.")))
    Q.append(Question("pec", G3, N_("¿Desea destinar $3 al Fondo de Campaña Presidencial?"), "yesno", tp,
                      "presidential_fund", help=N_("No cambia su impuesto ni su reembolso.")))
    if ret.is_joint():
        Q.append(Question("pec_sp", G3, N_("¿Su cónyuge desea destinar $3 al Fondo de Campaña Presidencial?"), "yesno",
                          sp, "presidential_fund"))
    Q.append(Question("ippin", G3, N_("PIN de Protección de Identidad del IRS (si lo tiene)"), "text", tp, "ip_pin",
                      width=10, check=lambda v: not v or _digits(v, 6),
                      help=N_("6 dígitos que el IRS envía por carta (CP01A) o en su cuenta en línea. Déjelo en blanco "
                              "si no tiene.")))
    if ret.is_joint():
        Q.append(Question("ippin_sp", G3, N_("PIN de Protección de Identidad de su cónyuge (si lo tiene)"), "text", sp,
                          "ip_pin", width=10, check=lambda v: not v or _digits(v, 6)))
    if ret.filing_status in ("hoh", "qss"):
        Q.append(Question("hoh_name", G3, N_("Si la persona que le da derecho a este estado civil es un hijo que NO es "
                                             "su dependiente, escriba su nombre"), "text", f, "hoh_qualifying_name"))
    if ret.filing_status in ("mfs", "hoh"):
        Q.append(Question("apart", G3, N_("¿Vivió separado(a) de su cónyuge los últimos 6 meses del año?"), "yesno", f,
                          "lived_apart"))
    G4 = N_("Reembolso y pagos")
    if L.get("34", 0) >= 1:
        Q.append(Question("dd", G4, N_("¿Desea recibir el reembolso por depósito directo?"), "yesno", f, "direct_deposit",
                          help=N_("Es la forma más rápida. Si responde No, el IRS envía un cheque por correo.")))
        if fi.direct_deposit:
            Q.append(Question("routing", G4, N_("Número de ruta bancaria (9 dígitos)"), "text", f, "routing",
                              required=True, width=14, check=lambda v: _digits(v, 9),
                              help=N_("Aparece en la parte inferior izquierda de sus cheques.")))
            Q.append(Question("account", G4, N_("Número de cuenta"), "text", f, "account", required=True, width=22,
                              check=lambda v: 4 <= len("".join(ch for ch in (v or "") if ch.isalnum())) <= 17))
            Q.append(Question("acct_type", G4, N_("Tipo de cuenta"), "choice", f, "account_type",
                              choices=[("checking", N_("Corriente (checking)")), ("savings", N_("Ahorros (savings)"))]))
        Q.append(Question("next_year", G4, N_("Parte del reembolso que desea aplicar a sus impuestos estimados del año "
                                              "próximo (opcional)"), "money", f, "apply_to_next_year"))
    G5 = N_("Tercero designado y preparador")
    Q.append(Question("designee", G5, N_("¿Autoriza a otra persona (por ejemplo, su preparador) a hablar con el IRS "
                                         "sobre esta declaración?"), "yesno", f, "designee"))
    if fi.designee:
        Q.append(Question("des_name", G5, N_("Nombre del designado"), "text", f, "designee_name", required=True))
        Q.append(Question("des_phone", G5, N_("Teléfono del designado"), "text", f, "designee_phone", width=18))
        Q.append(Question("des_pin", G5, N_("PIN del designado (5 dígitos que él o ella elige)"), "text", f,
                          "designee_pin", width=8, required=True, check=lambda v: _digits(v, 5)))
    # ----- Anexo B
    if inc.taxable_interest > 1500 or inc.ordinary_dividends > 1500 or fi.foreign_account:
        GB = N_("Anexo B — intereses y dividendos")
        if inc.taxable_interest > 1500:
            Q.append(Question("int_payers", GB, N_("Lista de quienes le pagaron intereses (banco, emisor) y cuánto"),
                              "list", list_kind="interest_payers",
                              check=lambda r: abs(sum(p.amount for p in r.income.interest_payers)
                                                  - r.income.taxable_interest) < 1,
                              help=N_("El Anexo B exige el nombre de cada pagador. La suma debe igualar sus intereses "
                                      "tributables.")))
        if inc.ordinary_dividends > 1500:
            Q.append(Question("div_payers", GB, N_("Lista de quienes le pagaron dividendos y cuánto"), "list",
                              list_kind="dividend_payers",
                              check=lambda r: abs(sum(p.amount for p in r.income.dividend_payers)
                                                  - r.income.ordinary_dividends) < 1))
        Q.append(Question("foreign", GB, N_("¿Tuvo cuentas financieras en el extranjero (o firma autorizada en ellas)?"),
                          "yesno", f, "foreign_account"))
        if fi.foreign_account:
            Q.append(Question("fbar", GB, N_("¿Debe presentar el informe FinCEN 114 (FBAR)? (saldo combinado mayor de "
                                             "$10,000 en algún momento del año)"), "yesno", f, "fbar_required"))
            if fi.fbar_required:
                Q.append(Question("countries", GB, N_("País(es) donde están las cuentas"), "text", f,
                                  "foreign_countries", required=True))
        Q.append(Question("trust", GB, N_("¿Recibió una distribución de un fideicomiso extranjero, o fue su creador?"),
                          "yesno", f, "foreign_trust"))
    # ----- Anexo C
    if inc.business_gross or inc.schedule_c_expenses():
        GC = N_("Anexo C — su negocio")
        i_ = lambda r: r.income  # noqa: E731
        Q.append(Question("biz_activity", GC, N_("Actividad principal del negocio (producto o servicio)"), "text", i_,
                          "business_activity", required=True,
                          help=N_("Ejemplos: Construction - painting; Uber driver; House cleaning. De preferencia en inglés.")))
        Q.append(Question("biz_code", GC, N_("Código de actividad de 6 dígitos (instrucciones del Anexo C)"), "text", i_,
                          "business_code", required=True, width=10, check=lambda v: _digits(v, 6),
                          help=N_("Ejemplos: 238320 pintura; 485310 taxi/rideshare; 561720 limpieza; 812111 barbería; "
                                  "541990 servicios profesionales. Lista completa en las instrucciones del Anexo C.")))
        Q.append(Question("biz_name", GC, N_("Nombre comercial (si tiene uno distinto a su nombre)"), "text", i_,
                          "business_name"))
        Q.append(Question("biz_ein", GC, N_("EIN del negocio (si tiene)"), "text", i_, "business_ein", width=14,
                          check=lambda v: not v or _digits(v, 9)))
        Q.append(Question("biz_addr", GC, N_("Dirección del negocio (si es distinta a su casa)"), "text", i_,
                          "business_address", width=40))
        if inc.business_address:
            Q.append(Question("biz_city", GC, N_("Ciudad, estado y ZIP del negocio"), "text", i_, "business_city",
                              width=40))
        Q.append(Question("biz_method", GC, N_("Método de contabilidad"), "choice", i_, "accounting_method",
                          choices=[("cash", N_("Efectivo (cash) — el más común")), ("accrual", N_("Acumulación (accrual)"))]))
        Q.append(Question("biz_part", GC, N_("¿Participó materialmente en el negocio (lo trabajó usted mismo)?"), "yesno",
                          i_, "material_participation"))
        Q.append(Question("biz_new", GC, N_("¿Empezó o compró este negocio durante el año?"), "yesno", i_,
                          "business_started"))
        Q.append(Question("biz_1099", GC, N_("¿Hizo pagos que lo obligan a emitir formularios 1099 (p. ej. $600 o más a "
                                             "un contratista)?"), "yesno", i_, "made_1099_payments"))
        if inc.made_1099_payments:
            Q.append(Question("biz_1099f", GC, N_("¿Presentó o presentará esos formularios 1099?"), "yesno", i_,
                              "filed_1099s"))
        if inc.exp_car:
            Q.append(Question("veh_date", GC, N_("Fecha en que empezó a usar el vehículo para el negocio (MM/DD/AAAA)"),
                              "text", i_, "vehicle_in_service", required=True, width=14,
                              check=lambda v: bool(re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", (v or "").strip()))))
            Q.append(Question("veh_biz", GC, N_("Millas de negocio en el año"), "money", i_, "miles_business",
                              required=True, check=lambda v: (v or 0) > 0))
            Q.append(Question("veh_comm", GC, N_("Millas de ida y vuelta al trabajo (commuting)"), "money", i_,
                              "miles_commuting"))
            Q.append(Question("veh_other", GC, N_("Otras millas (personales)"), "money", i_, "miles_other"))
            Q.append(Question("veh_pers", GC, N_("¿El vehículo estaba disponible para uso personal fuera del horario de "
                                                 "trabajo?"), "yesno", i_, "vehicle_personal_use"))
            Q.append(Question("veh_other_car", GC, N_("¿Usted (o su cónyuge) tiene otro vehículo para uso personal?"),
                              "yesno", i_, "other_vehicle"))
            Q.append(Question("veh_evid", GC, N_("¿Tiene pruebas (registro de millas) que respalden la deducción?"),
                              "yesno", i_, "vehicle_evidence"))
            if inc.vehicle_evidence:
                Q.append(Question("veh_writ", GC, N_("¿Esas pruebas están por escrito?"), "yesno", i_,
                                  "vehicle_evidence_written"))
        if inc.home_office_sqft:
            Q.append(Question("home_total", GC, N_("Pies cuadrados totales de su vivienda (oficina en casa)"), "money",
                              i_, "home_total_sqft", required=True, check=lambda v: (v or 0) > 0))
        if inc.exp_other and not inc.other_expenses:
            Q.append(Question("other_exp", GC, N_("Detalle de 'otros gastos' del negocio (tipo y monto)"), "list",
                              list_kind="other_expenses",
                              check=lambda r: bool(r.income.other_expenses),
                              help=N_("El IRS necesita saber qué son: p. ej. 'Licencias', 'Uniformes', 'Herramientas'.")))
    # ----- Anexo D
    if inc.short_term_gain or inc.long_term_gain:
        Q.append(Question("sales", N_("Anexo D — ventas de inversiones"),
                          N_("Detalle de cada venta (1099-B): descripción, fechas, precio de venta y costo"), "list",
                          list_kind="sales", check=lambda r: not (r.income.short_term_gain or r.income.long_term_gain),
                          help=N_("Ingresó solo la ganancia neta. Para el Anexo D y el Formulario 8949 se necesita el "
                                  "precio de venta y el costo; al agregar las ventas, ponga en 0 la ganancia neta para "
                                  "no contarla dos veces.")))
    # ----- 2441
    if fed["credits"]["cdcc"] >= 0.5 or cr.dependent_care_benefits:
        Q.append(Question("providers", N_("Formulario 2441 — cuidado de dependientes"),
                          N_("Proveedores de cuidado: nombre, dirección, SSN o EIN y monto pagado"), "list",
                          list_kind="care_providers",
                          check=lambda r: bool(r.credits.care_providers) and all(
                              p.name and p.address and p.tin for p in r.credits.care_providers),
                          required=True,
                          help=N_("Pida al proveedor el formulario W-10 o su identificación fiscal. Sin estos datos "
                                  "el IRS puede negar el crédito.")))
    # ----- 8863
    if cr.students:
        Q.append(Question("students", N_("Formulario 8863 — educación"),
                          N_("Datos de cada estudiante: SSN, institución, dirección y EIN (del 1098-T)"), "list",
                          list_kind="students", required=True,
                          check=lambda r: all(_ssn_ok(s.ssn) and s.school and s.school_address
                                              for s in r.credits.students)))
    # ----- 8889
    if ded.hsa_deduction or ded.hsa_employer:
        Q.append(Question("hsa_cov", N_("Formulario 8889 — cuenta HSA"),
                          N_("Tipo de cobertura de su seguro médico con deducible alto (HDHP)"), "choice",
                          lambda r: r.deductions, "hsa_coverage", required=True,
                          choices=[("self", N_("Individual (self-only)")), ("family", N_("Familiar (family)"))],
                          check=lambda v: v in ("self", "family")))
        Q.append(Question("hsa_emp", N_("Formulario 8889 — cuenta HSA"),
                          N_("Aportes de su empleador a la HSA (W-2 casilla 12, código W)"), "money",
                          lambda r: r.deductions, "hsa_employer"))
    # ----- Anexo 1-A auto
    if ded.car_loan_interest:
        Q.append(Question("vin", N_("Anexo 1-A — interés de préstamo de auto"),
                          N_("Número de identificación del vehículo (VIN, 17 caracteres)"), "text",
                          lambda r: r.deductions, "car_vin", required=True, width=24,
                          check=lambda v: len((v or "").replace(" ", "")) == 17))
    return Q


def missing(ret: TaxReturn, res: dict, required_only: bool = False) -> List[Question]:
    return [q for q in questions(ret, res) if q.is_missing(ret) and (q.required or not required_only)]
