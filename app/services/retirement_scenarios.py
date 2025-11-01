"""
Retirement Scenarios Builder Service
מייצר 3 תרחישי פרישה: מקסימום קצבה, מקסימום הון, מקסימום NPV
"""
import logging
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import date, datetime
from decimal import Decimal
import json
import copy

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from app.models.termination_event import TerminationEvent
from app.models.fixation_result import FixationResult

logger = logging.getLogger("app.scenarios")

# Constants
PENSION_COEFFICIENT = 200  # מקדם קצבה להמרת נכסים הוניים
MINIMUM_PENSION = 5500  # קצבת מינימום בשקלים
HIGH_QUALITY_ANNUITY_THRESHOLD = 150  # סף לקצבה איכותית


class RetirementScenariosBuilder:
    """בונה תרחישי פרישה"""
    
    def __init__(self, db: Session, client_id: int, retirement_age: int, pension_portfolio: Optional[List[Dict]] = None):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.pension_portfolio = pension_portfolio or []  # נתוני תיק פנסיוני
        self.client = db.query(Client).filter(Client.id == client_id).first()
        self.actions = []  # רשימת כל הפעולות שבוצעו בתרחיש
        
        if not self.client:
            raise ValueError(f"לקוח {client_id} לא נמצא")
        
        # המרת נתוני תיק פנסיוני ל-PensionFund אם קיימים
        if self.pension_portfolio:
            self._import_pension_portfolio()
    
    def _add_action(self, action_type: str, details: str, from_asset: str = "", to_asset: str = "", amount: float = 0):
        """מוסיף פעולה לרשימת הפעולות"""
        self.actions.append({
            "type": action_type,
            "details": details,
            "from": from_asset,
            "to": to_asset,
            "amount": amount
        })
    
    def _create_scenario_capital_asset(self, asset_name: str, asset_type: str, value: float, 
                                       tax_treatment: str = "taxable", source_info: dict = None) -> CapitalAsset:
        """יוצר נכס הון עם סימון שמקורו בתרחיש"""
        retirement_year = self._get_retirement_year()
        
        conversion_source = json.dumps({
            "source": "scenario_conversion",
            "scenario_type": "retirement",
            **(source_info or {})
        })
        
        return CapitalAsset(
            client_id=self.client_id,
            asset_name=asset_name,
            asset_type=asset_type,
            current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
            monthly_income=Decimal(str(value)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
            annual_return_rate=Decimal("0.04"),
            payment_frequency="monthly",
            start_date=date(retirement_year, 1, 1),
            indexation_method="none",
            tax_treatment=tax_treatment,
            conversion_source=conversion_source
        )
    
    def _import_pension_portfolio(self):
        """ייבוא נתוני תיק פנסיוני והמרתם ל-PensionFund זמניים"""
        logger.info(f"📦 Importing pension portfolio: {len(self.pension_portfolio)} accounts")
        
        for account in self.pension_portfolio:
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
            self._add_action("import", f"ייבוא מתיק פנסיוני: {pf.fund_name} ({tax_status})",
                            from_asset=f"תיק פנסיוני: {account.get('מספר_חשבון')}",
                            to_asset=f"יתרה: {balance:,.0f} ₪ ({tax_status})",
                            amount=balance)
        
        self.db.flush()
        logger.info(f"  ✅ Imported {len(self.pension_portfolio)} pension accounts")
    
    def build_all_scenarios(self) -> Dict[str, any]:
        """בונה את כל 3 התרחישים"""
        logger.info(f"🎯 Building scenarios for client {self.client_id}, retirement age {self.retirement_age}")
        
        # Save current state
        original_state = self._save_current_state()
        
        try:
            # Scenario 1: Maximum Pension
            self.actions = []  # אפס רשימת פעולות
            scenario1 = self._build_max_pension_scenario()
            
            # Restore state
            self._restore_state(original_state)
            
            # Scenario 2: Maximum Capital
            self.actions = []  # אפס רשימת פעולות
            scenario2 = self._build_max_capital_scenario()
            
            # Restore state
            self._restore_state(original_state)
            
            # Scenario 3: Maximum NPV
            self.actions = []  # אפס רשימת פעולות
            scenario3 = self._build_max_npv_scenario()
            
            # Restore original state
            self._restore_state(original_state)
            
            return {
                "scenario_1_max_pension": scenario1,
                "scenario_2_max_capital": scenario2,
                "scenario_3_max_npv": scenario3
            }
            
        except Exception as e:
            logger.error(f"❌ Error building scenarios: {e}", exc_info=True)
            # Restore state on error
            self._restore_state(original_state)
            raise
    
    def _save_current_state(self) -> Dict:
        """שומר את מצב הנתונים הנוכחי"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        
        additional_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id
        ).all()
        
        termination_events = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).all()
        
        return {
            "pension_funds": [self._serialize_pension_fund(pf) for pf in pension_funds],
            "capital_assets": [self._serialize_capital_asset(ca) for ca in capital_assets],
            "additional_incomes": [self._serialize_additional_income(ai) for ai in additional_incomes],
            "termination_events": [self._serialize_termination_event(te) for te in termination_events]
        }
    
    def _restore_state(self, state: Dict):
        """משחזר את מצב הנתונים"""
        # Delete all current records
        self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).delete()
        self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).delete()
        self.db.query(AdditionalIncome).filter(AdditionalIncome.client_id == self.client_id).delete()
        self.db.query(TerminationEvent).filter(TerminationEvent.client_id == self.client_id).delete()
        
        # Restore from state
        for pf_data in state["pension_funds"]:
            pf = PensionFund(**pf_data)
            self.db.add(pf)
        
        for ca_data in state["capital_assets"]:
            ca = CapitalAsset(**ca_data)
            self.db.add(ca)
        
        for ai_data in state["additional_incomes"]:
            ai = AdditionalIncome(**ai_data)
            self.db.add(ai)
        
        for te_data in state["termination_events"]:
            te = TerminationEvent(**te_data)
            self.db.add(te)
        
        self.db.flush()
    
    # ============ SCENARIO 1: MAXIMUM PENSION ============
    
    def _build_max_pension_scenario(self) -> Dict:
        """תרחיש 1: מקסימום קצבה"""
        logger.info("📊 Building Scenario 1: Maximum Pension")
        
        # 0. Import pension portfolio if provided
        if self.pension_portfolio:
            self._import_pension_portfolio()
        
        # 1. Convert all pension funds to pensions
        self._convert_all_pension_funds_to_pension()
        
        # 1.5. Convert education funds to exempt pensions
        self._convert_education_fund_to_pension()
        
        # 2. Convert taxable capital assets to pensions
        self._convert_taxable_capital_to_pension()
        
        # 3. Convert tax-exempt capital to exempt pension (NOT income!)
        self._convert_exempt_capital_to_pension()
        
        # 4. Handle termination event
        self._handle_termination_for_pension()
        
        # 5. Verify fixation and exempt pension
        self._verify_fixation_and_exempt_pension()
        
        # 6. Calculate NPV and return results
        return self._calculate_scenario_results("מקסימום קצבה")
    
    def _convert_all_pension_funds_to_pension(self):
        """המרת כל המוצרים הפנסיוניים לקצבה (למעט קרנות השתלמות)"""
        # קרנות השתלמות יטופלו בנפרד
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')  # לא קרנות השתלמות
        ).all()
        
        for pf in pension_funds:
            original_balance = pf.balance
            original_pension = pf.pension_amount
            tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
            
            # חישוב קצבה - גם ל-calculated וגם למוצרים עם balance+annuity_factor
            if pf.balance and pf.annuity_factor and not pf.pension_amount:
                # Calculate pension amount from balance
                pf.pension_amount = float(pf.balance) / float(pf.annuity_factor)
                logger.info(f"  💰 Converted {pf.fund_name}: Balance {pf.balance} → Pension {pf.pension_amount} ({tax_status})")
                
                # רישום המרה במפרט
                self._add_action("conversion", f"המרת יתרה לקצבה: {pf.fund_name} ({tax_status})",
                                from_asset=f"יתרה: {original_balance:,.0f} ₪",
                                to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                                amount=float(original_balance or 0))
                
                # ✅ איפוס balance אחרי המרה לקצבה!
                pf.balance = None
            elif pf.pension_amount:
                # קצבה שכבר הוגדרה
                self._add_action("use_existing", f"שימוש בקצבה קיימת: {pf.fund_name} ({tax_status})",
                                from_asset="",
                                to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                                amount=0)
            else:
                logger.warning(f"  ⚠️ Cannot convert {pf.fund_name}: missing balance or annuity_factor")
            
            # Set start date to retirement year
            retirement_year = self._get_retirement_year()
            pf.pension_start_date = date(retirement_year, 1, 1)
        
        self.db.flush()
    
    def _convert_taxable_capital_to_pension(self):
        """המרת נכסים הוניים חייבים במס לקצבה"""
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id,
            CapitalAsset.tax_treatment == "taxable"
        ).all()
        
        for ca in capital_assets:
            # Create pension fund from capital asset
            # תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
            capital_value = float(ca.monthly_income or 0)
            pension_amount = capital_value / PENSION_COEFFICIENT
            retirement_year = self._get_retirement_year()
            
            pf = PensionFund(
                client_id=self.client_id,
                fund_name=f"קצבה מ{ca.asset_name}",
                fund_type="converted_capital",
                input_mode="manual",
                pension_amount=pension_amount,
                pension_start_date=date(retirement_year, 1, 1),
                indexation_method="none",
                conversion_source=json.dumps({
                    "source_type": "capital_asset",
                    "source_id": ca.id,
                    "source_name": ca.asset_name,
                    "original_value": capital_value
                })
            )
            self.db.add(pf)
            logger.info(f"  Converted capital asset '{ca.asset_name}': {capital_value} → Pension {pension_amount}")
            self._add_action("conversion", f"המרת נכס הון לקצבה: {ca.asset_name}",
                            from_asset=f"הון: {ca.asset_name} ({capital_value:,.0f} ₪)",
                            to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש",
                            amount=capital_value)
            
            # Delete capital asset
            self.db.delete(ca)
        
        self.db.flush()
    
    def _convert_education_fund_to_pension(self):
        """המרת קרן השתלמות (education fund) לקצבה פטורה"""
        # מחפש את כל קרנות ההשתלמות שיובאו מהתיק הפנסיוני
        education_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            PensionFund.tax_treatment == "exempt",
            PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        retirement_year = self._get_retirement_year()
        
        for ef in education_funds:
            # קרן השתלמות - כל היתרה פטורה ממס
            original_balance = ef.balance
            
            if not original_balance or original_balance <= 0:
                logger.warning(f"  Education fund {ef.fund_name} has no balance, skipping")
                continue
            
            # המרה לקצבה פטורה
            pension_amount = float(original_balance) / PENSION_COEFFICIENT
            
            # עדכון הקרן הקיימת במקום יצירת חדשה (כדי לא לאבד מידע)
            ef.pension_amount = pension_amount
            ef.pension_start_date = date(retirement_year, 1, 1)
            ef.annuity_factor = PENSION_COEFFICIENT
            ef.fund_type = "education_fund_pension"  # סימון שעברה המרה
            
            logger.info(f"  Converted education fund '{ef.fund_name}': {original_balance} → Exempt PENSION {pension_amount} ₪/month")
            self._add_action("conversion", f"המרת קרן השתלמות לקצבה פטורה: {ef.fund_name}",
                            from_asset=f"קרן השתלמות: {ef.fund_name} ({original_balance:,.0f} ₪)",
                            to_asset=f"קצבה פטורה: {pension_amount:,.0f} ₪/חודש",
                            amount=float(original_balance))
        
        self.db.flush()
    
    def _convert_education_fund_to_capital(self):
        """המרת קרן השתלמות להון פטור (אופציה 2)"""
        education_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            PensionFund.tax_treatment == "exempt",
            PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        retirement_year = self._get_retirement_year()
        
        for ef in education_funds:
            original_balance = ef.balance
            
            if not original_balance or original_balance <= 0:
                logger.warning(f"  Education fund {ef.fund_name} has no balance, skipping")
                continue
            
            # יצירת נכס הוני פטור
            ca = self._create_scenario_capital_asset(
                asset_name=f"הון פטור מ{ef.fund_name}",
                asset_type="education_fund",
                value=float(original_balance),
                tax_treatment="exempt",
                source_info={
                    "source_type": "education_fund",
                    "source_id": getattr(ef, 'id', None),
                    "source_name": ef.fund_name,
                    "original_balance": float(original_balance),
                    "tax_treatment": "exempt"
                }
            )
            self.db.add(ca)
            
            logger.info(f"  Converted education fund '{ef.fund_name}': {original_balance} → Exempt CAPITAL {original_balance} ₪")
            self._add_action("conversion", f"המרת קרן השתלמות להון פטור: {ef.fund_name}",
                            from_asset=f"קרן השתלמות: {ef.fund_name} ({original_balance:,.0f} ₪)",
                            to_asset=f"הון פטור: {original_balance:,.0f} ₪",
                            amount=float(original_balance))
            
            # מחיקת הקרן המקורית
            self.db.delete(ef)
        
        self.db.flush()
    
    def _convert_exempt_capital_to_pension(self):
        """המרת נכסים הוניים פטורים לקצבה פטורה (לא להכנסה נוספת!)"""
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id,
            CapitalAsset.tax_treatment == "exempt"
        ).all()
        
        retirement_year = self._get_retirement_year()
        
        for ca in capital_assets:
            # Create PENSION FUND (tax-exempt) - NOT additional income!
            # תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
            capital_value = float(ca.monthly_income or 0)
            pension_amount = capital_value / PENSION_COEFFICIENT
            
            pf = PensionFund(
                client_id=self.client_id,
                fund_name=f"קצבה פטורה מ{ca.asset_name}",
                fund_type="converted_capital",
                input_mode="manual",
                pension_amount=pension_amount,
                pension_start_date=date(self._get_retirement_year(), 1, 1),
                indexation_method="none",
                tax_treatment="exempt",  # קצבה פטורה!
                conversion_source=json.dumps({
                    "source_type": "capital_asset",
                    "source_id": getattr(ca, 'id', None),
                    "source_name": ca.asset_name,
                    "original_value": capital_value,
                    "tax_treatment": "exempt"
                })
            )
            self.db.add(pf)
            logger.info(f"  Converted exempt capital '{ca.asset_name}': {capital_value} → Exempt PENSION {pension_amount} ₪/month")
            self._add_action("conversion", f"המרת נכס פטור לקצבה פטורה: {ca.asset_name}",
                            from_asset=f"נכס פטור: {ca.asset_name} ({capital_value:,.0f} ₪)",
                            to_asset=f"קצבה פטורה: {pension_amount:,.0f} ₪/חודש",
                            amount=capital_value)
            
            # Delete capital asset
            self.db.delete(ca)
        
        self.db.flush()
    
    def _handle_termination_for_pension(self):
        """טיפול בעזיבת עבודה - בחירה בקצבה"""
        from app.models.current_employer import CurrentEmployer
        from app.models.employer_grant import EmployerGrant, GrantType
        from app.services.current_employer_service import CurrentEmployerService
        from app.services.annuity_coefficient_service import get_annuity_coefficient
        
        # Check if termination event exists
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()
        
        if not termination:
            logger.info("  ℹ️ No termination event found, skipping")
            return
        
        logger.info("  📝 Processing termination event for pension choice")
        
        # מציאת המעביד הנוכחי
        current_employer = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == self.client_id,
            CurrentEmployer.id == termination.employment_id
        ).first()
        
        if not current_employer:
            logger.warning("  ⚠️ Current employer not found for termination event")
            return
        
        # מציאת כל המענקים של המעביד
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.current_employer_id == current_employer.id
        ).all()
        
        if not grants:
            logger.info("  ℹ️ No grants found for termination")
            return
        
        # קבלת נתוני לקוח לחישוב מקדם
        client = self.db.query(Client).filter(Client.id == self.client_id).first()
        retirement_year = self._get_retirement_year()
        pension_start_date = date(retirement_year, 1, 1)
        
        # קיבוץ מענקים לפי תכנית - כל תכנית תקבל קצבה נפרדת
        grants_by_plan = {}
        for grant in grants:
            if grant.grant_type == GrantType.severance:
                plan_key = grant.plan_name or "ללא תכנית"
                if plan_key not in grants_by_plan:
                    grants_by_plan[plan_key] = {
                        'grants': [],
                        'plan_start_date': grant.plan_start_date,
                        'plan_name': grant.plan_name,
                        'product_type': grant.product_type  # שמירת סוג המוצר
                    }
                grants_by_plan[plan_key]['grants'].append(grant)
        
        if not grants_by_plan:
            logger.info("  ℹ️ No severance grants to process")
            return
        
        # יצירת קצבה נפרדת לכל תכנית
        total_pensions_created = 0
        for plan_key, plan_data in grants_by_plan.items():
            plan_grants = plan_data['grants']
            plan_start_date = plan_data['plan_start_date']
            plan_name = plan_data['plan_name'] or "תכנית ללא שם"
            product_type = plan_data.get('product_type') or 'ביטוח מנהלים'  # ברירת מחדל: ביטוח מנהלים
            
            # חישוב סכומים לתכנית זו
            plan_severance = 0
            plan_exempt = 0
            
            for grant in plan_grants:
                calc_result = CurrentEmployerService.calculate_severance_grant(
                    current_employer, grant
                )
                plan_severance += calc_result.indexed_amount
                plan_exempt += calc_result.grant_exempt
                logger.info(f"    💰 Grant for {plan_name}: {grant.grant_amount} ₪ (Exempt: {calc_result.grant_exempt:,.0f}, Taxable: {calc_result.grant_taxable:,.0f})")
            
            if plan_severance == 0:
                logger.info(f"  ℹ️ No severance amount for plan {plan_name}")
                continue
            
            # חישוב מקדם קצבה דינמי לפי תאריך התחלת התכנית וסוג המוצר
            try:
                logger.info(f"  📊 Calculating coefficient for {plan_name}: product_type='{product_type}'")
                coefficient_result = get_annuity_coefficient(
                    product_type=product_type,  # שימוש בסוג המוצר האמיתי מהגרנט
                    start_date=plan_start_date if plan_start_date else (current_employer.start_date if current_employer.start_date else date.today()),
                    gender=client.gender if client else 'זכר',
                    retirement_age=self._get_retirement_age(),
                    survivors_option='תקנוני',
                    spouse_age_diff=0,
                    birth_date=client.birth_date if client else None,
                    pension_start_date=pension_start_date
                )
                annuity_factor = coefficient_result['factor_value']
                factor_source = coefficient_result['source_table']
                logger.info(f"  📊 Dynamic annuity coefficient for {plan_name}: {annuity_factor} (source: {factor_source})")
            except Exception as e:
                logger.warning(f"  ⚠️ Failed to calculate dynamic coefficient for {plan_name}: {e}, using default 200")
                annuity_factor = PENSION_COEFFICIENT
                factor_source = "default"
            
            # חישוב קצבה: סכום ÷ מקדם המרה
            pension_amount = plan_severance / annuity_factor
            
            # קביעת יחס מס לפי חלק הפטור
            exempt_ratio = plan_exempt / plan_severance if plan_severance > 0 else 0
            tax_treatment = "exempt" if exempt_ratio > 0.8 else "taxable"  # אם מעל 80% פטור, נחשב פטור
            tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
            
            pf = PensionFund(
                client_id=self.client_id,
                fund_name=f"קצבה מפיצויי פרישה - {plan_name}",
                fund_type="severance_pension",
                input_mode="manual",
                balance=plan_severance,
                annuity_factor=annuity_factor,
                pension_amount=pension_amount,
                pension_start_date=pension_start_date,
                indexation_method="none",
                tax_treatment=tax_treatment,
                remarks=f"תכנית: {plan_name}\nמקדם קצבה: {annuity_factor:.2f} (מקור: {factor_source})\nתאריך התחלת תכנית: {plan_start_date.strftime('%d/%m/%Y') if plan_start_date else 'לא ידוע'}",
                conversion_source=json.dumps({
                    "source": "termination_event",
                    "termination_id": termination.id,
                    "employer_id": current_employer.id,
                    "plan_name": plan_name,
                    "plan_start_date": plan_start_date.isoformat() if plan_start_date else None,
                    "plan_severance": plan_severance,
                    "plan_exempt": plan_exempt,
                    "annuity_factor": annuity_factor,
                    "factor_source": factor_source
                })
            )
            self.db.add(pf)
            
            logger.info(f"  ✅ Created pension for {plan_name}: {pension_amount:,.0f} ₪/month ({tax_status})")
            self._add_action("conversion", f"המרת פיצויי פרישה לקצבה - {plan_name} ({tax_status})",
                            from_asset=f"פיצויים מ-{plan_name}: {plan_severance:,.0f} ₪ (פטור: {plan_exempt:,.0f})",
                            to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש ({tax_status})",
                            amount=plan_severance)
            
            total_pensions_created += 1
        
        logger.info(f"  🎯 Total pensions created: {total_pensions_created}")
        self.db.flush()
    
    def _handle_termination_for_capital(self):
        """טיפול בעזיבת עבודה - בחירה בהון"""
        from app.models.current_employer import CurrentEmployer
        from app.models.employer_grant import EmployerGrant, GrantType
        from app.services.current_employer_service import CurrentEmployerService
        from decimal import Decimal
        
        # Check if termination event exists
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).first()
        
        if not termination:
            logger.info("  ℹ️ No termination event found, skipping")
            return
        
        logger.info("  📝 Processing termination event for capital choice")
        
        # מציאת המעביד הנוכחי
        current_employer = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == self.client_id,
            CurrentEmployer.id == termination.employment_id
        ).first()
        
        if not current_employer:
            logger.warning("  ⚠️ Current employer not found for termination event")
            return
        
        # מציאת כל המענקים של המעביד
        grants = self.db.query(EmployerGrant).filter(
            EmployerGrant.current_employer_id == current_employer.id
        ).all()
        
        if not grants:
            logger.info("  ℹ️ No grants found for termination")
            return
        
        # קיבוץ מענקים לפי תכנית - כל תכנית תקבל נכס הון נפרד
        grants_by_plan = {}
        for grant in grants:
            if grant.grant_type == GrantType.severance:
                plan_key = grant.plan_name or "ללא תכנית"
                if plan_key not in grants_by_plan:
                    grants_by_plan[plan_key] = {
                        'grants': [],
                        'plan_start_date': grant.plan_start_date,
                        'plan_name': grant.plan_name
                    }
                grants_by_plan[plan_key]['grants'].append(grant)
        
        if not grants_by_plan:
            logger.info("  ℹ️ No severance grants to process")
            return
        
        # יצירת נכס הון נפרד לכל תכנית
        total_assets_created = 0
        for plan_key, plan_data in grants_by_plan.items():
            plan_grants = plan_data['grants']
            plan_start_date = plan_data['plan_start_date']
            plan_name = plan_data['plan_name'] or "תכנית ללא שם"
            
            # חישוב סכומים לתכנית זו
            plan_severance = 0
            plan_exempt = 0
            
            for grant in plan_grants:
                calc_result = CurrentEmployerService.calculate_severance_grant(
                    current_employer, grant
                )
                plan_severance += calc_result.indexed_amount
                plan_exempt += calc_result.grant_exempt
                logger.info(f"    💰 Grant for {plan_name}: {grant.grant_amount} ₪ (Exempt: {calc_result.grant_exempt:,.0f}, Taxable: {calc_result.grant_taxable:,.0f})")
            
            if plan_severance == 0:
                logger.info(f"  ℹ️ No severance amount for plan {plan_name}")
                continue
            
            # קביעת יחס מס לפי חלק הפטור
            exempt_ratio = plan_exempt / plan_severance if plan_severance > 0 else 0
            tax_treatment = "exempt" if exempt_ratio > 0.8 else "taxable"  # אם מעל 80% פטור, נחשב פטור
            tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
            
            ca = self._create_scenario_capital_asset(
                asset_name=f"פיצויי פרישה - {plan_name}",
                asset_type="severance",
                value=plan_severance,
                tax_treatment=tax_treatment,
                source_info={
                    "termination_id": termination.id,
                    "employer_id": current_employer.id,
                    "plan_name": plan_name,
                    "plan_start_date": plan_start_date.isoformat() if plan_start_date else None,
                    "plan_severance": plan_severance,
                    "plan_exempt": plan_exempt
                }
            )
            self.db.add(ca)
            
            logger.info(f"  ✅ Created capital asset for {plan_name}: {plan_severance:,.0f} ₪ ({tax_status})")
            self._add_action("conversion", f"שמירת פיצויי פרישה כנכס הוני - {plan_name} ({tax_status})",
                            from_asset=f"פיצויים מ-{plan_name}: {plan_severance:,.0f} ₪ (פטור: {plan_exempt:,.0f})",
                            to_asset=f"הון: {plan_severance:,.0f} ₪ ({tax_status})",
                            amount=plan_severance)
            
            total_assets_created += 1
        
        logger.info(f"  🎯 Total capital assets created: {total_assets_created}")
        self.db.flush()
    
    # ============ SCENARIO 2: MAXIMUM CAPITAL ============
    
    def _build_max_capital_scenario(self) -> Dict:
        """תרחיש 2: מקסימום הון (עם שמירת קצבת מינימום 5,500)"""
        logger.info("📊 Building Scenario 2: Maximum Capital (with minimum pension)")
        
        # Step 0: Import pension portfolio if provided
        if self.pension_portfolio:
            self._import_pension_portfolio()
        
        # Step 0.5: Handle termination event - convert to capital
        self._handle_termination_for_capital()
        
        # Step 1: Convert all pension funds to pensions first (excluding education funds)
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')  # לא קרנות השתלמות
        ).all()
        
        for pf in pension_funds:
            if pf.balance and pf.annuity_factor:
                original_balance = pf.balance
                pf.pension_amount = float(pf.balance) / float(pf.annuity_factor)
                pf.pension_start_date = date(self._get_retirement_year(), 1, 1)
                tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
                self._add_action("conversion", f"המרת יתרה לקצבה: {pf.fund_name} ({tax_status})",
                                from_asset=f"יתרה: {original_balance:,.0f} ₪",
                                to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                                amount=float(original_balance))
                # ✅ איפוס balance אחרי המרה!
                pf.balance = None
        
        self.db.flush()
        
        # Step 1.5: Convert education funds to capital (keep as exempt capital)
        self._convert_education_fund_to_capital()
        
        # Step 2: Calculate total pension available
        total_pension_available = sum(pf.pension_amount or 0 for pf in pension_funds)
        logger.info(f"  Total pension available: {total_pension_available} ₪")
        
        if total_pension_available < MINIMUM_PENSION:
            logger.warning(f"  ⚠️ Cannot capitalize - total pension {total_pension_available} < minimum {MINIMUM_PENSION}")
            # Convert everything to pension (can't capitalize at all)
            self._convert_all_pension_funds_to_pension()
            self._convert_taxable_capital_to_pension()
            self._convert_exempt_capital_to_pension()
            return self._calculate_scenario_results("מקסימום הון (לא ניתן להיוון)")
        
        # Step 3: Sort by annuity factor - capitalize worst quality first
        sorted_pensions = sorted(
            [pf for pf in pension_funds if pf.pension_amount and pf.annuity_factor],
            key=lambda p: p.annuity_factor,
            reverse=True  # Highest annuity factor first (worst quality)
        )
        
        # Step 4: Keep minimum pension, capitalize the rest
        remaining_pension = total_pension_available
        
        for pf in sorted_pensions:
            if remaining_pension <= MINIMUM_PENSION:
                # Keep this pension
                tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
                logger.info(f"  ✅ Keeping pension: {pf.fund_name} ({pf.pension_amount} ₪) ({tax_status})")
                self._add_action("keep", f"שמירת קצבה מינימום: {pf.fund_name} ({tax_status})",
                                from_asset="",
                                to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                                amount=0)
            else:
                # Check how much we can capitalize
                can_capitalize = remaining_pension - MINIMUM_PENSION
                
                if pf.pension_amount <= can_capitalize:
                    # Capitalize entire fund - יורש מצב מס מהקצבה
                    capital_value = pf.pension_amount * pf.annuity_factor
                    tax_treatment = "exempt" if pf.tax_treatment == "exempt" else "taxable"
                    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
                    
                    ca = self._create_scenario_capital_asset(
                        asset_name=f"הון מהיוון {pf.fund_name}",
                        asset_type="provident_fund",
                        value=capital_value,
                        tax_treatment=tax_treatment,
                        source_info={"pension_fund": pf.fund_name, "annuity_factor": float(pf.annuity_factor)}
                    )
                    self.db.add(ca)
                    remaining_pension -= pf.pension_amount
                    logger.info(f"  💼 Full capitalization: {pf.fund_name} → {capital_value} ₪ capital ({tax_status})")
                    self._add_action("capitalization", f"היוון מלא של {pf.fund_name} ({tax_status})", 
                                    from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount:,.0f} ₪/חודש)",
                                    to_asset=f"הון: {capital_value:,.0f} ₪ ({tax_status})",
                                    amount=capital_value)
                    self.db.delete(pf)
                else:
                    # Partial capitalization - capitalize only the excess - יורש מצב מס מהקצבה
                    capitalize_amount = can_capitalize
                    keep_amount = pf.pension_amount - capitalize_amount
                    tax_treatment = "exempt" if pf.tax_treatment == "exempt" else "taxable"
                    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
                    
                    capital_value = capitalize_amount * pf.annuity_factor
                    ca = self._create_scenario_capital_asset(
                        asset_name=f"הון מהיוון חלקי {pf.fund_name}",
                        asset_type="provident_fund",
                        value=capital_value,
                        tax_treatment=tax_treatment,
                        source_info={"pension_fund": pf.fund_name, "partial": True}
                    )
                    self.db.add(ca)
                    
                    # Update pension to keep minimum
                    pf.pension_amount = keep_amount
                    # ✅ לא להחזיר balance! המוצר כבר במצב pension
                    remaining_pension = MINIMUM_PENSION
                    logger.info(f"  ⚖️ Partial capitalization: {pf.fund_name} - {capitalize_amount} ₪ → capital ({tax_status}), {keep_amount} ₪ remains pension")
                    self._add_action("capitalization", f"היוון חלקי של {pf.fund_name} ({tax_status})",
                                    from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount + capitalize_amount:,.0f} ₪/חודש)",
                                    to_asset=f"הון: {capital_value:,.0f} ₪ ({tax_status}) + קצבה: {keep_amount:,.0f} ₪/חודש",
                                    amount=capital_value)
        
        self.db.flush()
        
        # Step 5: Keep capital assets as is (DON'T convert to pension!)
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        logger.info(f"  ✅ Final pension amount: {remaining_pension} ₪ (minimum: {MINIMUM_PENSION})")
        logger.info(f"  ✅ Keeping {len(capital_assets)} capital assets as is")
        
        # Step 6: Verify
        self._verify_fixation_and_exempt_pension()
        
        # Step 7: Calculate and return
        return self._calculate_scenario_results("מקסימום הון (קצבת מינימום: 5,500)")
    
    def _convert_pension_funds_to_capital(self):
        """המרת מוצרים פנסיוניים להון"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        convertible_funds = []
        non_convertible_funds = []
        
        for pf in pension_funds:
            # Assume all funds with balance are convertible
            # In reality, would check fund_type or other criteria
            if pf.balance and pf.balance > 0:
                convertible_funds.append(pf)
            else:
                non_convertible_funds.append(pf)
        
        # Convert convertible funds to capital assets
        for pf in convertible_funds:
            # ✅ שימור יחס המס מהקרן המקורית
            tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
            
            ca = CapitalAsset(
                client_id=self.client_id,
                asset_name=f"הון מ{pf.fund_name}",
                asset_type="provident_fund",
                current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                monthly_income=Decimal(str(pf.balance)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                annual_return_rate=Decimal("0.04"),  # Default 4%
                payment_frequency="monthly",
                start_date=date(self._get_retirement_year(), 1, 1),
                indexation_method="none",
                tax_treatment=tax_treatment,  # ✅ שימור יחס המס המקורי
                conversion_source=json.dumps({
                    "source_type": "pension_fund",
                    "source_id": pf.id,
                    "source_name": pf.fund_name,
                    "original_balance": float(pf.balance),
                    "original_tax_treatment": tax_treatment
                })
            )
            self.db.add(ca)
            logger.info(f"  💼 Converted pension fund '{pf.fund_name}' to capital: {pf.balance}")
            
            # Delete pension fund
            self.db.delete(pf)
        
        self.db.flush()
    
    def _capitalize_pensions_with_iron_law(self):
        """היוון קצבאות עם חוק הברזל (קצבת מינימום 5,500)"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        if not pension_funds:
            logger.info("  ℹ️ No pension funds to capitalize")
            return
        
        # Sort by annuity factor (lowest first)
        sorted_funds = sorted(pension_funds, key=lambda pf: pf.annuity_factor or 999999)
        
        total_pension = 0
        capitalized_funds = []
        minimum_pension_funds = []
        
        # Build minimum pension
        for pf in sorted_funds:
            if total_pension >= MINIMUM_PENSION:
                # Can capitalize this one
                capitalized_funds.append(pf)
            else:
                # Need for minimum pension
                pension_needed = MINIMUM_PENSION - total_pension
                
                if pf.pension_amount and pf.pension_amount >= pension_needed:
                    # Partial capitalization
                    minimum_pension_funds.append((pf, pension_needed))
                    
                    # Capitalize the rest
                    remaining_pension = pf.pension_amount - pension_needed
                    if remaining_pension > 0:
                        capitalized_funds.append((pf, remaining_pension))
                    
                    total_pension = MINIMUM_PENSION
                else:
                    # Use entire pension for minimum
                    minimum_pension_funds.append((pf, pf.pension_amount))
                    total_pension += pf.pension_amount or 0
        
        # Capitalize funds above minimum
        for item in capitalized_funds:
            if isinstance(item, tuple):
                pf, amount = item
                # Partial capitalization - create capital asset for part
                capital_value = amount * (pf.annuity_factor or 180)
                # ✅ שימור יחס המס מהקרן המקורית
                tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
                
                ca = CapitalAsset(
                    client_id=self.client_id,
                    asset_name=f"הון מהיוון {pf.fund_name} (חלקי)",
                    asset_type="provident_fund",
                    current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                    monthly_income=Decimal(str(capital_value)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                    annual_return_rate=Decimal("0.04"),
                    payment_frequency="monthly",
                    start_date=date(self._get_retirement_year(), 1, 1),
                    indexation_method="none",
                    tax_treatment=tax_treatment  # ✅ שימור יחס המס המקורי
                )
                self.db.add(ca)
                
                # Update pension fund to keep only minimum part
                pf.pension_amount = MINIMUM_PENSION - sum([amt for _, amt in minimum_pension_funds if _ != pf])
                
                logger.info(f"  🔄 Partial capitalization of '{pf.fund_name}': {amount} → Capital {capital_value}")
            else:
                pf = item
                # Full capitalization
                if pf.annuity_factor and pf.pension_amount:
                    capital_value = pf.pension_amount * pf.annuity_factor
                    # ✅ שימור יחס המס מהקרן המקורית
                    tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
                    
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=f"הון מהיוון {pf.fund_name}",
                        asset_type="provident_fund",
                        current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                        monthly_income=Decimal(str(capital_value)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                        annual_return_rate=Decimal("0.04"),
                        payment_frequency="monthly",
                        start_date=date(self._get_retirement_year(), 1, 1),
                        indexation_method="none",
                        tax_treatment=tax_treatment  # ✅ שימור יחס המס המקורי
                    )
                    self.db.add(ca)
                    
                    logger.info(f"  💰 Full capitalization of '{pf.fund_name}': {pf.pension_amount} → Capital {capital_value}")
                    
                    # Delete pension fund
                    self.db.delete(pf)
        
        self.db.flush()
        logger.info(f"  ✅ Minimum pension preserved: {MINIMUM_PENSION} ₪")
    
    # ============ SCENARIO 3: MAXIMUM NPV ============
    
    def _build_max_npv_scenario(self) -> Dict:
        """תרחיש 3: מאוזן - 50% ערך כקצבה, 50% ערך כהון"""
        logger.info("📊 Building Scenario 3: Balanced (50/50 Split)")
        
        # Strategy: Balance between pension security and capital liquidity
        # Target: 50% of total asset value as pension, 50% as capital
        # This provides middle ground between scenarios 1 (100% pension) and 2 (min pension + max capital)
        
        # Step 0: Import pension portfolio if provided
        if self.pension_portfolio:
            self._import_pension_portfolio()
        
        # Step 0.5: Handle termination event - convert 50% to pension, 50% to capital
        # For balanced scenario, convert severance to capital first, then will be partially converted
        self._handle_termination_for_capital()
        
        # Step 1: Convert education funds to capital (keep as exempt capital)
        self._convert_education_fund_to_capital()
        
        # Step 2: Convert pension funds to pensions (excluding education funds)
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id,
            ~PensionFund.fund_type.like('%השתלמות%')
        ).all()
        
        for pf in pension_funds:
            if pf.balance and pf.annuity_factor:
                original_balance = pf.balance
                pf.pension_amount = float(pf.balance) / float(pf.annuity_factor)
                pf.pension_start_date = date(self._get_retirement_year(), 1, 1)
                tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"
                self._add_action("conversion", f"המרת יתרה לקצבה: {pf.fund_name} ({tax_status})",
                                from_asset=f"יתרה: {original_balance:,.0f} ₪",
                                to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
                                amount=float(original_balance))
                # ✅ איפוס balance אחרי המרה!
                pf.balance = None
        
        self.db.flush()
        
        # Step 3: Keep existing capital assets as is (DON'T convert to pension!)
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        # ✅ תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
        total_capital_monthly = sum(float(ca.monthly_income or 0) for ca in capital_assets)
        logger.info(f"  ✅ Keeping {len(capital_assets)} capital assets ({total_capital_monthly:,.0f} ₪/month) as is")
        
        # Step 4: Now capitalize half (50%) of the PENSION FUNDS value only
        all_pensions = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        total_pension_amount = sum(pf.pension_amount or 0 for pf in all_pensions)
        logger.info(f"  Total pension amount available: {total_pension_amount} ₪/month")
        
        # Check if we can capitalize at all (need minimum pension)
        if total_pension_amount < MINIMUM_PENSION:
            logger.warning(f"  ⚠️ Cannot capitalize - total pension {total_pension_amount} < minimum {MINIMUM_PENSION}")
            # Keep all as pension
            return self._calculate_scenario_results("מאוזן (50% קצבה, 50% הון) - לא ניתן להיוון")
        
        total_pension_value_now = sum(pf.pension_amount * pf.annuity_factor for pf in all_pensions if pf.pension_amount and pf.annuity_factor)
        
        # Calculate target: try to keep minimum pension and capitalize the rest
        # But don't exceed 50% of total value
        max_can_capitalize = (total_pension_amount - MINIMUM_PENSION) * PENSION_COEFFICIENT
        target_capitalize_value = min(total_pension_value_now * 0.5, max_can_capitalize)
        
        logger.info(f"  Target to capitalize: {target_capitalize_value} (max 50% or keep min pension)")
        
        # Sort by annuity factor (worst quality first)
        if target_capitalize_value > 0:
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
                    tax_treatment = "exempt" if pf.tax_treatment == "exempt" else "taxable"
                    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
                    
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=f"הון מהיוון {pf.fund_name}",
                        asset_type="provident_fund",
                        current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                        monthly_income=Decimal(str(pf_value)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                        annual_return_rate=Decimal("0.04"),
                        payment_frequency="monthly",
                        start_date=date(self._get_retirement_year(), 1, 1),
                        indexation_method="none",
                        tax_treatment=tax_treatment
                    )
                    self.db.add(ca)
                    capitalized_value += pf_value
                    remaining_pension -= pf.pension_amount
                    logger.info(f"  💼 Full capitalization: {pf.fund_name} → {pf_value} ₪ capital ({tax_status})")
                    self._add_action("capitalization", f"היוון מלא (50%): {pf.fund_name} ({tax_status})",
                                    from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount:,.0f} ₪/חודש)",
                                    to_asset=f"הון: {pf_value:,.0f} ₪ ({tax_status})",
                                    amount=pf_value)
                    self.db.delete(pf)
                else:
                    # Partial capitalization
                    remaining_pension_value = pf_value - need_to_capitalize
                    new_pension_amount = remaining_pension_value / pf.annuity_factor
                    tax_treatment = "exempt" if pf.tax_treatment == "exempt" else "taxable"
                    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
                    
                    ca = CapitalAsset(
                        client_id=self.client_id,
                        asset_name=f"הון מהיוון חלקי {pf.fund_name}",
                        asset_type="provident_fund",
                        current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                        monthly_income=Decimal(str(need_to_capitalize)),  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                        annual_return_rate=Decimal("0.04"),
                        payment_frequency="monthly",
                        start_date=date(self._get_retirement_year(), 1, 1),
                        indexation_method="none",
                        tax_treatment=tax_treatment
                    )
                    self.db.add(ca)
                    
                    original_pension_amount = pf.pension_amount
                    pf.pension_amount = new_pension_amount
                    # ✅ לא להחזיר balance! המוצר כבר במצב pension
                    capitalized_value += need_to_capitalize
                    logger.info(f"  ⚖️ Partial capitalization: {pf.fund_name} - {need_to_capitalize} ₪ → capital ({tax_status}), {new_pension_amount} ₪ remains pension")
                    self._add_action("capitalization", f"היוון חלקי (50%): {pf.fund_name} ({tax_status})",
                                    from_asset=f"קצבה: {pf.fund_name} ({original_pension_amount:,.0f} ₪/חודש)",
                                    to_asset=f"הון: {need_to_capitalize:,.0f} ₪ ({tax_status}) + קצבה: {new_pension_amount:,.0f} ₪/חודש",
                                    amount=need_to_capitalize)
            
            logger.info(f"  ✅ Capitalized {capitalized_value} ₪ (target: {target_capitalize_value})")
        
        self.db.flush()
        
        # Step 5: Keep exempt capital as is (don't convert!)
        exempt_capital = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id,
            CapitalAsset.tax_treatment == "exempt"
        ).all()
        logger.info(f"  ✅ Keeping {len(exempt_capital)} exempt capital assets as is")
        
        # Step 6: Verify
        self._verify_fixation_and_exempt_pension()
        
        # Step 7: Calculate and return
        return self._calculate_scenario_results("מאוזן (50% קצבה, 50% הון)")
    
    # ============ HELPERS ============
    
    def _get_retirement_year(self) -> int:
        """מחשב שנת פרישה על בסיס גיל הפרישה"""
        if not self.client.birth_date:
            raise ValueError("תאריך לידה חסר")
        
        birth_year = self.client.birth_date.year
        return birth_year + self.retirement_age
    
    def _get_retirement_age(self) -> int:
        """מחזיר את גיל הפרישה"""
        return self.retirement_age
    
    def _verify_fixation_and_exempt_pension(self):
        """וידוא קיום קיבוע זכויות וקצבה פטורה"""
        # Check for fixation result
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).first()
        
        if not fixation:
            logger.warning("  ⚠️ No fixation result found for client")
        else:
            logger.info("  ✅ Fixation result exists")
        
        # Check for exempt pension in additional income
        exempt_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id,
            AdditionalIncome.tax_treatment == "exempt"
        ).all()
        
        if not exempt_incomes:
            logger.warning("  ⚠️ No exempt pension income found")
        else:
            logger.info(f"  ✅ Found {len(exempt_incomes)} exempt income sources")
    
    def _calculate_npv(self, monthly_pension: float, monthly_additional: float, capital: float, 
                       discount_rate: float = 0.03) -> float:
        """
        מחשב NPV באמצעות שיטת DCF (Discounted Cash Flow) עד גיל 90
        
        Args:
            monthly_pension: קצבה חודשית
            monthly_additional: הכנסה נוספת חודשית
            capital: הון חד-פעמי
            discount_rate: שיעור היוון שנתי (ברירת מחדל 3%)
            
        Returns:
            NPV כערך נוכחי נקי
            
        Note:
            החישוב מבוצע עד גיל 90 של הלקוח, לא תקופה קבועה.
            ריבית היוון: 3% לשנה (לפי מפרט המערכת)
        """
        # חישוב מספר שנים עד גיל 90
        if not self.client or not self.client.birth_date:
            years_to_90 = 30  # ברירת מחדל אם אין תאריך לידה
        else:
            current_age = (date.today() - self.client.birth_date).days / 365.25
            retirement_age = self.retirement_age
            years_to_90 = max(1, int(90 - retirement_age))  # מגיל פרישה עד גיל 90
        
        logger.info(f"  📊 NPV Calculation: retirement_age={self.retirement_age}, years_to_90={years_to_90}, discount_rate={discount_rate}")
        
        # הון חד-פעמי בשנה 0 (לא מהוון)
        npv = float(capital)
        
        # חישוב חודשי עם היוון חודשי
        monthly_income = monthly_pension + monthly_additional
        monthly_discount_rate = (1 + discount_rate) ** (1/12) - 1  # המרה לריבית חודשית
        
        # הוספת תזרימי מזומנים חודשיים מהוונים
        total_months = years_to_90 * 12
        for month in range(1, total_months + 1):
            discounted_cashflow = monthly_income / ((1 + monthly_discount_rate) ** month)
            npv += discounted_cashflow
        
        logger.info(f"  💰 NPV Result: total_months={total_months}, monthly_income={monthly_income:.2f}, npv={npv:.2f}")
        
        return round(npv, 2)
    
    def _calculate_scenario_results(self, scenario_name: str) -> Dict:
        """מחשב NPV ומחזיר את תוצאות התרחיש"""
        # Get current state
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        
        additional_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id
        ).all()
        
        # Calculate totals
        total_pension = sum(pf.pension_amount or 0 for pf in pension_funds)
        # ✅ תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
        total_capital_monthly = sum(float(ca.monthly_income or 0) for ca in capital_assets)
        
        # ✅ תוקן: חישוב הכנסות נוספות לפי תדירות
        total_additional = 0
        for ai in additional_incomes:
            if ai.frequency == "monthly":
                total_additional += float(ai.amount)
            elif ai.frequency == "quarterly":
                total_additional += float(ai.amount) / 3  # ממוצע חודשי
            elif ai.frequency == "annually":
                total_additional += float(ai.amount) / 12  # ממוצע חודשי
            else:
                total_additional += float(ai.amount)  # ברירת מחדל
        
        # חישוב NPV תקין באמצעות DCF
        # נכסי הון הם תשלום חודשי, לא הון חד-פעמי
        npv = self._calculate_npv(
            monthly_pension=total_pension,
            monthly_additional=total_additional + total_capital_monthly,  # ✅ נכסי הון = תשלום חודשי
            capital=0,  # ✅ אין הון חד-פעמי
            discount_rate=0.03  # ✅ 3% שיעור היוון (לפי מפרט המערכת)
        )
        
        logger.info(f"  📊 {scenario_name} Results:")
        logger.info(f"     Total Pension: {total_pension} ₪/month")
        logger.info(f"     Total Capital (monthly): {total_capital_monthly} ₪/month")
        logger.info(f"     Total Additional: {total_additional} ₪/month")
        logger.info(f"     Estimated NPV (DCF): {npv} ₪")
        
        return {
            "scenario_name": scenario_name,
            "total_pension_monthly": total_pension,
            "total_capital": total_capital_monthly,  # ✅ תוקן: נכסי הון = תשלום חודשי
            "total_additional_income_monthly": total_additional,
            "estimated_npv": npv,
            "pension_funds_count": len(pension_funds),
            "capital_assets_count": len(capital_assets),
            "additional_incomes_count": len(additional_incomes),
            "execution_plan": self.actions  # מפרט ביצוע מפורט
        }
    
    # Serialization helpers
    
    def _serialize_pension_fund(self, pf: PensionFund) -> Dict:
        """ממיר PensionFund לדיקשנרי"""
        return {
            "client_id": pf.client_id,
            "fund_name": pf.fund_name,
            "fund_type": pf.fund_type,
            "input_mode": pf.input_mode,
            "balance": float(pf.balance) if pf.balance else None,
            "annuity_factor": float(pf.annuity_factor) if pf.annuity_factor else None,
            "pension_amount": float(pf.pension_amount) if pf.pension_amount else None,
            "pension_start_date": pf.pension_start_date,
            "indexation_method": pf.indexation_method,
            "fixed_index_rate": float(pf.fixed_index_rate) if pf.fixed_index_rate else None,
            "indexed_pension_amount": float(pf.indexed_pension_amount) if pf.indexed_pension_amount else None,
            "remarks": pf.remarks,
            "deduction_file": pf.deduction_file,
            "conversion_source": pf.conversion_source
        }
    
    def _serialize_capital_asset(self, ca: CapitalAsset) -> Dict:
        """ממיר CapitalAsset לדיקשנרי"""
        return {
            "client_id": ca.client_id,
            "asset_name": ca.asset_name,
            "asset_type": ca.asset_type,
            "description": ca.description,
            "current_value": float(ca.current_value),
            "monthly_income": float(ca.monthly_income) if ca.monthly_income else None,
            "annual_return_rate": float(ca.annual_return_rate),
            "payment_frequency": ca.payment_frequency,
            "start_date": ca.start_date,
            "end_date": ca.end_date,
            "indexation_method": ca.indexation_method,
            "fixed_rate": float(ca.fixed_rate) if ca.fixed_rate else None,
            "tax_treatment": ca.tax_treatment,
            "tax_rate": float(ca.tax_rate) if ca.tax_rate else None,
            "spread_years": ca.spread_years,
            "remarks": ca.remarks,
            "conversion_source": ca.conversion_source
        }
    
    def _serialize_additional_income(self, ai: AdditionalIncome) -> Dict:
        """ממיר AdditionalIncome לדיקשנרי"""
        return {
            "client_id": ai.client_id,
            "source_type": ai.source_type,
            "description": ai.description,
            "amount": float(ai.amount),
            "frequency": ai.frequency,
            "start_date": ai.start_date,
            "end_date": ai.end_date,
            "indexation_method": ai.indexation_method,
            "fixed_rate": float(ai.fixed_rate) if ai.fixed_rate else None,
            "tax_treatment": ai.tax_treatment,
            "tax_rate": float(ai.tax_rate) if ai.tax_rate else None,
            "remarks": ai.remarks
        }
    
    def _serialize_termination_event(self, te: TerminationEvent) -> Dict:
        """ממיר TerminationEvent לדיקשנרי"""
        return {
            "client_id": te.client_id,
            "employment_id": te.employment_id,
            "planned_termination_date": te.planned_termination_date,
            "actual_termination_date": te.actual_termination_date,
            "reason": te.reason,
            "severance_basis_nominal": float(te.severance_basis_nominal) if te.severance_basis_nominal else None,
            "package_paths": te.package_paths
        }
