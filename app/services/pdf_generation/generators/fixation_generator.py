"""
יצירת PDF של קיבוע זכויות
"""

from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
import logging

from ..data_fetchers import fetch_fixation_data
from ..templates import FixationHTMLTemplate
from ..converters import html_to_pdf

logger = logging.getLogger(__name__)


def generate_fixation_summary_pdf(
    db: Session, client_id: int, output_dir: Path
) -> Optional[Path]:
    """
    מייצר PDF של טבלת הסיכום - בדיוק כמו במסך קיבוע זכויות

    Args:
        db: סשן DB
        client_id: מזהה לקוח
        output_dir: תיקיית פלט

    Returns:
        נתיב ל-PDF שנוצר או None אם נכשל
    """
    try:
        logger.info(f"📄 Generating fixation summary PDF for client {client_id}")

        # שליפת נתונים
        data = fetch_fixation_data(db, client_id)
        if not data:
            return None

        # בניית שם לקוח
        client_name = f"{data.client.first_name} {data.client.last_name}"
        client_id_number = data.client.id_number or ""

        # יצירת תבנית HTML
        template = FixationHTMLTemplate(
            client_name=client_name,
            client_id_number=client_id_number,
            exemption_summary=data.exemption_summary,
            grants_summary=data.grants_summary,
        )

        # רינדור HTML
        html_content = template.render()

        # שמירת HTML זמני
        html_path = output_dir / "fixation_summary.html"
        html_path.write_text(html_content, encoding="utf-8")

        # המרה ל-PDF
        pdf_path = output_dir / "טופס_קיבוע_זכויות_161ד.pdf"
        html_to_pdf(html_path, pdf_path)

        # מחיקת HTML זמני
        html_path.unlink()

        logger.info(f"✅ Fixation summary PDF created: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"❌ Error creating fixation summary PDF: {e}", exc_info=True)
        return None
