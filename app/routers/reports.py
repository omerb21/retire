"""
Reports API router - PDF report generation
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import io
from datetime import datetime

from app.database import get_db
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.report_service import ReportService

router = APIRouter()

class ReportRequest(BaseModel):
    scenario_ids: List[int]
    report_type: str = "comprehensive"  # comprehensive, summary, cashflow, comparison
    include_charts: bool = True
    include_cashflow: bool = True

@router.post("/clients/{client_id}/reports/generate")
def generate_report(
    client_id: int,
    request: ReportRequest,
    db: Session = Depends(get_db)
):
    """
    Generate PDF report for selected scenarios
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Validate scenarios belong to client
    scenarios = db.query(Scenario).filter(
        Scenario.id.in_(request.scenario_ids),
        Scenario.client_id == client_id
    ).all()
    
    if len(scenarios) != len(request.scenario_ids):
        raise HTTPException(
            status_code=400,
            detail={"error": "חלק מהתרחישים לא נמצאו או לא שייכים ללקוח"}
        )
    
    try:
        # Generate PDF report
        pdf_buffer = ReportService.generate_pdf_report(
            client=client,
            scenarios=scenarios,
            report_type=request.report_type,
            include_charts=request.include_charts,
            include_cashflow=request.include_cashflow
        )
        
        # Return PDF as response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"retirement_report_{client_id}_{timestamp}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה ביצירת דוח: {str(e)}"}
        )

@router.get("/clients/{client_id}/reports/preview")
def preview_report_data(
    client_id: int,
    scenario_ids: str,  # comma-separated scenario IDs
    db: Session = Depends(get_db)
):
    """
    Preview report data without generating PDF
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Parse scenario IDs
    try:
        scenario_id_list = [int(id.strip()) for id in scenario_ids.split(',')]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "מזהי תרחישים לא תקינים"}
        )
    
    # Get scenarios
    scenarios = db.query(Scenario).filter(
        Scenario.id.in_(scenario_id_list),
        Scenario.client_id == client_id
    ).all()
    
    if len(scenarios) != len(scenario_id_list):
        raise HTTPException(
            status_code=400,
            detail={"error": "חלק מהתרחישים לא נמצאו או לא שייכים ללקוח"}
        )
    
    # Return preview data
    return {
        "client": {
            "id": client.id,
            "name": client.full_name,
            "id_number": client.id_number
        },
        "scenarios": [
            {
                "id": scenario.id,
                "name": scenario.scenario_name,
                "created_at": scenario.created_at,
                "parameters": scenario.parameters,
                "summary_results": scenario.summary_results
            }
            for scenario in scenarios
        ],
        "report_ready": True
    }

@router.post("/clients/{client_id}/reports/pdf")
def generate_simple_pdf_report(
    client_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Simple PDF report generation endpoint for frontend compatibility
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get scenario ID from request
    scenario_id = request.get('scenario_id', 1)
    
    # Get scenario
    scenario = db.query(Scenario).filter(
        Scenario.id == scenario_id,
        Scenario.client_id == client_id
    ).first()
    
    if not scenario:
        # Create a default scenario if none exists
        scenario = Scenario(
            client_id=client_id,
            scenario_name="דוח ברירת מחדל",
            parameters="{}",
            summary_results="{}",
            cashflow_projection="{}"
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
    
    try:
        # Generate PDF report using the existing service
        pdf_buffer = ReportService.generate_pdf_report(
            client=client,
            scenarios=[scenario],
            report_type=request.get('report_type', 'comprehensive'),
            include_charts=request.get('include_charts', True),
            include_cashflow=request.get('include_cashflow', True)
        )
        
        # Return PDF as response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"retirement_report_{client_id}_{timestamp}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה ביצירת דוח: {str(e)}"}
        )
