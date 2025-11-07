"""
Termination Service Module
מודול שירותי סיום העסקה
"""
import json
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
        print(f"🔵 TERMINATION DECISION RECEIVED: {json.dumps(decision.model_dump(), indent=2, default=str)}")
        
        result = {
            "created_grant_id": None,
            "created_pension_id": None,
            "created_capital_asset_id": None
        }
        
        # פרסור נתונים
        source_account_names = self._parse_source_accounts(decision.source_accounts)
        plan_details_list = self._parse_plan_details(decision)
        source_suffix = self._create_source_suffix(source_account_names)
        
        # עדכון תאריך סיום
        employer.end_date = decision.termination_date
        self.db.add(employer)
        self.db.flush()
        print(f"✅ Updated CurrentEmployer end_date to: {decision.termination_date}")
        
        # מחיקת מענקים קיימים
        self._delete_existing_severance_grants(employer.id)
        
        # יצירת מענקים חדשים
        self._create_employer_grants(employer, decision, plan_details_list)
        
        # עיבוד סכומים
        if decision.exempt_amount > 0:
            self._process_exempt_amount(client, employer, decision, source_suffix, result)
        
        if decision.taxable_amount > 0:
            self._process_taxable_amount(client, employer, decision, source_suffix, result)
        
        self.db.commit()
        print(f"✅ TRANSACTION COMMITTED - RESULT: {result}")
        
        return result
    
    def delete_termination(
        self,
        client: Client,
        employer: CurrentEmployer
    ) -> Dict[str, Any]:
        """מחיקת כל הישויות שנוצרו מהחלטת סיום העסקה"""
        deleted_count = 0
        severance_to_restore = employer.severance_accrued or 0
        
        print(f"🔵 DELETE TERMINATION: client_id={client.id}, employer_name={employer.employer_name}")
        
        if employer.employer_name:
            deleted_count += self._delete_grants(client.id, employer.employer_name)
            deleted_count += self._delete_capital_assets(client.id, employer.employer_name)
            deleted_count += self._delete_pension_funds(client.id, employer.employer_name)
        
        employer.end_date = None
        self.db.add(employer)
        self.db.commit()
        
        print(f"✅ DELETED {deleted_count} entities")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "severance_to_restore": severance_to_restore,
            "message": f"נמחקו {deleted_count} אלמנטים הקשורים לעזיבה"
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
            print(f"🗑️ Deleting {len(existing_grants)} existing EmployerGrants")
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
        print(f"🟡 PROCESSING EXEMPT AMOUNT: {decision.exempt_amount}")
        
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
        result: Dict
    ):
        """עיבוד סכום חייב - קצבה/נכס הון עם פריסת מס"""
        print(f"🔵 PROCESSING TAXABLE AMOUNT: {decision.taxable_amount}")
        
        if decision.taxable_choice == 'redeem_no_exemption':
            # נכס הון עם פריסת מס
            spread_years = decision.max_spread_years or 1
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
                
        elif decision.taxable_choice == 'annuity':
            # יצירת קצבאות
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
        from app.services.annuity_coefficient_service import get_annuity_coefficient
        
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
        
        # יצירת קצבה לכל תכנית
        for plan_key, plan_data in grants_by_plan.items():
            plan_grants = plan_data['grants']
            plan_grant_amount = sum(g.grant_amount for g in plan_grants)
            plan_amount = (plan_grant_amount / total_grant_amount) * amount if total_grant_amount > 0 else 0
            
            # חישוב מקדם קצבה
            try:
                coefficient_result = get_annuity_coefficient(
                    product_type=plan_data['product_type'],
                    start_date=plan_data['plan_start_date'] or employer.start_date or decision.termination_date,
                    gender=client.gender or 'זכר',
                    retirement_age=67,
                    survivors_option='תקנוני',
                    spouse_age_diff=0,
                    birth_date=client.birth_date,
                    pension_start_date=decision.termination_date
                )
                annuity_factor = coefficient_result['factor_value']
            except:
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
