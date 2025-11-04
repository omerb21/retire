"""
מחולל טבלת סיכום קיבוע זכויות
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..data_fetchers import fetch_fixation_data
from ..templates import SummaryHTMLTemplate
from ..converters import html_to_pdf

logger = logging.getLogger(__name__)


def generate_summary_table(db: Session, client_id: int, output_dir: Path) -> Optional[Path]:
    """
    יוצר טבלת סיכום קיבוע זכויות בפורמט HTML וממיר ל-PDF
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט
        
    Returns:
        נתיב לטבלה שנוצרה או None אם נכשל
    """
    try:
        # שליפת נתוני קיבוע זכויות
        fixation_data = fetch_fixation_data(db, client_id)
        if not fixation_data:
            logger.info(f"No fixation data found for client {client_id}")
            return None
        
        # יצירת תבנית HTML
        client_name = f"{fixation_data.client.first_name} {fixation_data.client.last_name}"
        client_id_number = fixation_data.client.id_number or ''
        
        template = SummaryHTMLTemplate(
            client_name=client_name,
            client_id_number=client_id_number,
            exemption_summary=fixation_data.exemption_summary,
            grants=fixation_data.grants_summary
        )
        
        # רינדור HTML
        html_content = template.render()
        
        # שמירת HTML
        html_path = output_dir / "summary_table.html"
        html_path.write_text(html_content, encoding='utf-8')
        
        # המרה ל-PDF
        pdf_path = output_dir / "טבלת סיכום.pdf"
        try:
            html_to_pdf(html_path, pdf_path)
            logger.info(f"✅ Summary table created: {pdf_path}")
            return pdf_path
        except Exception as e:
            logger.warning(f"Could not convert HTML to PDF: {e}")
            return html_path
        
    except Exception as e:
        logger.error(f"❌ Error creating summary table: {e}", exc_info=True)
        return None
