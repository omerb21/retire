from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.pensions import calc_monthly_pension_from_capital

def test_pension_monthly_simple():
    params = InMemoryTaxParamsProvider().get_params()
    assert calc_monthly_pension_from_capital(200000.0, params) == 1000.0
