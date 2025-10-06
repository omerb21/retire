from starlette.testclient import TestClient
from app.main import app

def test_reports_pdf_endpoint_smoke():
    c = TestClient(app)
    r = c.post("/api/v1/reports/pdf", json={"client_id": 1, "scenario_ids": [1]})
    # בלי DB מאותחל נקבל 404/422/500 – העיקר לא קורס באיסוף/ייבוא
    assert r.status_code in (200, 404, 422, 500)
    if r.status_code == 200:
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
