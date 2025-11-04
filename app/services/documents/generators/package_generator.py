"""
מחולל חבילת מסמכים מלאה
"""
from sqlalchemy.orm import Session
import logging

from ..utils import get_client_package_dir, PACKAGES_DIR
from ..data_fetchers import fetch_client_data
from .form_161d_generator import fill_161d_form
from .grants_generator import generate_grants_appendix
from .commutations_generator import generate_actual_commutations_appendix
from .summary_generator import generate_summary_table

logger = logging.getLogger(__name__)


def generate_document_package(db: Session, client_id: int) -> dict:
    """
    מייצר חבילת מסמכים מלאה ללקוח
    ממלא טופס 161ד ריק + יוצר נספחים
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        
    Returns:
        dict: {"success": True, "folder": str, "files": list} או {"success": False, "error": str}
    """
    try:
        logger.info(f"📦 Starting package generation for client {client_id}")
        
        # שליפת לקוח
        client = fetch_client_data(db, client_id)
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
