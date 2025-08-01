"""
Router for rights fixation (קיבוע זכויות) endpoints
"""
import os
import sys
import pathlib
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client

# Add the rights fixation system to Python path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]  # מצביע ל-RETIRE
rights_dir = PROJECT_ROOT / "מערכת קיבוע זכויות"
rights_app_dir = rights_dir / "app"

# Import rights fixation modules with specific path handling
try:
    if rights_app_dir.exists():
        sys.path.insert(0, str(rights_app_dir))
        import utils as fixation_utils
        import pdf_filler as fixation_pdf
        
        get_client_package_dir = fixation_utils.get_client_package_dir
        fill_161d_form = fixation_pdf.fill_161d_form
        generate_grants_appendix = fixation_pdf.generate_grants_appendix
        generate_commutations_appendix = fixation_pdf.generate_commutations_appendix
        
        RIGHTS_FIXATION_AVAILABLE = True
    else:
        raise ImportError("Rights fixation app directory not found")
except ImportError as e:
    print(f"Warning: Rights fixation modules not available: {e}")
    RIGHTS_FIXATION_AVAILABLE = False
    
    # Create dummy functions for testing
    def get_client_package_dir(client_id, first_name, last_name):
        return Path(f"/tmp/test_package_{client_id}")
    
    def fill_161d_form(client_id, out_dir):
        return str(out_dir / "161d.pdf")
    
    def generate_grants_appendix(client_id, out_dir):
        return str(out_dir / "grants_appendix.pdf")
    
    def generate_commutations_appendix(client_id, out_dir):
        return str(out_dir / "commutations_appendix.pdf")

router = APIRouter(prefix="/api/v1/fixation", tags=["fixation"])


def validate_client_and_permissions(client_id: int, db: Session) -> Client:
    """
    Validate client exists, is active, and check system permissions
    
    Args:
        client_id: Client ID to validate
        db: Database session
        
    Returns:
        Client object if valid
        
    Raises:
        HTTPException: If client not found, inactive, or system issues
    """
    # Check if client exists and is active
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "לקוח לא נמצא במערכת"}
        )
    
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "לקוח לא פעיל במערכת"}
        )
    
    # Check if 161d template exists
    template_path = rights_dir / "app" / "static" / "templates" / "161d.pdf"
    if not template_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "תבנית טופס 161ד לא נמצאה במערכת"}
        )
    
    # Check packages directory exists and is writable
    packages_dir = rights_dir / "packages"
    try:
        packages_dir.mkdir(exist_ok=True)
        # Test write permission by creating a temporary file
        test_file = packages_dir / "test_write_permission.tmp"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "אין הרשאות כתיבה לתיקיית החבילות"}
        )
    
    return client


@router.post("/{client_id}/161d")
def generate_161d_form(client_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Generate 161d form for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    client = validate_client_and_permissions(client_id, db)
    
    try:
        # Get client package directory
        out_dir = get_client_package_dir(client_id, client.first_name, client.last_name)
        
        # Generate 161d form
        file_path = fill_161d_form(client_id, out_dir)
        
        return {
            "success": True,
            "message": "טופס 161ד נוצר בהצלחה",
            "file_path": str(file_path),
            "client_id": client_id,
            "client_name": f"{client.first_name} {client.last_name}",
            "generated_at": str(Path(file_path).stat().st_mtime)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת טופס 161ד: {str(e)}"}
        )


@router.post("/{client_id}/grants-appendix")
def generate_grants_appendix_endpoint(client_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Generate grants appendix for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    client = validate_client_and_permissions(client_id, db)
    
    try:
        # Get client package directory
        out_dir = get_client_package_dir(client_id, client.first_name, client.last_name)
        
        # Generate grants appendix
        file_path = generate_grants_appendix(client_id, out_dir)
        
        return {
            "success": True,
            "message": "נספח מענקים נוצר בהצלחה",
            "file_path": str(file_path),
            "client_id": client_id,
            "client_name": f"{client.first_name} {client.last_name}",
            "generated_at": str(Path(file_path).stat().st_mtime)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת נספח מענקים: {str(e)}"}
        )


@router.post("/{client_id}/commutations-appendix")
def generate_commutations_appendix_endpoint(client_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Generate commutations appendix for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    client = validate_client_and_permissions(client_id, db)
    
    try:
        # Get client package directory
        out_dir = get_client_package_dir(client_id, client.first_name, client.last_name)
        
        # Generate commutations appendix
        file_path = generate_commutations_appendix(client_id, out_dir)
        
        return {
            "success": True,
            "message": "נספח היוונים נוצר בהצלחה",
            "file_path": str(file_path),
            "client_id": client_id,
            "client_name": f"{client.first_name} {client.last_name}",
            "generated_at": str(Path(file_path).stat().st_mtime)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת נספח היוונים: {str(e)}"}
        )


@router.post("/{client_id}/package")
def generate_complete_package(client_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Generate complete rights fixation package for a client
    Runs all three document generations in sequence
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with all file paths and metadata
    """
    client = validate_client_and_permissions(client_id, db)
    
    try:
        # Get client package directory
        out_dir = get_client_package_dir(client_id, client.first_name, client.last_name)
        
        # Generate all documents in sequence
        form_161d_path = fill_161d_form(client_id, out_dir)
        grants_appendix_path = generate_grants_appendix(client_id, out_dir)
        commutations_appendix_path = generate_commutations_appendix(client_id, out_dir)
        
        return {
            "success": True,
            "message": "חבילת קיבוע זכויות הושלמה בהצלחה",
            "client_id": client_id,
            "client_name": f"{client.first_name} {client.last_name}",
            "package_directory": str(out_dir),
            "files": {
                "form_161d": {
                    "path": str(form_161d_path),
                    "generated_at": str(Path(form_161d_path).stat().st_mtime)
                },
                "grants_appendix": {
                    "path": str(grants_appendix_path),
                    "generated_at": str(Path(grants_appendix_path).stat().st_mtime)
                },
                "commutations_appendix": {
                    "path": str(commutations_appendix_path),
                    "generated_at": str(Path(commutations_appendix_path).stat().st_mtime)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת חבילת קיבוע זכויות: {str(e)}"}
        )
