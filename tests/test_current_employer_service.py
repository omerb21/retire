"""
Unit tests for CurrentEmployer service layer - Sprint 3
Tests for calculation logic and service operations
"""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock
from app.services.current_employer_service import CurrentEmployerService
from app.models import CurrentEmployer, EmployerGrant
from app.models.current_employment import ActiveContinuityType, GrantType


class TestCurrentEmployerService:
    """Test cases for CurrentEmployer service calculations"""
    
    def test_calculate_service_years_basic(self):
        """Test basic service years calculation without non-continuous periods"""
        start_date = date(2020, 1, 1)
        end_date = date(2024, 1, 1)
        
        service_years = CurrentEmployerService.calculate_service_years(
            start_date, end_date
        )
        
        assert service_years == 4.0
    
    def test_calculate_service_years_with_end_date_none(self):
        """Test service years calculation with no end date (current employment)"""
        start_date = date(2023, 1, 1)
        
        service_years = CurrentEmployerService.calculate_service_years(
            start_date, None
        )
        
        # Should calculate from start_date to today
        expected_years = (date.today() - start_date).days / 365.25
        assert abs(service_years - expected_years) < 0.01
    
    def test_calculate_service_years_with_non_continuous_periods(self):
        """Test service years calculation with non-continuous periods"""
        start_date = date(2020, 1, 1)
        end_date = date(2024, 1, 1)
        
        # 6 months unpaid leave
        non_continuous_periods = [
            {
                "start_date": "2022-01-01",
                "end_date": "2022-07-01",
                "reason": "unpaid_leave"
            }
        ]
        
        service_years = CurrentEmployerService.calculate_service_years(
            start_date, end_date, non_continuous_periods
        )
        
        # 4 years minus 6 months (0.5 years)
        assert abs(service_years - 3.5) < 0.01
    
    def test_calculate_service_years_with_invalid_periods(self):
        """Test service years calculation with invalid non-continuous periods"""
        start_date = date(2020, 1, 1)
        end_date = date(2024, 1, 1)
        
        # Invalid periods should be skipped
        non_continuous_periods = [
            {"start_date": "invalid", "end_date": "2022-07-01"},
            {"start_date": "2022-01-01"},  # Missing end_date
            {
                "start_date": "2023-01-01",
                "end_date": "2023-04-01",
                "reason": "sick_leave"
            }
        ]
        
        service_years = CurrentEmployerService.calculate_service_years(
            start_date, end_date, non_continuous_periods
        )
        
        # Only the valid period (3 months) should be deducted
        expected_years = 4.0 - (90 / 365.25)  # 90 days = ~3 months
        assert abs(service_years - expected_years) < 0.01
    
    def test_calculate_severance_grant_basic(self):
        """Test basic severance grant calculation"""
        # Create mock current employer
        current_employer = Mock(spec=CurrentEmployer)
        current_employer.start_date = date(2020, 1, 1)
        current_employer.end_date = date(2024, 1, 1)
        current_employer.non_continuous_periods = None
        current_employer.last_salary = 10000.0
        
        # Create mock grant
        grant = Mock(spec=EmployerGrant)
        grant.grant_amount = 50000.0
        grant.grant_type = GrantType.severance
        
        result = CurrentEmployerService.calculate_severance_grant(
            current_employer, grant
        )
        
        assert result.service_years == 4.0
        assert result.indexed_amount == 50000.0  # Stub indexing
        assert result.severance_exemption_cap > 0
        assert result.grant_exempt <= result.indexed_amount
        assert result.grant_taxable >= 0
        assert result.tax_due >= 0
    
    def test_calculate_severance_grant_with_high_exemption(self):
        """Test severance grant calculation where entire amount is exempt"""
        # Create mock current employer with high salary and long service
        current_employer = Mock(spec=CurrentEmployer)
        current_employer.start_date = date(2010, 1, 1)
        current_employer.end_date = date(2024, 1, 1)
        current_employer.non_continuous_periods = None
        current_employer.last_salary = 50000.0  # High salary
        
        # Create mock grant with modest amount
        grant = Mock(spec=EmployerGrant)
        grant.grant_amount = 100000.0
        grant.grant_type = GrantType.severance
        
        result = CurrentEmployerService.calculate_severance_grant(
            current_employer, grant
        )
        
        assert result.service_years == 14.0
        # With high exemption cap, most/all should be exempt
        assert result.grant_exempt > 0
        assert result.tax_due >= 0
    
    def test_calculate_severance_grant_with_non_continuous_periods(self):
        """Test severance grant calculation with non-continuous periods"""
        # Create mock current employer
        current_employer = Mock(spec=CurrentEmployer)
        current_employer.start_date = date(2020, 1, 1)
        current_employer.end_date = date(2024, 1, 1)
        current_employer.non_continuous_periods = [
            {
                "start_date": "2022-01-01",
                "end_date": "2022-07-01",
                "reason": "unpaid_leave"
            }
        ]
        current_employer.last_salary = 10000.0
        
        # Create mock grant
        grant = Mock(spec=EmployerGrant)
        grant.grant_amount = 50000.0
        grant.grant_type = GrantType.severance
        
        result = CurrentEmployerService.calculate_severance_grant(
            current_employer, grant
        )
        
        # Service years should be reduced by non-continuous period
        assert result.service_years == 3.5
        assert result.indexed_amount == 50000.0
        assert result.grant_exempt >= 0
        assert result.grant_taxable >= 0
    
    def test_calculate_severance_grant_zero_salary(self):
        """Test severance grant calculation with zero/None salary"""
        # Create mock current employer with no salary info
        current_employer = Mock(spec=CurrentEmployer)
        current_employer.start_date = date(2020, 1, 1)
        current_employer.end_date = date(2024, 1, 1)
        current_employer.non_continuous_periods = None
        current_employer.last_salary = None
        
        # Create mock grant
        grant = Mock(spec=EmployerGrant)
        grant.grant_amount = 50000.0
        grant.grant_type = GrantType.severance
        
        result = CurrentEmployerService.calculate_severance_grant(
            current_employer, grant
        )
        
        assert result.service_years == 4.0
        assert result.indexed_amount == 50000.0
        # With no salary, exemption cap should be 0, so all taxable
        assert result.severance_exemption_cap == 0.0
        assert result.grant_exempt == 0.0
        assert result.grant_taxable == 50000.0
        assert result.tax_due > 0  # Should have tax on full amount


class TestCurrentEmployerServiceIntegration:
    """Integration tests for CurrentEmployer service with database operations"""
    
    def test_service_years_calculation_edge_cases(self):
        """Test edge cases in service years calculation"""
        # Test same start and end date
        service_years = CurrentEmployerService.calculate_service_years(
            date(2024, 1, 1), date(2024, 1, 1)
        )
        assert service_years == 0.0
        
        # Test leap year handling
        service_years = CurrentEmployerService.calculate_service_years(
            date(2020, 1, 1), date(2021, 1, 1)  # 2020 is leap year
        )
        assert abs(service_years - 1.0) < 0.01
        
        # Test negative periods (should return 0)
        non_continuous_periods = [
            {
                "start_date": "2020-01-01",
                "end_date": "2025-01-01",  # Longer than employment
                "reason": "invalid_period"
            }
        ]
        service_years = CurrentEmployerService.calculate_service_years(
            date(2020, 1, 1), date(2024, 1, 1), non_continuous_periods
        )
        assert service_years == 0.0  # Should not go negative
