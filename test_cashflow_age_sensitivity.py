"""
Test RUN_RETIREMENT_CASHFLOW_ANALYSIS for age sensitivity (Run 16)
Direct test to verify annuity coefficient is used correctly for different retirement ages
"""

import logging
import sys
from datetime import date
from app.database import get_db
from app.services.llm_agent_tools_service import AgentToolsService

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding="utf-8")

# Setup logging to see all debug messages
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

print("=" * 100)
print("[RUN 16] Testing RUN_RETIREMENT_CASHFLOW_ANALYSIS Age Sensitivity")
print("=" * 100)

# Get DB session
db = next(get_db())

try:
    # Test parameters
    client_id = 2  # Client with pension balance

    # Initialize service with client_id
    service = AgentToolsService(db, client_id)

    print("\n" + "=" * 100)
    print("[TEST 1] Retirement at Age 70 (January 1, 2028)")
    print("=" * 100)

    result_70 = service.run_retirement_cashflow_analysis(
        retirement_date="2028-01-01", desired_monthly_income=10000
    )

    if result_70.get("success"):
        result_data_70 = result_70.get("result", {})
        print(f"\n[SUCCESS] Result for Age 70:")
        print(f"  Retirement Age: {result_data_70.get('retirement_age')}")
        print(
            f"  Projected Pension: ₪{result_data_70.get('projected_pension', 0):,.2f}/month"
        )
        print(
            f"  Total Guaranteed Income: ₪{result_data_70.get('total_guaranteed_income', 0):,.2f}/month"
        )
    else:
        print(f"\n[FAILED] Test 1 failed: {result_70.get('error')}")

    print("\n" + "=" * 100)
    print("[TEST 2] Retirement at Age 71 (January 1, 2029)")
    print("=" * 100)

    result_71 = service.run_retirement_cashflow_analysis(
        retirement_date="2029-01-01", desired_monthly_income=10000
    )

    if result_71.get("success"):
        result_data_71 = result_71.get("result", {})
        print(f"\n[SUCCESS] Result for Age 71:")
        print(f"  Retirement Age: {result_data_71.get('retirement_age')}")
        print(
            f"  Projected Pension: ₪{result_data_71.get('projected_pension', 0):,.2f}/month"
        )
        print(
            f"  Total Guaranteed Income: ₪{result_data_71.get('total_guaranteed_income', 0):,.2f}/month"
        )
    else:
        print(f"\n[FAILED] Test 2 failed: {result_71.get('error')}")

    print("\n" + "=" * 100)
    print("[COMPARISON]")
    print("=" * 100)

    if result_70.get("success") and result_71.get("success"):
        pension_70 = result_70["result"].get("projected_pension", 0)
        pension_71 = result_71["result"].get("projected_pension", 0)

        print(f"\n  Age 70 Projected Pension: ₪{pension_70:,.2f}/month")
        print(f"  Age 71 Projected Pension: ₪{pension_71:,.2f}/month")
        print(f"  Difference: ₪{pension_71 - pension_70:,.2f}/month")

        if pension_70 == pension_71:
            print("\n[PROBLEM] Pensions are IDENTICAL (should differ by age)")
            print("   -> Check logs above for annuity coefficient values")
        elif pension_71 > pension_70:
            print("\n[CORRECT] Pension at 71 is HIGHER than at 70")
            pct_increase = (
                ((pension_71 - pension_70) / pension_70 * 100) if pension_70 > 0 else 0
            )
            print(f"   -> Increase: {pct_increase:.2f}%")
        else:
            print("\n[UNEXPECTED] Pension at 71 is LOWER than at 70")

    print("\n" + "=" * 100)
    print("[INSTRUCTIONS]")
    print("=" * 100)
    print("\n1. Review the logs above marked with [RUN 16 DEBUG]")
    print("2. Check if annuity_factor differs between age 70 and 71")
    print("3. Verify source_table is 'pension_fund_coefficient' (not 'default')")
    print(
        "4. If factors are identical or source is 'default', there's a data/logic issue"
    )
    print("\n" + "=" * 100)

finally:
    db.close()
