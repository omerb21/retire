#!/usr/bin/env python
"""Test if annuity_coefficient router is loaded"""
try:
    from app.routers import annuity_coefficient
    print("✅ Router loaded successfully")
    print(f"✅ Router has {len(annuity_coefficient.router.routes)} routes")
    for route in annuity_coefficient.router.routes:
        print(f"  - {route.methods} {route.path}")
except Exception as e:
    print(f"❌ Error loading router: {e}")
    import traceback
    traceback.print_exc()
