from datetime import date
from app.calculation.seniority import calc_seniority_years
import pytest

def test_calc_seniority_basic():
    y = calc_seniority_years(date(2020,1,1), date(2025,1,1))
    assert 4.99 < y < 5.01

def test_calc_seniority_invalid():
    with pytest.raises(ValueError):
        calc_seniority_years(date(2025,1,1), date(2024,1,1))
