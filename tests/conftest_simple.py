"""
Simple pytest fixtures that avoid SQLAlchemy mapper conflicts
"""
import pytest
from unittest.mock import MagicMock
from datetime import date


@pytest.fixture
def mock_db():
    """Simple mock database session"""
    return MagicMock()


@pytest.fixture
def mock_client():
    """Mock client object"""
    client = MagicMock()
    client.id = 1
    client.id_number = "123456789"
    client.full_name = "Test Client"
    client.first_name = "Test"
    client.last_name = "Client"
    client.birth_date = date(1980, 1, 1)
    client.gender = "male"
    client.marital_status = "single"
    client.self_employed = False
    client.current_employer_exists = True
    client.is_active = True
    client.planned_termination_date = None
    return client


@pytest.fixture
def mock_current_employer():
    """Mock current employer object"""
    employer = MagicMock()
    employer.id = 1
    employer.client_id = 1
    employer.employer_name = "Test Employer"
    employer.start_date = date(2020, 1, 1)
    employer.end_date = None
    return employer
