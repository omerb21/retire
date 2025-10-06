"""
Report router for PDF generation endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Client, Scenario
from app.services.report_service import ReportService
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ReportRequest(BaseModel):
    """Request model for PDF report generation."""
    client_id: int
    scenario_ids: Optional[List[int]] = None


@router.post("/pdf")
async def generate_pdf_report(
    request: ReportRequest,
    db: Session = Depends(get_db)
):
    """
    Generate PDF report for client scenarios.
    
    Args:
        request: Report request with client_id and optional scenario_ids
        db: Database session
        
    Returns:
        StreamingResponse with PDF content
        
    Raises:
        HTTPException: If client not found or scenarios not calculated
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == request.client_id).first()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"לקוח עם מזהה {request.client_id} לא נמצא"
            )
        
        # Get scenarios
        if request.scenario_ids:
            scenarios = db.query(Scenario).filter(
                Scenario.id.in_(request.scenario_ids),
                Scenario.client_id == request.client_id
            ).all()
            
            if len(scenarios) != len(request.scenario_ids):
                found_ids = [s.id for s in scenarios]
                missing_ids = [sid for sid in request.scenario_ids if sid not in found_ids]
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"תרחישים לא נמצאו: {missing_ids}"
                )
        else:
            # Get first 3 scenarios for the client
            scenarios = db.query(Scenario).filter(
                Scenario.client_id == request.client_id
            ).order_by(Scenario.created_at.desc()).limit(3).all()
        
        if not scenarios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="לא נמצאו תרחישים עבור הלקוח"
            )
        
        # Check if scenarios have been calculated
        uncalculated_scenarios = []
        for scenario in scenarios:
            if not scenario.summary_results or not scenario.cashflow_projection:
                uncalculated_scenarios.append(scenario.id)
        
        if uncalculated_scenarios:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"התרחישים הבאים לא חושבו עדיין: {uncalculated_scenarios}. הרץ חישוב לפני יצוא PDF"
            )
        
        # Generate report components
        logger.info(f"Generating PDF report for client {request.client_id} with scenarios {[s.id for s in scenarios]}")
        
        # Build summary data
        summary = ReportService.build_summary_table(client, scenarios, db)
        
        # Generate charts
        chart_cashflow = None
        chart_compare = None
        
        if scenarios:
            # Use first scenario for cashflow chart
            first_scenario_cashflow = None
            if scenarios[0].cashflow_projection:
                try:
                    import json
                    first_scenario_cashflow = json.loads(scenarios[0].cashflow_projection) if isinstance(scenarios[0].cashflow_projection, str) else scenarios[0].cashflow_projection
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Error parsing cashflow for scenario {scenarios[0].id}: {e}")
            
            if first_scenario_cashflow:
                chart_cashflow = ReportService.render_cashflow_chart(first_scenario_cashflow)
            
            # Generate comparison chart if multiple scenarios
            if len(scenarios) > 1:
                chart_compare = ReportService.render_scenarios_compare_chart(scenarios)
        
        # Compose PDF
        pdf_bytes = ReportService.compose_pdf(
            client=client,
            scenarios=scenarios,
            summary=summary,
            chart_cashflow=chart_cashflow,
            chart_compare=chart_compare
        )
        
        # Create streaming response
        pdf_stream = io.BytesIO(pdf_bytes)
        
        logger.info(f"PDF report generated successfully for client {request.client_id}, size: {len(pdf_bytes)} bytes")
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=report_{request.client_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF report for client {request.client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה ביצירת דוח PDF: {str(e)}"
        )


@router.post("/preview")
async def preview_report_data(
    request: ReportRequest,
    db: Session = Depends(get_db)
):
    """
    Preview report data as JSON for debugging/QA purposes.
    
    Args:
        request: Report request with client_id and optional scenario_ids
        db: Database session
        
    Returns:
        JSON with summary data that would be used in PDF
    """
    try:
        # Get client
        client = db.query(Client).filter(Client.id == request.client_id).first()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"לקוח עם מזהה {request.client_id} לא נמצא"
            )
        
        # Get scenarios
        if request.scenario_ids:
            scenarios = db.query(Scenario).filter(
                Scenario.id.in_(request.scenario_ids),
                Scenario.client_id == request.client_id
            ).all()
        else:
            scenarios = db.query(Scenario).filter(
                Scenario.client_id == request.client_id
            ).order_by(Scenario.created_at.desc()).limit(3).all()
        
        # Build summary data
        summary = ReportService.build_summary_table(client, scenarios, db)
        
        return {
            "client_id": request.client_id,
            "scenarios_count": len(scenarios),
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing report data for client {request.client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"שגיאה בתצוגה מקדימה של דוח: {str(e)}"
        )
