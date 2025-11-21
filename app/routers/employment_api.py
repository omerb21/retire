"""
Employment API router for legacy employment & termination endpoints.
This router exposes the /api/v1/clients/{client_id}/employment/... paths
used by tests/test_employment_api.py, delegating to EmploymentService.
"""
import logging
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.schemas.employment import (
    TerminationPlanIn,
    TerminationConfirmIn,
    TerminationEventOut,
)
from app.services.employment_service import EmploymentService, coerce_termination_reason

# Set up logger
logger = logging.getLogger("app.employment_api")

# Router for legacy employment API endpoints
router = APIRouter(prefix="/api/v1/clients", tags=["employment"])


def validate_client_exists_and_active(client_id: int, db: Session) -> Client:
    """Validate client exists and is active for employment operations."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "לקוח לא נמצא במערכת"},
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "לקוח לא פעיל במערכת"},
        )

    return client


@router.patch("/{client_id}/employment/termination/plan", response_model=TerminationEventOut)
def plan_termination(
    client_id: int,
    termination_data: TerminationPlanIn,
    db: Session = Depends(get_db),
) -> TerminationEventOut:
    """Plan termination for a client's current employment.

    - Returns 200 with TerminationEventOut on success.
    - Returns 409 if there is no current employment to terminate.
    - Returns 422 for invalid termination reason or past planned date.
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
            reason=reason_enum,
        )

        logger.info(
            {
                "event": "employment.plan",
                "client_id": client_id,
                "ok": True,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "employment_id": termination_event.employment_id,
            }
        )
        return termination_event

    except ValueError as e:
        # Handle business logic errors from service
        logger.info(
            {
                "event": "employment.plan",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": str(e),
            }
        )

        message = str(e)
        # Map specific errors to appropriate status codes. We look for the
        # same encoded substring used in the legacy employment router to
        # detect the "no current employment" case.
        if "׳׳ ׳ ׳™׳×׳ ׳׳×׳›׳ ׳ ׳¢׳–׳™׳‘׳”" in message:
            # No current employment to terminate
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": message},
            )
        if "invalid_termination_reason" in message:
            # Invalid termination reason
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "סיבת עזיבה אינה תקינה"},
            )

        # Default: validation/business error
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": message},
        )
    except Exception as e:
        logger.info(
            {
                "event": "employment.plan",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה בתכנון עזיבה: {str(e)}"},
        )


def generate_fixation_package_for_client_background(db: Session, client_id: int) -> None:
    """Trigger fixation package generation in a background thread.

    This mirrors the helper from the legacy employment router and is
    intentionally fire-and-forget: any failure is logged but does not
    affect the main API response.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import threading

    # Use the same connection parameters as the provided session
    db_url = str(db.bind.url)

    def _generate_fixation_package_in_bg(db_url: str, client_id: int) -> None:
        try:
            engine = create_engine(db_url)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            bg_db = SessionLocal()
            try:
                from app.routers.fixation import generate_fixation_package_for_client

                result = generate_fixation_package_for_client(db=bg_db, client_id=client_id)
                if result.get("success", False):
                    logger.info(
                        "Background fixation package generated for client %s: %s files",
                        client_id,
                        len(result.get("files", [])),
                    )
                else:
                    logger.warning(
                        "Background fixation package generation failed for client %s: %s",
                        client_id,
                        result.get("message", "Unknown error"),
                    )
            finally:
                bg_db.close()
        except Exception as exc:
            logger.exception("fixation_bg_trigger_error: %s", exc)

    try:
        thread = threading.Thread(
            target=_generate_fixation_package_in_bg, args=(db_url, client_id)
        )
        thread.daemon = True
        thread.start()
    except Exception:
        logger.exception("fixation_bg_trigger_error")


@router.post("/{client_id}/employment/termination/confirm", response_model=TerminationEventOut)
def confirm_termination(
    client_id: int,
    termination_data: TerminationConfirmIn,
    db: Session = Depends(get_db),
) -> TerminationEventOut:
    """Confirm termination for a client's current employment.

    On success, also triggers background fixation package generation.
    """
    # Validate client exists and is active
    client = validate_client_exists_and_active(client_id, db)

    start = time.perf_counter()
    try:
        termination_event = EmploymentService.confirm_termination(
            db=db,
            client_id=client_id,
            actual_date=termination_data.actual_termination_date,
        )

        logger.info(
            {
                "event": "employment.confirm",
                "client_id": client_id,
                "ok": True,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "employment_id": termination_event.employment_id,
            }
        )

        # Fire-and-forget background fixation package generation
        try:
            generate_fixation_package_for_client_background(db, client_id)
        except Exception as bg_exc:
            logger.warning(
                "Background fixation package generation failed for client %s: %s",
                client_id,
                bg_exc,
            )

        return termination_event

    except ValueError as e:
        logger.info(
            {
                "event": "employment.confirm",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": str(e),
            }
        )

        message = str(e)
        if "אין מעסיק נוכחי" in message:
            # No current employment to confirm termination for
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": message},
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": message},
        )
    except Exception as e:
        logger.info(
            {
                "event": "employment.confirm",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"שגיאה באישור עזיבה: {str(e)}"},
        )
