"""Pruebas del motor de calculo con casos calculados a mano.

Ejecutar:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taxapp.engine import compute_all  # noqa: E402
from taxapp.models import TaxReturn, W2, Dependent, Person  # noqa: E402
from taxapp.review import review  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
