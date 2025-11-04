"""
Portfolio import service for retirement scenarios
שירות ייבוא תיק פנסיוני
"""
import logging
import json
from typing import List, Dict, Optional, Callable
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund

logger = logging.getLogger("app.scenarios.portfolio")


class PortfolioImportService:
    """שירות לייבוא תיק פנסיוני"""
    
    def __init__(self, db: Session, client_id: int, add_action_callback: Optional[Callable] = None):
        self.db = db
        self.client_id = client_id
        self.add_action = add_action_callback
    
    def import_pension_portfolio(self, pension_portfolio: List[Dict]) -> None:
        """ייבוא נתוני תיק פנסיוני והמרתם ל-PensionFund זמניים"""
        logger.info(f"📦 Importing pension portfolio: {len(pension_portfolio)} accounts")
        
        for account in pension_portfolio:
            # חישוב יתרה כוללת מכל הרכיבים
            balance = float(account.get('יתרה', 0))
            
            # אם יש פירוט סכומים, נחבר את כל הרכיבים
            if balance == 0:
                components = [
                    'פיצויים_מעסיק_נוכחי', 'פיצויים_לאחר_התחשבנות', 
                    'פיצויים_שלא_עברו_התחשבנות', 'פיצויים_ממעסיקים_קודמים_רצף_זכויות',
                    'פיצויים_ממעסיקים_קודמים_רצף_קצבה', 'תגמולי_עובד_עד_2000',
                    'תגמולי_עובד_אחרי_2000', 'תגמולי_עובד_אחרי_2008_לא_משלמת',
                    'תגמולי_מעביד_עד_2000', 'תגמולי_מעביד_אחרי_2000',
                    'תגמולי_מעביד_אחרי_2008_לא_משלמת'
                ]
                balance = sum(float(account.get(comp, 0) or 0) for comp in components)
            
            if balance <= 0:
                logger.warning(f"  ⚠️ Skipping account {account.get('שם_תכנית')} - zero balance")
                continue
            
            # קביעת annuity factor ויחס מס לפי סוג המוצר
            product_type = account.get('סוג_מוצר', '')
            annuity_factor = 180.0  # ברירת מחדל
            tax_treatment = "taxable"  # ברירת מחדל
            
            if 'ביטוחית' in product_type or 'פנסיה' in product_type:
                annuity_factor = 150.0  # קצבה איכותית יותר
                tax_treatment = "taxable"
            elif 'קופת גמל' in product_type:
                annuity_factor = 200.0
                tax_treatment = "taxable"
            elif 'השתלמות' in product_type:
                # קרן השתלמות - כל היתרה היא הונית ופטורה ממס
                annuity_factor = 200.0
                tax_treatment = "exempt"
                logger.info(f"  🎁 Detected education fund (קרן השתלמות): {account.get('שם_תכנית')} - tax exempt")
            
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
                        "source": "pension_portfolio",
                        "account_number": account_number,
                        "company": account.get('חברה_מנהלת'),
                        "original_balance": balance,
                        "tax_treatment": tax_treatment
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
