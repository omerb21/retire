"""
Maximum Capital Scenario
תרחיש מקסימום הון
"""
import logging
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
        
        # Step 0: Import pension portfolio if provided
        self._import_pension_portfolio_if_needed()
        
        # Step 0.5: Handle termination event - convert to capital
        self.termination_service.handle_termination_for_capital()
        
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
            return self._calculate_scenario_results("מקסימום הון (לא ניתן להיוון)")
        
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
        return self._calculate_scenario_results("מקסימום הון (קצבת מינימום: 5,500)")
    
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
    
    def _capitalize_pensions_keeping_minimum(self, sorted_pensions, total_pension_available):
        """היוון קצבאות תוך שמירת מינימום"""
        remaining_pension = total_pension_available
        
        for pf in sorted_pensions:
            if remaining_pension <= MINIMUM_PENSION:
                # Keep this pension
                tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
                logger.info(f"  ✅ Keeping pension: {pf.fund_name} ({pf.pension_amount} ₪) ({tax_status})")
                self._add_action(
                    "keep",
                    f"שמירת קצבה מינימום: {pf.fund_name} ({tax_status})",
                    from_asset="",
                    to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                    amount=0
                )
            else:
                # Check how much we can capitalize
                can_capitalize = remaining_pension - MINIMUM_PENSION
                
                if pf.pension_amount <= can_capitalize:
                    # Capitalize entire fund
                    self._capitalize_full_pension(pf)
                    remaining_pension -= pf.pension_amount
                else:
                    # Partial capitalization
                    self._capitalize_partial_pension(pf, can_capitalize)
                    remaining_pension = MINIMUM_PENSION
        
        self.db.flush()
        logger.info(f"  ✅ Final pension amount: {remaining_pension} ₪ (minimum: {MINIMUM_PENSION})")
    
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
            self.db.delete(pf)
    
    def _capitalize_partial_pension(self, pf, capitalize_amount):
        """היוון חלקי של קצבה"""
        keep_amount = pf.pension_amount - capitalize_amount
        tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
        
        capital_value = capitalize_amount * pf.annuity_factor
        
        # Create capital asset for capitalized part
        from decimal import Decimal
        import json
        ca = CapitalAsset(
            client_id=self.client_id,
            asset_name=f"הון מהיוון חלקי {pf.fund_name}",
            asset_type="provident_fund",
            current_value=Decimal("0"),
            monthly_income=Decimal(str(capital_value)),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="monthly",
            start_date=date(self._get_retirement_year(), 1, 1),
            indexation_method="none",
            tax_treatment=tax_treatment,
            conversion_source=json.dumps({
                "source": "scenario_conversion",
                "scenario_type": "retirement",
                "pension_fund": pf.fund_name,
                "partial": True,
                "tax_treatment": tax_treatment
            })
        )
        self.db.add(ca)
        
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
