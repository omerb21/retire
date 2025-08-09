from starlette.testclient import TestClient
from app.main import app

def test_calc_calculate_smoke():
    c = TestClient(app)
    r = c.post("/api/v1/calc/1/calculate", json={"scenario_ids": [2, 3]})
    assert r.status_code == 200
    j = r.json()
    assert j["client_id"] == 1
    assert j["scenarios"] == [2, 3]
    assert "engine_version" in j
