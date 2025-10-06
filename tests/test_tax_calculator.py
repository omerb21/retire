"""
בדיקות יחידה למודול חישוב המס
"""

import pytest
from datetime import date
from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails, IncomeSource

class TestTaxCalculator:
    """בדיקות למחשבון המס"""
    
    def setup_method(self):
        """הכנה לכל בדיקה"""
        self.calculator = TaxCalculator(2024)
    
    def test_basic_income_tax_calculation(self):
        """בדיקת חישוב מס הכנסה בסיסי"""
        # הכנסה של 100,000 ש"ח בשנה
        tax, breakdown = self.calculator.calculate_income_tax(100000)
        
        # צפוי: 10% על 84,000 + 14% על 16,000
        expected_tax = (84000 * 0.10) + (16000 * 0.14)
        assert abs(tax - expected_tax) < 0.01
        assert len(breakdown) == 2
    
    def test_high_income_tax_calculation(self):
        """בדיקת חישוב מס הכנסה גבוהה"""
        # הכנסה של 500,000 ש"ח בשנה
        tax, breakdown = self.calculator.calculate_income_tax(500000)
        
        # בדיקה שהמס חושב נכון לפי כל המדרגות
        assert tax > 0
        assert len(breakdown) == 5  # צריך לעבור על 5 מדרגות
    
    def test_zero_income_tax(self):
        """בדיקת מס על הכנסה אפס"""
        tax, breakdown = self.calculator.calculate_income_tax(0)
        
        assert tax == 0
        assert len(breakdown) == 0
    
    def test_national_insurance_calculation(self):
        """בדיקת חישוב ביטוח לאומי"""
        # הכנסה של 120,000 ש"ח בשנה (10,000 בחודש)
        ni = self.calculator.calculate_national_insurance(120000)
        
        # בדיקה שהחישוב סביר
        assert ni > 0
        assert ni < 120000 * 0.1  # לא יכול להיות יותר מ-10% מההכנסה
    
    def test_health_tax_calculation(self):
        """בדיקת חישוב מס בריאות"""
        # הכנסה של 120,000 ש"ח בשנה
        health_tax = self.calculator.calculate_health_tax(120000)
        
        # בדיקה שהחישוב סביר
        assert health_tax > 0
        assert health_tax < 120000 * 0.06  # לא יכול להיות יותר מ-6% מההכנסה
    
    def test_tax_credits_basic(self):
        """בדיקת נקודות זיכוי בסיסיות"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            marital_status="single",
            num_children=0
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=100000
        )
        
        credits_amount, applied_credits = self.calculator.calculate_applicable_credits(input_data)
        
        # צריך לקבל לפחות זיכוי בסיסי
        assert credits_amount >= 2640
        assert len(applied_credits) >= 1
        assert any(credit.code == "basic" for credit in applied_credits)
    
    def test_tax_credits_with_children(self):
        """בדיקת זיכוי ילדים"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            marital_status="married",
            num_children=2
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=100000
        )
        
        credits_amount, applied_credits = self.calculator.calculate_applicable_credits(input_data)
        
        # צריך לקבל זיכוי בסיסי + בן זוג + 2 ילדים
        expected_minimum = 2640 + 2640 + (1320 * 2)  # בסיסי + בן זוג + ילדים
        assert credits_amount >= expected_minimum
    
    def test_elderly_tax_credit(self):
        """בדיקת זיכוי זקנה"""
        personal_details = PersonalDetails(
            birth_date=date(1950, 1, 1),  # גיל 74
            marital_status="single",
            num_children=0
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=50000
        )
        
        credits_amount, applied_credits = self.calculator.calculate_applicable_credits(input_data)
        
        # צריך לקבל זיכוי בסיסי + זיכוי זקנה
        assert any(credit.code == "elderly" for credit in applied_credits)
    
    def test_pension_exemptions(self):
        """בדיקת פטורים לפנסיונרים"""
        personal_details = PersonalDetails(
            birth_date=date(1950, 1, 1),  # גיל 74
            marital_status="single"
        )
        
        exemption = self.calculator.calculate_pension_exemptions(50000, personal_details)
        
        # צריך לקבל פטור בסיסי
        assert exemption > 0
        assert exemption <= 50000  # לא יכול להיות יותר מההכנסה מפנסיה
    
    def test_comprehensive_tax_calculation(self):
        """בדיקת חישוב מס מקיף"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            marital_status="married",
            num_children=1,
            is_veteran=False,
            is_disabled=False
        )
        
        input_data = TaxCalculationInput(
            tax_year=2024,
            personal_details=personal_details,
            salary_income=150000,
            pension_income=0,
            pension_contributions=10000,
            study_fund_contributions=5000
        )
        
        result = self.calculator.calculate_comprehensive_tax(input_data)
        
        # בדיקות בסיסיות
        assert result.total_income == 150000
        assert result.taxable_income < result.total_income  # בגלל ניכויים
        assert result.income_tax > 0
        assert result.national_insurance > 0
        assert result.health_tax > 0
        assert result.tax_credits_amount > 0
        assert result.net_income > 0
        assert result.effective_tax_rate > 0
        assert result.effective_tax_rate < 50  # לא יכול להיות יותר מ-50%
    
    def test_optimization_suggestions(self):
        """בדיקת הצעות אופטימיזציה"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            marital_status="single"
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=200000,
            pension_contributions=5000  # נמוך מהמקסימום
        )
        
        result = self.calculator.calculate_comprehensive_tax(input_data)
        suggestions = self.calculator.generate_optimization_suggestions(input_data, result)
        
        # צריך לקבל הצעות
        assert len(suggestions) > 0
        
        # צריך להציע הגדלת הפרשות לפנסיה
        pension_suggestion = next(
            (s for s in suggestions if s.suggestion_type == "pension_contribution"), 
            None
        )
        assert pension_suggestion is not None
        assert pension_suggestion.potential_savings > 0
    
    def test_different_tax_years(self):
        """בדיקת שנות מס שונות"""
        calculator_2024 = TaxCalculator(2024)
        calculator_2025 = TaxCalculator(2025)
        
        # בדיקה שיש הבדל במדרגות המס
        brackets_2024 = calculator_2024.tax_brackets
        brackets_2025 = calculator_2025.tax_brackets
        
        assert len(brackets_2024) == len(brackets_2025)
        # המדרגות ל-2025 צריכות להיות גבוהות יותר (הצמדה)
        assert brackets_2025[0].max_income > brackets_2024[0].max_income

