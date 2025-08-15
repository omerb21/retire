from datetime import date
from typing import Tuple
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
# נעדיף להשתמש בלוגיקת ההצמדה הקיימת בפרויקט אם ישנה:
# from app.services.indexation import compute_indexation_factor
# אם אין, נגדיר פקטור בסיסי כאן.

def _compute_indexation_factor(method: str, start: date | None, fixed_rate: float | None, today: date | None = None) -> float:
    if method == "none":
        return 1.0
    if method == "fixed":
        # הצמדה לינארית/אקספוננציאלית שנתית לפי הצורך; כאן בסיסית: (1 + r)
        return 1.0 + (fixed_rate or 0.0)
    if method == "cpi":
        # אם יש compute_indexation_factor קיים – להשתמש בו.
        # כאן ברירת מחדל ניטרלית אם אין נתונים.
        return 1.0
    return 1.0

def calculate_pension_amount(fund: PensionFund) -> float:
    if fund.input_mode == "manual":
        return float(fund.pension_amount or 0.0)
    # calculated
    bal = float(fund.balance or 0.0)
    af = float(fund.annuity_factor or 0.0)
    if af <= 0:
        return 0.0
    return bal / af

def compute_and_apply_indexation(fund: PensionFund) -> Tuple[float, float]:
    base_amount = calculate_pension_amount(fund)
    factor = _compute_indexation_factor(
        method=fund.indexation_method,
        start=fund.pension_start_date,
        fixed_rate=fund.fixed_index_rate,
    )
    indexed = base_amount * factor
    return base_amount, indexed

def compute_and_persist(db: Session, fund: PensionFund) -> PensionFund:
    base, indexed = compute_and_apply_indexation(fund)
    fund.pension_amount = base
    fund.indexed_pension_amount = indexed
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund
