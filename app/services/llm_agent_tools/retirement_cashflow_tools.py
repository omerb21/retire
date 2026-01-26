import logging
from typing import Any, Dict, Optional

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.schemas.tax_schemas import PersonalDetails, TaxCalculationInput
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.retirement.constants import PENSION_COEFFICIENT
from app.services.rights_fixation.exemption_caps import get_exemption_percentage, get_monthly_cap
from app.services.tax_calculator import TaxCalculator
from app.utils.date_serializer import parse_date_flexible

logger = logging.getLogger("app.llm_agent_tools")


class RetirementCashflowToolsMixin:
    def run_retirement_cashflow_analysis(
        self,
        retirement_date: str,
        desired_monthly_income: Optional[float] = None,
        apply_max_exemption: bool = False,
        desired_income_is_net: Optional[bool] = None,
        explicit_age: Optional[int] = None,
        explicit_gender: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        מבצע ניתוח תזרים מזומנים בפרישה:
        1. חישוב קצבה פנסיונית צפויה
        2. חישוב ביטוח לאומי (אזרח ותיק)
        3. בדיקת גירעון מול היעד
        4. חישוב משך הזמן שההון יספיק לכיסוי הגירעון
        """
        from datetime import datetime, date
        from dateutil.relativedelta import relativedelta
        
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        # 1. Parsing & Defaults
        try:
            target_date = parse_date_flexible(retirement_date)
        except ValueError:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": f"תאריך לא תקין: {retirement_date}. יש להשתמש בפורמט YYYY-MM-DD.",
            }

        if desired_monthly_income is None:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": (
                    "חסר יעד הכנסה חודשי. כדי להריץ תזרים במערכת צריך יעד חודשי מפורש (ברוטו או נטו).\n\n"
                    "דוגמאות להעתקה:\n"
                    "יעד נטו: <מספר>\n"
                    "יעד ברוטו: <מספר>\n\n"
                    "דוגמאות מלאות:\n"
                    "יעד נטו: 28000\n"
                    "יעד ברוטו: 31000"
                ),
            }

        # 2. חישוב גיל הפרישה המתוכנן
        # שימוש בלוגיקה קיימת של המודל אם אפשר, או חישוב פשוט
        birth_date = getattr(client, "birth_date", None)
        if birth_date is None:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "חסר תאריך לידה של הלקוח במערכת ולכן לא ניתן לבצע חישוב מס בצורה תקינה.",
            }

        if explicit_age is None:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "חסר גיל מפורש לביצוע חישוב. אנא ציין גיל (למשל: 'גבר בן <גיל>' / 'אישה בת <גיל>').",
            }

        if explicit_gender is None:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "חסר מין מפורש לביצוע חישוב. אנא ציין מין (למשל: 'גבר בן <גיל>' / 'אישה בת <גיל>').",
            }

        try:
            age_at_retirement = int(explicit_age)
        except Exception:
            age_at_retirement = None
        if age_at_retirement is None or age_at_retirement < 40 or age_at_retirement > 80:
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": "גיל לא תקין לביצוע חישוב. אנא ציין גיל בין 40 ל-80.",
            }
        
        # Refresh client to ensure relationships are loaded
        self.db.refresh(client)

        # 3. חישוב קצבה פנסיונית צפויה (Projected Pension)
        
        total_pension_balance = 0.0
        # סכום קצבאות שכבר נקובות (למשל פנסיה תקציבית או ותיקה)
        existing_pension_sum = 0.0
        
        pension_funds = []
        capital_assets = []
        
        # בדיקה האם יש נכסים בבסיס הנתונים (לאחר המרה)
        # אם יש - נעדיף אותם על פני נתונים מוזרקים כדי למנוע כפילויות
        db_pension_count = self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).count()
        db_capital_count = self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).count()
        has_db_assets = (db_pension_count + db_capital_count) > 0
        
        if has_db_assets:
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %d pension funds and %d capital assets in DB for client %s - using DB records",
                db_pension_count, db_capital_count, self.client_id
            )
        
        # אם יש נכסים ב-DB, נשתמש בהם. אחרת, נשתמש בנתונים המוזרקים
        if has_db_assets:
            # שימוש בנכסים מבסיס הנתונים (לאחר TRANSFORM_FUNDS_TO_ASSETS)
            pension_funds = list(self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).all())
            capital_assets = list(self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).all())
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Loaded %d pension funds and %d capital assets from DB",
                len(pension_funds), len(capital_assets)
            )
        elif self.pension_portfolio_data and len(self.pension_portfolio_data) > 0:
            # שלב 1: שימוש בנתונים המוזרקים מה-Request (Pydantic models)
            # המרה לאובייקטי מודל כדי שהלוגיקה בהמשך תעבוד
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Using injected pension_portfolio_data with %s accounts for client %s",
                len(self.pension_portfolio_data),
                getattr(self, "client_id", None),
            )
            for acc in self.pension_portfolio_data:
                balance = float(acc.יתרה or 0)
                product_type_raw = acc.סוג_מוצר or ""
                name = acc.שם_תכנית or "ללא שם"

                if balance <= 0:
                    continue

                # סייגי מוצר בעדיפות עליונה
                is_study_fund = "קרן השתלמות" in product_type_raw
                is_investment_gemel = "גמל להשקעה" in product_type_raw
                is_gemel_fund = ("קופת גמל" in product_type_raw) and not is_investment_gemel

                classification: str | None = None  # "pension", "capital", "unspecified"

                if is_study_fund or is_investment_gemel:
                    classification = "capital"
                else:
                    # קריאת טורי פיצויים ותגמולים אם קיימים
                    pitz_current = float(getattr(acc, "פיצויים_מעסיק_נוכחי", 0) or 0)
                    pitz_after_settlement = float(getattr(acc, "פיצויים_לאחר_התחשבנות", 0) or 0)
                    pitz_not_settled = float(getattr(acc, "פיצויים_שלא_עברו_התחשבנות", 0) or 0)
                    pitz_prev_rights = float(getattr(acc, "פיצויים_ממעסיקים_קודמים_רצף_זכויות", 0) or 0)
                    pitz_prev_pension = float(getattr(acc, "פיצויים_ממעסיקים_קודמים_רצף_קצבה", 0) or 0)

                    emp_before_2000 = float(getattr(acc, "תגמולי_עובד_עד_2000", 0) or 0)
                    emp_after_2000 = float(getattr(acc, "תגמולי_עובד_אחרי_2000", 0) or 0)
                    emp_after_2008_np = float(getattr(acc, "תגמולי_עובד_אחרי_2008_לא_משלמת", 0) or 0)
                    empr_before_2000 = float(getattr(acc, "תגמולי_מעביד_עד_2000", 0) or 0)
                    empr_after_2000 = float(getattr(acc, "תגמולי_מעביד_אחרי_2000", 0) or 0)
                    empr_after_2008_np = float(getattr(acc, "תגמולי_מעביד_אחרי_2008_לא_משלמת", 0) or 0)

                    capital_sum = 0.0
                    pension_sum = 0.0
                    unspecified_sum = 0.0

                    # טורי "ללא סיווג": פיצויים שלא עברו התחשבנות + רצף זכויות
                    unspecified_sum += pitz_not_settled + pitz_prev_rights

                    # פיצויים לאחר התחשבנות – הון
                    capital_sum += pitz_after_settlement

                    # פיצויים מעסיק נוכחי – גמיש, ברירת מחדל הון
                    capital_sum += pitz_current

                    # פיצויים ממעסיקים קודמים ברצף קצבה – קצבה
                    pension_sum += pitz_prev_pension

                    # תגמולי עובד/מעביד אחרי 2000 – קצבה, למעט קופת גמל = הון
                    if emp_after_2000 > 0:
                        if is_gemel_fund:
                            capital_sum += emp_after_2000
                        else:
                            pension_sum += emp_after_2000
                    if empr_after_2000 > 0:
                        if is_gemel_fund:
                            capital_sum += empr_after_2000
                        else:
                            pension_sum += empr_after_2000

                    # תגמולי עובד/מעביד אחרי 2008 (לא משלמת) – קצבה
                    pension_sum += emp_after_2008_np + empr_after_2008_np

                    # תגמולי עובד/מעביד עד 2000 – גמיש, ברירת מחדל הון
                    capital_sum += emp_before_2000 + empr_before_2000

                    total_cols = capital_sum + pension_sum + unspecified_sum

                    if total_cols > 0:
                        if capital_sum == 0 and pension_sum == 0:
                            classification = "unspecified"
                        elif pension_sum >= capital_sum:
                            classification = "pension"
                        else:
                            classification = "capital"

                if classification is None:
                    # fallback: קופת גמל כהון, אחרת קצבה
                    if is_gemel_fund or is_study_fund or is_investment_gemel:
                        classification = "capital"
                    else:
                        classification = "pension"

                logger.info(
                    "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Injected account classified as %s - name=%s, type=%s, balance=%.2f",
                    classification,
                    name,
                    product_type_raw,
                    balance,
                )

                if classification == "unspecified":
                    # לא נכנס לחישוב הון/קצבה, דורש החלטה נפרדת
                    continue

                if classification == "capital":
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=name,
                        asset_type=acc.סוג_מוצר,
                        current_value=balance,
                        annual_return_rate=0,
                        payment_frequency='monthly',
                        start_date=date.today(),
                    )
                    capital_assets.append(ca)
                else:
                    pf = PensionFund(
                        client_id=self.client_id,
                        fund_name=name,
                        fund_type=acc.סוג_מוצר,
                        balance=balance,
                        pension_amount=0,
                        input_mode="manual",
                    )
                    pension_funds.append(pf)

            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s pension funds (via raw data injection) and %s capital assets",
                len(pension_funds),
                len(capital_assets),
            )
            
        else:
            # Fallback למקרה שהנתונים לא הוזרקו כלל - נסיון אחרון דרך ה-Client
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: No injected pension portfolio data, falling back to client relationships.")
            pension_funds_raw = self.client.pension_funds if self.client else []
            capital_assets_raw = self.client.capital_assets if self.client else []
            
            pension_funds = [acc for acc in pension_funds_raw if isinstance(acc, PensionFund)]
            capital_assets = [acc for acc in capital_assets_raw if isinstance(acc, CapitalAsset)]
            
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s pension funds (via client relationship fallback) for client %s",
                len(pension_funds), getattr(self, "client_id", None),
            )
            logger.info(
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Found %s capital assets (via client relationship fallback) for client %s",
                len(capital_assets), getattr(self, "client_id", None),
            )

        # לוג מפורט על כל קרן פנסיה לפני החישוב
        if pension_funds:
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: Pension fund details for client %s:", getattr(self, "client_id", None))
            for pf in pension_funds:
                logger.info(
                    "  Fund id=%s, name=%s, type=%s, balance=%.2f, pension_amount=%.2f, input_mode=%s, start_date=%s",
                    getattr(pf, "id", None),
                    getattr(pf, "fund_name", None),
                    getattr(pf, "fund_type", None),
                    (pf.balance or 0.0),
                    (pf.pension_amount or 0.0),
                    getattr(pf, "input_mode", None),
                    getattr(pf, "pension_start_date", None),
                )

        # לוג מפורט על כל נכס הון לפני החישוב (כדי לאתר הון שמופיע רק כ-capital_asset)
        if capital_assets:
            logger.info("RUN_RETIREMENT_CASHFLOW_ANALYSIS: Capital asset details for client %s:", getattr(self, "client_id", None))
            for ca in capital_assets:
                logger.info(
                    "  CapitalAsset id=%s, name=%s, type=%s, current_value=%.2f, monthly_income=%.2f, start_date=%s",
                    getattr(ca, "id", None),
                    getattr(ca, "asset_name", None),
                    getattr(ca, "asset_type", None),
                    float(ca.current_value or 0),
                    float(ca.monthly_income or 0),
                    getattr(ca, "start_date", None),
                )

        for pf in pension_funds:
            total_pension_balance += (pf.balance or 0)
            existing_pension_sum += (pf.pension_amount or 0)

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Total pension balance after aggregation = %.2f, existing monthly pension sum = %.2f",
            total_pension_balance,
            existing_pension_sum,
        )

        # קבלת מקדם המרה דינמי לפי גיל ותאריך תחילת קצבה
        annuity_factor = float(PENSION_COEFFICIENT)
        logger.info(
            "🔍 [RUN 16 DEBUG] Starting annuity coefficient retrieval for age %s, date %s",
            age_at_retirement, target_date
        )
        try:
            coeff_result = get_annuity_coefficient(
                product_type="קרן פנסיה",  # שימוש בזיהוי קרן פנסיה כמו בשאר המערכת
                start_date=target_date,
                gender=str(explicit_gender),
                retirement_age=age_at_retirement,
                target_year=target_date.year,
                birth_date=birth_date,
                pension_start_date=target_date,
            )
            logger.info(
                "✅ [RUN 16 DEBUG] Coefficient result: %s",
                coeff_result
            )
            annuity_factor = float(coeff_result.get("factor_value") or annuity_factor)
            logger.info(
                "📊 [RUN 16 DEBUG] Using annuity_factor: %.2f (source: %s)",
                annuity_factor,
                coeff_result.get("source_table", "unknown")
            )
        except Exception as e:  # הגנה: אם השירות נכשל, נשתמש במקדם ברירת מחדל
            logger.warning(
                "❌ [RUN 16 DEBUG] Failed to get annuity coefficient, "
                "falling back to default %s: %s",
                annuity_factor,
                e,
            )

        if annuity_factor <= 0:
            logger.warning("⚠️ [RUN 16 DEBUG] Factor was <= 0, resetting to default: %s", PENSION_COEFFICIENT)
            annuity_factor = float(PENSION_COEFFICIENT)

        logger.info(
            "🧮 [RUN 16 DEBUG] Calculating projected pension: balance=%.2f / factor=%.2f",
            total_pension_balance, annuity_factor
        )
        projected_new_pension = total_pension_balance / annuity_factor if total_pension_balance > 0 else 0.0
        logger.info(
            "💰 [RUN 16 DEBUG] Projected NEW pension from balance: %.2f ₪/month",
            projected_new_pension
        )
        total_pension_income = existing_pension_sum + projected_new_pension
        logger.info(
            "💵 [RUN 16 DEBUG] TOTAL pension income: existing=%.2f + new=%.2f = %.2f ₪/month",
            existing_pension_sum, projected_new_pension, total_pension_income
        )

        # 4. חישוב קצבת אזרח ותיק (ביטוח לאומי)
        # הערכה בסיסית: בסיס + תוספת ותק
        # בסיס ליחיד (2025 משוער): ~1730 ש"ח
        # תוספת ותק מקסימלית (50%): ~865 ש"ח
        # סה"כ מקסימלי ליחיד: ~2600 ש"ח
        # (נניח תרחיש סביר של 2400 ש"ח אם לא ידוע אחרת)
        # לצורך דיבאג ננטרל את ברירת המחדל וניצור לוג מפורט על הערך בפועל
        social_security_amount = 0.0
        
        # התאמה לפי גיל הזכאות (נשים 62-65, גברים 67)
        # אם פורש לפני הזמן - 0
        gender_norm = str(explicit_gender or "").strip().lower()
        is_female = gender_norm in {"female", "f", "נקבה", "נ"}
        legal_retirement_age = 65 if is_female else 67
        if age_at_retirement < legal_retirement_age:
            social_security_amount = 0.0

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Social security amount used = %.2f (age_at_retirement=%s, legal_retirement_age=%s)",
            social_security_amount,
            age_at_retirement,
            legal_retirement_age,
        )

        # ===== הכנסות נוספות (AdditionalIncome) =====
        # משקלל לתוך התזרים (מול יעד ההכנסה) לפי ההכנסות שב-DB
        # ללא שינוי מצב (קריאה בלבד)
        additional_incomes = (
            self.db.query(AdditionalIncome)
            .filter(AdditionalIncome.client_id == self.client_id)
            .order_by(AdditionalIncome.id.asc())
            .all()
        )

        additional_income_taxable_gross_monthly = 0.0
        additional_income_exempt_gross_monthly = 0.0

        for ai in additional_incomes:
            try:
                if getattr(ai, "start_date", None) and ai.start_date > target_date:
                    continue
                if getattr(ai, "end_date", None) and ai.end_date < target_date:
                    continue
            except Exception:
                pass

            try:
                raw_amount = float(getattr(ai, "amount", 0) or 0)
            except Exception:
                raw_amount = 0.0

            if raw_amount <= 0:
                continue

            freq = str(getattr(ai, "frequency", "") or "").strip().lower()
            if freq == "monthly":
                monthly_amount = raw_amount
            elif freq == "quarterly":
                monthly_amount = raw_amount / 3
            elif freq == "annually":
                monthly_amount = raw_amount / 12
            else:
                monthly_amount = raw_amount

            tax_treatment = str(getattr(ai, "tax_treatment", "taxable") or "taxable").strip().lower()
            if tax_treatment == "exempt":
                additional_income_exempt_gross_monthly += monthly_amount
            else:
                additional_income_taxable_gross_monthly += monthly_amount

        additional_income_gross_monthly = additional_income_taxable_gross_monthly + additional_income_exempt_gross_monthly

        total_guaranteed_income_gross = total_pension_income + additional_income_gross_monthly + social_security_amount

        # ===== חישוב מס על הקצבה (Tax Analysis) =====
        # יצירת פרטים אישיים לחישוב מס
        tax_personal_details = PersonalDetails(
            birth_date=birth_date,
            marital_status="single",  # ברירת מחדל - ניתן לשפר בהמשך
            is_veteran=False,
            is_disabled=False,
        )

        # חישוב מס על הקצבה השנתית
        annual_pension_gross = total_pension_income * 12
        tax_year = target_date.year

        # ===== חישוב פטור קיבוע זכויות (Run 25) =====
        # אם apply_max_exemption=True, נחשב את הפטור המקסימלי לפי שנת הפרישה
        # ונשמור את תוצאות הקיבוע ל-DB כדי שיהיו זמינות לדוחות ולממשק
        exempt_pension_monthly = 0.0
        exemption_percentage = 0.0
        monthly_cap = 0.0
        fixation_saved = False

        if apply_max_exemption:
            # חישוב פטור מקסימלי לפי שנת הזכאות
            # פטור חודשי = תקרת פיצויים × אחוז פטור
            monthly_cap = get_monthly_cap(tax_year)
            exemption_percentage = get_exemption_percentage(tax_year)
            exempt_pension_monthly = monthly_cap * exemption_percentage

            # הפטור לא יכול לעלות על הקצבה בפועל
            exempt_pension_monthly = min(exempt_pension_monthly, total_pension_income)

            logger.info(
                "EXEMPTION ANALYSIS (Run 25): Year=%d, Monthly Cap=%.2f, Exemption %%=%.1f%%, Max Exempt=%.2f",
                tax_year, monthly_cap, exemption_percentage * 100, exempt_pension_monthly
            )

            # שמירת קיבוע זכויות ל-DB כדי שיהיה זמין לדוחות ולממשק
            try:
                from app.routers.rights_fixation import (
                    calculate_and_save_fixation_for_client,
                    update_fixation_exempt_pension_fields,
                )
                fixation_result = calculate_and_save_fixation_for_client(self.db, self.client_id)
                if fixation_result:
                    try:
                        update_fixation_exempt_pension_fields(fixation_result)
                    except Exception as update_err:
                        logger.warning(
                            "RIGHTS FIXATION: Failed updating exempt pension fields: %s",
                            update_err,
                        )

                    self.db.commit()
                    self.db.refresh(fixation_result)
                    fixation_saved = True
                    logger.info(
                        "RIGHTS FIXATION: Auto-saved fixation for client %s (exempt_capital_remaining=%.2f)",
                        self.client_id, fixation_result.exempt_capital_remaining or 0
                    )
                else:
                    logger.warning("RIGHTS FIXATION: Failed to auto-save fixation for client %s", self.client_id)
            except Exception as fix_err:
                self.db.rollback()
                logger.warning("RIGHTS FIXATION: Error auto-saving fixation: %s", fix_err)

        try:
            tax_calculator = TaxCalculator(tax_year=tax_year)

            # ===== 1) מס על הקצבה בלבד (לשדות תאימות לאחור) =====
            tax_input_pension_only = TaxCalculationInput(
                tax_year=tax_year,
                personal_details=tax_personal_details,
                pension_income=annual_pension_gross,
                exempt_pension_amount=exempt_pension_monthly,  # פטור חודשי מקיבוע זכויות
                pension_months_in_year=12,
            )
            tax_result_pension_only = tax_calculator.calculate_comprehensive_tax(tax_input_pension_only)

            annual_net_pension_only = float(tax_result_pension_only.net_income)
            monthly_net_pension = annual_net_pension_only / 12
            monthly_tax_deduction = float(tax_result_pension_only.net_tax) / 12
            monthly_health_tax = float(tax_result_pension_only.health_tax) / 12
            monthly_income_tax = float(tax_result_pension_only.income_tax) / 12

            # ===== 2) מס משוקלל: קצבה + הכנסות נוספות חייבות (לניתוח פער מול יעד) =====
            annual_other_taxable = float(additional_income_taxable_gross_monthly * 12)
            tax_input_total = TaxCalculationInput(
                tax_year=tax_year,
                personal_details=tax_personal_details,
                pension_income=annual_pension_gross,
                other_income=annual_other_taxable,
                exempt_pension_amount=exempt_pension_monthly,
                pension_months_in_year=12,
            )
            tax_result_total = tax_calculator.calculate_comprehensive_tax(tax_input_total)
            annual_net_total_taxable = float(tax_result_total.net_income)
            monthly_net_total_taxable = annual_net_total_taxable / 12
            monthly_income_tax_total = float(tax_result_total.income_tax) / 12
            monthly_tax_deduction_total = float(tax_result_total.net_tax) / 12

            logger.info(
                "TAX ANALYSIS: Pension-only annual gross=%.2f, annual net=%.2f, income_tax=%.2f",
                annual_pension_gross,
                annual_net_pension_only,
                float(tax_result_pension_only.income_tax),
            )
            logger.info(
                "TAX ANALYSIS: Combined annual gross=%.2f (pension + other taxable=%.2f), annual net=%.2f, income_tax=%.2f",
                annual_pension_gross + annual_other_taxable,
                annual_other_taxable,
                annual_net_total_taxable,
                float(tax_result_total.income_tax),
            )
            logger.info(
                "TAX ANALYSIS: Monthly pension gross=%.2f, pension net=%.2f, pension tax deduction=%.2f, Exempt=%.2f",
                total_pension_income,
                monthly_net_pension,
                monthly_tax_deduction,
                exempt_pension_monthly,
            )
            logger.info(
                "TAX ANALYSIS: Monthly total net taxable (pension+other)=%.2f, monthly income tax total=%.2f",
                monthly_net_total_taxable,
                monthly_income_tax_total,
            )

        except Exception as e:
            logger.error(
                "TAX ANALYSIS: Failed to calculate tax for retirement_date=%s (tax_year=%s). Refusing to return fallback tax=0: %s",
                retirement_date,
                tax_year,
                e,
                exc_info=True,
            )
            return {
                "success": False,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {},
                "explanation": (
                    "שגיאה בחישוב מס הכנסה לקצבה. "
                    "כדי למנוע הצגת נתונים שגויים, המערכת לא מחזירה תוצאת מס משוערת במקרה זה. "
                    f"פרטים טכניים: {str(e)}"
                ),
            }

        # הכנסה מובטחת נטו (כולל ביטוח לאומי שהוא פטור ממס)
        # לצורך פער מול יעד, משתמשים בנטו משוקלל: קצבה + הכנסות נוספות חייבות
        total_guaranteed_income_net = monthly_net_total_taxable + additional_income_exempt_gross_monthly + social_security_amount
        total_guaranteed_income = total_guaranteed_income_gross  # לשמירה על תאימות לאחור

        # 5. ניתוח גירעון (Gap Analysis)
        # נחשב גם פער נטו וגם פער ברוטו. "gap" הוא הפער הפעיל בהתאם לבחירת המשתמש.
        gap_net = desired_monthly_income - total_guaranteed_income_net
        gap_gross = desired_monthly_income - total_guaranteed_income_gross

        # ברירת מחדל: אם לא נאמר במפורש – נשמרת תאימות לאחור: נטו.
        if desired_income_is_net is None:
            desired_income_is_net = True
        gap = gap_net if desired_income_is_net else gap_gross
        
        # 6. חישוב הון זמין
        # שימוש ברשימה המסוננת שכבר יצרנו
        # capital_assets כבר חושב למעלה
        # המרה ל-float כדי למנוע שגיאת Decimal serialization
        total_capital_available = 0.0
        for ca in capital_assets:
            try:
                val = float(getattr(ca, "current_value", 0) or 0)
            except Exception:
                val = 0.0
            if val <= 0:
                try:
                    val = float(getattr(ca, "monthly_income", 0) or 0)
                except Exception:
                    val = 0.0
            total_capital_available += val
        # נניח שגם קרנות השתלמות נזילות בפרישה
        
        # 7. חישוב משך כיסוי (Sufficiency)
        sufficiency_years: float | None = 999.0 # אינסוף
        is_sustainable = True
        required_capital_withdrawal = 0.0

        logger.info(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Final calculations - Projected Pension: %s, Total Liquid Capital: %s, Gap: %s",
            total_pension_income, total_capital_available, gap
        )

        gap_epsilon = 0.01
        if gap <= gap_epsilon:
            # אין גירעון חודשי (או זניח ברמת אגורות) – לא מחלקים כדי למנוע שנים לא סבירות.
            required_capital_withdrawal = 0.0
            sufficiency_years = None
            is_sustainable = True
        elif gap > 0:
            is_sustainable = False
            required_capital_withdrawal = gap
            if total_capital_available > 0:
                months_covered = total_capital_available / gap
                sufficiency_years = months_covered / 12
                if sufficiency_years > (120 - age_at_retirement): # הנחת תוחלת חיים
                     is_sustainable = True
            else:
                sufficiency_years = 0.0
        else:
            # עודף תזרימי
            sufficiency_years = None
            
        # 8. בניית התשובה
        
        # יצירת הסבר
        deficit_status = "עודף" if gap <= 0 else "גירעון"
        gap_abs = abs(gap)

        target_mode_label = "נטו" if desired_income_is_net else "ברוטו"
        basis_label = "נטו" if desired_income_is_net else "ברוטו"
        
        # בניית הסבר עם/בלי פטור קיבוע זכויות
        exemption_info = ""
        if apply_max_exemption and exempt_pension_monthly > 0:
            exemption_info = f"\n🎁 **פטור קיבוע זכויות (מקסימלי):**\n   אחוז פטור: {exemption_percentage * 100:.1f}%\n   קצבה פטורה: {exempt_pension_monthly:,.0f} ₪/חודש\n"

        explanation_lines = [
            f"**דוח תזרים לפרישה בתאריך {target_date.strftime('%d/%m/%Y')} (גיל {age_at_retirement})**",
            f"",
            f"💰 **הכנסה ברוטו חודשית:** {total_guaranteed_income_gross:,.0f} ₪",
            f"   (פנסיה ברוטו: {total_pension_income:,.0f} ₪ + הכנסות נוספות: {additional_income_gross_monthly:,.0f} ₪ + ביטוח לאומי: {social_security_amount:,.0f} ₪)",
        ]

        if exemption_info:
            explanation_lines.append(exemption_info)

        explanation_lines.extend([
            f"",
            f"📊 **ניתוח מס הכנסה:**",
            f"   מס הכנסה חודשי (סה\"כ הכנסות חייבות): {monthly_income_tax_total:,.0f} ₪",
            f"   (מתוך זה, מס על הקצבה בלבד: {monthly_income_tax:,.0f} ₪)",
            f"",
            f"✅ **הכנסה נטו חודשית:** {total_guaranteed_income_net:,.0f} ₪",
            f"   (פנסיה נטו: {monthly_net_pension:,.0f} ₪ + הכנסות נוספות נטו (כלולות במס): {additional_income_taxable_gross_monthly:,.0f} ₪ + הכנסות פטורות: {additional_income_exempt_gross_monthly:,.0f} ₪ + ביטוח לאומי: {social_security_amount:,.0f} ₪)",
            f"",
            f"🎯 **יעד הכנסה ({target_mode_label}):** {desired_monthly_income:,.0f} ₪",
            f"📉 **{deficit_status} חודשי (לפי {basis_label}):** {gap_abs:,.0f} ₪",
        ])
        
        if gap > gap_epsilon:
            explanation_lines.append(f"")
            explanation_lines.append(f"🏦 **שימוש בהון פנוי:**")
            explanation_lines.append(f"   סך הון זמין: {total_capital_available:,.0f} ₪")
            if total_capital_available > 0:
                explanation_lines.append(f"   ההון יספיק לכיסוי הגירעון למשך **{sufficiency_years:.1f} שנים** (עד גיל {age_at_retirement + sufficiency_years:.1f}).")
            else:
                explanation_lines.append(f"   ⚠️ אין הון פנוי לכיסוי הגירעון!")
        elif gap <= gap_epsilon:
            explanation_lines.append(f"")
            explanation_lines.append("✅ **אין גירעון חודשי ביחס ליעד**")

        return {
            "success": True,
            "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "result": {
                "retirement_date": retirement_date,
                "retirement_age": age_at_retirement,
                # ברוטו
                "projected_pension": round(total_pension_income, 2),
                "social_security": social_security_amount,
                "total_guaranteed_income": round(total_guaranteed_income_gross, 2),
                # פטור קיבוע זכויות
                "apply_max_exemption": apply_max_exemption,
                "exemption_percentage": round(exemption_percentage * 100, 1),
                "exempt_pension_monthly": round(exempt_pension_monthly, 2),
                # ניתוח מס
                "monthly_income_tax": round(monthly_income_tax, 2),
                "monthly_health_tax": round(monthly_health_tax, 2),
                "monthly_tax_deduction": round(monthly_tax_deduction, 2),
                "monthly_income_tax_total": round(monthly_income_tax_total, 2),
                "monthly_tax_deduction_total": round(monthly_tax_deduction_total, 2),
                # נטו
                "projected_pension_net": round(monthly_net_pension, 2),
                "total_guaranteed_income_net": round(total_guaranteed_income_net, 2),
                "additional_income_gross_monthly": round(additional_income_gross_monthly, 2),
                "additional_income_taxable_gross_monthly": round(additional_income_taxable_gross_monthly, 2),
                "additional_income_exempt_gross_monthly": round(additional_income_exempt_gross_monthly, 2),
                # יעד וגירעון
                "desired_monthly_income": desired_monthly_income,
                "desired_income_is_net": bool(desired_income_is_net),
                "gap_to_target_net": round(gap_net, 2),
                "gap_to_target_gross": round(gap_gross, 2),
                "monthly_deficit_or_surplus": round(-gap, 2),  # שלילי = גירעון
                "required_capital_withdrawal": round(required_capital_withdrawal, 2),
                "total_liquid_capital": round(total_capital_available, 2),
                "capital_sufficiency_years": (
                    round(float(sufficiency_years), 1) if sufficiency_years is not None else None
                ),
                "is_sustainable": is_sustainable
            },
            "explanation": "\n".join(explanation_lines)
        }
