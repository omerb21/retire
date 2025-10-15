from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Optional
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import subprocess
import tempfile
from pathlib import Path

router = APIRouter()

# מיפוי סוגי מוצרים
PRODUCT_TYPE_MAP = {
    '1': 'פוליסת ביטוח חיים משולב חיסכון',
    '2': 'פוליסת ביטוח חיים',
    '3': 'קופת גמל',
    '4': 'קרן פנסיה',
    '5': 'פוליסת חיסכון טהור'
}

class PensionPortfolioProcessor:
    """מעבד קבצי XML ו-DAT של המסלקה לחילוץ נתוני תיק פנסיוני"""
    
    def __init__(self):
        # יתרה - לפי הקוד המקורי, TOTAL-CHISACHON-MTZBR הוא השדה העיקרי
        self.balance_fields = [
            'TOTAL-CHISACHON-MTZBR',  # השדה העיקרי לפי הקוד המקורי
            'TOTAL-ERKEI-PIDION', 
            'YITRAT-KASPEY-TAGMULIM',
            'YITRAT-PITZUIM'
        ]
        
        self.account_elements = [
            'HeshbonOPolisa', 'Heshbon', 'Account', 'Policy', 'Polisa',
            'PensionAccount', 'PensionPolicy', 'KupatGemel', 'BituachMenahalim', 'KerenPensia'
        ]
    
    def process_file_content(self, content: str, file_name: str) -> List[dict]:
        """עיבוד תוכן XML או DAT לחילוץ נתוני חשבונות פנסיוניים"""
        try:
            # ניקוי תוכן - הסרת תווים מיוחדים שעלולים להפריע לפרסור
            content = content.replace('\x1a', '')  # תו EOF
            content = content.replace('\x00', '')  # תו NULL
            content = content.strip()
            
            # ניסיון לפרסר כ-XML
            root = ET.fromstring(content)
            
            accounts = []
            account_elements = self._find_account_elements(root)
            
            for account_elem in account_elements:
                account_data = self._extract_account_data(account_elem, file_name)
                if account_data:
                    accounts.append(account_data)
            
            return accounts
            
        except ET.ParseError as e:
            # אם הפרסור נכשל, ננסה טיפול חלופי
            print(f"נסיון פרסור ישיר נכשל עבור {file_name}, מנסה עיבוד מתקדם...")
            try:
                # שלב 1: ניסיון לתקן XML פגום
                fixed_content = self._try_fix_xml(content)
                root = ET.fromstring(fixed_content)
                
                accounts = []
                account_elements = self._find_account_elements(root)
                
                for account_elem in account_elements:
                    account_data = self._extract_account_data(account_elem, file_name)
                    if account_data:
                        accounts.append(account_data)
                
                print(f"תיקון XML הצליח עבור {file_name}, נמצאו {len(accounts)} חשבונות")
                return accounts
                
            except Exception as xml_fix_error:
                # שלב 2: אם גם תיקון XML נכשל, נסה regex fallback
                print(f"תיקון XML נכשל עבור {file_name}, מנסה חילוץ regex...")
                try:
                    accounts = self._extract_with_regex_fallback(content, file_name)
                    if accounts:
                        print(f"חילוץ regex הצליח עבור {file_name}, נמצאו {len(accounts)} חשבונות")
                        return accounts
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"לא הצלחתי לחלץ נתונים מקובץ {file_name}. הקובץ עשוי להיות פגום או בפורמט לא נתמך."
                        )
                except HTTPException:
                    raise
                except Exception as regex_error:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"שגיאה בניתוח קובץ {file_name}. פרסור XML נכשל: {str(e)}. תיקון נכשל: {str(xml_fix_error)}. חילוץ regex נכשל: {str(regex_error)}"
                    )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"שגיאה בעיבוד קובץ {file_name}: {str(e)}")
    
    def _find_account_elements(self, root: ET.Element) -> List[ET.Element]:
        """חיפוש אלמנטי חשבונות ב-XML"""
        account_elements = []
        
        # חיפוש לפי שמות אלמנטים מוכרים
        for elem_name in self.account_elements:
            elements = root.findall(f'.//{elem_name}')
            account_elements.extend(elements)
        
        # אם לא נמצאו, חיפוש לפי ילדים רלוונטיים
        if not account_elements:
            for elem in root.iter():
                if self._has_account_children(elem):
                    account_elements.append(elem)
        
        # אם עדיין לא נמצאו, השתמש ב-root אם יש בו נתוני חשבון
        if not account_elements and self._has_account_data(root):
            account_elements = [root]
        
        return account_elements
    
    def _has_account_children(self, elem: ET.Element) -> bool:
        """בדיקה אם לאלמנט יש ילדים המאפיינים חשבון"""
        account_tags = [
            'MISPAR-POLISA-O-HESHBON', 'MISPAR-HESHBON', 'MISPAR-POLISA',
            'SHEM-YATZRAN', 'YATZRAN', 'SHEM-TOCHNIT', 'TOCHNIT'
        ]
        return any(child.tag in account_tags for child in elem)
    
    def _has_account_data(self, elem: ET.Element) -> bool:
        """בדיקה אם באלמנט יש נתוני חשבון"""
        return (elem.find('.//MISPAR-POLISA-O-HESHBON') is not None or
                elem.find('.//MISPAR-HESHBON') is not None or
                elem.find('.//MISPAR-POLISA') is not None)
    
    def _try_fix_xml(self, content: str) -> str:
        """ניסיון לתקן XML פגום - טיפול בבעיות נפוצות בקבצי DAT"""
        import re
        
        # הסרת תווים לא חוקיים נוספים (שמירה על תווי עברית)
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', content)
        
        # הוספת XML declaration אם חסר
        if not content.strip().startswith('<?xml'):
            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
        
        # תיקון רווחים בתגיות
        content = re.sub(r'<\s+', '<', content)
        content = re.sub(r'\s+>', '>', content)
        
        # תיקון תגיות לא מאוזנות - ניסיון בסיסי
        # מחפש תגיות פתיחה ללא סגירה מתאימה
        try:
            # ספירת תגיות פתיחה וסגירה
            open_tags = re.findall(r'<([A-Za-z0-9\-]+)[^>]*>', content)
            close_tags = re.findall(r'</([A-Za-z0-9\-]+)>', content)
            
            # אם יש תגיות פתיחה שאין להן סגירה, נוסיף תגית root
            if len(open_tags) > len(close_tags):
                # עטוף בתגית root אם אין כזו
                if not re.search(r'<root', content, re.IGNORECASE):
                    # מצא את סוף ה-XML declaration
                    xml_decl_end = content.find('?>') + 2 if '?>' in content else 0
                    before = content[:xml_decl_end]
                    after = content[xml_decl_end:]
                    content = before + '\n<root>\n' + after.strip() + '\n</root>'
        except Exception:
            pass  # אם נכשל, נשאיר את התוכן כמו שהוא
        
        return content
    
    def _extract_with_regex_fallback(self, content: str, file_name: str) -> List[dict]:
        """חילוץ נתונים באמצעות regex כ-fallback כשפרסור XML נכשל"""
        import re
        
        print(f"מנסה חילוץ regex עבור {file_name}...")
        accounts = []
        
        # חיפוש דפוסי חשבונות באמצעות regex
        # דוגמה: מחפש תגיות חשבון עם נתונים בסיסיים
        account_patterns = [
            r'<HeshbonOPolisa[^>]*>.*?</HeshbonOPolisa>',
            r'<Heshbon[^>]*>.*?</Heshbon>',
            r'<Account[^>]*>.*?</Account>'
        ]
        
        for pattern in account_patterns:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    account_text = match.group(0)
                    
                    # ניסיון לפרסר את הקטע הספציפי
                    account_elem = ET.fromstring(account_text)
                    account_data = self._extract_account_data(account_elem, file_name)
                    if account_data:
                        accounts.append(account_data)
                except Exception:
                    continue
        
        return accounts
    
    def _extract_account_data(self, account_elem: ET.Element, file_name: str) -> Optional[dict]:
        """חילוץ נתוני חשבון מאלמנט XML"""
        
        def get_text(tag_name: str) -> str:
            elem = account_elem.find(f'.//{tag_name}')
            return elem.text.strip() if elem is not None and elem.text else ''
        
        def get_float(tag_name: str) -> float:
            text = get_text(tag_name)
            if not text:
                return 0.0
            try:
                return float(text.replace(',', ''))
            except ValueError:
                return 0.0
        
        # מספר חשבון
        account_number = (get_text('MISPAR-POLISA-O-HESHBON') or
                         get_text('MISPAR-HESHBON') or
                         get_text('MISPAR-POLISA') or
                         'לא ידוע')
        
        # שם תכנית
        plan_name = (get_text('SHEM-TOCHNIT') or
                    get_text('TOCHNIT') or
                    get_text('SHEM_TOCHNIT') or
                    'לא ידוע')
        
        # חברה מנהלת - לפי הקוד המקורי
        managing_company = (get_text('SHEM-YATZRAN') or
                           get_text('SHEM-METAFEL') or
                           get_text('SHEM_HA_MOSAD') or
                           get_text('Provider') or
                           get_text('Company') or
                           'לא ידוע')
        
        # קוד חברה מנהלת
        company_code = (get_text('KOD-MEZAHE-YATZRAN') or
                       get_text('KOD-YATZRAN') or
                       get_text('MEZAHE-YATZRAN'))
        
        # יתרה - חיפוש בשדות שונים
        balance = 0.0
        for field in self.balance_fields:
            value = get_float(field)
            if value > 0:
                balance = value
                break
        
        # תאריך נכונות יתרה
        balance_date = (get_text('TAARICH-NECHONUT-YITROT') or
                       get_text('TAARICH-YITROT') or
                       get_text('TAARICH-NECHONUT') or
                       'לא ידוע')
        
        # תאריך התחלה
        start_date = (get_text('TAARICH-TCHILAT-HAFRASHA') or
                     get_text('TAARICH-TCHILA') or
                     get_text('TAARICH-HITZTARFUT-RISHON') or
                     get_text('TAARICH-HITZTARFUT'))
        
        # סוג מוצר
        product_type_code = (get_text('SUG-MUTZAR') or
                            get_text('SUG-TOCHNIT-O-CHESHBON') or
                            get_text('SUG-POLISA'))
        
        product_type = PRODUCT_TYPE_MAP.get(product_type_code, product_type_code or 'לא ידוע')
        
        # מעסיקים היסטוריים - חיפוש מורחב
        employer_tags = ['SHEM-MAASIK', 'SHEM-MESHALEM', 'SHEM-BAAL-POLISA', 'SHEM-MAFKID']
        employers = []
        
        for tag in employer_tags:
            employer_elements = account_elem.findall(f'.//{tag}')
            for emp_elem in employer_elements:
                if emp_elem.text and emp_elem.text.strip():
                    employer = emp_elem.text.strip()
                    if employer not in employers:
                        employers.append(employer)

        # פיצויים - חילוץ נתוני פיצויים מסוגים שונים
        פיצויים_מעסיק_נוכחי = get_float('YITRAT-PITZUIM-MAASIK-NOCHECHI') or get_float('ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI') or 0
        פיצויים_לאחר_התחשבנות = get_float('YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM') or get_float('ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM') or 0
        פיצויים_שלא_עברו_התחשבנות = get_float('YITRAT-PITZUIM-SHELO-AVRU-HITCHASHVUT') or 0
        פיצויים_ממעסיקים_קודמים_רצף_זכויות = get_float('PITZUIM-MAAVIDIM-KODMIM-RETZEF-ZCHUYOT') or 0
        פיצויים_ממעסיקים_קודמים_רצף_קצבה = get_float('PITZUIM-MAAVIDIM-KODMIM-RETZEF-KITZBA') or 0

        # תגמולים - חילוץ נתוני תגמולים לפי תקופות
        תגמולי_עובד_עד_2000 = get_float('TAGMULIM-OVED-AD-2000') or 0
        תגמולי_עובד_אחרי_2000 = get_float('TAGMULIM-OVED-ACHAREI-2000') or 0
        תגמולי_עובד_אחרי_2008_לא_משלמת = get_float('TAGMULIM-OVED-ACHAREI-2008-LO-MESHALMET') or 0
        תגמולי_מעביד_עד_2000 = get_float('TAGMULIM-MAAVID-AD-2000') or 0
        תגמולי_מעביד_אחרי_2000 = get_float('TAGMULIM-MAAVID-ACHAREI-2000') or 0
        תגמולי_מעביד_אחרי_2008_לא_משלמת = get_float('TAGMULIM-MAAVID-ACHAREI-2008-LO-MESHALMET') or 0
        
        # רק אם יש מידע משמעותי
        if account_number == 'לא ידוע' and plan_name == 'לא ידוע' and balance == 0:
            return None
        
        return {
            'מספר_חשבון': account_number,
            'שם_תכנית': plan_name,
            'חברה_מנהלת': managing_company,
            'קוד_חברה_מנהלת': company_code,
            'יתרה': balance,
            'תאריך_נכונות_יתרה': balance_date,
            'תאריך_התחלה': start_date,
            'סוג_מוצר': product_type,
            'מעסיקים_היסטוריים': ', '.join(employers),
            'פיצויים_מעסיק_נוכחי': פיצויים_מעסיק_נוכחי,
            'פיצויים_לאחר_התחשבנות': פיצויים_לאחר_התחשבנות,
            'פיצויים_שלא_עברו_התחשבנות': פיצויים_שלא_עברו_התחשבנות,
            'פיצויים_ממעסיקים_קודמים_רצף_זכויות': פיצויים_ממעסיקים_קודמים_רצף_זכויות,
            'פיצויים_ממעסיקים_קודמים_רצף_קצבה': פיצויים_ממעסיקים_קודמים_רצף_קצבה,
            'תגמולי_עובד_עד_2000': תגמולי_עובד_עד_2000,
            'תגמולי_עובד_אחרי_2000': תגמולי_עובד_אחרי_2000,
            'תגמולי_עובד_אחרי_2008_לא_משלמת': תגמולי_עובד_אחרי_2008_לא_משלמת,
            'תגמולי_מעביד_עד_2000': תגמולי_מעביד_עד_2000,
            'תגמולי_מעביד_אחרי_2000': תגמולי_מעביד_אחרי_2000,
            'תגמולי_מעביד_אחרי_2008_לא_משלמת': תגמולי_מעביד_אחרי_2008_לא_משלמת,
            'קובץ_מקור': file_name
        }

