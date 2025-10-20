"""
מודול ליצירת מסמכי קיבוע זכויות
"""
from pathlib import Path
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Optional
import logging
import subprocess
import re

from app.models.client import Client
from app.models.grant import Grant
from app.models.pension_fund import PensionFund
from app.services.rights_fixation import calculate_full_fixation
import pdf_filler

logger = logging.getLogger(__name__)

# נתיבים לתבניות
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
TEMPLATE_161D = TEMPLATE_DIR / "161d.pdf"
PACKAGES_DIR = Path(__file__).parent.parent.parent / "packages"


def get_client_package_dir(client_id: int, client_first_name: str, client_last_name: str) -> Path:
    """
    יוצר או מחזיר נתיב לתיקיית חבילת המסמכים של הלקוח
    פורמט: packages/<client_id>_<first_name>_<last_name>/
    """
    # ניקוי שמות מתווים לא חוקיים
    safe_first = re.sub(r'[^\w\s-]', '', client_first_name).strip()
    safe_last = re.sub(r'[^\w\s-]', '', client_last_name).strip()
    
    client_dir_name = f"{client_id}_{safe_first}_{safe_last}"
    client_package_dir = PACKAGES_DIR / client_dir_name
    client_package_dir.mkdir(parents=True, exist_ok=True)
    
    return client_package_dir


