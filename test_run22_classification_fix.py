"""
Run 25: Tax Analysis with Rights Fixation Exemption
Test that RUN_RETIREMENT_CASHFLOW_ANALYSIS correctly calculates:
1. Gross pension income
2. Tax deductions (income tax + health tax)
3. Net pension income
4. Maximum exemption from rights fixation (kibua zchuyot)
"""
import json
import sys
from datetime import date
from types import SimpleNamespace

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

from app.database import get_db
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService


def print_result(year: str, res: dict, with_exemption: bool = False) -> None:
    """Print formatted result with tax analysis"""
    exemption_label = " (WITH MAX EXEMPTION)" if with_exemption else " (NO EXEMPTION)"
    print(f"\n[SUCCESS] Result for {year}{exemption_label}:")
    print(f"  Retirement Age: {res.get('retirement_age')}")
    print(f"")
    print(f"  === GROSS (Bruto) ===")
    print(f"  Projected Pension (Gross): {res.get('projected_pension'):,.2f} ILS/month")
    print(f"  Social Security: {res.get('social_security'):,.2f} ILS/month")
    print(f"  Total Guaranteed Income (Gross): {res.get('total_guaranteed_income'):,.2f} ILS/month")

    if with_exemption:
        print(f"")
        print(f"  === EXEMPTION (Kibua Zchuyot) ===")
        print(f"  Exemption Percentage: {res.get('exemption_percentage'):.1f}%")
        print(f"  Exempt Pension Monthly: {res.get('exempt_pension_monthly'):,.2f} ILS/month")

    print(f"")
    print(f"  === TAX ANALYSIS ===")
    print(f"  Income Tax: {res.get('monthly_income_tax'):,.2f} ILS/month")
    print(f"  Health Tax: {res.get('monthly_health_tax'):,.2f} ILS/month")
    print(f"  Total Tax Deduction: {res.get('monthly_tax_deduction'):,.2f} ILS/month")
    print(f"")
    print(f"  === NET (Neto) ===")
    print(f"  Projected Pension (Net): {res.get('projected_pension_net'):,.2f} ILS/month")
    print(f"  Total Guaranteed Income (Net): {res.get('total_guaranteed_income_net'):,.2f} ILS/month")
    print(f"")
    print(f"  === OTHER ===")
    print(f"  Total Liquid Capital: {res.get('total_liquid_capital'):,.2f} ILS")


