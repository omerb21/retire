"""
Special tax rates and indexation rates for Israel.
שיעורי מס מיוחדים ושיעורי הצמדה לישראל.
"""

from typing import Dict


# שיעורי מס מיוחדים לסוגי הכנסות שונות
SPECIAL_TAX_RATES: Dict[str, float] = {
    'rental_income': 0.10,  # מס קבוע 10% על הכנסה משכירות
    'capital_gains': 0.25,  # מס רווח הון 25%
    'dividend_income': 0.25,  # מס דיבידנד 25%
    'interest_income': 0.15,  # מס על ריבית 15%
}

# שיעורי הצמדה למדד
INDEXATION_RATES: Dict[str, float] = {
    'cpi_annual': 0.025,  # 2.5% הצמדה שנתית למדד המחירים
    'salary_annual': 0.030,  # 3.0% הצמדה שנתית לשכר הממוצע
}
