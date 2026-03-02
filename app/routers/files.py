"""
Router for file download endpoints
"""

import logging
import os
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/files", tags=["files"])
logger = logging.getLogger(__name__)


@router.get("")
def download_file(
    path: str = Query(..., description="File path relative to packages directory")
):
    """
    Download a file from the packages directory

    Args:
        path: File path relative to packages directory

    Returns:
        File download response
    """
    try:
        # Validate path is under packages directory only (prevent Path Traversal)
        try:
            from app.services.documents.utils import PACKAGES_DIR

            packages_dir = PACKAGES_DIR.resolve()
        except Exception:
            packages_dir = Path("packages").resolve()
        requested_path = (packages_dir / path).resolve()

        # Security check: ensure the resolved path is still under packages
        if not str(requested_path).startswith(str(packages_dir)):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "גישה לנתיב זה אסורה - רק קבצים בתיקיית packages מותרים"
                },
            )

        # Check if file exists
        if not requested_path.exists() or not requested_path.is_file():
            raise HTTPException(status_code=404, detail={"error": "הקובץ לא נמצא"})

        # Get filename for download
        filename = requested_path.name

        logger.debug(f"Serving file: {requested_path}")

        encoded_filename = quote(filename)

        return FileResponse(
            path=str(requested_path),
            filename=filename,
            headers={
                "Content-Disposition": f"attachment; filename={filename}; filename*=UTF-8''{encoded_filename}"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {path}: {e}")
        raise HTTPException(
            status_code=500, detail={"error": f"שגיאה בהורדת הקובץ: {str(e)}"}
        )
