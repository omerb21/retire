from datetime import date
from app.schemas.tax import TaxParameters

def index_factor(params: TaxParameters, base_date: date, target_date: date) -> float:
    # לוקחים ערך לתחילת החודש של התאריך (יום 1)
    base_key = date(base_date.year, base_date.month, 1)
    target_key = date(target_date.year, target_date.month, 1)
    try:
        base = params.cpi_series[base_key]
        target = params.cpi_series[target_key]
    except KeyError:
        raise ValueError("סדרת מדד חסרה לתאריכים המבוקשים")
    return round(target / base, 6)

def index_amount(amount: float, factor: float) -> float:
    return round(amount * factor, 2)
