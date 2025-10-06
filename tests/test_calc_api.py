# tests/test_calc_api.py
import pytest
import uuid
from datetime import date
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.models import Client, Employer, Employment

client = TestClient(fastapi_app)

def _create_active_client_and_employment(db):
    # ׳³ג„¢׳³ֲ¦׳³ג„¢׳³ֲ¨׳³ֳ— ׳³ֲ׳³ג€“׳³ג€׳³ג„¢׳³ֲ ׳³ג„¢׳³ג„¢׳³ג€”׳³ג€¢׳³ג€׳³ג„¢׳³ג„¢׳³ֲ ׳³ֲ׳³ג€÷׳³ֲ ׳³ג€˜׳³ג€׳³ג„¢׳³ֲ§׳³ג€
    from tests.utils import gen_valid_id
    unique_suffix = str(uuid.uuid4())[:8]
    id_number = gen_valid_id()  # ׳³ֲ׳³ֲ¡׳³ג‚×׳³ֲ¨ ׳³ג€“׳³ג€׳³ג€¢׳³ֳ— ׳³ג„¢׳³ג„¢׳³ג€”׳³ג€¢׳³ג€׳³ג„¢ ׳³ֲ¢׳³ֲ ׳³ג€”׳³ג„¢׳³ֲ©׳³ג€¢׳³ג€˜ ׳³ג€˜׳³ג„¢׳³ֲ§׳³ג€¢׳³ֲ¨׳³ֳ— ׳³ֳ—׳³ֲ§׳³ג„¢׳³ֲ
    email = f"test_{unique_suffix}@test.com"
    employer_reg = f"12345678{hash(unique_suffix) % 10}"
    
    c = Client(
        id_number_raw=id_number,
        id_number=id_number,
        full_name="׳³ג„¢׳³ֲ©׳³ֲ¨׳³ֲ׳³ֲ ׳³ג„¢׳³ֲ©׳³ֲ¨׳³ֲ׳³ֲ׳³ג„¢",
        birth_date=date(1980,1,1),
        email=email, phone="0500000000",
        is_active=True
    )
    db.add(c); db.commit(); db.refresh(c)
    
    employer = Employer(
        name=f"׳³ֲ׳³ֲ¢׳³ֲ¡׳³ג„¢׳³ֲ§ ׳³ג€˜׳³ג€׳³ג„¢׳³ֲ§׳³ג€ {unique_suffix[:4]}",
        reg_no=employer_reg
    )
    db.add(employer); db.commit(); db.refresh(employer)
    
    emp = Employment(client_id=c.id, employer_id=employer.id, start_date=date(2023,1,1), is_current=True)
    db.add(emp); db.commit()
    return c.id

def test_calc_endpoint_200(_test_db):
    # ׳³ֲ ׳³ג„¢׳³ג€™׳³ֲ© ׳³ֲ׳²ֲ¾DB ׳³ֲ׳³ג€׳²ֲ¾override
    Session = _test_db["Session"]
    with Session() as db:
        cid = _create_active_client_and_employment(db)

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

def test_calc_endpoint_inactive_client(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ׳³ֲ ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ
    Session = _test_db["Session"]
    with Session() as db:
        from tests.utils import gen_valid_id
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = gen_valid_id()  # ׳³ֲ׳³ֲ¡׳³ג‚×׳³ֲ¨ ׳³ג€“׳³ג€׳³ג€¢׳³ֳ— ׳³ג„¢׳³ג„¢׳³ג€”׳³ג€¢׳³ג€׳³ג„¢ ׳³ֲ¢׳³ֲ ׳³ג€”׳³ג„¢׳³ֲ©׳³ג€¢׳³ג€˜ ׳³ג€˜׳³ג„¢׳³ֲ§׳³ג€¢׳³ֲ¨׳³ֳ— ׳³ֳ—׳³ֲ§׳³ג„¢׳³ֲ
        email = f"inactive_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="׳³ֲ׳³ֲ ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ",
            birth_date=date(1980,1,1),
            email=email, phone="0500000000",
            is_active=False
        )
        db.add(c); db.commit(); db.refresh(c)
        client_id = c.id
        
    payload = {"monthly_expenses": 5000.0}
    res = client.post(f"/api/v1/calc/{client_id}", json=payload)
    assert res.status_code == 400
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0

