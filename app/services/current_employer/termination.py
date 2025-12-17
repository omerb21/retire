"""
Termination Service Module
מודול שירותי סיום העסקה
"""
import json
import logging
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
    
    # ========== Private Helper Methods ==========
    
    def _parse_source_accounts(self, source_accounts: Optional[str]) -> List[str]:
        """פרסור חשבונות מקור"""
        if not source_accounts:
            return []
        try:
            return json.loads(source_accounts)
        except:
            return []
    
    def _parse_plan_details(self, decision: TerminationDecisionCreate) -> List[Dict]:
        """פרסור פרטי תכניות"""
        if not hasattr(decision, 'plan_details') or not decision.plan_details:
            return []
        try:
            return json.loads(decision.plan_details)
        except:
            return []
    
    def _create_source_suffix(self, source_account_names: List[str]) -> str:
        """יצירת סיומת מקור לשמות"""
        if not source_account_names:
            return ""
        if len(source_account_names) == 1:
            return f" - נוצר מ: {source_account_names[0]}"
        suffix = f" - נוצר מ: {', '.join(source_account_names[:2])}"
        if len(source_account_names) > 2:
            suffix += f" ועוד {len(source_account_names) - 2}"
        return suffix
    
    def _delete_existing_severance_grants(self, employer_id: int):
        """מחיקת EmployerGrants קיימים"""
        existing_grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == employer_id,
            EmployerGrant.grant_type == GrantType.severance
        ).all()
        
        if existing_grants:
            logger.debug("Deleting %s existing EmployerGrants", len(existing_grants))
            for grant in existing_grants:
                self.db.delete(grant)
            self.db.flush()
    
    def _create_employer_grants(
        self,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        plan_details_list: List[Dict]
    ):
        """יצירת EmployerGrant לכל תכנית"""
        if plan_details_list:
            for plan_detail in plan_details_list:
                amount = plan_detail.get('amount', 0)
                if amount > 0:
                    employer_grant = EmployerGrant(
                        employer_id=employer.id,
                        grant_type=GrantType.severance,
                        grant_amount=amount,
                        grant_date=decision.termination_date,
                        plan_name=plan_detail.get('plan_name'),
                        plan_start_date=self._parse_date(plan_detail.get('plan_start_date')),
                        product_type=plan_detail.get('product_type', 'קופת גמל')
                    )
                    self.db.add(employer_grant)
            self.db.flush()
        else:
            # Fallback: יצירת מענק יחיד
            total_amount = decision.exempt_amount + decision.taxable_amount
            if total_amount > 0:
                employer_grant = EmployerGrant(
                    employer_id=employer.id,
                    grant_type=GrantType.severance,
                    grant_amount=total_amount,
                    grant_date=decision.termination_date,
                    plan_name="ללא תכנית",
                    plan_start_date=employer.start_date
                )
                self.db.add(employer_grant)
                self.db.flush()
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """פרסור תאריך"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except:
            try:
                return datetime.fromisoformat(date_str).date()
            except:
                return None
    
    def _process_exempt_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        source_suffix: str,
        result: Dict
    ):
        """עיבוד סכום פטור - מענק/קצבה/נכס הון"""
        logger.debug("Processing exempt amount: %s", decision.exempt_amount)
        
        if decision.exempt_choice == 'redeem_with_exemption':
            # יצירת מענק + נכס הון פטור
            grant = Grant(
                client_id=client.id,
                employer_name=f"מענק פיצויים פטור - {employer.employer_name}{source_suffix}",
                work_start_date=employer.start_date,
                work_end_date=decision.termination_date,
                grant_amount=decision.exempt_amount,
                grant_date=decision.termination_date,
                grant_indexed_amount=decision.exempt_amount,
                limited_indexed_amount=decision.exempt_amount
            )
            self.db.add(grant)
            self.db.flush()
            result["created_grant_id"] = grant.id
            
            capital_asset = CapitalAsset(
                client_id=client.id,
                asset_name=f"מענק פיצויים פטור ({employer.employer_name}){source_suffix}",
                asset_type="other",
                current_value=Decimal("0"),
                monthly_income=decision.exempt_amount,
                annual_return_rate=0.0,
                payment_frequency="annually",
                start_date=decision.termination_date,
                indexation_method="none",
                tax_treatment="exempt",
                remarks=f"מענק פיצויים פטור ממס - {decision.exempt_amount:,.0f} ₪"
            )
            self.db.add(capital_asset)
            self.db.flush()
            result["created_capital_asset_id"] = capital_asset.id
            
        elif decision.exempt_choice == 'redeem_no_exemption':
            # נכס הון עם פריסת מס
            spread_years = decision.max_spread_years or 1
            capital_asset = CapitalAsset(
                client_id=client.id,
                asset_name=f"מענק פיצויים פטור ({employer.employer_name}){source_suffix}",
                asset_type="other",
                current_value=Decimal("0"),
                monthly_income=decision.exempt_amount,
                annual_return_rate=0.0,
                payment_frequency="annually",
                start_date=decision.termination_date,
                indexation_method="none",
                tax_treatment="tax_spread",
                spread_years=spread_years,
                remarks=f"מענק פיצויים פטור ממס עם פריסת מס ל-{spread_years} שנים"
            )
            self.db.add(capital_asset)
            self.db.flush()
            result["created_capital_asset_id"] = capital_asset.id
            
        elif decision.exempt_choice == 'annuity':
            # יצירת קצבאות
            self._create_pension_funds_from_amount(
                client, employer, decision, decision.exempt_amount, "exempt", result
            )
    
    def _process_taxable_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        source_suffix: str,
        result: Dict,
        max_spread_years: int = 6
    ):
        """עיבוד סכום חייב - קצבה/נכס הון עם פריסת מס"""
        logger.debug("Processing taxable amount: %s", decision.taxable_amount)
        
        # D4.4: אכיפת שנות פריסה מקסימליות לטובת הלקוח
        requested_spread = decision.tax_spread_years
        if requested_spread is None or requested_spread < 1 or requested_spread > max_spread_years:
            effective_spread_years = max_spread_years
            logger.debug(
                "Enforcing max spread years (requested=%s, using=%s)",
                requested_spread,
                effective_spread_years,
            )
        else:
            effective_spread_years = requested_spread
            logger.debug("Using requested spread years: %s", effective_spread_years)
        
        # D4.4: שמירת הפריסה בפועל ב-result
        result["effective_spread_years"] = effective_spread_years
        result["requested_spread_years"] = requested_spread
        
        # D4.1: בדיקה אם יש פיצול של הסכום החייב
        taxable_annuity = getattr(decision, 'taxable_annuity_amount', None)
        taxable_capital = getattr(decision, 'taxable_capital_amount', None)
        
        if decision.taxable_choice == 'split' or (taxable_annuity is not None or taxable_capital is not None):
            # D4.1: פיצול הסכום החייב - חלק לקצבה וחלק למענק
            annuity_amount = float(taxable_annuity or 0)
            capital_amount = float(taxable_capital or 0)
            
            logger.debug(
                "Split taxable amount (annuity=%s, capital=%s)",
                annuity_amount,
                capital_amount,
            )
            
            # יצירת קצבה מהחלק שהוקצה לרצף קצבה
            if annuity_amount > 0:
                logger.debug("Creating pension from annuity amount: %s", annuity_amount)
                self._create_pension_funds_from_amount(
                    client, employer, decision, annuity_amount, "taxable", result
                )
            
            # יצירת נכס הון מהחלק שהוקצה למענק
            if capital_amount > 0:
                logger.debug("Creating capital asset from capital amount: %s", capital_amount)
                spread_years = effective_spread_years  # D4.4: שימוש בפריסה המאוכפת
                capital_asset = CapitalAsset(
                    client_id=client.id,
                    asset_name=f"מענק פיצויים חייב במס ({employer.employer_name}){source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),
                    monthly_income=capital_amount,
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="tax_spread",
                    spread_years=spread_years,
                    remarks=f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים (D4.1 split)"
                )
                self.db.add(capital_asset)
                self.db.flush()
                if not result.get("created_capital_asset_id"):
                    result["created_capital_asset_id"] = capital_asset.id
                
                # D4.2: חישוב המס על המענק ההוני
                tax_info = self._calculate_capital_tax(capital_amount, spread_years)
                result["capital_tax_info"] = tax_info
                logger.debug("Capital tax calculated: %s", tax_info)
            
        elif decision.taxable_choice == 'redeem_no_exemption':
            # נכס הון עם פריסת מס - כל הסכום החייב
            spread_years = effective_spread_years  # D4.4: שימוש בפריסה המאוכפת
            capital_asset = CapitalAsset(
                client_id=client.id,
                asset_name=f"מענק פיצויים חייב במס ({employer.employer_name}){source_suffix}",
                asset_type="other",
                current_value=Decimal("0"),
                monthly_income=decision.taxable_amount,
                annual_return_rate=0.0,
                payment_frequency="annually",
                start_date=decision.termination_date,
                indexation_method="none",
                tax_treatment="tax_spread",
                spread_years=spread_years,
                remarks=f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים"
            )
            self.db.add(capital_asset)
            self.db.flush()
            if not result.get("created_capital_asset_id"):
                result["created_capital_asset_id"] = capital_asset.id
            
            # D4.2: חישוב המס על המענק ההוני
            tax_info = self._calculate_capital_tax(float(decision.taxable_amount), spread_years)
            result["capital_tax_info"] = tax_info
            logger.debug("Capital tax calculated: %s", tax_info)
                
        elif decision.taxable_choice == 'annuity':
            # יצירת קצבאות - כל הסכום החייב
            self._create_pension_funds_from_amount(
                client, employer, decision, decision.taxable_amount, "taxable", result
            )
    
    def _create_pension_funds_from_amount(
        self,
        client: Client,
        employer: CurrentEmployer,
        decision: TerminationDecisionCreate,
        amount: Decimal,
        tax_treatment: str,
        result: Dict
    ):
        """יצירת קצבאות מסכום נתון"""
        from app.services.annuity_coefficient import get_annuity_coefficient
        
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == employer.id,
            EmployerGrant.grant_type == GrantType.severance
        ).all()
        
        total_grant_amount = sum(g.grant_amount for g in grants)
        
        # קיבוץ לפי תכנית
        grants_by_plan = {}
        for grant in grants:
            plan_key = grant.plan_name or "ללא תכנית"
            if plan_key not in grants_by_plan:
                grants_by_plan[plan_key] = {
                    'grants': [],
                    'plan_start_date': grant.plan_start_date,
                    'plan_name': grant.plan_name,
                    'product_type': grant.product_type or 'קופת גמל'
                }
            grants_by_plan[plan_key]['grants'].append(grant)
        
        # D6.1: אתחול מצברים לחישוב קצבה כוללת
        total_annuity_deposit = 0.0
        total_monthly_annuity = 0.0
        annuity_details = []
        
        # יצירת קצבה לכל תכנית
        for plan_key, plan_data in grants_by_plan.items():
            plan_grants = plan_data['grants']
            plan_grant_amount = sum(g.grant_amount for g in plan_grants)
            plan_amount = (plan_grant_amount / total_grant_amount) * amount if total_grant_amount > 0 else 0
            
            # D3.9: חישוב מקדם קצבה לפי סוג המוצר
            product_type = plan_data['product_type']
            start_date = plan_data['plan_start_date'] or employer.start_date or decision.termination_date
            logger.debug(
                "Calculating annuity coefficient (plan=%s, product_type=%s, start_date=%s, amount=%s)",
                plan_key,
                product_type,
                start_date,
                plan_amount,
            )
            
            try:
                coefficient_result = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date,
                    gender=client.gender or 'זכר',
                    retirement_age=67,
                    survivors_option='תקנוני',
                    spouse_age_diff=0,
                    birth_date=client.birth_date,
                    pension_start_date=decision.termination_date
                )
                annuity_factor = coefficient_result['factor_value']
                logger.debug(
                    "Got coefficient (factor=%s, source=%s)",
                    annuity_factor,
                    coefficient_result.get("source_table", "unknown"),
                )
            except Exception as e:
                logger.warning("Coefficient error (%s), using default 200", e)
                annuity_factor = 200
            
            monthly_amount = plan_amount / annuity_factor
            
            pension_fund = PensionFund(
                client_id=client.id,
                fund_name=f"קצבה ממענק פיצויים {tax_treatment} - {plan_data['plan_name']} ({employer.employer_name})",
                fund_type="monthly_pension",
                input_mode="manual",
                balance=plan_amount,
                annuity_factor=annuity_factor,
                pension_amount=monthly_amount,
                pension_start_date=decision.termination_date,
                indexation_method="none",
                tax_treatment=tax_treatment,
                remarks=f"מקדם קצבה: {annuity_factor:.2f}, תכנית: {plan_data['plan_name']}"
            )
            self.db.add(pension_fund)
            self.db.flush()
            
            if not result.get("created_pension_id"):
                result["created_pension_id"] = pension_fund.id
            
            # D6.1: צבירת נתוני הקצבה
            total_annuity_deposit += float(plan_amount)
            total_monthly_annuity += float(monthly_amount)
            annuity_details.append({
                "plan_name": plan_data['plan_name'],
                "deposit": round(float(plan_amount), 2),
                "coefficient": round(annuity_factor, 2),
                "monthly_annuity": round(float(monthly_amount), 2)
            })
        
        # D6.1: עדכון result עם נתוני הקצבה
        if total_annuity_deposit > 0:
            # אתחול אם לא קיים
            if "annuity_projection" not in result:
                result["annuity_projection"] = {
                    "total_annuity_deposit": 0.0,
                    "total_monthly_annuity": 0.0,
                    "details": []
                }
            
            # הוספה לסכומים הקיימים (יכול להיות גם exempt וגם taxable)
            result["annuity_projection"]["total_annuity_deposit"] += round(total_annuity_deposit, 2)
            result["annuity_projection"]["total_monthly_annuity"] += round(total_monthly_annuity, 2)
            result["annuity_projection"]["details"].extend(annuity_details)
            
            logger.debug(
                "Annuity projection updated (deposit=%s, monthly=%s)",
                total_annuity_deposit,
                total_monthly_annuity,
            )
    
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
