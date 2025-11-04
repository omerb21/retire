"""
מחולל נספח מענקים
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..data_fetchers import fetch_fixation_data, fetch_grants_data
from ..templates import GrantsHTMLTemplate
from ..converters import html_to_pdf

logger = logging.getLogger(__name__)


def generate_grants_appendix(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר נספח מענקים בפורמט HTML - בדיוק כמו בטבלת המענקים במסך קיבוע זכויות
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט
        
    Returns:
        נתיב לנספח שנוצר או None אם נכשל
    """
    try:
        logger.info(f"📄 Generating grants appendix for client {client_id}")
        
        # שליפת נתוני קיבוע זכויות
        fixation_data = fetch_fixation_data(db, client_id)
        if not fixation_data:
            return None
        
        grants_summary = fixation_data.grants_summary
        
        if not grants_summary:
            logger.warning(f"⚠️ No grants in fixation data for client {client_id}")
            return None
        
        # שליפת תאריכי עבודה מה-DB
        grants_dates_map = fetch_grants_data(db, client_id)
        
        # יצירת תבנית HTML
        client_name = f"{fixation_data.client.first_name} {fixation_data.client.last_name}"
        client_id_number = fixation_data.client.id_number or ''
        
        template = GrantsHTMLTemplate(
            client_name=client_name,
            client_id_number=client_id_number,
            eligibility_date=fixation_data.eligibility_date,
            grants_summary=grants_summary,
            grants_dates_map=grants_dates_map
        )
        
        # רינדור HTML
        html_content = template.render()
        
        # שמירת HTML
        html_path = output_dir / "grants_appendix.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "נספח מענקים.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"✅ Grants appendix created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"❌ Error creating grants appendix: {e}", exc_info=True)
        return None
