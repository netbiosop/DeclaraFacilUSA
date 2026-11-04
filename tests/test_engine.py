"""Pruebas del motor de calculo con casos calculados a mano.

Ejecutar:  python -m unittest discover -s tests -v
"""
import os
import pathlib
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taxapp.engine import compute_all  # noqa: E402
from taxapp.models import TaxReturn, W2, Dependent, Person, clean_money_text  # noqa: E402
from taxapp.review import review, valid_ssn  # noqa: E402
from taxapp import storage  # noqa: E402


def make(year=2025, status="single", wages=0.0, state="TX", county="", locality="", dob="1985-06-01", **income):
    r = TaxReturn(tax_year=year, filing_status=status)
    r.taxpayer = Person(first_name="Ana", last_name="Perez", ssn="123-45-6789", dob=dob)
    if status in ("mfj", "mfs"):
        r.spouse = Person(first_name="Luis", last_name="Perez", ssn="123-45-6788", dob=dob)
    if wages:
        r.w2s.append(W2(employer="ACME", box1_wages=wages, state=state))
    r.address.state = state
    r.address.county = county
    r.address.locality = locality
    for k, v in income.items():
        setattr(r.income, k, v)
    return r


class FederalTests(unittest.TestCase):
    def test_single_2025(self):
        f = compute_all(make(2025, wages=60000))["federal"]
        self.assertAlmostEqual(f["taxable_income"], 44250)
        self.assertAlmostEqual(f["tax"], 5071.50, places=2)

    def test_single_2026(self):
        f = compute_all(make(2026, wages=60000))["federal"]
        self.assertAlmostEqual(f["taxable_income"], 43900)
        self.assertAlmostEqual(f["tax"], 5020.00, places=2)

    def test_mfj_two_kids_ctc(self):
        r = make(2025, "mfj", wages=80000)
        r.dependents = [Dependent(first_name="A", dob="2020-03-01", ssn="123-45-6787"),
                        Dependent(first_name="B", dob="2015-03-01", ssn="123-45-6786")]
        f = compute_all(r)["federal"]
        self.assertAlmostEqual(f["tax"], 5343.00, places=2)
        self.assertAlmostEqual(f["credits"]["ctc_nonref"], 4400)
        self.assertAlmostEqual(f["total_tax"], 943.00, places=2)
        self.assertEqual(f["credits"]["eitc"], 0)

    def test_hoh_eitc_actc(self):
        r = make(2025, "hoh", wages=20000)
        r.dependents = [Dependent(first_name="Hijo", dob="2017-05-05", ssn="123-45-6785")]
        f = compute_all(r)["federal"]
        self.assertEqual(f["taxable_income"], 0)
        self.assertAlmostEqual(f["credits"]["eitc"], 4328)
        self.assertAlmostEqual(f["credits"]["actc"], 1700)
        self.assertAlmostEqual(f["refund"], 6028)

    def test_capital_gains_worksheet(self):
        f = compute_all(make(2025, wages=50000, long_term_gain=20000))["federal"]
        self.assertAlmostEqual(f["taxable_income"], 54250)
        self.assertAlmostEqual(f["tax"], 4756.50, places=2)

    def test_senior_social_security(self):
        r = make(2025, dob="1955-02-01", pension_gross=40000, pension_taxable=40000, social_security=20000)
        f = compute_all(r)["federal"]
        self.assertAlmostEqual(f["taxable_ss"], 17000)
        self.assertAlmostEqual(f["sched1a"]["senior"], 6000)
        self.assertAlmostEqual(f["standard_deduction"], 17750)
        self.assertAlmostEqual(f["taxable_income"], 33250)
        self.assertAlmostEqual(f["tax"], 3751.50, places=2)

    def test_self_employment_qbi(self):
        f = compute_all(make(2025, business_gross=50000))["federal"]
        self.assertAlmostEqual(f["se_tax"], 7064.78, places=1)
        self.assertAlmostEqual(f["qbi"], 6143.52, places=1)
        self.assertAlmostEqual(f["total_tax"], 9775.17, places=1)

    def test_tips_overtime_deductions(self):
        r = make(2025, wages=70000, qualified_tips=10000, qualified_overtime=5000)
        f = compute_all(r)["federal"]
        self.assertAlmostEqual(f["sched1a"]["tips"], 10000)
        self.assertAlmostEqual(f["sched1a"]["overtime"], 5000)
        self.assertAlmostEqual(f["taxable_income"], 70000 - 15750 - 15000)

    def test_salt_itemized(self):
        r = make(2025, "mfj", wages=300000, state="CA")
        r.w2s[0].box17_state_withheld = 20000
        r.deductions.real_estate_tax = 25000
        r.deductions.mortgage_interest = 20000
        f = compute_all(r)["federal"]
        self.assertTrue(f["itemize"])
        self.assertAlmostEqual(f["itemized_detail"]["salt"], 40000)
        self.assertAlmostEqual(f["deduction"], 60000)


