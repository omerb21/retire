from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Any, Dict
from app.database import get_db
from app.schemas.compare import ScenarioCompareRequest
from app.services.compare_service import compare_scenarios

router = APIRouter(
    prefix="/api/v1",
    tags=["Scenario Compare"],
)


@router.post("/clients/{client_id}/scenarios/compare", summary="Compare scenarios cashflow (monthly + yearly)")
def compare_scenarios_endpoint(
    client_id: int,
    body: ScenarioCompareRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    משווה מספר תרחישים עבור לקוח נתון ומחזיר תזרים חודשי וטוטלים שנתיים.
    
    **Request Body Example:**
    ```json
    {
        "scenarios": [24, 25],
        "from": "2025-01",
        "to": "2025-12",
        "frequency": "monthly"
    }
    ```
    
    **Response Example:**
    ```json
    {
        "meta": {
            "client_id": 1,
            "from": "2025-01",
            "to": "2025-12",
            "frequency": "monthly"
        },
        "scenarios": {
            "24": {
                "monthly": [
                    {
                        "date": "2025-01-01",
                        "inflow": 10000.0,
                        "outflow": 5000.0,
                        "additional_income_net": 2000.0,
                        "capital_return_net": 500.0,
                        "net": 7500.0
                    }
                ],
                "yearly": {
                    "2025": {
                        "inflow": 120000.0,
                        "outflow": 60000.0,
                        "additional_income_net": 24000.0,
                        "capital_return_net": 6000.0,
                        "net": 90000.0
                    }
                }
            },
            "25": {
                "monthly": [...],
                "yearly": {...}
            }
        }
    }
    ```
    
    מחזיר עבור כל תרחיש:
    - **monthly**: רשימת שורות תזרים חודשי עם שדות: date, inflow, outflow, additional_income_net, capital_return_net, net
    - **yearly**: טוטלים שנתיים מצוברים לפי שנה
    
    **Validation:**
    - scenarios: רשימה לא ריקה של מזהי תרחיש חיוביים
    - from/to: פורמט YYYY-MM
    - frequency: רק "monthly" נתמך כרגע
    """
    try:
        data = compare_scenarios(
            db_session=db,
            client_id=client_id,
            scenario_ids=body.scenarios,
            from_yyyymm=body.from_,
            to_yyyymm=body.to,
            frequency=body.frequency,
        )
        return data
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to compare scenarios: {str(e)}")
