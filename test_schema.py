from app.schemas.pension_fund import PensionFundCreate
import json

# Test schema includes tax_treatment
fields = PensionFundCreate.model_fields.keys()
print("✅ Schema fields:", list(fields))
print("✅ tax_treatment in schema:", "tax_treatment" in fields)

# Test creating instance
data = {
    "client_id": 1,
    "fund_name": "Test Fund",
    "input_mode": "manual",
    "indexation_method": "none",
    "tax_treatment": "exempt"
}

instance = PensionFundCreate(**data)
print("✅ Created instance with tax_treatment:", instance.tax_treatment)
print("✅ Instance dump:", instance.model_dump())
