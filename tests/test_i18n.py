"""Pruebas de idioma / Language tests: every translatable string has an English entry with matching placeholders,
every user-facing note in data/*.json is translated, and the engine produces English output."""
import ast
import json
import pathlib
import string
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxapp import i18n  # noqa: E402
from taxapp.lang_en import EN  # noqa: E402
from taxapp.lang_en_data import EN_DATA  # noqa: E402

CATALOG = {**EN_DATA, **EN}


def source_keys():
    keys = set()
    for p in (ROOT / "taxapp").rglob("*.py"):
        if p.name.startswith("lang_en"):
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_", "N_", "tr") and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                keys.add(n.args[0].value)
    return keys


def data_keys():
    keys = set()
    for y in (2025, 2026):
        st = json.loads((ROOT / "data" / f"states_{y}.json").read_text(encoding="utf-8"))["states"]
        for d in st.values():
            keys.update(d.get("notes", []))
        lo = json.loads((ROOT / "data" / f"local_{y}.json").read_text(encoding="utf-8"))
        keys.update(lo["notes"])
        for d in lo["states"].values():
            keys.update(n for n in d.get("notes", []) if n)
            if d.get("label"):
                keys.add(d["label"])
            for k, j in d.get("localities", {}).items():
                if j.get("note"):
                    keys.add(j["note"])
            for j in d.get("counties", {}).values():
                if j.get("note"):
                    keys.add(j["note"])
    return keys


def fields(s):
    return sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)


class CatalogTests(unittest.TestCase):
    def test_all_source_strings_translated(self):
        missing = sorted(k for k in source_keys() if k not in CATALOG)
        self.assertEqual(missing, [], f"{len(missing)} missing English translations")

    def test_all_data_notes_translated(self):
        missing = sorted(k for k in data_keys() if k not in CATALOG)
        self.assertEqual(missing, [], f"{len(missing)} data notes without translation")

    def test_placeholders_match(self):
        bad = [k for k, v in CATALOG.items() if fields(k) != fields(v)]
        self.assertEqual(bad, [])

    def test_no_unused_entries(self):
        used = source_keys() | data_keys()
        unused = sorted(k for k in EN if k not in used)
        self.assertEqual(unused, [], "catalog entries no longer used in the code")


class EnglishOutputTests(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en", save=False)

    def tearDown(self):
        i18n.set_language("es", save=False)

    def test_engine_and_report_in_english(self):
        from tests.test_engine import make
        from taxapp.engine import compute_all, balance_text
        from taxapp.review import review
        from taxapp import reports
        r = make(2026, "mfs", wages=60000, state="MD", county="Montgomery", qualified_tips=5000)
        r.taxpayer.ssn = "bad"
        res = compute_all(r)
        self.assertTrue(balance_text(100).startswith("Refund"))
        msgs = " ".join(f["message"] for f in review(r, res))
        self.assertIn("SSN/ITIN", msgs)
        self.assertIn("file jointly", msgs)
        self.assertTrue(any("Federal AGI" in n for n, _v in res["state"]["lines"]))
        html = reports.to_html(r, res, review(r, res))
        self.assertIn('lang="en"', html)
        self.assertIn("TOTAL INCOME", html)
        self.assertNotIn("INGRESO TOTAL", html)

    def test_reverse_lookup(self):
        self.assertEqual(i18n.reverse("Stepchild", ["Hijo(a)", "Hijastro(a)"]), "Hijastro(a)")
        self.assertEqual(i18n.reverse("Philadelphia (resident)", ["Philadelphia (residente)"]), "Philadelphia (residente)")

    def test_spanish_is_identity(self):
        i18n.set_language("es", save=False)
        self.assertEqual(i18n._("Ingresos"), "Ingresos")
        self.assertEqual(i18n.tr("Reembolso {m}", m="$1"), "Reembolso $1")


if __name__ == "__main__":
    unittest.main()
