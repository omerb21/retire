import logging
import json
import re
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.fixation_result import FixationResult


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

            # נדרשת כיסוי מלא של ההיוון כדי לסמן אותו כפטור
            if remaining_exempt + 1e-2 < amount:
                # אין מספיק הון פטור לכיסוי מלא של ההיוון הזה – נמשיך הלאה
                continue

            logger.info(
                "  → Applying exempt capital %.2f on commutation '%s' (amount=%.2f, asset_id=%s)",
                amount,
                asset.asset_name,
                amount,
                getattr(asset, "id", None),
            )

            # שינוי יחס המס לנכס הוני
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
