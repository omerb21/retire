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
from app.services.report_request_service import (
    get_client_or_raise,
    get_scenarios_for_client_or_raise,
    parse_scenario_ids_csv,
    get_or_create_default_scenario,
)

router = APIRouter()


class ReportRequest(BaseModel):
    scenario_ids: List[int]
    report_type: str = "comprehensive"  # comprehensive, summary, cashflow, comparison
    include_charts: bool = True
    include_cashflow: bool = True


@router.post("/clients/{client_id}/reports/generate")
def generate_report(
    client_id: int, request: ReportRequest, db: Session = Depends(get_db)
):
    """
    Generate PDF report for selected scenarios
    """
    try:
        client = get_client_or_raise(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
        raise

    try:
        scenarios = get_scenarios_for_client_or_raise(
            db=db, client_id=client_id, scenario_ids=request.scenario_ids
        )
    except ValueError as e:
        if str(e) == "scenario_mismatch":
            raise HTTPException(
                status_code=400,
                detail={"error": "חלק מהתרחישים לא נמצאו או לא שייכים ללקוח"},
            )
        raise

    try:
        # Generate PDF report
        pdf_buffer = ReportService.generate_pdf_report(
            client=client,
            scenarios=scenarios,
            report_type=request.report_type,
            include_charts=request.include_charts,
            include_cashflow=request.include_cashflow,
        )

        # Return PDF as response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"retirement_report_{client_id}_{timestamp}.pdf"

        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"error": f"שגיאה ביצירת דוח: {str(e)}"}
        )


@router.get("/clients/{client_id}/reports/preview")
def preview_report_data(
    client_id: int,
    scenario_ids: str,  # comma-separated scenario IDs
    db: Session = Depends(get_db),
):
    """
    Preview report data without generating PDF
    """
    try:
        client = get_client_or_raise(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
        raise

    try:
        scenario_id_list = parse_scenario_ids_csv(scenario_ids)
    except ValueError as e:
        if str(e) == "invalid_scenario_ids":
            raise HTTPException(
                status_code=400, detail={"error": "מזהי תרחישים לא תקינים"}
            )
        raise

    try:
        scenarios = get_scenarios_for_client_or_raise(
            db=db, client_id=client_id, scenario_ids=scenario_id_list
        )
    except ValueError as e:
        if str(e) == "scenario_mismatch":
            raise HTTPException(
                status_code=400,
                detail={"error": "חלק מהתרחישים לא נמצאו או לא שייכים ללקוח"},
            )
        raise

    # Return preview data
    return {
        "client": {
            "id": client.id,
            "name": client.full_name,
            "id_number": client.id_number,
        },
        "scenarios": [
            {
                "id": scenario.id,
                "name": scenario.scenario_name,
                "created_at": scenario.created_at,
                "parameters": scenario.parameters,
                "summary_results": scenario.summary_results,
            }
            for scenario in scenarios
        ],
        "report_ready": True,
    }


@router.post("/clients/{client_id}/reports/pdf")
def generate_simple_pdf_report(
    client_id: int, request: dict, db: Session = Depends(get_db)
):
    """
    Simple PDF report generation endpoint for frontend compatibility
    """
    try:
        client = get_client_or_raise(db=db, client_id=client_id)
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
        raise

    # Get scenario ID from request
    scenario_id = request.get("scenario_id", 1)
    scenario = get_or_create_default_scenario(
        db=db, client_id=client_id, scenario_id=scenario_id
    )

    try:
        # Generate PDF report using the existing service
        pdf_buffer = ReportService.generate_pdf_report(
            client=client,
            scenarios=[scenario],
            report_type=request.get("report_type", "comprehensive"),
            include_charts=request.get("include_charts", True),
            include_cashflow=request.get("include_cashflow", True),
        )

        # Return PDF as response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"retirement_report_{client_id}_{timestamp}.pdf"

        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"error": f"שגיאה ביצירת דוח: {str(e)}"}
        )


@router.get("/reports/{report_id}/download")
def download_report_by_id(report_id: str):
    """
    Download a generated PDF report by its report_id.
    Reports are stored in artifacts/reports/{report_id}.pdf
    """
    import os
    from fastapi.responses import FileResponse

    project_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_dir = os.path.dirname(os.path.dirname(__file__))

    candidate_dirs = [
        os.path.join(project_root_dir, "artifacts", "reports"),
        os.path.join(app_dir, "artifacts", "reports"),
    ]

    searched_paths = []

    pdf_path = None
    for d in candidate_dirs:
        candidate = os.path.join(d, f"{report_id}.pdf")
        searched_paths.append(candidate)
        if os.path.exists(candidate):
            pdf_path = candidate
            break

    if not pdf_path:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"דוח {report_id} לא נמצא",
                "searched_paths": searched_paths,
            },
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
        headers={"Content-Disposition": f"attachment; filename={report_id}.pdf"},
    )


@router.get("/documents/{doc_id}/download")
def download_document_by_id(doc_id: str):
    """
    Download a generated PDF document by its doc_id.
    Documents are stored in artifacts/documents/{doc_id}.pdf
    """
    import os
    from fastapi.responses import FileResponse

    project_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_dir = os.path.dirname(os.path.dirname(__file__))

    candidate_dirs = [
        os.path.join(project_root_dir, "artifacts", "documents"),
        os.path.join(app_dir, "artifacts", "documents"),
    ]

    searched_paths = []

    pdf_path = None
    for d in candidate_dirs:
        candidate = os.path.join(d, f"{doc_id}.pdf")
        searched_paths.append(candidate)
        if os.path.exists(candidate):
            pdf_path = candidate
            break

    if not pdf_path:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"מסמך {doc_id} לא נמצא",
                "searched_paths": searched_paths,
            },
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{doc_id}.pdf",
        headers={"Content-Disposition": f"attachment; filename={doc_id}.pdf"},
    )
