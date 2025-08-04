# app/routers/calc.py
import time
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.scenario import ScenarioIn, ScenarioOut, ScenarioCreateIn, ScenarioCreateOut, ScenarioListOut, ScenarioListItem
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.engine import CalculationEngine
from app.models import Client, Scenario

logger = logging.getLogger(__name__)
router = APIRouter()

def _run_calculation_handler(client_id: int, scenario: ScenarioIn, db: Session) -> ScenarioOut:
    """Shared calculation handler with structured logging"""
    start_time = time.time()
    
    try:
        # אימות בסיסי (בעברית)
        client = db.query(Client).get(client_id)
        if not client:
            logger.debug(f"event=calc.run, ok=false, client_id={client_id}, error=client_not_found")
            raise HTTPException(status_code=404, detail="לקוח לא נמצא")
        if not client.is_active:
            logger.debug(f"event=calc.run, ok=false, client_id={client_id}, error=client_inactive")
            raise HTTPException(status_code=400, detail="הלקוח אינו פעיל")

        # הרצת החישוב
        engine = CalculationEngine(db=db, tax_provider=InMemoryTaxParamsProvider())
        result = engine.run(client_id=client_id, scenario=scenario)
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"event=calc.run, ok=true, client_id={client_id}, duration_ms={duration_ms}")
        
        return result
        
    except ValueError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"event=calc.run, ok=false, client_id={client_id}, duration_ms={duration_ms}, error=validation")
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions (already logged above)
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"event=calc.run, ok=false, client_id={client_id}, duration_ms={duration_ms}, error=unexpected")
        raise HTTPException(status_code=500, detail="אירעה שגיאה בעת החישוב")

@router.post("/calc/{client_id}", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def run_calculation(client_id: int, scenario: ScenarioIn, db: Session = Depends(get_db)):
    """Run calculation for client scenario"""
    return _run_calculation_handler(client_id, scenario, db)

@router.post("/clients/{client_id}/calculate", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def calculate_client_scenario(client_id: int, scenario: ScenarioIn, db: Session = Depends(get_db)):
    """Alias endpoint: Run calculation for client scenario"""
    return _run_calculation_handler(client_id, scenario, db)

@router.post("/clients/{client_id}/scenarios", response_model=ScenarioCreateOut, status_code=status.HTTP_201_CREATED)
def create_scenario(client_id: int, scenario_data: ScenarioCreateIn, db: Session = Depends(get_db)):
    """Create and save a new scenario for client"""
    start_time = time.time()
    
    try:
        # אימות לקוח
        client = db.query(Client).get(client_id)
        if not client:
            logger.debug(f"event=scenario.create, ok=false, client_id={client_id}, error=client_not_found")
            raise HTTPException(status_code=404, detail="לקוח לא נמצא")
        if not client.is_active:
            logger.debug(f"event=scenario.create, ok=false, client_id={client_id}, error=client_inactive")
            raise HTTPException(status_code=400, detail="הלקוח אינו פעיל")

        # הכנת נתוני תרחיש לחישוב
        scenario_in = ScenarioIn(
            planned_termination_date=scenario_data.planned_termination_date,
            retirement_age=scenario_data.retirement_age,
            monthly_expenses=scenario_data.monthly_expenses,
            other_incomes_monthly=scenario_data.other_incomes_monthly
        )
        
        # הרצת החישוב
        engine = CalculationEngine(db=db, tax_provider=InMemoryTaxParamsProvider())
        result = engine.run(client_id=client_id, scenario=scenario_in)
        
        # שמירת התרחיש בבסיס הנתונים
        scenario_record = Scenario(
            client_id=client_id,
            scenario_name=scenario_data.scenario_name,
            parameters=json.dumps(scenario_in.model_dump(), default=str, ensure_ascii=False),
            summary_results=json.dumps({
                "seniority_years": result.seniority_years,
                "grant_gross": result.grant_gross,
                "grant_exempt": result.grant_exempt,
                "grant_tax": result.grant_tax,
                "grant_net": result.grant_net,
                "pension_monthly": result.pension_monthly,
                "indexation_factor": result.indexation_factor
            }, ensure_ascii=False),
            cashflow_projection=json.dumps([cf.model_dump() for cf in result.cashflow], default=str, ensure_ascii=False)
        )
        
        db.add(scenario_record)
        db.commit()
        db.refresh(scenario_record)
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"event=scenario.create, ok=true, client_id={client_id}, scenario_id={scenario_record.id}, duration_ms={duration_ms}")
        
        return ScenarioCreateOut(
            scenario_id=scenario_record.id,
            seniority_years=result.seniority_years,
            grant_gross=result.grant_gross,
            grant_exempt=result.grant_exempt,
            grant_tax=result.grant_tax,
            grant_net=result.grant_net,
            pension_monthly=result.pension_monthly,
            indexation_factor=result.indexation_factor,
            cashflow=result.cashflow
        )
        
    except ValueError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"event=scenario.create, ok=false, client_id={client_id}, duration_ms={duration_ms}, error=validation")
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"event=scenario.create, ok=false, client_id={client_id}, duration_ms={duration_ms}, error=unexpected")
        raise HTTPException(status_code=500, detail="אירעה שגיאה בעת יצירת התרחיש")

