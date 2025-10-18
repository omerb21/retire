"""
יצירת PDFs של קיבוע זכויות - בדיוק כמו במסך SimpleFixation
"""
from pathlib import Path
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
import subprocess

from app.models.client import Client
from app.models.grant import Grant
from app.models.fixation_result import FixationResult
from sqlalchemy import desc

logger = logging.getLogger(__name__)


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """ממיר HTML ל-PDF"""
    wkhtmltopdf_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "wkhtmltopdf"
    ]
    
    wkhtmltopdf_path = None
    for path in wkhtmltopdf_paths:
        try:
            subprocess.run([path, "--version"], capture_output=True, check=True, timeout=5)
            wkhtmltopdf_path = path
            break
        except:
            continue
    
    if not wkhtmltopdf_path:
        raise RuntimeError("wkhtmltopdf not found")
    
    cmd = [
        wkhtmltopdf_path,
        '--encoding', 'UTF-8',
        '--page-size', 'A4',
        '--margin-top', '15mm',
        '--margin-right', '15mm',
        '--margin-bottom', '15mm',
        '--margin-left', '15mm',
        str(html_path),
        str(pdf_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"wkhtmltopdf failed: {result.stderr}")
    
    return pdf_path


def generate_fixation_summary_pdf(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    מייצר PDF של טבלת הסיכום - בדיוק כמו במסך קיבוע זכויות
    """
    try:
        logger.info(f"📄 Generating fixation summary PDF for client {client_id}")
        
        # שליפת נתונים
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(f"Client {client_id} not found")
            return None
        
        # שליפת תוצאות קיבוע זכויות מה-DB
        fixation = db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).order_by(desc(FixationResult.created_at)).first()
        
        if not fixation or not fixation.raw_result:
            logger.warning(f"No fixation data found for client {client_id}")
            return None
        
        raw_result = fixation.raw_result
        
        exemption_summary = raw_result.get('exemption_summary', {})
        grants_summary = raw_result.get('grants', [])
        
        # בניית HTML
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <title>טופס קיבוע זכויות - {client.first_name} {client.last_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
            background-color: white;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #28a745;
            padding-bottom: 20px;
        }}
        h1 {{
            color: #28a745;
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .client-info {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .client-info p {{
            margin: 5px 0;
            font-size: 14px;
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
            background-color: #28a745;
            color: white;
            font-weight: bold;
        }}
        .summary-table td:first-child {{
            font-weight: 500;
            background-color: #f8f9fa;
        }}
        .summary-table td:last-child {{
            font-family: monospace;
            text-align: left;
        }}
        .highlight-row {{
            background-color: #d4edda !important;
        }}
        .highlight-row td {{
            font-weight: bold;
            font-size: 16px;
        }}
        .secondary-row {{
            background-color: #f8f9fa;
        }}
        .secondary-row td {{
            color: #6c757d;
        }}
        .green-text {{
            color: #28a745;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 טופס קיבוע זכויות (161ד)</h1>
        <p style="font-size: 14px; color: #666;">מסמך רשמי לרשות המיסים</p>
    </div>

    <div class="client-info">
        <p><strong>שם הלקוח:</strong> {client.first_name} {client.last_name}</p>
        <p><strong>תעודת זהות:</strong> {client.id_number or ''}</p>
        <p><strong>תאריך חישוב:</strong> {date.today().strftime("%d/%m/%Y")}</p>
        <p><strong>שנת זכאות:</strong> {exemption_summary.get('eligibility_year', '')}</p>
    </div>

    <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">סיכום קיבוע זכויות</h2>
    
    <table class="summary-table">
        <tbody>
            <tr>
                <td>יתרת הון פטורה ראשונית</td>
                <td class="green-text">{exemption_summary.get('exempt_capital_initial', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך מענקים נומינליים רלוונטיים</td>
                <td>{exemption_summary.get('grants_nominal', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך המענקים הרלוונטיים לאחר הוצמדה</td>
                <td>{exemption_summary.get('grants_indexed', 0):,.0f} ₪</td>
            </tr>
            <tr>
                <td>סך הכל פגיעה בפטור בגין מענקים פטורים</td>
                <td>{exemption_summary.get('total_impact', 0):,.0f} ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>מענק עתידי משוריין (נומינלי)</td>
                <td>0 ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>השפעת מענק עתידי (×1.35)</td>
                <td>0 ₪</td>
            </tr>
            <tr class="secondary-row">
                <td>סך היוונים</td>
                <td>0 ₪</td>
            </tr>
            <tr>
                <td>יתרת הון פטורה לאחר קיזוזים</td>
                <td class="green-text">{exemption_summary.get('remaining_exempt_capital', 0):,.0f} ₪</td>
            </tr>
            <tr style="background-color: #fff3cd;">
                <td>תקרת קצבה מזכה</td>
                <td>{exemption_summary.get('pension_ceiling', 0):,.0f} ₪</td>
            </tr>
            <tr class="highlight-row">
                <td>קצבה פטורה מחושבת</td>
                <td>{exemption_summary.get('exempt_pension_monthly', 0):,.0f} ₪ ({exemption_summary.get('exemption_percentage', 0) * 100:.1f}%)</td>
            </tr>
        </tbody>
    </table>

    <div style="page-break-before: always;"></div>
    
    <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">פירוט מענקים</h2>
    
    <table>
        <thead>
            <tr>
                <th>שם מעסיק</th>
                <th>תאריך קבלת מענק</th>
                <th>מענק נומינאלי</th>
                <th>סכום רלוונטי</th>
                <th>לאחר הצמדה</th>
                <th>פגיעה בפטור</th>
            </tr>
        </thead>
        <tbody>
"""
        
        # הוספת מענקים
        for grant in grants_summary:
            html_content += f"""
            <tr>
                <td>{grant.get('employer_name', '')}</td>
                <td>{grant.get('grant_date_formatted', '')}</td>
                <td style="text-align: left;">{grant.get('amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('relevant_amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('indexed_amount', 0):,.0f} ₪</td>
                <td style="text-align: left;">{grant.get('impact_on_exemption', 0):,.0f} ₪</td>
            </tr>
"""
        
        html_content += f"""
        </tbody>
    </table>

    <div class="footer">
        <p>מסמך זה הופק אוטומטית ממערכת ניהול פנסיה</p>
        <p>תאריך הפקה: {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    </div>
</body>
</html>
"""
        
        # שמירה והמרה
        html_path = output_dir / "fixation_summary.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        pdf_path = output_dir / "טופס_קיבוע_זכויות_161ד.pdf"
        html_to_pdf(html_path, pdf_path)
        
        # מחיקת HTML
        html_path.unlink()
        
        logger.info(f"✅ Fixation summary PDF created: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"❌ Error creating fixation summary PDF: {e}", exc_info=True)
        return None
