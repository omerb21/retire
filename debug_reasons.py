"""
Debug script to check what reasons are returned by detect_case
"""
from app.services.case_service import detect_case
from unittest.mock import MagicMock
from datetime import date, timedelta

# Create mock database
mock_db = MagicMock()

# Create mock client past retirement age
mock_client = MagicMock()
mock_client.id = 1
mock_client.birth_date = date.today() - timedelta(days=68*365)  # 68 years old
mock_client.planned_termination_date = None

# No current employer for this test
mock_employer = None

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

mock_db.query.side_effect = mock_query_side_effect

# Test the case detection
result = detect_case(mock_db, 1)

print(f"Case ID: {result.case_id}")
print(f"Client ID: {result.client_id}")
print(f"Reasons: {result.reasons}")
for i, reason in enumerate(result.reasons):
    print(f"  {i}: '{reason}'")