def test_create_scenario_201_and_fetch_returns_same_values(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³׳³ֲ§׳³ג€¢׳³ג€” ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ ׳³ֲ¢׳³ ׳³ֳ—׳³ֲ¢׳³ֲ¡׳³ג€¢׳³ֲ§׳³"
    Session = _test_db["Session"]
    with Session() as db:
        cid = _create_active_client_and_employment(db)

    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ג€”׳³ג€׳³ֲ©
    create_payload = {
        "scenario_name": "׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ג€˜׳³ג€׳³ג„¢׳³ֲ§׳³ג€",
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
    
    # ׳³ג€˜׳³ג€¢׳³ג€׳³ֲ§ ׳³ֲ©׳³ג€׳³ֳ—׳³ג€™׳³ג€¢׳³ג€˜׳³ג€ ׳³ֲ׳³ג€÷׳³ג„¢׳³ֲ׳³ג€ scenario_id
    assert "scenario_id" in create_data
    scenario_id = create_data["scenario_id"]
    
    # ׳³ג€׳³ֲ¨׳³ֲ¦׳³ֳ— ׳³ג€׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ג€÷׳³ג€׳³ג„¢ ׳³ֲ׳³ֲ§׳³ג€˜׳³ֲ ׳³ֳ—׳³ג€¢׳³ֲ¦׳³ֲ׳³ג€¢׳³ֳ—
    run_res = client.post(f"/api/v1/scenarios/{scenario_id}/run")
    assert run_res.status_code == 200, run_res.text
    run_data = run_res.json()
    
    # ׳³ג€˜׳³ג€¢׳³ג€׳³ֲ§ ׳³ֲ©׳³ג€׳³ֳ—׳³ג€™׳³ג€¢׳³ג€˜׳³ג€ ׳³ֲ׳³ג€÷׳³ג„¢׳³ֲ׳³ג€ ׳³ֲ׳³ֳ— ׳³ג€÷׳³ֲ ׳³ג€׳³ֲ©׳³ג€׳³ג€¢׳³ֳ— ׳³ג€׳³ֲ ׳³ג€׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor", "cashflow"]:
        assert key in run_data
    assert len(run_data["cashflow"]) >= 12
    
    # ׳³ֲ©׳³ג€¢׳³ֲ׳³ֲ£ ׳³ֲ׳³ֳ— ׳³ג€׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ג€׳³ג€˜׳³ֲ¡׳³ג„¢׳³ֲ¡ ׳³ֲ ׳³ֳ—׳³ג€¢׳³ֲ ׳³ג„¢׳³ֲ ׳³ג€¢׳³ג€˜׳³ג€¢׳³ג€׳³ֲ§ ׳³ֲ©׳³ג€׳³ֲ¢׳³ֲ¨׳³ג€÷׳³ג„¢׳³ֲ ׳³ג€“׳³ג€׳³ג„¢׳³ֲ
    get_res = client.get(f"/api/v1/scenarios/{scenario_id}")
    assert get_res.status_code == 200, get_res.text
    get_data = get_res.json()
    
    # ׳³ג€׳³ֲ©׳³ג€¢׳³ג€¢׳³ֲ׳³ֳ— ׳³ֲ¢׳³ֲ¨׳³ג€÷׳³ג„¢׳³ֲ ׳³ֲ¢׳³ג„¢׳³ֲ§׳³ֲ¨׳³ג„¢׳³ג„¢׳³ֲ (׳³ג€˜׳³ג„¢׳³ֲ run ׳³ֲ׳³ג€˜׳³ג„¢׳³ֲ get)
    for key in ["seniority_years", "grant_gross", "grant_exempt", "grant_tax", 
                "grant_net", "pension_monthly", "indexation_factor"]:
        assert get_data[key] == run_data[key], f"Mismatch in {key}: {get_data[key]} != {run_data[key]}"
    
    # ׳³ג€˜׳³ג€׳³ג„¢׳³ֲ§׳³ֳ— ׳³ֳ—׳³ג€“׳³ֲ¨׳³ג„¢׳³ֲ
    assert len(get_data["cashflow"]) == len(run_data["cashflow"])
    for i, (get_cf, run_cf) in enumerate(zip(get_data["cashflow"], run_data["cashflow"])):
        for cf_key in ["date", "inflow", "outflow", "net"]:
            assert get_cf[cf_key] == run_cf[cf_key], f"Cashflow mismatch at index {i}, key {cf_key}"

def test_list_scenarios_returns_created_item(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ ׳³ֲ¢׳³ֲ ׳³ֳ—׳³ֲ¢׳³ֲ¡׳³ג€¢׳³ֲ§׳³ג€
    Session = _test_db["Session"]; db = Session()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ג€”׳³ג€׳³ֲ©
    create_payload = {
        "scenario_name": "׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ג€",
        "planned_termination_date": date(2025,6,1).isoformat(),
        "monthly_expenses": 6000.0,
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    create_res = client.post(f"/api/v1/clients/{cid}/scenarios", json=create_payload)
    assert create_res.status_code == 201
    scenario_id = create_res.json()["scenario_id"]
    
    # ׳³ֲ©׳³ג€¢׳³ֲ׳³ֲ£ ׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ֳ— ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ©׳³ג„¢׳³ֲ
    list_res = client.get(f"/api/v1/clients/{cid}/scenarios")
    assert list_res.status_code == 200, list_res.text
    list_data = list_res.json()
    
    # ׳³ג€˜׳³ג€¢׳³ג€׳³ֲ§ ׳³ֲ©׳³ג€׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ג€ ׳³ֲ׳³ג€÷׳³ג„¢׳³ֲ׳³ג€ ׳³ֲ׳³ֳ— ׳³ג€׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ©׳³ֲ ׳³ג€¢׳³ֲ¦׳³ֲ¨
    assert "scenarios" in list_data
    scenarios = list_data["scenarios"]
    assert len(scenarios) >= 1
    
    # ׳³ֲ׳³ג€¢׳³ֲ¦׳³ֲ ׳³ֲ׳³ֳ— ׳³ג€׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ©׳³ֲ ׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ג€˜׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ג€
    found_scenario = None
    for s in scenarios:
        if s["id"] == scenario_id:
            found_scenario = s
            break
    
    assert found_scenario is not None, f"Scenario {scenario_id} not found in list"
    assert found_scenario["scenario_name"] == "׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ג€"
    assert "created_at" in found_scenario

def test_create_scenario_404_client_not_found():
    # ׳³ֲ׳³ֲ ׳³ֲ¡׳³ג€ ׳³ֲ׳³ג„¢׳³ֲ¦׳³ג€¢׳³ֲ¨ ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ©׳³ֲ׳³ֲ ׳³ֲ§׳³ג„¢׳³ג„¢׳³ֲ
    create_payload = {
        "scenario_name": "׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ׳³ֲ ׳³ֲ§׳³ג„¢׳³ג„¢׳³ֲ",
        "monthly_expenses": 5000.0,
        "planned_termination_date": "2025-06-30",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    res = client.post("/api/v1/clients/99999/scenarios", json=create_payload)
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_400_inactive_client(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ׳³ֲ ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ
    Session = _test_db["Session"]; db = Session()
    try:
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = f"33333333{hash(unique_suffix) % 10}"
        email = f"inactive_scenario_{unique_suffix}@test.com"
        
        c = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="׳³ֲ׳³ֲ ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ ׳³ֲ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ©",
            birth_date=date(1980,1,1),
            email=email, phone="0500000000",
            is_active=False
        )
        db.add(c); db.commit(); db.refresh(c)
        client_id = c.id
    finally:
        db.close()
        
    create_payload = {
        "scenario_name": "׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ׳³ֲ ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ",
        "monthly_expenses": 5000.0,
        "planned_termination_date": "2025-06-30",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    res = client.post(f"/api/v1/clients/{client_id}/scenarios", json=create_payload)
    assert res.status_code == 400
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_get_scenario_404_scenario_not_found(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ ׳³ֲ¢׳³ֲ ׳³ֳ—׳³ֲ¢׳³ֲ¡׳³ג€¢׳³ֲ§׳³ג€
    Session = _test_db["Session"]; db = Session()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳³ֲ׳³ֲ ׳³ֲ¡׳³ג€ ׳³ֲ׳³ֲ©׳³ֲ׳³ג€¢׳³ֲ£ ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ©׳³ֲ׳³ֲ ׳³ֲ§׳³ג„¢׳³ג„¢׳³ֲ
    res = client.get(f"/api/v1/scenarios/99999")
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_list_scenarios_404_client_not_found():
    # ׳³ֲ׳³ֲ ׳³ֲ¡׳³ג€ ׳³ֲ׳³ֲ©׳³ֲ׳³ג€¢׳³ֲ£ ׳³ֲ¨׳³ֲ©׳³ג„¢׳³ֲ׳³ֳ— ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ©׳³ג„¢׳³ֲ ׳³ֲ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ֲ©׳³ֲ׳³ֲ ׳³ֲ§׳³ג„¢׳³ג„¢׳³ֲ
    res = client.get("/api/v1/clients/99999/scenarios")
    assert res.status_code == 404
    detail = res.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_422_invalid_scenario_name(_test_db):
    # ׳³ג„¢׳³ג€¢׳³ֲ¦׳³ֲ¨ ׳³ֲ׳³ֲ§׳³ג€¢׳³ג€” ׳³ג‚×׳³ֲ¢׳³ג„¢׳³ֲ ׳³ֲ¢׳³ֲ ׳³ֳ—׳³ֲ¢׳³ֲ¡׳³ג€¢׳³ֲ§׳³ג€
    Session = _test_db["Session"]; db = Session()
    try:
        cid = _create_active_client_and_employment(db)
    finally:
        db.close()

    # ׳³ֲ׳³ֲ ׳³ֲ¡׳³ג€ ׳³ֲ׳³ג„¢׳³ֲ¦׳³ג€¢׳³ֲ¨ ׳³ֳ—׳³ֲ¨׳³ג€”׳³ג„¢׳³ֲ© ׳³ֲ¢׳³ֲ ׳³ֲ©׳³ֲ ׳³ֲ¨׳³ג„¢׳³ֲ§
    create_payload = {
        "scenario_name": "",  # ׳©׳ ׳¨׳™׳§,
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

