#!/usr/bin/env python
"""Test the exact query from the service"""
from app.database import engine
from sqlalchemy import text

sex = 'זכר'
retirement_age = 68
survivors_option = 'תקנוני'
spouse_age_diff = 0

print(f"Testing exact query with:")
print(f"  sex = '{sex}'")
print(f"  retirement_age = {retirement_age}")
print(f"  survivors_option = '{survivors_option}'")
print(f"  spouse_age_diff = {spouse_age_diff}")
print()

query = text("""
    SELECT 
        base_coefficient,
        adjust_percent,
        fund_name,
        notes
    FROM pension_fund_coefficient
    WHERE sex = :sex
      AND retirement_age = :retirement_age
      AND survivors_option = :survivors_option
      AND spouse_age_diff = :spouse_age_diff
    ORDER BY id DESC
    LIMIT 1
""")

with engine.connect() as conn:
    result = conn.execute(query, {
        'sex': sex,
        'retirement_age': retirement_age,
        'survivors_option': survivors_option,
        'spouse_age_diff': spouse_age_diff
    }).fetchone()
    
    if result:
        print(f"✅ FOUND!")
        print(f"  base_coefficient = {result[0]}")
        print(f"  adjust_percent = {result[1]}")
        print(f"  fund_name = {result[2]}")
        print(f"  notes = {result[3]}")
        factor = result[0] * result[1]
        print(f"  Factor = {result[0]} * {result[1]} = {factor}")
    else:
        print(f"❌ NOT FOUND!")
        
        # Debug: Check what values exist
        print("\nDebug: Checking individual conditions...")
        
        with engine.connect() as conn2:
            # Check sex
            r = conn2.execute(text(f"SELECT COUNT(*) FROM pension_fund_coefficient WHERE sex = '{sex}'")).scalar()
            print(f"  Rows with sex='{sex}': {r}")
            
            # Check retirement_age
            r = conn2.execute(text(f"SELECT COUNT(*) FROM pension_fund_coefficient WHERE retirement_age = {retirement_age}")).scalar()
            print(f"  Rows with retirement_age={retirement_age}: {r}")
            
            # Check survivors_option
            r = conn2.execute(text(f"SELECT COUNT(*) FROM pension_fund_coefficient WHERE survivors_option = '{survivors_option}'")).scalar()
            print(f"  Rows with survivors_option='{survivors_option}': {r}")
            
            # Check spouse_age_diff
            r = conn2.execute(text(f"SELECT COUNT(*) FROM pension_fund_coefficient WHERE spouse_age_diff = {spouse_age_diff}")).scalar()
            print(f"  Rows with spouse_age_diff={spouse_age_diff}: {r}")
            
            # Check combination
            r = conn2.execute(text(f"""
                SELECT COUNT(*) FROM pension_fund_coefficient 
                WHERE sex = '{sex}' 
                  AND retirement_age = {retirement_age}
                  AND survivors_option = '{survivors_option}'
                  AND spouse_age_diff = {spouse_age_diff}
            """)).scalar()
            print(f"  Rows with ALL conditions: {r}")
