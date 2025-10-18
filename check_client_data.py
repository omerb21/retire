"""
בדיקת נתוני לקוח 4
"""
from app.database import SessionLocal
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome

db = SessionLocal()

client_id = 4

print("=" * 60)
print(f"בדיקת נתונים עבור לקוח {client_id}")
print("=" * 60)

# בדיקת קצבאות
pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
print(f"\n📊 קצבאות (PensionFund): {len(pension_funds)}")
for pf in pension_funds:
    print(f"  - {pf.fund_name}: {pf.balance} ₪ (קצבה: {pf.pension_amount}, annuity: {pf.annuity_factor})")

# בדיקת נכסי הון
capital_assets = db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).all()
print(f"\n💰 נכסי הון (CapitalAsset): {len(capital_assets)}")
for ca in capital_assets:
    print(f"  - {ca.asset_name}: {ca.current_value} ₪ (סוג: {ca.asset_type}, מס: {ca.tax_treatment})")

# בדיקת הכנסות נוספות
additional_incomes = db.query(AdditionalIncome).filter(AdditionalIncome.client_id == client_id).all()
print(f"\n💵 הכנסות נוספות (AdditionalIncome): {len(additional_incomes)}")
for ai in additional_incomes:
    print(f"  - {ai.description}: {ai.amount} ₪ (סוג: {ai.source_type}, תדירות: {ai.frequency})")

# סכום כולל
total_pension_value = sum(float(pf.balance or 0) for pf in pension_funds)
total_capital_value = sum(float(ca.current_value or 0) for ca in capital_assets)
print(f"\n💎 סה\"כ ערך נכסים:")
print(f"  קצבאות: {total_pension_value:,.0f} ₪")
print(f"  הון: {total_capital_value:,.0f} ₪")
print(f"  סה\"כ: {total_pension_value + total_capital_value:,.0f} ₪")

db.close()
