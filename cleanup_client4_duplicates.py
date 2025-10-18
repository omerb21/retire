"""
Clean up duplicate pension funds for client 4
"""
from app.database import get_db
from app.models.pension_fund import PensionFund

db = next(get_db())

print("🧹 Cleaning up duplicate pension funds for Client 4...")
print()

# Get all pension funds for client 4
all_pf = db.query(PensionFund).filter(PensionFund.client_id == 4).all()
print(f"Total pension funds before cleanup: {len(all_pf)}")

# Group by deduction_file (account number)
from collections import defaultdict
groups = defaultdict(list)

for pf in all_pf:
    key = (pf.deduction_file, pf.fund_name)
    groups[key].append(pf)

print(f"Unique products: {len(groups)}")
print()

deleted_count = 0

for (account_num, fund_name), products in groups.items():
    if len(products) > 1:
        print(f"📦 {fund_name} (Account: {account_num})")
        print(f"   Found {len(products)} duplicates")
        
        # Keep the one with pension_amount, delete others
        keep = None
        to_delete = []
        
        for p in products:
            if p.pension_amount and p.pension_amount > 0:
                if not keep:
                    keep = p
                else:
                    to_delete.append(p)
            else:
                to_delete.append(p)
        
        # If none have pension_amount, keep the first one
        if not keep and products:
            keep = products[0]
            to_delete = products[1:]
        
        if keep:
            print(f"   ✅ Keeping: ID={keep.id}, Pension={keep.pension_amount}")
        
        for p in to_delete:
            print(f"   ❌ Deleting: ID={p.id}, Pension={p.pension_amount}")
            db.delete(p)
            deleted_count += 1
        
        print()

if deleted_count > 0:
    db.commit()
    print(f"✅ Deleted {deleted_count} duplicate pension funds")
else:
    print("✅ No duplicates found")

# Verify
remaining = db.query(PensionFund).filter(PensionFund.client_id == 4).count()
print(f"\nTotal pension funds after cleanup: {remaining}")
