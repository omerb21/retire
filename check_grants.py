from app.database import SessionLocal
from app.models.employer_grant import EmployerGrant

def check_grants():
    db = SessionLocal()
    try:
        grants = db.query(EmployerGrant).filter(EmployerGrant.employer_id == 1).all()
        print(f'Found {len(grants)} grants')
        for grant in grants:
            print(f'- {grant.grant_type}: {grant.grant_amount} on {grant.grant_date}')
    finally:
        db.close()

if __name__ == "__main__":
    check_grants()
