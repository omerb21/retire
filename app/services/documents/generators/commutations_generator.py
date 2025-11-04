"""
מחולל נספח היוונים
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..data_fetchers import fetch_client_data, fetch_pension_data, fetch_commutations_data
from ..templates import CommutationsHTMLTemplate
from ..converters import html_to_pdf

logger = logging.getLogger(__name__)


def generate_commutations_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח קצבאות בפורמט HTML וממיר ל-PDF
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט
        
    Returns:
        נתיב לנספח שנוצר או None אם נכשל
    """
    try:
        client = fetch_client_data(db, client_id)
        if not client:
            return None
        
        # שליפת קצבאות
        pensions = fetch_pension_data(db, client_id)
        
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
        
        # המרה ל-PDF
        pdf_path = output_dir / "נספח קצבאות.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"✅ Commutations appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"❌ Error creating commutations appendix: {e}", exc_info=True)
        return None


def generate_actual_commutations_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח היוונים (ממש היוונים, לא קצבאות) בפורמט HTML וממיר ל-PDF
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט
        
    Returns:
        נתיב לנספח שנוצר או None אם נכשל
    """
    try:
        client = fetch_client_data(db, client_id)
        if not client:
            return None
        
        # שליפת היוונים
        commutations = fetch_commutations_data(db, client_id)
        
        if not commutations:
            logger.info(f"No exempt commutations found for client {client_id}")
            return None
        
        # יצירת תבנית HTML
        client_name = f"{client.first_name} {client.last_name}"
        client_id_number = client.id_number or ''
        
        template = CommutationsHTMLTemplate(
            client_name=client_name,
            client_id_number=client_id_number,
            commutations=commutations
        )
        
        # רינדור HTML
        html_content = template.render()
        
        # שמירת HTML
        html_path = output_dir / "commutations_appendix.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "נספח היוונים.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"✅ Commutations appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"❌ Error creating commutations appendix: {e}", exc_info=True)
        return None
