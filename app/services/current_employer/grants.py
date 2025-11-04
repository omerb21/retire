"""
Grants Service Module
מודול שירותי מענקים
"""
from typing import Tuple
from sqlalchemy.orm import Session
from app.models.current_employer import CurrentEmployer
from app.models.employer_grant import EmployerGrant
from app.schemas.current_employer import EmployerGrantCreate, GrantCalculationResult
from .calculations import ServiceYearsCalculator, GrantCalculator


class GrantService:
    """שירות ניהול מענקים"""
    
    def __init__(self, db: Session):
        """
        אתחול שירות מענקים
        
        Args:
            db: סשן מסד נתונים
        """
        self.db = db
        self.service_years_calc = ServiceYearsCalculator()
        self.grant_calc = GrantCalculator()
    
    def add_grant(
        self,
        employer: CurrentEmployer,
        grant_data: EmployerGrantCreate
    ) -> Tuple[EmployerGrant, GrantCalculationResult]:
        """
        הוספת מענק למעסיק וחישוב תוצאות
        
        Args:
            employer: מעסיק נוכחי
            grant_data: נתוני מענק
            
        Returns:
            tuple של (EmployerGrant, GrantCalculationResult)
            
        Raises:
            ValueError: אם המעסיק לא נמצא
        """
        if not employer:
            raise ValueError("מעסיק נוכחי לא נמצא")
        
        # יצירת מענק
        grant = EmployerGrant(
            employer_id=employer.id,
            **grant_data.model_dump()
        )
        
        # חישוב שנות ותק
        service_years = self.service_years_calc.calculate(
            employer.start_date,
            employer.end_date,
            employer.non_continuous_periods or [],
            getattr(employer, "continuity_years", 0.0)
        )
        
        # חישוב תוצאות מענק
        calculation = self.grant_calc.calculate_grant(
            grant_amount=grant.grant_amount,
            service_years=service_years,
            last_salary=employer.last_salary or 0.0
        )
        
        # עדכון מענק עם ערכים מחושבים
        grant.grant_exempt = calculation.grant_exempt
        grant.grant_taxable = calculation.grant_taxable
        grant.tax_due = calculation.tax_due
        grant.indexed_amount = calculation.indexed_amount
        
        # עדכון מעסיק נוכחי עם ערכים מחושבים
        employer.indexed_severance = calculation.indexed_amount
        employer.severance_exemption_cap = calculation.severance_exemption_cap
        employer.severance_exempt = calculation.grant_exempt
        employer.severance_taxable = calculation.grant_taxable
        employer.severance_tax_due = calculation.tax_due
        
        self.db.add(grant)
        self.db.commit()
        self.db.refresh(grant)
        
        return grant, calculation
    
    def delete_grants_by_employer(
        self,
        employer: CurrentEmployer,
        grant_type: str = None
    ) -> int:
        """
        מחיקת מענקים לפי מעסיק
        
        Args:
            employer: מעסיק נוכחי
            grant_type: סוג מענק (אופציונלי)
            
        Returns:
            מספר מענקים שנמחקו
        """
        from app.models.employer_grant import EmployerGrant, GrantType
        
        query = self.db.query(EmployerGrant).filter(
            EmployerGrant.employer_id == employer.id
        )
        
        if grant_type:
            query = query.filter(EmployerGrant.grant_type == grant_type)
        
        grants = query.all()
        count = len(grants)
        
        for grant in grants:
            self.db.delete(grant)
        
        self.db.flush()
        return count
