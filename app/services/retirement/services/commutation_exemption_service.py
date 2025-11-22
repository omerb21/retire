import logging
import json
import re
from datetime import date
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.fixation_result import FixationResult
from app.models.pension_fund import PensionFund
from app.services.retirement.constants import DEFAULT_DISCOUNT_RATE


logger = logging.getLogger("app.scenarios.commutation_exemption")


class CommutationExemptionService:
    """שירות לניצול הון פטור על היוונים (COMMUTATION) בתרחישי פרישה.

    הלוגיקה מיועדת בעיקר לתרחיש מקסימום הון:
    כל עוד יש יתרת הון פטורה לאחר קיזוזים (exempt_capital_remaining),
    נעבור על היוונים שנוצרו מהתרחיש עם יחס מס "taxable" ונסמן אותם כ"exempt",
    עד שננצל את ההון הפטור ככל האפשר.
    """

    def __init__(self, db: Session, client_id: int) -> None:
        self.db = db
        self.client_id = client_id

    def _extract_commutation_amount(self, asset: CapitalAsset) -> float:
        """מוציא את סכום ההיוון מהערת COMMUTATION או משדות הסכום."""
        amount: float = 0.0

        if asset.remarks:
            match = re.search(r"amount=([\d.]+)", asset.remarks)
            if match:
                try:
                    amount = float(match.group(1))
                except (TypeError, ValueError):
                    amount = 0.0

        if amount <= 0:
            # נפילה לערכים בפועל אם אין amount ב-remarks
            if asset.current_value is not None:
                try:
                    amount = float(asset.current_value)
                except (TypeError, ValueError):
                    amount = 0.0
            elif asset.monthly_income is not None:
                try:
                    amount = float(asset.monthly_income)
                except (TypeError, ValueError):
                    amount = 0.0

        return max(0.0, amount)

    def _update_remarks_amount(self, remarks: str, new_amount: float) -> str:
        """עדכון ערך amount= בהערת COMMUTATION מבלי לשנות מידע נוסף."""
        if not remarks:
            return remarks
        try:
            return re.sub(r"amount=([\d.]+)", f"amount={new_amount}", remarks)
        except re.error:
            return remarks

    def _apply_partial_exemption(
        self,
        asset: CapitalAsset,
        amount: float,
        remaining_exempt: float,
    ) -> float:
        """החלת פטור חלקי על היוון יחיד באמצעות פיצול הנכס ההוני.

        יוצרת נכס הון חדש עבור החלק הפטור (tax_treatment="exempt") ומשאירה
        את שארית הסכום בנכס המקורי כחייב במס. מחזירה את סכום ההון הפטור
        שנוצל בפועל (לרוב כל remaining_exempt).
        """
        use_amount = min(float(remaining_exempt or 0.0), float(amount or 0.0))
        if use_amount <= 0.0 or amount <= 0.0:
            return 0.0

        # זיהוי השדה שבו מיוצג סכום ההיוון בפועל
        value_field = None
        full_value = 0.0
        try:
            if asset.current_value is not None and float(asset.current_value) > 0:
                value_field = "current_value"
                full_value = float(asset.current_value)
            elif asset.monthly_income is not None and float(asset.monthly_income) > 0:
                value_field = "monthly_income"
                full_value = float(asset.monthly_income)
        except (TypeError, ValueError):
            full_value = 0.0

        if full_value <= 0.0:
            # fallback לערך שהופק מהערות
            full_value = float(amount)

        taxable_remainder = max(0.0, full_value - use_amount)

        # עדכון הנכס המקורי כך שייצג רק את החלק החייב במס
        try:
            if value_field == "current_value":
                asset.current_value = Decimal(str(taxable_remainder))
            else:
                # ברירת מחדל – מרבית ההיוונים מיוצגים כהכנסה חודשית
                asset.monthly_income = Decimal(str(taxable_remainder))
        except Exception:
            # אם יש בעיה בעדכון, נעדיף לא לשבור את התהליך
            pass

        # עדכון ההערות כך שסכום ה"amount" יתאים לחלק החייב
        if asset.remarks:
            asset.remarks = self._update_remarks_amount(asset.remarks, taxable_remainder)

        # עדכון conversion_source לחלק החייב
        try:
            if asset.conversion_source:
                src = json.loads(asset.conversion_source)
                if isinstance(src, dict):
                    src["tax_treatment"] = "taxable"
                    src["partial_exemption"] = True
                    src["exempt_amount"] = use_amount
                    src["taxable_remainder"] = taxable_remainder
                    asset.conversion_source = json.dumps(src)
        except Exception:
            # לא נכשיל בגלל בעיית JSON
            pass

        # יצירת נכס הון חדש עבור החלק הפטור
        exempt_remarks = self._update_remarks_amount(asset.remarks or "", use_amount)
        try:
            src_for_exempt = json.loads(asset.conversion_source) if asset.conversion_source else {}
        except Exception:
            src_for_exempt = {}

        if isinstance(src_for_exempt, dict):
            src_for_exempt["tax_treatment"] = "exempt"
            src_for_exempt["partial_exemption"] = True
            src_for_exempt["exempt_amount"] = use_amount
            src_for_exempt["taxable_remainder"] = taxable_remainder

        exempt_asset = CapitalAsset(
            client_id=asset.client_id,
            asset_name=(asset.asset_name or "היוון") + " (חלק פטור)",
            asset_type=asset.asset_type,
            description=asset.description,
            current_value=Decimal("0") if value_field != "current_value" else Decimal(str(use_amount)),
            monthly_income=Decimal(str(use_amount)) if value_field != "current_value" else asset.monthly_income,
            rental_income=asset.rental_income,
            monthly_rental_income=asset.monthly_rental_income,
            annual_return_rate=asset.annual_return_rate,
            payment_frequency=asset.payment_frequency,
            start_date=asset.start_date,
            end_date=asset.end_date,
            indexation_method=asset.indexation_method,
            fixed_rate=asset.fixed_rate,
            tax_treatment="exempt",
            tax_rate=asset.tax_rate,
            spread_years=asset.spread_years,
            original_principal=asset.original_principal,
            remarks=exempt_remarks,
            conversion_source=json.dumps(src_for_exempt) if isinstance(src_for_exempt, dict) else asset.conversion_source,
        )

        self.db.add(exempt_asset)

        logger.info(
            "  → Created partial exempt commutation asset (id=%s) for %.2f out of %.2f on original asset id=%s",
            getattr(exempt_asset, "id", None),
            use_amount,
            amount,
            getattr(asset, "id", None),
        )

        return use_amount

    def _load_scenario_commutations(self) -> List[Tuple[CapitalAsset, float]]:
        """מחזיר רשימת היוונים מהתרחיש עם הסכום שלהם.

        אנחנו מגבילים להיוונים שנוצרו מהתרחיש עצמו באמצעות conversion_source,
        כדי לא לגעת בהיוונים ידניים שהמשתמש יצר.
        """
        assets: List[CapitalAsset] = (
            self.db.query(CapitalAsset)
            .filter(
                CapitalAsset.client_id == self.client_id,
                CapitalAsset.conversion_source.isnot(None),
                CapitalAsset.conversion_source.like('%"source": "scenario_conversion"%'),
                CapitalAsset.remarks.isnot(None),
                CapitalAsset.remarks.like('%COMMUTATION:%'),
                CapitalAsset.tax_treatment == "taxable",
            )
            .all()
        )

        result: List[Tuple[CapitalAsset, float]] = []
        for asset in assets:
            amount = self._extract_commutation_amount(asset)
            if amount > 0:
                result.append((asset, amount))

        # מיון מהסכומים הקטנים לגדולים כדי למקסם ניצול הון פטור (להשאיר שארית מינימלית)
        result.sort(key=lambda item: item[1])
        return result

    def apply_exempt_capital_to_scenario_commutations(self, fixation: FixationResult) -> None:
        """ניצול יתרת הון פטורה על היווני תרחיש ושינוי יחס המס שלהם לחייב/פטור.

        לוגיקה:
        - לוקחים את exempt_capital_remaining מקיבוע הזכויות.
        - מאתרים את כל נכסי ההון מהתרחיש שהם COMMUTATION וחייבים במס.
        - עוברים עליהם מהסכום הקטן לגדול.
        - לכל היוון שסכומו קטן או שווה ליתרה הפטורה:
          * משנים tax_treatment ל-"exempt".
          * מעדכנים conversion_source.tax_treatment אם קיים.
          * מקטינים את exempt_capital_remaining ומגדילים used_commutation.
        - מעדכנים את רשומת הקיבוע (FixationResult) בהתאם.
        """
        remaining_exempt = float(fixation.exempt_capital_remaining or 0.0)
        if remaining_exempt <= 0:
            logger.info(
                "CommutationExemptionService: no exempt capital remaining for client %s, skipping",
                self.client_id,
            )
            return

        commutations = self._load_scenario_commutations()
        if not commutations:
            logger.info(
                "CommutationExemptionService: no scenario commutations found for client %s",
                self.client_id,
            )
            return

        logger.info(
            "CommutationExemptionService: starting allocation of exempt capital %.2f on %d commutations for client %s",
            remaining_exempt,
            len(commutations),
            self.client_id,
        )

        used_total = 0.0

        for asset, amount in commutations:
            if remaining_exempt <= 0:
                break

            # אם יש מספיק הון פטור לכיסוי מלא של ההיוון – נסמן את כולו כפטור
            if remaining_exempt + 1e-2 >= amount:
                logger.info(
                    "  → Applying exempt capital %.2f on commutation '%s' (amount=%.2f, asset_id=%s)",
                    amount,
                    asset.asset_name,
                    amount,
                    getattr(asset, "id", None),
                )

                asset.tax_treatment = "exempt"

                # עדכון conversion_source.tax_treatment אם יש JSON תקין
                try:
                    if asset.conversion_source:
                        src = json.loads(asset.conversion_source)
                        if isinstance(src, dict):
                            src["tax_treatment"] = "exempt"
                            asset.conversion_source = json.dumps(src)
                except Exception as e:  # לא נכשיל תהליך בגלל בעיית JSON
                    logger.warning(
                        "  ⚠️ Failed to update conversion_source for capital asset %s: %s",
                        getattr(asset, "id", None),
                        e,
                    )

                remaining_exempt -= amount
                used_total += amount
                continue

            # אין מספיק הון פטור לכיסוי מלא של ההיוון – ננסה פטור חלקי על ההיוון הקטן ביותר שנותר
            partial_used = self._apply_partial_exemption(asset, amount, remaining_exempt)
            if partial_used > 0:
                used_total += partial_used
                remaining_exempt -= partial_used
            # לאחר פטור חלקי ננצל את כל היתרה ונצא מהלולאה
            break

        if used_total <= 0:
            logger.info(
                "CommutationExemptionService: no commutations were updated for client %s (remaining_exempt=%.2f)",
                self.client_id,
                remaining_exempt,
            )
            return

        # עדכון רשומת הקיבוע
        previous_used = float(fixation.used_commutation or 0.0)
        fixation.used_commutation = previous_used + used_total
        fixation.exempt_capital_remaining = max(0.0, remaining_exempt)

        # נסה לעדכן גם את ה-exemption_summary בתוך raw_result אם קיים
        try:
            raw = fixation.raw_result or {}
            if isinstance(raw, dict):
                exemption_summary = raw.get("exemption_summary") or {}
                exemption_summary["remaining_exempt_capital"] = fixation.exempt_capital_remaining
                raw["exemption_summary"] = exemption_summary
                fixation.raw_result = raw
        except Exception as e:
            logger.warning(
                "  ⚠️ Failed to update fixation.raw_result for client %s: %s",
                self.client_id,
                e,
            )

        self.db.flush()
        logger.info(
            "CommutationExemptionService: used %.2f exempt capital on commutations for client %s; remaining_exempt=%.2f",
            used_total,
            self.client_id,
            fixation.exempt_capital_remaining,
        )

    def calculate_exempt_commutations_npv(
        self,
        discount_rate: float = DEFAULT_DISCOUNT_RATE,
    ) -> float:
        """מחשב NPV של ההטבה ממס על היוונים פטורים (COMMUTATION) עבור לקוח.

        הלוגיקה מתבססת על נכסי הון שהם COMMUTATION עם יחס מס "exempt" לאחר קיבוע,
        בדומה לטבלת ההיוונים במסך קיבוע הזכויות לאחר הסינון שם.

        עבור כל היוון פטור, נזהה את סכום ההיוון ואת תאריך ההיוון, ונחשב את הערך
        הנוכחי שלו כתשלום חד-פעמי במועד ההיוון, בהיוון לפי שיעור ברירת המחדל.
        """
        try:
            today = date.today()

            assets: List[CapitalAsset] = (
                self.db.query(CapitalAsset)
                .filter(
                    CapitalAsset.client_id == self.client_id,
                    CapitalAsset.remarks.isnot(None),
                    CapitalAsset.remarks.like("%COMMUTATION:%"),
                    CapitalAsset.tax_treatment == "exempt",
                )
                .all()
            )

            if not assets:
                return 0.0

            total_pv = 0.0

            for asset in assets:
                amount = self._extract_commutation_amount(asset)
                if amount <= 0:
                    continue

                # סינון היוונים שמקורם בקצבה פטורה ממס, בדומה למסך הקיבוע
                pension_fund_id = None
                try:
                    if asset.remarks:
                        match = re.search(r"pension_fund_id=(\d+)", asset.remarks)
                        if match:
                            pension_fund_id = int(match.group(1))
                except Exception:
                    pension_fund_id = None

                if pension_fund_id:
                    fund = (
                        self.db.query(PensionFund)
                        .filter(
                            PensionFund.id == pension_fund_id,
                            PensionFund.client_id == self.client_id,
                        )
                        .first()
                    )
                    if fund and getattr(fund, "tax_treatment", None) == "exempt":
                        # קצבה שהייתה פטורה גם בלי קיבוע – לא נספור את ההיוון שלה כהטבה
                        continue

                commutation_date = asset.start_date or getattr(asset, "purchase_date", None)

                years_from_now = 0.0
                try:
                    if isinstance(commutation_date, date):
                        delta_days = (commutation_date - today).days
                        if delta_days > 0:
                            years_from_now = delta_days / 365.25
                except Exception:
                    years_from_now = 0.0

                if discount_rate and discount_rate > 0:
                    pv = amount / ((1 + float(discount_rate)) ** years_from_now)
                else:
                    pv = amount

                total_pv += pv

            return round(total_pv, 2)

        except Exception as e:
            logger.error(
                "CommutationExemptionService: failed to calculate exempt commutations NPV for client %s: %s",
                self.client_id,
                e,
            )
            return 0.0
