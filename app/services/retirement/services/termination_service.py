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
from app.services.current_employer import TerminationService as CurrentEmployerTerminationService
from app.schemas.current_employer import TerminationDecisionCreate
from app.services.tax_data import TaxDataService
from app.services.annuity_coefficient import get_annuity_coefficient
from ..constants import PENSION_COEFFICIENT

logger = logging.getLogger("app.scenarios.termination")


class TerminationService:
    """שירות לטיפול באירועי עזיבת עבודה"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        add_action_callback: Optional[Callable] = None,
        use_current_employer_termination: bool = False,
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.add_action = add_action_callback
        self.use_current_employer_termination = use_current_employer_termination
    
    def _get_retirement_year(self, client: Client) -> int:
        """מחשב שנת פרישה"""
        if not client.birth_date:
            raise ValueError("תאריך לידה חסר")
        return client.birth_date.year + self.retirement_age
    
    def _calculate_max_spread_years(self, service_years: float) -> int:
        """חישוב שנות פריסת מס מקסימליות לפי שנות ותק (כמו בפרונט)"""
        if service_years >= 22:
            return 6
        if service_years >= 18:
            return 5
        if service_years >= 14:
            return 4
        if service_years >= 10:
            return 3
        if service_years >= 6:
            return 2
        if service_years >= 2:
            return 1
        return 0
    
    def _calculate_severance_breakdown(
        self,
        employer: CurrentEmployer,
        termination_date: date,
    ) -> Optional[dict]:
        """חישוב פיצויים, חלק פטור/חייב ושנות פריסה לתרחיש, לפי הלוגיקה של מסך מעסיק נוכחי.

        הלוגיקה מתיישרת עם הפרונט:
        - שנות ותק: CurrentEmployerService.calculate_service_years
        - סכום פיצויים: מקסימום בין expectedGrant (שכר אחרון * שנות ותק) לבין severance_accrued
        - תקרת פטור: תקרת פטור חודשית * שנות ותק (TaxDataService.get_current_severance_cap)
        - חלוקה לפטור/חייב + שנות פריסה מקסימליות
        """
        if not employer.start_date or not employer.last_salary:
            logger.info(
                "  ℹ️ Missing start_date or last_salary on CurrentEmployer, "
                "skipping severance calculation for scenario termination",
            )
            return None

        service_years = CurrentEmployerService.calculate_service_years(
            start_date=employer.start_date,
            end_date=termination_date,
            non_continuous_periods=employer.non_continuous_periods or [],
            continuity_years=getattr(employer, "continuity_years", 0.0),
        )

        max_spread_years = self._calculate_max_spread_years(service_years)

        severance_accrued = float(employer.severance_accrued or 0.0)
        expected_grant = float(employer.last_salary or 0.0) * float(service_years)

        if severance_accrued not in (0.0, None):
            severance_amount = severance_accrued
            severance_source = "employer_severance_accrued"
        else:
            severance_amount = expected_grant
            severance_source = "formula_last_salary_x_service_years"

        logger.info(
            "SCENARIO_SEVERANCE_AMOUNT_SOURCE client_id=%s employer_id=%s severance_source=%s employer_severance_accrued=%s formula_total=%s severance_total=%s",
            self.client_id,
            getattr(employer, "id", None),
            severance_source,
            getattr(employer, "severance_accrued", None),
            expected_grant,
            severance_amount,
        )

        logger.info(
            "SCENARIO_TERMINATION_SSOT client_id=%s employer_id=%s termination_date=%s employer_start_date=%s employer_last_salary=%s employer_severance_accrued=%s formula_total=%s severance_total=%s source_flags=%s",
            self.client_id,
            getattr(employer, "id", None),
            termination_date,
            getattr(employer, "start_date", None),
            getattr(employer, "last_salary", None),
            getattr(employer, "severance_accrued", None),
            expected_grant,
            severance_amount,
            {
                "used_accrued": severance_source == "employer_severance_accrued",
                "severance_source": severance_source,
            },
        )

        termination_year = termination_date.year
        try:
            monthly_cap = float(TaxDataService.get_current_severance_cap(termination_year))
        except Exception as e:
            logger.warning(
                "  ⚠️ Failed to get severance cap for year %s: %s, using fallback 13,750",
                termination_year,
                e,
            )
            monthly_cap = 13750.0

        exempt_cap_total = monthly_cap * float(service_years)
        exempt_amount = min(severance_amount, exempt_cap_total)
        taxable_amount = max(0.0, severance_amount - exempt_amount)

        logger.info(
            "  📊 Severance breakdown for scenario termination: "
            "service_years=%.2f, severance_amount=%.0f, exempt_amount=%.0f, "
            "taxable_amount=%.0f, max_spread_years=%d",
            service_years,
            severance_amount,
            exempt_amount,
            taxable_amount,
            max_spread_years,
        )

        return {
            "service_years": service_years,
            "severance_amount": severance_amount,
            "exempt_amount": exempt_amount,
            "taxable_amount": taxable_amount,
            "max_spread_years": max_spread_years,
        }

    def _build_termination_decision(
        self,
        employer: CurrentEmployer,
        termination_date: date,
        exempt_choice: str,
        taxable_choice: str,
        use_employer_completion: bool = True,
        source_accounts: Optional[str] = None,
        plan_details: Optional[str] = None,
    ) -> Optional[TerminationDecisionCreate]:
        """בניית TerminationDecisionCreate לתרחיש פרישה אחד.

        ההחלטה מבוססת על חישוב פיצויים (_calculate_severance_breakdown) ועל בחירות התרחיש
        (exempt_choice / taxable_choice). הטיפול בפועל יתבצע ע"י CurrentEmployerTerminationService.
        """
        breakdown = self._calculate_severance_breakdown(employer, termination_date)
        if not breakdown:
            return None

        severance_amount = float(breakdown["severance_amount"])
        exempt_amount = float(breakdown["exempt_amount"])
        taxable_amount = float(breakdown["taxable_amount"])
        max_spread_years = int(breakdown["max_spread_years"])

        decision = TerminationDecisionCreate(
            termination_date=termination_date,
            use_employer_completion=use_employer_completion,
            severance_amount=severance_amount,
            exempt_amount=exempt_amount,
            taxable_amount=taxable_amount,
            exempt_choice=exempt_choice,
            taxable_choice=taxable_choice,
            tax_spread_years=max_spread_years,
            max_spread_years=max_spread_years,
            confirmed=True,
            source_accounts=source_accounts,
            plan_details=plan_details,
        )

        logger.info(
            "  🧾 Built TerminationDecisionCreate for scenario: "
            "severance_amount=%.0f, exempt_amount=%.0f, taxable_amount=%.0f, "
            "exempt_choice=%s, taxable_choice=%s, spread_years=%d",
            severance_amount,
            exempt_amount,
            taxable_amount,
            exempt_choice,
            taxable_choice,
            max_spread_years,
        )

        return decision

    def run_current_employer_termination(
        self,
        exempt_choice: str,
        taxable_choice: str,
    ) -> None:
        """הרצת תהליך עזיבה מלא דרך שירות המעסיק הנוכחי עבור תרחיש פרישה.

        הפונקציה בונה החלטת עזיבה (TerminationDecisionCreate) על בסיס נתוני CurrentEmployer
        וחלוקת פטור/חייב, ומעבירה אותה לשירות המלא של current_employer.
        """
        # שליפת לקוח ומעסיק נוכחי
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        if not client:
            logger.info("  ℹ️ Client not found for termination scenario, skipping")
            return

        current_employer = (
            self.db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == self.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )

        if not current_employer:
            logger.info("  ℹ️ No current employer found for scenario termination, skipping")
            return

        # קביעת תאריך עזיבה: אם המשתמש הגדיר end_date במסך מעסיק נוכחי, זה מקור האמת.
        try:
            retirement_year = self._get_retirement_year(client)
            scenario_fallback_date = date(retirement_year, 1, 1)
            termination_date = current_employer.end_date or scenario_fallback_date

            logger.info(
                "SCENARIO_TERMINATION_DATE_SOURCE client_id=%s employer_id=%s employer_end_date=%s scenario_fallback_date=%s chosen_termination_date=%s source=%s",
                self.client_id,
                getattr(current_employer, "id", None),
                getattr(current_employer, "end_date", None),
                scenario_fallback_date,
                termination_date,
                "employer_end_date" if current_employer.end_date else "scenario_fallback",
            )
        except Exception as e:
            logger.warning(
                "  ⚠️ Failed to compute termination date for scenario termination: %s",
                e,
            )
            return

        decision = self._build_termination_decision(
            employer=current_employer,
            termination_date=termination_date,
            exempt_choice=exempt_choice,
            taxable_choice=taxable_choice,
            use_employer_completion=True,
            source_accounts=None,
            plan_details=None,
        )

        if not decision:
            logger.info("  ℹ️ Scenario termination decision could not be built, skipping")
            return

        termination_service = CurrentEmployerTerminationService(self.db)

        try:
            result = termination_service.process_termination(
                client,
                current_employer,
                decision,
                reset_severance_balance=False,
            )
            logger.info(
                "  ✅ CurrentEmployer termination processed for scenario "
                "(grant_id=%s, pension_id=%s, capital_id=%s)",
                result.get("created_grant_id"),
                result.get("created_pension_id"),
                result.get("created_capital_asset_id"),
            )
        except Exception as e:
            logger.error(
                "  ⚠️ Failed to process CurrentEmployer termination for scenario: %s",
                e,
            )

    def handle_termination_for_pension(self) -> None:
        """טיפול בעזיבת עבודה - בחירה בקצבה"""
        # ננסה קודם למצוא אירוע עזיבה (זרימה ישנה) – אך הלוגיקה מבוססת תמיד על CurrentEmployer + EmployerGrant
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()

        # מציאת מעביד נוכחי/אחרון עבור הלקוח (תומך גם בזרימה החדשה של מעסיק נוכחי)
        current_employer = (
            self.db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == self.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )

        if not current_employer:
            logger.info("  ℹ️ No current employer found for termination, skipping")
            return

        # מציאת כל מענקי הפיצויים של המעביד הנוכחי
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == current_employer.id,
            EmployerGrant.grant_type == GrantType.severance
        ).all()

        if not grants:
            logger.info("  ℹ️ No severance grants found for termination")
            return

        logger.info("  📝 Processing termination event for pension choice")

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
        termination_id = termination.id if termination else None
        for plan_key, plan_data in grants_by_plan.items():
            pension_created = self._create_pension_from_plan(
                plan_data,
                current_employer,
                client,
                pension_start_date,
                termination_id,
            )
            if pension_created:
                total_pensions_created += 1

        logger.info(f"  🎯 Total pensions created: {total_pensions_created}")
        self.db.flush()
    
    def handle_termination_for_capital(self) -> None:
        """טיפול בעזיבת עבודה - בחירה בהון"""
        # ננסה קודם למצוא אירוע עזיבה (אם קיים), אך נבסס את ההיוון על CurrentEmployer + EmployerGrant
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()

        # מציאת מעביד נוכחי/אחרון עבור הלקוח
        current_employer = (
            self.db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == self.client_id)
            .order_by(CurrentEmployer.id.desc())
            .first()
        )

        if not current_employer:
            logger.info("  ℹ️ No current employer found for termination, skipping")
            return

        # מציאת כל מענקי הפיצויים של המעביד הנוכחי
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == current_employer.id,
            EmployerGrant.grant_type == GrantType.severance
        ).all()

        if not grants:
            logger.info("  ℹ️ No severance grants found for termination")
            return

        logger.info("  📝 Processing termination event for capital choice")

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
        termination_id = termination.id if termination else None
        for plan_key, plan_data in grants_by_plan.items():
            asset_created = self._create_capital_from_plan(
                plan_data,
                current_employer,
                retirement_year,
                termination_id,
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
            }, ensure_ascii=False)
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
            }, ensure_ascii=False)
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
