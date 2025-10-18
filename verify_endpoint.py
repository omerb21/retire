#!/usr/bin/env python
"""Verify that the retirement scenarios endpoint is registered"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("VERIFYING RETIREMENT SCENARIOS ENDPOINT")
print("=" * 60)

# Step 1: Import the service
print("\n1. Importing RetirementScenariosBuilder...")
try:
    from app.services.retirement_scenarios import RetirementScenariosBuilder
    print("   ✅ Service imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import service: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Import the router
print("\n2. Importing scenarios router...")
try:
    from app.routers.scenarios import router
    print("   ✅ Router imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import router: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Check routes
print("\n3. Checking registered routes:")
found_retirement_route = False
for route in router.routes:
    methods_str = ','.join(route.methods) if hasattr(route, 'methods') else 'N/A'
    path = route.path
    print(f"   {methods_str:10} {path}")
    if 'retirement-scenarios' in path:
        found_retirement_route = True
        print(f"      ⭐ FOUND RETIREMENT SCENARIOS ROUTE!")

if found_retirement_route:
    print("\n✅ SUCCESS: Retirement scenarios route is registered!")
else:
    print("\n❌ ERROR: Retirement scenarios route NOT found!")
    sys.exit(1)

# Step 4: Check main app
print("\n4. Checking main.py imports...")
try:
    from app.main import app
    print("   ✅ Main app imported successfully")
    
    print("\n5. Checking all app routes:")
    retirement_found_in_app = False
    for route in app.routes:
        if hasattr(route, 'path') and 'retirement-scenarios' in route.path:
            print(f"   ⭐ {route.path}")
            retirement_found_in_app = True
    
    if retirement_found_in_app:
        print("\n✅ COMPLETE SUCCESS: Route is in the FastAPI app!")
    else:
        print("\n⚠️ WARNING: Route not found in main FastAPI app")
        print("   This might mean the server needs to restart")
        
except Exception as e:
    print(f"   ❌ Failed to import main app: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
