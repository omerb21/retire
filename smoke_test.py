import sys,random
sys.path.append('.')
from fastapi.testclient import TestClient
from app.main import app
from datetime import date, timedelta

# מחולל ת"ז ישראלית תקינה (Checksum)
def gen_israeli_id():
    # Generate 8 random digits
    first8 = str(random.randint(10000000, 99999999))
    total = 0
    for i, ch in enumerate(first8):
        d = int(ch)
        factor = 1 if i % 2 == 0 else 2
        x = d * factor
        if x > 9: x -= 9
        total += x
    check = (10 - (total % 10)) % 10
    return first8 + str(check)

c = TestClient(app)
uid = gen_israeli_id()
r = c.post('/api/v1/clients', json={
    'id_number_raw': uid,
    'full_name': 'ישראל ישראלי',
    'birth_date': '1980-01-01',
    'email': f'ui{random.randint(1000,9999)}@example.com',
    'phone': '0501234567'
})
print('clients:', r.status_code, r.json())
assert r.status_code == 201, 'client create failed'
cid = r.json()['id']

r = c.post(f'/api/v1/clients/{cid}/employment/current', json={
    'employer_name':'חברת טק',
    'employer_reg_no':'123456789',
    'start_date':'2023-01-01'
})
print('employment:', r.status_code, r.json())
assert r.status_code == 201

pd = (date.today() + timedelta(days=30)).isoformat()
r = c.patch(f'/api/v1/clients/{cid}/employment/termination/plan', json={
    'planned_termination_date': pd,
    'termination_reason': 'retired'
})
print('plan:', r.status_code, r.json())

r2 = c.post(f'/api/v1/clients/{cid}/employment/termination/confirm', json={
    'actual_termination_date': date.today().isoformat()
})
print('confirm:', r2.status_code, r2.json())

r = c.post(f'/api/v1/calc/{cid}', json={
    'planned_termination_date':'2025-06-01',
    'monthly_expenses': 8000
})
print('calc:', r.status_code, (list(r.json().keys()) if r.status_code==200 else r.json()))

r = c.post(f'/api/v1/clients/{cid}/scenarios', json={
    'scenario_name':'תרחיש 1',
    'planned_termination_date':'2025-06-01',
    'monthly_expenses':8000
})
print('scenario create:', r.status_code, (r.json().get('scenario_id') if r.status_code==201 else r.json()))
if r.status_code == 201:
    sid = r.json()['scenario_id']
    r = c.get(f'/api/v1/clients/{cid}/scenarios')
    print('scenarios list:', r.status_code, (len(r.json()) if r.status_code==200 else r.json()))
    r = c.get(f'/api/v1/clients/{cid}/scenarios/{sid}')
    print('scenario get:', r.status_code, (list(r.json().keys()) if r.status_code==200 else r.json()))
