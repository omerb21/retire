"""
Portfolio import service for retirement scenarios
שירות ייבוא תיק פנסיוני
"""
import logging
import json
from datetime import date, datetime
from typing import List, Dict, Optional, Callable
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.client import Client
from app.services.annuity_coefficient import get_annuity_coefficient

logger = logging.getLogger("app.scenarios.portfolio")


class PortfolioImportService:
    """שירות לייבוא תיק פנסיוני"""
    
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
    
    def import_pension_portfolio(self, pension_portfolio: List[Dict]) -> None:
        """ייבוא נתוני תיק פנסיוני והמרתם ל-PensionFund זמניים"""
        logger.info(f"📦 Importing pension portfolio: {len(pension_portfolio)} accounts")
        
        # שליפת פרטי הלקוח לחישוב מקדמי קצבה דינמיים
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        retirement_age = getattr(self, "retirement_age", None)
        retirement_date: Optional[date] = None
        retirement_year: int
        if client and getattr(client, "birth_date", None) and retirement_age is not None:
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
            raw_balance = float(account.get('יתרה', 0) or 0)
            component_fields = [
                'פיצויים_מעסיק_נוכחי', 'פיצויים_לאחר_התחשבנות', 
                'פיצויים_שלא_עברו_התחשבנות', 'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
                'פיצויים_ממעסיקים_קודמים_רצף_קצבה', 'תגמולי_עובד_עד_2000',
                'תגמולי_עובד_אחרי_2000', 'תגמולי_עובד_אחרי_2008_לא_משלמת',
                'תגמולי_מעביד_עד_2000', 'תגמולי_מעביד_אחרי_2000',
                'תגמולי_מעביד_אחרי_2008_לא_משלמת'
            ]
            balance = raw_balance
            
            # אם יש פירוט סכומים, נחבר את כל הרכיבים
            if balance == 0:
                balance = sum(float(account.get(comp, 0) or 0) for comp in component_fields)
            
            if balance <= 0:
                logger.warning(f"  ⚠️ Skipping account {account.get('שם_תכנית')} - zero balance")
                continue
            
            # בניית פירוט רכיבים לצורך שחזור עתידי (התאם ללוגיקה בפרונט)
            specific_amounts: Dict[str, float] = {}
            if raw_balance > 0:
                # אם יש יתרה כללית, נשתמש בה בתור רכיב יחיד
                specific_amounts['יתרה'] = raw_balance
            else:
                for field in component_fields:
                    value = float(account.get(field, 0) or 0)
                    if value > 0:
                        specific_amounts[field] = value

            # קביעת סוג מוצר ויחס מס בסיסי
            product_type = account.get('סוג_מוצר', '') or ''
            tax_treatment = "taxable"
            if 'השתלמות' in product_type:
                # קרן השתלמות - כל היתרה היא הונית ופטורה ממס
                tax_treatment = "exempt"
                logger.info(
                    f"  🎁 Detected education fund (קרן השתלמות): "
                    f"{account.get('שם_תכנית')} - tax exempt"
                )

            # ניסיון לחישוב מקדם קצבה דינמי מטבלאות המקדמים
            annuity_factor = 180.0  # ברירת מחדל אם אין נתונים
            try:
                # נגזרת תאריך התחלת התכנית
                start_date_raw = account.get('תאריך_התחלה')
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
                
                coeff = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=retirement_age or 67,
                    company_name=account.get('חברה_מנהלת'),
                    option_name=None,
                    survivors_option='תקנוני',
                    spouse_age_diff=0,
                    target_year=retirement_year,
                    birth_date=getattr(client, "birth_date", None),
                    pension_start_date=retirement_date or None,
                )
                annuity_factor = float(coeff.get("factor_value") or annuity_factor)
                logger.info(
                    f"  📊 Annuity factor from table for {account.get('שם_תכנית')}: "
                    f"{annuity_factor} (source={coeff.get('source_table')})"
                )
            except Exception as e:
                logger.warning(
                    f"  ⚠️ Failed to get annuity coefficient for "
                    f"{account.get('שם_תכנית')}, using default {annuity_factor}: {e}"
                )
            
            # בדיקה אם המוצר כבר קיים (למניעת כפילויות)
            account_number = account.get('מספר_חשבון', '')
            existing_pf = self.db.query(PensionFund).filter(
                PensionFund.client_id == self.client_id,
                PensionFund.deduction_file == account_number,
                PensionFund.conversion_source.like('%"source": "pension_portfolio"%')
            ).first()
            
            if existing_pf:
                # עדכן מוצר קיים
                existing_pf.balance = balance
                existing_pf.annuity_factor = annuity_factor
                existing_pf.tax_treatment = tax_treatment
                logger.info(f"  🔄 Updated existing: {existing_pf.fund_name} - Balance: {balance:,.0f} ₪")
                pf = existing_pf
            else:
                # יצירת PensionFund חדש
                pf = PensionFund(
                    client_id=self.client_id,
                    fund_name=account.get('שם_תכנית', 'תכנית ללא שם'),
                    fund_type=account.get('סוג_מוצר', 'unknown'),
                    input_mode="manual",
                    balance=balance,
                    annuity_factor=annuity_factor,
                    pension_amount=None,  # יחושב בתרחיש
                    pension_start_date=None,  # יוגדר בתרחיש
                    indexation_method="none",
                    tax_treatment=tax_treatment,  # יחס למס
                    deduction_file=account_number,
                    conversion_source=json.dumps({
                        "type": "pension_portfolio",
                        "source": "pension_portfolio",
                        "account_name": account.get('שם_תכנית'),
                        "company": account.get('חברה_מנהלת'),
                        "account_number": account_number,
                        "product_type": product_type,
                        "amount": balance,
                        "specific_amounts": specific_amounts,
                        "conversion_date": date.today().isoformat(),
                        "tax_treatment": tax_treatment,
                        "original_balance": balance,
                    })
                )
                
                self.db.add(pf)
                logger.info(f"  ✅ Imported NEW: {pf.fund_name} - Balance: {balance:,.0f} ₪")
            
            tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
            logger.info(f"  ✅ Imported: {pf.fund_name} - Balance: {balance:,.0f} ₪ (Factor: {annuity_factor}, {tax_status})")
            
            if self.add_action:
                self.add_action(
                    "import",
                    f"ייבוא מתיק פנסיוני: {pf.fund_name} ({tax_status})",
                    from_asset=f"תיק פנסיוני: {account.get('מספר_חשבון')}",
                    to_asset=f"יתרה: {balance:,.0f} ₪ ({tax_status})",
                    amount=balance
                )
        
        self.db.flush()
        logger.info(f"  ✅ Imported {len(pension_portfolio)} pension accounts")
