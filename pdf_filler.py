"""
מודול למילוי טפסי PDF עם נתונים
משתמש ב-pdfrw למילוי שדות AcroForm
"""

import logging
from pathlib import Path

from pdfrw import PdfDict, PdfName, PdfObject, PdfReader, PdfString, PdfWriter

logger = logging.getLogger(__name__)


def fill_acroform(template_path: Path, output_path: Path, field_data: dict) -> Path:
    """
    ממלא טופס PDF עם נתונים

    Args:
        template_path: נתיב לטופס PDF ריק
        output_path: נתיב לקובץ מלא
        field_data: מילון של שדות ועריכים

    Returns:
        Path to filled PDF
    """
    try:
        logger.info(f"📖 Reading template: {template_path}")

        # קריאת הטופס
        reader = PdfReader(str(template_path))

        # אפשור הצגת שדות ממולאים
        if reader.Root.AcroForm:
            reader.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject("true")))
            logger.info(f"✅ AcroForm found, NeedAppearances set")
        else:
            logger.warning("⚠️ No AcroForm found in PDF!")
            return None

        # קודם נאסוף את כל שמות השדות
        pdf_fields = []
        if reader.Root.AcroForm and reader.Root.AcroForm.Fields:
            for field in reader.Root.AcroForm.Fields:
                if field.T:
                    clean_name = (
                        field.T[1:-1] if field.T.startswith("(") else str(field.T)
                    )
                    pdf_fields.append(clean_name)

        logger.info(f"📋 PDF has {len(pdf_fields)} fields:")
        for fname in pdf_fields[:10]:  # הצג רק 10 ראשונים
            logger.info(f"   - {fname}")
        if len(pdf_fields) > 10:
            logger.info(f"   ... and {len(pdf_fields) - 10} more")

        logger.info(f"📝 Attempting to fill {len(field_data)} data fields")

        # מילוי השדות
        filled_count = 0
        if reader.Root.AcroForm and reader.Root.AcroForm.Fields:
            for field in reader.Root.AcroForm.Fields:
                # קבלת שם השדה
                field_name = field.T
                if field_name:
                    # הסרת סימני מרכאות מהשם
                    clean_name = (
                        field_name[1:-1]
                        if field_name.startswith("(")
                        else str(field_name)
                    )

                    # אם יש ערך בנתונים, ממלאים את השדה
                    if clean_name in field_data:
                        raw_value = field_data[clean_name]
                        field_type = str(getattr(field, "FT", "") or "")

                        if field_type == "/Btn":
                            checked = bool(raw_value)
                            field.V = PdfName.Yes if checked else PdfName.Off
                            field.AS = PdfName.Yes if checked else PdfName.Off
                            value = "Yes" if checked else "Off"
                        else:
                            value = str(raw_value)
                            field.V = PdfString.from_unicode(value)

                        # ניקוי appearance stream כדי לאלץ יצירה מחדש
                        if field_type != "/Btn" and hasattr(field, "AP"):
                            field.AP = PdfDict()

                        filled_count += 1
                        logger.info(f"✅ Filled '{clean_name}' = '{value}'")

        logger.info(
            f"📊 Successfully filled {filled_count} out of {len(field_data)} fields"
        )

        # שמירת ה-PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        PdfWriter(str(output_path), trailer=reader).write()

        logger.info(f"💾 PDF saved: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"❌ Error filling PDF: {e}", exc_info=True)
        raise


def get_pdf_fields(template_path: Path) -> list:
    """
    מחזיר רשימת שדות הטופס
    שימושי לדיבוג ומיפוי

    Args:
        template_path: נתיב לטופס PDF

    Returns:
        List of field names
    """
    try:
        reader = PdfReader(str(template_path))
        fields = []

        if reader.Root.AcroForm and reader.Root.AcroForm.Fields:
            for field in reader.Root.AcroForm.Fields:
                if field.T:
                    clean_name = (
                        field.T[1:-1] if field.T.startswith("(") else str(field.T)
                    )
                    fields.append(clean_name)

        return fields

    except Exception as e:
        logger.error(f"Error reading PDF fields: {e}")
        return []
