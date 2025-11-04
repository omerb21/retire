"""
Base scenario builder for retirement scenarios
מחלקת בסיס לבניית תרחישי פרישה
"""
import logging
from typing import Dict, List, Optional
from datetime import date
from sqlalchemy.orm import Session
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from .constants import DEFAULT_DISCOUNT_RATE, MAX_AGE_FOR_NPV
from .services.state_service import StateService
from .services.portfolio_import_service import PortfolioImportService
from .services.conversion_service import ConversionService
from .services.termination_service import TerminationService
from .utils.calculation_utils import calculate_npv_dcf, calculate_years_to_age

logger = logging.getLogger("app.scenarios.base")


class BaseScenarioBuilder:
    """מחלקת בסיס לבניית תרחישי פרישה"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        pension_portfolio: Optional[List[Dict]] = None
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.pension_portfolio = pension_portfolio or []
        self.actions = []  # רשימת כל הפעולות שבוצעו בתרחיש
        
        # טעינת לקוח
        self.client = db.query(Client).filter(Client.id == client_id).first()
        if not self.client:
            raise ValueError(f"לקוח {client_id} לא נמצא")
        
        # אתחול שירותים
        self.state_service = StateService(db, client_id)
        self.portfolio_service = PortfolioImportService(db, client_id, self._add_action)
        self.conversion_service = ConversionService(
            db, client_id, self._get_retirement_year(), self._add_action
        )
        self.termination_service = TerminationService(
            db, client_id, retirement_age, self._add_action
        )
    
    def _add_action(
        self,
        action_type: str,
        details: str,
        from_asset: str = "",
        to_asset: str = "",
        amount: float = 0
    ):
        """מוסיף פעולה לרשימת הפעולות"""
        self.actions.append({
            "type": action_type,
            "details": details,
            "from": from_asset,
            "to": to_asset,
            "amount": amount
        })
    
    def _get_retirement_year(self) -> int:
        """מחשב שנת פרישה על בסיס גיל הפרישה"""
        if not self.client.birth_date:
            raise ValueError("תאריך לידה חסר")
        return self.client.birth_date.year + self.retirement_age
    
    def _get_retirement_age(self) -> int:
        """מחזיר את גיל הפרישה"""
        return self.retirement_age
    
    def _import_pension_portfolio_if_needed(self):
        """ייבוא תיק פנסיוני אם קיים"""
        if self.pension_portfolio:
            self.portfolio_service.import_pension_portfolio(self.pension_portfolio)
    
    def _calculate_scenario_results(self, scenario_name: str) -> Dict:
        """מחשב NPV ומחזיר את תוצאות התרחיש"""
        # Get current state
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        
        additional_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id
        ).all()
        
        # Calculate totals
        total_pension = sum(pf.pension_amount or 0 for pf in pension_funds)
        # ✅ תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
        total_capital_monthly = sum(float(ca.monthly_income or 0) for ca in capital_assets)
        
        # ✅ תוקן: חישוב הכנסות נוספות לפי תדירות
        total_additional = 0
        for ai in additional_incomes:
            if ai.frequency == "monthly":
                total_additional += float(ai.amount)
            elif ai.frequency == "quarterly":
                total_additional += float(ai.amount) / 3  # ממוצע חודשי
            elif ai.frequency == "annually":
                total_additional += float(ai.amount) / 12  # ממוצע חודשי
            else:
                total_additional += float(ai.amount)  # ברירת מחדל
        
        # חישוב NPV תקין באמצעות DCF
        years_to_90 = calculate_years_to_age(self.client, self.retirement_age, MAX_AGE_FOR_NPV)
        
        # נכסי הון הם תשלום חודשי, לא הון חד-פעמי
        npv = calculate_npv_dcf(
            monthly_pension=total_pension,
            monthly_additional=total_additional + total_capital_monthly,  # ✅ נכסי הון = תשלום חודשי
            capital=0,  # ✅ אין הון חד-פעמי
            years=years_to_90,
            discount_rate=DEFAULT_DISCOUNT_RATE
        )
        
        logger.info(f"  📊 {scenario_name} Results:")
        logger.info(f"     Total Pension: {total_pension} ₪/month")
        logger.info(f"     Total Capital (monthly): {total_capital_monthly} ₪/month")
        logger.info(f"     Total Additional: {total_additional} ₪/month")
        logger.info(f"     Estimated NPV (DCF): {npv} ₪")
        
        return {
            "scenario_name": scenario_name,
            "total_pension_monthly": total_pension,
            "total_capital": total_capital_monthly,  # ✅ תוקן: נכסי הון = תשלום חודשי
            "total_additional_income_monthly": total_additional,
            "estimated_npv": npv,
            "pension_funds_count": len(pension_funds),
            "capital_assets_count": len(capital_assets),
            "additional_incomes_count": len(additional_incomes),
            "execution_plan": self.actions  # מפרט ביצוע מפורט
        }
    
    def build_scenario(self) -> Dict:
        """מתודה מופשטת לבניית תרחיש - יש לממש במחלקות היורשות"""
        raise NotImplementedError("Subclasses must implement build_scenario()")
