"""
Mock models for testing without SQLAlchemy conflicts
"""
from datetime import date

class MockClient:
    """Mock client model for testing"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.id_number = kwargs.get('id_number', '123456789')
        self.id_number_raw = kwargs.get('id_number_raw', '123456789')
        self.full_name = kwargs.get('full_name', 'Test User')
        self.first_name = kwargs.get('first_name', 'Test')
        self.last_name = kwargs.get('last_name', 'User')
        self.birth_date = kwargs.get('birth_date', date(1980, 1, 1))
        self.gender = kwargs.get('gender', 'male')
        self.marital_status = kwargs.get('marital_status', 'single')
        self.self_employed = kwargs.get('self_employed', False)
        self.current_employer_exists = kwargs.get('current_employer_exists', True)
        self.is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        
    def __repr__(self):
        return f"<MockClient(id={self.id}, full_name='{self.full_name}', id_number='{self.id_number}')>"

class MockCurrentEmployer:
    """Mock current employer model for testing"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.client_id = kwargs.get('client_id', 1)
        self.employer_name = kwargs.get('employer_name', 'Test Corp')
        self.start_date = kwargs.get('start_date', date(2020, 1, 1))
        self.end_date = kwargs.get('end_date', None)
        self.monthly_salary = kwargs.get('monthly_salary', 10000)
        self.created_at = kwargs.get('created_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        
    def __repr__(self):
        return f"<MockCurrentEmployer(id={self.id}, employer_name='{self.employer_name}')>"

class MockGrant:
    """Mock grant model for testing"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.client_id = kwargs.get('client_id', 1)
        self.employer_name = kwargs.get('employer_name', 'Past Corp')
        self.grant_amount = kwargs.get('grant_amount', 50000)
        self.grant_date = kwargs.get('grant_date', date(2019, 12, 31))
        self.years_of_service = kwargs.get('years_of_service', 5)
        self.created_at = kwargs.get('created_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        
    def __repr__(self):
        return f"<MockGrant(id={self.id}, employer_name='{self.employer_name}', grant_amount={self.grant_amount})>"

class MockScenario:
    """Mock scenario model for testing"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.client_id = kwargs.get('client_id', 1)
        self.name = kwargs.get('name', 'Default Scenario')
        self.description = kwargs.get('description', 'Default retirement scenario')
        self.retirement_age = kwargs.get('retirement_age', 67)
        self.created_at = kwargs.get('created_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        
    def __repr__(self):
        return f"<MockScenario(id={self.id}, name='{self.name}')>"

def create_mock_client():
    """Create a mock client with default values"""
    return MockClient()

def create_mock_current_employer(client_id=1):
    """Create a mock current employer with default values"""
    return MockCurrentEmployer(client_id=client_id)

def create_mock_grant(client_id=1):
    """Create a mock grant with default values"""
    return MockGrant(client_id=client_id)

def create_mock_scenario(client_id=1):
    """Create a mock scenario with default values"""
    return MockScenario(client_id=client_id)

def test_mock_models():
    """Test mock models"""
    client = create_mock_client()
    employer = create_mock_current_employer(client_id=client.id)
    grant = create_mock_grant(client_id=client.id)
    scenario = create_mock_scenario(client_id=client.id)
    
    print(f"Client: {client}")
    print(f"Current Employer: {employer}")
    print(f"Grant: {grant}")
    print(f"Scenario: {scenario}")
    
    return True

if __name__ == "__main__":
    test_mock_models()
