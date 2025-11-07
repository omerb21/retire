"""
Termination event handling service
שירות טיפול באירועי עזיבת עבודה
"""
import logging
import json
from datetime import date
from typing import Optional, Callable
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.termination_event import TerminationEvent
from app.models.current_employment import CurrentEmployer, EmployerGrant, GrantType
from app.services.current_employer_service import CurrentEmployerService
from app.services.annuity_coefficient_service import get_annuity_coefficient
from ..constants import PENSION_COEFFICIENT

logger = logging.getLogger("app.scenarios.termination")


class TerminationService:
    """שירות לטיפול באירועי עזיבת עבודה"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        add_action_callback: Optional[Callable] = None
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.add_action = add_action_callback
    
    def _get_retirement_year(self, client: Client) -> int:
        """מחשב שנת פרישה"""
        if not client.birth_date:
            raise ValueError("תאריך לידה חסר")
        return client.birth_date.year + self.retirement_age
    
    def handle_termination_for_pension(self) -> None:
        """טיפול בעזיבת עבודה - בחירה בקצבה"""
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()
        
        if not termination:
            logger.info("  ℹ️ No termination event found, skipping")
            return
        
        logger.info("  📝 Processing termination event for pension choice")
        
        # מציאת המעביד הנוכחי
        current_employer = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == self.client_id,
            CurrentEmployer.id == termination.employment_id
        ).first()
        
        if not current_employer:
            logger.warning("  ⚠️ Current employer not found for termination event")
            return
        
        # מציאת כל המענקים של המעביד
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.current_employer_id == current_employer.id
        ).all()
        
        if not grants:
            logger.info("  ℹ️ No grants found for termination")
            return
        
        # קבלת נתוני לקוח לחישוב מקדם
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        retirement_year = self._get_retirement_year(client)
        pension_start_date = date(retirement_year, 1, 1)
        
        # קיבוץ מענקים לפי תכנית
        grants_by_plan = self._group_grants_by_plan(grants)
        
        if not grants_by_plan:
            logger.info("  ℹ️ No severance grants to process")
            return
        
        # יצירת קצבה נפרדת לכל תכנית
        total_pensions_created = 0
        for plan_key, plan_data in grants_by_plan.items():
            pension_created = self._create_pension_from_plan(
                plan_data,
                current_employer,
                client,
                pension_start_date,
                termination.id
            )
            if pension_created:
                total_pensions_created += 1
        
        logger.info(f"  🎯 Total pensions created: {total_pensions_created}")
        self.db.flush()
    
    def handle_termination_for_capital(self) -> None:
        """טיפול בעזיבת עבודה - בחירה בהון"""
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()
        
        if not termination:
            logger.info("  ℹ️ No termination event found, skipping")
            return
        
        logger.info("  📝 Processing termination event for capital choice")
        
        # מציאת המעביד הנוכחי
        current_employer = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == self.client_id,
            CurrentEmployer.id == termination.employment_id
        ).first()
        
        if not current_employer:
            logger.warning("  ⚠️ Current employer not found for termination event")
            return
        
        # מציאת כל המענקים של המעביד
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.current_employer_id == current_employer.id
        ).all()
        
        if not grants:
            logger.info("  ℹ️ No grants found for termination")
            return
        
        # קיבוץ מענקים לפי תכנית
        grants_by_plan = self._group_grants_by_plan(grants)
        
        if not grants_by_plan:
            logger.info("  ℹ️ No severance grants to process")
            return
        
        # קבלת נתוני לקוח
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        retirement_year = self._get_retirement_year(client)
        
        # יצירת נכס הון נפרד לכל תכנית
        total_assets_created = 0
        for plan_key, plan_data in grants_by_plan.items():
            asset_created = self._create_capital_from_plan(
                plan_data,
                current_employer,
                retirement_year,
                termination.id
            )
            if asset_created:
                total_assets_created += 1
        
        logger.info(f"  🎯 Total capital assets created: {total_assets_created}")
        self.db.flush()
    
    def _group_grants_by_plan(self, grants):
        """קיבוץ מענקים לפי תכנית"""
        grants_by_plan = {}
        for grant in grants:
            if grant.grant_type == GrantType.severance:
                plan_key = grant.plan_name or "ללא תכנית"
                if plan_key not in grants_by_plan:
                    grants_by_plan[plan_key] = {
                        'grants': [],
                        'plan_start_date': grant.plan_start_date,
                        'plan_name': grant.plan_name,
                        'product_type': grant.product_type
                    }
                grants_by_plan[plan_key]['grants'].append(grant)
        return grants_by_plan
    
    def _create_pension_from_plan(self, plan_data, current_employer, client, pension_start_date, termination_id):
        """יצירת קצבה מתכנית"""
        plan_grants = plan_data['grants']
        plan_start_date = plan_data['plan_start_date']
        plan_name = plan_data['plan_name'] or "תכנית ללא שם"
        product_type = plan_data.get('product_type') or 'ביטוח מנהלים'
        
        # חישוב סכומים לתכנית זו
        plan_severance = 0
        plan_exempt = 0
        
        for grant in plan_grants:
            calc_result = CurrentEmployerService.calculate_severance_grant(
                current_employer, grant
            )
            plan_severance += calc_result.indexed_amount
            plan_exempt += calc_result.grant_exempt
            logger.info(f"    💰 Grant for {plan_name}: {grant.grant_amount} ₪ (Exempt: {calc_result.grant_exempt:,.0f}, Taxable: {calc_result.grant_taxable:,.0f})")
        
        if plan_severance == 0:
            logger.info(f"  ℹ️ No severance amount for plan {plan_name}")
            return False
        
        # חישוב מקדם קצבה דינמי
        try:
            logger.info(f"  📊 Calculating coefficient for {plan_name}: product_type='{product_type}'")
            coefficient_result = get_annuity_coefficient(
                product_type=product_type,
                start_date=plan_start_date if plan_start_date else (current_employer.start_date if current_employer.start_date else date.today()),
                gender=client.gender if client else 'זכר',
                retirement_age=self.retirement_age,
                survivors_option='תקנוני',
                spouse_age_diff=0,
                birth_date=client.birth_date if client else None,
                pension_start_date=pension_start_date
            )
            annuity_factor = coefficient_result['factor_value']
            factor_source = coefficient_result['source_table']
            logger.info(f"  📊 Dynamic annuity coefficient for {plan_name}: {annuity_factor} (source: {factor_source})")
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to calculate dynamic coefficient for {plan_name}: {e}, using default {PENSION_COEFFICIENT}")
            annuity_factor = PENSION_COEFFICIENT
            factor_source = "default"
        
        # חישוב קצבה
        pension_amount = plan_severance / annuity_factor
        
        # קביעת יחס מס
        exempt_ratio = plan_exempt / plan_severance if plan_severance > 0 else 0
        tax_treatment = "exempt" if exempt_ratio > 0.8 else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        pf = PensionFund(
            client_id=self.client_id,
            fund_name=f"קצבה מפיצויי פרישה - {plan_name}",
            fund_type="severance_pension",
            input_mode="manual",
            balance=plan_severance,
            annuity_factor=annuity_factor,
            pension_amount=pension_amount,
            pension_start_date=pension_start_date,
            indexation_method="none",
            tax_treatment=tax_treatment,
            remarks=f"תכנית: {plan_name}\nמקדם קצבה: {annuity_factor:.2f} (מקור: {factor_source})\nתאריך התחלת תכנית: {plan_start_date.strftime('%d/%m/%Y') if plan_start_date else 'לא ידוע'}",
            conversion_source=json.dumps({
                "source": "termination_event",
                "termination_id": termination_id,
                "employer_id": current_employer.id,
                "plan_name": plan_name,
                "plan_start_date": plan_start_date.isoformat() if plan_start_date else None,
                "plan_severance": plan_severance,
                "plan_exempt": plan_exempt,
                "annuity_factor": annuity_factor,
                "factor_source": factor_source
            })
        )
        self.db.add(pf)
        
        logger.info(f"  ✅ Created pension for {plan_name}: {pension_amount:,.0f} ₪/month ({tax_status})")
        
        if self.add_action:
            self.add_action(
                "conversion",
                f"המרת פיצויי פרישה לקצבה - {plan_name} ({tax_status})",
                from_asset=f"פיצויים מ-{plan_name}: {plan_severance:,.0f} ₪ (פטור: {plan_exempt:,.0f})",
                to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש ({tax_status})",
                amount=plan_severance
            )
        
        return True
    
    def _create_capital_from_plan(self, plan_data, current_employer, retirement_year, termination_id):
        """יצירת נכס הון מתכנית"""
        plan_grants = plan_data['grants']
        plan_start_date = plan_data['plan_start_date']
        plan_name = plan_data['plan_name'] or "תכנית ללא שם"
        
        # חישוב סכומים לתכנית זו
        plan_severance = 0
        plan_exempt = 0
        
        for grant in plan_grants:
            calc_result = CurrentEmployerService.calculate_severance_grant(
                current_employer, grant
            )
            plan_severance += calc_result.indexed_amount
            plan_exempt += calc_result.grant_exempt
            logger.info(f"    💰 Grant for {plan_name}: {grant.grant_amount} ₪ (Exempt: {calc_result.grant_exempt:,.0f}, Taxable: {calc_result.grant_taxable:,.0f})")
        
        if plan_severance == 0:
            logger.info(f"  ℹ️ No severance amount for plan {plan_name}")
            return False
        
        # קביעת יחס מס
        exempt_ratio = plan_exempt / plan_severance if plan_severance > 0 else 0
        tax_treatment = "exempt" if exempt_ratio > 0.8 else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        ca = CapitalAsset(
            client_id=self.client_id,
            asset_name=f"פיצויי פרישה - {plan_name}",
            asset_type="severance",
            current_value=Decimal("0"),
            monthly_income=Decimal(str(plan_severance)),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="monthly",
            start_date=date(retirement_year, 1, 1),
            indexation_method="none",
            tax_treatment=tax_treatment,
            conversion_source=json.dumps({
                "source": "scenario_conversion",
                "scenario_type": "retirement",
                "termination_id": termination_id,
                "employer_id": current_employer.id,
                "plan_name": plan_name,
                "plan_start_date": plan_start_date.isoformat() if plan_start_date else None,
                "plan_severance": plan_severance,
                "plan_exempt": plan_exempt
            })
        )
        self.db.add(ca)
        
        logger.info(f"  ✅ Created capital asset for {plan_name}: {plan_severance:,.0f} ₪ ({tax_status})")
        
        if self.add_action:
            self.add_action(
                "conversion",
                f"שמירת פיצויי פרישה כנכס הוני - {plan_name} ({tax_status})",
                from_asset=f"פיצויים מ-{plan_name}: {plan_severance:,.0f} ₪ (פטור: {plan_exempt:,.0f})",
                to_asset=f"הון: {plan_severance:,.0f} ₪ ({tax_status})",
                amount=plan_severance
            )
        
        return True
