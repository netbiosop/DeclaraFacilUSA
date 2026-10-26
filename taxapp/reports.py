"""Genera el borrador de la declaracion (Formulario 1040, anexos, estatal y local) en PDF o HTML.
Generates the return draft (Form 1040, schedules, state and local) as PDF or HTML, in the current language.

El PDF requiere 'reportlab' (pip install reportlab). Si no esta instalado, se genera HTML imprimible.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import List, Tuple

from . import APP_NAME, __version__, data_loader
from .engine import fmt_money, balance_text
from .i18n import _, N_, tr, get_language
from .models import FILING_STATUSES, TaxReturn

LINE_LABELS = [
    ("1z", N_("Salarios, sueldos y propinas (W-2)")), ("2a", N_("Intereses exentos de impuestos")),
    ("2b", N_("Intereses tributables")), ("3a", N_("Dividendos calificados")), ("3b", N_("Dividendos ordinarios")),
    ("4a", N_("Distribuciones de IRA")), ("4b", N_("IRA - monto tributable")), ("5a", N_("Pensiones y anualidades")),
    ("5b", N_("Pensiones - monto tributable")), ("6a", N_("Beneficios del Seguro Social")), ("6b", N_("Seguro Social tributable")),
    ("7", N_("Ganancia o (perdida) de capital")), ("8", N_("Ingresos adicionales (Anexo 1, linea 10)")),
    ("9", N_("INGRESO TOTAL")), ("10", N_("Ajustes al ingreso (Anexo 1, linea 26)")),
    ("11", N_("INGRESO BRUTO AJUSTADO (AGI)")), ("12", N_("Deduccion estandar o itemizada (Anexo A)")),
    ("13a", N_("Deduccion por ingreso calificado de negocio (QBI)")), ("13b", N_("Deducciones adicionales (Anexo 1-A)")),
    ("14", N_("Total de deducciones")), ("15", N_("INGRESO TRIBUTABLE")), ("16", N_("Impuesto")),
    ("17", N_("Impuesto minimo alternativo (Anexo 2, linea 3)")), ("18", N_("Suma de lineas 16 y 17")),
    ("19", N_("Credito por hijos y otros dependientes")), ("20", N_("Creditos no reembolsables (Anexo 3, linea 8)")),
    ("21", N_("Total de creditos")), ("22", N_("Impuesto menos creditos")),
    ("23", N_("Otros impuestos, incl. trabajo independiente (Anexo 2, linea 21)")), ("24", N_("IMPUESTO TOTAL")),
    ("25a", N_("Retencion federal - W-2")), ("25b", N_("Retencion federal - 1099 y otros")), ("25d", N_("Total retenido")),
    ("26", N_("Pagos estimados y con la prorroga")), ("27", N_("Credito por ingreso del trabajo (EIC)")),
    ("28", N_("Credito tributario adicional por hijos (ACTC)")), ("29", N_("Credito de oportunidad americana (reembolsable)")),
    ("31", N_("Otros pagos (Anexo 3, linea 15)")), ("32", N_("Total de otros pagos y creditos reembolsables")),
    ("33", N_("PAGOS TOTALES")), ("34", N_("PAGO EN EXCESO (REEMBOLSO)")), ("37", N_("CANTIDAD ADEUDADA")),
]

DISCLAIMER = N_("Este documento es un BORRADOR generado por un estimador. No es un formulario oficial del IRS ni de su estado. "
              "Transcriba los montos a los formularios oficiales (irs.gov y el sitio de su estado) o use un servicio de "
              "presentacion electronica autorizado. Verifique todos los valores; la ley tributaria cambia y algunos casos "
              "especiales no estan modelados.")

SEVERITY = {"error": N_("ERROR"), "aviso": N_("REVISE"), "info": N_("Nota"), "ok": N_("Listo")}


def build_sections(ret: TaxReturn, res: dict, findings: List[dict]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    fed, st, loc = res["federal"], res["state"], res["local"]
    a = ret.address
    info = data_loader.states_info().get(a.state, {})
    S = []
    names = ret.taxpayer.full_name() + (tr(" y {n}", n=ret.spouse.full_name()) if ret.is_joint() and ret.spouse.full_name() else "")
    S.append((_("Datos del contribuyente"), [
        (_("Ano fiscal"), str(ret.tax_year)),
        (_("Nombre(s)"), names or "-"),
        (_("Estado civil para la declaracion"), _(FILING_STATUSES.get(ret.filing_status, ret.filing_status))),
        (_("Direccion"), ", ".join(x for x in (a.street, a.apt, a.city, a.state, a.zip) if x) or "-"),
        (_("Condado"), a.county or "-"),
        (_("Jurisdiccion local"), _(a.locality) if a.locality else "-"),
        (_("Dependientes"), ", ".join(d.full_name() for d in ret.dependents) or _("Ninguno")),
    ]))
    S.append((_("Resumen"), [
        (_("Federal"), balance_text(fed["balance"])),
        (tr("Estatal ({s})", s=st.get("name") or a.state or "-"), balance_text(st["balance"])),
        (_("Local"), balance_text(loc["balance"])),
        (_("TOTAL"), balance_text(res["summary"]["total_balance"])),
        (_("Tasa marginal federal"), f"{fed['marginal_rate'] * 100:.0f}%"),
        (_("Tasa efectiva federal (impuesto total / ingreso total)"), f"{fed['effective_rate'] * 100:.2f}%"),
        (_("Fecha limite federal"), fed["deadline"]),
    ]))
    L = fed["lines"]
    S.append((tr("Formulario 1040 ({y}) - borrador linea por linea", y=ret.tax_year),
              [(tr("Linea {k}: {lbl}", k=k, lbl=_(lbl)), fmt_money(L.get(k, 0))) for k, lbl in LINE_LABELS]))
    sch1 = [(_("Ganancia neta de negocio (Anexo C)"), fmt_money(fed["profit"])),
            (_("Desempleo, reembolsos estatales, juegos y otros"), fmt_money(fed["lines"]["8"] - fed["profit"])),
            (_("Mitad del impuesto de trabajo independiente"), fmt_money(fed["half_se"])),
            (_("Seguro medico de trabajador independiente"), fmt_money(fed["se_health"])),
            (_("Gastos de educador"), fmt_money(fed["educator"])),
            (_("HSA"), fmt_money(ret.deductions.hsa_deduction)), (_("IRA"), fmt_money(ret.deductions.ira_deduction)),
            (_("Interes de prestamos estudiantiles"), fmt_money(fed["student_loan"])),
            (_("Total de ajustes"), fmt_money(fed["adjustments"]))]
    S.append((_("Anexo 1 - Ingresos adicionales y ajustes"), sch1))
    s1a = fed["sched1a"]
    S.append((_("Anexo 1-A - Deducciones adicionales (OBBBA)"), [
        (_("Propinas calificadas"), fmt_money(s1a["tips"])), (_("Horas extra calificadas"), fmt_money(s1a["overtime"])),
        (_("Interes de prestamo de auto"), fmt_money(s1a["car_loan"])), (_("Deduccion para mayores de 65"), fmt_money(s1a["senior"])),
        (_("Total"), fmt_money(s1a["total"]))]))
    it = fed["itemized_detail"]
    S.append((_("Deducciones (Anexo A vs. estandar)"), [
        (_("Deduccion estandar disponible"), fmt_money(fed["standard_deduction"])),
        (_("Gastos medicos (sobre 7.5% del AGI)"), fmt_money(it["medical"])),
        (_("Impuestos estatales y locales (SALT) deducibles"),
         tr("{a} (pagado {b}, tope {c})", a=fmt_money(it["salt"]), b=fmt_money(it["salt_raw"]), c=fmt_money(it["salt_cap"]))),
        (_("Intereses (hipoteca, puntos, inversion)"), fmt_money(it["interest"])),
        (_("Donaciones caritativas"), fmt_money(it["charity"])), (_("Otras"), fmt_money(it["other"])),
        (_("Reduccion por tramo del 37% (2026+)"), fmt_money(it["limit_37"])),
        (_("Total itemizado"), fmt_money(fed["itemized_net"])),
        (_("Metodo usado"), _("Itemizada") if fed["itemize"] else _("Estandar")),
        (_("Donacion para quien no itemiza (2026+)"), fmt_money(fed["nonitemizer_charity"]))]))
    c = fed["credits"]
    S.append((_("Creditos"), [
        (tr("Credito por hijos (CTC, {a} hijos) + otros dependientes ({b})", a=c["n_ctc"], b=c["n_odc"]), fmt_money(c["ctc_nonref"])),
        (_("Credito adicional por hijos (ACTC, reembolsable)"), fmt_money(c["actc"])),
        (tr("Credito por ingreso del trabajo (EITC, {n} hijos)", n=c["n_eitc"]), fmt_money(c["eitc"])),
        (_("Cuidado de hijos y dependientes (Form 2441)"), fmt_money(c["cdcc"])),
        (_("Educativos no reembolsables (AOTC/LLC)"), fmt_money(c["education_nonref"])),
        (_("AOTC reembolsable"), fmt_money(c["aotc_refundable"])),
        (_("Credito del ahorrador (Form 8880)"), fmt_money(c["savers"])),
        (_("Impuestos extranjeros"), fmt_money(c["foreign"]))]))
    o = fed["other_taxes"]
    S.append((_("Anexo 2 / Anexo SE - Otros impuestos"), [
        (_("Impuesto de trabajo independiente (Anexo SE)"), fmt_money(o["se_tax"])),
        (_("Impuesto adicional de Medicare (Form 8959)"), fmt_money(o["addl_medicare"])),
        (_("Impuesto sobre ingresos netos de inversion (Form 8960)"), fmt_money(o["niit"])),
        (_("AMT (Form 6251, simplificado)"), fmt_money(fed["amt"]))]))
    if st.get("name"):
        rows = [(n, fmt_money(v)) for n, v in st.get("lines", [])]
        rows += [(_("Retencion estatal (W-2 casilla 17)"), fmt_money(st["withholding"])),
                 (_("Pagos y creditos reembolsables"), fmt_money(st["payments"])),
                 (_("Resultado"), balance_text(st["balance"])),
                 (_("Formulario"), st.get("form") or _("No requiere declaracion de renta")),
                 (_("Agencia"), f"{st.get('agency') or ''} - {st.get('url') or ''}")]
        S.append((tr("Declaracion estatal - {n} ({y})", n=st.get("name", ""), y=ret.tax_year), rows))
    lrows = [(f"{i['name']} ({i['rate']})", fmt_money(i["tax"])) for i in loc["items"]]
    lrows += [(_("Total impuestos locales"), fmt_money(loc["total"])), (_("Retencion local (W-2 casilla 19)"), fmt_money(loc["withholding"])),
              (_("Resultado local"), balance_text(loc["balance"]))]
    S.append((_("Impuestos locales (condado / ciudad)"), lrows))
    if info:
        stx = info["sales_tax"]
        S.append((_("Informacion de su zona"), [
            (_("Impuesto estatal a las ventas"), f"{stx['state']}%"), (_("Promedio local a las ventas"), f"{stx['avg_local']}%"),
            (_("Combinado promedio"), f"{stx['combined']}%"), (_("Fecha limite estatal"), f"{ret.tax_year + 1}-{info['deadline_mmdd']}")]))
    notes = [(f"[{_(SEVERITY.get(f['severity'], f['severity'])).upper()}]", f["message"]) for f in findings if f["severity"] != "ok"]
    notes += [(f"[{_('ESTADO')}]", n) for n in st.get("notes", [])]
    S.append((_("Revision y notas"), notes or [("OK", _("Sin observaciones"))]))
    S.append((_("Como presentar"), [
        (_("Federal en linea"), _("IRS Free File (irs.gov/freefile) o software autorizado (e-file). IRS Direct File no esta disponible en 2026.")),
        (_("Federal en papel"), _("Formulario 1040 oficial; direccion segun su estado: irs.gov/filing/where-to-file-tax-returns-addresses-listed-by-return-type")),
        (_("Pagar al IRS"), _("IRS Direct Pay (irs.gov/payments) o EFTPS")),
        (_("Estado de su reembolso"), _("irs.gov/refunds (Where's My Refund?)")),
        (_("Estatal"), f"{st.get('agency') or _('Departamento de ingresos de su estado')}: {st.get('url') or ''}"),
    ]))
    return S


def to_html(ret: TaxReturn, res: dict, findings: List[dict]) -> str:
    secs = build_sections(ret, res, findings)
    e = html.escape
    title = tr("Borrador de declaracion {y}", y=ret.tax_year)
    gen = tr("Generado el {d} con {app} v{v}", d=f"{datetime.now():%Y-%m-%d %H:%M}", app=APP_NAME, v=__version__)
    parts = [f"""<!doctype html><html lang="{get_language()}"><head><meta charset="utf-8">
