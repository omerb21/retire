# tests/test_calc_api.py
import pytest
import uuid
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import get_db, Base
from app.models import Client, Employer, Employment

# Global test database setup
test_engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
Base.metadata.create_all(bind=test_engine)
TestSessionLocal = sessionmaker(bind=test_engine)

def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

def _create_active_client_and_employment(db):
    # יצירת מזהים ייחודיים לכל בדיקה
    from tests.utils import gen_valid_id
    unique_suffix = str(uuid.uuid4())[:8]
    id_number = gen_valid_id()  # מספר זהות ייחודי עם חישוב ביקורת תקין
    email = f"test_{unique_suffix}@test.com"
    employer_reg = f"12345678{hash(unique_suffix) % 10}"
    
    c = Client(
        id_number_raw=id_number,
        id_number=id_number,
        full_name="ישראל ישראלי",
        birth_date=date(1980,1,1),
        email=email, phone="0500000000",
        is_active=True
    )
    db.add(c); db.commit(); db.refresh(c)
    
    employer = Employer(
        name=f"מעסיק בדיקה {unique_suffix[:4]}",
        reg_no=employer_reg
    )
    db.add(employer); db.commit(); db.refresh(employer)
    
    emp = Employment(client_id=c.id, employer_id=employer.id, start_date=date(2023,1,1), is_current=True)
    db.add(emp); db.commit()
    return c.id

def test_calc_endpoint_200():
    # ניגש ל־DB מה־override
    db = TestSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    payload = {
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 8000.0,
        "other_incomes_monthly": None
    }
    res = client.post(f"/api/v1/calc/{cid}", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for key in ["seniority_years","grant_gross","grant_exempt",
                "grant_tax","grant_net","pension_monthly","indexation_factor","cashflow"]:
        assert key in data
    assert len(data["cashflow"]) == 12

def test_calc_endpoint_client_not_found():
    payload = {"monthly_expenses": 5000.0}
    res = client.post("/api/v1/calc/9999", json=payload)
    assert res.status_code == 404
    assert "לקוח לא נמצא" in res.text

def test_calc_endpoint_inactive_client():
    # יוצר לקוח לא פעיל
    db = TestSessionLocal()
    try:
        from tests.utils import gen_valid_id
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = gen_valid_id()  # מספר זהות ייחודי עם חישוב ביקורת תקין
        email = f"inactive_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="לא פעיל",
            birth_date=date(1980,1,1),
            email=email, phone="0500000000",
            is_active=False
        )
        db.add(c); db.commit(); db.refresh(c)
        client_id = c.id
    finally:
        db.close()
        
    payload = {"monthly_expenses": 5000.0}
    res = client.post(f"/api/v1/calc/{client_id}", json=payload)
    assert res.status_code == 400
    assert "הלקוח אינו פעיל" in res.text

def test_create_scenario_201_and_fetch_returns_same_values():
    # יוצר לקוח פעיל עם תעסוקה
    db = TestSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # יוצר תרחיש חדש
    create_payload = {
        "scenario_name": "תרחיש בדיקה",
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 7500.0,
        "other_incomes_monthly": None
    }
    
    create_res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert create_res.status_code == 201, create_res.text
    create_data = create_res.json()
    
    # בודק שהתגובה מכילה את כל השדות הנדרשים
    assert "scenario_id" in create_data
    scenario_id = create_data["scenario_id"]
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor", "cashflow"]:
        assert key in create_data
    assert len(create_data["cashflow"]) == 12
    
    # שולף את התרחיש מהבסיס נתונים ובודק שהערכים זהים
    get_res = client.get(f"/api/v1/clients/{cid}/scenarios/{scenario_id}")
    assert get_res.status_code == 200, get_res.text
    get_data = get_res.json()
    
    # השוואת ערכים עיקריים (ללא scenario_id שקיים רק ב-create)
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor"]:
        assert get_data[key] == create_data[key], f"Mismatch in {key}: {get_data[key]} != {create_data[key]}"
    
    # בדיקת תזרים
    assert len(get_data["cashflow"]) == len(create_data["cashflow"])
    for i, (get_cf, create_cf) in enumerate(zip(get_data["cashflow"], create_data["cashflow"])):
        for cf_key in ["date", "inflow", "outflow", "net"]:
            assert get_cf[cf_key] == create_cf[cf_key], f"Cashflow mismatch at index {i}, key {cf_key}"

def test_list_scenarios_returns_created_item():
    # יוצר לקוח פעיל עם תעסוקה
    db = TestSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # יוצר תרחיש חדש
    create_payload = {
        "scenario_name": "תרחיש לרשימה",
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 6000.0
    }
    
    create_res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert create_res.status_code == 201
    scenario_id = create_res.json()["scenario_id"]
    
    # שולף רשימת תרחישים
    list_res = client.get(f"/api/v1/clients/{cid}/scenarios")
    assert list_res.status_code == 200, list_res.text
    list_data = list_res.json()
    
    # בודק שהרשימה מכילה את התרחיש שנוצר
    assert "scenarios" in list_data
    scenarios = list_data["scenarios"]
    assert len(scenarios) >= 1
    
    # מוצא את התרחיש שנוצר ברשימה
    found_scenario = None
    for s in scenarios:
        if s["id"] == scenario_id:
            found_scenario = s
            break
    
    assert found_scenario is not None, f"Scenario {scenario_id} not found in list"
    assert found_scenario["scenario_name"] == "תרחיש לרשימה"
    assert "created_at" in found_scenario

def test_create_scenario_404_client_not_found():
    # מנסה ליצור תרחיש ללקוח שלא קיים
    create_payload = {
        "scenario_name": "תרחיש ללקוח לא קיים",
        "monthly_expenses": 5000.0
    }
    
    res = client.post("/api/v1/clients/99999/scenarios", json=create_payload)
    assert res.status_code == 404
    assert "לקוח לא נמצא" in res.text

def test_create_scenario_400_inactive_client():
    # יוצר לקוח לא פעיל
    db = TestSessionLocal()
    try:
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = f"33333333{hash(unique_suffix) % 10}"
        email = f"inactive_scenario_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="לא פעיל לתרחיש",
            birth_date=date(1980,1,1),
            email=email, phone="0500000000",
            is_active=False
        )
        db.add(c); db.commit(); db.refresh(c)
        client_id = c.id
    finally:
        db.close()
        
    create_payload = {
        "scenario_name": "תרחיש ללקוח לא פעיל",
        "monthly_expenses": 5000.0
    }
    
    res = client.post(f"/api/v1/clients/{client_id}/scenarios", json=create_payload)
    assert res.status_code == 400
    assert "הלקוח אינו פעיל" in res.text

def test_get_scenario_404_scenario_not_found():
    # יוצר לקוח פעיל עם תעסוקה
    db = TestSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # מנסה לשלוף תרחיש שלא קיים
    res = client.get(f"/api/v1/clients/{cid}/scenarios/99999")
    assert res.status_code == 404
    assert "תרחיש לא נמצא" in res.text

def test_list_scenarios_404_client_not_found():
    # מנסה לשלוף רשימת תרחישים ללקוח שלא קיים
    res = client.get("/api/v1/clients/99999/scenarios")
    assert res.status_code == 404
    assert "לקוח לא נמצא" in res.text

def test_create_scenario_422_invalid_scenario_name():
    # יוצר לקוח פעיל עם תעסוקה
    db = TestSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # מנסה ליצור תרחיש עם שם ריק
    create_payload = {
        "scenario_name": "",  # שם ריק
        "monthly_expenses": 5000.0
    }
    
    res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert res.status_code == 422
