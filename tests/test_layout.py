"""Ajuste automático de textos / Automatic text wrapping: la línea se adapta al ancho disponible sin oscilar."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from taxapp.gui import layout
except ImportError:  # sin Tkinter
    layout = None


class FakeLabel:
    def __init__(self, textw, wl, ip=4, x=10, pad=8):
        self.textw, self.wl, self.ip, self.x, self.pad = textw, wl, ip, x, pad

    def winfo_exists(self):
        return True

    def winfo_manager(self):
        return "pack"

    def pack_info(self):
        return {"side": "top", "padx": f"0 {self.pad}"}

    def winfo_x(self):
        return self.x

    def winfo_reqwidth(self):
        return min(self.textw, self.wl) + 2 * self.ip

    def cget(self, _k):
        return str(self.wl)

    def configure(self, wraplength):
        self.wl = wraplength


class FakeParent:
    def __init__(self, labels, fixed=None):
        self._aw_labels, self.fixed, self._aw_job = labels, fixed, None

    def winfo_reqwidth(self):
        return max(lb.x + lb.winfo_reqwidth() + lb.pad for lb in self._aw_labels)

    def winfo_width(self):
        return self.fixed or self.winfo_reqwidth()


@unittest.skipIf(layout is None, "Tkinter no disponible")
class ReflowTests(unittest.TestCase):
    def run_reflow(self, fixed, textw, wl):
        lb = FakeLabel(textw, wl)
        p = FakeParent([lb], fixed)
        seen = []
        for _ in range(10):
            layout._reflow(p)
            seen.append(lb.wl)
        self.assertEqual(len(set(seen[1:])), 1, seen)     # se estabiliza, no oscila
        return lb, p

    def test_long_text_shrinks_to_fit(self):
        lb, p = self.run_reflow(500, 2000, 860)
        self.assertLessEqual(lb.x + lb.winfo_reqwidth() + lb.pad, p.winfo_width())

    def test_grows_when_window_is_wider(self):
        lb, _p = self.run_reflow(1200, 2000, 400)
        self.assertGreater(lb.wl, 1100)

    def test_short_text_untouched(self):
        lb, _p = self.run_reflow(1200, 200, 400)
        self.assertEqual(lb.wl, 400)

    def test_shrink_wrapped_parent_is_stable(self):
        lb, _p = self.run_reflow(None, 2000, 860)
        self.assertEqual(lb.wl, 860)

    def test_px_scales_with_font_size(self):
        from taxapp.gui import widgets
        old = widgets.STYLE["scale"]
        try:
            widgets.STYLE["scale"] = 1.12
            self.assertEqual(layout.px(100), round(100 * 1.12 * layout.factor(False)))
        finally:
            widgets.STYLE["scale"] = old


if __name__ == "__main__":
    unittest.main()
