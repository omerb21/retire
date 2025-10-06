"""
מחשבון מס הכנסה מקיף לישראל
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from .tax_constants import TaxConstants, TaxBracket, TaxCredit
from ..schemas.tax_schemas import (
    TaxCalculationInput, TaxCalculationResult, TaxBreakdown,
    TaxCreditInput, MonthlyTaxProjection, AnnualTaxProjection,
    TaxOptimizationSuggestion, ComprehensiveTaxAnalysis
)

logger = logging.getLogger(__name__)

class TaxCalculator:
    """מחשבון מס הכנסה מקיף"""
    
    def __init__(self, tax_year: int = None):
        """
        אתחול מחשבון המס
        
        Args:
            tax_year: שנת המס (ברירת מחדל: השנה הנוכחית)
        """
        self.tax_year = tax_year or date.today().year
        self.tax_brackets = TaxConstants.get_tax_brackets(self.tax_year)
        self.national_insurance = TaxConstants.get_national_insurance_rates(self.tax_year)
        self.health_tax = TaxConstants.get_health_tax_rates(self.tax_year)
        self.available_credits = TaxConstants.get_tax_credits(self.tax_year)
        self.pension_exemptions = TaxConstants.get_pension_exemptions()
        
        logger.info(f"אותחל מחשבון מס לשנת {self.tax_year}")
    
    def calculate_income_tax(self, taxable_income: float) -> Tuple[float, List[TaxBreakdown]]:
        """
        מחשב מס הכנסה לפי מדרגות המס
        
        Args:
            taxable_income: הכנסה חייבת במס
            
        Returns:
            Tuple של (סך המס, פירוט לפי מדרגות)
        """
        if taxable_income <= 0:
            return 0.0, []
        
        total_tax = 0.0
        breakdown = []
        remaining_income = taxable_income
        
        for bracket in self.tax_brackets:
            if remaining_income <= 0:
                break
            
            # חישוב הסכום החייב במדרגה הנוכחית
            bracket_size = (
                bracket.max_income - bracket.min_income 
                if bracket.max_income 
                else float('inf')
            )
            
            # הסכום שיחויב במדרגה זו
            taxable_in_bracket = min(remaining_income, bracket_size)
            
            if taxable_in_bracket > 0:
                tax_in_bracket = taxable_in_bracket * bracket.rate
                total_tax += tax_in_bracket
                
                breakdown.append(TaxBreakdown(
                    bracket_min=bracket.min_income,
                    bracket_max=bracket.max_income,
                    rate=bracket.rate,
                    taxable_amount=taxable_in_bracket,
                    tax_amount=tax_in_bracket
                ))
                
                remaining_income -= taxable_in_bracket
        
        return round(total_tax, 2), breakdown
    
    def calculate_national_insurance(self, annual_income: float) -> float:
        """
        מחשב ביטוח לאומי
        
        Args:
            annual_income: הכנסה שנתית
            
        Returns:
            סכום ביטוח לאומי שנתי
        """
        if annual_income <= 0:
            return 0.0
        
        monthly_income = annual_income / 12
        ni_rates = self.national_insurance
        
        if monthly_income <= ni_rates['low_threshold_monthly']:
            # עד התקרה הנמוכה
            monthly_ni = monthly_income * ni_rates['employee_rate_low']
        else:
            # מעל התקרה הנמוכה
            low_part = ni_rates['low_threshold_monthly'] * ni_rates['employee_rate_low']
            high_part = min(
                monthly_income - ni_rates['low_threshold_monthly'],
                ni_rates['high_threshold_monthly'] - ni_rates['low_threshold_monthly']
            ) * ni_rates['employee_rate_high']
            monthly_ni = low_part + high_part
        
        # הגבלה לתשלום מקסימלי
        monthly_ni = min(monthly_ni, ni_rates['max_monthly_payment'])
        
        return round(monthly_ni * 12, 2)
    
    def calculate_health_tax(self, annual_income: float) -> float:
        """
        מחשב מס בריאות
        
        Args:
            annual_income: הכנסה שנתית
            
        Returns:
            סכום מס בריאות שנתי
        """
        if annual_income <= 0:
            return 0.0
        
        monthly_income = annual_income / 12
        health_rates = self.health_tax
        
        if monthly_income <= health_rates['low_threshold_monthly']:
            # עד התקרה הנמוכה
            monthly_health = monthly_income * health_rates['rate_low']
        else:
            # מעל התקרה הנמוכה
            low_part = health_rates['low_threshold_monthly'] * health_rates['rate_low']
            high_part = min(
                monthly_income - health_rates['low_threshold_monthly'],
                health_rates['high_threshold_monthly'] - health_rates['low_threshold_monthly']
            ) * health_rates['rate_high']
            monthly_health = low_part + high_part
        
        # הגבלה לתשלום מקסימלי
        monthly_health = min(monthly_health, health_rates['max_monthly_payment'])
        
        return round(monthly_health * 12, 2)
    
    def calculate_applicable_credits(self, input_data: TaxCalculationInput) -> Tuple[float, List[TaxCreditInput]]:
        """
        מחשב את נקודות הזיכוי מהקלט בלבד - ללא חישובים אוטומטיים
        
        Args:
            input_data: נתוני הקלט
            
        Returns:
            Tuple של (סך הזיכויים, רשימת זיכויים שהוחלו)
        """
        applied_credits = []
        total_credits = 0.0
        
        # רק זיכויים שהוזנו ידנית מהקלט
        for credit in input_data.additional_tax_credits:
            applied_credits.append(credit)
            total_credits += credit.amount or 0
        
        return round(total_credits, 2), applied_credits
    
    def calculate_pension_exemptions(self, pension_income: float, personal_details) -> float:
        """
        מחשב פטורים ממס לפנסיונרים
        
        Args:
            pension_income: הכנסה מפנסיה
            personal_details: פרטים אישיים
            
        Returns:
            סכום הפטור ממס
        """
        if pension_income <= 0:
            return 0.0
        
        age = personal_details.get_age()
        exemptions = self.pension_exemptions
        
        total_exemption = 0.0
        
        # פטור בסיסי לפנסיונר
        if age >= exemptions['age_threshold']:
            total_exemption += exemptions['basic_exemption_monthly'] * 12
        
        # פטור נוסף לוחם משוחרר
        if personal_details.is_veteran:
            total_exemption += exemptions['veteran_exemption_monthly'] * 12
        
        # פטור נוסף לנכה
        if personal_details.is_disabled:
            total_exemption += exemptions['disability_exemption_monthly'] * 12
        
        # הפטור לא יכול להיות גדול מההכנסה מפנסיה
        return min(total_exemption, pension_income)
    
    def calculate_comprehensive_tax(self, input_data: TaxCalculationInput) -> TaxCalculationResult:
        """
        מחשב מס מקיף
        
        Args:
            input_data: נתוני הקלט
            
        Returns:
            תוצאת חישוב מס מקיפה
        """
        logger.info(f"מתחיל חישוב מס מקיף לשנת {input_data.tax_year}")
        
        # חישוב סך ההכנסה
        total_income = input_data.get_total_annual_income()
        
        # חישוב פטורים לפנסיה
        pension_exemption = self.calculate_pension_exemptions(
            input_data.pension_income, 
            input_data.personal_details
        )
        
        # חישוב ניכויים
        total_deductions = input_data.get_total_deductions()
        
        # הכנסה חייבת במס
        taxable_income = max(0, total_income - pension_exemption - total_deductions)
        exempt_income = total_income - taxable_income
        
        # חישוב מס הכנסה
        income_tax, tax_breakdown = self.calculate_income_tax(taxable_income)
        
        # חישוב ביטוח לאומי ומס בריאות
        national_insurance = self.calculate_national_insurance(total_income)
        health_tax = self.calculate_health_tax(total_income)
        
        # חישוב זיכויים
        tax_credits_amount, applied_credits = self.calculate_applicable_credits(input_data)
        
        # סך המסים לפני זיכויים
        total_tax_before_credits = income_tax + national_insurance + health_tax
        
        # מס נטו לתשלום (לא יכול להיות שלילי)
        net_tax = max(0, total_tax_before_credits - tax_credits_amount)
        
        # הכנסה נטו
        net_income = total_income - net_tax
        
        # שיעורי מס
        effective_tax_rate = (net_tax / total_income * 100) if total_income > 0 else 0
        
        # שיעור מס שולי (המדרגה הגבוהה ביותר שהופעלה)
        marginal_tax_rate = 0
        if tax_breakdown:
            marginal_tax_rate = tax_breakdown[-1].rate * 100
        
        result = TaxCalculationResult(
            total_income=round(total_income, 2),
            taxable_income=round(taxable_income, 2),
            exempt_income=round(exempt_income, 2),
            income_tax=round(income_tax, 2),
            national_insurance=round(national_insurance, 2),
            health_tax=round(health_tax, 2),
            total_tax=round(total_tax_before_credits, 2),
            tax_credits_amount=round(tax_credits_amount, 2),
            applied_credits=applied_credits,
            net_tax=round(net_tax, 2),
            net_income=round(net_income, 2),
            effective_tax_rate=round(effective_tax_rate, 2),
            marginal_tax_rate=round(marginal_tax_rate, 2),
            tax_breakdown=tax_breakdown,
            calculation_date=datetime.now(),
            tax_year=input_data.tax_year
        )
        
        logger.info(f"הושלם חישוב מס: הכנסה {total_income:,.2f}, מס נטו {net_tax:,.2f}")
        return result
    
    def generate_optimization_suggestions(self, input_data: TaxCalculationInput, 
                                        current_result: TaxCalculationResult) -> List[TaxOptimizationSuggestion]:
        """
        מייצר הצעות לאופטימיזציית מס
        
        Args:
            input_data: נתוני הקלט
            current_result: תוצאת החישוב הנוכחית
            
        Returns:
            רשימת הצעות אופטימיזציה
        """
        suggestions = []
        
        # הצעה להגדלת הפרשות לפנסיה
        if input_data.pension_contributions < input_data.salary_income * 0.07:
            max_contribution = input_data.salary_income * 0.07
            additional_contribution = max_contribution - input_data.pension_contributions
            potential_savings = additional_contribution * current_result.marginal_tax_rate / 100
            
            suggestions.append(TaxOptimizationSuggestion(
                suggestion_type="pension_contribution",
                description=f"הגדלת הפרשות לפנסיה ב-{additional_contribution:,.0f} ש\"ח",
                potential_savings=potential_savings,
                implementation_difficulty="קל"
            ))
        
        # הצעה לקרן השתלמות
        if input_data.study_fund_contributions == 0 and input_data.salary_income > 0:
            max_study_fund = min(input_data.salary_income * 0.075, 8500)  # מקסימום לשנת 2024
            potential_savings = max_study_fund * current_result.marginal_tax_rate / 100
            
            suggestions.append(TaxOptimizationSuggestion(
                suggestion_type="study_fund",
                description=f"פתיחת קרן השתלמות - הפרשה של {max_study_fund:,.0f} ש\"ח",
                potential_savings=potential_savings,
                implementation_difficulty="קל"
            ))
        
        # הצעה לתרומות
        if input_data.charitable_donations < input_data.get_total_annual_income() * 0.35:
            max_donation = input_data.get_total_annual_income() * 0.35
            suggested_donation = min(10000, max_donation)  # הצעה סבירה
            potential_savings = suggested_donation * current_result.marginal_tax_rate / 100
            
            suggestions.append(TaxOptimizationSuggestion(
                suggestion_type="charitable_donations",
                description=f"תרומות לעמותות מוכרות - {suggested_donation:,.0f} ש\"ח",
                potential_savings=potential_savings,
                implementation_difficulty="קל"
            ))
        
        return suggestions
