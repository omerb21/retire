"""Test importing retirement scenarios"""
import sys
print("Python path:")
"""
Test import of retirement scenarios and models
"""
print("Testing imports...")

try:
    from app.models.employer_grant import EmployerGrant, GrantType
    print("✅ EmployerGrant imported successfully")
    print(f"   GrantType values: {[gt.value for gt in GrantType]}")
except Exception as e:
    print(f"❌ Failed to import EmployerGrant: {e}")

try:
    from app.services.retirement_scenarios import RetirementScenarios
    print("✅ RetirementScenarios imported successfully")
except Exception as e:
    print(f"❌ Failed to import RetirementScenarios: {e}")

try:
    from app.services.retirement_scenarios import RetirementScenariosBuilder
    print("✅ RetirementScenariosBuilder imported successfully")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.routers.scenarios import router
    print("✅ Scenarios router imported successfully")
    print("Routes:")
    for route in router.routes:
        print(f"  {route.methods} {route.path}")
except Exception as e:
    print(f"❌ Failed to import router: {e}")
    import traceback
    traceback.print_exc()
