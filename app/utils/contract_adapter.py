"""
Contract adapter layer to standardize function signatures and API responses
"""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.schemas.report import ReportPdfRequest


class ReportServiceAdapter:
    """Adapter for report service to maintain stable API contract"""
    
    @staticmethod
    def normalize_pdf_request(
        scenario_id: Optional[int] = None,
        request: Optional[ReportPdfRequest] = None
    ) -> Dict[str, Any]:
        """
        Normalize PDF request inputs to canonical format
        
        Priority:
        1. scenario_id from path parameter
        2. scenario_ids from request body
        3. scenarios from request body (alternative name)
        
        Returns:
            Canonical payload with scenario_ids list
        """
        import logging
        logger = logging.getLogger(__name__)
        
        scenario_ids = []
        
        # Priority 1: scenario_id from path
        if scenario_id is not None:
            scenario_ids = [scenario_id]
            logger.info(f"Using scenario_id from path: {scenario_id}")
        
        # Priority 2: scenario_ids from request body
        elif request and hasattr(request, 'scenario_ids') and request.scenario_ids:
            scenario_ids = request.scenario_ids
            logger.info(f"Using scenario_ids from request body: {scenario_ids}")
        
        # Priority 3: scenarios from request body (alternative field)
        elif request and hasattr(request, 'scenarios') and request.scenarios:
            scenario_ids = request.scenarios
            logger.info(f"Using scenarios from request body: {scenario_ids}")
        
        if not scenario_ids:
            raise ValueError("No scenario id(s) provided")
        
        return {
            "scenario_ids": scenario_ids,
            "from": request.from_ if request else "2025-01",
            "to": request.to if request else "2025-12",
            "frequency": "monthly",
            "sections": request.sections if request and hasattr(request, 'sections') else {
                "summary": True,
                "cashflow_table": True,
                "net_chart": True,
                "scenarios_compare": True
            }
        }
    
    @staticmethod
    def generate_pdf_report(
        db: Session,
        client_id: int,
        scenario_id: int,
        request: ReportPdfRequest
    ) -> bytes:
        """
        Standardized PDF generation interface with input normalization
        
        Args:
            db: Database session
            client_id: Client ID
            scenario_id: Scenario ID from path
            request: Report request with date range and sections
            
        Returns:
            PDF as bytes
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Normalize inputs to canonical format
            normalized = ReportServiceAdapter.normalize_pdf_request(scenario_id, request)
            logger.info(f"Normalized PDF request: client_id={client_id}, scenario_ids={normalized['scenario_ids']}")
            
            from app.services.report_service import generate_report_pdf
            
            # Call service with normalized parameters
            return generate_report_pdf(
                db=db,
                client_id=client_id,
                scenario_id=normalized['scenario_ids'][0],  # Use first scenario for single-scenario PDF
                request=request
            )
            
        except ValueError as e:
            logger.error(f"PDF request validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"PDF generation adapter error: {e}")
            raise ValueError(f"PDF generation failed: {e}")


class CompareServiceAdapter:
    """Adapter for compare service to ensure consistent response format"""
    
    @staticmethod
    def compare_scenarios_for_api(
        db_session: Session,
        client_id: int,
        scenario_ids: List[int],
        from_yyyymm: str,
        to_yyyymm: str,
        frequency: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Standardized scenario comparison for API endpoints
        
        Returns:
            Consistent format with scenarios array containing scenario data
        """
        from app.services.compare_service import compare_scenarios
        
        # Get raw data from service
        data = compare_scenarios(
            db_session=db_session,
            client_id=client_id,
            scenario_ids=scenario_ids,
            from_yyyymm=from_yyyymm,
            to_yyyymm=to_yyyymm,
            frequency=frequency
        )
        
        # Convert to standardized API format
        scenarios_list = []
        for scenario_id, scenario_data in data.get("scenarios", {}).items():
            monthly_data = scenario_data.get("monthly", [])
            yearly_data = scenario_data.get("yearly", {})
            
            # Ensure yearly data exists even if empty
            if not yearly_data:
                yearly_data = {}
                
            # Ensure all years have all required fields with default 0
            for year in yearly_data:
                for field in ["inflow", "outflow", "additional_income_net", "capital_return_net", "net"]:
                    if field not in yearly_data[year]:
                        yearly_data[year][field] = 0.0
                        
                # Recalculate net from components using Decimal for precision
                from decimal import Decimal, ROUND_HALF_UP
                
                inflow = Decimal(str(yearly_data[year]["inflow"]))
                outflow = Decimal(str(yearly_data[year]["outflow"]))
                additional_income = Decimal(str(yearly_data[year]["additional_income_net"]))
                capital_return = Decimal(str(yearly_data[year]["capital_return_net"]))
                
                net_calculated = inflow - outflow + additional_income + capital_return
                yearly_data[year]["net"] = float(net_calculated.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                
                # Round all values to 2 decimal places using Decimal precision
                for field in yearly_data[year]:
                    value = Decimal(str(yearly_data[year][field]))
                    yearly_data[year][field] = float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            
            scenarios_list.append({
                "scenario_id": int(scenario_id),
                "monthly": monthly_data,
                "yearly_totals": yearly_data
            })
        
        return {
            "scenarios": scenarios_list,
            "meta": data.get("meta", {})
        }


class CaseDetectionAdapter:
    """Adapter for case detection to ensure consistent response format"""
    
    @staticmethod
    def detect_case_for_api(db_session: Session, client_id: int) -> Dict[str, Any]:
        """
        Standardized case detection for API endpoints
        
        Returns:
            Simple case detection response
        """
        try:
            from app.services.case_service import detect_case
            result = detect_case(db_session, client_id)
            return {
                "case": result.case_name if hasattr(result, 'case_name') else "standard",
                "case_id": result.case_id if hasattr(result, 'case_id') else 1
            }
        except Exception:
            # Fallback to standard case
            return {
                "case": "standard",
                "case_id": 1
            }
