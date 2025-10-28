from app.database import SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.pension_fund import PensionFund
from app.models.fixation_result import FixationResult

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
    total_additional_monthly = 0
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
        total_additional_monthly += monthly
        print(f"  - {income.description or income.source_type}: ₪{monthly:,.2f}/חודש (סכום: ₪{amount:,.2f}, תדירות: {income.frequency})")
        print(f"    סוג: {income.source_type}, יחס למס: {income.tax_treatment}")
    print(f"  סה״כ הכנסות נוספות חודשיות: ₪{total_additional_monthly:,.2f}")
    
    # Get pension funds
    pensions = db.query(PensionFund).filter(PensionFund.client_id == 4).all()
    print(f"\nקצבאות ({len(pensions)}):")
    total_pension_monthly = 0
    total_capital = 0
    for pension in pensions:
        pension_amount = pension.pension_amount or pension.computed_monthly_amount or pension.monthly_amount or 0
        total_pension_monthly += pension_amount
        print(f"  - {pension.fund_name}: ₪{pension_amount:,.2f}/חודש")
        print(f"    תאריך התחלה: {pension.pension_start_date or pension.start_date}")
        if pension.balance:
            total_capital += pension.balance
    print(f"  סה״כ קצבאות חודשיות: ₪{total_pension_monthly:,.2f}")
    
    # Get fixation data
    fixation = db.query(FixationResult).filter(FixationResult.client_id == 4).first()
    print(f"\nנתוני קיבוע זכויות:")
    if fixation:
        print(f"  סכום פטור נותר: ₪{fixation.exempt_capital_remaining:,.2f}")
        print(f"  קצבה פטורה חודשית: ₪{fixation.exempt_capital_remaining / 180:,.2f}")
    else:
        print(f"  ❌ אין נתוני קיבוע זכויות")
    
    # Calculate NPV
    print(f"\nחישוב NPV (DCF):")
    print(f"  הון חד-פעמי: ₪{total_capital:,.2f}")
    print(f"  קצבה חודשית: ₪{total_pension_monthly:,.2f}")
    print(f"  הכנסה נוספת חודשית: ₪{total_additional_monthly:,.2f}")
    
    # NPV calculation with DCF
    discount_rate = 0.05
    years = 30
    npv = float(total_capital)
    monthly_income = total_pension_monthly + total_additional_monthly
    annual_income = monthly_income * 12
    
    for year in range(1, years + 1):
        discounted_cashflow = annual_income / ((1 + discount_rate) ** year)
        npv += discounted_cashflow
    
    print(f"  שיעור היוון: 5%")
    print(f"  תקופת הקרנה: 30 שנים")
    print(f"  NPV מחושב: ₪{npv:,.2f}")
    
else:
    print("לקוח 4 לא נמצא")

db.close()
