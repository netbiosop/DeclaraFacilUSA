"""Modelo de datos de una declaracion de impuestos (federal + estatal + local).

Todas las clases son dataclasses serializables a JSON con to_dict()/from_dict().
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from datetime import date
from typing import List, Optional

from .i18n import N_

# Etiquetas en espanol (clave de traduccion); se muestran con i18n._()
FILING_STATUSES = {
    "single": N_("Soltero(a)"),
    "mfj": N_("Casado(a) declarando en conjunto"),
    "mfs": N_("Casado(a) declarando por separado"),
    "hoh": N_("Cabeza de familia (Head of Household)"),
    "qss": N_("Conyuge sobreviviente calificado(a)"),
}


def _num(v) -> float:
    try:
        if v in (None, ""):
            return 0.0
        return float(str(v).replace(",", "").replace("$", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def nonzero_amounts(section) -> dict:
    """Montos distintos de cero de una sección; las casillas sí/no (bool) no son montos."""
    return {k: v for k, v in vars(section).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v}


def _from_dict(cls, data: dict):
    if data is None:
        return cls()
    kwargs = {}
    names = {f.name: f for f in fields(cls)}
    for k, v in data.items():
        if k not in names:
            continue
        kwargs[k] = v
    return cls(**kwargs)


def age_at_year_end(dob: str, year: int) -> Optional[int]:
    """Edad al 31 de diciembre del ano fiscal. dob en formato AAAA-MM-DD."""
    if not dob:
        return None
    try:
        y, m, d = (int(x) for x in dob.strip().split("-"))
        born = date(y, m, d)
    except (ValueError, TypeError):
        return None
    # El IRS considera que una persona cumple anos el dia ANTERIOR a su cumpleanos, por eso se mide al 1 de enero
    # del ano siguiente (ej.: nacido el 1-ene-1961 cuenta como 65 anos al cierre de 2025).
    ref = date(year + 1, 1, 1)
    return ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))


@dataclass
class Person:
    first_name: str = ""
    last_name: str = ""
    ssn: str = ""
    dob: str = ""               # AAAA-MM-DD
    occupation: str = ""
    blind: bool = False
    valid_ssn_for_work: bool = True
    can_be_claimed: bool = False  # puede ser reclamado como dependiente por otra persona
    ip_pin: str = ""              # PIN de protección de identidad del IRS (6 dígitos), si lo tiene
    presidential_fund: bool = False  # $3 al fondo de campaña presidencial (no cambia el impuesto)

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Dependent:
    first_name: str = ""
    last_name: str = ""
    ssn: str = ""
    relationship: str = "Hijo(a)"
    dob: str = ""
    months_lived: int = 12
    has_ssn: bool = True
    full_time_student: bool = False
    disabled: bool = False
    lived_in_us: bool = True      # vivió con usted en EE.UU. (columna 5b del 1040 / Anexo EIC)

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def age(self, year: int) -> Optional[int]:
        return age_at_year_end(self.dob, year)

    def is_child_relation(self) -> bool:
        r = (self.relationship or "").lower()
        return any(k in r for k in ("hijo", "hija", "hijastr", "nieto", "nieta", "herman", "sobrin", "crianza", "acogid",
                                    "child", "son", "daughter", "foster", "brother", "sister", "sibling", "niece", "nephew"))

    def qualifies_ctc(self, year: int) -> bool:
        a = self.age(year)
        return self.has_ssn and a is not None and a < 17 and self.months_lived > 6 and self.is_child_relation()

    def qualifies_eitc(self, year: int) -> bool:
        a = self.age(year)
        if a is None or self.months_lived <= 6 or not self.is_child_relation() or not self.has_ssn:
            return False
        return a < 19 or (a < 24 and self.full_time_student) or self.disabled

    def qualifies_care(self, year: int) -> bool:
        a = self.age(year)
        return (a is not None and a < 13) or self.disabled


@dataclass
class W2:
    employer: str = ""
    ein: str = ""
    owner: str = "contribuyente"   # contribuyente | conyuge
    box1_wages: float = 0.0
    box2_fed_withheld: float = 0.0
    box3_ss_wages: float = 0.0
    box4_ss_withheld: float = 0.0
    box5_medicare_wages: float = 0.0
    box6_medicare_withheld: float = 0.0
    box7_ss_tips: float = 0.0
    box12_401k: float = 0.0
    state: str = ""
    box16_state_wages: float = 0.0
    box17_state_withheld: float = 0.0
    box18_local_wages: float = 0.0
    box19_local_withheld: float = 0.0
    box20_locality: str = ""

    def __post_init__(self):
        for f in fields(self):
            if f.type in ("float", float):
                setattr(self, f.name, _num(getattr(self, f.name)))


@dataclass
class Payer:
    """Pagador de intereses o dividendos (Anexo B)."""
    name: str = ""
    amount: float = 0.0

    def __post_init__(self):
        self.amount = _num(self.amount)


@dataclass
class Sale:
    """Venta de acciones, fondos, criptomonedas u otro activo de capital (1099-B / 1099-DA / Formulario 8949)."""
    description: str = ""
    acquired: str = ""            # fecha de compra (MM/DD/AAAA o "VARIOUS")
    sold: str = ""                # fecha de venta
    proceeds: float = 0.0         # precio de venta (d)
    cost: float = 0.0             # costo o base (e)
    adjustment: float = 0.0       # ajuste (g), p. ej. venta ficticia (wash sale) no permitida
    code: str = ""                # código de ajuste (f)
    term: str = "long"            # short | long
    basis_reported: bool = True   # el 1099-B dice que la base se informó al IRS
    form_1099: bool = True        # recibió 1099-B / 1099-DA por esta venta
    digital: bool = False         # activo digital (1099-DA)

    def __post_init__(self):
        for n in ("proceeds", "cost", "adjustment"):
            setattr(self, n, _num(getattr(self, n)))

    def gain(self) -> float:
        return self.proceeds - self.cost + self.adjustment

    def box(self) -> str:
        """Casilla del Formulario 8949 (A-L)."""
        short = self.term == "short"
        if self.digital:
            k = "GHI" if short else "JKL"
        else:
            k = "ABC" if short else "DEF"
        if not self.form_1099:
            return k[2]
        return k[0] if self.basis_reported else k[1]


@dataclass
class OtherExpense:
    description: str = ""
    amount: float = 0.0

    def __post_init__(self):
        self.amount = _num(self.amount)


@dataclass
class Income:
    taxable_interest: float = 0.0
    tax_exempt_interest: float = 0.0
    ordinary_dividends: float = 0.0
    qualified_dividends: float = 0.0
    short_term_gain: float = 0.0          # neto (puede ser negativo)
    long_term_gain: float = 0.0           # neto (puede ser negativo)
    capital_gain_distributions: float = 0.0
    capital_loss_carryover: float = 0.0   # positivo
    investment_withheld: float = 0.0
    # Retiro
    pension_gross: float = 0.0
    pension_taxable: float = 0.0
    pension_withheld: float = 0.0
    ira_gross: float = 0.0
    ira_taxable: float = 0.0
    ira_withheld: float = 0.0
    social_security: float = 0.0          # SSA-1099 casilla 5
    ss_withheld: float = 0.0
    # Otros
    unemployment: float = 0.0
    unemployment_withheld: float = 0.0
    state_refund_taxable: float = 0.0
    gambling: float = 0.0
    other_income: float = 0.0
    other_income_desc: str = ""
    interest_payers: List[Payer] = field(default_factory=list)
    dividend_payers: List[Payer] = field(default_factory=list)
    sales: List[Sale] = field(default_factory=list)
    # Trabajo independiente (Schedule C simplificado)
    business_name: str = ""
    business_gross: float = 0.0
    business_returns: float = 0.0
    business_cogs: float = 0.0
    exp_advertising: float = 0.0
    exp_car: float = 0.0
    exp_insurance: float = 0.0
    exp_office: float = 0.0
    exp_supplies: float = 0.0
    exp_phone_internet: float = 0.0
    exp_travel_meals: float = 0.0       # comidas de negocio (se deducen al 50%)
    exp_travel: float = 0.0             # viajes de negocio (100%)
    exp_contract_labor: float = 0.0
    exp_rent: float = 0.0
    exp_other: float = 0.0
    home_office_sqft: float = 0.0       # metodo simplificado $5/pie2 hasta 300
    home_total_sqft: float = 0.0        # pies cuadrados totales de la vivienda (Anexo C línea 30)
    business_withheld: float = 0.0
    # Datos del Anexo C (encabezado y Parte IV)
    business_activity: str = ""         # A: actividad principal (producto o servicio)
    business_code: str = ""             # B: código de 6 dígitos de las instrucciones
    business_ein: str = ""              # D
    business_address: str = ""          # E
    business_city: str = ""             # E: ciudad, estado y ZIP
    accounting_method: str = "cash"     # cash | accrual
    material_participation: bool = True
    business_started: bool = False      # H
    made_1099_payments: bool = False    # I
    filed_1099s: bool = True            # J
    other_expenses: List[OtherExpense] = field(default_factory=list)   # Parte V (detalle de 'otros gastos')
    vehicle_in_service: str = ""        # 43: fecha MM/DD/AAAA
    miles_business: float = 0.0
    miles_commuting: float = 0.0
    miles_other: float = 0.0
    vehicle_personal_use: bool = True   # 45
    other_vehicle: bool = True          # 46
    vehicle_evidence: bool = True       # 47a
    vehicle_evidence_written: bool = True  # 47b
    # OBBBA (Schedule 1-A)
    qualified_tips: float = 0.0
    qualified_overtime: float = 0.0      # solo la "prima" (la mitad del 1.5x)

    def __post_init__(self):
        for f in fields(self):
            if f.type in ("float", float):
                setattr(self, f.name, _num(getattr(self, f.name)))
        self.interest_payers = [x if isinstance(x, Payer) else _from_dict(Payer, x) for x in (self.interest_payers or [])]
        self.dividend_payers = [x if isinstance(x, Payer) else _from_dict(Payer, x) for x in (self.dividend_payers or [])]
        self.sales = [x if isinstance(x, Sale) else _from_dict(Sale, x) for x in (self.sales or [])]
        self.other_expenses = [x if isinstance(x, OtherExpense) else _from_dict(OtherExpense, x)
                               for x in (self.other_expenses or [])]

    def other_expenses_total(self) -> float:
        """'Otros gastos' del Anexo C: el detalle (Parte V) si existe; si no, el monto global."""
        detail = sum(x.amount for x in self.other_expenses)
        return detail if self.other_expenses else self.exp_other

    def home_office_deduction(self) -> float:
        return min(self.home_office_sqft, 300) * 5

    def sales_gain(self, term: str) -> float:
        return sum(s.gain() for s in self.sales if s.term == term)

    def schedule_c_expenses(self) -> float:
        meals_half = self.exp_travel_meals * 0.5
        return (self.business_cogs + self.business_returns + self.exp_advertising + self.exp_car + self.exp_insurance
                + self.exp_office + self.exp_supplies + self.exp_phone_internet + meals_half + self.exp_travel
                + self.exp_contract_labor + self.exp_rent + self.other_expenses_total() + self.home_office_deduction())

    def schedule_c_profit(self) -> float:
        if not self.business_gross and not self.schedule_c_expenses():
            return 0.0
        return self.business_gross - self.schedule_c_expenses()


@dataclass
class Deductions:
    mode: str = "auto"                      # auto | standard | itemized
    # Ajustes (Schedule 1, parte II)
    educator_expenses: float = 0.0
    hsa_deduction: float = 0.0
    ira_deduction: float = 0.0
    se_health_insurance: float = 0.0
    student_loan_interest: float = 0.0
    other_adjustments: float = 0.0
    hsa_coverage: str = ""                  # "" (no indicado) | self | family  (Formulario 8889)
    hsa_employer: float = 0.0               # aportes del empleador a la HSA (W-2 casilla 12, código W)
    # Schedule 1-A (OBBBA)
    car_loan_interest: float = 0.0          # vehiculo nuevo ensamblado en EE.UU., prestamo desde 2025
    car_vin: str = ""                       # número de identificación del vehículo (VIN, 17 caracteres)
    # Itemizadas (Schedule A)
    medical: float = 0.0
    salt_use_sales_tax: bool = False
    state_income_tax_paid_extra: float = 0.0   # pagos estimados/saldo del ano anterior pagados en el ano
    sales_tax_paid: float = 0.0
    real_estate_tax: float = 0.0
    personal_property_tax: float = 0.0
    mortgage_interest: float = 0.0
    mortgage_points: float = 0.0
    investment_interest: float = 0.0
    charity_cash: float = 0.0
    charity_noncash: float = 0.0
    casualty_loss: float = 0.0
    other_itemized: float = 0.0

    def __post_init__(self):
        for f in fields(self):
            if f.type in ("float", float):
                setattr(self, f.name, _num(getattr(self, f.name)))


@dataclass
class Student:
    name: str = ""
    credit: str = "AOTC"     # AOTC | LLC
    expenses: float = 0.0
    ssn: str = ""
    school: str = ""          # institución educativa
    school_address: str = ""
    school_ein: str = ""      # EIN de la institución (Formulario 1098-T)
    got_1098t: bool = True
    half_time: bool = True    # matriculado al menos medio tiempo (requisito del AOTC)
    first_four_years: bool = True  # no había completado 4 años de estudios superiores antes del año

    def __post_init__(self):
        self.expenses = _num(self.expenses)


@dataclass
class CareProvider:
    """Proveedor de cuidado (Formulario 2441, Parte I)."""
    name: str = ""
    address: str = ""
    tin: str = ""             # SSN o EIN del proveedor
    amount: float = 0.0
    household_employee: bool = False

    def __post_init__(self):
        self.amount = _num(self.amount)


@dataclass
class Credits:
    care_expenses: float = 0.0
    care_persons: int = 0                 # 0 = calcular por dependientes
    dependent_care_benefits: float = 0.0  # W-2 casilla 10
    students: List[Student] = field(default_factory=list)
    care_providers: List[CareProvider] = field(default_factory=list)
    retirement_contrib_taxpayer: float = 0.0
    retirement_contrib_spouse: float = 0.0
    foreign_tax_paid: float = 0.0
    other_nonrefundable: float = 0.0
    other_refundable: float = 0.0
    claim_eitc: bool = True

    def __post_init__(self):
        self.students = [s if isinstance(s, Student) else _from_dict(Student, s) for s in (self.students or [])]
        self.care_providers = [c if isinstance(c, CareProvider) else _from_dict(CareProvider, c)
                               for c in (self.care_providers or [])]
        for n in ("care_expenses", "dependent_care_benefits", "retirement_contrib_taxpayer", "retirement_contrib_spouse",
                  "foreign_tax_paid", "other_nonrefundable", "other_refundable"):
            setattr(self, n, _num(getattr(self, n)))
        self.care_persons = int(_num(self.care_persons))


@dataclass
class Payments:
    federal_estimated: float = 0.0
    federal_extension: float = 0.0
    federal_prior_overpayment: float = 0.0
    state_estimated: float = 0.0
    state_extension: float = 0.0
    local_estimated: float = 0.0

    def __post_init__(self):
        for f in fields(self):
            setattr(self, f.name, _num(getattr(self, f.name)))


@dataclass
class Address:
    street: str = ""
    apt: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    county: str = ""
    locality: str = ""            # jurisdiccion local de residencia (de local_YYYY.json) o ""
    work_locality: str = ""       # jurisdiccion donde trabaja (impuestos por lugar de trabajo)
    months_in_state: int = 12
    phone: str = ""
    email: str = ""


@dataclass
class CustomLocalTax:
    name: str = ""
    base: str = "earned"      # earned | agi | state_taxable | state_tax
    rate: float = 0.0         # porcentaje, p. ej. 1.5 = 1.5%
    withheld: float = 0.0

    def __post_init__(self):
        self.rate = _num(self.rate)
        self.withheld = _num(self.withheld)


@dataclass
class StateExtras:
    additions: float = 0.0
    subtractions: float = 0.0
    itemized_override: float = 0.0       # deducciones estatales itemizadas (si conviene)
    other_state_credit: float = 0.0      # credito por impuestos pagados a otro estado
    other_credits: float = 0.0
    refundable_credits: float = 0.0
    locality_rate_override: float = 0.0  # para jurisdicciones "editable" (porcentaje)
    custom_local: List[CustomLocalTax] = field(default_factory=list)

    def __post_init__(self):
        self.custom_local = [c if isinstance(c, CustomLocalTax) else _from_dict(CustomLocalTax, c) for c in (self.custom_local or [])]
        for n in ("additions", "subtractions", "itemized_override", "other_state_credit", "other_credits",
                  "refundable_credits", "locality_rate_override"):
            setattr(self, n, _num(getattr(self, n)))


@dataclass
class FilingInfo:
    """Datos que solo se usan para llenar los formularios oficiales (no cambian el cálculo)."""
    digital_assets: bool = False          # 1040: ¿recibió, vendió o intercambió activos digitales?
    lived_apart: bool = False             # MFS/HOH: vivió separado del cónyuge los últimos 6 meses
    hoh_qualifying_name: str = ""         # HOH/QSS: nombre del hijo calificado si NO es su dependiente
    # Reembolso
    direct_deposit: bool = False
    routing: str = ""                     # número de ruta (9 dígitos)
    account: str = ""                     # número de cuenta
    account_type: str = "checking"        # checking | savings
    apply_to_next_year: float = 0.0       # parte del reembolso aplicada a impuestos estimados del próximo año
    # Tercero designado
    designee: bool = False
    designee_name: str = ""
    designee_phone: str = ""
    designee_pin: str = ""                # 5 dígitos elegidos por el designado
    # Anexo B, Parte III
    foreign_account: bool = False
    fbar_required: bool = False
    foreign_countries: str = ""
    foreign_trust: bool = False
    # Preparador pagado (datos en Configuración); se imprime si está activado
    use_preparer: bool = True
    forms_language: str = ""              # "" = idioma de la aplicación | en | es (versiones oficiales en español)
    answered: List[str] = field(default_factory=list)   # preguntas guiadas ya respondidas (claves)

    def __post_init__(self):
        self.apply_to_next_year = _num(self.apply_to_next_year)
        self.answered = [str(k) for k in (self.answered or [])]


@dataclass
class TaxReturn:
    tax_year: int = 2025
    filing_status: str = "single"
    taxpayer: Person = field(default_factory=Person)
    spouse: Person = field(default_factory=Person)
    address: Address = field(default_factory=Address)
    dependents: List[Dependent] = field(default_factory=list)
    w2s: List[W2] = field(default_factory=list)
    income: Income = field(default_factory=Income)
    deductions: Deductions = field(default_factory=Deductions)
    credits: Credits = field(default_factory=Credits)
    payments: Payments = field(default_factory=Payments)
    state_extras: StateExtras = field(default_factory=StateExtras)
    filing: FilingInfo = field(default_factory=FilingInfo)
    notes: str = ""
    app_version: str = "1.0"

    # ------------------------------------------------------------------ helpers
    def is_joint(self) -> bool:
        return self.filing_status == "mfj"

    def has_spouse(self) -> bool:
        return self.filing_status in ("mfj", "mfs")

    def taxpayer_age(self) -> Optional[int]:
        return age_at_year_end(self.taxpayer.dob, self.tax_year)

    def spouse_age(self) -> Optional[int]:
        return age_at_year_end(self.spouse.dob, self.tax_year) if self.has_spouse() else None

    def num_people(self) -> int:
        return 2 if self.is_joint() else 1

    # ------------------------------------------------------------------ JSON
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TaxReturn":
        r = cls()
        r.tax_year = int(d.get("tax_year", 2025))
        r.filing_status = d.get("filing_status", "single")
        r.taxpayer = _from_dict(Person, d.get("taxpayer"))
        r.spouse = _from_dict(Person, d.get("spouse"))
        r.address = _from_dict(Address, d.get("address"))
        r.dependents = [_from_dict(Dependent, x) for x in d.get("dependents", [])]
        r.w2s = [_from_dict(W2, x) for x in d.get("w2s", [])]
        r.income = _from_dict(Income, d.get("income"))
        r.deductions = _from_dict(Deductions, d.get("deductions"))
        r.credits = _from_dict(Credits, d.get("credits"))
        r.payments = _from_dict(Payments, d.get("payments"))
        r.state_extras = _from_dict(StateExtras, d.get("state_extras"))
        r.filing = _from_dict(FilingInfo, d.get("filing"))
        r.notes = d.get("notes", "")
        return r
