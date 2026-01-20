"""
Maximum Capital Scenario
תרחיש מקסימום הון
"""
import logging
import json
from typing import Dict
from datetime import date
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from ..base_scenario_builder import BaseScenarioBuilder
from ..constants import MINIMUM_PENSION
from ..utils.capital_utils import create_capital_asset_from_pension
from ..utils.pension_utils import convert_balance_to_pension

logger = logging.getLogger("app.scenarios.max_capital")


class MaxCapitalScenario(BaseScenarioBuilder):
    """תרחיש 2: מקסימום הון (עם שמירת קצבת מינימום 5,500)"""
    
    def build_scenario(self) -> Dict:
        """בניית תרחיש מקסימום הון"""
        logger.info("📊 Building Scenario 2: Maximum Capital (with minimum pension)")
        self._log_scenario_start("מקסימום הון (קצבת מינימום: 5,500)")
        
        # Step 0: Import pension portfolio if provided
        self._import_pension_portfolio_if_needed()
        
        # Step 0.1: Apply 4% compound projection up to retirement date (if > ~6 months away)
        self._apply_retirement_projection_if_needed()
        
        # Step 0.5: Handle termination event - convert to capital
        if self.use_current_employer_termination:
            # תרחיש 2: מקסימום הון – פדיון החלק הפטור והחייב כמענק/הון (עם פריסת מס לחלק החייב)
            self.termination_service.run_current_employer_termination(
                exempt_choice="redeem_with_exemption",
                taxable_choice="redeem_no_exemption",
            )
        
        # Step 1: Convert all pension funds to pensions first (excluding education funds)
        self._convert_pension_funds_to_pension_first()
        
        # Step 1.5: Convert education funds to capital (keep as exempt capital)
        self.conversion_service.convert_education_funds_to_capital()
        
        # Step 2: Calculate total pension available
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        total_pension_available = sum(pf.pension_amount or 0 for pf in pension_funds)
        logger.info(f"  Total pension available: {total_pension_available} ₪")
        
        if total_pension_available < MINIMUM_PENSION:
            logger.warning(f"  ⚠️ Cannot capitalize - total pension {total_pension_available} < minimum {MINIMUM_PENSION}")
            # Convert everything to pension (can't capitalize at all)
            self.conversion_service.convert_all_pension_funds_to_pension()
            self.conversion_service.convert_taxable_capital_to_pension()
            self.conversion_service.convert_exempt_capital_to_pension()
            return self._calculate_scenario_results("מקסימום הון")
        
        # Step 3: Sort by annuity factor - capitalize worst quality first
        sorted_pensions = sorted(
            [pf for pf in pension_funds if pf.pension_amount and pf.annuity_factor],
            key=lambda p: p.annuity_factor,
            reverse=True  # Highest annuity factor first (worst quality)
        )
        
        # Step 4: Keep minimum pension, capitalize the rest
        self._capitalize_pensions_keeping_minimum(sorted_pensions, total_pension_available)
        
        # Step 5: Keep capital assets as is (DON'T convert to pension!)
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        logger.info(f"  ✅ Keeping {len(capital_assets)} capital assets as is")
        
        # Step 6: Verify
        self.conversion_service.verify_fixation_and_exempt_pension()
        
        # Step 7: Calculate and return
        results = self._calculate_scenario_results_with_capital("מקסימום הון (קצבת מינימום: 5,500)")
        self._log_scenario_complete("מקסימום הון (קצבת מינימום: 5,500)")
        return results
    
    def _convert_pension_funds_to_pension_first(self):
        """המרת קרנות פנסיה לקצבה בשלב ראשון"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for pf in pension_funds:
            if pf.balance and pf.annuity_factor:
                convert_balance_to_pension(pf, self._get_retirement_year(), self._add_action)
        
        self.db.flush()
    
    def _calculate_scenario_results_with_capital(self, scenario_name: str) -> Dict:
        """Calculate scenario results with adjusted capital aggregation for Max Capital."""
        # השתמש בלוגיקה הבסיסית לחישוב קצבאות, הכנסות נוספות ו-NPV
        results = self._calculate_scenario_results(scenario_name)

        # חישוב סך הון בפועל לפי נכסי הון הקיימים לאחר התרחיש
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()

        total_capital = 0.0
        for ca in capital_assets:
            value = 0.0

            # עדיפות לערך הון חד-פעמי אם קיים
            if ca.current_value is not None:
                try:
                    current_val = float(ca.current_value or 0)
                except (TypeError, ValueError):
                    current_val = 0.0
                if current_val > 0:
                    value = current_val

            # אם אין current_value חיובי – עבור לנכסי הון שמיוצגים כהכנסה חודשית
            if value <= 0 and ca.monthly_income is not None:
                try:
                    monthly_val = float(ca.monthly_income or 0)
                except (TypeError, ValueError):
                    monthly_val = 0.0
                if monthly_val > 0:
                    value = monthly_val

            total_capital += value

        results["total_capital"] = total_capital
        self.scenario_results = results
        return results
    
    def _get_max_capitalizable_pension(self, pf: PensionFund) -> float:
        """חישוב חלק הקצבה המקסימלי שניתן להוון להון לפי רכיבים מתיק פנסיוני"""
        pension_amount = float(pf.pension_amount or 0)
        if pension_amount <= 0:
            return 0.0

        conv_source = getattr(pf, "conversion_source", None)
        if not conv_source:
            # אם אין מידע על רכיבים – נאפשר היוון מלא של הקצבה
            return pension_amount

        try:
            source_data = json.loads(conv_source)
        except (TypeError, ValueError):
            return pension_amount

        source_type = source_data.get("type") or source_data.get("source")
        if source_type != "pension_portfolio":
            # קצבאות שלא יובאו מתיק פנסיוני אינן מוגבלות ברמת רכיב בתרחיש
            return pension_amount

        specific_amounts = source_data.get("specific_amounts") or {}
        if not isinstance(specific_amounts, dict):
            return 0.0

        # החלק המותר להמרה להון לפי הרכיבים שניתן להמיר להון בצד הפרונט:
        # - פיצויים לאחר התחשבנות (הוני)
        # - תגמולי עובד עד 2000 (הוני)
        # - תגמולי מעביד עד 2000 (הוני)
        convertible_balance = 0.0
        for field in (
            "פיצויים_לאחר_התחשבנות",
            "תגמולי_עובד_עד_2000",
            "תגמולי_מעביד_עד_2000",
        ):
            value = specific_amounts.get(field)
            try:
                convertible_balance += float(value or 0)
            except (TypeError, ValueError):
                continue

        if convertible_balance <= 0:
            return 0.0

        total_balance = float(
            source_data.get("original_balance")
            or source_data.get("amount")
            or pf.balance
            or 0.0
        )
        if total_balance <= 0:
            return 0.0

        ratio = convertible_balance / total_balance
        if ratio <= 0:
            return 0.0
        if ratio > 1:
            ratio = 1.0

        return pension_amount * ratio
    
    def _capitalize_pensions_keeping_minimum(self, sorted_pensions, total_pension_available):
        """היוון קצבאות תוך שמירת מינימום"""
        # סך הקצבה הזמינה לאחר כל ההמרות הראשוניות
        total_pension = float(total_pension_available or 0)

        # אם אין מספיק קצבה להגיע למינימום – לא מהוונים כלל
        if total_pension <= MINIMUM_PENSION:
            logger.info(
                f"  ℹ️ Total pension ({total_pension}) <= minimum ({MINIMUM_PENSION}), "
                "skipping capitalization of pensions"
            )
            return

        # כמה קצבה צריך להשאיר בסך הכול
        remaining_to_keep = float(MINIMUM_PENSION)

        # כדי לשמור את הקצבאות האיכותיות ביותר, נמיין לפי מקדם (מקדם נמוך יותר = קצבה טובה יותר)
        pensions_by_quality = sorted(
            sorted_pensions,
            key=lambda p: float(p.annuity_factor or 0) if getattr(p, "annuity_factor", None) is not None else 999999.0,
        )

        for pf in pensions_by_quality:
            pension_amount = float(pf.pension_amount or 0)
            if pension_amount <= 0:
                continue

            tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"

            if remaining_to_keep <= 0:
                # כבר הגענו לקצבת המינימום – את כל הקצבאות הנוספות מהוונים במלואן
                logger.info(
                    f"  💼 Capitalizing full pension above minimum: {pf.fund_name} "
                    f"({pension_amount} ₪) ({tax_status})"
                )
                self._capitalize_full_pension(pf)
                continue

            if pension_amount <= remaining_to_keep:
                # קצבה זו כולה דרושה כדי להגיע למינימום – נשאיר אותה כקצבה
                remaining_to_keep -= pension_amount
                logger.info(
                    f"  ✅ Keeping pension towards minimum: {pf.fund_name} "
                    f"({pension_amount} ₪) ({tax_status}), remaining_to_keep={remaining_to_keep}"
                )
                self._add_action(
                    "keep",
                    f"שמירת קצבה מינימום: {pf.fund_name} ({tax_status})",
                    from_asset="",
                    to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש ({tax_status})",
                    amount=0,
                )
            else:
                # צריך רק חלק מהקצבה הזו; שארית הקצבה תהוון להון
                capitalize_amount = pension_amount - remaining_to_keep
                logger.info(
                    f"  ⚖️ Partial capitalization to reach minimum: {pf.fund_name} - "
                    f"capitalize {capitalize_amount} ₪, keep {remaining_to_keep} ₪ ({tax_status})"
                )
                self._capitalize_partial_pension(pf, capitalize_amount)
                remaining_to_keep = 0.0

        # חישוב קצבה סופית לאחר כל ההיוונים
        final_pension = sum(float(pf.pension_amount or 0) for pf in pensions_by_quality)
        self.db.flush()
        logger.info(
            f"  ✅ Final pension amount after capitalization: {final_pension} ₪ "
            f"(target minimum: {MINIMUM_PENSION})"
        )
    
    def _capitalize_full_pension(self, pf):
        """היוון מלא של קצבה"""
        tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        ca = create_capital_asset_from_pension(
            pf,
            self.client_id,
            self._get_retirement_year(),
            partial=False,
            add_action_callback=self._add_action
        )
        
        if ca:
            self.db.add(ca)

            # היוון מלא בתרחיש – כמו במסך הקצבאות: הקצבה נשארת אך היתרה והקצבה החודשית מאופסות
            if pf.balance is not None:
                pf.balance = 0.0
            pf.pension_amount = 0.0
    
    def _capitalize_partial_pension(self, pf, capitalize_amount):
        """היוון חלקי של קצבה"""
        keep_amount = pf.pension_amount - capitalize_amount
        tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        capital_value = capitalize_amount * pf.annuity_factor
        
        # Create capital asset for capitalized part – מסומן כהיוון (COMMUTATION)
        from decimal import Decimal
        import json

        remarks = None
        if getattr(pf, "id", None) is not None:
            remarks = f"COMMUTATION:pension_fund_id={pf.id}&amount={capital_value}"

        # צילום הקצבה המקורית לפני ההיוון החלקי – לצורך שחזור מדויק במידת הצורך
        original_pension_snapshot = {
            "id": getattr(pf, "id", None),
            "fund_name": getattr(pf, "fund_name", None),
            "fund_type": getattr(pf, "fund_type", None),
            "input_mode": str(getattr(pf, "input_mode", None)) if getattr(pf, "input_mode", None) is not None else None,
            "balance": float(pf.balance) if getattr(pf, "balance", None) is not None else None,
            "annuity_factor": float(pf.annuity_factor) if getattr(pf, "annuity_factor", None) is not None else None,
            "pension_amount": float(pf.pension_amount) if getattr(pf, "pension_amount", None) is not None else None,
            "pension_start_date": pf.pension_start_date.isoformat() if getattr(pf, "pension_start_date", None) else None,
            "indexation_method": str(getattr(pf, "indexation_method", None)) if getattr(pf, "indexation_method", None) is not None else None,
            "tax_treatment": getattr(pf, "tax_treatment", None),
            "deduction_file": getattr(pf, "deduction_file", None),
            "remarks": getattr(pf, "remarks", None),
        }

        ca = CapitalAsset(
            client_id=self.client_id,
            asset_name=f"הון מהיוון חלקי {pf.fund_name}",
            asset_type="provident_fund",
            current_value=Decimal(str(capital_value)),
            monthly_income=Decimal("0"),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="annually",
            start_date=date(self._get_retirement_year(), 1, 1),
            indexation_method="none",
            tax_treatment=tax_treatment,
            remarks=remarks,
            conversion_source=json.dumps({
                "source": "scenario_conversion",  # זיהוי כתוצאה של תרחיש
                "scenario_type": "retirement",
                "source_type": "pension_fund",
                "type": "pension_commutation",  # מאפשר שחזור כמו במסך הקצבאות
                "pension_fund_id": getattr(pf, "id", None),
                "pension_fund": pf.fund_name,
                "partial": True,
                "tax_treatment": tax_treatment,
                "original_pension": original_pension_snapshot,
            }, ensure_ascii=False)
        )
        self.db.add(ca)
        
        if pf.balance is not None:
            pf.balance = max(0.0, (pf.balance or 0) - float(capital_value))
        
        # Update pension to keep minimum
        pf.pension_amount = keep_amount
        
        logger.info(f"  ⚖️ Partial capitalization: {pf.fund_name} - {capitalize_amount} ₪ → capital ({tax_status}), {keep_amount} ₪ remains pension")
        self._add_action(
            "capitalization",
            f"היוון חלקי של {pf.fund_name} ({tax_status})",
            from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount + capitalize_amount:,.0f} ₪/חודש)",
            to_asset=f"הון: {capital_value:,.0f} ₪ ({tax_status}) + קצבה: {keep_amount:,.0f} ₪/חודש",
            amount=capital_value
        )
