# -*- coding: utf-8 -*-
from starlette.testclient import TestClient
from app.main import app

c = TestClient(app)

def pick_id(obj):
    # נסיונות שכיחים להוציא מזהים ממבני JSON שונים
    if isinstance(obj, dict):
        # direct keys
        for k in ("id", "client_id", "scenario_id"):
            if k in obj and isinstance(obj[k], int):
                return obj[k]
        # nested common envelopes
        for k in ("client", "data", "result"):
            if k in obj and isinstance(obj[k], dict):
                for kk in ("id", "client_id", "scenario_id"):
                    if kk in obj[k] and isinstance(obj[k][kk], int):
                        return obj[k][kk]
    return None

def debug(resp, label):
    try:
        j = resp.json()
    except Exception:
        j = resp.text
    print(f"[{label}] {resp.status_code} {resp.headers.get('content-type')} -> {str(j)[:300]}")

# 1) יצירת לקוח
client_payload = {
    "id_number_raw": "123456782",
    "id_number": "123456782",
    "full_name": "ישראל ישראלי",
    "birth_date": "1980-01-01",
    "email": "israel@test.com",
    "phone": "0500000000",
    "is_active": True,
}
r = c.post("/api/v1/clients", json=client_payload)
debug(r, "create-client")
cid = None
if r.status_code in (200, 201):
    try:
        cid = pick_id(r.json())
    except Exception:
        cid = None
if not cid:
    # 409 או כשל בזיהוי – נאתר לפי חיפוש
    r2 = c.get(f"/api/v1/clients", params={"search": client_payload["id_number"]})
    debug(r2, "list-clients")
    if r2.status_code == 200:
        data = r2.json()
        items = data.get("items") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for x in items:
            if x.get("id_number") == client_payload["id_number"] or x.get("email") == client_payload["email"]:
                cid = x.get("id")
                break
if not cid:
    raise SystemExit("Failed to resolve client id from API responses.")

# 2) יצירת תרחיש
scenario_payload = {
    "scenario_name": "תרחיש בדיקה",
    "monthly_expenses": 5000.0,
    "planned_termination_date": "2026-06-30",
    "apply_tax_planning": False,
    "apply_capitalization": False,
    "apply_exemption_shield": False,
}
r = c.post(f"/api/v1/clients/{cid}/scenarios", json=scenario_payload)
debug(r, "create-scenario")
sid = None
if r.status_code in (200, 201):
    try:
        sid = pick_id(r.json())
    except Exception:
        sid = None
if not sid:
    # גיבוי: רשימת תרחישים ושאיבת האחרון
    r2 = c.get(f"/api/v1/clients/{cid}/scenarios")
    debug(r2, "list-scenarios")
    if r2.status_code == 200:
        data = r2.json()
        scenarios = data.get("scenarios") if isinstance(data, dict) else []
        if scenarios:
            sid = scenarios[-1].get("id") or scenarios[-1].get("scenario_id")
if not sid:
    raise SystemExit("Failed to resolve scenario id from API responses.")

# 2.5) וידוא תעסוקה נוכחית (חובה לפני הרצת תרחיש)
employment_payload = {
    "employer_name": "חברת הטכנולוגיה בע\"מ",
    "employer_reg_no": "123456789",
    "address_city": "תל אביב",
    "address_street": "רחוב הארבעה 10",
    "start_date": "2023-01-01",
    "monthly_salary_nominal": 15000.0,
    "is_current": True
}
re = c.post(f"/api/v1/clients/{cid}/employment/current", json=employment_payload)
debug(re, "set-employment")

# 3) להריץ תרחיש (אם מחזיר 422 בגלל נתוני CPI – ממשיכים)
rr = c.post(f"/api/v1/scenarios/{sid}/run")
debug(rr, "run-scenario")

# 3.5) אם יש שגיאת CPI, ננסה להוסיף נתוני CPI
if rr.status_code == 422 and "CPI" in rr.text:
    print("[CPI-FIX] Adding CPI data for scenario calculation")
    # יצירת נתוני CPI בסיסיים לטווח התאריכים הרלוונטי
    from datetime import datetime, timedelta
    today = datetime.now().date()
    # נוסיף נתוני CPI מ-2022 עד שנתיים קדימה
    start_year = 2022
    end_year = today.year + 2
    
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            cpi_data = {
                "year": year,
                "month": month,
                "value": 100.0 + (year - start_year) * 2.0 + (month / 12.0)
            }
            cpi_resp = c.post("/api/v1/cpi", json=cpi_data)
            if cpi_resp.status_code not in (200, 201, 409):
                print(f"[CPI-ERROR] Failed to add CPI for {year}-{month}: {cpi_resp.status_code}")
    
    # נריץ שוב את התרחיש אחרי הוספת נתוני CPI
    rr = c.post(f"/api/v1/scenarios/{sid}/run")
    debug(rr, "run-scenario-after-cpi")

# 4) ייצוא PDF
r = c.post("/api/v1/reports/pdf", json={"client_id": cid, "scenario_ids": [sid]})
print("STATUS:", r.status_code, "| CT:", r.headers.get("content-type"), "| size:", len(r.content))
print("HEAD:", r.content[:4])

# בדיקת תקינות ה-PDF
assert r.status_code == 200, f"PDF export failed with status {r.status_code}: {r.text}"
assert "application/pdf" in (r.headers.get("content-type") or ""), f"Expected PDF content type, got {r.headers.get('content-type')}"
assert r.content[:4] == b"%PDF", f"Invalid PDF header: {r.content[:20]}"
assert len(r.content) > 10_000, f"PDF too small ({len(r.content)} bytes), likely not a valid report"

with open("report_smoke.pdf", "wb") as f:
    f.write(r.content)
print("Saved to report_smoke.pdf")
