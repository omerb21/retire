"""Check registered routes in FastAPI app"""
from app.main import app

print("=" * 80)
print("REGISTERED ROUTES CONTAINING 'client':")
print("=" * 80)

for route in app.routes:
    if hasattr(route, 'path') and 'client' in route.path.lower():
        methods = getattr(route, 'methods', set())
        name = getattr(route, 'name', 'unnamed')
        print(f"Path: {route.path}")
        print(f"  Methods: {methods}")
        print(f"  Name: {name}")
        print()

print("=" * 80)
print("LOOKING FOR FIXATION ENDPOINT:")
print("=" * 80)

fixation_found = False
for route in app.routes:
    if hasattr(route, 'path') and 'fixation' in route.path.lower():
        methods = getattr(route, 'methods', set())
        name = getattr(route, 'name', 'unnamed')
        print(f"✓ FOUND: {route.path}")
        print(f"  Methods: {methods}")
        print(f"  Name: {name}")
        fixation_found = True

if not fixation_found:
    print("✗ NO FIXATION ENDPOINT FOUND!")
