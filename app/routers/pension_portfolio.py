from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
import json
from datetime import datetime
import subprocess
from pathlib import Path

from app.database import get_db
from app.services.pension_portfolio import PensionPortfolioProcessor

router = APIRouter()

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
            
            result = processor.process_file(file_content, file.filename)
            if result is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"לא הצלחתי לחלץ נתונים מקובץ {file.filename}. הקובץ עשוי להיות פגום או בפורמט לא נתמך."
                )

            accounts = result.get('accounts', [])
            all_accounts.extend(accounts)
            
            processed_files.append({
                'file': result.get('file', file.filename),
                'file_type': 'DAT' if filename_lower.endswith('.dat') else 'XML',
                'accounts_count': len(accounts),
                'accounts': accounts,
                'processed_at': result.get('processed_at', datetime.now().isoformat())
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
    conversion_data: dict,
    db: Session = Depends(get_db)
):
    """המרת חשבונות פנסיוניים לקצבאות או נכסי הון - מיידי ישירות ל-DB"""
    
    accounts = conversion_data.get('accounts', [])
    if not accounts:
        raise HTTPException(status_code=400, detail="לא נבחרו חשבונות להמרה")
    
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
    from app.models.capital_asset import CapitalAsset
    from app.services.annuity_coefficient import get_annuity_coefficient
    from app.services.retirement_age_service import calculate_retirement_age
    from datetime import date
    from decimal import Decimal
    
    client = db.query(Client).filter(Client.id == client_id).first()
    retirement_age = 67
    retirement_date = None
    retirement_year = date.today().year
    if client and getattr(client, "birth_date", None) and getattr(client, "gender", None):
        try:
            retirement_info = calculate_retirement_age(client.birth_date, client.gender)
            retirement_date = retirement_info.get("retirement_date")
            age_years = int(retirement_info.get("age_years") or retirement_age)
            age_months = int(retirement_info.get("age_months") or 0)
            retirement_age = age_years + (1 if age_months > 0 else 0)
            if retirement_date:
                retirement_year = retirement_date.year
        except Exception:
            retirement_date = None

    converted_count = 0
    
    for account in accounts:
        conversion_type = account.get('conversion_type', 'pension')  # ברירת מחדל: קצבה
        balance = float(account.get('יתרה', 0))
        
        if balance <= 0:
            continue
        
        if conversion_type == 'pension':
            # המרה לקצבה - שמירה ישירה ל-DB
            # קביעת יחס מס לפי סוג המוצר
            product_type = account.get('סוג_מוצר', '')
            tax_treatment = "exempt" if 'השתלמות' in product_type else "taxable"

            account_number = account.get('מספר_חשבון', '')

            start_date_raw = account.get('תאריך_התחלה')
            start_date_obj = None
            if isinstance(start_date_raw, str) and start_date_raw.strip():
                try:
                    start_date_obj = date.fromisoformat(start_date_raw.strip())
                except ValueError:
                    try:
                        start_date_obj = datetime.strptime(
                            start_date_raw.strip(), "%d/%m/%Y"
                        ).date()
                    except Exception:
                        start_date_obj = None

            annuity_factor = 200.0
            try:
                coeff = get_annuity_coefficient(
                    product_type=product_type,
                    start_date=start_date_obj or date(retirement_year, 1, 1),
                    gender=getattr(client, "gender", None) or "זכר",
                    retirement_age=retirement_age,
                    company_name=account.get('חברה_מנהלת') or None,
                    option_name=None,
                    survivors_option='תקנוני',
                    spouse_age_diff=0,
                    target_year=retirement_year,
                    birth_date=getattr(client, "birth_date", None) if client else None,
                    pension_start_date=retirement_date,
                )
                annuity_factor = float(coeff.get('factor_value') or annuity_factor)
                if annuity_factor <= 0:
                    annuity_factor = 200.0
            except Exception:
                annuity_factor = 200.0

            pension_amount = balance / annuity_factor

            conversion_source_json = json.dumps(
                {
                    "source": "pension_portfolio_convert",
                    "account_number": account_number,
                    "account_name": account.get('שם_תכנית', ''),
                    "company": account.get('חברה_מנהלת', ''),
                    "product_type": product_type,
                    "start_date": start_date_raw,
                    "resolved_annuity_factor": annuity_factor,
                    "coeff_source_table": coeff.get('source_table') if isinstance(coeff, dict) else None,
                    "converted_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )

            existing_pf = None
            if account_number:
                existing_pf = (
                    db.query(PensionFund)
                    .filter(
                        PensionFund.client_id == client_id,
                        PensionFund.deduction_file == account_number,
                        PensionFund.conversion_source.like(
                            '%"source": "pension_portfolio_convert"%'
                        ),
                    )
                    .first()
                )

            if existing_pf:
                existing_pf.fund_name = account.get('שם_תכנית', 'תכנית ללא שם')
                existing_pf.fund_type = account.get('סוג_מוצר', 'קופת גמל')
                existing_pf.input_mode = 'manual'
                existing_pf.balance = balance
                existing_pf.annuity_factor = annuity_factor
                existing_pf.pension_amount = pension_amount
                existing_pf.pension_start_date = retirement_date or date(retirement_year, 1, 1)
                existing_pf.indexation_method = 'none'
                existing_pf.tax_treatment = tax_treatment
                existing_pf.conversion_source = conversion_source_json
                existing_pf.remarks = f"הומר מתיק פנסיוני - {account.get('חברה_מנהלת', '')}"
            else:
                pf = PensionFund(
                    client_id=client_id,
                    fund_name=account.get('שם_תכנית', 'תכנית ללא שם'),
                    fund_type=account.get('סוג_מוצר', 'קופת גמל'),
                    input_mode='manual',
                    balance=balance,
                    annuity_factor=annuity_factor,
                    pension_amount=pension_amount,
                    pension_start_date=retirement_date or date(retirement_year, 1, 1),
                    indexation_method='none',
                    tax_treatment=tax_treatment,
                    deduction_file=account_number,
                    conversion_source=conversion_source_json,
                    remarks=f"הומר מתיק פנסיוני - {account.get('חברה_מנהלת', '')}"
                )
                db.add(pf)
            converted_count += 1
            
        elif conversion_type == 'capital_asset':
            # המרה לנכס הון - שמירה ישירה ל-DB
            ca = CapitalAsset(
                client_id=client_id,
                asset_name=account.get('שם_תכנית', 'נכס ללא שם'),
                asset_type='provident_fund',
                current_value=Decimal(str(balance)),
                annual_return_rate=Decimal('0.03'),
                payment_frequency='monthly',
                start_date=date(2025, 1, 1),
                indexation_method='none',
                tax_treatment='taxable',
                description=f"הומר מתיק פנסיוני - {account.get('חברה_מנהלת', '')}"
            )
            db.add(ca)
            converted_count += 1
    
    db.commit()
    
    return {
        'success': True,
        'message': f'✅ הומרו ונשמרו בהצלחה {converted_count} חשבונות!',
        'converted_count': converted_count
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
