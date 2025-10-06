"""
Unit tests for calculation engine functions
"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from app.services.calculations import (
    calculate_service_years,
    apply_indexation,
    calculate_severance_grant,
    calculate_pension_income,
    generate_cashflow
)


class TestCalculateServiceYears:
    """Test service years calculation"""
    
    def test_basic_service_years(self):
        """Test basic service years calculation"""
        start_date = date(2020, 1, 1)
        end_date = date(2025, 1, 1)
        
        result = calculate_service_years(start_date, end_date)
        
        assert result["service_years"] == 5.0
        assert result["start_date"] == "2020-01-01"
        assert result["end_date"] == "2025-01-01"
        assert result["total_days"] == 1826  # 5 years including leap year
        assert result["calculation_method"] == "basic_days_365"
    
    def test_service_years_with_non_continuous_periods(self):
        """Test service years with non-continuous periods"""
        start_date = date(2020, 1, 1)
        end_date = date(2025, 1, 1)
        non_continuous = [{"start": "2022-01-01", "end": "2022-06-01", "reason": "unpaid_leave"}]
        
        result = calculate_service_years(start_date, end_date, non_continuous)
        
        assert result["service_years"] == 4.9  # 5.0 - 0.1 (stub reduction)
        assert result["non_continuous_periods"] == non_continuous
    
    def test_service_years_current_employment(self):
        """Test service years for current employment (no end date)"""
        start_date = date(2020, 1, 1)
        
        result = calculate_service_years(start_date)
        
        assert "service_years" in result
        assert result["start_date"] == "2020-01-01"
        assert result["end_date"] == date.today().isoformat()


class TestApplyIndexation:
    """Test indexation calculations"""
    
    def test_no_indexation(self):
        """Test no indexation applied"""
        base_amount = Decimal("100000")
        
        result = apply_indexation(base_amount, "none")
        
        assert result["base_amount"] == 100000.0
        assert result["indexed_amount"] == 100000.0
        assert result["indexation_method"] == "none"
        assert result["total_increase"] == 0.0
        assert result["increase_percentage"] == 0.0
    
    def test_fixed_indexation(self):
        """Test fixed rate indexation"""
        base_amount = Decimal("100000")
        fixed_rate = Decimal("0.03")  # 3%
        years = 5
        
        result = apply_indexation(base_amount, "fixed", fixed_rate, years)
        
        expected_amount = 100000 * (1.03 ** 5)  # ~115927.41
        assert abs(result["indexed_amount"] - expected_amount) < 0.01
        assert result["indexation_method"] == "fixed"
        assert result["fixed_rate"] == 0.03
        assert result["years"] == 5
    
    def test_cpi_indexation(self):
        """Test CPI indexation"""
        base_amount = Decimal("100000")
        years = 3
        
        result = apply_indexation(base_amount, "cpi", years=years)
        
        expected_amount = 100000 * (1.02 ** 3)  # ~106120.80
        assert abs(result["indexed_amount"] - expected_amount) < 0.01
        assert result["indexation_method"] == "cpi"
        assert result["years"] == 3


class TestCalculateSeveranceGrant:
    """Test severance grant calculations"""
    
    def test_basic_severance_calculation(self):
        """Test basic severance calculation"""
        salary = Decimal("15000")
        service_years = Decimal("10")
        
        result = calculate_severance_grant(salary, service_years)
        
        assert result["gross_severance"] == 150000.0  # 15000 * 10
        assert result["salary"] == 15000.0
        assert result["service_years"] == 10.0
        assert result["calculation_method"] == "basic_salary_years"
    
    def test_severance_with_tax(self):
        """Test severance calculation with tax implications"""
        salary = Decimal("20000")
        service_years = Decimal("15")
        
        result = calculate_severance_grant(salary, service_years)
        
        gross_severance = 300000.0  # 20000 * 15
        exemption_cap = 400000.0
        
        assert result["gross_severance"] == gross_severance
        assert result["exemption_cap"] == exemption_cap
        assert result["exempt_amount"] == gross_severance  # Below cap
        assert result["taxable_amount"] == 0.0
        assert result["tax_due"] == 0.0
        assert result["net_severance"] == gross_severance
    
    def test_severance_above_exemption_cap(self):
        """Test severance calculation above exemption cap"""
        salary = Decimal("30000")
        service_years = Decimal("20")
        
        result = calculate_severance_grant(salary, service_years)
        
        gross_severance = 600000.0  # 30000 * 20
        exemption_cap = 400000.0
        taxable_amount = 200000.0  # 600000 - 400000
        tax_due = 70000.0  # 200000 * 0.35
        net_severance = 530000.0  # 600000 - 70000
        
        assert result["gross_severance"] == gross_severance
        assert result["exempt_amount"] == exemption_cap
        assert result["taxable_amount"] == taxable_amount
        assert result["tax_due"] == tax_due
        assert result["net_severance"] == net_severance


class TestCalculatePensionIncome:
    """Test pension income calculations"""
    
    def test_basic_pension_calculation(self):
        """Test basic pension income calculation"""
        balance = Decimal("1200000")  # 1.2M
        annuity_factor = Decimal("0.05")  # 5%
        
        result = calculate_pension_income(balance, annuity_factor)
        
        expected_monthly = 1200000 * 0.05 / 12  # 5000
        expected_annual = expected_monthly * 12  # 60000
        
        assert result["balance"] == 1200000.0
        assert result["annuity_factor"] == 0.05
        assert result["monthly_pension"] == expected_monthly
        assert result["annual_pension"] == expected_annual
        assert result["indexation_method"] == "none"
    
    def test_pension_with_fixed_indexation(self):
        """Test pension calculation with fixed indexation"""
        balance = Decimal("1000000")
        annuity_factor = Decimal("0.04")
        fixed_rate = Decimal("0.025")  # 2.5%
        
        result = calculate_pension_income(balance, annuity_factor, "fixed", fixed_rate)
        
        base_monthly = 1000000 * 0.04 / 12  # ~3333.33
        indexed_monthly = base_monthly * (1.025 ** 10)  # 10 years projection
        
        assert result["monthly_pension"] == base_monthly
        assert abs(result["indexed_monthly_pension"] - indexed_monthly) < 0.01
        assert result["indexation_method"] == "fixed"
        assert result["fixed_rate"] == 0.025
        assert result["projection_years"] == 10
    
    def test_pension_with_cpi_indexation(self):
        """Test pension calculation with CPI indexation"""
        balance = Decimal("800000")
        annuity_factor = Decimal("0.06")
        
        result = calculate_pension_income(balance, annuity_factor, "cpi")
        
        base_monthly = 800000 * 0.06 / 12  # 4000
        indexed_monthly = base_monthly * (1.02 ** 10)  # 2% CPI for 10 years
        
        assert result["monthly_pension"] == base_monthly
        assert abs(result["indexed_monthly_pension"] - indexed_monthly) < 0.01
        assert result["indexation_method"] == "cpi"


class TestGenerateCashflow:
    """Test cashflow generation"""
    
    def test_basic_cashflow_generation(self):
        """Test basic cashflow generation"""
        client_id = 1
        scenario_params = {"test_param": "value"}
        
        result = generate_cashflow(client_id, scenario_params)
        
        assert result["client_id"] == client_id
        assert result["scenario_params"] == scenario_params
        assert result["status"] == "completed"
        assert result["projection_period"] == "2025"
        
        # Check monthly data structure
        monthly_data = result["monthly"]
        assert len(monthly_data) == 12
        
        for i, month_data in enumerate(monthly_data, 1):
            assert month_data["month"] == i
            assert "date" in month_data
            assert "income" in month_data
            assert "expenses" in month_data
            assert "net" in month_data
            assert "cumulative_net" in month_data
        
        # Check yearly totals
        yearly_totals = result["yearly_totals"]["2025"]
        assert "income" in yearly_totals
        assert "expenses" in yearly_totals
        assert "net" in yearly_totals
        
        # Verify totals match sum of monthly data
        total_income = sum(item["income"] for item in monthly_data)
        total_expenses = sum(item["expenses"] for item in monthly_data)
        total_net = sum(item["net"] for item in monthly_data)
        
        assert yearly_totals["income"] == total_income
        assert yearly_totals["expenses"] == total_expenses
        assert yearly_totals["net"] == total_net
    
    def test_cashflow_data_consistency(self):
        """Test cashflow data consistency"""
        result = generate_cashflow(1, {})
        
        monthly_data = result["monthly"]
        
        # Check that net = income - expenses for each month
        for month_data in monthly_data:
            expected_net = month_data["income"] - month_data["expenses"]
            assert abs(month_data["net"] - expected_net) < 0.01
        
        # Check that yearly totals are consistent
        yearly_net = result["yearly_totals"]["2025"]["net"]
        monthly_net_sum = sum(item["net"] for item in monthly_data)
        assert abs(yearly_net - monthly_net_sum) < 0.01


# Integration test
def test_all_functions_return_expected_structure():
    """Test that all functions return expected data structures"""
    
    # Test calculate_service_years
    service_result = calculate_service_years(date(2020, 1, 1), date(2025, 1, 1))
    assert isinstance(service_result, dict)
    assert "service_years" in service_result
    
    # Test apply_indexation
    indexation_result = apply_indexation(Decimal("100000"))
    assert isinstance(indexation_result, dict)
    assert "indexed_amount" in indexation_result
    
    # Test calculate_severance_grant
    severance_result = calculate_severance_grant(Decimal("15000"), Decimal("10"))
    assert isinstance(severance_result, dict)
    assert "net_severance" in severance_result
    
    # Test calculate_pension_income
    pension_result = calculate_pension_income(Decimal("1000000"), Decimal("0.05"))
    assert isinstance(pension_result, dict)
    assert "monthly_pension" in pension_result
    
    # Test generate_cashflow
    cashflow_result = generate_cashflow(1, {})
    assert isinstance(cashflow_result, dict)
    assert "monthly" in cashflow_result
    assert "yearly_totals" in cashflow_result
