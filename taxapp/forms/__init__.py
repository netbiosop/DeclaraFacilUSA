"""Formularios oficiales del IRS llenos en PDF / Filled official IRS forms (PDF).

Uso:
    from taxapp import forms
    plan = forms.plan(ret, res)                       # qué formularios se necesitan y avisos
    out = forms.generate(ret, res, carpeta, draft=True)   # borrador con marca de agua
    out = forms.generate(ret, res, carpeta, draft=False)  # formularios finales para firmar y enviar

Se generan: un PDF por formulario, el paquete completo en orden de adjuntos, el comprobante 1040-V si hay saldo a
pagar y una hoja de instrucciones de envío (dirección del IRS, qué firmar, qué adjuntar).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

from .. import APP_NAME
from ..engine import fmt_money
from ..i18n import _, is_en, tr
from ..models import FILING_STATUSES, TaxReturn
from . import catalog, mailing, pdf
from .build import Plan, build as _build
from .pdf import MissingDependency

__all__ = ["available", "plan", "generate", "Generated", "MissingDependency", "pdf_support", "mailing"]


def pdf_support() -> bool:
    return pdf.pypdf is not None


def available(year: int) -> bool:
    return catalog.available(year)


def forms_language(ret: TaxReturn) -> str:
    """Idioma de los formularios: el elegido en la declaración o, si no se eligió, el idioma de la aplicación."""
    lang = (ret.filing.forms_language or "").strip()
    if lang in ("en", "es"):
        return lang
    return "en" if is_en() else "es"


def plan(ret: TaxReturn, res: dict, preparer: Optional[dict] = None, use_sr: Optional[bool] = None,
         lang: Optional[str] = None) -> Plan:
    return _build(ret, res, preparer, use_sr, lang or forms_language(ret))


@dataclass
class Generated:
    folder: Path
    package: Optional[Path] = None           # todos los formularios en orden, listo para imprimir
    instructions: Optional[Path] = None      # hoja de instrucciones de envío
    voucher: Optional[Path] = None           # 1040-V (si hay saldo a pagar)
    files: List[Path] = field(default_factory=list)   # un PDF por formulario
    forms: List[str] = field(default_factory=list)
    pages: int = 0
    warnings: List[str] = field(default_factory=list)
    draft: bool = False
    mailing: dict = field(default_factory=dict)
    lang: str = "en"
    spanish: List[str] = field(default_factory=list)   # formularios generados en su versión oficial en español


def _safe(s: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", s or "", flags=re.UNICODE).strip().replace(" ", "_")
    return s[:40] or "declaracion"


def default_folder(ret: TaxReturn, base: Path, draft: bool) -> Path:
    who = _safe(f"{ret.taxpayer.last_name}_{ret.taxpayer.first_name}")
    kind = _("borrador") if draft else _("formularios")
    return base / f"{who}_{ret.tax_year}_{_safe(kind)}"


def generate(ret: TaxReturn, res: dict, folder: Path, *, draft: bool, editable: bool = False,
             preparer: Optional[dict] = None, use_sr: Optional[bool] = None,
             lang: Optional[str] = None) -> Generated:
    pdf.require()
    year = ret.tax_year
    if not catalog.available(year):
        raise FileNotFoundError(tr("No hay formularios oficiales del IRS para {y} en esta versión.", y=year))
    lang = lang or forms_language(ret)
    p = _build(ret, res, preparer, use_sr, lang)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = Generated(folder=folder, draft=draft, warnings=list(p.warnings), forms=p.forms(), lang=lang)
    stamp = date.today().isoformat()
    big = _("BORRADOR - NO PRESENTAR")
    small = tr("Borrador generado el {d} con {app}. Revise todos los datos antes de firmar.", d=stamp, app=APP_NAME)
    prefix = (_("BORRADOR") + "_") if draft else ""

    def finish(data: bytes) -> bytes:
        return pdf.watermark(data, big, small) if draft else data

    # Formularios en el orden de adjuntos
    order = {fid: i for i, fid in enumerate(catalog.ORDER)}
    insts = sorted([i for i in p.instances if i.form != "1040v"], key=lambda i: order.get(i.form, 99))
    parts: List[bytes] = []
    per_form: dict = {}
    for inst in insts:
        var = catalog.variant(year, inst.form, lang)
        if var["lang"] == "es":
            out.spanish.append(inst.form) if inst.form not in out.spanish else None
        pages = inst.pages
        if inst.form == "1040sr" and var.get("pages"):
            pages = list(range(var["pages"] - 1))   # la última página es la tabla de deducción estándar
        args = (catalog.forms_dir(year) / var["file"], var["fields"], inst.values)
        flat = pdf.fill(*args, flatten=True, pages=pages)
        live = pdf.fill(*args, flatten=False, pages=pages) if editable else None
        per_form.setdefault(inst.form, []).append((flat, live))
    seq = 1
    for fid in sorted(per_form, key=lambda f: order.get(f, 99)):
        datas = per_form[fid]
        flat = finish(datas[0][0] if len(datas) == 1 else pdf.merge([d[0] for d in datas]))
        # El archivo individual queda editable solo si hay una copia (varias copias comparten nombres de campo).
        single = finish(datas[0][1]) if editable and len(datas) == 1 else flat
        path = folder / f"{prefix}{seq:02d}_{catalog.file_name(fid)}_{year}.pdf"
        path.write_bytes(single)
        out.files.append(path)
        parts.append(flat)
        seq += 1
    # Hojas adicionales (dependientes extra, pagadores extra, etc.)
    for stmt in p.statements:
        blocks = [("h1", stmt["title"]), ("p", f"{_names(ret)}   SSN {_ssn(ret.taxpayer.ssn)}"), ("sp", 6)]
        blocks += [("mono", ln) for ln in stmt["lines"]]
        data = finish(pdf.text_document(blocks, footer=f"{APP_NAME} - Form {catalog.SHORT.get(p.main_form)} {year}"))
        path = folder / f"{prefix}{seq:02d}_{_('Hoja_adicional')}_{_safe(stmt['title'])}.pdf"
        path.write_bytes(data)
        out.files.append(path)
        parts.append(data)
        seq += 1
    package = pdf.merge(parts)
    out.pages = pdf.page_count(package)
    out.package = folder / f"{prefix}{_('Declaracion_federal')}_{year}_{_('COMPLETA')}.pdf"
    out.package.write_bytes(package)
    # 1040-V aparte (va suelto, encima, con el cheque)
    owed = res["federal"]["lines"].get("37", 0.0)
    v_inst = [i for i in p.instances if i.form == "1040v"]
    if v_inst:
        var = catalog.variant(year, "1040v", lang)
        data = finish(pdf.fill(catalog.forms_dir(year) / var["file"], var["fields"], v_inst[0].values,
                               flatten=not editable))
        out.voucher = folder / f"{prefix}{catalog.file_name('1040v')}_{year}.pdf"
        out.voucher.write_bytes(data)
    # Instrucciones de envío
    out.mailing = mailing.mailing_info(ret.address.state, owed)
    out.instructions = folder / f"{prefix}00_{_('LEAME_Instrucciones_de_envio')}.pdf"
    out.instructions.write_bytes(instructions_pdf(ret, res, p, out, draft))
    return out


def _names(ret: TaxReturn) -> str:
    n = ret.taxpayer.full_name()
    if ret.is_joint() and ret.spouse.full_name():
        n += " & " + ret.spouse.full_name()
    return n.upper()


def _ssn(s: str) -> str:
    d = "".join(ch for ch in s or "" if ch.isdigit())
    return f"XXX-XX-{d[-4:]}" if len(d) == 9 else "—"


def instructions_pdf(ret: TaxReturn, res: dict, p: Plan, out: Generated, draft: bool) -> bytes:
    fed = res["federal"]
    L = fed["lines"]
    year = ret.tax_year
    info = out.mailing
    main = catalog.short(p.main_form)
    blocks = [("h1", tr("Declaración federal {y} — instrucciones de envío", y=year))]
    if draft:
        blocks.append(("box", _("ESTE ES UN BORRADOR. No lo firme ni lo envíe: revíselo y genere los formularios "
                                 "finales desde la aplicación.")))
    blocks += [("p", tr("Contribuyente: {n}   •   SSN {s}", n=_names(ret), s=_ssn(ret.taxpayer.ssn))),
               ("p", tr("Estado civil: {s}", s=_(FILING_STATUSES.get(ret.filing_status, ret.filing_status))))]
    if L.get("37", 0) >= 1:
        blocks.append(("p", tr("Resultado: SALDO A PAGAR de {a}", a=fmt_money(L["37"]))))
    elif L.get("34", 0) >= 1:
        blocks.append(("p", tr("Resultado: REEMBOLSO de {a}", a=fmt_money(L["34"]))))
    else:
        blocks.append(("p", _("Resultado: sin saldo a pagar ni reembolso.")))
    blocks += [("sp", 6), ("h2", _("Envíe su declaración por correo a:"))]
    blocks.append(("box", "\n".join(info["address"])))
    blocks.append(("p", tr("Dirección del IRS para su estado ({s}) {w}. Confírmela antes de enviar en: {u}",
                           s=ret.address.state or "—",
                           w=_("con pago") if info["with_payment"] else _("sin pago"), u=info["url"])))
    blocks += [("sp", 4), ("h2", _("Pasos para presentar"))]
    steps = [_("Revise cada formulario. Si algo no coincide, corríjalo en la aplicación y vuelva a generar.")]
    if ret.is_joint():
        steps.append(tr("Firme y feche el Formulario {f} en la página de firma ('Sign Here'). Al ser declaración "
                        "conjunta, AMBOS cónyuges deben firmar.", f=main))
    else:
        steps.append(tr("Firme y feche el Formulario {f} en la página de firma ('Sign Here').", f=main))
    steps.append(_("Adjunte la Copia B de cada W-2 (y de los W-2G y 1099-R con impuesto retenido) en el frente de la "
                   "página 1 del 1040."))
    steps.append(tr("Ordene las hojas así: {lst}. Así está armado el archivo COMPLETO.",
                    lst=", ".join(catalog.short(f) for f in p.forms() if f != "1040v")))
    if L.get("37", 0) >= 1:
        steps.append(tr("Pague {a}: en línea en www.irs.gov/payments (recomendado), o con cheque/giro a nombre de "
                        "\"United States Treasury\" escribiendo en él su teléfono, su SSN y \"{y} Form {f}\". Coloque "
                        "el cheque y el Formulario 1040-V SUELTOS (sin grapas) encima de la declaración.",
                        a=fmt_money(L["37"]), y=year, f=main))
    if L.get("34", 0) >= 1:
        if ret.filing.direct_deposit:
            steps.append(_("Verifique el número de ruta y de cuenta del depósito directo (líneas 35b y 35d)."))
        else:
            steps.append(_("El reembolso llegará por cheque a la dirección de la página 1. Para recibirlo antes, "
                           "indique una cuenta para depósito directo."))
    steps.append(tr("Envíe antes de la fecha límite ({d}). Si pidió prórroga, el plazo es el 15 de octubre. "
                    "Use correo certificado con acuse de recibo para tener comprobante.", d=fed.get("deadline", "")))
    steps.append(_("Guarde una copia completa (formularios, W-2, 1099 y comprobantes) por al menos 3 años."))
    for i, s in enumerate(steps, 1):
        blocks.append(("p", f"{i}. {s}"))
    blocks += [("sp", 4), ("h2", _("Formularios incluidos"))]
    for f in p.forms():
        n = sum(1 for inst in p.instances if inst.form == f)
        extra = tr(" ({n} copias)", n=n) if n > 1 else ""
        if out.lang == "es":
            extra += "  " + (_("[versión oficial en español]") if f in out.spanish or
                             (f == "1040v" and catalog.has_spanish(year, f)) else _("[solo existe en inglés]"))
        blocks.append(("p", f"• {catalog.title(year, f)}{extra}"))
    if out.lang == "es":
        blocks.append(("p", _("El IRS acepta las versiones en español (por ejemplo, el Formulario 1040(SP)) igual que "
                              "las versiones en inglés. Los formularios que el IRS no publica en español se presentan "
                              "en inglés; puede combinarlos en la misma declaración.")))
    if p.statements:
        blocks.append(("p", tr("• Hojas adicionales: {n}", n=len(p.statements))))
    if p.warnings:
        blocks += [("sp", 4), ("h2", _("Revise antes de firmar"))]
        blocks += [("p", f"• {w}") for w in p.warnings]
    blocks += [("sp", 6), ("p", _("Esta aplicación no presenta declaraciones electrónicamente ni envía nada al IRS. "
                                  "Usted es responsable de revisar la información antes de firmarla."))]
    return pdf.text_document(blocks, footer=f"{APP_NAME} • {date.today().isoformat()}")
