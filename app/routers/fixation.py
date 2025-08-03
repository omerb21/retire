"""
Router for rights fixation (קיבוע זכויות) endpoints
"""
import os
import sys
import pathlib
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import time
from typing import Dict, Any, Optional

from app.schemas.fixation import FixationSingleResponse, FixationPackageResponse
from app.database import get_db
from app.models.client import Client

# Set up logger
logger = logging.getLogger(__name__)


def log_document_generation(endpoint: str, client_id: int, ok: bool, fallback: bool, duration_ms: int, extra: Optional[Dict[str, Any]] = None):
    """
    Log document generation with structured metrics for monitoring
    
    Args:
        endpoint: Endpoint name (161d, grants, commutations, package)
        client_id: Client ID
        ok: Whether generation was successful
        fallback: Whether JSON fallback was used
        duration_ms: Duration in milliseconds
        extra: Additional fields to log
    """
    log_data = {
        "event": "fixation.generate",
        "endpoint": endpoint,
        "ok": ok,
        "fallback": fallback,
        "duration_ms": duration_ms,
        "client_id": client_id
    }
    
    if extra:
        log_data.update(extra)
    
    if ok:
        logger.info(f"Document generation: {log_data}")
    else:
        logger.error(f"Document generation failed: {log_data}")

# Set up router
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
    
    return client


@router.post("/{client_id}/161d", response_model=FixationSingleResponse)
def generate_161d_form(client_id: int, db: Session = Depends(get_db)) -> FixationSingleResponse:
    """
    Generate 161d form for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    from app.integrations.fixation_forms import fill_161d_form, TEMPLATE_161D, get_client_output_dir
    
    start_time = time.time()
    fallback_used = False
    success = False
    
    # Check if client exists and is active - this will raise appropriate HTTP exceptions
    # with correct status codes (404 for not found, 400 for inactive)
    client = validate_client_and_permissions(client_id, db)
    
    try:
        # Check templates and directories after validation
        templates_root = Path("templates") / "fixation"
        output_root = Path("packages")
        output_root.mkdir(parents=True, exist_ok=True)
        
        # Check if 161d template exists
        if not TEMPLATE_161D.exists():
            logger.debug(f"Template not found at: {TEMPLATE_161D}")
            # Template not existing is OK - we'll use JSON fallback
        
        # Create output directory
        output_dir = get_client_output_dir(client_id, client.full_name)
        
        # Wrap adapter call in try/except
        try:
            out_path = fill_161d_form(db, client_id, TEMPLATE_161D, output_dir)
            # Check if JSON fallback was used
            fallback_used = str(out_path).endswith('.json')
            success = True
        except Exception as e:
            logger.exception("fixation_adapter_error")
            # If JSON fallback is allowed, use it
            from app.config import allow_json_fallback
            if allow_json_fallback():
                # Create JSON fallback
                import json
                fallback_path = output_dir / "161d_fallback.json"
                with open(fallback_path, "w") as f:
                    json.dump({"client_id": client_id, "error": str(e)}, f)
                out_path = fallback_path
                fallback_used = True
                success = True
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"error": "שירות יצירת המסמכים אינו זמין כרגע"}
                )
        
        response = {
            "success": True,
            "message": "טופס 161ד נוצר בהצלחה",
            "file_path": str(out_path),
            "client_id": client_id,
            "client_name": client.full_name if client else None,
        }
        
        # Log metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="161d", 
            client_id=client_id, 
            ok=True, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"file_path": str(out_path)}
        )
        
        return response
        
    except Exception as e:
        # Log error metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="161d", 
            client_id=client_id, 
            ok=False, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת טופס 161ד: {str(e)}"}
        )


@router.post("/{client_id}/grants-appendix", response_model=FixationSingleResponse)
def generate_grants_appendix_endpoint(client_id: int, db: Session = Depends(get_db)) -> FixationSingleResponse:
    """
    Generate grants appendix for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    from app.integrations.fixation_forms import fill_grants_appendix, TEMPLATE_GRANTS, get_client_output_dir
    
    start_time = time.time()
    fallback_used = False
    
    try:
        client = validate_client_and_permissions(client_id, db)
        
        output_dir = get_client_output_dir(client_id, client.full_name)
        out_path = fill_grants_appendix(db, client_id, TEMPLATE_GRANTS, output_dir)
        
        # Check if JSON fallback was used
        fallback_used = str(out_path).endswith('.json')
        
        response = {
            "success": True,
            "message": "נספח מענקים נוצר בהצלחה",
            "file_path": str(out_path),
            "client_id": client_id,
            "client_name": client.full_name if client else None,
        }
        
        # Log metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="grants", 
            client_id=client_id, 
            ok=True, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"file_path": str(out_path)}
        )
        
        return response
        
    except Exception as e:
        # Log error metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="grants", 
            client_id=client_id, 
            ok=False, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת נספח מענקים: {str(e)}"}
        )


