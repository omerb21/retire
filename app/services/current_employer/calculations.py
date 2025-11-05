"""
Current Employer Calculations Module
מודול חישובים למעסיק נוכחי
"""
from typing import List, Dict, Any, Optional
from datetime import date
from decimal import Decimal
from app.schemas.current_employer import GrantCalculationResult


class ServiceYearsCalculator:
    """מחשבון שנות ותק"""
    
    @staticmethod
    def calculate(
        start_date: date, 
        end_date: Optional[date] = None, 
        non_continuous_periods: Optional[List[Dict[str, Any]]] = None,
        continuity_years: float = 0.0
    ) -> float:
        """
        חישוב שנות ותק עם ניכוי תקופות אי-רציפות והוספת שנות רציפות
        
        Args:
            start_date: תאריך התחלת עבודה
            end_date: תאריך סיום עבודה (None = היום)
            non_continuous_periods: רשימת תקופות לניכוי
            continuity_years: שנות רציפות נוספות (ברירת מחדל 0.0)
            
        Returns:
            שנות ותק כ-float
        """
        if end_date is None:
            end_date = date.today()
        
        # חישוב תקופת העסקה הכוללת בימים
        total_days = (end_date - start_date).days
        
        # ניכוי תקופות אי-רציפות
        deduction_days = 0
        if non_continuous_periods:
            for p in non_continuous_periods:
                # תמיכה בשני מפתחות: start/end או start_date/end_date
                s = p.get("start") or p.get("start_date")
                e = p.get("end") or p.get("end_date")
                if not s or not e:
                    continue
                
                # פרסור בטוח של תאריכים - דילוג על תאריכים לא תקינים
                try:
                    s = date.fromisoformat(s) if isinstance(s, str) else s
                    e = date.fromisoformat(e) if isinstance(e, str) else e
                    if s and e and e > s:
                        deduction_days += (e - s).days
                except (ValueError, TypeError):
                    # דילוג על תקופות תאריך לא תקינות
                    continue
        
        # המרה לשנים (365.25 ימים לשנה כדי לקחת בחשבון שנים מעוברות)
        years = max(0.0, (total_days - deduction_days) / 365.25)
        
        # המרה בטוחה ל-float עבור continuity_years
        try:
            cont = float(continuity_years) if continuity_years is not None else 0.0
        except (ValueError, TypeError):
            cont = 0.0
        
        return round(years + cont, 2)


class SeveranceCalculator:
    """מחשבון פיצויי פיטורין"""
    
    @staticmethod
    def calculate_severance_amount(
        last_salary: float,
        service_years: float
    ) -> float:
        """
        חישוב סכום פיצויי פיטורין
        
        Args:
            last_salary: משכורת אחרונה
            service_years: שנות ותק
            
        Returns:
            סכום פיצויים
        """
        return last_salary * service_years
    
    @staticmethod
    def calculate_exempt_and_taxable(
        severance_amount: float,
        service_years: float,
        exemption_cap_per_year: float = 13750.0
    ) -> Dict[str, float]:
        """
        חישוב חלוקה לפטור וחייב במס
        
        Args:
            severance_amount: סכום הפיצויים הכולל
            service_years: שנות ותק
            exemption_cap_per_year: תקרת פטור שנתית (ברירת מחדל 13,750)
            
        Returns:
            מילון עם exempt_amount ו-taxable_amount
        """
        # תקרת הפטור: תקרה שנתית * שנות ותק
        exempt_cap = exemption_cap_per_year * service_years
        exempt_amount = min(severance_amount, exempt_cap)
        
        # הסכום החייב הוא היתרה
        taxable_amount = max(0, severance_amount - exempt_amount)
        
        return {
            "exempt_amount": round(exempt_amount, 2),
            "taxable_amount": round(taxable_amount, 2),
            "exempt_cap": round(exempt_cap, 2)
        }


class GrantCalculator:
    """
    מחשבון מענקים
    
    DEPRECATED: פונקציה זו שומרת לתאימות לאחור בלבד.
    יש להשתמש ב-CurrentEmployerService.calculate_severance_grant() במקום,
    שמשתמש בנתוני מס אמיתיים מ-TaxDataService.
    """
    
    @staticmethod
    def calculate_grant(
        grant_amount: Decimal,
        service_years: float,
        last_salary: float,
        base_cap: float = 100000.0,
        index_factor: float = 1.0
    ) -> GrantCalculationResult:
        """
        חישוב מענק עם הצמדה ופירוק מס
        
        DEPRECATED: השתמש ב-CurrentEmployerService.calculate_severance_grant()
        
        Args:
            grant_amount: סכום המענק
            service_years: שנות ותק
            last_salary: משכורת אחרונה
            base_cap: תקרת פטור בסיסית (deprecated)
            index_factor: מקדם הצמדה (deprecated)
            
        Returns:
            GrantCalculationResult עם פרטי החישוב
        """
        # NOTE: חישוב זה משתמש בקבועים ישנים ולא מדויק
        # לחישוב מדויק, השתמש ב-CurrentEmployerService.calculate_severance_grant()
        indexed_amount = float(grant_amount)
        
        # חישוב תקרת פטור לפיצויים (לא מדויק - משתמש בקבועים ישנים)
        severance_exemption_cap = service_years * last_salary * base_cap * index_factor
        
        # חישוב חלקים פטורים וחייבים
        grant_exempt = min(indexed_amount, severance_exemption_cap)
        grant_taxable = max(0, indexed_amount - grant_exempt)
        
        # חישוב מס פשוט (לא מדויק - לא משתמש במדרגות מס אמיתיות)
        tax_rate = 0.25  # שיעור מס זמני
        tax_due = grant_taxable * tax_rate
        
        return GrantCalculationResult(
            grant_exempt=grant_exempt,
            grant_taxable=grant_taxable,
            tax_due=tax_due,
            indexed_amount=indexed_amount,
            service_years=service_years,
            severance_exemption_cap=severance_exemption_cap
        )
