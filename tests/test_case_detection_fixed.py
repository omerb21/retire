"""
Unit tests for case detection service - fixed version without SQLAlchemy fixtures
"""
import unittest
from unittest.mock import MagicMock
from datetime import date, timedelta

from app.services.case_service import detect_case
from app.schemas.case import ClientCase


class TestCaseDetection(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = MagicMock()
        
        # Create a mock client
        self.mock_client = MagicMock()
        self.mock_client.id = 1
        self.mock_client.id_number = "123456789"
        self.mock_client.full_name = "Test Client"
        self.mock_client.first_name = "Test"
        self.mock_client.last_name = "Client"
        self.mock_client.birth_date = date(1980, 1, 1)
        self.mock_client.gender = "male"
        self.mock_client.marital_status = "single"
        self.mock_client.self_employed = False
        self.mock_client.current_employer_exists = True
        self.mock_client.is_active = True
        
        # Set up default mock behavior
        self.db = self.mock_db

    def test_case_active_no_leave(self):
        """Test detection of active employment with no leave case (Case 4)"""
        # Create mock client
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.birth_date = date.today() - timedelta(days=45*365)  # 45 years old
        mock_client.planned_termination_date = None
        
        # Create mock current employer
        mock_employer = MagicMock()
        mock_employer.id = 1
        mock_employer.client_id = 1
        mock_employer.employer_name = "Test Employer"
        mock_employer.start_date = date(2020, 1, 1)
        mock_employer.end_date = None
        
        # Set up mock queries
        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__') and model.__name__ == 'Client':
                mock_query.filter.return_value.first.return_value = mock_client
            elif hasattr(model, '__name__') and model.__name__ == 'CurrentEmployer':
                mock_query.filter.return_value.first.return_value = mock_employer
            else:
                mock_query.filter.return_value.first.return_value = None
            return mock_query
        
        self.db.query.side_effect = mock_query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.ACTIVE_NO_LEAVE)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_current_employer", result.reasons)

    def test_case_regular_with_leave(self):
        """Test detection of regular case with planned leave (Case 5)"""
        # Create mock client
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.birth_date = date.today() - timedelta(days=45*365)  # 45 years old
        mock_client.planned_termination_date = date.today() + timedelta(days=30)  # Planned leave in 30 days
        
        # Create mock current employer
        mock_employer = MagicMock()
        mock_employer.id = 1
        mock_employer.client_id = 1
        mock_employer.employer_name = "Test Employer"
        mock_employer.start_date = date(2020, 1, 1)
        mock_employer.end_date = date.today() + timedelta(days=30)  # Matches planned termination
        
        # Set up mock queries
        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__') and model.__name__ == 'Client':
                mock_query.filter.return_value.first.return_value = mock_client
            elif hasattr(model, '__name__') and model.__name__ == 'CurrentEmployer':
                mock_query.filter.return_value.first.return_value = mock_employer
            else:
                mock_query.filter.return_value.first.return_value = None
            return mock_query
        
        self.db.query.side_effect = mock_query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.REGULAR_WITH_LEAVE)
        self.assertEqual(result.client_id, 1)
        self.assertIn("has_current_employer", result.reasons)
        # Check for the actual reason format - should be employer_end_date_set_ since employer has end_date
        found_end_date_reason = any("employer_end_date_set_" in reason for reason in result.reasons)
        self.assertTrue(found_end_date_reason, f"Expected employer_end_date_set_ reason, got: {result.reasons}")

    def test_case_past_retirement_age(self):
        """Test detection of past retirement age case (Case 1)"""
        # Create mock client past retirement age
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.birth_date = date.today() - timedelta(days=68*365)  # 68 years old
        mock_client.planned_termination_date = None
        
        # Set up mock queries - no current employer
        def mock_query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__') and model.__name__ == 'Client':
                mock_query.filter.return_value.first.return_value = mock_client
            else:
                mock_query.filter.return_value.first.return_value = None
            return mock_query
        
        self.db.query.side_effect = mock_query_side_effect
        
        result = detect_case(self.db, 1)
        
        self.assertEqual(result.case_id, ClientCase.PAST_RETIREMENT_AGE)
        self.assertEqual(result.client_id, 1)
        # Check for the actual reason format with age calculation
        found_age_reason = any("exceeds_retirement_age" in reason for reason in result.reasons)
        self.assertTrue(found_age_reason, f"Expected age-related reason, got: {result.reasons}")


if __name__ == '__main__':
    unittest.main()
