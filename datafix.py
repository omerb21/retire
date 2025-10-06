import requests

# מחק את כל המענקים הקיימים של לקוח 1
response = requests.get('http://localhost:8005/api/v1/clients/1/grants')
if response.status_code == 200:
    grants = response.json()
    for grant in grants:
        grant_id = grant['id']
        requests.post(f'http://localhost:8005/api/v1/grants/{grant_id}/delete')

# הוסף את שלושת המענקים החדשים
grants = [
    {
        "client_id": 1,
        "grant_amount": 100000,
        "work_start_date": "1980-01-01",
        "work_end_date": "2010-01-01",
        "grant_date": "2010-01-01",
        "employer_name": "מעסיק ראשון",
        "grant_type": "severance",
        "grant_year": 2010
    },
    {
        "client_id": 1,
        "grant_amount": 50000,
        "work_start_date": "2010-01-01",
        "work_end_date": "2015-01-01",
        "grant_date": "2015-01-01",
        "employer_name": "מעסיק שני",
        "grant_type": "severance",
        "grant_year": 2015
    },
    {
        "client_id": 1,
        "grant_amount": 75000,
        "work_start_date": "2015-01-01",
        "work_end_date": "2020-01-01",
        "grant_date": "2020-01-01",
        "employer_name": "מעסיק שלישי",
        "grant_type": "severance",
        "grant_year": 2020
    }
]

for grant in grants:
    response = requests.post('http://localhost:8005/api/v1/grants', json=grant)
    print(f"הוספת מענק: {response.status_code}")

print("סיום עדכון המענקים")