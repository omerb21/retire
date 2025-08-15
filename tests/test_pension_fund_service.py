from app.models.pension_fund import PensionFund
from app.services.pension_fund_service import calculate_pension_amount, compute_and_apply_indexation

def test_pension_calc_calculated_mode():
    f = PensionFund(input_mode="calculated", balance=120000, annuity_factor=200, indexation_method="none")
    assert calculate_pension_amount(f) == 600.0

def test_pension_calc_manual_mode():
    f = PensionFund(input_mode="manual", pension_amount=3500, indexation_method="none")
    assert calculate_pension_amount(f) == 3500.0

def test_pension_indexation_fixed():
    f = PensionFund(input_mode="manual", pension_amount=3000, indexation_method="fixed", fixed_index_rate=0.02)
    base, indexed = compute_and_apply_indexation(f)
    assert base == 3000.0
    assert indexed == 3000.0 * 1.02

def test_pension_indexation_none():
    f = PensionFund(input_mode="manual", pension_amount=3000, indexation_method="none")
    base, indexed = compute_and_apply_indexation(f)
    assert base == 3000.0
    assert indexed == 3000.0
