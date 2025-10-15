from datetime import date
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.calculation.indexation import index_factor, index_amount
from app.providers.tax_params import TaxParamsProvider

def _full_years_between(start: date, end: date) -> int:
    """Calculate complete years between two dates"""
    # שנות ותק מלאות (בלי לשבור על חודשים/ימים)
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(0, years)

def _compute_indexation_factor(method: str | None, start: date | None, fixed_rate: float | None, today: date | None = None) -> float:
    """Compute indexation factor based on method, start date, and fixed rate"""
    m = (method or "none").lower()
    
    if m == "none":
        return 1.0
        
    if m == "fixed":
        r = float(fixed_rate or 0.0)
        # אם יש תאריך התחלה – הצמדה שנתית בחזקה; אם אין – הצמדה חד-פעמית
        if start:
            t = today or date.today()
            years = _full_years_between(start, t)
            return (1.0 + r) ** years if years > 0 else 1.0
        return 1.0 + r
    
    if m == "cpi" and start:
        # Use the existing CPI indexation from the calculation module
        try:
            current_date = today or date.today()
            # Get tax parameters for CPI data
            tax_provider = TaxParamsProvider()
            params = tax_provider.get_params()
            return index_factor(params, start, current_date)
        except Exception:
            # Fallback if CPI data is not available
            return 1.0
            
    return 1.0

def calculate_pension_amount(fund: PensionFund) -> float:
    """Calculate the base pension amount based on input mode"""
    if fund.input_mode == "manual":
        return float(fund.pension_amount or 0.0)
    
    # For calculated mode, use balance and annuity factor
    bal = float(fund.balance or 0.0)
    af = float(fund.annuity_factor or 0.0)
    
    if af <= 0:
        return 0.0
        
    # Round to 2 decimal places for currency
    return round(bal / af, 2)

def _compute_base_pension(fund: PensionFund) -> float:
    """Calculate the base pension amount based on input mode"""
    if fund.input_mode == "calculated":
        if not fund.annuity_factor or fund.annuity_factor <= 0:
            raise ValueError("annuity_factor must be positive for calculated mode")
        return float(fund.balance or 0.0) / float(fund.annuity_factor)
    return float(fund.pension_amount or 0.0)

def compute_and_persist_fund(db: Session, fund_id: int) -> PensionFund:
    """Compute pension amounts and persist to database"""
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise ValueError(f"PensionFund {fund_id} not found")

    print(f"🔵 BEFORE COMPUTE: fund_id={fund_id}, balance={fund.balance}, input_mode={fund.input_mode}")

    # Calculate base pension amount
    base = _compute_base_pension(fund)
    
    # Apply indexation factor
    factor = _compute_indexation_factor(
        method=fund.indexation_method,
        start=fund.pension_start_date,
        fixed_rate=fund.fixed_index_rate
    )
    
    # Apply indexation and round to 2 decimal places
    indexed = base * factor

    fund.pension_amount = round(base, 2)
    fund.indexed_pension_amount = round(indexed, 2)
    
    # אל תאפס את ה-balance! אנחנו צריכים אותו להיוון
    # ה-balance מייצג את היתרה המקורית שעליה מבוססת הקצבה
    print(f"🟢 AFTER COMPUTE: fund_id={fund_id}, balance={fund.balance}, pension_amount={fund.pension_amount}")

    db.add(fund)
    db.commit()
    db.refresh(fund)
    
    print(f"🟣 AFTER REFRESH: fund_id={fund_id}, balance={fund.balance}")
    
    return fund

# For compatibility with existing code
def compute_and_apply_indexation(fund: PensionFund, reference_date: Optional[date] = None) -> Tuple[float, float]:
    """Compute base pension amount and apply indexation"""
    # Calculate base pension amount
    base_amount = _compute_base_pension(fund)
    
    # Apply indexation factor
    factor = _compute_indexation_factor(
        method=fund.indexation_method,
        start=fund.pension_start_date,
        fixed_rate=fund.fixed_index_rate,
        today=reference_date
    )
    
    # Apply indexation and round to 2 decimal places
    indexed = round(base_amount * factor, 2)
    
    return base_amount, indexed

def compute_and_persist(db: Session, fund: PensionFund, reference_date: Optional[date] = None) -> PensionFund:
    """Compute pension amounts and persist to database"""
    # Calculate base and indexed pension amounts
    base, indexed = compute_and_apply_indexation(fund, reference_date)
    
    # Update fund with calculated values
    fund.pension_amount = base
    fund.indexed_pension_amount = indexed
    
    # אל תאפס את ה-balance! אנחנו צריכים אותו להיוון
    # ה-balance מייצג את היתרה המקורית שעליה מבוססת הקצבה
    
    # Persist changes to database
    db.add(fund)
    db.commit()
    db.refresh(fund)
    
    return fund

def compute_all_pension_funds(db: Session, client_id: int) -> list[PensionFund]:
    """Compute all pension funds for a client"""
    # Get all pension funds for the client
    funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
    
    # Compute and persist each fund
    updated_funds = []
    for fund in funds:
        updated_fund = compute_and_persist(db, fund)
        updated_funds.append(updated_fund)
        
    return updated_funds