class StatutoryAmountsTests(unittest.TestCase):
    """Montos de la ley: umbral del Anexo SE, escalones del AOTC y reducción del CTC."""

    def test_se_tax_starts_at_400_net(self):
        below = compute_all(make(2025, business_gross=430))["federal"]   # 430 * 0.9235 = 397.11
        above = compute_all(make(2025, business_gross=440))["federal"]   # 440 * 0.9235 = 406.34
        self.assertEqual(below["se_tax"], 0)
        self.assertGreater(above["se_tax"], 0)

    def test_aotc_100_then_25_percent(self):
        from taxapp.models import Student
        r = make(2025, wages=40000)
        r.credits.students = [Student(name="Ana", credit="AOTC", expenses=3000)]
        self.assertAlmostEqual(compute_all(r)["federal"]["detail"]["aotc_gross"], 2000 + 0.25 * 1000)
        r.credits.students = [Student(name="Ana", credit="AOTC", expenses=9000)]
        self.assertAlmostEqual(compute_all(r)["federal"]["detail"]["aotc_gross"], 2500)

    def test_ctc_reduced_50_per_started_1000(self):
        r = make(2025, wages=210500)
        r.dependents = [Dependent(first_name="A", dob="2018-03-01", ssn="123-45-6787")]
        self.assertAlmostEqual(compute_all(r)["federal"]["detail"]["ctc_red"], 11 * 50)


class StateLocalTests(unittest.TestCase):
    def test_texas_no_tax(self):
        s = compute_all(make(2025, wages=60000, state="TX"))["state"]
        self.assertEqual(s["tax"], 0)

    def test_california_2026(self):
        s = compute_all(make(2026, wages=60000, state="CA"))["state"]
        self.assertAlmostEqual(s["taxable_income"], 54460)
        self.assertAlmostEqual(s["tax"], 1649.49, places=1)

    def test_maryland_montgomery_2025(self):
        res = compute_all(make(2025, wages=60000, state="MD", county="Montgomery County"))
        self.assertAlmostEqual(res["state"]["taxable_income"], 53450)
        self.assertAlmostEqual(res["state"]["tax"], 2486.38, places=1)
        self.assertAlmostEqual(res["local"]["total"], 1710.40, places=1)

    def test_maryland_anne_arundel_graduated(self):
        res = compute_all(make(2025, wages=80000, state="MD", county="Anne Arundel"))
        ti = res["state"]["taxable_income"]
        self.assertAlmostEqual(res["local"]["total"], 50000 * .027 + (ti - 50000) * .0294, places=1)

    def test_new_york_city_2026(self):
        res = compute_all(make(2026, wages=60000, state="NY", county="Kings", locality="New York City (NYC)"))
        self.assertAlmostEqual(res["state"]["taxable_income"], 52000)
        self.assertAlmostEqual(res["state"]["tax"], 2643.00, places=1)
        self.assertAlmostEqual(res["local"]["total"], 1890.69, places=1)

    def test_pennsylvania_philadelphia(self):
        res = compute_all(make(2025, wages=60000, state="PA", locality="Philadelphia (residente)"))
        self.assertAlmostEqual(res["state"]["tax"], 1842.00, places=2)
        self.assertAlmostEqual(res["local"]["total"], 2247.00, places=2)

    def test_indiana_marion_2026(self):
        res = compute_all(make(2026, wages=60000, state="IN", county="Marion"))
        self.assertAlmostEqual(res["state"]["tax"], 1740.50, places=2)
        self.assertAlmostEqual(res["local"]["total"], 1191.80, places=2)

    def test_all_states_run(self):
        from taxapp import data_loader
        for year in (2025, 2026):
            for code in data_loader.states_info():
                for status in ("single", "mfj", "hoh", "mfs", "qss"):
                    r = make(year, status, wages=85000, state=code, long_term_gain=5000, social_security=0)
                    r.dependents = [Dependent(first_name="K", dob="2014-01-01", ssn="123-45-6000")]
                    res = compute_all(r)
                    s = res["state"]
                    self.assertGreaterEqual(s["tax"], 0, (year, code, status))
                    self.assertLess(s["tax"], 85000 * 0.12, (year, code, status))


class MoneyTextTests(unittest.TestCase):
    def test_decimal_comma_and_thousands(self):
        cases = {"1500,50": "1500.50", "12,5": "12.5", "-3,25": "-3.25", "1,500": "1500",
                 "$1,500.25": "1500.25", "1,234,567": "1234567", " $ 2 000 ": "2000"}
        for text, expected in cases.items():
            self.assertEqual(clean_money_text(text), expected, text)
        self.assertEqual(W2(box1_wages="1500,50").box1_wages, 1500.5)


class EarnedIncomeAndAgeTests(unittest.TestCase):
    """Reglas del IRS que se aplicaban mal (revisión 2026-11-01)."""

    def kid(self, dob="2015-03-01", ssn="123-45-6787"):
        return Dependent(first_name="A", dob=dob, ssn=ssn, relationship="hijo", months_lived=12)

    def test_eitc_joint_needs_spouse_ssn_valid_for_work(self):
        # IRC §32(c)(1)(E) y §32(m): en declaración conjunta los DOS necesitan SSN válido para trabajar
        r = make(2025, "mfj", wages=25000)
        r.dependents = [self.kid(), self.kid(ssn="123-45-6786")]
        r.spouse.valid_ssn_for_work = False
        self.assertEqual(compute_all(r)["federal"]["credits"]["eitc"], 0)

    def test_schedule_c_loss_reduces_earned_income(self):
        # Pub. 596: la pérdida neta de trabajo independiente se resta del resto del ingreso del trabajo
        r = make(2025, wages=20000, business_gross=1000, exp_supplies=11000)
        r.dependents = [self.kid()]
        f = compute_all(r)["federal"]
        self.assertAlmostEqual(f["earned_income"], 10000)
        self.assertAlmostEqual(f["credits"]["eitc"], 3400, places=0)

    def test_child_born_january_first_is_not_a_year_older(self):
        # Rev. Rul. 2003-72: para el CTC y el hijo calificado se cumple años EL DÍA del cumpleaños
        r = make(2025, "hoh", wages=40000)
        r.dependents = [self.kid(dob="2009-01-01")]
        self.assertEqual(compute_all(r)["federal"]["credits"]["n_ctc"], 1)

    def test_taxpayer_born_january_first_turns_65_a_day_early(self):
        self.assertEqual(make(2025, dob="1961-01-01").taxpayer_age(), 65)


class TaxIdFormatTests(unittest.TestCase):
    def test_itin_is_a_valid_tax_id(self):
        # Los ITIN empiezan con 9 y su grupo central es 50-65, 70-88, 90-92 o 94-99
        self.assertTrue(valid_ssn("912-70-1234"))
        self.assertTrue(valid_ssn("999-94-1234"))

    def test_invalid_numbers_still_rejected(self):
        for bad in ("912-89-1234", "912-93-1234", "000-12-3456", "666-12-3456", "123-00-4567", "123-45-0000"):
            self.assertFalse(valid_ssn(bad), bad)


class StorageAndReview(unittest.TestCase):
    def test_roundtrip(self):
        r = make(2026, "mfj", wages=50000, state="OH", locality="Columbus")
        r.dependents.append(Dependent(first_name="X", dob="2019-01-01"))
        d = r.to_dict()
        r2 = TaxReturn.from_dict(d)
        self.assertEqual(r2.to_dict(), d)
        s = storage.dumps(r)
        self.assertEqual(storage.loads(s).to_dict(), d)

    def test_review_flags(self):
        r = make(2025, wages=1000, state="MD")
        r.taxpayer.ssn = "12"
        res = compute_all(r)
        sev = {x["severity"] for x in review(r, res)}
        self.assertIn("error", sev)

    def test_review_warns_itin_marked_as_ssn(self):
        # Un ITIN con "tiene SSN" marcado pediría CTC y EITC que no corresponden: la revisión debe avisar
        r = make(2025, wages=30000)
        r.taxpayer.ssn = "912-70-1234"
        r.dependents.append(Dependent(first_name="X", dob="2018-05-05", ssn="912-71-1234", relationship="hijo",
                                      months_lived=12))
        msgs = [x["message"] for x in review(r, compute_all(r)) if x["severity"] == "aviso"]
        self.assertTrue(any("ITIN" in m and "contribuyente" in m for m in msgs), msgs)
        self.assertTrue(any("ITIN" in m and "X" in m for m in msgs), msgs)


    def test_review_flags_spouse_w2_on_non_joint_return(self):
        # el W-2 del cónyuge solo va en una declaración conjunta; en MFS o soltero se sumaría como salario propio
        r = make(2025, "mfs", wages=50000)
        r.w2s.append(W2(employer="Esposa SA", box1_wages=50000, owner="conyuge"))
        errors = [x["message"] for x in review(r, compute_all(r)) if x["severity"] == "error"]
        self.assertTrue(any("Esposa SA" in m for m in errors), errors)
        r.filing_status = "mfj"
        errors = [x["message"] for x in review(r, compute_all(r)) if x["severity"] == "error"]
        self.assertFalse(any("Esposa SA" in m for m in errors), errors)

    def test_save_as_name_with_dot_keeps_it(self):
        # "Garcia.Maria" se guardaba como "Garcia.dfusa" y pisaba otra declaración sin preguntar
        with tempfile.TemporaryDirectory() as d, mock.patch.object(storage, "add_recent"):
            other = storage.save(make(2025, wages=1), pathlib.Path(d) / "Garcia")
            p = storage.save(make(2025, wages=2), pathlib.Path(d) / "Garcia.Maria")
            self.assertEqual(p.name, "Garcia.Maria.dfusa")
            self.assertEqual(storage.load(other).w2s[0].box1_wages, 1)
            self.assertEqual(storage.save(make(2025), pathlib.Path(d) / "x.DFUSA").name, "x.DFUSA")
            self.assertEqual(storage.save(make(2025), pathlib.Path(d) / "vieja.json").name, "vieja.dfusa")


