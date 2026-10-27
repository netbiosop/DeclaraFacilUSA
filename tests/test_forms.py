"""Pruebas de los formularios oficiales / Official forms tests: mapa de campos, valores de cada formulario, preguntas
guiadas, direcciones del IRS y generación de los PDF."""
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxapp import forms  # noqa: E402
from taxapp.engine import compute_all  # noqa: E402
from taxapp.forms import catalog, mailing, questions  # noqa: E402
from taxapp.forms.build import Builder, m, whole  # noqa: E402
from taxapp.models import (Address, CareProvider, Credits, Dependent, FilingInfo, OtherExpense, Payer,  # noqa: E402
                           Person, Sale, Student, TaxReturn, W2)

try:
    import pypdf  # noqa: F401
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False


def family():
    r = TaxReturn(tax_year=2025, filing_status="mfj")
    r.taxpayer = Person(first_name="Juan", last_name="Perez", ssn="123-45-6789", dob="1985-04-02", occupation="Cook")
    r.spouse = Person(first_name="Maria", last_name="Perez", ssn="987-65-4321", dob="1987-09-12")
    r.address = Address(street="123 Main St", city="Houston", state="TX", zip="77001")
    r.dependents = [Dependent(first_name="Ana", last_name="Perez", ssn="111-22-3333", dob="2019-03-10"),
                    Dependent(first_name="Luis", last_name="Perez", ssn="222-33-4444", dob="2014-07-01"),
                    Dependent(first_name="Sofia", last_name="Perez", ssn="333-44-5555", dob="2005-01-20",
                              full_time_student=True)]
    r.w2s = [W2(employer="A", box1_wages=28000, box2_fed_withheld=900, box3_ss_wages=28000, box4_ss_withheld=1736,
                box5_medicare_wages=28000, box6_medicare_withheld=406),
             W2(employer="B", owner="conyuge", box1_wages=14000, box2_fed_withheld=300, box3_ss_wages=14000,
                box4_ss_withheld=868, box5_medicare_wages=14000, box6_medicare_withheld=203)]
    r.income.qualified_tips = 4200
    r.credits = Credits(care_expenses=4000,
                        care_providers=[CareProvider(name="Daycare", address="1 Oak, Houston TX", tin="12-3456789",
                                                     amount=4000)],
                        students=[Student(name="Sofia Perez", ssn="333-44-5555", expenses=3500, school="HCC",
                                          school_address="3100 Main St")])
    r.filing = FilingInfo(direct_deposit=True, routing="111000025", account="123456789")
    return r


def business():
    r = TaxReturn(tax_year=2025, filing_status="single")
    r.taxpayer = Person(first_name="Robert", last_name="Smith", ssn="555-66-7777", dob="1958-11-30")
    r.address = Address(street="9 Elm", city="Columbus", state="OH", zip="43004")
    r.w2s = [W2(employer="Acme", box1_wages=210000, box2_fed_withheld=38000, box3_ss_wages=176100,
                box4_ss_withheld=10918, box5_medicare_wages=210000, box6_medicare_withheld=3405)]
    i = r.income
    i.taxable_interest = 2600
    i.interest_payers = [Payer("Chase", 1600), Payer("Treasury", 1000)]
    i.ordinary_dividends, i.qualified_dividends = 3100, 2500
    i.sales = [Sale("AAPL", "03/01/2020", "06/15/2025", 25000, 12000, term="long"),
               Sale("XYZ", "01/10/2025", "05/02/2025", 4000, 5200, term="short"),
               Sale("BTC", "02/01/2023", "08/01/2025", 9000, 4000, term="long", basis_reported=False)]
    i.business_name, i.business_code, i.business_gross = "Smith Consulting", "541600", 60000
    i.exp_advertising, i.exp_travel, i.exp_travel_meals = 1200, 2000, 800
    i.other_expenses = [OtherExpense("Dues", 500), OtherExpense("Software", 700)]
    i.home_office_sqft, i.home_total_sqft = 200, 1800
    d = r.deductions
    d.mortgage_interest, d.real_estate_tax, d.charity_cash = 14000, 7000, 5000
    d.hsa_deduction, d.hsa_coverage, d.hsa_employer = 4000, "self", 500
    r.payments.federal_estimated = 4000
    return r


def num(s):
    if not s:
        return 0
    s = str(s).replace(",", "")
    return -int(s.strip("()")) if s.startswith("(") else int(s)


