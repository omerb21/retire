# tests/test_calc_api.py
import pytest
import uuid
import os
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db, Base
from app.main import app as fastapi_app
from app.models import Client, Employer, Employment

# Global test database setup
test_engine = create_engine("sqlite:///test_suite.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = override_get_db
client = TestClient(fastapi_app)

@pytest.fixture(scope="module", autouse=True)
def teardown_module():
    yield
    # Clean up
    test_engine.dispose()
    if os.path.exists("test_suite.db"):
        os.remove("test_suite.db")

def _create_active_client_and_employment(db):
    # ׳™׳¦׳™׳¨׳× ׳׳–׳”׳™׳ ׳™׳™׳—׳•׳“׳™׳™׳ ׳׳›׳ ׳‘׳“׳™׳§׳”
    from tests.utils import gen_valid_id
    unique_suffix = str(uuid.uuid4())[:8]
    id_number = gen_valid_id()  # ׳׳¡׳₪׳¨ ׳–׳”׳•׳× ׳™׳™׳—׳•׳“׳™ ׳¢׳ ׳—׳™׳©׳•׳‘ ׳‘׳™׳§׳•׳¨׳× ׳×׳§׳™׳
    email = f"test_{unique_suffix}@test.com"
    employer_reg = f"12345678{hash(unique_suffix) % 10}"
    
    c = Client(
        id_number_raw=id_number,
        id_number=id_number,
        full_name="׳™׳©׳¨׳׳ ׳™׳©׳¨׳׳׳™",
        birth_date=date(1980,1,1),
        email=email, phone="0500000000",
        is_active=True
    )
    db.add(c); db.commit(); db.refresh(c)
    
    employer = Employer(
        name=f"׳׳¢׳¡׳™׳§ ׳‘׳“׳™׳§׳” {unique_suffix[:4]}",
        reg_no=employer_reg
    )
    db.add(employer); db.commit(); db.refresh(employer)
    
    emp = Employment(client_id=c.id, employer_id=employer.id, start_date=date(2023,1,1), is_current=True)
    db.add(emp); db.commit()
    return c.id

def test_calc_endpoint_200():
    # ׳ ׳™׳’׳© ׳ײ¾DB ׳׳”ײ¾override
    db = TestingSessionLocal()
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
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_calc_endpoint_inactive_client():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳
    db = TestingSessionLocal()
    try:
        from tests.utils import gen_valid_id
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = gen_valid_id()  # ׳׳¡׳₪׳¨ ׳–׳”׳•׳× ׳™׳™׳—׳•׳“׳™ ׳¢׳ ׳—׳™׳©׳•׳‘ ׳‘׳™׳§׳•׳¨׳× ׳×׳§׳™׳
        email = f"inactive_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="׳׳ ׳₪׳¢׳™׳",
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
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_201_and_fetch_returns_same_values():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳₪׳¢׳™׳ ׳¢׳ ׳×׳¢׳¡׳•׳§׳”
    db = TestingSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳™׳•׳¦׳¨ ׳×׳¨׳—׳™׳© ׳—׳“׳©
    create_payload = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳‘׳“׳™׳§׳”",
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 7500.0,
        "other_incomes_monthly": None,
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    create_res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert create_res.status_code == 201, create_res.text
    create_data = create_res.json()
    
    # ׳‘׳•׳“׳§ ׳©׳”׳×׳’׳•׳‘׳” ׳׳›׳™׳׳” scenario_id
    assert "scenario_id" in create_data
    scenario_id = create_data["scenario_id"]
    
    # ׳”׳¨׳¦׳× ׳”׳×׳¨׳—׳™׳© ׳›׳“׳™ ׳׳§׳‘׳ ׳×׳•׳¦׳׳•׳×
    run_res = client.post(f"/api/v1/scenarios/{scenario_id}/run")
    assert run_res.status_code == 200, run_res.text
    run_data = run_res.json()
    
    # ׳‘׳•׳“׳§ ׳©׳”׳×׳’׳•׳‘׳” ׳׳›׳™׳׳” ׳׳× ׳›׳ ׳”׳©׳“׳•׳× ׳”׳ ׳“׳¨׳©׳™׳
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor", "cashflow"]:
        assert key in run_data
    assert len(run_data["cashflow"]) >= 12
    
    # ׳©׳•׳׳£ ׳׳× ׳”׳×׳¨׳—׳™׳© ׳׳”׳‘׳¡׳™׳¡ ׳ ׳×׳•׳ ׳™׳ ׳•׳‘׳•׳“׳§ ׳©׳”׳¢׳¨׳›׳™׳ ׳–׳”׳™׳
    get_res = client.get(f"/api/v1/scenarios/{scenario_id}")
    assert get_res.status_code == 200, get_res.text
    get_data = get_res.json()
    
    # ׳”׳©׳•׳•׳׳× ׳¢׳¨׳›׳™׳ ׳¢׳™׳§׳¨׳™׳™׳ (׳‘׳™׳ run ׳׳‘׳™׳ get)
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor"]:
        assert get_data[key] == run_data[key], f"Mismatch in {key}: {get_data[key]} != {run_data[key]}"
    
    # ׳‘׳“׳™׳§׳× ׳×׳–׳¨׳™׳
    assert len(get_data["cashflow"]) == len(run_data["cashflow"])
    for i, (get_cf, run_cf) in enumerate(zip(get_data["cashflow"], run_data["cashflow"])):
        for cf_key in ["date", "inflow", "outflow", "net"]:
            assert get_cf[cf_key] == run_cf[cf_key], f"Cashflow mismatch at index {i}, key {cf_key}"

def test_list_scenarios_returns_created_item():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳₪׳¢׳™׳ ׳¢׳ ׳×׳¢׳¡׳•׳§׳”
    db = TestingSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳™׳•׳¦׳¨ ׳×׳¨׳—׳™׳© ׳—׳“׳©
    create_payload = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳¨׳©׳™׳׳”",
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 6000.0,
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    create_res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert create_res.status_code == 201
    scenario_id = create_res.json()["scenario_id"]
    
    # ׳©׳•׳׳£ ׳¨׳©׳™׳׳× ׳×׳¨׳—׳™׳©׳™׳
    list_res = client.get(f"/api/v1/clients/{cid}/scenarios")
    assert list_res.status_code == 200, list_res.text
    list_data = list_res.json()
    
    # ׳‘׳•׳“׳§ ׳©׳”׳¨׳©׳™׳׳” ׳׳›׳™׳׳” ׳׳× ׳”׳×׳¨׳—׳™׳© ׳©׳ ׳•׳¦׳¨
    assert "scenarios" in list_data
    scenarios = list_data["scenarios"]
    assert len(scenarios) >= 1
    
    # ׳׳•׳¦׳ ׳׳× ׳”׳×׳¨׳—׳™׳© ׳©׳ ׳•׳¦׳¨ ׳‘׳¨׳©׳™׳׳”
    found_scenario = None
    for s in scenarios:
        if s["id"] == scenario_id:
            found_scenario = s
            break
    
    assert found_scenario is not None, f"Scenario {scenario_id} not found in list"
    assert found_scenario["scenario_name"] == "׳×׳¨׳—׳™׳© ׳׳¨׳©׳™׳׳”"
    assert "created_at" in found_scenario

def test_create_scenario_404_client_not_found():
    # ׳׳ ׳¡׳” ׳׳™׳¦׳•׳¨ ׳×׳¨׳—׳™׳© ׳׳׳§׳•׳— ׳©׳׳ ׳§׳™׳™׳
    create_payload = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳׳§׳•׳— ׳׳ ׳§׳™׳™׳",
        "monthly_expenses": 5000.0,
        "planned_termination_date": "2025-06-30",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    res = client.post("/api/v1/clients/99999/scenarios", json=create_payload)
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_400_inactive_client():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳
    db = TestingSessionLocal()
    try:
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = f"33333333{hash(unique_suffix) % 10}"
        email = f"inactive_scenario_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="׳׳ ׳₪׳¢׳™׳ ׳׳×׳¨׳—׳™׳©",
            birth_date=date(1980,1,1),
            email=email, phone="0500000000",
            is_active=False
        )
        db.add(c); db.commit(); db.refresh(c)
        client_id = c.id
    finally:
        db.close()
        
    create_payload = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳",
        "monthly_expenses": 5000.0,
        "planned_termination_date": "2025-06-30",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    res = client.post(f"/api/v1/clients/{client_id}/scenarios", json=create_payload)
    assert res.status_code == 400
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_get_scenario_404_scenario_not_found():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳₪׳¢׳™׳ ׳¢׳ ׳×׳¢׳¡׳•׳§׳”
    db = TestingSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳׳ ׳¡׳” ׳׳©׳׳•׳£ ׳×׳¨׳—׳™׳© ׳©׳׳ ׳§׳™׳™׳
    res = client.get(f"/api/v1/scenarios/99999")
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_list_scenarios_404_client_not_found():
    # ׳׳ ׳¡׳” ׳׳©׳׳•׳£ ׳¨׳©׳™׳׳× ׳×׳¨׳—׳™׳©׳™׳ ׳׳׳§׳•׳— ׳©׳׳ ׳§׳™׳™׳
    res = client.get("/api/v1/clients/99999/scenarios")
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_422_invalid_scenario_name():
    # ׳™׳•׳¦׳¨ ׳׳§׳•׳— ׳₪׳¢׳™׳ ׳¢׳ ׳×׳¢׳¡׳•׳§׳”
    db = TestingSessionLocal()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳׳ ׳¡׳” ׳׳™׳¦׳•׳¨ ׳×׳¨׳—׳™׳© ׳¢׳ ׳©׳ ׳¨׳™׳§
    create_payload = {
        "scenario_name": "",  # שם ריק,
        "monthly_expenses": 5000.0,
        "planned_termination_date": "2025-06-30",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert res.status_code == 422

def test_calc_calculate_smoke():
    c = TestClient(fastapi_app)
    r = c.post("/api/v1/calc/1/calculate", json={"scenario_ids": [2, 3]})
    assert r.status_code == 200
    j = r.json()
    assert j["client_id"] == 1
    assert j["scenarios"] == [2, 3]
    assert "engine_version" in j