class TestTaxCalculatorEdgeCases:
    """בדיקות מקרי קצה"""
    
    def setup_method(self):
        self.calculator = TaxCalculator(2024)
    
    def test_very_high_income(self):
        """בדיקת הכנסה גבוהה מאוד"""
        tax, breakdown = self.calculator.calculate_income_tax(10000000)  # 10 מיליון
        
        assert tax > 0
        assert len(breakdown) == 6  # כל המדרגות
        # המדרגה האחרונה צריכה להיות 47%
        assert breakdown[-1].rate == 0.47
    
    def test_negative_income(self):
        """בדיקת הכנסה שלילית"""
        tax, breakdown = self.calculator.calculate_income_tax(-1000)
        
        assert tax == 0
        assert len(breakdown) == 0
    
    def test_maximum_children(self):
        """בדיקת מספר ילדים מקסימלי"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            num_children=10  # מספר גבוה של ילדים
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=100000
        )
        
        credits_amount, applied_credits = self.calculator.calculate_applicable_credits(input_data)
        
        # צריך לקבל זיכוי עבור כל הילדים
        child_credits = [c for c in applied_credits if c.code == "child"]
        assert len(child_credits) == 1  # זיכוי אחד שמכיל את כל הילדים
        assert "10 ילדים" in child_credits[0].description
    
    def test_100_percent_disability(self):
        """בדיקת נכות 100%"""
        personal_details = PersonalDetails(
            birth_date=date(1980, 1, 1),
            is_disabled=True,
            disability_percentage=100
        )
        
        input_data = TaxCalculationInput(
            personal_details=personal_details,
            salary_income=50000
        )
        
        credits_amount, applied_credits = self.calculator.calculate_applicable_credits(input_data)
        
        # צריך לקבל זיכוי נכות מלא
        disability_credits = [c for c in applied_credits if c.code == "disabled"]
        assert len(disability_credits) == 1
        assert disability_credits[0].amount == 7920  # זיכוי מלא

if __name__ == "__main__":
    pytest.main([__file__])
