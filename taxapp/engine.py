"""Punto de entrada del calculo: federal + estatal + local."""
from __future__ import annotations

from .federal import compute_federal
from .local import compute_local
from .models import TaxReturn
from .i18n import tr, _
from .state import compute_state


def compute_all(ret: TaxReturn) -> dict:
    fed = compute_federal(ret)
    st = compute_state(ret, fed)
    loc = compute_local(ret, fed, st)
    total_balance = fed["balance"] + st["balance"] + loc["balance"]
    return {
        "federal": fed,
        "state": st,
        "local": loc,
        "summary": {
            "federal_balance": fed["balance"],
            "state_balance": st["balance"],
            "local_balance": loc["balance"],
            "total_balance": total_balance,
            "total_tax": fed["total_tax"] + st["tax"] + loc["total"],
        },
    }


def fmt_money(v: float, signed: bool = False) -> str:
    if v is None:
        return "$0"
    s = f"${abs(v):,.2f}"
    if v < 0:
        return f"-{s}"
    return f"+{s}" if signed and v > 0 else s


def balance_text(balance: float) -> str:
    if balance >= 0.005:
        return tr("Reembolso {m}", m=fmt_money(balance))
    if balance <= -0.005:
        return tr("A pagar {m}", m=fmt_money(-balance))
    return _("Saldo $0.00")
