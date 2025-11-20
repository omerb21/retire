"""
Maximum NPV Scenario (Balanced 50/50)
תרחיש מאוזן - מקסימום NPV
"""
import logging
from typing import Dict
from datetime import date
from decimal import Decimal
import json
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from ..base_scenario_builder import BaseScenarioBuilder
from ..constants import MINIMUM_PENSION, PENSION_COEFFICIENT
from ..utils.pension_utils import convert_balance_to_pension

logger = logging.getLogger("app.scenarios.max_npv")


class MaxNPVScenario(BaseScenarioBuilder):
    """תרחיש 3: מאוזן - 50% ערך כקצבה, 50% ערך כהון"""
    
    def build_scenario(self) -> Dict:
        """בניית תרחיש מאוזן"""
        logger.info("📊 Building Scenario 3: Balanced (50/50 Split)")
        self._log_scenario_start("מאוזן (50% קצבה, 50% הון)")
        
        # Step 0: Import pension portfolio if provided
        self._import_pension_portfolio_if_needed()
        
        # Step 0.1: Apply 4% compound projection up to retirement date (if > ~6 months away)
        self._apply_retirement_projection_if_needed()
        
        # Step 0.5: Handle termination event - convert to capital first
        if self.use_current_employer_termination:
            # תרחיש 3: מאוזן – חלק פטור כהון, חלק חייב כקצבה
            self.termination_service.run_current_employer_termination(
                exempt_choice="redeem_with_exemption",
                taxable_choice="annuity",
            )
        else:
            self.termination_service.handle_termination_for_capital()
        
        # Step 1: Convert education funds to capital (keep as exempt capital)
        self.conversion_service.convert_education_funds_to_capital()
        
        # Step 2: Convert pension funds to pensions (excluding education funds)
        self._convert_pension_funds_to_pension()
        
        # Step 3: Keep existing capital assets as is
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        total_capital_monthly = sum(float(ca.monthly_income or 0) for ca in capital_assets)
        logger.info(f"  ✅ Keeping {len(capital_assets)} capital assets ({total_capital_monthly:,.0f} ₪/month) as is")
        
        # Step 4: Capitalize half (50%) of the PENSION FUNDS value only
        self._capitalize_half_of_pensions()
        
        # Step 5: Verify
        self.conversion_service.verify_fixation_and_exempt_pension()
        
        # Step 6: Calculate and return
        results = self._calculate_scenario_results("מאוזן (50% קצבה, 50% הון)")
        self._log_scenario_complete("מאוזן (50% קצבה, 50% הון)")
        return results
    
    def _convert_pension_funds_to_pension(self):
        """המרת קרנות פנסיה לקצבה"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for pf in pension_funds:
            if pf.balance and pf.annuity_factor:
                convert_balance_to_pension(pf, self._get_retirement_year(), self._add_action)
        
        self.db.flush()
    
    def _capitalize_half_of_pensions(self):
        """היוון חצי מהקצבאות"""
        all_pensions = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        total_pension_amount = sum(pf.pension_amount or 0 for pf in all_pensions)
        logger.info(f"  Total pension amount available: {total_pension_amount} ₪/month")
        
        # Check if we can capitalize at all
        if total_pension_amount < MINIMUM_PENSION:
            logger.warning(f"  ⚠️ Cannot capitalize - total pension {total_pension_amount} < minimum {MINIMUM_PENSION}")
            return
        
        total_pension_value_now = sum(
            pf.pension_amount * pf.annuity_factor
            for pf in all_pensions
            if pf.pension_amount and pf.annuity_factor
        )
        
        # Calculate target: try to keep minimum pension and capitalize the rest
        # But don't exceed 50% of total value
        max_can_capitalize = (total_pension_amount - MINIMUM_PENSION) * PENSION_COEFFICIENT
        target_capitalize_value = min(total_pension_value_now * 0.5, max_can_capitalize)
        
        logger.info(f"  Target to capitalize: {target_capitalize_value} (max 50% or keep min pension)")
        
        if target_capitalize_value > 0:
            self._perform_capitalization(all_pensions, target_capitalize_value, total_pension_amount)
        
        self.db.flush()
    
    def _perform_capitalization(self, all_pensions, target_capitalize_value, total_pension_amount):
        """ביצוע היוון בפועל"""
        # Sort by annuity factor (worst quality first)
        sorted_pensions = sorted(
            [pf for pf in all_pensions if pf.pension_amount and pf.annuity_factor],
            key=lambda p: p.annuity_factor,
            reverse=True  # Highest annuity factor first (worst quality)
        )
        
        capitalized_value = 0
        remaining_pension = total_pension_amount
        
        for pf in sorted_pensions:
            if capitalized_value >= target_capitalize_value or remaining_pension <= MINIMUM_PENSION:
                logger.info(f"  ✅ Keeping pension: {pf.fund_name} ({pf.pension_amount} ₪)")
                continue
            
            pf_value = pf.pension_amount * pf.annuity_factor
            need_to_capitalize = target_capitalize_value - capitalized_value
            
            # Check if we can capitalize without going below minimum
            can_capitalize_amount = min(pf.pension_amount, remaining_pension - MINIMUM_PENSION)
            
            if can_capitalize_amount <= 0:
                logger.info(f"  ✅ Keeping pension: {pf.fund_name} (at minimum)")
                continue
            
            if pf_value <= need_to_capitalize and can_capitalize_amount >= pf.pension_amount:
                # Capitalize entire fund
                self._capitalize_full_fund(pf, pf_value)
                capitalized_value += pf_value
                remaining_pension -= pf.pension_amount
            else:
                # Partial capitalization
                self._capitalize_partial_fund(pf, need_to_capitalize)
                capitalized_value += need_to_capitalize
        
        logger.info(f"  ✅ Capitalized {capitalized_value} ₪ (target: {target_capitalize_value})")
    
    def _capitalize_full_fund(self, pf, pf_value):
        """היוון מלא של קרן"""
        tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        remarks = None
        if getattr(pf, "id", None) is not None:
            remarks = f"COMMUTATION:pension_fund_id={pf.id}&amount={pf_value}"

        # צילום מלא של הקצבה לפני ההיוון – לשחזור מדויק ממסך הקצבאות
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
            asset_name=f"הון מהיוון {pf.fund_name}",
            asset_type="provident_fund",
            current_value=Decimal("0"),
            monthly_income=Decimal(str(pf_value)),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="monthly",
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
                "tax_treatment": tax_treatment,
                "original_pension": original_pension_snapshot,
            })
        )
        self.db.add(ca)
        
        logger.info(f"  Full capitalization: {pf.fund_name} → {pf_value} ₪ capital ({tax_status})")
        self._add_action(
            "capitalization",
            f"היוון מלא (50%): {pf.fund_name} ({tax_status})",
            from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount:,.0f} ₪/חודש)",
            to_asset=f"הון: {pf_value:,.0f} ₪ ({tax_status})",
            amount=pf_value
        )

        # בתרחיש מאוזן – כמו במסך הקצבאות: הקצבה נשארת אך היתרה והקצבה החודשית מאופסות
        if pf.balance is not None:
            pf.balance = 0.0
        pf.pension_amount = 0.0
    
    def _capitalize_partial_fund(self, pf, need_to_capitalize):
        """היוון חלקי של קרן"""
        remaining_pension_value = (pf.pension_amount * pf.annuity_factor) - need_to_capitalize
        new_pension_amount = remaining_pension_value / pf.annuity_factor
        tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        remarks = None
        if getattr(pf, "id", None) is not None:
            remarks = f"COMMUTATION:pension_fund_id={pf.id}&amount={need_to_capitalize}"

        # צילום מלא של הקצבה לפני ההיוון החלקי – לשחזור מדויק במידת הצורך
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
            current_value=Decimal("0"),
            monthly_income=Decimal(str(need_to_capitalize)),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="monthly",
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
                "partial": True,
                "tax_treatment": tax_treatment,
                "original_pension": original_pension_snapshot,
            })
        )
        self.db.add(ca)
        
        if pf.balance is not None:
            pf.balance = max(0.0, remaining_pension_value)
        
        original_pension_amount = pf.pension_amount
        pf.pension_amount = new_pension_amount
        
        logger.info(f"  ⚖️ Partial capitalization: {pf.fund_name} - {need_to_capitalize} ₪ → capital ({tax_status}), {new_pension_amount} ₪ remains pension")
        self._add_action(
            "capitalization",
            f"היוון חלקי (50%): {pf.fund_name} ({tax_status})",
            from_asset=f"קצבה: {pf.fund_name} ({original_pension_amount:,.0f} ₪/חודש)",
            to_asset=f"הון: {need_to_capitalize:,.0f} ₪ ({tax_status}) + קצבה: {new_pension_amount:,.0f} ₪/חודש",
            amount=need_to_capitalize
        )
