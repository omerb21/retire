from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.grants import calc_grant_components

def test_grant_tax_with_exemption_and_brackets():
    params = InMemoryTaxParamsProvider().get_params()
    # gross=100000, cap=60000 => taxable=40000 => 10% עד 40,000 => 4,000
    ex, taxable, tax = calc_grant_components(100000.0, params)
    assert ex == 60000.0
    assert taxable == 40000.0
    assert tax == 4000.0
