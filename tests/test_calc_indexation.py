from datetime import date
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.indexation import index_factor, index_amount

def test_indexation_factor_and_amount():
    p = InMemoryTaxParamsProvider().get_params()
    f = index_factor(p, date(2023,6,1), date(2025,6,1))
    assert round(f,6) == round(106.0/100.0, 6)
    assert index_amount(1000.0, f) == round(1000.0 * (106/100), 2)
