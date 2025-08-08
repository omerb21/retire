# app/routers/calc.py
import time
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.scenario import ScenarioIn, ScenarioOut, ScenarioCreateIn, ScenarioListOut, ScenarioListItem
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.engine import CalculationEngine
from app.models import Client, Scenario
from app.services.scenario_service import ScenarioService

logger = logging.getLogger("app.calc")
router = APIRouter()

def _run_calculation_handler(client_id: int, scenario: ScenarioIn, db: Session) -> ScenarioOut:
    """Shared calculation handler with structured logging"""
    start = time.perf_counter()
    
    try:
        # ׳׳™׳׳•׳× ׳‘׳¡׳™׳¡׳™ (׳‘׳¢׳‘׳¨׳™׳×)
        client = db.get(Client, client_id)
        if not client:
            logger.info({
                "event": "calc.run",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": "client_not_found"
            })
            raise HTTPException(status_code=404, detail="׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳")
        if not client.is_active:
            logger.info({
                "event": "calc.run",
                "client_id": client_id,
                "ok": False,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "error": "client_inactive"
            })
            raise HTTPException(status_code=400, detail="׳”׳׳§׳•׳— ׳׳™׳ ׳• ׳₪׳¢׳™׳")

        # ׳”׳¨׳¦׳× ׳”׳—׳™׳©׳•׳‘
        engine = CalculationEngine(db=db, tax_provider=InMemoryTaxParamsProvider())
        result = engine.run(client_id=client_id, scenario=scenario)
        
        logger.info({
            "event": "calc.run",
            "client_id": client_id,
            "ok": True,
            "duration_ms": int((time.perf_counter() - start) * 1000)
        })
        
        return result
        
    except ValueError as e:
        logger.info({
            "event": "calc.run",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions (already logged above)
        raise
    except Exception as e:
        logger.info({
            "event": "calc.run",
            "client_id": client_id,
            "ok": False,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="׳׳™׳¨׳¢׳” ׳©׳’׳™׳׳” ׳‘׳¢׳× ׳”׳—׳™׳©׳•׳‘")

@router.post("/calc/{client_id}", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def run_calculation(client_id: int, scenario: ScenarioIn, db: Session = Depends(get_db)):
    """Run calculation for client scenario"""
    return _run_calculation_handler(client_id, scenario, db)

@router.post("/clients/{client_id}/calculate", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def calculate_client_scenario(client_id: int, scenario: ScenarioIn, db: Session = Depends(get_db)):
    """Alias endpoint: Run calculation for client scenario"""
    return _run_calculation_handler(client_id, scenario, db)

@router.post("/clients/{client_id}/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(client_id: int, scenario_data: ScenarioCreateIn, db: Session = Depends(get_db)):
    """Create a new scenario for client"""
    try:
        scenario = ScenarioService.create_scenario(db, client_id, scenario_data)
        return {"scenario_id": scenario.id}
    except ValueError as e:
        if "׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in create_scenario: {e}")
        raise HTTPException(status_code=500, detail="׳׳™׳¨׳¢׳” ׳©׳’׳™׳׳” ׳‘׳¢׳× ׳™׳¦׳™׳¨׳× ׳”׳×׳¨׳—׳™׳©")

@router.get("/clients/{client_id}/scenarios", response_model=ScenarioListOut, status_code=status.HTTP_200_OK)
def list_scenarios(client_id: int, db: Session = Depends(get_db)):
    """List all scenarios for client"""
    try:
        # Check if client exists
        client = db.get(Client, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳")
        
        scenarios = ScenarioService.list_scenarios(db, client_id)
        return ScenarioListOut(scenarios=scenarios)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in list_scenarios: {e}")
        raise HTTPException(status_code=500, detail="׳׳™׳¨׳¢׳” ׳©׳’׳™׳׳” ׳‘׳¢׳× ׳©׳׳™׳₪׳× ׳¨׳©׳™׳׳× ׳”׳×׳¨׳—׳™׳©׳™׳")

@router.post("/scenarios/{scenario_id}/run", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def run_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Run a scenario calculation and return results"""
    try:
        result = ScenarioService.run_scenario(db, scenario_id)
        return result
    except ValueError as e:
        if "׳׳™׳ ׳ ׳×׳•׳ ׳™ ׳×׳¢׳¡׳•׳§׳” ׳׳—׳™׳©׳•׳‘" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        elif "׳¡׳“׳¨׳× ׳׳“׳“ ׳—׳¡׳¨׳” ׳׳×׳׳¨׳™׳›׳™׳ ׳”׳׳‘׳•׳§׳©׳™׳" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        elif "׳×׳¨׳—׳™׳© ׳׳ ׳ ׳׳¦׳" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳" in str(e) or "׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in run_scenario: {e}")
        raise HTTPException(status_code=500, detail="׳׳™׳¨׳¢׳” ׳©׳’׳™׳׳” ׳‘׳¢׳× ׳”׳¨׳¦׳× ׳”׳×׳¨׳—׳™׳©")

@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Get full scenario details from database"""
    try:
        result = ScenarioService.get_scenario(db, scenario_id)
        if not result:
            raise HTTPException(status_code=404, detail="׳×׳¨׳—׳™׳© ׳׳ ׳ ׳׳¦׳")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in get_scenario: {e}")
        raise HTTPException(status_code=500, detail="׳׳™׳¨׳¢׳” ׳©׳’׳™׳׳” ׳‘׳¢׳× ׳©׳׳™׳₪׳× ׳”׳×׳¨׳—׳™׳©")