def fill_161d_form(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    ממלא טופס 161ד עם נתוני קיבוע זכויות מהDB
    """
    try:
        logger.info(f"📝 Starting form 161d fill for client {client_id}")
        
        # בדיקת קיום טמפלייט
        if not TEMPLATE_161D.exists():
            logger.error(f"❌ Template not found: {TEMPLATE_161D}")
            return None
        
        logger.info(f"✅ Template found: {TEMPLATE_161D}")
        
        # שליפת נתוני לקוח
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(f"❌ Client {client_id} not found")
            return None
        
        logger.info(f"✅ Client data loaded: {client.first_name} {client.last_name}")
        
        # שליפת תוצאות קיבוע זכויות מה-DB
        from app.models.fixation_result import FixationResult
        from sqlalchemy import desc
        
        fixation = db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).order_by(desc(FixationResult.created_at)).first()
        
        if not fixation or not fixation.raw_result:
            logger.error(f"❌ No fixation data found for client {client_id}. Please calculate fixation first!")
            return None
        
        raw_result = fixation.raw_result
        exemption_summary = raw_result.get('exemption_summary', {})
        
        logger.info(f"✅ Fixation data loaded from DB")
        logger.info(f"📊 Raw result keys: {list(raw_result.keys())}")
        logger.info(f"📊 Exemption summary keys: {list(exemption_summary.keys())}")
        logger.info(f"📊 Exemption summary: {exemption_summary}")
        
        # חילוץ כל הנתונים הנדרשים
        eligibility_date = raw_result.get('eligibility_date', '')
        if eligibility_date:
            try:
                if isinstance(eligibility_date, str):
                    eligibility_date = datetime.fromisoformat(eligibility_date).strftime("%d/%m/%Y")
                else:
                    eligibility_date = eligibility_date.strftime("%d/%m/%Y")
            except:
                eligibility_date = ''
        
        # נתוני טופס 161ד
        exempt_capital_initial = exemption_summary.get('exempt_capital_initial', 0)
        total_impact = exemption_summary.get('total_impact', 0)
        remaining_exempt_capital = exemption_summary.get('remaining_exempt_capital', 0)
        exemption_percentage = exemption_summary.get('exemption_percentage', 0)
        
        # חישוב נתונים שחסרים מה-grants
        grants_list = raw_result.get('grants', [])
        grants_nominal = sum(g.get('grant_amount', 0) for g in grants_list)
        grants_indexed = sum(g.get('limited_indexed_amount', 0) for g in grants_list)
        
        # חישוב סך מענקים פטורים (רק מענקים שפוגעים בפטור)
        total_exempt_grants = sum(g.get('limited_indexed_amount', 0) for g in grants_list if g.get('impact_on_exemption', 0) > 0)
        
        # סך פגיעה בפטור = total_impact מה-exemption_summary
        total_impact_on_exemption = total_impact
        
        # חישוב קצבה פטורה (מיתרת הפטור / 180)
        exempt_pension_monthly = remaining_exempt_capital / 180 if remaining_exempt_capital > 0 else 0
        
        # תקרת קצבה מזכה (9,430 לשנת 2025)
        pension_ceiling = 9430
        
        # מענק עתידי משוריין
        reserved_grant = exemption_summary.get('future_grant_reserved', 0)
        reserved_grant_impact = exemption_summary.get('future_grant_impact', 0)
        
        # סך היוונים פטורים
        commutations_total = exemption_summary.get('total_commutations', 0)
        
        # Build address string
        address_parts = []
        if client.address_street:
            address_parts.append(client.address_street)
        if client.address_city:
            address_parts.append(client.address_city)
        client_address = ", ".join(address_parts) if address_parts else ""
        
        field_data = {
            "Today": date.today().strftime("%d/%m/%Y"),
            "ClientFirstName": client.first_name or "",
            "ClientLastName": client.last_name or "",
            "ClientID": client.id_number or "",
            "ClientAddress": client_address,
            "ClientBdate": client.birth_date.strftime("%d/%m/%Y") if client.birth_date else "",
            "Clientphone": client.phone or "",
            "ClientZdate": eligibility_date,
            
            # נתוני קיבוע זכויות
            "ExemptCapitalInitial": f"{exempt_capital_initial:,.0f}",
            "GrantsNominal": f"{grants_nominal:,.0f}",
            "GrantsIndexed": f"{grants_indexed:,.0f}",
            "TotalImpact": f"{total_impact:,.0f}",
            "ReservedGrant": f"{reserved_grant:,.0f}",
            "CommutationsTotal": f"{commutations_total:,.0f}",
            "RemainingExemptCapital": f"{remaining_exempt_capital:,.0f}",
            "PensionCeiling": f"{pension_ceiling:,.0f}",
            "ExemptPensionMonthly": f"{exempt_pension_monthly:,.0f}",
            "ExemptionPercentage": f"{exemption_percentage * 100:.1f}%",
            
            # שדות נוספים לטופס 161ד
            "Clientmaanakpatur": f"{total_exempt_grants:,.0f}",  # סך מענקים פטורים
            "Clientpgiabahon": f"{total_impact_on_exemption:,.0f}",  # סך פגיעה בפטור
            "clientcapsum": f"{commutations_total:,.0f}",  # סך היוונים פטורים
            "clientshiryun": f"{reserved_grant_impact:,.0f}"  # השפעת מענק עתידי משוריין
        }
        
        logger.info(f"📊 Form data prepared:")
        logger.info(f"   - Exempt capital initial: {exempt_capital_initial:,.0f}")
        logger.info(f"   - Grants nominal: {grants_nominal:,.0f}")
        logger.info(f"   - Grants indexed: {grants_indexed:,.0f}")
        logger.info(f"   - Total impact: {total_impact:,.0f}")
        logger.info(f"   - Remaining exempt capital: {remaining_exempt_capital:,.0f}")
        logger.info(f"   - Exempt pension monthly: {exempt_pension_monthly:,.0f}")
        
        # מילוי הטופס
        output_path = output_dir / "טופס_161ד.pdf"
        logger.info(f"📄 Filling PDF form...")
        logger.info(f"   Template: {TEMPLATE_161D}")
        logger.info(f"   Output: {output_path}")
        logger.info(f"   Fields count: {len(field_data)}")
        
        result = pdf_filler.fill_acroform(TEMPLATE_161D, output_path, field_data)
        
        logger.info(f"📊 fill_acroform returned: {result}")
        
        if output_path.exists():
            size = output_path.stat().st_size
            logger.info(f"✅ Form 161d created successfully: {output_path} ({size:,} bytes)")
            return output_path
        else:
            logger.error(f"❌ Form file not created at {output_path}")
            logger.error(f"   fill_acroform returned: {result}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Error creating 161ד form: {e}", exc_info=True)
        return None


def generate_grants_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח מענקים בפורמט HTML - בדיוק כמו בטבלת המענקים במסך קיבוע זכויות
    """
    try:
        logger.info(f"📄 Generating grants appendix for client {client_id}")
        
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(f"Client {client_id} not found")
            return None
        
        # שליפת תוצאות קיבוע זכויות מה-DB
        from app.models.fixation_result import FixationResult
        from sqlalchemy import desc
        
        fixation = db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).order_by(desc(FixationResult.created_at)).first()
        
        if not fixation or not fixation.raw_result:
            logger.warning(f"No fixation data found for client {client_id}")
            return None
        
        raw_result = fixation.raw_result
        grants_summary = raw_result.get('grants', [])
        
        logger.info(f"📊 Raw result keys: {list(raw_result.keys())}")
        logger.info(f"📊 Grants summary count: {len(grants_summary)}")
        if grants_summary:
            logger.info(f"📊 First grant keys: {list(grants_summary[0].keys())}")
            logger.info(f"📊 First grant data: {grants_summary[0]}")
        
        if not grants_summary:
            logger.warning(f"⚠️ No grants in fixation data for client {client_id}")
            return None
        
        # שליפת נתוני Grant מה-DB כדי לקבל תאריכי עבודה
        grants_with_dates = db.query(Grant).filter(Grant.client_id == client_id).all()
        grants_dates_map = {
            g.employer_name: {
                'work_start_date': g.work_start_date.strftime("%d/%m/%Y") if g.work_start_date else "-",
                'work_end_date': g.work_end_date.strftime("%d/%m/%Y") if g.work_end_date else "-"
            }
            for g in grants_with_dates
        }
        
        eligibility_date = raw_result.get('eligibility_date', '')
        if eligibility_date:
            try:
                if isinstance(eligibility_date, str):
                    eligibility_date = datetime.fromisoformat(eligibility_date).date()
            except:
                eligibility_date = None
        
        # יצירת HTML
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>נספח מענקים</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        .total-row {{
            background-color: #ecf0f1;
            font-weight: bold;
        }}
        .client-info {{
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>נספח מענקים - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {client.first_name} {client.last_name}</p>
        <p><strong>תעודת זהות:</strong> {client.id_number or ''}</p>
        <p><strong>תאריך זכאות:</strong> {eligibility_date.strftime("%d/%m/%Y") if eligibility_date else "לא ידוע"}</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>מעסיק</th>
                <th>תאריך תחילה</th>
                <th>תאריך סיום</th>
                <th>סכום נומינלי</th>
                <th>תאריך קבלה</th>
                <th>מענק נומינלי רלוונטי</th>
                <th>מענק פטור צמוד</th>
                <th>השפעה על הפטור</th>
            </tr>
        </thead>
        <tbody>
"""
        
        total_nominal = 0
        total_relevant_nominal = 0
        total_indexed = 0
        total_impact = 0
        
        # שימוש בנתונים מחושבים מקיבוע הזכויות
        for grant in grants_summary:
            employer_name = grant.get('employer_name', '')
            grant_date = grant.get('grant_date', '')
            nominal = grant.get('grant_amount', 0)
            relevant_nominal = grant.get('grant_amount', 0)  # אותו סכום
            indexed = grant.get('limited_indexed_amount', 0)
            impact = grant.get('impact_on_exemption', 0)
            
            # שליפת תאריכי עבודה מה-map
            dates_info = grants_dates_map.get(employer_name, {})
            work_start = dates_info.get('work_start_date', '-')
            work_end = dates_info.get('work_end_date', '-')
            
            html_content += f"""
            <tr>
                <td>{employer_name}</td>
                <td>{work_start}</td>
                <td>{work_end}</td>
                <td>{nominal:,.0f}</td>
                <td>{grant_date}</td>
                <td>{relevant_nominal:,.0f}</td>
                <td>{indexed:,.0f}</td>
                <td>{impact:,.0f}</td>
            </tr>
"""
            
            total_nominal += nominal
            total_relevant_nominal += relevant_nominal
            total_indexed += indexed
            total_impact += impact
        
        html_content += f"""
            <tr class="total-row">
                <td colspan="3">סה"כ</td>
                <td>{total_nominal:,.2f}</td>
                <td></td>
                <td>{total_relevant_nominal:,.2f}</td>
                <td>{total_indexed:,.2f}</td>
                <td>{total_impact:,.2f}</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""
        
        # שמירת HTML
        html_path = output_dir / "grants_appendix.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF אם wkhtmltopdf זמין
        pdf_path = output_dir / "נספח מענקים.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"Grants appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"Error creating grants appendix: {e}", exc_info=True)
        return None


def generate_commutations_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח היוונים בפורמט HTML וממיר ל-PDF
    """
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return None
        
        # שליפת קצבאות
        pensions = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
        
        if not pensions:
            logger.info(f"No pension funds found for client {client_id}")
            return None
        
        # יצירת HTML
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>נספח היוונים</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }}
        th {{
            background-color: #e74c3c;
            color: white;
        }}
        .total-row {{
            background-color: #ecf0f1;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <h1>נספח היוונים - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {client.first_name} {client.last_name}</p>
        <p><strong>תעודת זהות:</strong> {client.id_number or ''}</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>קופת גמל/קרן פנסיה</th>
                <th>יתרה</th>
                <th>קצבה חודשית</th>
                <th>תאריך תחילת קצבה</th>
            </tr>
        </thead>
        <tbody>
"""
        
        total_balance = 0
        total_pension = 0
        
        for pension in pensions:
            balance = pension.balance or 0
            monthly_pension = pension.pension_amount or 0
            start_date = pension.pension_start_date.strftime("%d/%m/%Y") if pension.pension_start_date else ""
            
            html_content += f"""
            <tr>
                <td>{pension.fund_name or ''}</td>
                <td>{balance:,.2f}</td>
                <td>{monthly_pension:,.2f}</td>
                <td>{start_date}</td>
            </tr>
"""
            
            total_balance += balance
            total_pension += monthly_pension
        
        html_content += f"""
            <tr class="total-row">
                <td>סה"כ</td>
                <td>{total_balance:,.2f}</td>
                <td>{total_pension:,.2f}</td>
                <td></td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""
        
        # שמירת HTML
        html_path = output_dir / "commutations_appendix.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF אם wkhtmltopdf זמין
        pdf_path = output_dir / "נספח קצבאות.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"Commutations appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"Error creating commutations appendix: {e}", exc_info=True)
        return None


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """
    ממיר קובץ HTML ל-PDF באמצעות wkhtmltopdf
    """
    # נסה למצוא את wkhtmltopdf
    wkhtmltopdf_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "wkhtmltopdf"  # אם זמין ב-PATH
    ]
    
    wkhtmltopdf_path = None
    for path in wkhtmltopdf_paths:
        try:
            subprocess.run([path, "--version"], capture_output=True, check=True)
            wkhtmltopdf_path = path
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    
    if not wkhtmltopdf_path:
        raise RuntimeError("wkhtmltopdf not found. Please install from https://wkhtmltopdf.org/downloads.html")
    
    # המרה ל-PDF
    cmd = [
        wkhtmltopdf_path,
        '--encoding', 'UTF-8',
        '--page-size', 'A4',
        '--margin-top', '10mm',
        '--margin-right', '10mm',
        '--margin-bottom', '10mm',
        '--margin-left', '10mm',
        str(html_path),
        str(pdf_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"wkhtmltopdf failed: {result.stderr.strip()}")
    
    return pdf_path


def generate_actual_commutations_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח היוונים (ממש היוונים, לא קצבאות) בפורמט HTML וממיר ל-PDF
    """
    try:
        from app.models.capital_asset import CapitalAsset
        
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return None
        
        # שליפת היוונים מנכסי הון (asset_type = 'commutation') - רק פטורים ממס
        commutations = db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.remarks.like('%pension_fund_id=%'),
            CapitalAsset.tax_treatment == 'exempt'  # רק היוונים פטורים ממס
        ).all()
        
        if not commutations:
            logger.info(f"No exempt commutations found for client {client_id}")
            return None
        
        # יצירת HTML
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>נספח היוונים</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        .total-row {{
            background-color: #ecf0f1;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <h1>נספח היוונים - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {client.first_name} {client.last_name}</p>
        <p><strong>תעודת זהות:</strong> {client.id_number or ''}</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>שם המשלם</th>
                <th>תיק ניכויים</th>
                <th>תאריך היוון</th>
                <th>סכום היוון</th>
                <th>סוג ההיוון</th>
            </tr>
        </thead>
        <tbody>
"""
        
        total_amount = 0
        
        for comm in commutations:
            # חילוץ נתונים מה-remarks
            import re
            amount_match = re.search(r'amount=([\d.]+)', comm.remarks or '')
            amount = float(amount_match.group(1)) if amount_match else (comm.current_value or 0)
            
            fund_id_match = re.search(r'pension_fund_id=(\d+)', comm.remarks or '')
            fund_name = comm.asset_name or comm.description or 'לא ידוע'
            
            start_date = comm.start_date.strftime("%d/%m/%Y") if comm.start_date else ""
            tax_treatment = "פטור ממס" if comm.tax_treatment == "exempt" else "חייב במס"
            
            html_content += f"""
            <tr>
                <td>{fund_name}</td>
                <td>-</td>
                <td>{start_date}</td>
                <td>{amount:,.2f}</td>
                <td>{tax_treatment}</td>
            </tr>
"""
            
            total_amount += amount
        
        html_content += f"""
            <tr class="total-row">
                <td colspan="3">סה"כ</td>
                <td>{total_amount:,.2f}</td>
                <td></td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""
        
        # שמירת HTML
        html_path = output_dir / "commutations_appendix.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "נספח היוונים.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"Commutations appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"Error creating commutations appendix: {e}", exc_info=True)
        return None


def generate_summary_table(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר טבלת סיכום קיבוע זכויות בפורמט HTML וממיר ל-PDF
    """
    try:
        from app.models.fixation_result import FixationResult
        
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return None
        
        # שליפת נתוני קיבוע זכויות
        fixation = db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).order_by(FixationResult.created_at.desc()).first()
        
        if not fixation or not fixation.raw_result:
            logger.info(f"No fixation data found for client {client_id}")
            return None
        
        exemption_summary = fixation.raw_result.get('exemption_summary', {})
        grants = fixation.raw_result.get('grants', [])
        
        # חישוב כל הסיכומים מהטבלה המקורית
        exempt_capital_initial = exemption_summary.get('exempt_capital_initial', 0)
        total_impact = exemption_summary.get('total_impact', 0)
        remaining_exempt_capital = exemption_summary.get('remaining_exempt_capital', 0)
        exempt_pension = remaining_exempt_capital / 180 if remaining_exempt_capital > 0 else 0
        
        # נתונים נוספים
        grants_nominal = sum(g.get('grant_amount', 0) for g in grants)
        grants_indexed = sum(g.get('limited_indexed_amount', 0) for g in grants)
        future_grant_reserved = exemption_summary.get('future_grant_reserved', 0)
        future_grant_impact = exemption_summary.get('future_grant_impact', 0)
        total_commutations = exemption_summary.get('total_commutations', 0)
        pension_ceiling = 9430  # תקרת קצבה מזכה
        exemption_percentage = (exempt_pension / pension_ceiling * 100) if pension_ceiling > 0 else 0
        
        # יצירת HTML
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>טבלת סיכום קיבוע זכויות</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: right;
        }}
        th {{
            background-color: #27ae60;
            color: white;
            font-weight: bold;
        }}
        .highlight-row {{
            background-color: #d5f4e6;
            font-weight: bold;
        }}
        .section-header {{
            background-color: #95a5a6;
            color: white;
            font-weight: bold;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>טבלת סיכום - קיבוע זכויות</h1>
    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {client.first_name} {client.last_name}</p>
        <p><strong>תעודת זהות:</strong> {client.id_number or ''}</p>
        <p><strong>תאריך:</strong> {date.today().strftime('%d/%m/%Y')}</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>פרט</th>
                <th>סכום (₪)</th>
            </tr>
        </thead>
        <tbody>
            <tr style="background-color: #d1ecf1;">
                <td style="font-weight: bold;">יתרת הון פטורה לשנת הזכאות</td>
                <td style="font-weight: bold;">{exempt_capital_initial:,.2f}</td>
            </tr>
            <tr>
                <td>סך נומינאלי של מענקי הפרישה</td>
                <td>{grants_nominal:,.2f}</td>
            </tr>
            <tr>
                <td>סך המענקים הרלוונטים לאחר הוצמדה</td>
                <td>{grants_indexed:,.2f}</td>
            </tr>
            <tr>
                <td>סך הכל פגיעה בפטור בגין מענקים פטורים</td>
                <td>{total_impact:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>מענק עתידי משוריין (נומינלי)</td>
                <td>{future_grant_reserved:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>השפעת מענק עתידי (×1.35)</td>
                <td>{future_grant_impact:,.2f}</td>
            </tr>
            <tr style="background-color: #f8f9fa; color: #6c757d;">
                <td>סך היוונים</td>
                <td>{total_commutations:,.2f}</td>
            </tr>
            <tr>
                <td style="font-weight: 500;">יתרת הון פטורה לאחר קיזוזים</td>
                <td style="color: #28a745;">{remaining_exempt_capital:,.2f}</td>
            </tr>
            <tr style="background-color: #fff3cd;">
                <td>תקרת קצבה מזכה</td>
                <td>{pension_ceiling:,.2f}</td>
            </tr>
            <tr style="background-color: #d4edda;">
                <td style="font-weight: bold;">קצבה פטורה מחושבת</td>
                <td style="font-weight: bold;">{exempt_pension:,.2f} ₪ ({exemption_percentage:.1f}%)</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""
        
        # שמירת HTML
        html_path = output_dir / "summary_table.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "טבלת סיכום.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"Summary table created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"Error creating summary table: {e}", exc_info=True)
        return None


def generate_document_package(db: Session, client_id: int) -> dict:
    """
    מייצר חבילת מסמכים מלאה ללקוח
    ממלא טופס 161ד ריק + יוצר נספחים
    
    Returns:
        dict: {"success": True, "folder": str, "files": list}
    """
    try:
        logger.info(f"📦 Starting package generation for client {client_id}")
        
        # שליפת לקוח
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(f"❌ Client {client_id} not found in database")
            return {"success": False, "error": "לקוח לא נמצא"}
        
        logger.info(f"✅ Client found: {client.first_name} {client.last_name}")
        
        # יצירת תיקייה
        output_dir = get_client_package_dir(client_id, client.first_name or "", client.last_name or "")
        logger.info(f"📁 Output directory: {output_dir}")
        
        files = []
        
        # 1. מילוי טופס 161ד המקורי
        logger.info(f"📄 Filling form 161d...")
        try:
            form_161d = fill_161d_form(db, client_id, output_dir)
            if form_161d and form_161d.exists():
                files.append(form_161d.name)
                logger.info(f"✅ Form 161d created: {form_161d.name}")
            else:
                logger.error(f"❌ Form 161d not created - returned None or doesn't exist")
        except Exception as e:
            logger.error(f"❌ Exception in fill_161d_form: {e}", exc_info=True)
        
        # 2. נספח מענקים מפורט
        logger.info(f"📄 Generating grants appendix...")
        grants_app = generate_grants_appendix(db, client_id, output_dir)
        if grants_app and grants_app.exists():
            files.append(grants_app.name)
            logger.info(f"✅ Grants appendix created: {grants_app.name}")
        else:
            logger.warning(f"⚠️ Grants appendix not created")
        
        # 3. נספח היוונים
        logger.info(f"📄 Generating commutations appendix...")
        try:
            commutations_app = generate_actual_commutations_appendix(db, client_id, output_dir)
            if commutations_app and commutations_app.exists():
                files.append(commutations_app.name)
                logger.info(f"✅ Commutations appendix created: {commutations_app.name}")
            else:
                logger.warning(f"⚠️ Commutations appendix not created")
        except Exception as e:
            logger.error(f"❌ Exception in generate_commutations_appendix: {e}", exc_info=True)
        
        # 4. טבלת סיכום
        logger.info(f"📄 Generating summary table...")
        try:
            summary_table = generate_summary_table(db, client_id, output_dir)
            if summary_table and summary_table.exists():
                files.append(summary_table.name)
                logger.info(f"✅ Summary table created: {summary_table.name}")
            else:
                logger.warning(f"⚠️ Summary table not created")
        except Exception as e:
            logger.error(f"❌ Exception in generate_summary_table: {e}", exc_info=True)
        
        logger.info(f"✅ Package generated for client {client_id}: {len(files)} files")
        
        return {
            "success": True,
            "folder": str(output_dir.relative_to(PACKAGES_DIR.parent)),
            "files": files
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating package: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
