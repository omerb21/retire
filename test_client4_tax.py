"""בדיקת חישוב מס עבור לקוח 4 - הכנסת עסק"""

from datetime import date
from decimal import Decimal
from app.database import SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.services.additional_income_service import AdditionalIncomeService

db = SessionLocal()

# Get client 4
client = db.query(Client).filter(Client.id == 4).first()

# Get business income
business_income = db.query(AdditionalIncome).filter(
    AdditionalIncome.client_id == 4,
    AdditionalIncome.source_type == "business"
).first()

if business_income and client:
    print(f"\n{'='*80}")
    print(f"בדיקת חישוב מס עבור לקוח 4 - הכנסת עסק")
    print(f"{'='*80}\n")
    
    print(f"לקוח: {client.full_name}")
    print(f"תאריך לידה: {client.birth_date}")
    print(f"גיל נוכחי: {client.get_age()} שנים")
    print(f"\nהכנסת עסק:")
    print(f"  סכום: ₪{business_income.amount:,.2f}")
    print(f"  תדירות: {business_income.frequency}")
    print(f"  יחס למס: {business_income.tax_treatment}")
    
    # חישוב מס
    service = AdditionalIncomeService()
    
    # תאריך בדיקה - היום
    test_date = date.today()
    
    # חישוב מס
    tax_amount = service.calculate_tax(
        gross_amount=business_income.amount,
        income=business_income,
        client=client,
        calculation_date=test_date
    )
    
    print(f"\nחישוב מס:")
    print(f"  הכנסה ברוטו: ₪{business_income.amount:,.2f}")
    print(f"  מס מחושב: ₪{tax_amount:,.2f}")
    print(f"  הכנסה נטו: ₪{float(business_income.amount) - float(tax_amount):,.2f}")
    
    # פירוט המס
    from app.services.tax_calculator import TaxCalculator
    tax_calc = TaxCalculator()
    
    annual_income = float(business_income.amount) * 12
    income_tax, _ = tax_calc.calculate_income_tax(annual_income)
    ni_tax = tax_calc.calculate_national_insurance(annual_income)
    
    print(f"\nפירוט המס השנתי:")
    print(f"  מס הכנסה: ₪{income_tax:,.2f} (₪{income_tax/12:,.2f}/חודש)")
    print(f"  ביטוח לאומי: ₪{ni_tax:,.2f} (₪{ni_tax/12:,.2f}/חודש)")
    print(f"  סה״כ: ₪{income_tax + ni_tax:,.2f} (₪{(income_tax + ni_tax)/12:,.2f}/חודש)")
    
    print(f"\n{'='*80}\n")
else:
    print("לא נמצאה הכנסת עסק ללקוח 4")

db.close()