@router.post("/clients/{client_id}/pension-portfolio/process-xml")
async def process_pension_xml_files(
    client_id: int,
    files: List[UploadFile] = File(...)
):
    """עיבוד קבצי XML ו-DAT של המסלקה"""
    
    if not files:
        raise HTTPException(status_code=400, detail="לא נבחרו קבצים")
    
    processor = PensionPortfolioProcessor()
    all_accounts = []
    processed_files = []
    skipped_files = []
    
    for file in files:
        filename_lower = file.filename.lower()
        
        # תמיכה בקבצי XML ו-DAT
        if not (filename_lower.endswith('.xml') or filename_lower.endswith('.dat')):
            skipped_files.append({
                'file': file.filename,
                'reason': 'סוג קובץ לא נתמך (נדרש XML או DAT)'
            })
            continue
        
        try:
            content = await file.read()
            
            # ניסיון לפענח עם קידודים שונים
            file_content = None
            for encoding in ['utf-8', 'windows-1255', 'iso-8859-8', 'latin1']:
                try:
                    file_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"לא הצלחתי לפענח את הקובץ {file.filename}. קידוד לא נתמך"
                )
            
            accounts = processor.process_file_content(file_content, file.filename)
            all_accounts.extend(accounts)
            
            processed_files.append({
                'file': file.filename,
                'file_type': 'DAT' if filename_lower.endswith('.dat') else 'XML',
                'accounts_count': len(accounts),
                'accounts': accounts,
                'processed_at': datetime.now().isoformat()
            })
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"שגיאה בעיבוד קובץ {file.filename}: {str(e)}"
            )
    
    return {
        'total_accounts': len(all_accounts),
        'processed_files_count': len(processed_files),
        'skipped_files_count': len(skipped_files),
        'processed_files': processed_files,
        'skipped_files': skipped_files,
        'accounts': all_accounts
    }

