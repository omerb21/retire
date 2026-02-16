from __future__ import annotations


def compute_termination_amounts_ssot(*, formula_total: float | None, accrued_total: float | None, exempt_amount: float | None) -> dict:
    try:
        formula_val = float(formula_total or 0)
    except Exception:
        formula_val = 0.0

    try:
        accrued_val = float(accrued_total or 0)
    except Exception:
        accrued_val = 0.0

    try:
        exempt_val = float(exempt_amount or 0)
    except Exception:
        exempt_val = 0.0

    severance_total = max(formula_val, accrued_val)
    taxable_amount = max(0.0, severance_total - exempt_val)

    return {
        "severance_total": severance_total,
        "exempt_amount": exempt_val,
        "taxable_amount": taxable_amount,
    }