class DependentQualificationTests(unittest.TestCase):
    """Quién cuenta como hijo calificado y quién recibe el AOTC (revisión 2026-11-02)."""

    def test_other_household_member_is_not_a_qualifying_child(self):
        # "Otra persona del hogar" contiene "son" (per-son-a) y se tomaba como hijo: CTC y EITC indebidos
        r = make(2025, "hoh", wages=30000)
        r.dependents = [Dependent(first_name="A", dob="2015-03-01", ssn="123-45-6787",
                                  relationship="Otra persona del hogar", months_lived=12)]
        f = compute_all(r)["federal"]
        self.assertEqual(f["credits"]["n_ctc"], 0)
        self.assertEqual(f["credits"]["eitc"], 0)

    def test_english_relationships_still_count(self):
        for rel in ("son", "Stepson", "grandson", "daughter", "nephew", "Stepchild", "Grandchild", "half brother"):
            self.assertTrue(Dependent(relationship=rel).is_child_relation(), rel)
        for rel in ("person", "Godson", "Otra persona del hogar", "Otro pariente", "Padre / Madre"):
            self.assertFalse(Dependent(relationship=rel).is_child_relation(), rel)

    def test_eitc_child_must_live_in_us(self):
        # IRC §32(c)(3)(C): el hijo calificado del EITC debe vivir con usted en EE. UU. más de medio año
        r = make(2025, "hoh", wages=20000)
        r.dependents = [Dependent(first_name="A", dob="2015-03-01", ssn="123-45-6787", relationship="Hijo(a)",
                                  months_lived=12, lived_in_us=False)]
        self.assertEqual(compute_all(r)["federal"]["credits"]["n_eitc"], 0)

    def test_child_born_after_tax_year_does_not_qualify(self):
        r = make(2025, "hoh", wages=30000)
        r.dependents = [Dependent(first_name="A", dob="2026-03-01", ssn="123-45-6787", relationship="Hijo(a)")]
        f = compute_all(r)["federal"]
        self.assertEqual(f["credits"]["n_ctc"], 0)
        self.assertEqual(f["credits"]["n_odc"], 0)
        self.assertEqual(f["credits"]["eitc"], 0)

    def test_aotc_requires_half_time_and_first_four_years(self):
        # Formulario 8863 líneas 24 y 25: sin medio tiempo o con 4 años ya completados no hay AOTC
        from taxapp.models import Student
        for flags in ({"half_time": False}, {"first_four_years": False}):
            r = make(2025, wages=40000)
            r.credits.students = [Student(name="Ana", credit="AOTC", expenses=4000, **flags)]
            self.assertEqual(compute_all(r)["federal"]["detail"]["aotc_gross"], 0, flags)

    def test_review_flags_impossible_birth_date(self):
        r = make(2025, wages=30000)
        r.dependents.append(Dependent(first_name="X", dob="2015-02-30", ssn="123-45-6787", relationship="Hijo(a)"))
        errs = [x["message"] for x in review(r, compute_all(r)) if x["severity"] == "error"]
        self.assertTrue(any("X" in m for m in errs), errs)


if __name__ == "__main__":
    unittest.main()
