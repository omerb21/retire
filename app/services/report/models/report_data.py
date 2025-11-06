"""
Report data models for structured report information
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class ClientInfo(BaseModel):
    """Client information for report"""
    full_name: str
    id_number: str
    birth_date: str
    email: str
    phone: str
    address: str


class EmploymentInfo(BaseModel):
    """Employment information"""
    employer_name: str
    start_date: str
    end_date: str
    monthly_salary: str
    is_current: bool


class ScenarioSummary(BaseModel):
    """Scenario summary information"""
    id: int
    name: str
    created_at: str
    has_results: bool
    total_pension: Optional[Any] = None
    monthly_pension: Optional[Any] = None
    total_grants: Optional[Any] = None
    net_worth_at_retirement: Optional[Any] = None
    parse_error: bool = False


class CaseInfo(BaseModel):
    """Case detection information"""
    id: int
    name: str
    display_name: str
    reasons: List[str]


class ReportMetadata(BaseModel):
    """Report metadata"""
    generated_at: str
    scenarios_count: int
    client_is_active: bool


class SummaryData(BaseModel):
    """Complete summary data structure"""
    client_info: ClientInfo
    employment_info: List[EmploymentInfo]
    scenarios_summary: List[ScenarioSummary]
    cashflow_data: Dict[int, Any]
    report_metadata: ReportMetadata
    case: CaseInfo


class ReportData(BaseModel):
    """Main report data container"""
    client_id: int
    scenario_ids: List[int]
    summary: SummaryData
    cashflow_rows: List[Dict[str, Any]]
    yearly_totals: Dict[str, Dict[str, float]]
    date_range: str
    sections: Dict[str, bool]
