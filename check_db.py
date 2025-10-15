from app.database import SessionLocal
from app.models.pension_fund import PensionFund

db = SessionLocal()

# Get all pension funds for client 4
funds = db.query(PensionFund).filter(PensionFund.client_id == 4).all()

print(f"\n=== Pension Funds for Client 4 ===")
for fund in funds:
    print(f"ID: {fund.id}")
    print(f"  Name: {fund.fund_name}")
    print(f"  Input Mode: {fund.input_mode}")
    print(f"  Balance: {fund.balance}")
    print(f"  Annuity Factor: {fund.annuity_factor}")
    print(f"  Pension Amount: {fund.pension_amount}")
    print(f"  Created: {fund.created_at}")
    print(f"  Updated: {fund.updated_at}")
    print()

db.close()