@router.get("/clients/{client_id}/pension-portfolio/")
async def get_pension_portfolio(client_id: int):
    """קבלת נתוני תיק פנסיוני קיימים"""
    # כאן ניתן לטעון נתונים שנשמרו קודם במסד הנתונים
    # לעת עתה נחזיר רשימה ריקה
    return []

@router.post("/clients/{client_id}/pension-portfolio/save")
async def save_pension_portfolio(
    client_id: int,
    portfolio_data: dict
):
    """שמירת נתוני תיק פנסיוני"""
    # כאן ניתן לשמור את הנתונים במסד הנתונים
    # לעת עתה נחזיר הצלחה
    return {
        'message': 'נתוני התיק הפנסיוני נשמרו בהצלחה',
        'client_id': client_id,
        'accounts_count': len(portfolio_data.get('accounts', []))
    }

@router.post("/clients/{client_id}/pension-portfolio/convert")
async def convert_pension_accounts(
    client_id: int,
    conversion_data: dict
):
    """המרת חשבונות פנסיוניים לקצבאות או נכסי הון"""
    
    accounts = conversion_data.get('accounts', [])
    if not accounts:
        raise HTTPException(status_code=400, detail="לא נבחרו חשבונות להמרה")
    
    converted_accounts = []
    
    for account in accounts:
        conversion_type = account.get('conversion_type')
        
        if conversion_type == 'pension':
            # המרה לקצבה
            pension_data = {
                'fund_name': account.get('שם_תכנית'),
                'managing_company': account.get('חברה_מנהלת'),
                'deduction_file': account.get('מספר_חשבון'),
                'calculation_mode': 'manual',
                'pension_amount': round(account.get('יתרה', 0) * 0.04 / 12),  # 4% שנתי
                'pension_start_date': '2025-01-01',
                'indexation_method': 'cpi'
            }
            converted_accounts.append({
                'type': 'pension',
                'original_account': account.get('מספר_חשבון'),
                'data': pension_data
            })
            
        elif conversion_type == 'capital_asset':
            # המרה לנכס הון
            asset_type = 'provident_fund' if 'קופת גמל' in account.get('סוג_מוצר', '') else 'education_fund'
            
            asset_data = {
                'asset_type': asset_type,
                'description': account.get('שם_תכנית'),
                'current_value': account.get('יתרה', 0),
                'purchase_value': account.get('יתרה', 0),
                'purchase_date': account.get('תאריך_התחלה', '2020-01-01'),
                'annual_return': 0,
                'annual_return_rate': 0.03,
                'payment_frequency': 'monthly',
                'liquidity': 'medium',
                'risk_level': 'medium',
                'monthly_income': round(account.get('יתרה', 0) * 0.03 / 12),
                'start_date': '2025-01-01',
                'indexation_method': 'cpi',
                'tax_treatment': 'capital_gains'
            }
            converted_accounts.append({
                'type': 'capital_asset',
                'original_account': account.get('מספר_חשבון'),
                'data': asset_data
            })
    
    return {
        'message': f'הומרו בהצלחה {len(converted_accounts)} חשבונות',
        'converted_accounts': converted_accounts
    }

