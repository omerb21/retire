"""
מודלי נתונים לחישוב מס הכנסה
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal

class TaxCreditInput(BaseModel):
    """נקודת זיכוי במס"""
    code: str = Field(..., description="קוד הזיכוי")
    amount: Optional[float] = Field(None, description="סכום הזיכוי (אם שונה מברירת המחדל)")
    description: Optional[str] = Field(None, description="תיאור הזיכוי")
    
    class Config:
        json_encoders = {
            Decimal: float
        }

class IncomeSource(BaseModel):
    """מקור הכנסה"""
    source_type: str = Field(..., description="סוג ההכנסה")
    annual_amount: float = Field(..., ge=0, description="סכום שנתי")
    monthly_amount: Optional[float] = Field(None, ge=0, description="סכום חודשי")
    is_taxable: bool = Field(True, description="האם חייב במס")
    tax_exemption_amount: float = Field(0, ge=0, description="סכום פטור ממס")
    
    @validator('monthly_amount', always=True)
    def calculate_monthly_amount(cls, v, values):
        if v is None and 'annual_amount' in values:
            return values['annual_amount'] / 12
        return v

class PersonalDetails(BaseModel):
    """פרטים אישיים למטרות מס"""
    birth_date: Optional[date] = Field(None, description="תאריך לידה")
    marital_status: str = Field("single", description="מצב משפחתי")
    num_children: int = Field(0, ge=0, description="מספר ילדים")
    is_new_immigrant: bool = Field(False, description="עולה חדש")
    is_veteran: bool = Field(False, description="חייל משוחרר")
    is_disabled: bool = Field(False, description="נכה")
    disability_percentage: Optional[int] = Field(None, ge=0, le=100, description="אחוז נכות")
    is_student: bool = Field(False, description="סטודנט")
    reserve_duty_days: int = Field(0, ge=0, description="ימי מילואים בשנה")
    
    @validator('birth_date')
    def validate_birth_date(cls, v):
        if v and v > date.today():
            raise ValueError('תאריך לידה לא יכול להיות בעתיד')
        return v
    
    def get_age(self, reference_date: date = None) -> int:
        """מחשב גיל"""
        if not self.birth_date:
            return 0
        if reference_date is None:
            reference_date = date.today()
        return (reference_date - self.birth_date).days // 365

class TaxCalculationInput(BaseModel):
    """קלט לחישוב מס"""
    tax_year: int = Field(default_factory=lambda: date.today().year, description="שנת מס")
    personal_details: PersonalDetails = Field(..., description="פרטים אישיים")
    income_sources: List[IncomeSource] = Field(default_factory=list, description="מקורות הכנסה")
    additional_tax_credits: List[TaxCreditInput] = Field(default_factory=list, description="זיכויים נוספים")
    
    # הכנסות ספציפיות
    salary_income: float = Field(0, ge=0, description="הכנסה משכר")
    pension_income: float = Field(0, ge=0, description="הכנסה מפנסיה")
    rental_income: float = Field(0, ge=0, description="הכנסה משכירות")
    capital_gains: float = Field(0, ge=0, description="רווח הון")
    business_income: float = Field(0, ge=0, description="הכנסה עצמאית")
    interest_income: float = Field(0, ge=0, description="הכנסה מריבית")
    dividend_income: float = Field(0, ge=0, description="הכנסה מדיבידנדים")
    other_income: float = Field(0, ge=0, description="הכנסות אחרות")
    
    # ניכויים
    pension_contributions: float = Field(0, ge=0, description="הפרשות לפנסיה")
    study_fund_contributions: float = Field(0, ge=0, description="הפרשות לקרן השתלמות")
    insurance_premiums: float = Field(0, ge=0, description="דמי ביטוח")
    charitable_donations: float = Field(0, ge=0, description="תרומות")
    
    @validator('tax_year')
    def validate_tax_year(cls, v):
        current_year = date.today().year
        if v < 2020 or v > current_year + 2:
            raise ValueError(f'שנת מס חייבת להיות בין 2020 ל-{current_year + 2}')
        return v
    
    def get_total_annual_income(self) -> float:
        """מחשב סך ההכנסה השנתית"""
        return (
            self.salary_income +
            self.pension_income +
            self.rental_income +
            self.capital_gains +
            self.business_income +
            self.interest_income +
            self.dividend_income +
            self.other_income +
            sum(source.annual_amount for source in self.income_sources)
        )
    
    def get_total_deductions(self) -> float:
        """מחשב סך הניכויים"""
        return (
            self.pension_contributions +
            self.study_fund_contributions +
            self.insurance_premiums +
            self.charitable_donations
        )

class TaxBreakdown(BaseModel):
    """פירוט חישוב מס"""
    bracket_min: float = Field(..., description="תחילת מדרגה")
    bracket_max: Optional[float] = Field(None, description="סוף מדרגה")
    rate: float = Field(..., description="שיעור מס")
    taxable_amount: float = Field(..., description="סכום חייב במדרגה זו")
    tax_amount: float = Field(..., description="מס במדרגה זו")

class TaxCalculationResult(BaseModel):
    """תוצאת חישוב מס"""
    # הכנסות
    total_income: float = Field(..., description="סך ההכנסה")
    taxable_income: float = Field(..., description="הכנסה חייבת במס")
    exempt_income: float = Field(..., description="הכנסה פטורה ממס")
    
    # מסים
    income_tax: float = Field(..., description="מס הכנסה")
    national_insurance: float = Field(..., description="ביטוח לאומי")
    health_tax: float = Field(..., description="מס בריאות")
    total_tax: float = Field(..., description="סך המסים")
    
    # זיכויים
    tax_credits_amount: float = Field(..., description="סך נקודות הזיכוי")
    applied_credits: List[TaxCreditInput] = Field(default_factory=list, description="זיכויים שהוחלו")
    
    # תוצאה סופית
    net_tax: float = Field(..., description="מס נטו לתשלום")
    net_income: float = Field(..., description="הכנסה נטו")
    effective_tax_rate: float = Field(..., description="שיעור מס אפקטיבי")
    marginal_tax_rate: float = Field(..., description="שיעור מס שולי")
    
    # פירוט מדרגות
    tax_breakdown: List[TaxBreakdown] = Field(default_factory=list, description="פירוט מס לפי מדרגות")
    
    # מטא-דאטה
    calculation_date: datetime = Field(default_factory=datetime.now, description="תאריך החישוב")
    tax_year: int = Field(..., description="שנת המס")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: float
        }

class MonthlyTaxProjection(BaseModel):
    """תחזית מס חודשית"""
    month: int = Field(..., ge=1, le=12, description="חודש")
    year: int = Field(..., description="שנה")
    monthly_income: float = Field(..., description="הכנסה חודשית")
    monthly_tax: float = Field(..., description="מס חודשי")
    cumulative_income: float = Field(..., description="הכנסה מצטברת")
    cumulative_tax: float = Field(..., description="מס מצטבר")

class AnnualTaxProjection(BaseModel):
    """תחזית מס שנתית"""
    year: int = Field(..., description="שנה")
    projected_income: float = Field(..., description="הכנסה צפויה")
    projected_tax: float = Field(..., description="מס צפוי")
    monthly_projections: List[MonthlyTaxProjection] = Field(default_factory=list, description="תחזית חודשית")

class TaxOptimizationSuggestion(BaseModel):
    """הצעה לאופטימיזציית מס"""
    suggestion_type: str = Field(..., description="סוג ההצעה")
    description: str = Field(..., description="תיאור ההצעה")
    potential_savings: float = Field(..., description="חיסכון פוטנציאלי")
    implementation_difficulty: str = Field(..., description="רמת קושי ביישום")
    
class ComprehensiveTaxAnalysis(BaseModel):
    """ניתוח מס מקיף"""
    current_calculation: TaxCalculationResult = Field(..., description="חישוב נוכחי")
    annual_projections: List[AnnualTaxProjection] = Field(default_factory=list, description="תחזיות שנתיות")
    optimization_suggestions: List[TaxOptimizationSuggestion] = Field(default_factory=list, description="הצעות אופטימיזציה")
    comparison_scenarios: Dict[str, TaxCalculationResult] = Field(default_factory=dict, description="תרחישי השוואה")
