from app.database import SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.pension_fund import PensionFund

db = SessionLocal()

# Get client 4
client = db.query(Client).filter(Client.id == 4).first()
if client:
    print(f"\n{'='*80}")
    print(f"לקוח מספר 4: {client.full_name}")
    print(f"{'='*80}\n")
    
    # Get additional incomes
    incomes = db.query(AdditionalIncome).filter(AdditionalIncome.client_id == 4).all()
    print(f"הכנסות נוספות ({len(incomes)}):")
    for income in incomes:
        amount = float(income.amount)
        if income.frequency == 'monthly':
            monthly = amount
        elif income.frequency == 'quarterly':
            monthly = amount / 3
        elif income.frequency == 'annually':
            monthly = amount / 12
        else:
            monthly = amount
        print(f"  - {income.description or income.source_type}: ₪{monthly:,.2f}/חודש (סכום: ₪{amount:,.2f}, תדירות: {income.frequency})")
        print(f"    סוג: {income.source_type}, יחס למס: {income.tax_treatment}")
    
    # Get pension funds
    pensions = db.query(PensionFund).filter(PensionFund.client_id == 4).all()
    print(f"\nקצבאות ({len(pensions)}):")
    for pension in pensions:
        print(f"  - {pension.fund_name}: ₪{pension.pension_amount or pension.computed_monthly_amount or pension.monthly_amount or 0:,.2f}/חודש")
        print(f"    תאריך התחלה: {pension.pension_start_date or pension.start_date}")
else:
    print("לקוח 4 לא נמצא")

db.close()
