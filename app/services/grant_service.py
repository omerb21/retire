"""
Grant service for handling grant operations and calculations
"""
from sqlalchemy.orm import Session
from app.models.grant import Grant
from app.schemas.grant import GrantCreate, GrantUpdate
from app.calculation.tax_calculation import calculate_grant_tax
from typing import Dict, Tuple, Any

class GrantService:
    @staticmethod
    def create_grant(db: Session, client_id: int, grant_data: GrantCreate) -> Tuple[Grant, Dict[str, float]]:
        """
        Create a new grant and calculate tax implications
        Returns the created grant and tax calculation results
        """
        # Create new grant
        grant = Grant(
            client_id=client_id,
            employer_name=grant_data.employer_name,
            work_start_date=grant_data.work_start_date,
            work_end_date=grant_data.work_end_date,
            grant_amount=grant_data.amount,
            grant_date=grant_data.grant_date
        )
        
        # Add to database to get ID
        db.add(grant)
        db.flush()
        
        # Calculate service years if not provided
        service_years = grant_data.service_years
        if not service_years and grant.work_start_date and grant.work_end_date:
            days = (grant.work_end_date - grant.work_start_date).days
            service_years = days / 365.25
        
        # Calculate tax implications
        calculation = GrantService.calculate_tax_implications(grant, service_years)
        
        # Update grant with calculation results
        grant.grant_indexed_amount = calculation.get("grant_exempt", 0) + calculation.get("grant_taxable", 0)
        grant.limited_indexed_amount = calculation.get("grant_exempt", 0)
        
        # Commit changes
        db.commit()
        db.refresh(grant)
        
        return grant, calculation
    
    @staticmethod
    def calculate_tax_implications(grant: Grant, service_years: float = None) -> Dict[str, float]:
        """
        Calculate tax implications for a grant
        Returns dictionary with grant_exempt, grant_taxable, and tax_due
        """
        # Default values
        calculation = {
            "grant_exempt": 0.0,
            "grant_taxable": 0.0,
            "tax_due": 0.0
        }
        
        # Use the tax_calculation module for accurate calculations
        from app.calculation.tax_calculation import calculate_grant_tax
        
        if service_years and service_years > 0:
            # For severance grants, use proper tax calculation
            tax_calc = calculate_grant_tax(
                amount=grant.grant_amount,
                service_years=service_years
            )
            calculation["grant_exempt"] = tax_calc["grant_exempt"]
            calculation["grant_taxable"] = tax_calc["grant_taxable"]
            calculation["tax_due"] = tax_calc["tax_due"]
        else:
            # For other grants, all amount is taxable
            tax_calc = calculate_grant_tax(
                amount=grant.grant_amount,
                service_years=None
            )
            calculation["grant_exempt"] = tax_calc["grant_exempt"]
            calculation["grant_taxable"] = tax_calc["grant_taxable"]
            calculation["tax_due"] = tax_calc["tax_due"]
        
        return calculation
    
    @staticmethod
    def update_grant(db: Session, grant_id: int, grant_data: GrantUpdate) -> Tuple[Grant, Dict[str, float]]:
        """
        Update an existing grant and recalculate tax implications
        Returns the updated grant and tax calculation results
        """
        # Get grant
        grant = db.query(Grant).filter(Grant.id == grant_id).first()
        if not grant:
            raise ValueError("מענק לא נמצא")
        
        # Update grant fields
        for key, value in grant_data.model_dump(exclude_unset=True).items():
            setattr(grant, key, value)
        
        # Recalculate tax implications
        calculation = GrantService.calculate_tax_implications(grant, grant_data.service_years)
        
        # Update grant with calculation results
        grant.grant_indexed_amount = calculation.get("grant_exempt", 0) + calculation.get("grant_taxable", 0)
        grant.limited_indexed_amount = calculation.get("grant_exempt", 0)
        
        # Commit changes
        db.commit()
        db.refresh(grant)
        
        return grant, calculation