@router.post("/clients/{client_id}/pension-portfolio/restore")
async def restore_pension_amounts(
    client_id: int,
    restore_data: dict
):
    """החזרת סכומים שהומרו חזרה לתיק הפנסיוני
    
    נקרא כאשר מוחקים קצבה או נכס הון שמקורם בהמרה מתיק פנסיוני.
    הפונקציה מחזירה את הסכומים לשדות המקוריים בטבלה.
    
    בשלב זה, הפונקציה מחזירה הצלחה כיוון שהנתונים נשמרים ב-localStorage בצד הלקוח.
    בעתיד ניתן להוסיף שמירה במסד נתונים.
    """
    
    account_name = restore_data.get('account_name')
    company = restore_data.get('company')
    account_number = restore_data.get('account_number')
    product_type = restore_data.get('product_type')
    amount = restore_data.get('amount')
    specific_amounts = restore_data.get('specific_amounts', {})
    
    if not account_name or not amount:
        raise HTTPException(
            status_code=400,
            detail="חסרים פרטים נדרשים להחזרת הסכומים"
        )
    
    # כאן ניתן להוסיף לוגיקה לעדכון מסד נתונים אם נשמור את נתוני התיק הפנסיוני
    # לעת עתה, הנתונים מנוהלים ב-localStorage בצד הלקוח
    
    return {
        'success': True,
        'message': 'הסכומים הוחזרו בהצלחה לתיק הפנסיוני',
        'restored_account': {
            'account_name': account_name,
            'company': company,
            'account_number': account_number,
            'product_type': product_type,
            'amount': amount,
            'specific_amounts': specific_amounts
        }
    }

@router.post("/clients/{client_id}/pension-portfolio/process-directory")
async def process_pension_directory(
    client_id: int,
    directory_path: str
):
    """עיבוד תיקייה של קבצי XML באמצעות הסקריפט הקיים"""
    
    # נתיב לתיקיית NESS
    ness_dir = Path(__file__).parent.parent.parent / "NESS"
    process_script = ness_dir / "process_pensions.py"
    
    if not process_script.exists():
        raise HTTPException(
            status_code=404, 
            detail="סקריפט עיבוד המסלקה לא נמצא"
        )
    
    try:
        # הרצת הסקריפט
        result = subprocess.run(
            ["python", str(process_script)],
            cwd=str(ness_dir),
            capture_output=True,
            text=True,
            timeout=300  # 5 דקות timeout
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"שגיאה בהרצת סקריפט העיבוד: {result.stderr}"
            )
        
        # קריאת תוצאות
        results_file = ness_dir / "DATA" / "pension_results.json"
        if results_file.exists():
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            return results
        else:
            raise HTTPException(
                status_code=404,
                detail="קובץ תוצאות לא נמצא"
            )
            
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="עיבוד הקבצים ארך יותר מדי זמן"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בעיבוד התיקייה: {str(e)}"
        )
