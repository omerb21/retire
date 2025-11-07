"""
מחשבון מס הכנסה מקיף לישראל
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from .tax.constants import TaxConstants, TaxBracket, TaxCredit
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
    
    def calculate_income_tax(self, taxable_income: float, is_business_income: bool = False) -> Tuple[float, List[TaxBreakdown]]:
        """
        מחשב מס הכנסה לפי מדרגות המס
        
        Args:
            taxable_income: הכנסה חייבת במס
            is_business_income: לא בשימוש (נשמר לתאימות לאחור)
            
        Returns:
            Tuple של (סך המס, פירוט לפי מדרגות)
        """
        if taxable_income <= 0:
            return 0.0, []
        
        # חישוב מס הכנסה לפי מדרגות המס
        # אלגוריתם נכון: עוברים על המדרגות ומחשבים כמה מההכנסה נופלת בכל מדרגה
        total_tax = 0.0
        breakdown = []
        processed_income = 0.0  # כמה הכנסה כבר עיבדנו
        
        for bracket in self.tax_brackets:
            # אם עיבדנו את כל ההכנסה, נסיים
            if processed_income >= taxable_income:
                break
            
            # כמה הכנסה נופלת במדרגה הנוכחית
            if bracket.max_income:
                # מדרגה עם תקרה
                income_in_bracket = min(
                    taxable_income - processed_income,  # ההכנסה שנותרה
                    bracket.max_income - processed_income  # הגבול העליון של המדרגה פחות מה שכבר עיבדנו
                )
            else:
                # מדרגה אחרונה ללא תקרה
                income_in_bracket = taxable_income - processed_income
            
            if income_in_bracket > 0:
                tax_in_bracket = income_in_bracket * bracket.rate
                total_tax += tax_in_bracket
                
                breakdown.append(TaxBreakdown(
                    bracket_min=bracket.min_income,
                    bracket_max=bracket.max_income,
                    rate=bracket.rate,
                    taxable_amount=income_in_bracket,
                    tax_amount=tax_in_bracket
                ))
                
                processed_income += income_in_bracket
                
                logger.debug(f"Tax Bracket {bracket.min_income}-{bracket.max_income}: "
                           f"Income {income_in_bracket:.2f} at {bracket.rate*100}% = {tax_in_bracket:.2f}")
        
        logger.debug(f"Total Annual Tax: {total_tax:.2f} on income {taxable_income:.2f}")
        return round(total_tax, 2), breakdown
    
    def calculate_national_insurance(self, annual_income: float, personal_details=None) -> float:
        """
        מחשב ביטוח לאומי
        
        Args:
            annual_income: הכנסה שנתית
            personal_details: פרטים אישיים (לבדיקת גיל פרישה)
            
        Returns:
            סכום ביטוח לאומי שנתי
        """
        if annual_income <= 0:
            return 0.0
        
        # בדיקת גיל פרישה - ביטוח לאומי לא חל אחרי גיל פרישה
        if personal_details and personal_details.get_age() >= 67:
            logger.info(f"ביטוח לאומי לא חל - מעל גיל פרישה ({personal_details.get_age()})")
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
    
    def calculate_health_tax(self, annual_income: float, personal_details=None) -> float:
        """
        מחשב מס בריאות
        
        Args:
            annual_income: הכנסה שנתית
            personal_details: פרטים אישיים (לבדיקת גיל פרישה)
            
        Returns:
            סכום מס בריאות שנתי
        """
        if annual_income <= 0:
            return 0.0
        
        # בדיקת גיל פרישה - מס בריאות מופחת אחרי גיל פרישה
        # לפנסיונרים מעל גיל 67 יש שיעור מופחת
        if personal_details and personal_details.get_age() >= 67:
            logger.info(f"מס בריאות מופחת - מעל גיל פרישה ({personal_details.get_age()})")
            # שיעור מופחת לפנסיונרים: 3.1% על כל ההכנסה
            monthly_income = annual_income / 12
            monthly_health = monthly_income * 0.031  # 3.1% קבוע לפנסיונרים
            return round(monthly_health * 12, 2)
        
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
        מחשב מס מקיף - עם טיפול נכון בסוגי הכנסות שונים
        
        Args:
            input_data: נתוני הקלט
            
        Returns:
            תוצאת חישוב מס מקיפה
        """
        logger.info(f"מתחיל חישוב מס מקיף לשנת {input_data.tax_year}")
        
        from ..schemas.tax_schemas import IncomeTypeBreakdown
        
        # 1. חישוב סך ההכנסה הכוללת
        total_income = input_data.get_total_annual_income()
        
        # 2. חישוב מסים מיוחדים לסוגי הכנסות שונים
        special_tax_incomes = input_data.get_special_tax_incomes()
        special_taxes = {}
        income_breakdown = []
        total_special_tax = 0.0
        
        # מס שכירות - 10% קבוע
        if special_tax_incomes['rental_income'] > 0:
            rental_tax = special_tax_incomes['rental_income'] * TaxConstants.SPECIAL_TAX_RATES['rental_income']
            special_taxes['rental_income'] = rental_tax
            total_special_tax += rental_tax
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="הכנסה משכירות",
                amount=special_tax_incomes['rental_income'],
                tax_rate=0.10,
                tax_amount=rental_tax,
                is_included_in_taxable=False,
                description="מס קבוע 10%"
            ))
            logger.info(f"מס שכירות: {rental_tax:,.2f} על {special_tax_incomes['rental_income']:,.2f}")
        
        # מס רווח הון - 25%
        if special_tax_incomes['capital_gains'] > 0:
            capital_gains_tax = special_tax_incomes['capital_gains'] * TaxConstants.SPECIAL_TAX_RATES['capital_gains']
            special_taxes['capital_gains'] = capital_gains_tax
            total_special_tax += capital_gains_tax
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="רווח הון",
                amount=special_tax_incomes['capital_gains'],
                tax_rate=0.25,
                tax_amount=capital_gains_tax,
                is_included_in_taxable=False,
                description="מס רווח הון 25%"
            ))
            logger.info(f"מס רווח הון: {capital_gains_tax:,.2f} על {special_tax_incomes['capital_gains']:,.2f}")
        
        # מס דיבידנד - 25%
        if special_tax_incomes['dividend_income'] > 0:
            dividend_tax = special_tax_incomes['dividend_income'] * TaxConstants.SPECIAL_TAX_RATES['dividend_income']
            special_taxes['dividend_income'] = dividend_tax
            total_special_tax += dividend_tax
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="הכנסה מדיבידנד",
                amount=special_tax_incomes['dividend_income'],
                tax_rate=0.25,
                tax_amount=dividend_tax,
                is_included_in_taxable=False,
                description="מס דיבידנד 25%"
            ))
            logger.info(f"מס דיבידנד: {dividend_tax:,.2f} על {special_tax_incomes['dividend_income']:,.2f}")
        
        # מס ריבית - 15%
        if special_tax_incomes['interest_income'] > 0:
            interest_tax = special_tax_incomes['interest_income'] * TaxConstants.SPECIAL_TAX_RATES['interest_income']
            special_taxes['interest_income'] = interest_tax
            total_special_tax += interest_tax
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="הכנסה מריבית",
                amount=special_tax_incomes['interest_income'],
                tax_rate=0.15,
                tax_amount=interest_tax,
                is_included_in_taxable=False,
                description="מס ריבית 15%"
            ))
            logger.info(f"מס ריבית: {interest_tax:,.2f} על {special_tax_incomes['interest_income']:,.2f}")
        
        # 3. חישוב הכנסה חייבת במס רגיל (ללא מסים מיוחדים)
        # תיקון: התאמת הכנסת הקצבה למספר חודשים בשנה
        adjusted_pension_income = input_data.pension_income
        if input_data.pension_months_in_year < 12:
            # אם הקצבה התחילה באמצע השנה, נתאים את הסכום השנתי
            monthly_pension = input_data.pension_income / 12
            adjusted_pension_income = monthly_pension * input_data.pension_months_in_year
            logger.info(f"התאמת הכנסת קצבה: {input_data.pension_income:,.2f} -> {adjusted_pension_income:,.2f} ({input_data.pension_months_in_year} חודשים)")
        
        regular_taxable_income = (
            input_data.salary_income +
            adjusted_pension_income +
            input_data.business_income +
            input_data.other_income +
            sum(source.annual_amount for source in input_data.income_sources if source.is_taxable)
        )
        
        # הוספת פירוט הכנסות רגילות
        if input_data.salary_income > 0:
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="שכר עבודה",
                amount=input_data.salary_income,
                tax_rate=None,
                tax_amount=0,
                is_included_in_taxable=True,
                description="חייב במס רגיל"
            ))
        
        if adjusted_pension_income > 0:
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="פנסיה",
                amount=adjusted_pension_income,
                tax_rate=None,
                tax_amount=0,
                is_included_in_taxable=True,
                description=f"חייב במס רגיל (עם פטורים) - {input_data.pension_months_in_year} חודשים"
            ))
        
        if input_data.business_income > 0:
            income_breakdown.append(IncomeTypeBreakdown(
                income_type="הכנסה עצמאית",
                amount=input_data.business_income,
                tax_rate=None,
                tax_amount=0,
                is_included_in_taxable=True,
                description="חייב במס רגיל"
            ))
        
        # 4. חישוב פטורים לפנסיה
        # תיקון: שילוב פטור מקיבוע זכויות + פטור רגיל
        pension_exemption_regular = self.calculate_pension_exemptions(
            adjusted_pension_income, 
            input_data.personal_details
        )
        
        # הוספת קצבה פטורה מקיבוע זכויות (התאמה למספר חודשים)
        exempt_pension_annual = input_data.exempt_pension_amount * input_data.pension_months_in_year
        
        # סך הפטורים מקצבה
        pension_exemption = pension_exemption_regular + exempt_pension_annual
        
        logger.info(f"פטורי פנסיה: רגיל={pension_exemption_regular:,.2f}, מקיבוע זכויות={exempt_pension_annual:,.2f}, סה\"כ={pension_exemption:,.2f}")
        
        # 5. חישוב ניכויים
        total_deductions = input_data.get_total_deductions()
        
        # 6. הכנסה חייבת במס רגיל (לאחר פטורים וניכויים)
        taxable_income = max(0, regular_taxable_income - pension_exemption - total_deductions)
        
        # 7. חישוב מס הכנסה - מפרידים בין הכנסה מעסק להכנסה רגילה
        business_income = input_data.business_income
        other_income = taxable_income - business_income if taxable_income > business_income else 0
        
        # חישוב מס על הכנסה מעסק
        business_tax, business_breakdown = self.calculate_income_tax(business_income, is_business_income=True)
        
        # חישוב מס על שאר ההכנסות
        other_tax, other_breakdown = self.calculate_income_tax(other_income, is_business_income=False)
        
        # איחוד התוצאות
        income_tax = business_tax + other_tax
        tax_breakdown = business_breakdown + other_breakdown
        
        # 8. חישוב ביטוח לאומי ומס בריאות (רק על הכנסה רגילה, עם בדיקת גיל)
        national_insurance = self.calculate_national_insurance(regular_taxable_income, input_data.personal_details)
        health_tax = self.calculate_health_tax(regular_taxable_income, input_data.personal_details)
        
        # 9. חישוב זיכויים
        tax_credits_amount, applied_credits = self.calculate_applicable_credits(input_data)
        
        # 10. סך המסים
        total_tax_before_credits = income_tax + national_insurance + health_tax + total_special_tax
        
        # 11. מס נטו לתשלום
        net_tax = max(0, total_tax_before_credits - tax_credits_amount)
        
        # 12. הכנסה נטו
        net_income = total_income - net_tax
        
        # 13. הכנסה פטורה
        # הכנסות עם מס מיוחד אינן נחשבות "פטורות" אלא ממוסות בנפרד
        exempt_income = pension_exemption
        
        # 14. שיעורי מס
        effective_tax_rate = (net_tax / total_income * 100) if total_income > 0 else 0
        marginal_tax_rate = tax_breakdown[-1].rate * 100 if tax_breakdown else 0
        
        result = TaxCalculationResult(
            total_income=round(total_income, 2),
            taxable_income=round(taxable_income, 2),
            exempt_income=round(exempt_income, 2),
            income_tax=round(income_tax, 2),
            national_insurance=round(national_insurance, 2),
            health_tax=round(health_tax, 2),
            special_taxes=special_taxes,
            total_tax=round(total_tax_before_credits, 2),
            tax_credits_amount=round(tax_credits_amount, 2),
            applied_credits=applied_credits,
            net_tax=round(net_tax, 2),
            net_income=round(net_income, 2),
            effective_tax_rate=round(effective_tax_rate, 2),
            marginal_tax_rate=round(marginal_tax_rate, 2),
            tax_breakdown=tax_breakdown,
            income_breakdown=income_breakdown,
            calculation_date=datetime.now(),
            tax_year=input_data.tax_year
        )
        
        logger.info(f"הושלם חישוב מס: הכנסה {total_income:,.2f}, מס נטו {net_tax:,.2f}")
        logger.info(f"פירוט: מס הכנסה={income_tax:,.2f}, בל={national_insurance:,.2f}, בריאות={health_tax:,.2f}, מיוחדים={total_special_tax:,.2f}")
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
