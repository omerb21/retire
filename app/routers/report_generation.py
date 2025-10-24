from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import logging

from app.database import get_db
from app.schemas.report import ReportPdfRequest
from app.utils.contract_adapter import ReportServiceAdapter

router = APIRouter(prefix="/api/v1", tags=["report-generation"])
logger = logging.getLogger(__name__)


@router.post("/scenarios/{scenario_id}/report/pdf")
async def generate_pdf_report(
    scenario_id: int,
    request: ReportPdfRequest,
    client_id: int = Query(..., description="Client ID for the report"),
    db: Session = Depends(get_db)
):
    """Generate PDF report with normalized input handling."""
    """
    Generate PDF report with cashflow data, charts, and summaries.
    
    This endpoint generates a comprehensive PDF report containing:
    - Client and scenario information
    - Monthly cashflow table with detailed breakdown
    - Yearly summary totals
    - Net cashflow chart visualization
    - Professional formatting with Hebrew support
    
    **Request Body Example:**
    ```json
    {
        "from": "2025-01",
        "to": "2025-12",
        "frequency": "monthly",
        "sections": {
            "summary": true,
            "cashflow_table": true,
            "net_chart": true,
            "scenarios_compare": true
        }
    }
    ```
    
    **Response:**
    - Content-Type: application/pdf
    - Content-Disposition: attachment with filename
    - Binary PDF data ready for download
    
    **Example Usage:**
    ```bash
    curl -X POST "http://localhost:8005/api/v1/scenarios/24/report/pdf?client_id=1" \
         -H "Content-Type: application/json" \
         -d '{"from":"2025-01","to":"2025-12","frequency":"monthly"}' \
         --output report.pdf
    ```
    
    The generated PDF includes:
    - Title page with system name and date range
    - Client/scenario identification details
    - Monthly cashflow breakdown table
    - Yearly aggregated totals
    - Net cashflow line chart (matplotlib-generated)
    - Professional Hebrew/RTL text support
    """
    try:
        logger.info(f"PDF report request: client_id={client_id}, scenario_id={scenario_id}, range={request.from_}-{request.to}")
        
        # Generate PDF using the adapter with detailed error handling
        try:
            pdf_bytes = ReportServiceAdapter.generate_pdf_report(
                db=db,
                client_id=client_id,
                scenario_id=scenario_id,
                request=request
            )
            
            # Verify PDF content
            if not pdf_bytes or len(pdf_bytes) < 100 or not pdf_bytes.startswith(b'%PDF'):
                logger.error(f"Generated invalid PDF format: {len(pdf_bytes)} bytes, starts with: {pdf_bytes[:20]}")
                raise ValueError("Invalid PDF format generated")
                
            logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
            
            # Create filename
            filename = f"report_{client_id}_{scenario_id}.pdf"
            
            # Return as streaming response
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except ValueError as e:
            logger.warning(f"Validation error in PDF generation: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # Log full exception details including traceback
            import traceback
            logger.error(f"Detailed PDF error: {traceback.format_exc()}")
            logger.error(f"Error generating PDF: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error during PDF generation: {type(e).__name__}")
    except HTTPException:
        # Just re-raise if it's already an HTTP exception
        raise
    except Exception as e:
        # Catch any unexpected errors in the router itself
        logger.error(f"Unexpected router error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error in PDF endpoint")
