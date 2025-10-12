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
    """מעבד קבצי XML של המסלקה לחילוץ נתוני תיק פנסיוני"""
    
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
    
    def process_xml_content(self, xml_content: str, file_name: str) -> List[dict]:
        """עיבוד תוכן XML לחילוץ נתוני חשבונות פנסיוניים"""
        try:
            # ניקוי תוכן XML
            xml_content = xml_content.replace('\x1a', '')
            root = ET.fromstring(xml_content)
            
            accounts = []
            account_elements = self._find_account_elements(root)
            
            for account_elem in account_elements:
                account_data = self._extract_account_data(account_elem, file_name)
                if account_data:
                    accounts.append(account_data)
            
            return accounts
            
        except ET.ParseError as e:
            raise HTTPException(status_code=400, detail=f"שגיאה בניתוח XML בקובץ {file_name}: {str(e)}")
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
    """עיבוד קבצי XML של המסלקה"""
    
    if not files:
        raise HTTPException(status_code=400, detail="לא נבחרו קבצים")
    
    processor = PensionPortfolioProcessor()
    all_accounts = []
    processed_files = []
    
    for file in files:
        if not file.filename.lower().endswith('.xml'):
            continue
        
        try:
            content = await file.read()
            xml_content = content.decode('utf-8')
            
            accounts = processor.process_xml_content(xml_content, file.filename)
            all_accounts.extend(accounts)
            
            processed_files.append({
                'file': file.filename,
                'accounts': accounts,
                'processed_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"שגיאה בעיבוד קובץ {file.filename}: {str(e)}"
            )
    
    return {
        'total_accounts': len(all_accounts),
        'processed_files': processed_files,
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
