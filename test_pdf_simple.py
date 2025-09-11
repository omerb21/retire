"""
Simple test script for PDF generation functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.pdf_builder import build_pdf
from unittest.mock import Mock
import tempfile

def test_pdf_generation():
    """Test basic PDF generation"""
    
    # Mock client
    mock_client = Mock()
    mock_client.id = 1
    mock_client.full_name = "Test Client"
    
    # Test context
    context = {
        'client': mock_client,
        'retirement_age': 67,
        'life_expectancy': 85,
        'indexation_rate': 0.02,
        'pension_calculation': {
            'total_capital': 1000000,
            'reservation_impact': 50000,
            'effective_capital': 950000,
            'years_in_retirement': 18,
            'annual_pension': 52777,
            'monthly_pension': 4398
        },
        'processed_grants': [
            {
                'grant_type': 'Severance',
                'original_amount': 200000,
                'reservation_impact': 70000,
                'payment_year': 2024
            }
        ],
        'tax_parameters': {
            'brackets': [
                {'min': 0, 'max': 75960, 'rate': 0.10},
                {'min': 75960, 'max': 108960, 'rate': 0.14}
            ]
        }
    }
    
    # Test cashflow
    cashflow = [
        {
            'year': 2024,
            'gross_income': 100000,
            'pension_income': 60000,
            'grant_income': 40000,
            'other_income': 0,
            'tax': 20000,
            'net_income': 80000
        },
        {
            'year': 2025,
            'gross_income': 105000,
            'pension_income': 62000,
            'grant_income': 43000,
            'other_income': 0,
            'tax': 21000,
            'net_income': 84000
        }
    ]
    
    # Generate PDF
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        file_path = tmp_file.name
    
    try:
        print(f"Generating PDF at: {file_path}")
        result_path = build_pdf(context, cashflow, file_path)
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"✓ PDF generated successfully")
            print(f"✓ File size: {file_size} bytes")
            
            # Check if it's a valid PDF
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header == b'%PDF':
                    print("✓ Valid PDF header found")
                else:
                    print("✗ Invalid PDF header")
            
            return True
        else:
            print("✗ PDF file not created")
            return False
    
    except Exception as e:
        print(f"✗ Error generating PDF: {str(e)}")
        return False
    
    finally:
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
            print("✓ Temporary file cleaned up")

if __name__ == "__main__":
    print("Testing PDF generation...")
    success = test_pdf_generation()
    
    if success:
        print("\n✓ PDF generation test PASSED")
        sys.exit(0)
    else:
        print("\n✗ PDF generation test FAILED")
        sys.exit(1)
