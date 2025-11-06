"""
High-level report generation functions
"""
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models import Client, Scenario
from app.schemas.report import ReportPdfRequest
from app.services.cashflow_service import generate_cashflow
from app.services.case_service import detect_case
from ..services.pdf_service import PDFService
from ..charts import create_net_cashflow_chart

_logger = logging.getLogger(__name__)


def generate_report_pdf(
    db: Session,
    client_id: int,
    scenario_id: int = None,
    request: ReportPdfRequest = None
) -> bytes:
    """
    Generate PDF report for client scenarios with cashflow data and charts.
    
    Args:
        db: Database session
        client_id: Client ID
        scenario_id: Single scenario ID (path parameter)
        request: Report request containing date range and sections
        
    Returns:
        PDF content as bytes
    """
    start_time = datetime.now()
    _logger.info(f"Starting PDF report generation for client={client_id}, scenario={scenario_id}, range={request.from_}-{request.to}")
    
    try:
        # Get client data
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Defensive handling: determine scenario_ids from multiple sources
        scenario_ids = []
        
        # Priority 1: scenario_id from path parameter
        if scenario_id is not None:
            scenario_ids = [scenario_id]
            _logger.info(f"Using scenario_id from path: {scenario_id}")
        
        # Priority 2: scenario_ids from request body (if exists)
        elif hasattr(request, 'scenario_ids') and request.scenario_ids:
            scenario_ids = request.scenario_ids
            _logger.info(f"Using scenario_ids from request body: {scenario_ids}")
        
        # Priority 3: scenarios from request body (alternative field name)
        elif hasattr(request, 'scenarios') and request.scenarios:
            scenario_ids = request.scenarios
            _logger.info(f"Using scenarios from request body: {scenario_ids}")
        
        # Fallback: error if no scenarios found
        else:
            raise ValueError("No scenario ID provided in path or request body")
        
        # Validate scenarios exist
        scenarios = db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()
        
        # Auto-detect case for consistency
        try:
            case_detection = detect_case(db, client_id)
            case_id = case_detection.case_id
            _logger.info(f"Detected case_id={case_id} for client={client_id}")
        except Exception as e:
            _logger.warning(f"Case detection failed, using default case: {e}")
            case_id = 1  # Default to standard case
        
        # Generate cashflow data using Sprint 7 service
        cashflow_data = []
        for sid in scenario_ids:
            try:
                _logger.info(f"Generating cashflow for scenario_id={sid}")
                cashflow_rows = generate_cashflow(
                    db=db,
                    client_id=client_id,
                    scenario_id=sid,
                    start_ym=request.from_,
                    end_ym=request.to,
                    case_id=case_id
                )
                _logger.info(f"Generated {len(cashflow_rows)} cashflow rows for scenario_id={sid}")
                cashflow_data.extend(cashflow_rows)
            except Exception as e:
                _logger.error(f"Error generating cashflow for scenario_id={sid}: {e}")
                raise ValueError(f"Failed to generate cashflow for scenario_id={sid}: {e}")
        
        # Calculate yearly totals for summary
        yearly_totals = {}
        for row in cashflow_data:
            # Handle both string and date object formats
            date_val = row['date']
            if hasattr(date_val, 'strftime'):
                year = date_val.strftime('%Y')
            else:
                year = str(date_val)[:4]  # Extract year from string
            if year not in yearly_totals:
                yearly_totals[year] = {
                    'inflow': 0,
                    'outflow': 0,
                    'additional_income_net': 0,
                    'capital_return_net': 0,
                    'net': 0
                }
            yearly_totals[year]['inflow'] += row.get('inflow', 0)
            yearly_totals[year]['outflow'] += row.get('outflow', 0)
            yearly_totals[year]['additional_income_net'] += row.get('additional_income_net', 0)
            yearly_totals[year]['capital_return_net'] += row.get('capital_return_net', 0)
            yearly_totals[year]['net'] += row.get('net', 0)
        
        # Create chart data for matplotlib
        chart_data = {
            'dates': [row['date'].strftime('%Y-%m') if hasattr(row['date'], 'strftime') else str(row['date'])[:7] for row in cashflow_data],
            'net_values': [row.get('net', 0) for row in cashflow_data]
        }
        
        # Generate charts
        chart_cashflow = None
        if request.sections.get('net_chart', True):
            chart_cashflow = create_net_cashflow_chart(chart_data)
        
        # Build PDF content - use first scenario for PDF generation
        primary_scenario = scenarios[0] if scenarios else None
        if not primary_scenario:
            raise ValueError("No scenarios available for PDF generation")
            
        pdf_content = PDFService.create_pdf_with_cashflow(
            client=client,
            scenario=primary_scenario,
            cashflow_data=cashflow_data,
            yearly_totals=yearly_totals,
            chart_cashflow=chart_cashflow,
            sections=request.sections,
            date_range=f"{request.from_} - {request.to}"
        )
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        pdf_size = len(pdf_content)
        _logger.info(f"PDF report completed in {duration:.2f}s, size={pdf_size} bytes")
        
        return pdf_content
        
    except ValueError as e:
        # Specific validation errors - log and re-raise
        _logger.error(f"PDF generation validation error: {e}")
        raise
    except Exception as e:
        # Log detailed error with traceback
        import traceback
        _logger.error(f"Unexpected error in PDF generation:\n{traceback.format_exc()}")
        _logger.error(f"Error details: {e}")
        # Safer to re-raise as ValueError for API consistency
        raise ValueError(f"Internal PDF generation error: {e}")
