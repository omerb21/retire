"""
Router for employment and termination endpoints
"""
import logging
import time
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.schemas.employment import (
    EmploymentCreate, EmploymentOut, 
    TerminationPlanIn, TerminationConfirmIn, TerminationEventOut
)
from app.services.employment_service import EmploymentService, coerce_termination_reason

# Set up logger
logger = logging.getLogger("app.employment")

# Set up router
router = APIRouter(prefix="/api/v1/clients", tags=["employment"])


def validate_client_exists_and_active(client_id: int, db: Session) -> Client:
    """
    Validate client exists and is active
    
    Args:
        client_id: Client ID to validate
        db: Database session
        
    Returns:
        Client object if valid
        
    Raises:
        HTTPException: If client not found or inactive
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳ ׳‘׳׳¢׳¨׳›׳×"}
        )
    
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳ ׳‘׳׳¢׳¨׳›׳×"}
        )
    
    return client


@router.post("/{client_id}/employment/current", response_model=EmploymentOut, status_code=status.HTTP_201_CREATED)
def set_current_employer(
    client_id: int, 
    employment_data: EmploymentCreate, 
    db: Session = Depends(get_db)
) -> EmploymentOut:
    """
    Set current employer for a client
    
    Args:
        client_id: Client ID
        employment_data: Employment creation data
        db: Database session
        
    Returns:
        Employment object with 201 status
    """
    # Validate client exists and is active
    client = validate_client_exists_and_active(client_id, db)
    
    start = time.perf_counter()
    try:
        # Call employment service
        employment = EmploymentService.set_current_employer(
            db=db,
            client_id=client_id,
            employer_name=employment_data.employer_name,
            reg_no=employment_data.employer_reg_no,
            start_date=employment_data.start_date
        )
        
        logger.info({
            "event": "employment.set_current",
            "client_id": client_id,
            "ok": True,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "employment_id": employment.id
        })
        return employment
        
    except ValueError as e:
        # Handle business logic errors from service
        logger.info({
            "event": "employment.set_current",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        
        # Map specific errors to appropriate status codes
        if "׳׳™׳ ׳׳¢׳¡׳™׳§ ׳ ׳•׳›׳—׳™" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": str(e)}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": str(e)}
            )
    except Exception as e:
        logger.info({
            "event": "employment.set_current",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"׳©׳’׳™׳׳” ׳‘׳™׳¦׳™׳¨׳× ׳×׳¢׳¡׳•׳§׳” ׳ ׳•׳›׳—׳™׳×: {str(e)}"}
        )


@router.patch("/{client_id}/employment/termination/plan", response_model=TerminationEventOut)
def plan_termination(
    client_id: int, 
    termination_data: TerminationPlanIn, 
    db: Session = Depends(get_db)
) -> TerminationEventOut:
    """
    Plan termination for a client's current employment
    
    Args:
        client_id: Client ID
        termination_data: Termination planning data
        db: Database session
        
    Returns:
        TerminationEvent object
    """
    # Validate client exists and is active
    client = validate_client_exists_and_active(client_id, db)
    
    start = time.perf_counter()
    try:
        # Parse termination reason first using helper
        reason_enum = coerce_termination_reason(termination_data.termination_reason)
        
        # Call employment service (service handles date validation)
        termination_event = EmploymentService.plan_termination(
            db=db,
            client_id=client_id,
            planned_date=termination_data.planned_termination_date,
            reason=reason_enum
        )
        
        logger.info({
            "event": "employment.plan",
            "client_id": client_id,
            "ok": True,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "employment_id": termination_event.employment_id
        })
        return termination_event
        
    except ValueError as e:
        # Handle business logic errors from service
        logger.info({
            "event": "employment.plan",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        
        # Map specific errors to appropriate status codes
        if "׳׳ ׳ ׳™׳×׳ ׳׳×׳›׳ ׳ ׳¢׳–׳™׳‘׳”" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": str(e)}
            )
        elif "invalid_termination_reason" in str(e):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "׳¡׳™׳‘׳× ׳¢׳–׳™׳‘׳” ׳׳™׳ ׳” ׳×׳§׳™׳ ׳”"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": str(e)}
            )
    except Exception as e:
        logger.info({
            "event": "employment.plan",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"׳©׳’׳™׳׳” ׳‘׳×׳›׳ ׳•׳ ׳¢׳–׳™׳‘׳”: {str(e)}"}
        )


def generate_fixation_package_for_client_background(db: Session, client_id: int):
    """
    Generate fixation package for a client in the background
    
    Args:
        db: Database session
        client_id: Client ID
    """
    from anyio import to_thread
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import get_db_url
    
    # Function to run in background thread with its own DB session
    def _generate_fixation_package_in_bg(db_url: str, client_id: int):
        try:
            # Create new session in background thread
            engine = create_engine(db_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()
            
            # Import here to avoid circular imports
            from app.routers.fixation import generate_fixation_package_for_client
            
            # Generate complete package
            result = generate_fixation_package_for_client(db=db, client_id=client_id)
            if result.get("success", False):
                logger.info(f"Background fixation package generated for client {client_id}: {len(result.get('files', []))} files")
            else:
                logger.warning(f"Background fixation package generation failed for client {client_id}: {result.get('message', 'Unknown error')}")
                
            # Close session
            db.close()
        except Exception as e:
            logger.exception(f"fixation_bg_trigger_error: {e}")
    
    # Get DB URL for background thread
    db_url = get_db_url()
    
    # Run in background thread without awaiting
    try:
        import threading
        thread = threading.Thread(target=_generate_fixation_package_in_bg, args=(db_url, client_id))
        thread.daemon = True
        thread.start()
    except Exception:
        logger.exception("fixation_bg_trigger_error")  # ׳׳ ׳׳₪׳™׳ ׳׳× ׳”-API


@router.post("/{client_id}/employment/termination/confirm", response_model=TerminationEventOut)
def confirm_termination(
    client_id: int, 
    termination_data: TerminationConfirmIn, 
    db: Session = Depends(get_db)
) -> TerminationEventOut:
    """
    Confirm termination for a client's current employment
    
    Args:
        client_id: Client ID
        termination_data: Termination confirmation data
        db: Database session
        
    Returns:
        TerminationEvent object
    """
    # Validate client exists and is active
    client = validate_client_exists_and_active(client_id, db)
    
    start = time.perf_counter()
    try:
        # Call employment service
        termination_event = EmploymentService.confirm_termination(
            db=db,
            client_id=client_id,
            actual_date=termination_data.actual_termination_date
        )
        
        logger.info({
            "event": "employment.confirm",
            "client_id": client_id,
            "ok": True,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "employment_id": termination_event.employment_id
        })
        
        # Trigger background fixation package generation (non-blocking)
        try:
            generate_fixation_package_for_client_background(db, client_id)
        except Exception as e:
            # Don't fail the main response if background task fails
            logger.warning(f"Background fixation package generation failed for client {client_id}: {e}")
        
        return termination_event
        
    except ValueError as e:
        # Handle business logic errors from service
        logger.info({
            "event": "employment.confirm",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        
        # Map specific errors to appropriate status codes
        if "׳׳™׳ ׳׳¢׳¡׳™׳§ ׳ ׳•׳›׳—׳™" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": str(e)}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": str(e)}
            )
    except Exception as e:
        logger.info({
            "event": "employment.confirm",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"׳©׳’׳™׳׳” ׳‘׳׳™׳©׳•׳¨ ׳¢׳–׳™׳‘׳”: {str(e)}"}
        )

