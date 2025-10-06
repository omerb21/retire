"""
CurrentEmployer service layer - Sprint 3
Business logic for current employer and grant calculations
"""
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models import CurrentEmployer, EmployerGrant, Client
from app.schemas.current_employer import (
    CurrentEmployerCreate, CurrentEmployerUpdate, EmployerGrantCreate,
    GrantCalculationResult
)

class CurrentEmployerService:
    """Service for current employer operations and calculations"""
    
    @staticmethod
    def calculate_service_years(
        start_date: date, 
        end_date: Optional[date] = None, 
        non_continuous_periods: Optional[List[Dict[str, Any]]] = None,
        continuity_years: float = 0.0
    ) -> float:
        """
        Calculate service years with deduction for non-continuous periods
        and addition of continuity years
        
        Args:
            start_date: Employment start date
            end_date: Employment end date (None = present)
            non_continuous_periods: List of periods to deduct
            continuity_years: Additional years to add for continuity (default 0.0)
            
        Returns:
            Service years as float
        """
        if end_date is None:
            end_date = date.today()
        
        # Calculate total employment period in days
        total_days = (end_date - start_date).days
        
        # Deduct non-continuous periods
        deduction_days = 0
        if non_continuous_periods:
            for p in non_continuous_periods:
                # Support both start/end and start_date/end_date keys
                s = p.get("start") or p.get("start_date")
                e = p.get("end") or p.get("end_date")
                if not s or not e:
                    continue
                
                # Safe date parsing - skip invalid dates
                try:
                    s = date.fromisoformat(s) if isinstance(s, str) else s
                    e = date.fromisoformat(e) if isinstance(e, str) else e
                    if s and e and e > s:
                        deduction_days += (e - s).days
                except (ValueError, TypeError):
                    # Skip invalid date periods
                    continue
        
        # Convert to years (365.25 days per year to account for leap years)
        years = max(0.0, (total_days - deduction_days) / 365.25)
        
        # Safe float conversion for continuity_years
        try:
            cont = float(continuity_years) if continuity_years is not None else 0.0
        except (ValueError, TypeError):
            cont = 0.0
        
        return round(years + cont, 2)
    
    @staticmethod
    def calculate_severance_grant(
        current_employer: CurrentEmployer, 
        grant: EmployerGrant
    ) -> GrantCalculationResult:
        """
        Calculate severance grant with indexing and tax breakdown
        
        Args:
            current_employer: CurrentEmployer instance
            grant: EmployerGrant instance
            
        Returns:
            GrantCalculationResult with calculation details
        """
        # Calculate service years
        service_years = CurrentEmployerService.calculate_service_years(
            current_employer.start_date,
            current_employer.end_date,
            current_employer.non_continuous_periods or [],
            getattr(current_employer, "continuity_years", 0.0)  # Guaranteed float
        )
        
        # TODO: Connect to CPI for proper indexing
        # For now, use stub that returns the same amount
        indexed_amount = grant.grant_amount
        
        # TODO: Connect to proper tax parameters
        # For now, use temporary constants
        base_cap = 100000.0  # Base exemption cap (temporary)
        index_factor = 1.0   # Index factor (temporary)
        
        # Calculate severance exemption cap
        last_salary = current_employer.last_salary or 0.0
        # If last_salary is 0, exemption cap is 0, making entire grant taxable
        severance_exemption_cap = service_years * last_salary * base_cap * index_factor
        
        # Calculate exempt and taxable portions
        grant_exempt = min(indexed_amount, severance_exemption_cap)
        grant_taxable = max(0, indexed_amount - grant_exempt)
        
        # TODO: Connect to tax brackets for proper tax calculation
        # For now, use stub tax calculation (25% on taxable portion)
        tax_rate = 0.25  # Temporary tax rate
        tax_due = grant_taxable * tax_rate
        
        return GrantCalculationResult(
            grant_exempt=grant_exempt,
            grant_taxable=grant_taxable,
            tax_due=tax_due,
            indexed_amount=indexed_amount,
            service_years=service_years,
            severance_exemption_cap=severance_exemption_cap
        )
    
    @staticmethod
    def create_current_employer(
        db: Session, 
        client_id: int, 
        employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """Create a new current employer for a client"""
        # Check if client exists
        client = db.get(Client, client_id)
        if not client:
            raise ValueError("לקוח לא נמצא")
        
        # Create current employer
        current_employer = CurrentEmployer(
            client_id=client_id,
            **employer_data.model_dump()
        )
        
        db.add(current_employer)
        db.commit()
        db.refresh(current_employer)
        
        return current_employer
    
    @staticmethod
    def update_current_employer(
        db: Session, 
        employer_id: int, 
        employer_data: CurrentEmployerUpdate
    ) -> Optional[CurrentEmployer]:
        """Update an existing current employer"""
        current_employer = db.get(CurrentEmployer, employer_id)
        if not current_employer:
            return None
        
        # Update only provided fields
        update_data = employer_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_employer, field, value)
        
        db.commit()
        db.refresh(current_employer)
        
        return current_employer
    
    @staticmethod
    def get_current_employer_by_client(
        db: Session, 
        client_id: int
    ) -> Optional[CurrentEmployer]:
        """Get current employer for a client"""
        return db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == client_id
        ).order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc()).first()
    
    @staticmethod
    def add_grant_to_employer(
        db: Session, 
        employer_id: int, 
        grant_data: EmployerGrantCreate
    ) -> tuple[EmployerGrant, GrantCalculationResult]:
        """Add a grant to current employer and calculate results"""
        # Get current employer
        current_employer = db.get(CurrentEmployer, employer_id)
        if not current_employer:
            raise ValueError("מעסיק נוכחי לא נמצא")
        
        # Create grant
        grant = EmployerGrant(
            employer_id=employer_id,
            **grant_data.model_dump()
        )
        
        # Calculate grant results
        calculation = CurrentEmployerService.calculate_severance_grant(
            current_employer, grant
        )
        
        # Update grant with calculated values
        grant.grant_exempt = calculation.grant_exempt
        grant.grant_taxable = calculation.grant_taxable
        grant.tax_due = calculation.tax_due
        grant.indexed_amount = calculation.indexed_amount
        
        # Update current employer with calculated values
        current_employer.indexed_severance = calculation.indexed_amount
        current_employer.severance_exemption_cap = calculation.severance_exemption_cap
        current_employer.severance_exempt = calculation.grant_exempt
        current_employer.severance_taxable = calculation.grant_taxable
        current_employer.severance_tax_due = calculation.tax_due
        
        db.add(grant)
        db.commit()
        db.refresh(grant)
        
        return grant, calculation