class FormatTests(unittest.TestCase):
    def test_money(self):
        self.assertEqual(m(1234.5), "1,235")
        self.assertEqual(m(-1234.4), "(1,234)")
        self.assertEqual(m(0), "")
        self.assertEqual(m(0, zero=True), "0")
        self.assertEqual(whole(2.5), 3)
        self.assertEqual(whole(-2.5), -3)

    def test_mailing_groups(self):
        self.assertEqual(mailing.irs_address("TX", False)[-1], "Austin, TX 73301-0002")
        self.assertEqual(mailing.irs_address("TX", True)[-1], "Charlotte, NC 28201-1214")
        self.assertEqual(mailing.irs_address("NY", False)[-1], "Kansas City, MO 64999-0002")
        self.assertEqual(mailing.irs_address("CA", False)[-1], "Ogden, UT 84201-0002")
        self.assertEqual(mailing.irs_address("AZ", True)[-1], "Louisville, KY 40293-1000")
        self.assertEqual(mailing.group_for("PR"), "abroad")
        self.assertFalse(mailing.mailing_info("TX", 0.4)["with_payment"])


class MapTests(unittest.TestCase):
    def test_map_covers_all_forms(self):
        self.assertTrue(catalog.available(2025))
        fm = catalog.forms(2025)
        for fid in catalog.ORDER + ["1040v"]:
            self.assertIn(fid, fm)
            self.assertTrue(catalog.pdf_path(2025, fid).exists(), fid)
        self.assertFalse(catalog.available(2026))   # el IRS aún no publica los de 2026

    @unittest.skipUnless(HAVE_PYPDF, "pypdf no instalado")
    def test_every_mapped_field_exists(self):
        sys.path.insert(0, str(ROOT / "herramientas"))
        import mapear_formularios as mf
        for fid, f in catalog.forms(2025).items():
            names = mf.pdf_fields(catalog.pdf_path(2025, fid))
            for key, spec in f["fields"].items():
                path = spec[0] if isinstance(spec, list) else spec
                self.assertIn(path, names, f"{fid}.{key}")
                if isinstance(spec, list) and spec[1]:
                    self.assertIn(spec[1], names[path][1], f"{fid}.{key}")


class BuilderTests(unittest.TestCase):
    def plan(self, ret, **kw):
        res = compute_all(ret)
        return res, forms.plan(ret, res, **kw)

    def vals(self, plan, fid, n=0):
        return [i for i in plan.instances if i.form == fid][n].values

    def test_family_forms_and_lines(self):
        ret = family()
        res, p = self.plan(ret)
        self.assertEqual(p.forms(), ["1040", "s1a", "s3", "2441", "sei", "s8812", "8863"])
        L = res["federal"]["lines"]
        v = self.vals(p, "1040")
        self.assertTrue(v["fs_mfj"])
        self.assertEqual(num(v["L11a"]), whole(L["11"]))
        self.assertEqual(num(v["L24"]), whole(L["24"]))
        self.assertEqual(num(v["L33"]), whole(L["33"]))
        self.assertEqual(v["routing"], "111000025")
        self.assertTrue(v["dep0_ctc"] and v["dep1_ctc"] and v["dep2_odc"])
        self.assertEqual(v["dep0_rel"], "CHILD")
        s8812 = self.vals(p, "s8812")
        self.assertEqual(num(s8812["L27"]), whole(L["28"]))
        self.assertEqual(s8812["L4"], "2")
        f2441 = self.vals(p, "2441")
        self.assertEqual(f2441["L8"], "21")
        self.assertEqual(num(f2441["L11"]), whole(res["federal"]["credits"]["cdcc"]))
        s3 = self.vals(p, "s3")
        self.assertEqual(num(s3["L8"]), whole(L["20"]))
        s1a = self.vals(p, "s1a")
        self.assertEqual(num(s1a["L13"]), 4200)
        f8863 = self.vals(p, "8863")
        self.assertEqual(num(f8863["L8"]), whole(L["29"]))
        self.assertEqual(f8863["L21_a"], "333")

    def test_business_forms_consistent(self):
        ret = business()
        res, p = self.plan(ret)
        fed = res["federal"]
        L = fed["lines"]
        self.assertEqual(p.main_form, "1040sr")
        for fid in ("s1", "s2", "sa", "sb", "sc", "sd", "8949", "sse", "8889", "8959", "8960", "1040v"):
            self.assertIn(fid, p.forms(), fid)
        sc = self.vals(p, "sc")
        self.assertEqual(num(sc["L31"]), whole(fed["profit"]))
        self.assertEqual(sc["oth1_desc"], "SOFTWARE")
        s1 = self.vals(p, "s1")
        self.assertEqual(num(s1["L10"]), whole(L["8"]))
        self.assertEqual(num(s1["L26"]), whole(L["10"]))
        sd = self.vals(p, "sd")
        self.assertEqual(num(sd["L16"]), whole(L["7"]))
        self.assertEqual(num(sd["L1ad"]), 4000)          # basis informada: línea 1a sin 8949
        self.assertEqual(num(sd["L9h"]), 5000)           # casilla E: 8949
        f8949 = self.vals(p, "8949")
        self.assertTrue(f8949["boxE"])
        s2 = self.vals(p, "s2")
        self.assertEqual(num(s2["L21"]), whole(L["23"]))
        sb = self.vals(p, "sb")
        self.assertEqual(sb["int0_name"], "CHASE")
        sa = self.vals(p, "sa")
        self.assertEqual(num(sa["L17"]), whole(L["12"]))
        v = self.vals(p, "1040sr")
        self.assertEqual(num(v["L37"]), whole(L["37"]))
        self.assertTrue(v["L12d_you65"])
        self.assertEqual([i for i in p.instances if i.form == "1040sr"][0].pages, [0, 1, 2])
        f8889 = self.vals(p, "8889")
        self.assertEqual(num(f8889["L3"]), 5300)          # 4,300 + 1,000 por tener 55+
        self.assertEqual(num(f8889["L13"]), 4000)
        _res, p2 = self.plan(ret, use_sr=False)
        self.assertEqual(p2.main_form, "1040")

    def test_many_dependents_statement(self):
        ret = family()
        ret.dependents += [Dependent(first_name=f"K{i}", last_name="P", ssn="444-55-666" + str(i), dob="2012-01-01")
                           for i in range(3)]
        _res, p = self.plan(ret)
        self.assertTrue(self.vals(p, "1040")["dep_more"])
        self.assertTrue(any("Dependents" in s["title"] for s in p.statements))