@router.post("/{client_id}/commutations-appendix", response_model=FixationSingleResponse)
def generate_commutations_appendix_endpoint(client_id: int, db: Session = Depends(get_db)) -> FixationSingleResponse:
    """
    Generate commutations appendix for a client
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with file path and metadata
    """
    from app.integrations.fixation_forms import fill_commutations_appendix, TEMPLATE_COMMUT, get_client_output_dir
    
    start_time = time.time()
    fallback_used = False
    
    try:
        client = validate_client_and_permissions(client_id, db)
        
        output_dir = get_client_output_dir(client_id, client.full_name)
        out_path = fill_commutations_appendix(db, client_id, TEMPLATE_COMMUT, output_dir)
        
        # Check if JSON fallback was used
        fallback_used = str(out_path).endswith('.json')
        
        response = {
            "success": True,
            "message": "נספח היוונים נוצר בהצלחה",
            "file_path": str(out_path),
            "client_id": client_id,
            "client_name": client.full_name if client else None,
        }
        
        # Log metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="commutations", 
            client_id=client_id, 
            ok=True, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"file_path": str(out_path)}
        )
        
        return response
        
    except Exception as e:
        # Log error metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="commutations", 
            client_id=client_id, 
            ok=False, 
            fallback=fallback_used, 
            duration_ms=duration_ms,
            extra={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת נספח היוונים: {str(e)}"}
        )


@router.post("/{client_id}/package", response_model=FixationPackageResponse)
def generate_complete_package(client_id: int, db: Session = Depends(get_db)) -> FixationPackageResponse:
    """
    Generate complete rights fixation package for a client
    Runs all three document generations in sequence
    
    Args:
        client_id: Client ID
        db: Database session
        
    Returns:
        Dictionary with all file paths and metadata
    """
    from app.integrations.fixation_forms import (
        fill_161d_form, fill_grants_appendix, fill_commutations_appendix,
        TEMPLATE_161D, TEMPLATE_GRANTS, TEMPLATE_COMMUT, get_client_output_dir
    )
    
    start_time = time.time()
    fallback_count = 0
    generated_files = 0
    
    try:
        client = validate_client_and_permissions(client_id, db)
        output_dir = get_client_output_dir(client_id, client.full_name)
        
        files = []
        
        # Generate 161d form
        form_161d_path = fill_161d_form(db, client_id, TEMPLATE_161D, output_dir)
        files.append(str(form_161d_path))
        generated_files += 1
        if str(form_161d_path).endswith('.json'):
            fallback_count += 1
        
        # Generate grants appendix
        grants_path = fill_grants_appendix(db, client_id, TEMPLATE_GRANTS, output_dir)
        files.append(str(grants_path))
        generated_files += 1
        if str(grants_path).endswith('.json'):
            fallback_count += 1
        
        # Generate commutations appendix
        commutations_path = fill_commutations_appendix(db, client_id, TEMPLATE_COMMUT, output_dir)
        files.append(str(commutations_path))
        generated_files += 1
        if str(commutations_path).endswith('.json'):
            fallback_count += 1
        
        response = {
            "success": True,
            "message": "חבילת קיבוע נוצרה בהצלחה",
            "files": files,
            "client_id": client_id,
            "client_name": client.full_name if client else None,
        }
        
        # Log metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="package", 
            client_id=client_id, 
            ok=True, 
            fallback=(fallback_count > 0), 
            duration_ms=duration_ms,
            extra={
                "fallback_count": fallback_count,
                "generated_files": generated_files,
                "file_count": len(files)
            }
        )
        
        return response
        
    except Exception as e:
        # Log error metrics
        duration_ms = int((time.time() - start_time) * 1000)
        log_document_generation(
            endpoint="package", 
            client_id=client_id, 
            ok=False, 
            fallback=(fallback_count > 0), 
            duration_ms=duration_ms,
            extra={
                "fallback_count": fallback_count,
                "generated_files": generated_files,
                "error": str(e)
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה ביצירת חבילת קיבוע זכויות: {str(e)}"}
        )


def generate_fixation_package_for_client(db: Session, client_id: int) -> dict:
    """
    Generate complete fixation package for internal use (e.g., background tasks)
    
    Args:
        db: Database session
        client_id: Client ID
        
    Returns:
        Dictionary with package metadata
    """
    from app.integrations.fixation_forms import (
        fill_161d_form, fill_grants_appendix, fill_commutations_appendix,
        TEMPLATE_161D, TEMPLATE_GRANTS, TEMPLATE_COMMUT, get_client_output_dir
    )
    
    try:
        # Validate client exists and is active
        client = validate_client_and_permissions(client_id, db)
        output_dir = get_client_output_dir(client_id, client.full_name)
        
        files = []
        
        # Generate all documents
        files.append(str(fill_161d_form(db, client_id, TEMPLATE_161D, output_dir)))
        files.append(str(fill_grants_appendix(db, client_id, TEMPLATE_GRANTS, output_dir)))
        files.append(str(fill_commutations_appendix(db, client_id, TEMPLATE_COMMUT, output_dir)))
        
        return {
            "success": True,
            "message": "חבילת קיבוע נוצרה בהצלחה",
            "files": files,
            "client_id": client_id,
            "client_name": client.full_name if client else None,
        }
        
    except Exception as e:
        logger.error(f"Error generating fixation package for client {client_id}: {e}")
        return {
            "success": False,
            "message": f"שגיאה ביצירת חבילת קיבוע זכויות: {str(e)}",
            "files": [],
            "client_id": client_id,
            "client_name": None,
        }