@router.get("/clients/{client_id}/scenarios", response_model=ScenarioListOut, status_code=status.HTTP_200_OK)
def list_scenarios(client_id: int, db: Session = Depends(get_db)):
    """List all scenarios for client"""
    start_time = time.time()
    
    try:
        # אימות לקוח
        client = db.query(Client).get(client_id)
        if not client:
            logger.debug(f"event=scenario.list, ok=false, client_id={client_id}, error=client_not_found")
            raise HTTPException(status_code=404, detail="לקוח לא נמצא")
        if not client.is_active:
            logger.debug(f"event=scenario.list, ok=false, client_id={client_id}, error=client_inactive")
            raise HTTPException(status_code=400, detail="הלקוח אינו פעיל")

        # שליפת רשימת תרחישים
        scenarios = db.query(Scenario).filter(Scenario.client_id == client_id).order_by(Scenario.created_at.desc()).all()
        
        scenario_items = [
            ScenarioListItem(
                id=s.id,
                scenario_name=s.scenario_name,
                created_at=s.created_at
            )
            for s in scenarios
        ]
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"event=scenario.list, ok=true, client_id={client_id}, count={len(scenario_items)}, duration_ms={duration_ms}")
        
        return ScenarioListOut(scenarios=scenario_items)
        
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"event=scenario.list, ok=false, client_id={client_id}, duration_ms={duration_ms}, error=unexpected")
        raise HTTPException(status_code=500, detail="אירעה שגיאה בעת שליפת רשימת התרחישים")

@router.get("/clients/{client_id}/scenarios/{scenario_id}", response_model=ScenarioOut, status_code=status.HTTP_200_OK)
def get_scenario(client_id: int, scenario_id: int, db: Session = Depends(get_db)):
    """Get full scenario details from database"""
    start_time = time.time()
    
    try:
        # אימות לקוח
        client = db.query(Client).get(client_id)
        if not client:
            logger.debug(f"event=scenario.get, ok=false, client_id={client_id}, scenario_id={scenario_id}, error=client_not_found")
            raise HTTPException(status_code=404, detail="לקוח לא נמצא")
        if not client.is_active:
            logger.debug(f"event=scenario.get, ok=false, client_id={client_id}, scenario_id={scenario_id}, error=client_inactive")
            raise HTTPException(status_code=400, detail="הלקוח אינו פעיל")

        # שליפת התרחיש
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.client_id == client_id
        ).first()
        
        if not scenario:
            logger.debug(f"event=scenario.get, ok=false, client_id={client_id}, scenario_id={scenario_id}, error=scenario_not_found")
            raise HTTPException(status_code=404, detail="תרחיש לא נמצא")
        
        # פענוח נתוני JSON
        try:
            summary_results = json.loads(scenario.summary_results)
            cashflow_data = json.loads(scenario.cashflow_projection)
            
            # המרת נתוני תזרים חזרה לאובייקטים
            from app.schemas.scenario import CashflowPoint
            cashflow_points = [CashflowPoint(**cf) for cf in cashflow_data]
            
            result = ScenarioOut(
                seniority_years=summary_results["seniority_years"],
                grant_gross=summary_results["grant_gross"],
                grant_exempt=summary_results["grant_exempt"],
                grant_tax=summary_results["grant_tax"],
                grant_net=summary_results["grant_net"],
                pension_monthly=summary_results["pension_monthly"],
                indexation_factor=summary_results["indexation_factor"],
                cashflow=cashflow_points
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug(f"event=scenario.get, ok=true, client_id={client_id}, scenario_id={scenario_id}, duration_ms={duration_ms}")
            
            return result
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"event=scenario.get, ok=false, client_id={client_id}, scenario_id={scenario_id}, error=json_decode")
            raise HTTPException(status_code=500, detail="שגיאה בפענוח נתוני התרחיש")
        
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"event=scenario.get, ok=false, client_id={client_id}, scenario_id={scenario_id}, duration_ms={duration_ms}, error=unexpected")
        raise HTTPException(status_code=500, detail="אירעה שגיאה בעת שליפת התרחיש")