def main() -> None:
    db = next(get_db())
    try:
        # Find scenario 271 which has the pension_portfolio with the 6M product
        scenario = db.query(Scenario).filter(Scenario.id == 271).first()
        if not scenario:
            print("[ERROR] Scenario 271 not found")
            return

        params = json.loads(scenario.parameters or "{}")
        pension_portfolio = params.get("pension_portfolio")
        if not pension_portfolio:
            print("[ERROR] No pension_portfolio in scenario 271")
            return

        print(f"[INFO] Found scenario 271 with {len(pension_portfolio)} accounts")
        print(f"[INFO] Client ID: {scenario.client_id}")

        # Convert dict accounts to SimpleNamespace objects (mimicking Pydantic models)
        portfolio_objects = []
        for acc in pension_portfolio:
            obj = SimpleNamespace()
            # Map Hebrew keys to attributes
            for key, value in acc.items():
                setattr(obj, key, value)
            portfolio_objects.append(obj)

        # Initialize AgentToolsService with the portfolio data
        service = AgentToolsService(
            db=db,
            client_id=scenario.client_id,
            pension_portfolio_data=portfolio_objects,
        )

        # ===== PART 1: WITHOUT EXEMPTION =====
        print("\n" + "=" * 80)
        print("[PART 1] WITHOUT EXEMPTION (Baseline)")
        print("=" * 80)

        print("\n" + "-" * 40)
        print("[TEST 1A] Retirement in 2028 - NO EXEMPTION")
        print("-" * 40)

        result_2028_no_exempt = service.run_retirement_cashflow_analysis(
            retirement_date="2028-01-01",
            desired_monthly_income=30000,
            apply_max_exemption=False,
        )

        if result_2028_no_exempt.get("success"):
            print_result("2028", result_2028_no_exempt.get("result", {}), with_exemption=False)
        else:
            print(f"\n[FAILED] {result_2028_no_exempt.get('explanation')}")

        print("\n" + "-" * 40)
        print("[TEST 1B] Retirement in 2029 - NO EXEMPTION")
        print("-" * 40)

        result_2029_no_exempt = service.run_retirement_cashflow_analysis(
            retirement_date="2029-01-01",
            desired_monthly_income=30000,
            apply_max_exemption=False,
        )

        if result_2029_no_exempt.get("success"):
            print_result("2029", result_2029_no_exempt.get("result", {}), with_exemption=False)
        else:
            print(f"\n[FAILED] {result_2029_no_exempt.get('explanation')}")

        # ===== PART 2: WITH MAX EXEMPTION =====
        print("\n" + "=" * 80)
        print("[PART 2] WITH MAXIMUM EXEMPTION (Kibua Zchuyot)")
        print("=" * 80)

        print("\n" + "-" * 40)
        print("[TEST 2A] Retirement in 2028 - WITH MAX EXEMPTION")
        print("-" * 40)

        result_2028_with_exempt = service.run_retirement_cashflow_analysis(
            retirement_date="2028-01-01",
            desired_monthly_income=30000,
            apply_max_exemption=True,
        )

        if result_2028_with_exempt.get("success"):
            print_result("2028", result_2028_with_exempt.get("result", {}), with_exemption=True)
        else:
            print(f"\n[FAILED] {result_2028_with_exempt.get('explanation')}")

        print("\n" + "-" * 40)
        print("[TEST 2B] Retirement in 2029 - WITH MAX EXEMPTION")
        print("-" * 40)

        result_2029_with_exempt = service.run_retirement_cashflow_analysis(
            retirement_date="2029-01-01",
            desired_monthly_income=30000,
            apply_max_exemption=True,
        )

        if result_2029_with_exempt.get("success"):
            print_result("2029", result_2029_with_exempt.get("result", {}), with_exemption=True)
        else:
            print(f"\n[FAILED] {result_2029_with_exempt.get('explanation')}")

        # ===== PART 3: COMPARISON =====
        print("\n" + "=" * 80)
        print("[PART 3] COMPARISON: NO EXEMPTION vs WITH MAX EXEMPTION")
        print("=" * 80)

        if (result_2028_no_exempt.get("success") and result_2029_no_exempt.get("success") and
            result_2028_with_exempt.get("success") and result_2029_with_exempt.get("success")):

            res_2028_no = result_2028_no_exempt["result"]
            res_2029_no = result_2029_no_exempt["result"]
            res_2028_ex = result_2028_with_exempt["result"]
            res_2029_ex = result_2029_with_exempt["result"]

            print(f"\n  {'Year':<6} {'Exemption':<15} {'Gross':<12} {'Tax':<12} {'Net':<12} {'Savings':<12}")
            print(f"  {'-'*6} {'-'*15} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

            for year, res_no, res_ex in [("2028", res_2028_no, res_2028_ex), ("2029", res_2029_no, res_2029_ex)]:
                gross = res_no.get("projected_pension", 0)
                tax_no = res_no.get("monthly_tax_deduction", 0)
                net_no = res_no.get("projected_pension_net", 0)
                tax_ex = res_ex.get("monthly_tax_deduction", 0)
                net_ex = res_ex.get("projected_pension_net", 0)
                savings = net_ex - net_no

                print(f"  {year:<6} {'No':<15} {gross:>9,.0f} {tax_no:>9,.0f} {net_no:>9,.0f}")
                print(f"  {'':<6} {'Max':<15} {gross:>9,.0f} {tax_ex:>9,.0f} {net_ex:>9,.0f} {'+' + f'{savings:,.0f}':>9}")
                print()

            print(f"\n  SUMMARY:")
            print(f"  - 2028 Tax Savings with Max Exemption: {res_2028_ex.get('projected_pension_net', 0) - res_2028_no.get('projected_pension_net', 0):,.0f} ILS/month")
            print(f"  - 2029 Tax Savings with Max Exemption: {res_2029_ex.get('projected_pension_net', 0) - res_2029_no.get('projected_pension_net', 0):,.0f} ILS/month")
            print(f"  - 2028 Exemption Percentage: {res_2028_ex.get('exemption_percentage', 0):.1f}%")
            print(f"  - 2029 Exemption Percentage: {res_2029_ex.get('exemption_percentage', 0):.1f}%")

        print("\n" + "=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
