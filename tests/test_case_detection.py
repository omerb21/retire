"""
Unit tests for case detection service and API functionality
"""
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.models.additional_income import AdditionalIncome, IncomeSourceType
from app.schemas.case import ClientCase
from app.services.case_service import detect_case, calculate_age


class TestCaseDetection(unittest.TestCase):
    """Test case detection logic and API endpoints"""

    def setUp(self):
        """Set up test database session mock"""
        self.db = MagicMock(spec=Session)
        self.today = date.today()
        
        # Setup a default client with reasonable defaults
        self.client = Client(
            id=1,
            first_name="Test",
            last_name="User",
            birth_date=date(1980, 1, 1),  # 45 years old in 2025
            id_number="123456789",
            is_active=True
        )
        
    def test_calculate_age(self):
        """Test age calculation function"""
        # Test with same month and day
        birth_date = date(1980, 6, 15)
        reference_date = date(2025, 6, 15)
        self.assertEqual(calculate_age(birth_date, reference_date), 45)
        
        # Test with reference date after birthday this year
        birth_date = date(1980, 6, 15)
        reference_date = date(2025, 7, 15)
        self.assertEqual(calculate_age(birth_date, reference_date), 45)
        
        # Test with reference date before birthday this year
        birth_date = date(1980, 6, 15)
        reference_date = date(2025, 5, 15)
        self.assertEqual(calculate_age(birth_date, reference_date), 44)
        
        # Test with exact retirement age
        birth_date = date(1958, 6, 15)
        reference_date = date(2025, 6, 15)
        self.assertEqual(calculate_age(birth_date, reference_date), 67)
        
    def test_case_past_retirement_age(self):
        """Test detection of past retirement age case (Case 3)"""
        # Set client birth date to be over retirement age
        self.client.birth_date = date.today() - timedelta(days=67*365 + 30)
        
        # Mock database query to return our test client
        self.db.query.return_value.filter.return_value.first.return_value = self.client
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.PAST_RETIREMENT_AGE)
        self.assertEqual(result.client_id, 1)
        # Check for retirement age reason (format: client_age_XX_exceeds_retirement_age_67)
        retirement_age_found = any("exceeds_retirement_age" in reason for reason in result.reasons)
        self.assertTrue(retirement_age_found, f"Expected retirement age reason in: {result.reasons}")
        
    def test_case_no_current_employer(self):
        """Test detection of no current employer case (Case 1)"""
        # Set client birth date to be under retirement age
        self.client.birth_date = date.today() - timedelta(days=45*365)
        
        # Mock database query to return our test client
        self.db.query.return_value.filter.return_value.first.return_value = self.client
        
        # Mock no current employer
        self.db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock no business income
        self.db.query.return_value.filter.return_value.all.return_value = []
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.NO_CURRENT_EMPLOYER)
        self.assertEqual(result.client_id, 1)
        self.assertIn("no_current_employer", result.reasons)
        
    def test_case_self_employed_only(self):
        """Test detection of self-employed case (Case 2)"""
        # Set client birth date to be under retirement age
        self.client.birth_date = date.today() - timedelta(days=45*365)
        
        # Mock business income
        business_income = AdditionalIncome(
            id=1,
            client_id=1,
            source_type=IncomeSourceType.business,
            amount=10000
        )
        
        # Set up proper side_effect for multiple queries
        def query_side_effect(*args):
            if args[0] == Client:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = self.client
                return mock_query
            elif args[0] == CurrentEmployer:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = None  # No current employer
                return mock_query
            elif args[0] == AdditionalIncome:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = business_income
                return mock_query
            else:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = None
                return mock_query
        
        self.db.query.side_effect = query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.SELF_EMPLOYED_ONLY)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_business_income", result.reasons)
        
    def test_case_active_no_leave(self):
        """Test detection of active employment with no leave case (Case 4)"""
        # Set client birth date to be under retirement age
        self.client.birth_date = date.today() - timedelta(days=45*365)
        self.client.planned_termination_date = None
        
        # Mock current employer with no end date
        current_employer = CurrentEmployer(
            id=1,
            client_id=1,
            employer_name="Test Employer",
            start_date=date(2020, 1, 1),
            end_date=None  # No planned leave
        )
        
        # Set up proper side_effect for multiple queries
        def query_side_effect(*args):
            if args[0] == Client:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = self.client
                return mock_query
            elif args[0] == CurrentEmployer:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = current_employer
                return mock_query
            else:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = None
                return mock_query
        
        self.db.query.side_effect = query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.ACTIVE_NO_LEAVE)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_current_employer", result.reasons)
        self.assertIn("no_planned_leave", result.reasons)
        
    def test_case_regular_with_leave(self):
        """Test detection of regular case with planned leave (Case 5)"""
        # Set client birth date to be under retirement age
        self.client.birth_date = date.today() - timedelta(days=45*365)
        
        # Mock current employer with end date
        current_employer = CurrentEmployer(
            id=1,
            client_id=1,
            employer_name="Test Employer",
            start_date=date(2020, 1, 1),
            end_date=date.today() + timedelta(days=180)  # Planned leave in 6 months
        )
        
        # Set up proper side_effect for multiple queries
        def query_side_effect(*args):
            if args[0] == Client:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = self.client
                return mock_query
            elif args[0] == CurrentEmployer:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = current_employer
                return mock_query
            else:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = None
                return mock_query
        
        self.db.query.side_effect = query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.REGULAR_WITH_LEAVE)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_current_employer", result.reasons)
        
    def test_client_planned_termination_date(self):
        """Test detection with client planned termination date set"""
        # Set client birth date to be under retirement age
        self.client.birth_date = date.today() - timedelta(days=45*365)
        self.client.planned_termination_date = date.today() + timedelta(days=90)
        
        # Mock current employer with no end date
        current_employer = CurrentEmployer(
            id=1,
            client_id=1,
            employer_name="Test Employer",
            start_date=date(2020, 1, 1),
            end_date=None  # No planned leave in employer record
        )
        
        # Set up proper side_effect for multiple queries
        def query_side_effect(*args):
            if args[0] == Client:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = self.client
                return mock_query
            elif args[0] == CurrentEmployer:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = current_employer
                return mock_query
            else:
                mock_query = MagicMock()
                mock_query.filter.return_value.first.return_value = None
                return mock_query
        
        self.db.query.side_effect = query_side_effect
        self.db.query.return_value.filter.return_value.first.return_value = current_employer
        
        # But client has planned termination date
        self.client.planned_termination_date = date.today() + timedelta(days=90)
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.REGULAR_WITH_LEAVE)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_current_employer", result.reasons)
        # Check for planned termination date in reasons (format: planned_termination_date_set_YYYY-MM-DD)
        planned_termination_found = any("planned_termination_date_set_" in reason for reason in result.reasons)
        self.assertTrue(planned_termination_found, f"Expected planned termination in reasons: {result.reasons}")
        
    def test_client_not_found(self):
        """Test error handling when client is not found"""
        # Mock database query to return None (client not found)
        self.db.query.return_value.filter.return_value.first.return_value = None
        
        with self.assertRaises(ValueError) as context:
            detect_case(self.db, 999)
            
        self.assertTrue("not found" in str(context.exception).lower())
        
    def test_missing_birth_date(self):
        """Test error handling when client birth date is missing"""
        # Set client birth date to None
        self.client.birth_date = None
        
        # Mock database query to return our test client without birth date
        self.db.query.return_value.filter.return_value.first.return_value = self.client
        
        with self.assertRaises(ValueError) as context:
            detect_case(self.db, 1)
            
        self.assertTrue("birth date" in str(context.exception).lower())
        

if __name__ == '__main__':
    unittest.main()
