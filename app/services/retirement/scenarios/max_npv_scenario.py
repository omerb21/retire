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
        
        # Step 6: Calculate and return (עם חישוב הון מותאם כמו במקסימום הון)
        results = self._calculate_scenario_results_with_capital("מאוזן (50% קצבה, 50% הון)")
        self._log_scenario_complete("מאוזן (50% קצבה, 50% הון)")
        return results

    def _calculate_scenario_results_with_capital(self, scenario_name: str) -> Dict:
        """חישוב תוצאות תרחיש עם צבירת הון מותאמת לתרחיש 50/50.

        הלוגיקה זהה לזו של תרחיש מקסימום הון: עבור כל נכס הון נשתמש תחילה בערך חד-פעמי
        (current_value) אם הוא חיובי; ואם אין כזה, נשתמש בתשלום החודשי (monthly_income)
        אם הוא חיובי. כך סך ההון משקף גם נכסים שמיוצגים כתזרים חודשי בלבד.
        """
        results = self._calculate_scenario_results(scenario_name)

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
    
    def _get_pension_value_for_balancing(self, pf: PensionFund) -> float:
        """ערך הוני של קצבה לצורך איזון 50/50 בין קצבה להון."""
        try:
            if pf.balance is not None and float(pf.balance) > 0:
                return float(pf.balance)
        except (TypeError, ValueError):
            pass

        pension_amount = float(pf.pension_amount or 0)
        if pension_amount <= 0:
            return 0.0

        annuity_factor = getattr(pf, "annuity_factor", None)
        try:
            if annuity_factor is not None and float(annuity_factor) > 0:
                return pension_amount * float(annuity_factor)
        except (TypeError, ValueError):
            pass

        # נפילה לברירת מחדל – שימוש במקדם כללי כאשר אין נתוני מקדם/יתרה
        return pension_amount * PENSION_COEFFICIENT
    
    def _get_capital_value_for_balancing(self, ca: CapitalAsset) -> float:
        """ערך הוני של נכס הון לצורך איזון 50/50 (רק נכסים שמייצרים תזרים חודשי)."""
        try:
            income = float(ca.monthly_income or 0)
        except (TypeError, ValueError):
            income = 0.0
        if income > 0:
            return income
        return 0.0
    
    def _capitalize_half_of_pensions(self):
        """איזון בין קצבאות לנכסי הון כך שהערך ההוני של כל צד יתקרב ככל האפשר ל-50/50."""
        all_pensions = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()

        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()

        if not all_pensions:
            logger.info("  ℹ️ No pensions found for 50/50 balancing")
            return

        total_pension_monthly = sum(float(pf.pension_amount or 0) for pf in all_pensions)
        pension_value = sum(self._get_pension_value_for_balancing(pf) for pf in all_pensions)
        capital_value = sum(self._get_capital_value_for_balancing(ca) for ca in capital_assets)

        logger.info(
            f"  50/50 balancing (lump-sum values): pension={pension_value:,.0f}, capital={capital_value:,.0f}"
        )

        if pension_value <= 0 and capital_value <= 0:
            logger.info("  ℹ️ Nothing to balance (no pension or capital value)")
            return

        # אם כבר יש שווי כמעט שווה – אין צורך בשינוי
        if abs(pension_value - capital_value) < 1:
            logger.info("  ℹ️ Pension and capital values already balanced – skipping rebalancing")
            return

        # ענף 1: קצבאות גבוהות מהון – מבצעים היוון כמו במקסימום הון, עד לאיזון / קצבת מינימום
        if pension_value > capital_value:
            if total_pension_monthly <= MINIMUM_PENSION:
                logger.warning(
                    f"  ⚠️ Cannot capitalize for 50/50 – total pension {total_pension_monthly} ≤ minimum {MINIMUM_PENSION}"
                )
                return

            total_value = pension_value + capital_value
            target_each_side = total_value / 2.0
            required_capitalization_value = max(0.0, pension_value - target_each_side)

            # מגבלת חוק: אסור לרדת מקצבת מינימום
            max_by_minimum = max(
                0.0, (total_pension_monthly - MINIMUM_PENSION) * PENSION_COEFFICIENT
            )

            target_capitalize_value = min(required_capitalization_value, max_by_minimum)

            logger.info(
                "  Target pension→capital for 50/50: "
                f"required={required_capitalization_value:,.0f}, "
                f"max_by_minimum={max_by_minimum:,.0f}, "
                f"final_target={target_capitalize_value:,.0f}"
            )

            if target_capitalize_value <= 0:
                logger.info("  ℹ️ No room to capitalize without breaching minimum pension")
                return

            self._perform_capitalization(all_pensions, target_capitalize_value, total_pension_monthly)
            self.db.flush()
            return

        # ענף 2: הון גבוה מקצבאות – ממירים חלק מנכסי ההון לקצבאות עד לאיזון
        self._rebalance_capital_to_pension_for_50_50(
            capital_assets,
            pension_value,
            capital_value,
        )
        self.db.flush()
    
    def _perform_capitalization(self, all_pensions, target_capitalize_value, total_pension_monthly):
        """ביצוע היוון בפועל כאשר הקצבאות גבוהות מההון."""
        # Sort by annuity factor (worst quality first)
        sorted_pensions = sorted(
            [pf for pf in all_pensions if pf.pension_amount and pf.annuity_factor],
            key=lambda p: p.annuity_factor,
            reverse=True  # Highest annuity factor first (worst quality)
        )

        capitalized_value = 0.0
        remaining_pension = float(total_pension_monthly or 0.0)

        for pf in sorted_pensions:
            if capitalized_value >= target_capitalize_value or remaining_pension <= MINIMUM_PENSION:
                logger.info(f"  ✅ Keeping pension: {pf.fund_name} ({pf.pension_amount} ₪)")
                continue

            pf_value = float(pf.pension_amount or 0) * float(pf.annuity_factor or 0)
            need_to_capitalize = target_capitalize_value - capitalized_value

            if pf_value <= 0 or need_to_capitalize <= 0:
                continue

            # בדיקה האם ניתן להוון מבלי לרדת מתחת לקצבת המינימום
            can_capitalize_amount = max(0.0, min(float(pf.pension_amount or 0), remaining_pension - MINIMUM_PENSION))

            # מגבלה נוספת: רק החלק שניתן להוון לפי רכיבים (תגמולים עד 2000, פיצויים לאחר התחשבנות וכו')
            max_by_components_monthly = self._get_max_capitalizable_pension(pf)
            max_by_components_value = max_by_components_monthly * float(pf.annuity_factor or 0)

            allowed_value_for_fund = min(
                need_to_capitalize,
                max_by_components_value,
                can_capitalize_amount * float(pf.annuity_factor or 0),
                pf_value,
            )

            if allowed_value_for_fund <= 0:
                logger.info(
                    f"  ✅ Keeping pension (no convertible components left): {pf.fund_name} ({pf.pension_amount} ₪)"
                )
                continue

            if pf_value <= allowed_value_for_fund + 1e-6:
                # Capitalize entire fund במסגרת המגבלות
                self._capitalize_full_fund(pf, pf_value)
                capitalized_value += pf_value
                remaining_pension -= float(pf.pension_amount or 0)
            else:
                # Partial capitalization – רק עד החלק המותר לפי רכיבים ומינימום קצבה
                self._capitalize_partial_fund(pf, allowed_value_for_fund)
                capitalized_value += allowed_value_for_fund

        logger.info(f"  ✅ Capitalized {capitalized_value:,.0f} ₪ (target: {target_capitalize_value:,.0f})")

    def _rebalance_capital_to_pension_for_50_50(
        self,
        capital_assets,
        pension_value: float,
        capital_value: float,
    ) -> None:
        """המרת נכסי הון לקצבאות עד שאיזון 50/50 בין קצבה להון מושג ככל האפשר."""
        if capital_value <= pension_value:
            logger.info("  ℹ️ No need to convert capital to pension (capital ≤ pension)")
            return

        total_value = pension_value + capital_value
        target_each_side = total_value / 2.0
        required_conversion_value = max(0.0, capital_value - target_each_side)

        logger.info(
            f"  Target capital→pension conversion for 50/50: {required_conversion_value:,.0f}"
        )

        # נכלול רק נכסי הון שמייצרים תזרים חודשי
        eligible_assets = [
            ca for ca in capital_assets
            if self._get_capital_value_for_balancing(ca) > 0
        ]

        if not eligible_assets or required_conversion_value <= 0:
            logger.info("  ℹ️ No eligible capital assets for conversion to pension")
            return

        # נמיין מהגדול לקטן כדי לצמצם מספר הנכסים שבהם מבוצעת המרה
        eligible_assets.sort(
            key=lambda ca: self._get_capital_value_for_balancing(ca),
            reverse=True,
        )

        remaining_to_convert = required_conversion_value

        for ca in eligible_assets:
            if remaining_to_convert <= 0:
                break

            full_value = self._get_capital_value_for_balancing(ca)
            if full_value <= 0:
                continue

            convert_value = min(full_value, remaining_to_convert)
            self._convert_capital_asset_partial_to_pension(ca, convert_value)
            remaining_to_convert -= convert_value

        logger.info(
            f"  ✅ Converted capital to pension for 50/50: target={required_conversion_value:,.0f}, "
            f"unconverted={max(0.0, remaining_to_convert):,.0f}"
        )

    def _convert_capital_asset_partial_to_pension(self, ca: CapitalAsset, convert_value: float) -> None:
        """המרה חלקית/מלאה של נכס הון לקצבה לצורך איזון 50/50."""
        try:
            full_value = float(ca.monthly_income or 0)
        except (TypeError, ValueError):
            full_value = 0.0

        if convert_value <= 0 or full_value <= 0:
            return

        convert_value = min(convert_value, full_value)
        remaining_value = full_value - convert_value

        tax_treatment = ca.tax_treatment if getattr(ca, "tax_treatment", None) else "taxable"
        tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"

        pension_amount = convert_value / PENSION_COEFFICIENT

        pf = PensionFund(
            client_id=self.client_id,
            fund_name=f"קרן פנסיה שנוצרה מ{ca.asset_name}",
            fund_type="converted_capital",
            input_mode="manual",
            pension_amount=pension_amount,
            pension_start_date=date(self._get_retirement_year(), 1, 1),
            indexation_method="none",
            tax_treatment=tax_treatment,
            conversion_source=json.dumps({
                "source_type": "capital_asset",
                "source_id": getattr(ca, "id", None),
                "source_name": ca.asset_name,
                "original_value": convert_value,
                "tax_treatment": tax_treatment,
                "partial": convert_value < full_value,
            }),
        )
        self.db.add(pf)

        from decimal import Decimal

        if remaining_value > 0:
            ca.monthly_income = Decimal(str(remaining_value))
        else:
            # לא מוחקים את הנכס כדי לשמור עקיבות, רק מאפסים את הזרם החודשי
            ca.monthly_income = Decimal("0")

        logger.info(
            f"  🔁 Converted capital asset '{ca.asset_name}': {convert_value:,.0f} → "
            f"Pension {pension_amount:,.0f} ₪/month ({tax_status}), remaining capital={remaining_value:,.0f}"
        )

        self._add_action(
            "conversion",
            f"המרת נכס הון לקצבה לצורך איזון 50/50: {ca.asset_name} ({tax_status})",
            from_asset=f"הון: {ca.asset_name}",
            to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש ({tax_status})",
            amount=convert_value,
        )
    
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
