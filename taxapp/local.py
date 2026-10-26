"""Impuestos locales sobre la renta (condados y ciudades).

- Maryland: los 23 condados + Baltimore City (tasa sobre el ingreso tributable de MD).
- Indiana: los 92 condados (tasa sobre el ingreso tributable de IN).
- Ciudades: NYC, Yonkers, Philadelphia, Pittsburgh, Ohio, Michigan, Kentucky, Missouri, Alabama, Wilmington,
  Portland/Multnomah, Denver/Aurora, distritos escolares de Iowa, y cualquier impuesto local personalizado.
"""
from __future__ import annotations

from typing import List, Optional

from . import data_loader
from .federal import bracket_tax, r2
from .i18n import _, N_, tr
from .models import TaxReturn


def normalize_county(name: str) -> str:
    n = (name or "").strip().lower()
    for suf in (" county", " parish", " borough", " census area", " municipality", " city and borough"):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return n.replace("saint ", "st. ").replace("st ", "st. ").replace("  ", " ").strip()


def find_county(counties: dict, name: str) -> Optional[str]:
    if not name:
        return None
    target = normalize_county(name)
    for c in counties:
        if normalize_county(c) == target:
            return c
    if target in ("baltimore", "baltimore county"):
        return "Baltimore County" if "Baltimore County" in counties else None
    return None


def _status_brackets(d: dict, status: str, hoh_uses: str = "single"):
    if status in ("mfj", "qss"):
        return d["mfj"]
    if status == "hoh":
        return d.get("hoh") or (d["mfj"] if hoh_uses == "mfj" else d["single"])
    return d["single"]


def earned_income(ret: TaxReturn, fedres: dict) -> float:
    return fedres["wages"] + max(0.0, fedres["profit"])


def _apply(j: dict, name: str, ret: TaxReturn, fedres: dict, stres: dict, override_rate: float = 0.0) -> dict:
    status = ret.filing_status
    method = j.get("method", "flat")
    base_key = j.get("base", "state_taxable")
    bases = {
        "earned": earned_income(ret, fedres),
        "agi": fedres["agi"],
        "state_taxable": stres.get("taxable_income", 0.0),
        "state_tax": stres.get("tax", 0.0),
    }
    rate_desc = ""
    tax = 0.0
    base = bases.get(base_key, bases["state_taxable"])
    if method == "flat":
        rate = (override_rate / 100.0) if (override_rate and j.get("editable")) else j["rate"]
        if base_key == "earned_less_exemptions" or j.get("base") == "earned_less_exemptions":
            people = (2 if ret.is_joint() else 1) + len(ret.dependents)
            base = max(0.0, bases["earned"] + ret.income.taxable_interest + ret.income.ordinary_dividends
                       - j.get("exemption", 0) * people)
        tax = base * rate
        rate_desc = f"{rate * 100:.4g}%"
    elif method == "graduated":
        br = _status_brackets(j["brackets"], status, j.get("hoh_uses", "single"))
        tax = bracket_tax(base, br)
        rate_desc = f"{br[0][1] * 100:.4g}% - {br[-1][1] * 100:.4g}%"
    elif method == "band_flat":
        bands = _status_brackets(j["bands"], status, j.get("hoh_uses", "single"))
        rate = bands[0][1]
        for floor, r in bands:
            if base > floor:
                rate = r
        tax = base * rate
        rate_desc = tr("{r}% (segun rango)", r=f"{rate * 100:.4g}")
    elif method == "pct_of_state_tax":
        rate = (override_rate / 100.0) if (override_rate and j.get("editable")) else j["rate"]
        base = bases["state_tax"]
        tax = base * rate
        rate_desc = tr("{r}% del impuesto estatal", r=f"{rate * 100:.4g}")
    elif method == "threshold":
        tiers = _status_brackets(j["tiers"], status, "mfj")
        tax = 0.0
        for i, (floor, rate) in enumerate(tiers):
            top = tiers[i + 1][0] if i + 1 < len(tiers) else float("inf")
            if base > floor:
                tax += (min(base, top) - floor) * rate
        rate_desc = _("sobre umbral")
    elif method == "monthly":
        months = 12 if fedres["wages"] > 0 else 0
        tax = j["amount"] * months
        base = months
        rate_desc = tr("${a}/mes", a=f"{j['amount']:.2f}")
    return {"name": name, "base": r2(base), "rate": rate_desc, "tax": r2(tax), "note": _(j.get("note", "")),
            "monthly": method == "monthly"}


def compute_local(ret: TaxReturn, fedres: dict, stres: dict) -> dict:
    code = (ret.address.state or "").upper()
    ld = data_loader.local(ret.tax_year)
    sdata = ld["states"].get(code, {})
    items: List[dict] = []
    notes: List[str] = []
    ex = ret.state_extras

    if sdata.get("county_tax"):
        counties = sdata["counties"]
        c = find_county(counties, ret.address.county)
        if c:
            j = dict(counties[c])
            j.setdefault("base", sdata.get("base", "state_taxable"))
            items.append(_apply(j, tr("Condado: {c}", c=c), ret, fedres, stres))
        else:
            notes.append(tr("{label}: seleccione un condado valido de {code} en 'Direccion y residencia' para calcularlo.",
                            label=_(sdata.get("label", N_("Impuesto de condado"))), code=code))
        notes.extend(_(n) for n in sdata.get("notes", []))

    locs = sdata.get("localities", {})
    for which, label in ((ret.address.locality, "Residencia"), (ret.address.work_locality, "Trabajo")):
        if which and which in locs:
            if label == "Trabajo" and which == ret.address.locality:
                continue
            it = _apply(locs[which], _(which), ret, fedres, stres, ex.locality_rate_override)
            it["kind"] = label
            items.append(it)

    for c in ex.custom_local:
        if not c.name and not c.rate:
            continue
        j = {"method": "pct_of_state_tax" if c.base == "state_tax" else "flat", "base": c.base, "rate": c.rate / 100.0}
        it = _apply(j, c.name or _("Impuesto local personalizado"), ret, fedres, stres)
        it["kind"] = "Personalizado"
        items.append(it)

    total = sum(i["tax"] for i in items)
    withheld = sum(w.box19_local_withheld for w in ret.w2s) + sum(c.withheld for c in ex.custom_local)
    payments = withheld + ret.payments.local_estimated
    balance = payments - total
    if not items and not sdata:
        notes.append(_("Su estado no tiene impuestos locales sobre la renta incluidos. Los condados cobran impuesto a la "
                       "propiedad y a las ventas, que no se declaran en esta declaracion."))
    return {"items": items, "total": r2(total), "withholding": r2(withheld), "payments": r2(payments),
            "balance": r2(balance), "refund": r2(max(0.0, balance)), "owed": r2(max(0.0, -balance)), "notes": notes}


def localities_for_state(year: int, code: str) -> list:
    s = data_loader.local(year)["states"].get((code or "").upper(), {})
    return list(s.get("localities", {}).keys())


def county_tax_info(year: int, code: str, county: str) -> str:
    s = data_loader.local(year)["states"].get((code or "").upper(), {})
    if not s.get("county_tax"):
        return _("Sin impuesto de condado sobre la renta.")
    c = find_county(s["counties"], county)
    if not c:
        return _("Seleccione el condado para ver su tasa.")
    j = s["counties"][c]
    if j["method"] == "flat":
        return tr("{c}: {r}% sobre el ingreso tributable estatal.", c=c, r=f"{j['rate'] * 100:.4g}")
    return f"{c}: {_(j.get('note', N_('tasa progresiva')))}"
