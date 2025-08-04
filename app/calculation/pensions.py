from app.schemas.tax import TaxParameters

def calc_monthly_pension_from_capital(capital: float, params: TaxParameters) -> float:
    if capital < 0:
        raise ValueError("הון פנסיוני שלילי אינו חוקי")
    return round(capital / params.annuity_factor, 2)