class QuestionTests(unittest.TestCase):
    def test_missing_and_required(self):
        ret = family()
        ret.taxpayer.ssn = ""
        ret.filing.routing = "123"
        res = compute_all(ret)
        keys = {q.key for q in questions.missing(ret, res, required_only=True)}
        self.assertIn("tp_ssn", keys)
        self.assertIn("routing", keys)
        ret.taxpayer.ssn = "123-45-6789"
        ret.filing.routing = "111000025"
        self.assertEqual(questions.missing(ret, compute_all(ret), required_only=True), [])

    def test_conditional_questions(self):
        ret = business()
        ret.income.exp_car = 1000
        res = compute_all(ret)
        keys = [q.key for q in questions.questions(ret, res)]
        for k in ("int_payers", "biz_code", "veh_date", "home_total", "hsa_cov"):
            self.assertIn(k, keys)
        self.assertNotIn("dd", keys)          # debe dinero: no hay depósito directo


class EngineChangeTests(unittest.TestCase):
    def test_sales_flow_into_capital_gain(self):
        res = compute_all(business())
        self.assertAlmostEqual(res["federal"]["lines"]["7"], 13000 - 1200 + 5000, places=2)

    def test_tips_reduction_rounds_down(self):
        r = TaxReturn(tax_year=2025, filing_status="single")
        r.taxpayer = Person(first_name="A", dob="1990-01-01")
        r.w2s = [W2(box1_wages=151500)]
        r.income.qualified_tips = 5000
        d = compute_all(r)["federal"]["detail"]
        self.assertAlmostEqual(d["tips"], 5000 - 100, places=2)     # 1,500 de exceso -> 1 x $100

    def test_hsa_limit(self):
        r = business()
        r.deductions.hsa_deduction = 9000
        f = compute_all(r)["federal"]
        self.assertAlmostEqual(f["hsa"], 4800, places=2)

    def test_extension_on_schedule3(self):
        r = family()
        r.payments.federal_extension = 300
        L = compute_all(r)["federal"]["lines"]
        self.assertEqual(L["26"], 0)
        self.assertAlmostEqual(L["31"], 300, places=2)


@unittest.skipUnless(HAVE_PYPDF, "pypdf no instalado")
class GenerateTests(unittest.TestCase):
    def test_generate_draft_and_final(self):
        ret = business()
        res = compute_all(ret)
        with tempfile.TemporaryDirectory() as tmp:
            out = forms.generate(ret, res, pathlib.Path(tmp) / "f", draft=False)
            self.assertTrue(out.package.exists() and out.instructions.exists() and out.voucher.exists())
            r = pypdf.PdfReader(str(out.package))
            self.assertEqual(len(r.pages), out.pages)
            self.assertNotIn("/AcroForm", r.trailer["/Root"])        # aplanado
            text = r.pages[0].extract_text()
            self.assertIn("SMITH", text)
            self.assertIn("210,000", text)
            d = forms.generate(ret, res, pathlib.Path(tmp) / "d", draft=True)
            self.assertIn("BORRADOR", pypdf.PdfReader(str(d.package)).pages[0].extract_text().upper().replace(" ", "")
                          .replace("DRAFT", "BORRADOR"))
            e = forms.generate(ret, res, pathlib.Path(tmp) / "e", draft=False, editable=True)
            single = [p for p in e.files if "Anexo_C" in p.name or "Schedule_C" in p.name][0]
            self.assertTrue(pypdf.PdfReader(str(single)).get_fields())


if __name__ == "__main__":
    unittest.main()
