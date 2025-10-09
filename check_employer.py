from app.database import SessionLocal
from app.models.current_employer import CurrentEmployer

def check_employer():
    db = SessionLocal()
    try:
        employers = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == 1).all()
        print(f'Found {len(employers)} employers')
        for emp in employers:
            print(f'- {emp.employer_name}: {emp.last_salary}')
            print(f'  ID: {emp.id}, Start: {emp.start_date}')
            print(f'  Severance: {emp.severance_accrued}')
    finally:
        db.close()

if __name__ == "__main__":
    check_employer()
