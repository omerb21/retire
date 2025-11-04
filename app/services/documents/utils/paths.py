"""
ניהול נתיבים ותיקיות למסמכים
"""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# נתיבים לתבניות
TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent.parent / "templates"
TEMPLATE_161D = TEMPLATE_DIR / "161d.pdf"
PACKAGES_DIR = Path(__file__).parent.parent.parent.parent.parent / "packages"


def get_client_package_dir(client_id: int, client_first_name: str, client_last_name: str) -> Path:
    """
    יוצר או מחזיר נתיב לתיקיית חבילת המסמכים של הלקוח
    
    Args:
        client_id: מזהה לקוח
        client_first_name: שם פרטי
        client_last_name: שם משפחה
        
    Returns:
        Path: נתיב לתיקיית הלקוח
        
    פורמט: packages/<client_id>_<first_name>_<last_name>/
    """
    from .text_utils import sanitize_filename
    
    # ניקוי שמות מתווים לא חוקיים
    safe_first = sanitize_filename(client_first_name)
    safe_last = sanitize_filename(client_last_name)
    
    client_dir_name = f"{client_id}_{safe_first}_{safe_last}"
    client_package_dir = PACKAGES_DIR / client_dir_name
    client_package_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"📁 Client package directory: {client_package_dir}")
    
    return client_package_dir
