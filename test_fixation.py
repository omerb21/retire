import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rights_fixation import calculate_adjusted_amount
from datetime import date
import logging

# הגדרת לוגינג כדי לראות את הפלט
logging.basicConfig(level=logging.INFO)

# נתוני הבדיקה
amount = 300000
grant_date = "2023-12-31"
eligibility_date = "2025-01-01"  # שינוי לתאריך שבדקנו ב-API

print(f"Calculating indexation for amount={amount} from {grant_date} to {eligibility_date}")
result = calculate_adjusted_amount(amount, grant_date, eligibility_date)
print(f"Result: {result}")

# בדיקה נוספת עם תאריך אחר
print(f"\nTesting with 2025-10-05:")
result2 = calculate_adjusted_amount(amount, grant_date, "2025-10-05")
print(f"Result: {result2}")

# בואו נבדוק גם את הפונקציה המלאה
from app.services.rights_fixation import compute_grant_effect

grant = {
    'grant_amount': 300000,
    'work_start_date': '2000-01-01',
    'work_end_date': '2023-12-31',
    'grant_date': '2023-12-31'
}

print("\nTesting compute_grant_effect:")
result = compute_grant_effect(grant, eligibility_date)
print(f"Result: {result}")
