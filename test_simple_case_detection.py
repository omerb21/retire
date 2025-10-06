"""
Simple test for case detection without complex SQLAlchemy relationships
"""
import pytest
from unittest.mock import MagicMock
from datetime import date, timedelta
from app.services.case_service import detect_case
from app.schemas.case import ClientCase

def test_simple_case_detection():
    """Test case detection with mocked database"""
    # Create mock database session
    mock_db = MagicMock()
    
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
        if model.__name__ == 'Client':
            mock_query.filter.return_value.first.return_value = mock_client
        elif model.__name__ == 'CurrentEmployer':
            mock_query.filter.return_value.first.return_value = mock_employer
        else:
            mock_query.filter.return_value.first.return_value = None
        return mock_query
    
    mock_db.query.side_effect = mock_query_side_effect
    
    # Test the case detection
    result = detect_case(mock_db, 1)
    
    # Verify results
    assert result.case_id == ClientCase.ACTIVE_NO_LEAVE
    assert result.client_id == 1
    assert "has_current_employer" in result.reasons

if __name__ == "__main__":
    test_simple_case_detection()
    print("Simple case detection test passed!")
