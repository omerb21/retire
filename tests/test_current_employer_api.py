"""
API tests for CurrentEmployer endpoints - Sprint 3
Tests for the three required API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date
from app.main import app as fastapi_app
from app.models import Client, CurrentEmployer, EmployerGrant


@pytest.fixture(scope="module", autouse=True)
def setup_test_client(_test_db):
    """Set up test client in database"""
    Session = _test_db["Session"]
    with Session() as db:
        test_client = Client(
            id_number_raw="123456782",
            id_number="123456782",
            full_name="Test Client Sprint 3",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)


class TestCurrentEmployerAPI:
    @pytest.fixture
    def client_without_employer(self, _test_db):
        """
        Create a client without a current employer specifically for the 'no employer' test.
        Returns the client ID.
        """
        Session = _test_db["Session"]
        db = Session()
        try:
            # Create a specific test client for this test
            test_client = Client(
                id_number_raw="no_current_employer_test_123",
                id_number="no_current_employer_test_123",
                full_name="Test Client Without Current Employer",
                birth_date=date(1990, 1, 1),
                is_active=True
            )
            db.add(test_client)
            db.commit()
            db.refresh(test_client)
            
            # Double-check client was saved
            client_id = test_client.id
            print(f"\n[FIXTURE] Created test client with ID: {client_id}")
            print(f"[FIXTURE] Name: {test_client.full_name}, ID Number: {test_client.id_number}")
            
            # Ensure no current employer exists for this client
            ce = db.scalar(select(CurrentEmployer).where(CurrentEmployer.client_id == client_id))
            if ce:
                db.delete(ce)
                db.commit()
                print(f"[FIXTURE] Deleted existing current employer for client {client_id}")
            else:
                print(f"[FIXTURE] No current employer found for client {client_id} - good!")
                
            return client_id
        finally:
            db.close()
    """Test cases for CurrentEmployer API endpoints"""
    
    def test_create_current_employer_201(self, _test_db):
        """Test creating a new current employer returns 201"""
        client = TestClient(fastapi_app)
        
        employer_data = {
            "employer_name": "טכנולוגיות ABC",
            "employer_id_number": "123456789",
            "start_date": "2020-01-01",
            "end_date": None,
            "last_salary": 15000.0,
            "average_salary": 14000.0,
            "severance_accrued": 50000.0,
            "active_continuity": "severance"
        }
        
        response = client.post("/api/v1/clients/1/current-employer", json=employer_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["employer_name"] == "טכנולוגיות ABC"
        assert data["client_id"] == 1
        assert data["last_salary"] == 15000.0
        assert data["active_continuity"] == "severance"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_current_employer_client_not_found_404(self, _test_db):
        """Test creating current employer for non-existent client returns 404"""
        client = TestClient(fastapi_app)
        
        employer_data = {
            "employer_name": "טכנולוגיות XYZ",
            "start_date": "2020-01-01"
        }
        
        response = client.post("/api/v1/clients/999/current-employer", json=employer_data)
        
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "לקוח לא נמצא"
    
    def test_update_existing_current_employer_200(self, _test_db):
        """Test updating existing current employer returns 200"""
        client = TestClient(fastapi_app)
        
        # First create an employer
        employer_data = {
            "employer_name": "חברת DEF",
            "start_date": "2021-01-01",
            "last_salary": 12000.0
        }
        
        create_response = client.post("/api/v1/clients/1/employment/current", json=employer_data)
        assert create_response.status_code in [200, 201]
        
        # Then update it
        update_data = {
            "employer_name": "חברת DEF מעודכנת",
            "start_date": "2021-01-01",
            "last_salary": 18000.0,
            "end_date": "2024-12-31"
        }
        
        update_response = client.post("/api/v1/clients/1/current-employer", json=update_data)
        
        # Should return 200 for update (or 201 if creating new)
        assert update_response.status_code in [200, 201]
        data = update_response.json()
        assert data["employer_name"] == "חברת DEF מעודכנת"
        assert data["last_salary"] == 18000.0
        assert data["end_date"] == "2024-12-31"
    
    def test_get_current_employer_200(self, _test_db):
        """Test retrieving existing current employer returns 200"""
        client = TestClient(fastapi_app)
        
        # First create an employer
        employer_data = {
            "employer_name": "חברת GHI",
            "start_date": "2022-01-01",
            "last_salary": 20000.0
        }
        
        create_response = client.post("/api/v1/clients/1/employment/current", json=employer_data)
        assert create_response.status_code in [200, 201]
        
        # Then retrieve it
        get_response = client.get("/api/v1/clients/1/current-employer")
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["employer_name"] == "חברת GHI"
        assert data["client_id"] == 1
        assert data["last_salary"] == 20000.0
    
    def test_get_current_employer_client_not_found_404(self, _test_db):
        """Test retrieving current employer for non-existent client returns 404"""
        client = TestClient(fastapi_app)
        
        response = client.get("/api/v1/clients/999/current-employer")
        
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "לקוח לא נמצא"
    
    def test_get_current_employer_no_employer_404(self, client, db_session):
        """Test retrieving current employer when none exists returns 404"""
        print("\n[TEST] Starting test_get_current_employer_no_employer_404")
        print(f"[TEST] DB session ID: {id(db_session)}")
        
        try:
            # Generate a unique ID to avoid collisions
            import uuid, time
            unique_id = f"{str(uuid.uuid4())[:8]}_{int(time.time())}"
            
            print(f"[TEST] Creating test client with unique ID: {unique_id}")
            test_client = Client(
                id_number_raw=f"test_no_employer_{unique_id}",
                id_number=f"test_no_employer_{unique_id}",
                full_name=f"Test Client {unique_id}",
                birth_date=date(1990, 5, 15),
                is_active=True
            )
            
            print(f"[TEST] Adding client to database")
            db_session.add(test_client)
            print(f"[TEST] Committing client to database")
            db_session.commit()
            print(f"[TEST] Refreshing client object")
            db_session.refresh(test_client)
            client_id = test_client.id
            print(f"[TEST] Created client with ID: {client_id}")
            
            # Force SQLAlchemy to execute a new query to verify client exists
            print(f"[TEST] Verifying client exists in database")
            db_session.expire_all()  # Clear session cache
            check_client = db_session.query(Client).filter(Client.id == client_id).first()
            if check_client:
                print(f"[TEST] Client verified: ID={check_client.id}, Name='{check_client.full_name}'")
            else:
                print(f"[TEST] WARNING: Could not verify client in database!")
            
            # Make request to API
            endpoint = f"/api/v1/clients/{client_id}/current-employer"
            print(f"[TEST] Calling GET {endpoint}")
            response = client.get(endpoint)
            print(f"[TEST] Response status: {response.status_code}")
            print(f"[TEST] Response body: {response.text}")
            
            # Assert response is correct
            assert response.status_code == 404, f"Expected 404, got {response.status_code}"
            error_msg = response.json()["detail"]["error"]
            expected_error = "אין מעסיק נוכחי רשום ללקוח"
            
            print(f"[TEST] Actual error: '{error_msg}'")
            print(f"[TEST] Expected error: '{expected_error}'")
            assert error_msg == expected_error, f"Wrong error message: got '{error_msg}'"   
        finally:
            print(f"[TEST] Test completed")
            # Session will be closed by pytest fixture
    
    def test_add_grant_to_current_employer_201(self, _test_db):
        """Test adding grant to current employer returns 201 with calculation"""
        client = TestClient(fastapi_app)
        
        # First create an employer
        employer_data = {
            "employer_name": "חברת JKL",
            "start_date": "2020-01-01",
            "end_date": "2024-01-01",
            "last_salary": 15000.0
        }
        
        create_response = client.post("/api/v1/clients/1/employment/current", json=employer_data)
        assert create_response.status_code in [200, 201]
        
        # Then add a grant
        grant_data = {
            "grant_type": "severance",
            "grant_amount": 80000.0,
            "grant_date": "2024-01-01",
            "tax_withheld": 5000.0
        }
        
        grant_response = client.post("/api/v1/clients/1/current-employer/grants", json=grant_data)
        
        assert grant_response.status_code == 201
        data = grant_response.json()
        
        # Verify grant data
        assert data["grant_type"] == "severance"
        assert data["grant_amount"] == 80000.0
        assert data["tax_withheld"] == 5000.0
        
        # Verify calculation results are included
        assert "calculation" in data
        calc = data["calculation"]
        assert "grant_exempt" in calc
        assert "grant_taxable" in calc
        assert "tax_due" in calc
        assert "indexed_amount" in calc
        assert "service_years" in calc
        assert "severance_exemption_cap" in calc
        
        # Verify calculation logic
        assert calc["service_years"] == 4.0  # 2020-2024
        assert calc["indexed_amount"] == 80000.0  # Stub indexing
        assert calc["grant_exempt"] >= 0
        assert calc["grant_taxable"] >= 0
        assert calc["tax_due"] >= 0
        assert calc["grant_exempt"] + calc["grant_taxable"] == calc["indexed_amount"]
    
    def test_add_grant_client_not_found_404(self, _test_db):
        """Test adding grant for non-existent client returns 404"""
        client = TestClient(fastapi_app)
        
        grant_data = {
            "grant_type": "severance",
            "grant_amount": 50000.0,
            "grant_date": "2024-01-01"
        }
        
        response = client.post("/api/v1/clients/999/current-employer/grants", json=grant_data)
        
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "לקוח לא נמצא"
    
    def test_add_grant_no_current_employer_404(self, _test_db, client):
        """Test adding grant when no current employer exists returns 404"""
        import uuid
        Session = _test_db["Session"]
        
        # Generate a unique ID for this test run
        unique_id = f"test{uuid.uuid4().hex[:8]}"
        
        # Create a new client without current employer
        with Session() as db:
            # First check if a client with this ID already exists
            existing = db.query(Client).filter(Client.id_number == unique_id).first()
            if existing:
                client_id = existing.id
            else:
                test_client = Client(
                    id_number_raw=unique_id,
                    id_number=unique_id,
                    full_name="Client Without Current Employer",
                    birth_date=date(1990, 3, 10),
                    is_active=True
                )
                db.add(test_client)
                db.commit()
                db.refresh(test_client)
                client_id = test_client.id
        
        grant_data = {
            "grant_type": "severance",
            "grant_amount": 50000.0,
            "grant_date": "2024-01-01"
        }
        
        response = client.post(f"/api/v1/clients/{client_id}/current-employer/grants", json=grant_data)
        
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "אין מעסיק נוכחי רשום ללקוח"
    
    def test_add_multiple_grants_calculation(self, _test_db):
        """Test adding multiple grants and verify calculations"""
        client = TestClient(fastapi_app)
        
        # Create employer with longer service period
        employer_data = {
            "employer_name": "חברת MNO",
            "start_date": "2015-01-01",
            "end_date": "2024-01-01",
            "last_salary": 25000.0,
            "average_salary": 22000.0
        }
        
        create_response = client.post("/api/v1/clients/1/employment/current", json=employer_data)
        assert create_response.status_code in [200, 201]
        
        # Add first grant
        grant1_data = {
            "grant_type": "severance",
            "grant_amount": 120000.0,
            "grant_date": "2024-01-01"
        }
        
        grant1_response = client.post("/api/v1/clients/1/current-employer/grants", json=grant1_data)
        assert grant1_response.status_code == 201
        
        calc1 = grant1_response.json()["calculation"]
        assert calc1["service_years"] == 9.0  # 2015-2024
        
        # Add second grant
        grant2_data = {
            "grant_type": "adjustment",
            "grant_amount": 30000.0,
            "grant_date": "2024-02-01"
        }
        
        grant2_response = client.post("/api/v1/clients/1/current-employer/grants", json=grant2_data)
        assert grant2_response.status_code == 201
        
        calc2 = grant2_response.json()["calculation"]
        assert calc2["service_years"] == 9.0  # Same employer, same service years
