"""
PDF Report generation routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db.session import get_db
from models.client import Client
from models.scenario import Scenario
from models.scenario_cashflow import ScenarioCashflow
from utils.pdf_builder import build_pdf
from utils.logging_decorators import log_calculation
from typing import Dict, Any, List
import tempfile
import os
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

@log_calculation
def prepare_report_context(client: Client, scenario: Scenario, db: Session) -> Dict[str, Any]:
    """
    Prepare context data for PDF report generation
    """
    
    # Basic client and scenario info
    context = {
        'client': client,
        'scenario': scenario,
        'retirement_age': scenario.parameters.get('retirement_age', 67),
        'life_expectancy': scenario.parameters.get('life_expectancy', 85),
        'indexation_rate': scenario.parameters.get('indexation_rate', 0.02)
    }
    
    # Pension calculation details
    pension_calc = scenario.parameters.get('pension_calculation', {})
    context['pension_calculation'] = {
        'total_capital': pension_calc.get('total_capital', 0),
        'reservation_impact': pension_calc.get('reservation_impact', 0),
        'effective_capital': pension_calc.get('effective_capital', 0),
        'years_in_retirement': context['life_expectancy'] - context['retirement_age'],
        'annual_pension': pension_calc.get('annual_pension', 0),
        'monthly_pension': pension_calc.get('annual_pension', 0) / 12
    }
    
    # Processed grants
    grants = scenario.parameters.get('processed_grants', [])
    context['processed_grants'] = grants
    
    # Tax parameters
    context['tax_parameters'] = {
        'brackets': [
            {'min': 0, 'max': 75960, 'rate': 0.10},
            {'min': 75960, 'max': 108960, 'rate': 0.14},
            {'min': 108960, 'max': 174960, 'rate': 0.20},
            {'min': 174960, 'max': 243120, 'rate': 0.31},
            {'min': 243120, 'max': 504360, 'rate': 0.35},
            {'min': 504360, 'max': 663240, 'rate': 0.47},
            {'min': 663240, 'max': None, 'rate': 0.50}
        ]
    }
    
    return context

@log_calculation
def prepare_cashflow_data(scenario: Scenario, db: Session) -> List[Dict[str, Any]]:
    """
    Prepare cashflow data for PDF report
    """
    
    # Get cashflow records
    cashflow_records = db.query(ScenarioCashflow).filter(
        ScenarioCashflow.scenario_id == scenario.id
    ).order_by(ScenarioCashflow.year).all()
    
    if not cashflow_records:
        return []
    
    # Convert to list of dictionaries
    cashflow_data = []
    for record in cashflow_records:
        cashflow_data.append({
            'year': record.year,
            'gross_income': float(record.gross_income or 0),
            'pension_income': float(record.pension_income or 0),
            'grant_income': float(record.grant_income or 0),
            'other_income': float(record.other_income or 0),
            'tax': float(record.tax or 0),
            'net_income': float(record.net_income or 0)
        })
    
    return cashflow_data

@router.post("/scenario/{scenario_id}/pdf")
async def generate_scenario_pdf_report(
    scenario_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate PDF report for a scenario
    """
    
    # Get scenario with client
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Get client
    client = db.query(Client).filter(Client.id == scenario.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    try:
        # Prepare report context
        context = prepare_report_context(client, scenario, db)
        
        # Prepare cashflow data
        cashflow_data = prepare_cashflow_data(scenario, db)
        
        if not cashflow_data:
            raise HTTPException(
                status_code=400, 
                detail="No cashflow data available for this scenario. Please run the scenario first."
            )
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"retirement_report_{client.id}_{scenario_id}_{timestamp}.pdf"
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        # Build PDF
        build_pdf(context, cashflow_data, file_path)
        
        # Schedule cleanup after response
        background_tasks.add_task(cleanup_temp_file, file_path)
        
        # Return file response
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@router.post("/client/{client_id}/comprehensive-report")
async def generate_comprehensive_client_report(
    client_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive PDF report for all client scenarios
    """
    
    # Get client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get all completed scenarios for client
    scenarios = db.query(Scenario).filter(
        Scenario.client_id == client_id,
        Scenario.status == 'completed'
    ).all()
    
    if not scenarios:
        raise HTTPException(
            status_code=400,
            detail="No completed scenarios found for this client"
        )
    
    try:
        # Use the first scenario for main report (or could combine multiple)
        main_scenario = scenarios[0]
        
        # Prepare report context
        context = prepare_report_context(client, main_scenario, db)
        
        # Add comparison data if multiple scenarios
        if len(scenarios) > 1:
            context['scenario_comparison'] = []
            for scenario in scenarios:
                cashflow = prepare_cashflow_data(scenario, db)
                if cashflow:
                    total_net = sum(entry['net_income'] for entry in cashflow)
                    context['scenario_comparison'].append({
                        'scenario_name': scenario.name,
                        'total_net_income': total_net,
                        'years_covered': len(cashflow)
                    })
        
        # Prepare cashflow data
        cashflow_data = prepare_cashflow_data(main_scenario, db)
        
        if not cashflow_data:
            raise HTTPException(
                status_code=400,
                detail="No cashflow data available. Please run scenarios first."
            )
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comprehensive_report_{client_id}_{timestamp}.pdf"
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        # Build PDF
        build_pdf(context, cashflow_data, file_path)
        
        # Schedule cleanup after response
        background_tasks.add_task(cleanup_temp_file, file_path)
        
        # Return file response
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf',
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate comprehensive report: {str(e)}")

@router.get("/scenario/{scenario_id}/preview")
async def preview_scenario_report_data(
    scenario_id: int,
    db: Session = Depends(get_db)
):
    """
    Preview report data without generating PDF (for debugging/testing)
    """
    
    # Get scenario with client
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Get client
    client = db.query(Client).filter(Client.id == scenario.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    try:
        # Prepare report context
        context = prepare_report_context(client, scenario, db)
        
        # Prepare cashflow data
        cashflow_data = prepare_cashflow_data(scenario, db)
        
        # Return preview data
        return {
            "context": {
                "client_name": getattr(client, 'full_name', 'Unknown'),
                "scenario_name": scenario.name,
                "retirement_age": context['retirement_age'],
                "life_expectancy": context['life_expectancy'],
                "pension_calculation": context['pension_calculation'],
                "grants_count": len(context['processed_grants']),
                "tax_brackets_count": len(context['tax_parameters']['brackets'])
            },
            "cashflow_summary": {
                "years_count": len(cashflow_data),
                "total_gross_income": sum(entry['gross_income'] for entry in cashflow_data),
                "total_net_income": sum(entry['net_income'] for entry in cashflow_data),
                "total_tax": sum(entry['tax'] for entry in cashflow_data),
                "first_year": min(entry['year'] for entry in cashflow_data) if cashflow_data else None,
                "last_year": max(entry['year'] for entry in cashflow_data) if cashflow_data else None
            },
            "sample_cashflow": cashflow_data[:5] if cashflow_data else []  # First 5 years
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview report: {str(e)}")

def cleanup_temp_file(file_path: str):
    """
    Clean up temporary PDF file
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass  # Ignore cleanup errors
