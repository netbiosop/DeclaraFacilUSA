"""A dónde enviar el Formulario 1040 en papel / Where to mail a paper Form 1040.

Fuente: IRS, "Where to file paper tax returns with or without a payment" (Form 1040 / 1040-SR), consultado en
octubre de 2026 para declaraciones de 2025. El IRS cambia estas direcciones de vez en cuando: la aplicación muestra
el enlace oficial para confirmarla antes de enviar.
"""
from __future__ import annotations

from typing import Dict, List

WHERE_TO_FILE_URL = "https://www.irs.gov/filing/where-to-file-paper-tax-returns-with-or-without-a-payment"

_GROUPS = {
    "south": ("AL", "FL", "GA", "LA", "MS", "NC", "SC", "TN", "TX"),
    "east": ("CT", "DE", "DC", "IL", "IN", "IA", "KY", "ME", "MD", "MA", "MN", "MO", "NH", "NJ", "NY", "PA", "RI", "VT",
             "VA", "WV", "WI"),
    "west": ("AK", "CA", "CO", "HI", "ID", "KS", "MI", "MT", "NE", "NV", "OH", "OR", "ND", "SD", "UT", "WA", "WY"),
    "southwest": ("AR", "AZ", "NM", "OK"),
}
_NO_PAY = {
    "south": ["Department of the Treasury", "Internal Revenue Service", "Austin, TX 73301-0002"],
    "east": ["Department of the Treasury", "Internal Revenue Service", "Kansas City, MO 64999-0002"],
    "west": ["Department of the Treasury", "Internal Revenue Service", "Ogden, UT 84201-0002"],
    "southwest": ["Department of the Treasury", "Internal Revenue Service", "Austin, TX 73301-0002"],
    "abroad": ["Department of the Treasury", "Internal Revenue Service", "Austin, TX 73301-0215", "USA"],
}
_PAY = {
    "south": ["Internal Revenue Service", "P.O. Box 1214", "Charlotte, NC 28201-1214"],
    "east": ["Internal Revenue Service", "P.O. Box 931000", "Louisville, KY 40293-1000"],
    "west": ["Internal Revenue Service", "P.O. Box 931000", "Louisville, KY 40293-1000"],
    "southwest": ["Internal Revenue Service", "P.O. Box 931000", "Louisville, KY 40293-1000"],
    "abroad": ["Internal Revenue Service", "P.O. Box 1303", "Charlotte, NC 28201-1303", "USA"],
}


def group_for(state: str) -> str:
    st = (state or "").upper().strip()
    for g, states in _GROUPS.items():
        if st in states:
            return g
    return "abroad"   # territorios, APO/FPO, extranjero o sin estado


def irs_address(state: str, with_payment: bool) -> List[str]:
    g = group_for(state)
    return list((_PAY if with_payment else _NO_PAY)[g])


def mailing_info(state: str, owed: float) -> Dict[str, object]:
    pay = owed >= 1  # el IRS no cobra saldos menores de $1
    return {"group": group_for(state), "with_payment": pay, "address": irs_address(state, pay), "url": WHERE_TO_FILE_URL}
