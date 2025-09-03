#!/usr/bin/env python3
"""Debug script for PDF generation issues"""

import traceback
import sys

def test_imports():
    """Test all imports step by step"""
    try:
        print("Testing imports...")
        
        # Test basic imports
        from app.database import SessionLocal
        print("✓ Database import OK")
        
        from app.models import Client, Scenario
        print("✓ Models import OK")
        
        from app.schemas.report import ReportPdfRequest
        print("✓ Report schema import OK")
        
        from app.services.cashflow_service import generate_cashflow
        print("✓ Cashflow service import OK")
        
        from app.services.report_service import generate_report_pdf
        print("✓ Report service import OK")
        
        return True
        
    except Exception as e:
        print(f"✗ Import error: {e}")
        traceback.print_exc()
        return False

def test_pdf_generation():
    """Test PDF generation with real data"""
    try:
        from app.database import SessionLocal
        from app.models import Client, Scenario
        from app.schemas.report import ReportPdfRequest
        from app.services.report_service import generate_report_pdf
        
        print("Testing PDF generation...")
        
        # Get database session
        db = SessionLocal()
        
        # Find test client and scenario
        client = db.query(Client).first()
        scenario = db.query(Scenario).first()
        
        if not client:
            print("✗ No client found in database")
            return False
            
        if not scenario:
            print("✗ No scenario found in database")
            return False
            
        print(f"✓ Found client {client.id} and scenario {scenario.id}")
        
        # Create request
        request = ReportPdfRequest(
            from_="2025-01",
            to="2025-12",
            frequency="monthly"
        )
        print("✓ Request created")
        
        # Generate PDF
        pdf_bytes = generate_report_pdf(
            db=db,
            client_id=client.id,
            scenario_id=scenario.id,
            request=request
        )
        
        print(f"✓ PDF generated successfully: {len(pdf_bytes)} bytes")
        
        # Verify PDF format
        if pdf_bytes[:4] == b"%PDF":
            print("✓ Valid PDF format")
        else:
            print("✗ Invalid PDF format")
            
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ PDF generation error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== PDF Generation Debug ===")
    
    if test_imports():
        print("\n=== Testing PDF Generation ===")
        test_pdf_generation()
    else:
        print("Import test failed, skipping PDF generation test")
