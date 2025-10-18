"""Check client 4 pension funds"""
from app.database import get_db
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset

db = next(get_db())

print("=== Client 4 - Pension Funds ===")
pf = db.query(PensionFund).filter(PensionFund.client_id == 4).all()
print(f"Total: {len(pf)} pension funds\n")
for p in pf:
    print(f"📋 {p.fund_name}")
    print(f"   Balance: {p.balance}")
    print(f"   Annuity Factor: {p.annuity_factor}")
    print(f"   Pension Amount: {p.pension_amount}")
    print(f"   Input Mode: {p.input_mode}")
    print(f"   Tax Treatment: {p.tax_treatment}")
    print()

print("=== Client 4 - Capital Assets ===")
ca = db.query(CapitalAsset).filter(CapitalAsset.client_id == 4).all()
print(f"Total: {len(ca)} capital assets\n")
for c in ca:
    print(f"💰 {c.asset_name}")
    print(f"   Value: {c.current_value}")
    print(f"   Type: {c.asset_type}")
    print(f"   Tax Treatment: {c.tax_treatment}")
    print()
