"""Genera data/formularios/<año>.json: el mapa de 'clave de línea' -> campo del PDF oficial del IRS.

Herramienta de desarrollo (no la usa la aplicación). Cada año el IRS publica los PDF nuevos y los nombres internos de
los campos pueden cambiar: se revisan con el volcado de campos (--volcar) y se ajusta SPEC. El script valida que cada
campo exista en el PDF y que la casilla tenga el estado indicado; si algo no coincide, se detiene.

Uso:
    python herramientas/mapear_formularios.py 2025            -> valida y escribe data/formularios/2025.json
    python herramientas/mapear_formularios.py 2025 --volcar   -> lista los campos de cada PDF (para revisar)

Notación de rutas: "P1.f1_14" = "Page1[0].f1_14[0]"; un segmento sin [n] recibe [0]. Las casillas llevan el estado
"encendido" tras '=' (p. ej. "P1.c1_8[1]=/2").
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------------------------------------- formularios
# id: (archivo, raíz XFA, número de secuencia de adjunto, título ES, título EN)
FORMS = {
    "1040": ("f1040.pdf", "topmostSubform", "", "Formulario 1040 – Declaración de impuestos", "Form 1040 – Individual Income Tax Return"),
    "1040sr": ("f1040s.pdf", "topmostSubform", "", "Formulario 1040-SR – Declaración para mayores de 65", "Form 1040-SR – Return for Seniors"),
    "s1": ("f1040s1.pdf", "topmostSubform", "01", "Anexo 1 – Ingresos adicionales y ajustes", "Schedule 1 – Additional Income and Adjustments"),
    "s1a": ("f1040s1a.pdf", "form1", "1A", "Anexo 1-A – Deducciones adicionales", "Schedule 1-A – Additional Deductions"),
    "s2": ("f1040s2.pdf", "form1", "02", "Anexo 2 – Impuestos adicionales", "Schedule 2 – Additional Taxes"),
    "s3": ("f1040s3.pdf", "topmostSubform", "03", "Anexo 3 – Créditos y pagos adicionales", "Schedule 3 – Additional Credits and Payments"),
    "sa": ("f1040sa.pdf", "form1", "07", "Anexo A – Deducciones detalladas", "Schedule A – Itemized Deductions"),
    "sb": ("f1040sb.pdf", "topmostSubform", "08", "Anexo B – Intereses y dividendos", "Schedule B – Interest and Dividends"),
    "sc": ("f1040sc.pdf", "topmostSubform", "09", "Anexo C – Ganancias o pérdidas de un negocio", "Schedule C – Profit or Loss From Business"),
    "sd": ("f1040sd.pdf", "topmostSubform", "12", "Anexo D – Ganancias y pérdidas de capital", "Schedule D – Capital Gains and Losses"),
    "8949": ("f8949.pdf", "topmostSubform", "12A", "Formulario 8949 – Ventas de activos de capital", "Form 8949 – Sales of Capital Assets"),
    "sse": ("f1040sse.pdf", "topmostSubform", "17", "Anexo SE – Impuesto sobre el trabajo por cuenta propia", "Schedule SE – Self-Employment Tax"),
    "2441": ("f2441.pdf", "topmostSubform", "21", "Formulario 2441 – Gastos de cuidado de hijos y dependientes", "Form 2441 – Child and Dependent Care Expenses"),
    "6251": ("f6251.pdf", "topmostSubform", "32", "Formulario 6251 – Impuesto mínimo alternativo", "Form 6251 – Alternative Minimum Tax"),
    "sei": ("f1040sei.pdf", "topmostSubform", "43", "Anexo EIC – Crédito por ingreso del trabajo", "Schedule EIC – Earned Income Credit"),
    "s8812": ("f1040s8.pdf", "topmostSubform", "47", "Anexo 8812 – Crédito por hijos y otros dependientes", "Schedule 8812 – Credits for Qualifying Children and Other Dependents"),
    "8863": ("f8863.pdf", "topmostSubform", "50", "Formulario 8863 – Créditos educativos", "Form 8863 – Education Credits"),
    "8889": ("f8889.pdf", "topmostSubform", "52", "Formulario 8889 – Cuentas de ahorro para la salud (HSA)", "Form 8889 – Health Savings Accounts"),
    "8880": ("f8880.pdf", "topmostSubform", "54", "Formulario 8880 – Crédito por aportes de ahorro para la jubilación", "Form 8880 – Retirement Savings Contributions Credit"),
    "8995": ("f8995.pdf", "topmostSubform", "55", "Formulario 8995 – Deducción por ingreso de negocio calificado", "Form 8995 – Qualified Business Income Deduction"),
    "8959": ("f8959.pdf", "topmostSubform", "71", "Formulario 8959 – Impuesto adicional de Medicare", "Form 8959 – Additional Medicare Tax"),
    "8960": ("f8960.pdf", "topmostSubform", "72", "Formulario 8960 – Impuesto sobre ingresos netos de inversión", "Form 8960 – Net Investment Income Tax"),
    "1040v": ("f1040v.pdf", "topmostSubform", "", "Formulario 1040-V – Comprobante de pago", "Form 1040-V – Payment Voucher"),
}


# Versiones oficiales en español publicadas por el IRS (van en data/formularios/<año>/es/). Los demás formularios
# solo existen en inglés.
SPANISH = {"1040": "f1040sp.pdf", "1040sr": "f1040srs.pdf", "s1": "f1040s1s.pdf", "s1a": "f1040asp.pdf",
           "s2": "f1040s2s.pdf", "s3": "f1040s3s.pdf", "s8812": "f1040s8s.pdf", "sc": "f1040scs.pdf",
           "sei": "f1040sep.pdf", "sse": "f1040ssp.pdf"}


def spec_1040():
    s = {
        "first": "P1.f1_14", "last": "P1.f1_15", "ssn": "P1.f1_16",
        "sp_first": "P1.f1_17", "sp_last": "P1.f1_18", "sp_ssn": "P1.f1_19",
        "street": "P1.Address_ReadOrder.f1_20", "apt": "P1.Address_ReadOrder.f1_21", "city": "P1.Address_ReadOrder.f1_22",
        "state": "P1.Address_ReadOrder.f1_23", "zip": "P1.Address_ReadOrder.f1_24",
        "f_country": "P1.Address_ReadOrder.f1_25", "f_province": "P1.Address_ReadOrder.f1_26", "f_postal": "P1.Address_ReadOrder.f1_27",
        "home_us": "P1.c1_5=/1", "pec_you": "P1.c1_6=/1", "pec_spouse": "P1.c1_7=/1",
        "fs_single": "P1.Checkbox_ReadOrder.c1_8[0]=/1", "fs_mfj": "P1.Checkbox_ReadOrder.c1_8[1]=/2",
        "fs_mfs": "P1.Checkbox_ReadOrder.c1_8[2]=/3", "mfs_spouse_name": "P1.Checkbox_ReadOrder.f1_28",
        "fs_hoh": "P1.c1_8[0]=/4", "fs_qss": "P1.c1_8[1]=/5", "hoh_child": "P1.f1_29",
        "digital_yes": "P1.c1_10[0]=/1", "digital_no": "P1.c1_10[1]=/2",
        "dep_more": "P1.Dependents_ReadOrder.c1_11=/1", "lived_apart": "P1.c1_32=/1",
        "L1a": "P1.f1_47", "L1b": "P1.f1_48", "L1c": "P1.f1_49", "L1d": "P1.f1_50", "L1e": "P1.f1_51", "L1f": "P1.f1_52",
        "L1g": "P1.f1_53", "L1h_type": "P1.f1_54", "L1h": "P1.f1_55", "L1i": "P1.f1_56", "L1z": "P1.f1_57",
        "L2a": "P1.f1_58", "L2b": "P1.f1_59", "L3a": "P1.f1_60", "L3b": "P1.f1_61", "L4a": "P1.f1_62", "L4b": "P1.f1_63",
        "L4c_rollover": "P1.c1_35=/1", "L5a": "P1.f1_65", "L5b": "P1.f1_66", "L5c_rollover": "P1.c1_38=/1",
        "L6a": "P1.f1_68", "L6b": "P1.f1_69", "L7a": "P1.f1_70", "L7b_nosd": "P1.c1_43=/1",
        "L8": "P1.f1_72", "L9": "P1.f1_73", "L10": "P1.f1_74", "L11a": "P1.f1_75",
        "L11b": "P2.f2_01", "L12a_you": "P2.c2_1=/1", "L12a_spouse": "P2.c2_2=/1", "L12b": "P2.c2_3=/1",
        "L12d_you65": "P2.c2_5=/1", "L12d_youblind": "P2.c2_6=/1", "L12d_sp65": "P2.c2_7=/1", "L12d_spblind": "P2.c2_8=/1",
        "L12e": "P2.f2_02", "L13a": "P2.f2_03", "L13b": "P2.f2_04", "L14": "P2.f2_05", "L15": "P2.f2_06",
        "L16": "P2.f2_08", "L17": "P2.f2_09", "L18": "P2.f2_10", "L19": "P2.f2_11", "L20": "P2.f2_12", "L21": "P2.f2_13",
        "L22": "P2.f2_14", "L23": "P2.f2_15", "L24": "P2.f2_16",
        "L25a": "P2.f2_17", "L25b": "P2.f2_18", "L25c": "P2.f2_19", "L25d": "P2.f2_20", "L26": "P2.f2_21",
        "L27a": "P2.f2_23", "L27c_noeic": "P2.c2_13=/1", "L28": "P2.f2_24", "L29": "P2.f2_25", "L30": "P2.f2_26",
        "L31": "P2.f2_27", "L32": "P2.f2_28", "L33": "P2.f2_29", "L34": "P2.f2_30", "L35a": "P2.f2_31",
        "routing": "P2.RoutingNo.f2_32", "acct_checking": "P2.c2_16[0]=/1", "acct_savings": "P2.c2_16[1]=/2",
        "account": "P2.AccountNo.f2_33", "L36": "P2.f2_34", "L37": "P2.f2_35", "L38": "P2.f2_36",
        "designee_yes": "P2.c2_17[0]=/1", "designee_no": "P2.c2_17[1]=/2", "designee_name": "P2.f2_37",
        "designee_phone": "P2.f2_38", "designee_pin": "P2.f2_39",
        "occupation": "P2.f2_40", "ippin": "P2.f2_41", "sp_occupation": "P2.f2_42", "sp_ippin": "P2.f2_43",
        "phone": "P2.f2_44", "email": "P2.f2_45",
        "prep_name": "P2.f2_46", "prep_ptin": "P2.f2_47", "prep_self": "P2.c2_18=/1", "prep_firm": "P2.f2_48",
        "prep_phone": "P2.f2_49", "prep_address": "P2.f2_50", "prep_ein": "P2.f2_51",
    }
    for i in range(4):
        d = f"P1.Table_Dependents.Row{{r}}.Dependent{i + 1}."
        s[f"dep{i}_first"] = f"P1.Table_Dependents.Row1.f1_{31 + i}"
        s[f"dep{i}_last"] = f"P1.Table_Dependents.Row2.f1_{35 + i}"
        s[f"dep{i}_ssn"] = f"P1.Table_Dependents.Row3.f1_{39 + i}"
        s[f"dep{i}_rel"] = f"P1.Table_Dependents.Row4.f1_{43 + i}"
        s[f"dep{i}_lived"] = d.format(r=5) + f"c1_{12 + 2 * i}=/1"
        s[f"dep{i}_us"] = d.format(r=5) + f"c1_{13 + 2 * i}=/1"
        s[f"dep{i}_student"] = d.format(r=6) + f"c1_{20 + 2 * i}=/1"
        s[f"dep{i}_disabled"] = d.format(r=6) + f"c1_{21 + 2 * i}=/1"
        s[f"dep{i}_ctc"] = d.format(r=7) + f"c1_{28 + i}[0]=/1"
        s[f"dep{i}_odc"] = d.format(r=7) + f"c1_{28 + i}[1]=/2"
    return s


def spec_s1():
    return {
        "name": "P1.f1_01", "ssn": "P1.f1_02",
        "L1": "P1.f1_04", "L3": "P1.f1_07", "L7": "P1.f1_12", "L8b": "P1.f1_14",
        "L8z_type": "P1.Line8z_ReadOrder.f1_35", "L8z": "P1.f1_36", "L9": "P1.f1_37", "L10": "P1.f1_38",
        "L11": "P2.f2_01", "L13": "P2.f2_03", "L15": "P2.f2_05", "L17": "P2.f2_07", "L20": "P2.f2_12", "L21": "P2.f2_13",
        "L24z_type": "P2.Line24z_ReadOrder.f2_27", "L24z": "P2.f2_28", "L25": "P2.f2_29", "L26": "P2.f2_30",
    }


def spec_s1a():
    s = {"name": "P1.f1_01", "ssn": "P1.f1_02", "L1": "P1.f1_03", "L2e": "P1.f1_08", "L3": "P1.f1_09"}
    for k, n in zip(["L4a", "L4b", "L4c", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12", "L13",
                     "L14a", "L14b", "L14c", "L15", "L16", "L17", "L18", "L19", "L20", "L21"], range(10, 32)):
        s[k] = f"P1.f1_{n}"
    s.update({
        "L22a_vin": "P2.Table_Line22.Line22a.VIN-1_Comb.f2_01", "L22a_ii": "P2.Table_Line22.Line22a.f2_02",
        "L22a_iii": "P2.Table_Line22.Line22a.f2_03",
    })
    for k, n in zip(["L23", "L24", "L25", "L26", "L27", "L28", "L29", "L30", "L31", "L32", "L33", "L34", "L35",
                     "L36a", "L36b", "L37", "L38"], range(7, 24)):
        s[k] = f"P2.f2_{n:02d}"
    return s


def spec_s2():
    return {"name": "P1.f1_01", "ssn": "P1.f1_02", "L1z": "P1.f1_11", "L2": "P1.f1_12", "L3": "P1.f1_13",
            "L4": "P1.f1_15", "L11": "P1.f1_22", "L12": "P1.f1_23", "L21": "P2.f2_24"}


def spec_s3():
    return {"name": "P1.f1_01", "ssn": "P1.f1_02", "L1": "P1.f1_03", "L2": "P1.f1_04", "L3": "P1.f1_05",
            "L4": "P1.f1_06", "L6z_type": "P1.Line6z_ReadOrder.f2_22", "L6z": "P1.f1_23", "L7": "P1.f1_24",
            "L8": "P1.f1_25", "L10": "P1.f1_27", "L11": "P1.f1_28", "L13z_type": "P1.Line13z_ReadOrder.f1_34",
            "L13z": "P1.f1_35", "L14": "P1.f1_36", "L15": "P1.f1_37"}


def spec_sa():
    return {"name": "P1.f1_1", "ssn": "P1.f1_2", "L1": "P1.f1_3", "L2": "P1.Line2_ReadOrder.f1_4", "L3": "P1.f1_5",
            "L4": "P1.f1_6", "L5a_sales": "P1.c1_1=/1", "L5a": "P1.f1_7", "L5b": "P1.f1_8", "L5c": "P1.f1_9",
            "L5d": "P1.f1_10", "L5e": "P1.f1_11", "L7": "P1.f1_14", "L8a": "P1.f1_15", "L8e": "P1.f1_20",
            "L9": "P1.f1_21", "L10": "P1.f1_22", "L11": "P1.f1_23", "L12": "P1.f1_24", "L14": "P1.f1_26",
            "L15": "P1.f1_27", "L16_type": "P1.f1_28", "L16": "P1.f1_29", "L17": "P1.f1_30",
            "L18": "P1.Line18_ReadOrder.c1_3=/1"}


def spec_sb():
    s = {"name": "P1.f1_01", "ssn": "P1.f1_02", "L2": "P1.f1_31", "L3": "P1.f1_32", "L4": "P1.f1_33", "L6": "P1.f1_64",
         "L7a_yes": "P1.TagcorrectingSubform.c1_1[0]=/1", "L7a_no": "P1.TagcorrectingSubform.c1_1[1]=/2",
         "fbar_yes": "P1.c1_2[0]=/1", "fbar_no": "P1.c1_2[1]=/2", "L7b": "P1.f1_65",
         "L8_yes": "P1.c1_3[0]=/1", "L8_no": "P1.c1_3[1]=/2"}
    for i in range(14):
        s[f"int{i}_name"] = "P1.Line1_ReadOrder.f1_03" if i == 0 else f"P1.f1_{3 + 2 * i:02d}"
        s[f"int{i}_amt"] = f"P1.f1_{4 + 2 * i:02d}"
    for i in range(15):
        s[f"div{i}_name"] = "P1.ReadOrderControl.f1_34" if i == 0 else f"P1.f1_{34 + 2 * i}"
        s[f"div{i}_amt"] = f"P1.f1_{35 + 2 * i}"
    return s


def spec_sc():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2", "A": "P1.f1_3", "B": "P1.BComb.f1_4", "C": "P1.f1_5", "D": "P1.DComb.f1_6",
         "E_addr": "P1.f1_7", "E_city": "P1.f1_8", "F_cash": "P1.c1_1[0]=/1", "F_accrual": "P1.c1_1[1]=/2",
         "G_yes": "P1.c1_2[0]=/Yes", "G_no": "P1.c1_2[1]=/No", "H": "P1.c1_3=/1",
         "I_yes": "P1.c1_4[0]=/Yes", "I_no": "P1.c1_4[1]=/No", "J_yes": "P1.c1_5[0]=/Yes", "J_no": "P1.c1_5[1]=/No",
         "L1": "P1.f1_10", "L2": "P1.f1_11", "L3": "P1.f1_12", "L4": "P1.f1_13", "L5": "P1.f1_14", "L6": "P1.f1_15",
         "L7": "P1.f1_16", "L8": "P1.Lines8-17.f1_17", "L9": "P1.Lines8-17.f1_18", "L11": "P1.Lines8-17.f1_20",
         "L15": "P1.Lines8-17.f1_24", "L18": "P1.Lines18-27.f1_28", "L20b": "P1.Lines18-27.f1_31",
         "L22": "P1.Lines18-27.f1_33", "L24a": "P1.Lines18-27.f1_35", "L24b": "P1.Lines18-27.f1_36",
         "L25": "P1.Lines18-27.f1_37", "L27b": "P1.Lines18-27.f1_39", "L28": "P1.f1_41", "L29": "P1.f1_42",
         "L30a": "P1.Line30_ReadOrder.f1_43", "L30b": "P1.Line30_ReadOrder.f1_44", "L30": "P1.f1_45", "L31": "P1.f1_46",
         "L32a": "P1.c1_7[0]=/1",
         "L33a": "P2.c2_1=/1", "L34_no": "P2.c2_4[1]=/2", "L35": "P2.f2_1", "L36": "P2.f2_2", "L40": "P2.f2_6",
         "L41": "P2.f2_7", "L42": "P2.f2_8",
         "L43_mm": "P2.f2_9", "L43_dd": "P2.f2_10", "L43_yyyy": "P2.f2_11", "L44a": "P2.f2_12", "L44b": "P2.f2_13",
         "L44c": "P2.f2_14", "L45_yes": "P2.c2_5[0]=/1", "L45_no": "P2.c2_5[1]=/2", "L46_yes": "P2.c2_6[0]=/1",
         "L46_no": "P2.c2_6[1]=/2", "L47a_yes": "P2.c2_7[0]=/1", "L47a_no": "P2.c2_7[1]=/2",
         "L47b_yes": "P2.c2_8[0]=/1", "L47b_no": "P2.c2_8[1]=/2", "L48": "P2.f2_33"}
    for i in range(9):
        s[f"oth{i}_desc"] = f"P2.PartVTable.Item{i + 1}.f2_{15 + 2 * i}"
        s[f"oth{i}_amt"] = f"P2.PartVTable.Item{i + 1}.f2_{16 + 2 * i}"
    return s


def spec_sd():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2", "qof_yes": "P1.c1_1[0]=/1", "qof_no": "P1.c1_1[1]=/2",
         "L6": "P1.f1_21", "L7": "P1.f1_22", "L13": "P1.f1_41", "L14": "P1.f1_42", "L15": "P1.f1_43",
         "L16": "P2.f2_1", "L17_yes": "P2.c2_1[0]=/1", "L17_no": "P2.c2_1[1]=/2", "L18": "P2.f2_2", "L19": "P2.f2_3",
         "L20_yes": "P2.c2_2[0]=/1", "L20_no": "P2.c2_2[1]=/2", "L21": "P2.f2_4",
         "L22_yes": "P2.c2_3[0]=/1", "L22_no": "P2.c2_3[1]=/2"}
    rows = [("1a", "Table_PartI.Row1a", 3, "degh"), ("1b", "Table_PartI.Row1b", 7, "degh"),
            ("2", "Table_PartI.Row2", 11, "degh"), ("3", "Table_PartI.Row3", 15, "degh"),
            ("8a", "Table_PartII.Row8a", 23, "degh"), ("8b", "Table_PartII.Row8b", 27, "degh"),
            ("9", "Table_PartII.Row9", 31, "degh"), ("10", "Table_PartII.Row10", 35, "degh")]
    for line, path, first, cols in rows:
        for j, c in enumerate(cols):
            s[f"L{line}{c}"] = f"P1.{path}.f1_{first + j}"
    return s


def spec_8949():
    s = {"name": "P1.f1_01", "ssn": "P1.f1_02", "name2": "P2.f2_01", "ssn2": "P2.f2_02"}
    for k, box in enumerate("ABCGHI"):
        s[f"box{box}"] = f"P1.c1_1[{k}]=/{k + 1}"
    for k, box in enumerate("DEFJKL"):
        s[f"box{box}"] = f"P2.c2_1[{k}]=/{k + 1}"
    for part, pg, tbl in ((1, 1, "Table_Line1_Part1"), (2, 2, "Table_Line1_Part2")):
        for r in range(11):
            for j, c in enumerate("abcdefgh"):
                s[f"p{part}r{r}{c}"] = f"P{pg}.{tbl}.Row{r + 1}.f{pg}_{3 + 8 * r + j:02d}"
        for j, c in enumerate("defgh"):
            s[f"p{part}tot{c}"] = f"P{pg}.f{pg}_{91 + j}"
    return s


def spec_sse():
    return {"name": "P1.f1_1", "ssn": "P1.f1_2", "L2": "P1.f1_5", "L3": "P1.f1_6", "L4a": "P1.f1_7", "L4c": "P1.f1_9",
            "L6": "P1.f1_12", "L7": "P1.f1_13", "L8a": "P1.Line8a_ReadOrder.f1_14", "L8d": "P1.f1_17", "L9": "P1.f1_18",
            "L10": "P1.f1_19", "L11": "P1.f1_20", "L12": "P1.f1_21", "L13": "P1.f1_22"}


def spec_s8812():
    return {"name": "P1.f1_1", "ssn": "P1.f1_2", "L1": "P1.f1_3", "L2d": "P1.f1_7", "L3": "P1.f1_8", "L4": "P1.f1_9",
            "L5": "P1.f1_10", "L6": "P1.Line6ReadOrder.f1_11", "L7": "P1.f1_12", "L8": "P1.f1_13", "L9": "P1.f1_14",
            "L10": "P1.f1_15", "L11": "P1.f1_16", "L12_no": "P1.c1_1[0]=/1", "L12_yes": "P1.c1_1[1]=/2",
            "L12": "P1.f1_17", "L13": "P1.f1_18", "L14": "P1.f1_19",
            "L16a": "P2.f2_2", "L16b_n": "P2.f2_3", "L16b": "P2.f2_4", "L17": "P2.f2_5", "L18a": "P2.f2_6",
            "L19_no": "P2.c2_1[0]=/1", "L19_yes": "P2.c2_1[1]=/2", "L19": "P2.f2_8", "L20": "P2.f2_9",
            "L20_no": "P2.c2_2[0]=/1", "L20_yes": "P2.c2_2[1]=/2", "L21": "P2.f2_10", "L22": "P2.f2_11",
            "L23": "P2.f2_12", "L24": "P2.f2_13", "L25": "P2.f2_14", "L26": "P2.f2_15", "L27": "P2.f2_16"}


def spec_sei():
    s = {"name": "P1.f1_01", "ssn": "P1.f1_02"}
    for i in range(3):
        s[f"c{i}_name"] = f"P1.f1_{3 + i:02d}"
        s[f"c{i}_ssn"] = f"P1.f1_{6 + i:02d}"
        s[f"c{i}_rel"] = f"P1.f1_{21 + i}"
        yr = ["P1.Year1_ReadOrder.f1_{:02d}", "P1.Year2_ReadOrder.f1_{:02d}", "P1.f1_{:02d}"][i]
        for d in range(4):
            s[f"c{i}_y{d}"] = yr.format(9 + 4 * i + d)
    s["c0_months"] = "P1.Line6_Child1_ReadOrder.f1_24"
    s["c1_months"] = "P1.Line6_Child2_ReadOrder.f1_25"
    s["c2_months"] = "P1.f1_26"
    s.update({
        "c0_4a_yes": "P1.Line4a_Child1_ReadOrder.Yes_ReadOrder.c1_1=/1", "c0_4a_no": "P1.Line4a_Child1_ReadOrder.c1_1=/2",
        "c1_4a_yes": "P1.Line4a_Child2_ReadOrder.Yes_ReadOrder.c1_2=/1", "c1_4a_no": "P1.Line4a_Child2_ReadOrder.c1_2=/2",
        "c2_4a_yes": "P1.Line4a_Child3_Yes_ReadOrder.c1_3=/1", "c2_4a_no": "P1.c1_3=/2",
        "c0_4b_yes": "P1.Line4b_Child1_ReadOrder.Yes_ReadOrder.c1_4=/1", "c0_4b_no": "P1.Line4b_Child1_ReadOrder.c1_4=/2",
        "c1_4b_yes": "P1.Line4b_Child2_ReadOrder.Yes_ReadOrder.c1_5=/1", "c1_4b_no": "P1.Line4b_Child2_ReadOrder.c1_5=/2",
        "c2_4b_yes": "P1.Line4b_Child3_Yes_ReadOrder.c1_6=/1", "c2_4b_no": "P1.c1_6=/2",
    })
    return s


def spec_2441():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2"}
    for i in range(3):
        row = f"P1.PartITable.BodyRow{i + 1}."
        s[f"prov{i}_name"] = row + f"f1_{3 + 4 * i}"
        s[f"prov{i}_addr"] = row + f"ColB.f1_{4 + 4 * i}"
        s[f"prov{i}_tin"] = row + f"f1_{5 + 4 * i}"
        s[f"prov{i}_hh_yes"] = row + f"ColD.c1_{4 + i}[0]=/1"
        s[f"prov{i}_hh_no"] = row + f"ColD.c1_{4 + i}[1]=/2"
        s[f"prov{i}_amt"] = row + f"f1_{6 + 4 * i}"
        row = f"P1.Table_Line2.Row{i + 1}."
        s[f"q{i}_first"] = row + f"f1_{15 + 4 * i}"
        s[f"q{i}_last"] = row + f"f1_{16 + 4 * i}"
        s[f"q{i}_ssn"] = row + f"f1_{17 + 4 * i}"
        s[f"q{i}_disabled"] = row + f"c1_{8 + i}=/1"
        s[f"q{i}_exp"] = row + f"f1_{18 + 4 * i}"
    for k, n in zip(["L3", "L4", "L5", "L6", "L7", "L8", "L9a", "L9b", "L9c", "L10", "L11"], range(27, 38)):
        s[k] = f"P1.f1_{n}"
    for k, n in zip(["L12", "L13", "L14", "L15"], range(1, 5)):
        s[k] = f"P2.f2_{n}"
    s["L16"] = "P2.Line16_ReadOrder.f2_5"
    for k, n in zip(["L17", "L18", "L19", "L20", "L21"], range(6, 11)):
        s[k] = f"P2.f2_{n}"
    s["L22_no"] = "P2.c2_1[0]=/1"
    s["L22_yes"] = "P2.c2_1[1]=/2"
    for k, n in zip(["L22", "L23", "L24", "L25", "L26", "L27", "L28", "L29", "L30", "L31"], range(11, 21)):
        s[k] = f"P2.f2_{n}"
    return s


def spec_8863():
    s = {"name": "P1.f1_1", "ssn_a": "P1.SocialSecurity.f1_2", "ssn_b": "P1.SocialSecurity.f1_3",
         "ssn_c": "P1.SocialSecurity.f1_4", "name2": "P2.f2_1", "ssn2_a": "P2.SSN.f2_2", "ssn2_b": "P2.SSN.f2_3",
         "ssn2_c": "P2.SSN.f2_4"}
    for k, n in zip(["L1", "L2", "L3", "L4", "L5", "L6_int", "L6_dec"], range(5, 12)):
        s[k] = f"P1.f1_{n}"
    s["L7_under24"] = "P1.c1_1=/1"
    for k, n in zip(["L7", "L8", "L9", "L10", "L11", "L12", "L13", "L14", "L15", "L16", "L17_int", "L17_dec",
                     "L18", "L19"], range(12, 26)):
        s[k] = f"P1.f1_{n}"
    s.update({
        "L20": "P2.f2-5", "L21_a": "P2.StudentSSN.f2_6", "L21_b": "P2.StudentSSN.f2_7", "L21_c": "P2.StudentSSN.f2_8",
        "L22a_name": "P2.Line22a.f2_9", "L22a_addr": "P2.Line22a.f2_10",
        "L22a_1098_yes": "P2.Line22a.c2_1[0]=/Yes", "L22a_1098_no": "P2.Line22a.c2_1[1]=/No",
        "L22a_prev_yes": "P2.Line22a.c2_2[0]=/Yes", "L22a_prev_no": "P2.Line22a.c2_2[1]=/No",
        "L23_yes": "P2.c2_5[0]=/Yes", "L23_no": "P2.c2_5[1]=/No", "L24_yes": "P2.c2_6[0]=/Yes", "L24_no": "P2.c2_6[1]=/No",
        "L25_yes": "P2.c2_7[0]=/Yes", "L25_no": "P2.c2_7[1]=/No", "L26_yes": "P2.c2_8[0]=/Yes", "L26_no": "P2.c2_8[1]=/No",
        "L27": "P2.f2_31", "L28": "P2.f2_32", "L29": "P2.f2_33", "L30": "P2.f2_34", "L31": "P2.f2_35",
    })
    for d in range(9):
        s[f"L22a_ein{d}"] = f"P2.Line22a.f2_{11 + d}"
    return s


def spec_8880():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2"}
    for line in range(1, 7):
        s[f"L{line}a"] = f"P1.Table_Ln1-6.BodyRow{line}.f1_{1 + 2 * line}"
        s[f"L{line}b"] = f"P1.Table_Ln1-6.BodyRow{line}.f1_{2 + 2 * line}"
    for k, n in zip(["L7", "L8", "L9", "L10", "L11", "L12"], range(15, 21)):
        s[k] = f"P1.f1_{n}"
    return s


def spec_8889():
    return {"name": "P1.f1_1", "ssn": "P1.f1_2", "cov_self": "P1.c1_1[0]=/1", "cov_family": "P1.c1_1[1]=/2",
            "L2": "P1.f1_3", "L3": "P1.f1_4", "L5": "P1.f1_6", "L6": "P1.f1_7", "L7": "P1.f1_8", "L8": "P1.f1_9",
            "L9": "P1.f1_10", "L11": "P1.f1_12", "L12": "P1.f1_13", "L13": "P1.f1_14"}


def spec_8995():
    s = {"name": "P1.f1_01", "ssn": "P1.f1_02"}
    for i, r in enumerate(["i", "ii", "iii", "iv", "v"]):
        s[f"b{i}_name"] = f"P1.Table.Row1{r}.f1_{3 + 3 * i:02d}"
        s[f"b{i}_tin"] = f"P1.Table.Row1{r}.f1_{4 + 3 * i:02d}"
        s[f"b{i}_qbi"] = f"P1.Table.Row1{r}.f1_{5 + 3 * i:02d}"
    s["L2"] = "P1.Line2_ReadOrder.f1_18"
    for k, n in zip(["L3", "L4", "L5"], range(19, 22)):
        s[k] = f"P1.f1_{n}"
    for k, n in zip(["L10", "L11", "L12", "L13", "L14", "L15"], range(26, 32)):
        s[k] = f"P1.f1_{n}"
    return s


def spec_6251():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2", "L1a": "P1.f1_3", "L1b": "P1.f1_4", "L2a": "P1.f1_5", "L4": "P1.f1_26"}
    for k, n in zip(["L5", "L6", "L7", "L8", "L9", "L10", "L11"], range(27, 34)):
        s[k] = f"P1.f1_{n}"
    return s


def spec_8959():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2"}
    for k, n in zip(["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12", "L13"], range(3, 16)):
        s[k] = f"P1.f1_{n}"
    for k, n in zip(["L18", "L19", "L20", "L21", "L22", "L23", "L24"], range(20, 27)):
        s[k] = f"P1.f1_{n}"
    return s


def spec_8960():
    s = {"name": "P1.f1_1", "ssn": "P1.f1_2", "L1": "P1.f1_3", "L2": "P1.f1_4", "L5a": "P1.f1_9", "L5d": "P1.f1_12",
         "L8": "P1.f1_15", "L11": "P1.f1_21"}
    for k, n in zip(["L12", "L13", "L14", "L15", "L16", "L17"], range(22, 28)):
        s[k] = f"P1.f1_{n}"
    return s


def spec_1040v():
    return {"ssn": "P1.f1_1", "sp_ssn": "P1.f1_2", "amount": "P1.f1_3", "first": "P1.f1_5", "last": "P1.f1_6",
            "sp_first": "P1.f1_7", "sp_last": "P1.f1_8", "street": "P1.f1_9", "apt": "P1.f1_10", "city": "P1.f1_11",
            "state": "P1.f1_12", "zip": "P1.f1_13"}


SPECS = {"1040": spec_1040, "s1": spec_s1, "s1a": spec_s1a, "s2": spec_s2, "s3": spec_s3, "sa": spec_sa, "sb": spec_sb,
         "sc": spec_sc, "sd": spec_sd, "8949": spec_8949, "sse": spec_sse, "s8812": spec_s8812, "sei": spec_sei,
         "2441": spec_2441, "8863": spec_8863, "8880": spec_8880, "8889": spec_8889, "8995": spec_8995,
         "6251": spec_6251, "8959": spec_8959, "8960": spec_8960, "1040v": spec_1040v}


# ------------------------------------------------------------------------------------------------- utilidades
def expand(root, short):
    path, _, state = short.partition("=")
    segs = []
    for seg in path.split("."):
        if seg.startswith("P") and seg[1:].isdigit():
            seg = "Page" + seg[1:]
        if "[" not in seg:
            seg += "[0]"
        segs.append(seg)
    return f"{root}[0]." + ".".join(segs), state


def pdf_fields(pdf):
    """{nombre completo: (tipo, [estados], maxlen, página)} leyendo los widgets de cada página."""
    import pypdf
    r = pypdf.PdfReader(str(pdf))
    out = {}
    for pi, page in enumerate(r.pages):
        for a in page.get("/Annots") or []:
            a = a.get_object()
            if a.get("/Subtype") != "/Widget":
                continue
            names, node = [], a
            while node is not None:
                if "/T" in node:
                    names.append(str(node["/T"]))
                node = node.get("/Parent")
                node = node.get_object() if node is not None else None
            full = ".".join(reversed(names))
            par = a.get("/Parent").get_object() if a.get("/Parent") else {}
            ft = a.get("/FT") or par.get("/FT")
            states = []
            ap = a.get("/AP")
            if ap and "/N" in ap:
                try:
                    states = [k for k in ap["/N"].keys() if k != "/Off"]
                except AttributeError:
                    states = []
            ml = a.get("/MaxLen") or par.get("/MaxLen")
            out[full] = (str(ft), states, int(ml) if ml else None, pi)
    return out


def build(year):
    src = ROOT / "data" / "formularios" / str(year)
    result = {"year": year, "forms": {}}
    errors = []
    for fid, (fname, root, seq, title_es, title_en) in FORMS.items():
        pdf = src / fname
        if not pdf.exists():
            errors.append(f"falta {pdf}")
            continue
        fields = pdf_fields(pdf)
        if fid == "1040sr":
            continue
        mapping = {}
        for key, short in SPECS[fid]().items():
            full, state = expand(root, short)
            if full not in fields:
                errors.append(f"{fid}.{key}: no existe {full}")
                continue
            ft, states, ml, _pg = fields[full]
            if state:
                if ft != "/Btn" or state not in states:
                    errors.append(f"{fid}.{key}: estado {state} no está en {states} ({full})")
                mapping[key] = [full, state]
            else:
                if ft != "/Tx":
                    errors.append(f"{fid}.{key}: {full} no es texto ({ft})")
                mapping[key] = [full, None, ml] if ml else full
        result["forms"][fid] = {"file": fname, "seq": seq, "title": [title_es, title_en],
                                "pages": len({p for (_t, _s, _m, p) in fields.values()}), "fields": mapping}
    # 1040-SR: mismo orden de campos que el 1040 (verificado comparando el texto descriptivo de cada campo).
    f1040 = list(pdf_fields(src / "f1040.pdf").keys())
    fsr = list(pdf_fields(src / "f1040s.pdf").keys())
    pos = {name: i for i, name in enumerate(f1040)}
    sr_map = {}
    for key, val in result["forms"]["1040"]["fields"].items():
        full = val[0] if isinstance(val, list) else val
        other = fsr[pos[full]]
        if isinstance(val, list):
            sr_map[key] = [other] + val[1:]
        else:
            sr_map[key] = other
    fname, root, seq, te, tn = FORMS["1040sr"]
    result["forms"]["1040sr"] = {"file": fname, "seq": seq, "title": [te, tn], "pages": 4, "fields": sr_map}
    # Versiones en español: se alinean campo por campo con la versión en inglés (mismo tipo, estados y largo).
    for fid, es_file in SPANISH.items():
        es_pdf = src / "es" / es_file
        if fid not in result["forms"] or not es_pdf.exists():
            continue
        en = result["forms"][fid]
        es_map, es_errs, n_pages = align_variant(src / en["file"], es_pdf, en["fields"])
        if es_errs:
            errors += [f"{fid} (es): {e}" for e in es_errs]
            continue
        en["es"] = {"file": "es/" + es_file, "pages": n_pages, "fields": es_map}
    # orden de presentación
    result["forms"] = {k: result["forms"][k] for k in FORMS if k in result["forms"]}
    return result, errors


def _signature(info):
    ft, states, ml, page = info
    return (ft, len(states) if ft == "/Btn" else 0, ml)


def align_variant(en_pdf, var_pdf, mapping):
    """Mapea las claves de un formulario a otra edición del mismo formulario (p. ej. la versión en español),
    alineando la secuencia de campos por tipo, estados de casilla, largo máximo y página."""
    import difflib
    import pypdf
    en = pdf_fields(en_pdf)
    va = pdf_fields(var_pdf)
    en_names, va_names = list(en), list(va)
    a = [_signature(en[n]) for n in en_names]
    b = [_signature(va[n]) for n in va_names]
    pos = {}
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                if a[i1 + k][0] == b[j1 + k][0]:
                    pos[en_names[i1 + k]] = va_names[j1 + k]
    out, errs = {}, []
    for key, val in mapping.items():
        full = val[0] if isinstance(val, list) else val
        other = pos.get(full)
        if not other:
            errs.append(f"{key}: sin campo equivalente para {full}")
            continue
        if isinstance(val, list) and val[1] and val[1] not in va[other][1]:
            if len(va[other][1]) == 1:   # misma casilla con otro nombre de estado (p. ej. /Yes -> /Si)
                out[key] = [other, va[other][1][0]] + val[2:]
                continue
            errs.append(f"{key}: el estado {val[1]} no existe en {other} ({va[other][1]})")
            continue
        out[key] = [other] + val[1:] if isinstance(val, list) else other
    return out, errs, len(pypdf.PdfReader(str(var_pdf)).pages)


def dump(year):
    src = ROOT / "data" / "formularios" / str(year)
    for fid, (fname, *_r) in FORMS.items():
        print(f"===== {fid} ({fname})")
        for name, (ft, states, ml, pg) in pdf_fields(src / fname).items():
            print(f"  p{pg + 1} {name} {ft} {','.join(states)} {ml or ''}")


if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    if "--volcar" in sys.argv:
        dump(yr)
        sys.exit(0)
    data, errs = build(yr)
    for e in errs:
        print("ERROR", e)
    if errs:
        sys.exit(1)
    out = ROOT / "data" / "formularios" / f"{yr}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(f["fields"]) for f in data["forms"].values())
    print(f"OK {out} ({len(data['forms'])} formularios, {n} campos)")
