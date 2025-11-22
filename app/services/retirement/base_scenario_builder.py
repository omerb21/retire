"""
Base Scenario Builder

כלי בסיס לבניית תרחישי פרישה
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from .services import ConversionService, TerminationService, PortfolioImportService
from .utils.calculation_utils import calculate_npv_dcf, calculate_years_to_age
from .constants import DEFAULT_DISCOUNT_RATE

logger = logging.getLogger("app.scenarios.base")


class BaseScenarioBuilder:
    """Base class for all retirement scenario builders"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        pension_portfolio: Optional[List[Dict]] = None,
        use_current_employer_termination: bool = False,
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.pension_portfolio = pension_portfolio or []
        self.use_current_employer_termination = use_current_employer_termination
        self.scenario_results: Dict = {}
        self.execution_plan: List[Dict] = []
        
        # Cache client and retirement date/year
        self._client: Optional[Client] = (
            self.db.query(Client).filter(Client.id == self.client_id).first()
        )
        self._retirement_date: Optional[date] = None
        self._retirement_year: Optional[int] = None
        
        if self._client and self._client.birth_date:
            try:
                self._retirement_date = date(
                    self._client.birth_date.year + self.retirement_age,
                    self._client.birth_date.month,
                    self._client.birth_date.day,
                )
            except ValueError:
                # טיפול במקרי קצה (למשל 29 בפברואר)
                self._retirement_date = self._client.birth_date.replace(
                    year=self._client.birth_date.year + self.retirement_age,
                    day=min(self._client.birth_date.day, 28),
                )
            self._retirement_year = self._retirement_date.year
        else:
            # ברירת מחדל אם אין תאריך לידה
            self._retirement_year = date.today().year + max(self.retirement_age - 67, 0)
        
        # Shared services for all scenarios
        retirement_year_for_conversion = self._retirement_year or date.today().year
        self.conversion_service = ConversionService(
            self.db,
            self.client_id,
            retirement_year_for_conversion,
            self._add_action,
        )
        self.termination_service = TerminationService(
            self.db,
            self.client_id,
            self.retirement_age,
            self._add_action,
            use_current_employer_termination=self.use_current_employer_termination,
        )
        self.portfolio_import_service = PortfolioImportService(
            self.db,
            self.client_id,
            self.retirement_age,
            self._add_action,
            ignore_current_employer_severance=self.use_current_employer_termination,
        )
    
    def build_scenario(self) -> Dict:
        """Build and return the scenario results
        
        This method must be implemented by all subclasses
        """
        raise NotImplementedError("Subclasses must implement build_scenario()")
    
    def _get_retirement_year(self) -> int:
        """מחשב שנת פרישה עבור גיל הפרישה המבוקש"""
        if self._retirement_year is not None:
            return self._retirement_year
        if self._client and self._client.birth_date:
            return self._client.birth_date.year + self.retirement_age
        return date.today().year + (self.retirement_age or 0)
    
    def _get_retirement_date(self) -> Optional[date]:
        """מחזיר את תאריך הפרישה (אם ניתן לחשב אותו)"""
        if self._retirement_date is not None:
            return self._retirement_date
        if self._client and self._client.birth_date:
            try:
                self._retirement_date = date(
                    self._client.birth_date.year + self.retirement_age,
                    self._client.birth_date.month,
                    self._client.birth_date.day,
                )
            except ValueError:
                self._retirement_date = self._client.birth_date.replace(
                    year=self._client.birth_date.year + self.retirement_age,
                    day=min(self._client.birth_date.day, 28),
                )
            return self._retirement_date
        return None
    
    def _add_action(
        self,
        action_type: str,
        details: str,
        from_asset: str,
        to_asset: str,
        amount: float,
    ) -> None:
        """רושם פעולה בתוכנית הביצוע של התרחיש"""
        self.execution_plan.append(
            {
                "type": action_type,
                "details": details,
                "from": from_asset,
                "to": to_asset,
                "amount": float(amount or 0),
            }
        )
    
    def _import_pension_portfolio_if_needed(self) -> None:
        """Import pension portfolio data if provided"""
        if not self.pension_portfolio:
            return
        
        logger.info("📥 Importing pension portfolio data...")
        self.portfolio_import_service.import_pension_portfolio(self.pension_portfolio)
    
    def _apply_retirement_projection_if_needed(self) -> None:
        """הצמדת היתרות ונכסי ההון לריבית דריבית 4% עד תאריך הפרישה.
        
        אם תאריך הפרישה מרוחק פחות או שישה חודשים – לא מתבצעת הצמדה.
        """
        retirement_date = self._get_retirement_date()
        if not retirement_date:
            logger.info("  ℹ️ Retirement date not available, skipping 4% projection")
            return
        
        today = date.today()
        days_to_retirement = (retirement_date - today).days
        if days_to_retirement <= 0:
            logger.info("  ℹ️ Retirement date is in the past or today, skipping 4% projection")
            return
        
        # פחות או שישה חודשים – לא מצמידים
        if days_to_retirement <= 182:
            logger.info("  ℹ️ Retirement date is within ~6 months, skipping 4% projection")
            return
        
        years_to_retirement = days_to_retirement / 365.25
        growth_factor = (1.04) ** years_to_retirement
        logger.info(
            f"  📈 Applying 4% compound projection for ~{years_to_retirement:.2f} years "
            f"(factor={growth_factor:.4f})"
        )
        
        factor_decimal = Decimal(str(growth_factor))
        
        # הצמדת כל היתרות בטבלת המוצרים הפנסיוניים
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        for pf in pension_funds:
            if pf.balance and pf.balance > 0:
                old_balance = pf.balance
                pf.balance = float(Decimal(str(pf.balance)) * factor_decimal)
                logger.info(
                    f"  🔁 Projected pension fund '{pf.fund_name}': "
                    f"{old_balance:,.2f} → {pf.balance:,.2f}"
                )
        
        # הצמדת נכסי הון – ערך נוכחי ותשלום חודשי
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        for ca in capital_assets:
            updated = False
            if ca.current_value is not None:
                original_cv = float(ca.current_value)
                ca.current_value = Decimal(str(original_cv)) * factor_decimal
                updated = True
            if ca.monthly_income is not None:
                original_mi = float(ca.monthly_income)
                ca.monthly_income = Decimal(str(original_mi)) * factor_decimal
                updated = True
            if updated:
                logger.info(
                    f"  🔁 Projected capital asset '{ca.asset_name}' to retirement date"
                )
        
        self.db.flush()
    
    def _calculate_scenario_results(self, scenario_name: str) -> Dict:
        """Calculate and return the scenario results"""
        client = self._client or self.db.query(Client).filter(Client.id == self.client_id).first()
        
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        additional_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id
        ).all()
        
        total_pension_monthly = sum(float(pf.pension_amount or 0) for pf in pension_funds)

        # סך הון חד-פעמי (מוצג בנפרד, לא נכלל ב-NPV של התזרים)
        total_capital = 0.0
        capital_income_monthly = 0.0
        for ca in capital_assets:
            # הון חד-פעמי: רק current_value>0
            if ca.current_value is not None and float(ca.current_value) > 0:
                total_capital += float(ca.current_value)

            # הכנסה חודשית מנכסי הון לצורך NPV
            if ca.monthly_income is not None:
                income_value = float(ca.monthly_income or 0)
                if income_value > 0:
                    capital_income_monthly += income_value

        # הכנסה חודשית נוספת (תזרימית)
        total_additional_income_monthly = 0.0
        for ai in additional_incomes:
            amount = float(ai.amount or 0)
            freq = (ai.frequency or "monthly").lower()
            if freq == "monthly":
                monthly = amount
            elif freq == "quarterly":
                monthly = amount / 3.0
            elif freq == "annually":
                monthly = amount / 12.0
            else:
                monthly = amount
            total_additional_income_monthly += monthly

        # הוספת הכנסות חודשיות מנכסי הון לתזרים החודשי לצורך NPV
        total_additional_income_monthly += capital_income_monthly

        # NPV מחושב על בסיס תזרימי הקצבאות + הכנסות נוספות בלבד (ללא הון חד-פעמי),
        # כדי ליישר את המספרים עם מסך הדוחות שבו ה-NPV מתייחס לתזרים בלבד.
        years_for_npv = calculate_years_to_age(client, self.retirement_age)
        estimated_npv = calculate_npv_dcf(
            monthly_pension=total_pension_monthly,
            monthly_additional=total_additional_income_monthly,
            capital=0.0,
            years=years_for_npv,
        )

        # התאמה חשובה: ההכנסות מהקצבאות מתחילות רק בגיל הפרישה, ולכן צריך להוון
        # גם את השנים שנותרו עד הפרישה (retirement_age - current_age).
        years_until_retirement = 0
        if client and getattr(client, "birth_date", None):
            try:
                current_age = client.get_age()
                if current_age is not None and self.retirement_age is not None:
                    diff = self.retirement_age - current_age
                    if diff > 0:
                        years_until_retirement = diff
            except Exception:
                years_until_retirement = 0

        if years_until_retirement > 0:
            try:
                discount_factor = (1 + DEFAULT_DISCOUNT_RATE) ** years_until_retirement
                estimated_npv = round(estimated_npv / discount_factor, 2)
            except Exception:
                # אם יש בעיה כלשהי בחישוב, נשאיר את ה-NPV ללא התאמה כדי לא לשבור את התרחישים
                pass
        
        results = {
            "scenario_name": scenario_name,
            "client_id": self.client_id,
            "retirement_age": self.retirement_age,
            "total_pension_monthly": total_pension_monthly,
            "total_capital": total_capital,
            "total_additional_income_monthly": total_additional_income_monthly,
            "estimated_npv": estimated_npv,
            "pension_funds_count": len(pension_funds),
            "capital_assets_count": len(capital_assets),
            "additional_incomes_count": len(additional_incomes),
            "execution_plan": self.execution_plan,
        }
        
        self.scenario_results = results
        return results
        
    def _log_scenario_start(self, scenario_name: str) -> None:
        """Log the start of scenario processing"""
        logger.info(f"🚀 Starting scenario: {scenario_name}")
        logger.info(f"Client ID: {self.client_id}")
        logger.info(f"Retirement age: {self.retirement_age}")
        
    def _log_scenario_complete(self, scenario_name: str) -> None:
        """Log the completion of scenario processing"""
        logger.info(f"✅ Completed scenario: {scenario_name}")
        logger.info("-" * 50)
