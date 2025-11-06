"""
Data service for report generation - handles data retrieval and processing
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.models import Client, Scenario, Employment, Employer
from app.services.case_service import detect_case

_logger = logging.getLogger(__name__)


class DataService:
    """Service for retrieving and processing report data"""
    
    @staticmethod
    def build_summary_table(client: Client, scenarios: List[Scenario], db: Session) -> Dict[str, Any]:
        """
        Build summary table data for the PDF report.
        
        Args:
            client: Client object
            scenarios: List of scenario objects
            db: Database session
            
        Returns:
            Dictionary with summary data organized by sections
        """
        # Detect case for client
        try:
            case_detection = detect_case(db, client.id)
            case_id = case_detection.case_id
            case_name = case_detection.case_name if hasattr(case_detection, 'case_name') else "standard"
            case_display_name = case_detection.display_name if hasattr(case_detection, 'display_name') else "מקרה רגיל"
            case_reasons = case_detection.reasons if hasattr(case_detection, 'reasons') else []
        except Exception as e:
            _logger.warning(f"Case detection failed for client {client.id}: {e}")
            case_id = 1
            case_name = "standard"
            case_display_name = "מקרה רגיל"
            case_reasons = ["זיהוי אוטומטי נכשל"]
        
        summary = {
            'client_info': {
                'full_name': client.full_name or 'N/A',
                'id_number': client.id_number or 'N/A',
                'birth_date': client.birth_date.strftime('%d/%m/%Y') if client.birth_date else 'N/A',
                'email': client.email or 'N/A',
                'phone': client.phone or 'N/A',
                'address': f"{client.address_street or ''}, {client.address_city or ''}".strip(', ') or 'N/A'
            },
            'employment_info': [],
            'scenarios_summary': [],
            'cashflow_data': {},
            'report_metadata': {
                'generated_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'scenarios_count': len(scenarios),
                'client_is_active': client.is_active
            },
            'case': {
                'id': case_id,
                'name': case_name,
                'display_name': case_display_name,
                'reasons': case_reasons
            }
        }
        
        # Get employment information
        try:
            employments = db.query(Employment).filter(
                Employment.client_id == client.id
            ).order_by(Employment.start_date.desc()).all()
            
            for emp in employments:
                employer = db.query(Employer).filter(Employer.id == emp.employer_id).first()
                emp_info = {
                    'employer_name': employer.name if employer else 'N/A',
                    'start_date': emp.start_date.strftime('%d/%m/%Y') if emp.start_date else 'N/A',
                    'end_date': emp.end_date.strftime('%d/%m/%Y') if emp.end_date else 'פעיל',
                    'monthly_salary': f"{emp.monthly_salary_nominal:,.0f} ₪" if emp.monthly_salary_nominal else 'N/A',
                    'is_current': emp.is_current
                }
                summary['employment_info'].append(emp_info)
        except Exception as e:
            _logger.error(f"Error fetching employment data: {e}")
            summary['employment_info'] = [{'error': 'שגיאה בטעינת נתוני תעסוקה'}]
        
        # Process scenarios
        for scenario in scenarios:
            scenario_summary = {
                'id': scenario.id,
                'name': f"תרחיש {scenario.id}",
                'created_at': scenario.created_at.strftime('%d/%m/%Y') if scenario.created_at else 'N/A',
                'has_results': bool(scenario.summary_results and scenario.cashflow_projection)
            }
            
            # Parse summary results if available
            if scenario.summary_results:
                try:
                    results = json.loads(scenario.summary_results) if isinstance(scenario.summary_results, str) else scenario.summary_results
                    scenario_summary.update({
                        'total_pension': results.get('total_pension_at_retirement', 'N/A'),
                        'monthly_pension': results.get('monthly_pension', 'N/A'),
                        'total_grants': results.get('total_grants', 'N/A'),
                        'net_worth_at_retirement': results.get('net_worth_at_retirement', 'N/A')
                    })
                except (json.JSONDecodeError, TypeError) as e:
                    _logger.error(f"Error parsing scenario {scenario.id} results: {e}")
                    scenario_summary['parse_error'] = True
            
            summary['scenarios_summary'].append(scenario_summary)
            
            # Store cashflow data for charts
            if scenario.cashflow_projection:
                try:
                    cashflow = json.loads(scenario.cashflow_projection) if isinstance(scenario.cashflow_projection, str) else scenario.cashflow_projection
                    summary['cashflow_data'][scenario.id] = cashflow
                except (json.JSONDecodeError, TypeError) as e:
                    _logger.error(f"Error parsing scenario {scenario.id} cashflow: {e}")
        
        return summary
