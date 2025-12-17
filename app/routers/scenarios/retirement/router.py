"""
Retirement scenarios router - handles retirement-specific endpoints
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.retirement_scenarios_api_service import (
    get_client_or_raise as get_client_or_raise_for_retirement,
    validate_retirement_age as validate_retirement_age_for_retirement,
    save_generated_retirement_scenarios,
    load_saved_retirement_scenarios,
)
from app.services.retirement_scenario_execution_service import (
    execute_retirement_scenario as execute_retirement_scenario_service,
)
from ..schemas import RetirementScenariosRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{client_id}/retirement-scenarios")
def generate_retirement_scenarios(
    request: RetirementScenariosRequest,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """
    מייצר 3 תרחישי פרישה אוטומטיים:
    1. מקסימום קצבה - כל הנכסים כקצבה
    2. מקסימום הון - מקסימום היוון עם שמירה על קצבת מינימום 5,500
    3. תרחיש מאוזן - 50% ערך כקצבה, 50% ערך כהון
    """
    logger.info(f"🎯🎯 Retirement scenarios endpoint called for client {client_id}, age {request.retirement_age}")
    
    retirement_age = request.retirement_age
    try:
        db_client = get_client_or_raise_for_retirement(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"לקוח {client_id} לא נמצא",
            )
        raise

    current_age = db_client.get_age()
    try:
        validate_retirement_age_for_retirement(
            retirement_age=retirement_age,
            current_age=current_age,
        )
    except ValueError as e:
        if str(e) == "age_out_of_range":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="גיל פרישה חייב להיות בין 50 ל-80",
            )
        if str(e) == "age_in_past":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="לא ניתן להפיק תרחיש לגיל עבר. ניתן להפיק תרחישים רק לגיל נוכחי או עתידי.",
            )
        raise
    
    try:
        # Build all scenarios
        builder = RetirementScenariosBuilder(
            db,
            client_id,
            retirement_age,
            request.pension_portfolio,
            request.include_current_employer_termination or False,
        )
        scenarios = builder.build_all_scenarios()
 
        saved_scenarios = save_generated_retirement_scenarios(
            db=db,
            client_id=client_id,
            retirement_age=retirement_age,
            pension_portfolio=request.pension_portfolio,
            include_current_employer_termination=bool(
                request.include_current_employer_termination or False
            ),
            scenarios=scenarios,
        )
         
        return {
            "success": True,
            "client_id": client_id,
            "retirement_age": retirement_age,
            "scenarios": saved_scenarios
        }
    
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"שגיאה ביצירת תרחישים: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה ביצירת תרחישים: {str(e)}"
        )


@router.get("/{client_id}/retirement-scenarios")
def get_saved_retirement_scenarios(
    client_id: int = Path(..., description="Client ID"),
    retirement_age: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    שולף תרחישי פרישה שמורים עבור לקוח.
    אם retirement_age מצוין, מחזיר רק תרחישים לגיל פרישה זה.
    """
    logger.info(f"📥 Getting saved retirement scenarios for client {client_id}, age {retirement_age}")

    try:
        get_client_or_raise_for_retirement(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"לקוח {client_id} לא נמצא",
            )
        raise

    return load_saved_retirement_scenarios(
        db=db,
        client_id=client_id,
        retirement_age=retirement_age,
    )


@router.post("/{client_id}/retirement-scenarios/{scenario_id}/execute")
def execute_retirement_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """
    מבצע בפועל את כל ההמרות של תרחיש מסוים.
    זה ישנה את המצב בפועל במערכת - קצבאות, נכסי הון, והכנסות נוספות.
    """
    try:
        return execute_retirement_scenario_service(db=db, client_id=client_id, scenario_id=scenario_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"לקוח {client_id} לא נמצא",
            )
        if str(e) == "scenario_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"תרחיש {scenario_id} לא נמצא",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה בביצוע התרחיש: {str(e)}",
        )
    except Exception as e:
        logger.error("❌ Failed to execute scenario %s: %s", scenario_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה בביצוע התרחיש: {str(e)}",
        )