<title>{e(title)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#1d2733;background:#fff}}
h1{{color:#0b5d3b;margin-bottom:4px}} .sub{{color:#5b6775;margin-bottom:24px}}
h2{{background:#0b5d3b;color:#fff;padding:6px 10px;font-size:15px;border-radius:4px;margin-top:26px}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td{{padding:5px 8px;border-bottom:1px solid #e3e8ee}}
td.v{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.disc{{background:#fff7e0;border:1px solid #f0d58a;padding:10px;border-radius:4px;font-size:12px;margin-top:20px}}
@media print{{h2{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<h1>{e(APP_NAME)} - {e(title)}</h1>
<div class="sub">{e(gen)}</div>
<div class="disc">{e(_(DISCLAIMER))}</div>"""]
    for t, rows in secs:
        parts.append(f"<h2>{e(t)}</h2><table>")
        for k, v in rows:
            parts.append(f"<tr><td>{e(str(k))}</td><td class='v'>{e(str(v))}</td></tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def to_pdf(ret: TaxReturn, res: dict, findings: List[dict], path: str) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

    styles = getSampleStyleSheet()
    green = colors.HexColor("#0b5d3b")
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=green, fontSize=18, spaceAfter=4)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=8.5, leading=11)
    cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=9, leading=11.5)
    cell_r = ParagraphStyle("cr", parent=cell, alignment=2)
    head = ParagraphStyle("t", parent=cell, textColor=colors.white)
    disc = ParagraphStyle("d", parent=small, backColor=colors.HexColor("#fff7e0"), borderColor=colors.HexColor("#f0d58a"),
                          borderWidth=0.6, borderPadding=6, spaceAfter=10)
    title = tr("Borrador de declaracion {y}", y=ret.tax_year)
    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch, title=title, author=APP_NAME)
    story = [Paragraph(html.escape(f"{APP_NAME} - {title}"), h1),
             Paragraph(html.escape(tr("Generado el {d} con {app} v{v}", d=f"{datetime.now():%Y-%m-%d %H:%M}",
                                      app=APP_NAME, v=__version__)), small), Spacer(1, 6),
             Paragraph(html.escape(_(DISCLAIMER)), disc)]
    for t_, rows in build_sections(ret, res, findings):
        data = [[Paragraph(f"<b>{html.escape(t_)}</b>", head), ""]]
        for k, v in rows:
            data.append([Paragraph(html.escape(str(k)), cell), Paragraph(html.escape(str(v)), cell_r)])
        t = Table(data, colWidths=[4.9 * inch, 2.4 * inch], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), green), ("SPAN", (0, 0), (-1, 0)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d9e0e7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story += [KeepTogether([t]) if len(rows) < 25 else t, Spacer(1, 10)]

    foot_left = tr("{app} - borrador no oficial - {n}", app=APP_NAME, n=ret.taxpayer.full_name())

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.6 * inch, 0.4 * inch, foot_left)
        canvas.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch, tr("Pagina {p}", p=d.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
