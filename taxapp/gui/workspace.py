"""Espacio de trabajo / Workspace: encabezado con resultado, pasos con progreso, pantalla actual, panel de resultado
en vivo (opcional) y asistente de IA acoplado (opcional)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..engine import fmt_money, balance_text
from ..i18n import _, N_, tr
from . import theme
from .forms_view import FormsScreen
from .screens import SCREENS
from .theme import icon, icon_font
from .ui import C, Pill, Progress, IconButton, flat_button, user_chip, label
from .widgets import COLORS, font, Tooltip

SECTIONS = [("personal", N_("Información personal")), ("address", N_("Dirección, estado y condado")),
            ("dependents", N_("Dependientes")), ("income", N_("Ingresos")), ("deductions", N_("Deducciones")),
            ("credits", N_("Créditos")), ("payments", N_("Pagos y retenciones")), ("state", N_("Declaración estatal")),
            ("local", N_("Impuestos locales")), ("review", N_("Revisión")), ("summary", N_("Resumen y presentar")),
            ("forms", N_("Formularios del IRS"))]
PHASES = [(N_("Usted y su familia"), ["personal", "address", "dependents"]), (N_("Ingresos"), ["income"]),
          (N_("Deducciones y créditos"), ["deductions", "credits", "payments"]),
          (N_("Estado y local"), ["state", "local"]), (N_("Revisar y presentar"), ["review", "summary", "forms"])]
KEYS = [k for k, _l in SECTIONS]


def section_done(key, ret, visited) -> bool:
    if key in visited:
        return True
    if ret is None:
        return False
    a, inc = ret.address, ret.income
    return {
        "personal": bool(ret.taxpayer.dob or ret.taxpayer.first_name),
        "address": bool(a.state),
        "dependents": bool(ret.dependents),
        "income": bool(ret.w2s) or any(isinstance(v, (int, float)) and v for v in vars(inc).values()),
    }.get(key, False)


def lock_widgets(widget):
    """Modo solo lectura (rol Consulta): desactiva todos los campos y botones de una pantalla."""
    for w in widget.winfo_children():
        cls = w.winfo_class()
        try:
            if cls in ("TEntry", "TCombobox", "TSpinbox", "TCheckbutton", "TRadiobutton", "TButton"):
                w.state(["disabled"])
            elif cls in ("Text", "Entry", "Spinbox", "Button", "Checkbutton"):
                w.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass
        lock_widgets(w)


class ResultPanel(tk.Frame):
    """Resultado en vivo (columna derecha; estilo del tema B)."""

    def __init__(self, parent):
        super().__init__(parent, bg=C("card"), padx=20, pady=18, highlightthickness=1, highlightbackground=C("border"))
        label(self, _("RESULTADO EN VIVO"), 9, "bold", fg=C("muted")).pack(anchor="w")
        self.cap = label(self, _("Total estimado"), 10, fg=C("muted"))
        self.cap.pack(anchor="w", pady=(12, 0))
        self.total = label(self, "—", 26, "bold", fg=C("refund"))
        self.total.pack(anchor="w")
        tk.Frame(self, bg=C("border"), height=1).pack(fill="x", pady=12)
        self.rows = {}
        for k, t in (("federal", _("Federal")), ("state", _("Estatal")), ("local", _("Local"))):
            r = tk.Frame(self, bg=C("card"))
            r.pack(fill="x", pady=3)
            label(r, t, 10, fg=C("muted")).pack(side="left")
            v = label(r, "—", 11, "bold")
            v.pack(side="right")
            self.rows[k] = v
        self.rates = label(self, "", 9, fg=C("muted"), wraplength=240)
        self.rates.pack(anchor="w", pady=(10, 0))

    def update_result(self, res):
        s = res["summary"]
        tot = s["total_balance"]
        self.cap.configure(text=_("Reembolso total estimado") if tot >= 0 else _("Total estimado a pagar"))
        self.total.configure(text=fmt_money(abs(tot)), fg=C("refund") if tot >= 0 else C("owe"))
        for k, key in (("federal", "federal_balance"), ("state", "state_balance"), ("local", "local_balance")):
            v = s[key]
            self.rows[k].configure(text=("+" if v > 0 else "−" if v < 0 else "") + fmt_money(abs(v)),
                                   fg=C("refund") if v > 0 else C("owe") if v < 0 else C("text"))
        f = res["federal"]
        self.rates.configure(text=tr("Tasa marginal {m}% • efectiva {e}%", m=f"{f['marginal_rate'] * 100:.0f}",
                                     e=f"{f['effective_rate'] * 100:.1f}"))


class Workspace(tk.Frame):
    def __init__(self, app):
        super().__init__(app, bg=C("bg"))
        self.app = app
        self.prefs = app.prefs
        self.theme = theme.current()
        meter = self.prefs.get("meter") or theme.THEMES[self.theme]["meter"]
        docked = self.prefs.get("ai_docked")
        if docked is None:
            docked = theme.THEMES[self.theme]["ai_docked"]
        self.meter_mode = meter if meter in ("header", "panel", "off") else "header"
        self.docked = bool(docked) and app.can("use_ai")
        self.visited = set()
        self.screens = {}
        self.current = None
        self.dock = None
        c = COLORS

        # ---- encabezado
        head = tk.Frame(self, bg=c["header"], padx=20, pady=12)
        head.pack(fill="x")
        IconButton(head, "home", app.show_home, tip=_("Menú principal"), bg=c["header"], fg=c["header_fg"]).pack(side="left")
        titles = tk.Frame(head, bg=c["header"])
        titles.pack(side="left", padx=14)
        self.title_lbl = tk.Label(titles, text="", bg=c["header"], fg=c["header_fg"], font=font(14, "bold"))
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = tk.Label(titles, text="", bg=c["header"], fg=c["header_muted"], font=font(9))
        self.sub_lbl.pack(anchor="w")
        user_chip(head, app, fg=c["header_fg"], bg=c["header"]).pack(side="right", padx=(10, 0))
        if app.can("use_ai") and not self.docked:
            flat_button(head, _("Asistente IA"), app.open_assistant, kind="accent", icon_name="ai").pack(side="right", padx=(10, 0))
        self.pills = {}
        if self.meter_mode == "header":
            for k, t in (("total", _("Total")), ("state", _("Estatal")), ("federal", _("Federal"))):
                p = Pill(head, t, dark=(k == "total"))
                p.pack(side="right", padx=4)
                self.pills[k] = p
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

        if self.theme == "C":     # barra de etapas
            self.phase_bar = tk.Frame(self, bg=c["header"], padx=20, pady=10)
            self.phase_bar.pack(fill="x")
            self.phases = []
            for i, (name, keys) in enumerate(PHASES):
                col = tk.Frame(self.phase_bar, bg=c["header"])
                col.grid(row=0, column=i, sticky="ew", padx=5)
                self.phase_bar.columnconfigure(i, weight=1, uniform="ph")
                bar = Progress(col, 0, height=6, bg=c["surface"])
                bar.pack(fill="x")
                lb = tk.Label(col, text=_(name), bg=c["header"], fg=c["header_muted"], font=font(9, "bold"), anchor="w")
                lb.pack(anchor="w", pady=(5, 0))
                lb.bind("<Button-1>", lambda e, k=keys[0]: self.show(k))
                lb.configure(cursor="hand2")
                self.phases.append((keys, bar, lb))
            tk.Frame(self, bg=c["border"], height=1).pack(fill="x")
        else:
            self.phases = []

        # ---- pie
        foot = tk.Frame(self, bg=c["card"], padx=24, pady=12)
        foot.pack(fill="x", side="bottom")
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x", side="bottom")
        self.status = tk.Label(foot, text="", bg=c["card"], fg=c["muted"], font=font(9))
        self.status.pack(side="left")
        self.next_btn = ttk.Button(foot, text=_("Continuar  ›"), style="Accent.TButton", command=self.next)
        self.next_btn.pack(side="right")
        self.prev_btn = ttk.Button(foot, text=_("‹  Atrás"), command=self.prev)
        self.prev_btn.pack(side="right", padx=8)

        # ---- cuerpo
        main = tk.Frame(self, bg=c["bg"])
        main.pack(fill="both", expand=True)
        side = tk.Frame(main, bg=c["sidebar"], width=268, padx=14, pady=16)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(main, bg=c["border"], width=1).pack(side="left", fill="y")
        prog = tk.Frame(side, bg=c["sidebar"], padx=8)
        prog.pack(fill="x", pady=(0, 12))
        top = tk.Frame(prog, bg=c["sidebar"])
        top.pack(fill="x")
        tk.Label(top, text=_("Su progreso"), bg=c["sidebar"], fg=c["sidebar_fg"], font=font(10, "bold")).pack(side="left")
        self.pct_lbl = tk.Label(top, text="0%", bg=c["sidebar"], fg=c["sidebar_muted"], font=font(10))
        self.pct_lbl.pack(side="right")
        self.prog = Progress(prog, 0, height=6)
        self.prog.pack(fill="x", pady=(6, 0))
        self.nav = {}
        groups = {keys[0]: name for name, keys in PHASES} if self.theme == "C" else {}
        for i, (key, lab) in enumerate(SECTIONS, 1):
            if key in groups:
                tk.Label(side, text=_(groups[key]).upper(), bg=c["sidebar"], fg=c["sidebar_muted"], font=font(8, "bold"),
                         anchor="w").pack(fill="x", padx=8, pady=(10, 2))
            row = tk.Frame(side, bg=c["sidebar"], padx=8, pady=6, cursor="hand2")
            row.pack(fill="x", pady=1)
            dot = tk.Label(row, text=str(i), width=2, font=font(9, "bold"), bg=c["surface"], fg=c["sidebar_muted"])
            dot.pack(side="left")
            txt = tk.Label(row, text=_(lab), bg=c["sidebar"], fg=c["sidebar_fg"], font=font(10), anchor="w")
            txt.pack(side="left", padx=(10, 0), fill="x")
            for w in (row, dot, txt):
                w.bind("<Button-1>", lambda e, k=key: self.show(k))
            self.nav[key] = (row, dot, txt, i)

        if self.docked or self.meter_mode == "panel":
            right = tk.Frame(main, bg=c["bg"], width=370 if self.docked else 300)
            right.pack(side="right", fill="y")
            right.pack_propagate(False)
            if self.meter_mode == "panel":
                self.result_panel = ResultPanel(right)
                self.result_panel.pack(fill="x", padx=(0, 16), pady=16)
            if self.docked:
                from .assistant import AssistantPanel
                holder = tk.Frame(right, bg=c["border"], padx=1, pady=1)
                holder.pack(fill="both", expand=True, padx=(0, 16) if self.meter_mode == "panel" else 0,
                            pady=(0, 16) if self.meter_mode == "panel" else 0)
                self.dock = AssistantPanel(holder, app, compact=True)
                self.dock.pack(fill="both", expand=True)
        if self.meter_mode != "panel":
            self.result_panel = None
        self.content = tk.Frame(main, bg=c["card"], highlightthickness=0)
        self.content.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------ navegacion
    def reset(self):
        for s in self.screens.values():
            s.frame.destroy()
        self.screens = {}
        self.current = None
        self.visited = set()

    def show(self, key):
        if self.current and self.current in self.screens:
            self.screens[self.current].frame.pack_forget()
        if key not in self.screens:
            cls = {c.key: c for c in SCREENS + [FormsScreen]}[key]
            self.screens[key] = cls(self.app, self.content)
            if self.app.readonly:
                lock_widgets(self.screens[key].frame)
        scr = self.screens[key]
        scr.frame.pack(fill="both", expand=True)
        if self.current:
            self.visited.add(self.current)
        self.current = key
        idx = KEYS.index(key)
        self.prev_btn.state(["disabled"] if idx == 0 else ["!disabled"])
        if idx < len(KEYS) - 1:
            self.next_btn.configure(text=tr("Continuar: {s}  ›", s=_(dict(SECTIONS)[KEYS[idx + 1]])))
            self.next_btn.state(["!disabled"])
        else:
            self.next_btn.configure(text=_("Generar formularios"))
            self.next_btn.state(["!disabled"] if self.app.can("export") else ["disabled"])
        scr.on_show()
        if self.app.result:
            scr.on_result(self.app.result)
        self.refresh_nav()

    def refresh_nav(self):
        c = COLORS
        ret = self.app.ret
        done_n = 0
        for key, (row, dot, txt, i) in self.nav.items():
            done = section_done(key, ret, self.visited)
            done_n += done
            cur = key == self.current
            rbg = c["sidebar_sel"] if cur else c["sidebar"]
            row.configure(bg=rbg)
            txt.configure(bg=rbg, fg=c["sidebar_sel_fg"] if cur else (c["sidebar_fg"] if done else c["sidebar_muted"]),
                          font=font(10, "bold" if cur else "normal"))
            if done and not cur:
                dot.configure(text=icon("check"), font=icon_font(8), bg=c["accent"], fg=c["on_accent"])
            elif cur:
                dot.configure(text=str(i), font=font(9, "bold"), bg=c["card"], fg=c["sidebar_sel_fg"])
            else:
                dot.configure(text=str(i), font=font(9, "bold"), bg=c["surface"], fg=c["sidebar_muted"])
        pct = done_n / len(KEYS)
        self.prog.set(pct)
        self.pct_lbl.configure(text=f"{pct * 100:.0f}%")
        for keys, bar, lb in self.phases:
            n = sum(section_done(k, ret, self.visited) for k in keys)
            bar.set(n / len(keys))
            active = self.current in keys
            lb.configure(fg=c["primary"] if active else c["header_muted"])
        return pct

    def next(self):
        idx = KEYS.index(self.current)
        if idx < len(KEYS) - 1:
            self.show(KEYS[idx + 1])
        else:
            self.screens["forms"].generate_final()

    def prev(self):
        idx = KEYS.index(self.current)
        if idx > 0:
            self.show(KEYS[idx - 1])

    # ------------------------------------------------------------------ resultado
    def update_meter(self, res):
        s = res["summary"]
        for key, val in (("federal", s["federal_balance"]), ("state", s["state_balance"]), ("total", s["total_balance"])):
            if key in self.pills:
                self.pills[key].set(val, ("▲ " if val >= 0 else "▼ ") + fmt_money(abs(val)))
        if self.result_panel:
            self.result_panel.update_result(res)
        r = self.app.ret
        from ..models import FILING_STATUSES
        self.title_lbl.configure(text=tr("Declaración {y}", y=r.tax_year)
                                 + (f" — {r.taxpayer.full_name()}" if r.taxpayer.full_name() else ""))
        bits = [_(FILING_STATUSES.get(r.filing_status, ""))]
        if r.address.state:
            bits.append(r.address.state)
        if self.app.readonly:
            bits.append(_("Solo lectura"))
        self.sub_lbl.configure(text=" · ".join(b for b in bits if b))
