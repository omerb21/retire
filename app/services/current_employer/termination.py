"""
Termination Service Module
מודול שירותי סיום העסקה
"""
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.grant import Grant
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.current_employment import EmployerGrant, GrantType
from app.schemas.current_employer import TerminationDecisionCreate
from .calculations import ServiceYearsCalculator, SeveranceCalculator
from app.services.current_employer.termination_parts.validation import (
    _create_source_suffix,
    _parse_date,
    _parse_plan_details,
    _parse_source_accounts,
)
from app.services.current_employer.termination_parts.repository import (
    TerminationRepositoryMixin,
    _create_employer_grants,
    _delete_capital_assets,
    _delete_existing_severance_grants,
    _delete_grants,
    _delete_pension_funds,
)
from app.services.current_employer.termination_parts.calculations import (
    _calculate_capital_tax,
    _calculate_employment_years,
)

logger = logging.getLogger("app.current_employer.termination")


class TerminationService:
    """שירות עיבוד סיום העסקה"""

    def __init__(self, db: Session):
        """אתחול שירות סיום העסקה"""
        self.db = db
        self.service_years_calc = ServiceYearsCalculator()
        self.severance_calc = SeveranceCalculator()

    def process_termination(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate
    ) -> Dict[str, Optional[int]]:
        """
        עיבוד החלטת סיום העסקה ויצירת ישויות מתאימות

        הפונקציה מטפלת בכל הלוגיקה של סיום העסקה:
        - עדכון תאריך סיום
        - יצירת EmployerGrants
        - עיבוד סכום פטור (מענק/קצבה/נכס הון)
        - עיבוד סכום חייב (קצבה/נכס הון עם פריסת מס)
        """
        logger.info("Termination decision received")
        logger.debug("Termination decision payload: %s", decision.model_dump())

        # D4.3: חישוב שנות פריסה מקסימליות לפי תקנות המס
        employment_years = self._calculate_employment_years(employer.start_date, decision.termination_date)
        calculated_max_spread = max(1, int(employment_years / 4))  # מינימום 1, עיגול למטה
        # מקסימום 6 שנים לפי חוק
        max_spread_years = min(calculated_max_spread, 6)

        logger.debug(
            "Termination max spread years derived (employment_years=%.2f, max_spread_years=%s)",
            employment_years,
            max_spread_years,
        )

        result = {
            "created_grant_id": None,
            "created_pension_id": None,
            "created_capital_asset_id": None,
            # D4.3: שנות פריסה מקסימליות
            "employment_years": round(employment_years, 2),
            "max_spread_years": max_spread_years,
            # D3.8: מידע על סכומים שאופסו - לעדכון הפרונטאנד
            "severance_reset_info": {
                "employer_severance_accrued_reset": 0,  # יעודכן בהמשך
                "portfolio_severance_to_reset": True,   # סימון לפרונטאנד לאפס פיצויים_מעסיק_נוכחי
                "source_accounts": []  # רשימת חשבונות מקור לאיפוס
            }
        }

        # פרסור נתונים
        source_account_names = self._parse_source_accounts(decision.source_accounts)
        plan_details_list = self._parse_plan_details(decision)
        source_suffix = self._create_source_suffix(source_account_names)

        # עדכון תאריך סיום
        employer.end_date = decision.termination_date
        self.db.add(employer)
        self.db.flush()
        logger.debug("Updated CurrentEmployer end_date to %s", decision.termination_date)

        # מחיקת מענקים קיימים
        self._delete_existing_severance_grants(employer.id)

        # יצירת מענקים חדשים
        self._create_employer_grants(employer, decision, plan_details_list)

        # עיבוד סכומים
        if decision.exempt_amount > 0:
            self._process_exempt_amount(client, employer, decision, source_suffix, result)

        if decision.taxable_amount > 0:
            self._process_taxable_amount(client, employer, decision, source_suffix, result, max_spread_years)

        # D3.7: איפוס יתרת הפיצויים במעסיק הנוכחי לאחר יצירת הקצבה/נכס הון
        # זה מונע ספירה כפולה - הכסף עבר מהפיצויים לקצבה/נכס הון
        original_severance = employer.severance_accrued
        employer.severance_accrued = 0
        self.db.add(employer)
        logger.debug("Reset severance_accrued from %s to 0", original_severance)

        # D3.8: עדכון מידע על איפוס הפיצויים בתוצאה
        result["severance_reset_info"]["employer_severance_accrued_reset"] = original_severance or 0
        result["severance_reset_info"]["source_accounts"] = source_account_names
        logger.debug("Severance reset info: %s", result["severance_reset_info"])

        # Persist termination confirmation marker on employer (server-side)
        try:
            other_grants = employer.other_grants or {}
            if not isinstance(other_grants, dict):
                other_grants = {}
            other_grants["termination_confirmed"] = True
            other_grants["termination_confirmed_at"] = datetime.utcnow().isoformat()
            other_grants["termination_date"] = decision.termination_date.isoformat()
            employer.other_grants = other_grants
            self.db.add(employer)
        except Exception:
            pass

        self.db.commit()
        logger.info("Termination transaction committed")
        logger.debug("Termination result: %s", result)

        return result

    def delete_termination(
        self,
        client: Client,
        employer: CurrentEmployer
    ) -> Dict[str, Any]:
        """מחיקת כל הישויות שנוצרו מהחלטת סיום העסקה"""
        deleted_count = 0

        logger.info("Delete termination requested (client_id=%s, employer_name=%s)", client.id, employer.employer_name)

        # D3.7: חישוב סכום הפיצויים לשחזור מה-EmployerGrants לפני המחיקה
        severance_grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == employer.id,
            EmployerGrant.grant_type == GrantType.severance
        ).all()
        severance_to_restore = sum(g.grant_amount or 0 for g in severance_grants)
        logger.debug(
            "Severance to restore from %s grants: %s",
            len(severance_grants),
            severance_to_restore,
        )

        if employer.employer_name:
            deleted_count += self._delete_grants(client.id, employer.employer_name)
            deleted_count += self._delete_capital_assets(client.id, employer.employer_name)
            deleted_count += self._delete_pension_funds(client.id, employer.employer_name)

        # מחיקת EmployerGrants
        for grant in severance_grants:
            self.db.delete(grant)
            deleted_count += 1

        # D3.7: שחזור יתרת הפיצויים ואיפוס תאריך סיום
        employer.end_date = None
        employer.severance_accrued = severance_to_restore

        # Clear server-side termination confirmation marker
        try:
            other_grants = employer.other_grants or {}
            if isinstance(other_grants, dict):
                other_grants.pop("termination_confirmed", None)
                other_grants.pop("termination_confirmed_at", None)
                other_grants.pop("termination_date", None)
                employer.other_grants = other_grants
        except Exception:
            pass
        self.db.add(employer)
        self.db.commit()

        logger.info(
            "Deleted termination entities (deleted_count=%s, restored_severance=%s)",
            deleted_count,
            severance_to_restore,
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "severance_to_restore": severance_to_restore,
            "message": f"נמחקו {deleted_count} אלמנטים הקשורים לעזיבה, שוחזרו פיצויים: {severance_to_restore:,.0f} ₪"
        }

    def calculate_severance(
        self,
        start_date: date,
        end_date: date,
        last_salary: float,
        continuity_years: float = 0.0
    ) -> Dict[str, float]:
        """חישוב פיצויי פיטורין"""
        service_years = self.service_years_calc.calculate(
            start_date=start_date,
            end_date=end_date,
            continuity_years=continuity_years
        )

        severance_amount = self.severance_calc.calculate_severance_amount(
            last_salary=last_salary,
            service_years=service_years
        )

        breakdown = self.severance_calc.calculate_exempt_and_taxable(
            severance_amount=severance_amount,
            service_years=service_years
        )

        return {
            "service_years": round(service_years, 2),
            "severance_amount": round(severance_amount, 2),
            "last_salary": last_salary,
            "exempt_amount": breakdown["exempt_amount"],
            "taxable_amount": breakdown["taxable_amount"],
            "annual_exemption_cap": 13750.0
        }

    _parse_source_accounts = _parse_source_accounts
    _parse_plan_details = _parse_plan_details
    _create_source_suffix = _create_source_suffix
    _parse_date = _parse_date

    _delete_existing_severance_grants = _delete_existing_severance_grants
    _create_employer_grants = _create_employer_grants

    _delete_grants = _delete_grants
    _delete_capital_assets = _delete_capital_assets
    _delete_pension_funds = _delete_pension_funds

    _calculate_employment_years = _calculate_employment_years
    _calculate_capital_tax = _calculate_capital_tax

    _process_exempt_amount = TerminationRepositoryMixin._process_exempt_amount
    _process_taxable_amount = TerminationRepositoryMixin._process_taxable_amount
    _create_pension_funds_from_amount = TerminationRepositoryMixin._create_pension_funds_from_amount


    def _delete_grants(self, client_id: int, employer_name: str) -> int:
        """מחיקת מענקים"""
        grants = self.db.query(Grant).filter(
            Grant.client_id == client_id,
            Grant.employer_name.like(f"%{employer_name}%")
        ).all()
        for grant in grants:
            self.db.delete(grant)
        return len(grants)
    
    def _delete_capital_assets(self, client_id: int, employer_name: str) -> int:
        """מחיקת נכסי הון"""
        assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.asset_name.like(f"%{employer_name}%")
        ).all()
        for asset in assets:
            self.db.delete(asset)
        return len(assets)
    
    def _delete_pension_funds(self, client_id: int, employer_name: str) -> int:
        """מחיקת קצבאות"""
        pensions = self.db.query(PensionFund).filter(
            PensionFund.client_id == client_id,
            PensionFund.fund_name.like(f"%{employer_name}%")
        ).all()
        for pension in pensions:
            self.db.delete(pension)
        return len(pensions)
    
    def _calculate_employment_years(self, start_date: date, end_date: date) -> float:
        """
        D4.3: חישוב שנות עבודה מלאות
        
        Args:
            start_date: תאריך תחילת עבודה
            end_date: תאריך סיום עבודה
            
        Returns:
            מספר שנות העבודה (כולל חלקי שנה)
        """
        if not start_date or not end_date:
            return 0.0
        
        # חישוב ההפרש בימים וחלוקה ב-365.25 (ממוצע שנה כולל שנים מעוברות)
        days_diff = (end_date - start_date).days
        years = days_diff / 365.25
        
        return max(0.0, years)
    
    def _calculate_capital_tax(self, gross_amount: float, spread_years: int) -> Dict[str, Any]:
        """
        D4.2: חישוב מס שולי על מענק הוני עם פריסת מס
        
        Args:
            gross_amount: סכום ברוטו של המענק
            spread_years: מספר שנות פריסה
            
        Returns:
            Dict עם פרטי המס: total_tax, net_amount, annual_portion, annual_tax, effective_rate
        """
        from app.services.tax.constants import TaxConstants
        
        if spread_years <= 0:
            spread_years = 1
        
        # חלוקה שווה של הסכום על השנים
        annual_portion = gross_amount / spread_years
        
        # חישוב מס שנתי לפי מדרגות מס 2025
        tax_brackets = TaxConstants.INCOME_TAX_BRACKETS_2025
        
        annual_tax = Decimal('0')
        remaining_income = Decimal(str(annual_portion))
        prev_threshold = Decimal('0')
        
        for bracket in tax_brackets:
            if remaining_income <= 0:
                break
            
            threshold = Decimal(str(bracket.max_income)) if bracket.max_income else None
            rate = Decimal(str(bracket.rate))
            
            if threshold is None:
                # מדרגה אחרונה
                annual_tax += remaining_income * rate
                break
            
            income_in_bracket = min(remaining_income, threshold - prev_threshold)
            annual_tax += income_in_bracket * rate
            remaining_income -= income_in_bracket
            prev_threshold = threshold
        
        # סה"כ מס = מס שנתי × מספר שנים
        total_tax = float(annual_tax) * spread_years
        net_amount = gross_amount - total_tax
        effective_rate = (total_tax / gross_amount * 100) if gross_amount > 0 else 0

        logger.debug(
            "Capital tax calculation (gross=%s, spread_years=%s, annual_portion=%s, annual_tax=%s, total_tax=%s, net=%s, effective_rate=%s)",
            gross_amount,
            spread_years,
            annual_portion,
            float(annual_tax),
            total_tax,
            net_amount,
            effective_rate,
        )
         
        return {
            "gross_amount": gross_amount,
            "spread_years": spread_years,
            "annual_portion": round(annual_portion, 2),
            "annual_tax": round(float(annual_tax), 2),
            "total_tax": round(total_tax, 2),
            "net_amount": round(net_amount, 2),
            "effective_rate": round(effective_rate, 2)
        }
