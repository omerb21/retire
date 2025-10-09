from app.database import SessionLocal
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.current_employer import CurrentEmployer
from app.models.employer_grant import EmployerGrant

def check_client():
    db = SessionLocal()
    try:
        # Find client
        client = db.query(Client).filter(Client.id_number == '123456789').first()
        if not client:
            print("Client not found!")
            return
            
        print(f"Client: {client.first_name} {client.last_name}")
        print(f"Gender: {client.gender}")
        print(f"Tax Credit Points: {client.tax_credit_points}")
        print(f"Pension Start Date: {client.pension_start_date}")
        
        # Check pension funds
        pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client.id).all()
        print(f"\nPension Funds: {len(pension_funds)}")
        for pf in pension_funds:
            print(f"- {pf.fund_name}: {pf.pension_amount} starting {pf.pension_start_date}")
            
        # Check current employer
        employers = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client.id).all()
        print(f"\nEmployers: {len(employers)}")
        for emp in employers:
            print(f"- {emp.employer_name}: {emp.last_salary} starting {emp.start_date}")
            
            # Check grants for this employer
            grants = db.query(EmployerGrant).filter(EmployerGrant.employer_id == emp.id).all()
            print(f"  Grants: {len(grants)}")
            for grant in grants:
                print(f"  - {grant.grant_type}: {grant.grant_amount} on {grant.grant_date}")
                if hasattr(grant, 'work_start_date') and grant.work_start_date:
                    print(f"    Work period: {grant.work_start_date} to {grant.work_end_date}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_client()
