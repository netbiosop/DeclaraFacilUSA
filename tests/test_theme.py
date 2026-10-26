"""Pruebas de temas y fechas clave (requieren tkinter) / Theme and key-date tests (need tkinter)."""
import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:
    import tkinter  # noqa: F401
    HAS_TK = True
except ImportError:
    HAS_TK = False


@unittest.skipUnless(HAS_TK, "tkinter no disponible")
class ThemeTests(unittest.TestCase):
    def test_contrast_all_themes_and_accents(self):
        from taxapp.gui.theme import palette, contrast, THEMES, ACCENTS
        pairs = [("text", "card"), ("muted", "card"), ("on_accent", "accent"), ("tint_fg", "tint"),
                 ("primary", "card"), ("refund", "refund_bg"), ("owe", "owe_bg"), ("chip_fg", "chip")]
        for t in THEMES:
            for _n, acc in [("", "")] + ACCENTS:
                p = palette(t, acc)
                for a, b in pairs:
                    self.assertGreaterEqual(contrast(p[a], p[b]), 4.5, (t, acc, a, b))

    def test_key_dates(self):
        from taxapp.gui.ui import key_dates, next_filing_deadline, year_status
        d, y, days = next_filing_deadline(date(2026, 10, 26))
        self.assertEqual((d, y, days), (date(2027, 4, 15), 2026, 171))
        ks = key_dates(date(2026, 10, 26))
        self.assertEqual(ks[0][0], date(2027, 1, 15))
        self.assertEqual(next_filing_deadline(date(2027, 4, 20))[0], date(2028, 4, 17))   # sabado -> lunes
        self.assertIn("2027", year_status(2026, date(2026, 10, 26)))


if __name__ == "__main__":
    unittest.main()
