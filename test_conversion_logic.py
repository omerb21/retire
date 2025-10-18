"""
Test conversion logic for education fund
"""

# Simulate account data
account = {
    'שם_תכנית': 'קרן השתלמות למורים תיכוניים',
    'סוג_מוצר': 'קרן השתלמות',
    'יתרה': 195693
}

# Test logic
product_type = account.get('סוג_מוצר', '')
tax_treatment = "exempt" if 'השתלמות' in product_type else "taxable"

print(f"Product Type: {product_type}")
print(f"Contains 'השתלמות': {'השתלמות' in product_type}")
print(f"Tax Treatment: {tax_treatment}")
print()

# Test with different formats
test_cases = [
    'קרן השתלמות',
    'קרן_השתלמות',
    'education_fund',
    'pension',
]

print("Test cases:")
for case in test_cases:
    result = "exempt" if 'השתלמות' in case else "taxable"
    print(f"  '{case}' -> {result}")
