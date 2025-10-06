#!/usr/bin/env python3
"""
Debug tax brackets API issue
"""
import sys
import traceback

try:
    from app.services.tax_data_service import TaxDataService
    
    print("Testing tax brackets service...")
    result = TaxDataService.get_tax_brackets(2025)
    print(f"Success: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
