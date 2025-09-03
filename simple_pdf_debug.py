#!/usr/bin/env python3
"""Simple debug script for PDF generation"""

import traceback

try:
    from app.database import SessionLocal
    from app.models import Client, Scenario
    from app.schemas.report import ReportPdfRequest
    from app.services.cashflow_service import generate_cashflow
    
    print("✓ All imports successful")
    
    # Test database connection
    db = SessionLocal()
    client = db.query(Client).first()
    scenario = db.query(Scenario).first()
    
    print(f"✓ Found client {client.id if client else 'None'}")
    print(f"✓ Found scenario {scenario.id if scenario else 'None'}")
    
    if client and scenario:
        # Test cashflow generation first
        cashflow_data = generate_cashflow(
            db=db,
            client_id=client.id,
            scenario_id=scenario.id,
            start_ym="2025-01",
            end_ym="2025-12",
            frequency="monthly"
        )
        
        print(f"✓ Cashflow generated: {len(cashflow_data)} rows")
        print(f"✓ First row date type: {type(cashflow_data[0]['date'])}")
        print(f"✓ First row date value: {cashflow_data[0]['date']}")
        
    db.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()
