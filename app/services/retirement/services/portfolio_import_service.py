"""
Portfolio import service for retirement scenarios
שירות ייבוא תיק פנסיוני
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.services.annuity_coefficient import get_annuity_coefficient

logger = logging.getLogger(__name__)

try:
    from app.services.retirement_age_service import (
        DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK,
    )
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67

logger = logging.getLogger("app.scenarios.portfolio")


class PortfolioImportService:
    """שירות לייבוא תיק פנסיוני"""

    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        add_action_callback: Optional[Callable] = None,
        ignore_current_employer_severance: bool = False,
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.add_action = add_action_callback
        # כאשר מופעל, לא נכליל את רכיב "פיצויים מעסקי נוכחי" בייבוא מהתיק הפנסיוני,
        # כדי למנוע ספירה כפולה כאשר סיום עבודה מטופל דרך שירות המעסיק הנוכחי.
        self.ignore_current_employer_severance = ignore_current_employer_severance

    def _get_account_value(self, account: Any, key: str, default: Any = None) -> Any:
        if isinstance(account, dict):
            return account.get(key, default)
        return getattr(account, key, default)

    def import_pension_portfolio(self, pension_portfolio: List[Any]) -> None:
        """ייבוא נתוני תיק פנסיוני והמרתם ל-PensionFund זמניים"""
        logger.info(
            f"📦 Importing pension portfolio: {len(pension_portfolio)} accounts"
        )

        # שליפת פרטי הלקוח לחישוב מקדמי קצבה דינמיים
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        retirement_age = getattr(self, "retirement_age", None)
        retirement_date: Optional[date] = None
        retirement_year: int
        if (
            client
            and getattr(client, "birth_date", None)
            and retirement_age is not None
        ):
            try:
                retirement_date = date(
                    client.birth_date.year + retirement_age,
                    client.birth_date.month,
                    client.birth_date.day,
                )
            except ValueError:
                # טיפול במקרי קצה (למשל 29 בפברואר)
                retirement_date = client.birth_date.replace(
                    year=client.birth_date.year + retirement_age,
                    day=min(client.birth_date.day, 28),
                )
            retirement_year = retirement_date.year
        else:
            retirement_year = date.today().year

        for account in pension_portfolio:
            # חישוב יתרה כוללת מכל הרכיבים
            raw_balance = float(self._get_account_value(account, "יתרה", 0) or 0)
            current_employer_severance = float(
                self._get_account_value(account, "פיצויים_מעסיק_נוכחי", 0) or 0
            )

            # ברירת מחדל: כוללים גם את רכיב "פיצויים_מעסיק_נוכחי" כחלק מהרכיבים,
            # אלא אם ignore_current_employer_severance מופעל (ראו בהמשך).
            component_fields = [
                "פיצויים_מעסיק_נוכחי",
                "פיצויים_לאחר_התחשבנות",
                "פיצויים_שלא_עברו_התחשבנות",
                "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
                "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
                "תגמולי_עובד_עד_2000",
                "תגמולי_עובד_אחרי_2000",
                "תגמולי_עובד_אחרי_2008_לא_משלמת",
                "תגמולי_מעביד_עד_2000",
                "תגמולי_מעביד_אחרי_2000",
                "תגמולי_מעביד_אחרי_2008_לא_משלמת",
            ]

            # כאשר סיום עבודה מטופל דרך שירות המעסיק הנוכחי, לא נייבא את רכיב
            # "פיצויים מעסקי נוכחי" כחלק מהיתרה, כדי למנוע ספירה כפולה של אותם כספים.
            if getattr(self, "ignore_current_employer_severance", False):
                component_fields = [
                    field
                    for field in component_fields
                    if field != "פיצויים_מעסיק_נוכחי"
                ]

            # בתרחישי פרישה איננו ממירים את טור "יתרה" עצמו אלא רק סכומים מפורטים לפי רכיבים.
            # לכן היתרה לתרחיש תחושב תמיד כסכום הרכיבים הרלוונטיים, ללא שימוש בערך הגולמי מטור "יתרה".
            balance = sum(
                float(self._get_account_value(account, comp, 0) or 0)
                for comp in component_fields
            )

            if balance <= 0:
                logger.warning(
                    f"  ⚠️ Skipping account {self._get_account_value(account, 'שם_תכנית')} - zero balance"
                )
                continue

            # בניית פירוט רכיבים לצורך שחזור עתידי ובהמשך לצורך המרות לפי רכיב.
            # כאן נשמור את כל הרכיבים הרלוונטיים (למשל תגמולי_* ופיצויים_*), גם אם קיימת
            # יתרה כללית, כדי לא לאבד מידע על התפלגות הסכומים בין הטורים.
            specific_amounts: Dict[str, float] = {}
            for field in component_fields:
                value = float(self._get_account_value(account, field, 0) or 0)
                if value > 0:
                    specific_amounts[field] = value

            # קביעת סוג מוצר ויחס מס בסיסי
            product_type = self._get_account_value(account, "סוג_מוצר", "") or ""
            tax_treatment = "taxable"
            if "השתלמות" in product_type:
                # קרן השתלמות - כל היתרה היא הונית ופטורה ממס
                tax_treatment = "exempt"
                logger.info(
                    f"  🎁 Detected education fund (קרן השתלמות): "
                    f"{self._get_account_value(account, 'שם_תכנית')} - tax exempt"
                )

            # ניסיון לחישוב מקדם קצבה דינמי מטבלאות המקדמים
            annuity_factor = 180.0  # ברירת מחדל אם אין נתונים
            try:
                # נגזרת תאריך התחלת התכנית
                start_date_raw = self._get_account_value(account, "תאריך_התחלה")
                start_date_obj: Optional[date] = None
                if start_date_raw:
                    try:
                        # ניסיון כפורמט ISO (YYYY-MM-DD)
                        start_date_obj = date.fromisoformat(start_date_raw)
                    except ValueError:
                        try:
                            # ניסיון כפורמט DD/MM/YYYY
                            start_date_obj = datetime.strptime(
                                start_date_raw, "%d/%m/%Y"
                            ).date()
                        except Exception:
                            start_date_obj = None
                retirement_age_for_coeff = retirement_age
                if (
                    retirement_age_for_coeff is None
                    and client
                    and getattr(client, "birth_date", None)
                    and getattr(client, "gender", None)
                ):
                    try:
                        from app.services.retirement_age_service import (
                            get_retirement_age_simple,
                        )

                        retirement_age_for_coeff = int(
                            get_retirement_age_simple(client.birth_date, client.gender)
                        )
                    except Exception:
                        retirement_age_for_coeff = None
                if retirement_age_for_coeff is None:
                    try:
                        from app.services.retirement_age_service import (
                            DEFAULT_MALE_RETIREMENT_AGE,
                        )

                        retirement_age_for_coeff = int(DEFAULT_MALE_RETIREMENT_AGE)
                    except Exception:
                        retirement_age_for_coeff = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)

                coeff = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=retirement_age_for_coeff,
                    company_name=self._get_account_value(account, "חברה_מנהלת"),
                    option_name=None,
                    survivors_option="תקנוני",
                    spouse_age_diff=0,
                    target_year=retirement_year,
                    birth_date=getattr(client, "birth_date", None),
                    pension_start_date=retirement_date or None,
                )
                annuity_factor = float(coeff.get("factor_value") or annuity_factor)
                logger.info(
                    f"  📊 Annuity factor from table for {self._get_account_value(account, 'שם_תכנית')}: "
                    f"{annuity_factor} (source={coeff.get('source_table')})"
                )
            except Exception as e:
                logger.warning(
                    f"  ⚠️ Failed to get annuity coefficient for "
                    f"{self._get_account_value(account, 'שם_תכנית')}, using default {annuity_factor}: {e}"
                )

            # בדיקה אם המוצר כבר קיים (למניעת כפילויות)
            account_number = self._get_account_value(account, "מספר_חשבון", "")
            existing_pf = (
                self.db.query(PensionFund)
                .filter(
                    PensionFund.client_id == self.client_id,
                    PensionFund.deduction_file == account_number,
                    PensionFund.conversion_source.like(
                        '%"source": "pension_portfolio"%'
                    ),
                )
                .first()
            )

            if existing_pf:
                # עדכן מוצר קיים
                existing_pf.balance = balance
                existing_pf.annuity_factor = annuity_factor
                existing_pf.tax_treatment = tax_treatment
                logger.info(
                    f"  🔄 Updated existing: {existing_pf.fund_name} - Balance: {balance:,.0f} ₪"
                )
                pf = existing_pf
            else:
                # יצירת PensionFund חדש
                pf = PensionFund(
                    client_id=self.client_id,
                    fund_name=self._get_account_value(
                        account, "שם_תכנית", "תכנית ללא שם"
                    ),
                    fund_type=self._get_account_value(account, "סוג_מוצר", "unknown"),
                    input_mode="manual",
                    balance=balance,
                    annuity_factor=annuity_factor,
                    pension_amount=None,  # יחושב בתרחיש
                    pension_start_date=None,  # יוגדר בתרחיש
                    indexation_method="none",
                    tax_treatment=tax_treatment,  # יחס למס
                    deduction_file=account_number,
                    conversion_source=json.dumps(
                        {
                            "type": "pension_portfolio",
                            "source": "pension_portfolio",
                            "account_name": self._get_account_value(
                                account, "שם_תכנית"
                            ),
                            "company": self._get_account_value(account, "חברה_מנהלת"),
                            "account_number": account_number,
                            "product_type": product_type,
                            "amount": balance,
                            "specific_amounts": specific_amounts,
                            "conversion_date": date.today().isoformat(),
                            "tax_treatment": tax_treatment,
                            "original_balance": balance,
                        },
                        ensure_ascii=False,
                    ),
                )

                self.db.add(pf)
                logger.info(
                    f"  ✅ Imported NEW: {pf.fund_name} - Balance: {balance:,.0f} ₪"
                )

            tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
            logger.info(
                f"  ✅ Imported: {pf.fund_name} - Balance: {balance:,.0f} ₪ (Factor: {annuity_factor}, {tax_status})"
            )

            if self.add_action:
                self.add_action(
                    "import",
                    f"ייבוא מתיק פנסיוני: {pf.fund_name} ({tax_status})",
                    from_asset=f"תיק פנסיוני: {self._get_account_value(account, 'מספר_חשבון')}",
                    to_asset=f"יתרה: {balance:,.0f} ₪ ({tax_status})",
                    amount=balance,
                )

        self.db.flush()
        logger.info(f"  ✅ Imported {len(pension_portfolio)} pension accounts")
