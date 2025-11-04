"""
המרת HTML ל-PDF באמצעות wkhtmltopdf
"""
from pathlib import Path
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def find_wkhtmltopdf() -> Optional[str]:
    """
    מחפש את wkhtmltopdf במיקומים נפוצים
    
    Returns:
        נתיב ל-wkhtmltopdf או None אם לא נמצא
    """
    wkhtmltopdf_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        "wkhtmltopdf"
    ]
    
    for path in wkhtmltopdf_paths:
        try:
            subprocess.run(
                [path, "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            logger.info(f"✅ Found wkhtmltopdf at: {path}")
            return path
        except Exception:
            continue
    
    logger.error("❌ wkhtmltopdf not found in any common location")
    return None


def html_to_pdf(
    html_path: Path,
    pdf_path: Path,
    page_size: str = 'A4',
    margin_top: str = '15mm',
    margin_right: str = '15mm',
    margin_bottom: str = '15mm',
    margin_left: str = '15mm'
) -> Path:
    """
    ממיר קובץ HTML ל-PDF
    
    Args:
        html_path: נתיב לקובץ HTML
        pdf_path: נתיב לקובץ PDF היעד
        page_size: גודל עמוד (ברירת מחדל: A4)
        margin_top: שוליים עליונים
        margin_right: שוליים ימניים
        margin_bottom: שוליים תחתונים
        margin_left: שוליים שמאליים
        
    Returns:
        נתיב לקובץ PDF שנוצר
        
    Raises:
        RuntimeError: אם wkhtmltopdf לא נמצא או ההמרה נכשלה
    """
    wkhtmltopdf_path = find_wkhtmltopdf()
    
    if not wkhtmltopdf_path:
        raise RuntimeError(
            "wkhtmltopdf not found. Please install it from: "
            "https://wkhtmltopdf.org/downloads.html"
        )
    
    cmd = [
        wkhtmltopdf_path,
        '--encoding', 'UTF-8',
        '--page-size', page_size,
        '--margin-top', margin_top,
        '--margin-right', margin_right,
        '--margin-bottom', margin_bottom,
        '--margin-left', margin_left,
        str(html_path),
        str(pdf_path)
    ]
    
    logger.info(f"🔄 Converting HTML to PDF: {html_path} -> {pdf_path}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf failed: {result.stderr}")
        
        logger.info(f"✅ PDF created successfully: {pdf_path}")
        return pdf_path
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("wkhtmltopdf timed out after 30 seconds")
    except Exception as e:
        logger.error(f"❌ Error converting HTML to PDF: {e}")
        raise
