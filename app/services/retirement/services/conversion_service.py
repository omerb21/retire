"""
Conversion service for retirement scenarios
שירות המרות לתרחישי פרישה
"""
import logging
from typing import Optional, Callable
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.fixation_result import FixationResult
from app.models.additional_income import AdditionalIncome
from ..utils.pension_utils import (
    convert_balance_to_pension,
    convert_capital_to_pension,
    convert_education_fund_to_pension,
    convert_education_fund_to_capital
)

logger = logging.getLogger("app.scenarios.conversion")


class ConversionService:
    """שירות המרות בין סוגי נכסים"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_year: int,
        add_action_callback: Optional[Callable] = None
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_year = retirement_year
        self.add_action = add_action_callback
    
    def convert_all_pension_funds_to_pension(self) -> None:
        """המרת כל המוצרים הפנסיוניים לקצבה (למעט קרנות השתלמות)"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for pf in pension_funds:
            if pf.balance and pf.annuity_factor and not pf.pension_amount:
                convert_balance_to_pension(pf, self.retirement_year, self.add_action)
            elif pf.pension_amount:
                # קצבה שכבר הוגדרה
                tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
                if self.add_action:
                    self.add_action(
                        "use_existing",
                        f"שימוש בקצבה קיימת: {pf.fund_name} ({tax_status})",
                        from_asset="",
                        to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                        amount=0
                    )
        
        self.db.flush()
    
    def convert_taxable_capital_to_pension(self) -> None:
        """המרת נכסים הוניים חייבים במס לקצבה"""
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id,
            CapitalAsset.tax_treatment == "taxable"
        ).all()
        
        for ca in capital_assets:
            pf = convert_capital_to_pension(
                ca,
                self.client_id,
                self.retirement_year,
                self.db,
                self.add_action
            )
            self.db.add(pf)
            self.db.delete(ca)
        
        self.db.flush()
    
    def convert_exempt_capital_to_pension(self) -> None:
        """המרת נכסים הוניים פטורים לקצבה פטורה"""
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id,
            CapitalAsset.tax_treatment == "exempt"
        ).all()
        
        for ca in capital_assets:
            pf = convert_capital_to_pension(
                ca,
                self.client_id,
                self.retirement_year,
                self.db,
                self.add_action
            )
            self.db.add(pf)
            self.db.delete(ca)
        
        self.db.flush()
    
    def convert_education_funds_to_pension(self) -> None:
        """המרת קרנות השתלמות לקצבה פטורה"""
        education_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            PensionFund.tax_treatment == "exempt",
            PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for ef in education_funds:
            convert_education_fund_to_pension(ef, self.retirement_year, self.add_action)
        
        self.db.flush()
    
    def convert_education_funds_to_capital(self) -> None:
        """המרת קרנות השתלמות להון פטור"""
        education_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            PensionFund.tax_treatment == "exempt",
            PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for ef in education_funds:
            ca = convert_education_fund_to_capital(
                ef,
                self.client_id,
                self.retirement_year,
                self.add_action
            )
            if ca:
                self.db.add(ca)
                self.db.delete(ef)
        
        self.db.flush()
    
    def verify_fixation_and_exempt_pension(self) -> None:
        """וידוא קיום קיבוע זכויות וקצבה פטורה"""
        # Check for fixation result
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).first()
        
        if not fixation:
            logger.warning("  ⚠️ No fixation result found for client")
        else:
            logger.info("  ✅ Fixation result exists")
        
        # Check for exempt pension in additional income
        exempt_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id,
            AdditionalIncome.tax_treatment == "exempt"
        ).all()
        
        if not exempt_incomes:
            logger.warning("  ⚠️ No exempt pension income found")
        else:
            logger.info(f"  ✅ Found {len(exempt_incomes)} exempt income sources")
