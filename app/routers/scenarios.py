"""
Scenarios router with CRUD operations for Scenario management
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.client import Client
from app.models.scenario import Scenario
# ייבוא סכמות התרחיש
try:
    from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioResponse
except ImportError:
    # יצירת סכמות זמניות אם הקובץ לא קיים
    from pydantic import BaseModel, Field
    from typing import Optional
    from datetime import datetime
    
    class ScenarioBase(BaseModel):
        name: str
        description: Optional[str] = None
        parameters: str = Field(default="{}", description="JSON parameters for scenario")
    
    class ScenarioCreate(BaseModel):
        name: str
        description: Optional[str] = None
    
    class ScenarioUpdate(ScenarioBase):
        name: Optional[str] = None
        parameters: Optional[str] = None
    
    class ScenarioResponse(BaseModel):
        id: int
        client_id: int
        name: str
        description: Optional[str] = None
        parameters: str = "{}"
        cashflow_projection: Optional[str] = None
        summary_results: Optional[str] = None
        created_at: datetime
        
        @classmethod
        def from_db_scenario(cls, db_scenario):
            return cls(
                id=db_scenario.id,
                client_id=db_scenario.client_id,
                name=db_scenario.scenario_name,
                description=None,  # Not stored in DB
                parameters=db_scenario.parameters or "{}",
                cashflow_projection=db_scenario.cashflow_projection,
                summary_results=db_scenario.summary_results,
                created_at=db_scenario.created_at
            )
        
        class Config:
            from_attributes = True

# ייבוא סכמת תגובת API
from app.schemas import APIResponse
from app.services.calculations import generate_cashflow
from app.services.retirement_scenarios import RetirementScenariosBuilder

router = APIRouter(
    prefix="/api/v1/clients",
    tags=["scenarios"],
    responses={404: {"description": "Not found"}},
)


@router.post("/{client_id}/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    scenario: ScenarioCreate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Create a new scenario for a client and run cashflow generation"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Generate cashflow using the calculation engine
    try:
        cashflow_result = generate_cashflow(client_id, {})
        cashflow_json = json.dumps(cashflow_result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cashflow: {str(e)}"
        )
    
    # Create scenario with generated cashflow - map frontend fields to DB fields
    db_scenario = Scenario(
        client_id=client_id,
        scenario_name=scenario.name,
        parameters='{}',  # Default empty parameters
        cashflow_projection=cashflow_json
    )
    
    # Create summary results from cashflow
    summary_results = {
        "total_months": len(cashflow_result.get("monthly", [])),
        "yearly_totals": cashflow_result.get("yearly_totals", {}),
        "status": "completed",
        "generated_at": cashflow_result.get("calculation_date")
    }
    db_scenario.summary_results = json.dumps(summary_results)
    
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    
    return ScenarioResponse.from_db_scenario(db_scenario)


@router.get("/{client_id}/scenarios", response_model=List[ScenarioResponse])
def get_client_scenarios(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """Get all scenarios for a client"""
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    scenarios = db.query(Scenario).filter(Scenario.client_id == client_id).all()
    return [ScenarioResponse.from_db_scenario(s) for s in scenarios]


@router.get("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get specific scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    return ScenarioResponse.from_db_scenario(db_scenario)


@router.put("/{client_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario: ScenarioUpdate,
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Update scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    # Update only provided fields
    update_data = scenario.model_dump(exclude_unset=True)
    
    # If parameters are updated, regenerate cashflow
    if "parameters" in update_data:
        try:
            scenario_params = json.loads(update_data["parameters"]) if update_data["parameters"] != "{}" else {}
            cashflow_result = generate_cashflow(client_id, scenario_params)
            update_data["cashflow_projection"] = json.dumps(cashflow_result)
            
            # Update summary results
            summary_results = {
                "total_months": len(cashflow_result.get("monthly", [])),
                "yearly_totals": cashflow_result.get("yearly_totals", {}),
                "status": "completed",
                "generated_at": cashflow_result.get("calculation_date")
            }
            update_data["summary_results"] = json.dumps(summary_results)
        except (json.JSONDecodeError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to process parameters or generate cashflow: {str(e)}"
            )
    
    for field, value in update_data.items():
        setattr(db_scenario, field, value)
    
    db.commit()
    db.refresh(db_scenario)
    
    return db_scenario


@router.delete("/{client_id}/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Delete scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    db.delete(db_scenario)
    db.commit()


@router.get("/{client_id}/scenarios/{scenario_id}/cashflow")
def get_scenario_cashflow(
    client_id: int = Path(..., description="Client ID"),
    scenario_id: int = Path(..., description="Scenario ID"),
    db: Session = Depends(get_db)
):
    """Get cashflow data for a specific scenario"""
    db_scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not db_scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    if not db_scenario.cashflow_projection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cashflow data available for this scenario"
        )
    
    try:
        cashflow_data = json.loads(db_scenario.cashflow_projection)
        return cashflow_data
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid cashflow data format"
        )


class RetirementScenariosRequest(BaseModel):
    """Request schema for retirement scenarios"""
    retirement_age: int = Field(..., ge=50, le=80, description="גיל פרישה מבוקש")
    pension_portfolio: Optional[List[dict]] = Field(default=None, description="נתוני תיק פנסיוני (אופציונלי)")


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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎯🎯 Retirement scenarios endpoint called for client {client_id}, age {request.retirement_age}")
    
    retirement_age = request.retirement_age
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"לקוח {client_id} לא נמצא"
        )
    
    # Validate retirement age
    if retirement_age < 50 or retirement_age > 80:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="גיל פרישה חייב להיות בין 50 ל-80"
        )
    
    try:
        # Build all scenarios
        builder = RetirementScenariosBuilder(db, client_id, retirement_age, request.pension_portfolio)
        scenarios = builder.build_all_scenarios()
        
        # שמירת התרחישים במסד הנתונים
        saved_scenarios = {}
        for scenario_key, scenario_data in scenarios.items():
            # מחיקת תרחישים קודמים לאותו גיל פרישה ואותו סוג תרחיש
            db.query(Scenario).filter(
                Scenario.client_id == client_id,
                Scenario.scenario_name == scenario_data["scenario_name"],
                Scenario.parameters.like(f'%"retirement_age": {retirement_age}%')
            ).delete(synchronize_session=False)
            
            # יצירת תרחיש חדש
            new_scenario = Scenario(
                client_id=client_id,
                scenario_name=scenario_data["scenario_name"],
                parameters=json.dumps({
                    "retirement_age": retirement_age,
                    "scenario_type": scenario_key,
                    "pension_portfolio": request.pension_portfolio  # שמירת נתוני תיק פנסיוני
                }),
                summary_results=json.dumps(scenario_data),
                cashflow_projection=None  # ניתן להוסיף בעתיד
            )
            db.add(new_scenario)
            db.flush()
            
            # הוספת ID לתוצאות
            scenario_data["scenario_id"] = new_scenario.id
            saved_scenarios[scenario_key] = scenario_data
        
        db.commit()
        
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
            detail=str(e)
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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📥 Getting saved retirement scenarios for client {client_id}, age {retirement_age}")
    
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"לקוח {client_id} לא נמצא"
        )
    
    # Query scenarios
    query = db.query(Scenario).filter(Scenario.client_id == client_id)
    
    if retirement_age:
        query = query.filter(Scenario.parameters.like(f'%"retirement_age": {retirement_age}%'))
    
    scenarios = query.order_by(Scenario.created_at.desc()).all()
    
    if not scenarios:
        return {
            "success": True,
            "client_id": client_id,
            "retirement_age": retirement_age,
            "scenarios": None,
            "message": "לא נמצאו תרחישים שמורים"
        }
    
    # ארגון התרחישים לפי סוג
    organized_scenarios = {}
    for scenario in scenarios:
        try:
            params = json.loads(scenario.parameters) if scenario.parameters else {}
            scenario_type = params.get("scenario_type", "unknown")
            age = params.get("retirement_age")
            
            # אם retirement_age לא צוין, נשתמש בגיל הראשון שנמצא
            if not retirement_age and age:
                retirement_age = age
            
            if scenario.summary_results:
                summary = json.loads(scenario.summary_results)
                summary["scenario_id"] = scenario.id
                organized_scenarios[scenario_type] = summary
        except Exception as e:
            logger.warning(f"Failed to parse scenario {scenario.id}: {e}")
    
    if organized_scenarios:
        return {
            "success": True,
            "client_id": client_id,
            "retirement_age": retirement_age,
            "scenarios": organized_scenarios
        }
    
    return {
        "success": True,
        "client_id": client_id,
        "retirement_age": retirement_age,
        "scenarios": None,
        "message": "לא נמצאו תרחישים שמורים"
    }


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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"⚡ Executing scenario {scenario_id} for client {client_id}")
    
    # Check if client exists
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"לקוח {client_id} לא נמצא"
        )
    
    # Get the scenario
    scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"תרחיש {scenario_id} לא נמצא"
        )
    
    try:
        # Parse scenario data
        params = json.loads(scenario.parameters) if scenario.parameters else {}
        summary_results = json.loads(scenario.summary_results) if scenario.summary_results else {}
        
        retirement_age = params.get("retirement_age")
        scenario_type = params.get("scenario_type")
        
        if not retirement_age:
            raise ValueError("גיל פרישה חסר בתרחיש")
        
        logger.info("🧹 Step 1: Cleaning up previous scenario results...")
        
        # ===== שלב 1: שחזור מצב מקורי - מחיקת כל התוצאות מתרחישים קודמים =====
        from app.models.pension_fund import PensionFund
        from app.models.capital_asset import CapitalAsset
        from app.models.additional_income import AdditionalIncome
        
        cleanup_count = 0
        
        # 1. מחיקת קצבאות שנוצרו מהמרות (יש להן pension_amount אבל נוצרו מתרחיש)
        # זיהוי: אם conversion_source מכיל "source": "termination_event" או יש להן pension_amount שהוגדר על ידי תרחיש
        scenario_pensions = db.query(PensionFund).filter(
            PensionFund.client_id == client_id,
            PensionFund.conversion_source.isnot(None),
            PensionFund.conversion_source.like('%"source": "termination_event"%')
        ).all()
        
        for pf in scenario_pensions:
            logger.info(f"  🗑️ Deleting scenario pension: {pf.fund_name}")
            db.delete(pf)
            cleanup_count += 1
        
        # 2. איפוס pension_amount של מוצרים מתיק פנסיוני (נשאיר רק balance)
        portfolio_pensions = db.query(PensionFund).filter(
            PensionFund.client_id == client_id,
            PensionFund.conversion_source.isnot(None),
            PensionFund.conversion_source.like('%"source": "pension_portfolio"%')
        ).all()
        
        for pf in portfolio_pensions:
            if pf.pension_amount:
                logger.info(f"  🔄 Resetting pension_amount for: {pf.fund_name} (keeping balance)")
                pf.pension_amount = None
                pf.pension_start_date = None
                cleanup_count += 1
        
        # 3. מחיקת נכסי הון שנוצרו מהמרות/היוונים
        scenario_capital = db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.conversion_source.isnot(None)
        ).all()
        
        for ca in scenario_capital:
            logger.info(f"  🗑️ Deleting scenario capital: {ca.asset_name}")
            db.delete(ca)
            cleanup_count += 1
        
        # 4. מחיקת הכנסות נוספות שנוצרו מהמרות (מזוהות ע"י remarks)
        scenario_incomes = db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == client_id,
            AdditionalIncome.remarks.isnot(None),
            AdditionalIncome.remarks.like('%"source": "scenario_conversion"%')
        ).all()
        
        for ai in scenario_incomes:
            logger.info(f"  🗑️ Deleting scenario income: {ai.description}")
            db.delete(ai)
            cleanup_count += 1
        
        db.flush()
        logger.info(f"  ✅ Cleaned up {cleanup_count} items from previous scenarios")
        logger.info("")
        
        logger.info("⚡ Step 2: Executing new scenario...")
        
        # ===== שלב 2: ביצוע התרחיש החדש על המצב הנקי =====
        
        # קריאת נתוני תיק פנסיוני מהפרמטרים השמורים
        pension_portfolio_data = params.get("pension_portfolio")
        
        if not pension_portfolio_data:
            logger.warning("  ⚠️ No pension portfolio data found in saved scenario")
        else:
            logger.info(f"  📦 Found {len(pension_portfolio_data)} pension accounts in saved scenario")
        
        # בניית התרחיש בפועל (ללא שחזור מצב)
        from app.services.retirement_scenarios import RetirementScenariosBuilder
        builder = RetirementScenariosBuilder(db, client_id, retirement_age, pension_portfolio_data)
        
        # בחירת הפונקציה המתאימה
        if scenario_type == "scenario_1_max_pension":
            result = builder._build_max_pension_scenario()
        elif scenario_type == "scenario_2_max_capital":
            result = builder._build_max_capital_scenario()
        elif scenario_type == "scenario_3_max_npv":
            result = builder._build_max_npv_scenario()
        else:
            raise ValueError(f"סוג תרחיש לא ידוע: {scenario_type}")
        
        # שמירת השינויים בפועל
        db.commit()
        
        actions_count = len(result.get('execution_plan', []))
        
        logger.info(f"")
        logger.info(f"✅ Scenario {scenario_id} executed successfully!")
        logger.info(f"   - Cleaned: {cleanup_count} old items")
        logger.info(f"   - Actions: {actions_count} steps")
        logger.info(f"   - Pension: {result.get('total_pension_monthly', 0):.0f} ₪/month")
        logger.info(f"   - Capital: {result.get('total_capital', 0):,.0f} ₪")
        
        return {
            "success": True,
            "message": f"התרחיש בוצע בהצלחה (ניקוי: {cleanup_count} פריטים, פעולות: {actions_count})",
            "scenario_id": scenario_id,
            "scenario_name": scenario.scenario_name,
            "cleanup_count": cleanup_count,
            "actions_count": actions_count,
            "result": result
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to execute scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה בביצוע התרחיש: {str(e)}"
        )
