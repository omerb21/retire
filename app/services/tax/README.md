# Tax Module - מודול מס

מודול מקיף לחישובי מס בישראל, כולל קבועים, מדרגות מס, ביטוח לאומי ומס בריאות.

## מבנה המודול

```
tax/
├── __init__.py
├── README.md
└── constants/
    ├── __init__.py              # נקודת כניסה מרכזית + TaxConstants class
    ├── base_models.py           # מודלים בסיסיים (TaxBracket, TaxCredit)
    ├── income_tax.py            # מדרגות מס הכנסה
    ├── national_insurance.py    # ביטוח לאומי
    ├── health_tax.py            # מס בריאות
    ├── tax_credits.py           # נקודות זיכוי במס
    ├── pension_tax.py           # פטורים לפנסיונרים
    ├── special_rates.py         # שיעורי מס מיוחדים
    └── enums.py                 # ENUMs וקבועים נוספים
```

## שימוש

### ייבוא מהמבנה החדש (מומלץ)

```python
# ייבוא המחלקה המרכזית
from app.services.tax.constants import TaxConstants

# ייבוא מודלים ספציפיים
from app.services.tax.constants import TaxBracket, TaxCredit

# ייבוא קבועים ספציפיים
from app.services.tax.constants import (
    INCOME_TAX_BRACKETS_2024,
    NATIONAL_INSURANCE_2024,
    SPECIAL_TAX_RATES
)
```

### ייבוא מהקובץ המקורי (תאימות לאחור)

```python
# עדיין עובד - מפנה למבנה החדש
from app.services.tax_constants import TaxConstants, TaxBracket
```

## דוגמאות שימוש

### קבלת מדרגות מס לשנה מסוימת

```python
from app.services.tax.constants import TaxConstants

# מדרגות מס לשנת 2024
brackets_2024 = TaxConstants.get_tax_brackets(2024)

# מדרגות מס לשנת 2025
brackets_2025 = TaxConstants.get_tax_brackets(2025)

# מדרגות מס לשנה הנוכחית (ברירת מחדל)
brackets_current = TaxConstants.get_tax_brackets()
```

### קבלת שיעורי ביטוח לאומי

```python
from app.services.tax.constants import TaxConstants

ni_rates = TaxConstants.get_national_insurance_rates(2024)
print(f"שיעור עובד נמוך: {ni_rates['employee_rate_low']}")
print(f"תקרה נמוכה: {ni_rates['low_threshold_monthly']}")
```

### קבלת נקודות זיכוי במס

```python
from app.services.tax.constants import TaxConstants

credits = TaxConstants.get_tax_credits(2024)
for credit in credits:
    print(f"{credit.name}: {credit.amount} ₪")
```

### גישה ישירה לקבועים

```python
from app.services.tax.constants import (
    SPECIAL_TAX_RATES,
    INDEXATION_RATES,
    INCOME_TYPES
)

# שיעור מס רווח הון
capital_gains_rate = SPECIAL_TAX_RATES['capital_gains']

# שיעור הצמדה למדד
cpi_rate = INDEXATION_RATES['cpi_annual']

# סוגי הכנסות
income_type_name = INCOME_TYPES['salary']  # 'שכר עבודה'
```

## יתרונות המבנה החדש

1. **ארגון טוב יותר** - כל נושא בקובץ נפרד
2. **אחזור קוד מהיר** - קל למצוא את מה שצריך
3. **תחזוקה קלה** - עדכון מדרגות מס לא משפיע על שאר הקוד
4. **טעינה יעילה** - ייבוא רק מה שצריך
5. **בדיקות יחידה** - קל לבדוק כל מודול בנפרד
6. **הרחבה עתידית** - קל להוסיף קבועים חדשים

## הוספת שנת מס חדשה

כדי להוסיף קבועים לשנת מס חדשה:

1. **מדרגות מס הכנסה** - ערוך `constants/income_tax.py`
2. **ביטוח לאומי** - ערוך `constants/national_insurance.py`
3. **מס בריאות** - ערוך `constants/health_tax.py`
4. **נקודות זיכוי** - ערוך `constants/tax_credits.py`

דוגמה להוספת שנת 2026:

```python
# בקובץ income_tax.py
INCOME_TAX_BRACKETS_2026: List[TaxBracket] = [
    TaxBracket(0, 90000, 0.10, "מדרגה ראשונה - 10%"),
    # ... שאר המדרגות
]

# עדכון הפונקציה get_tax_brackets
def get_tax_brackets(year: int = None) -> List[TaxBracket]:
    if year is None:
        year = 2024
    if year >= 2026:
        return INCOME_TAX_BRACKETS_2026
    elif year >= 2025:
        return INCOME_TAX_BRACKETS_2025
    else:
        return INCOME_TAX_BRACKETS_2024
```

## תאימות לאחור

הקובץ המקורי `app/services/tax_constants.py` עדיין קיים כ-wrapper שמפנה למבנה החדש.
כל הקוד הקיים ימשיך לעבוד ללא שינויים.

## הערות חשובות

- כל המדרגות והשיעורים מעודכנים לשנת המס 2024-2025
- הקבועים מבוססים על נתוני רשות המיסים הרשמיים
- יש לעדכן את הקבועים בתחילת כל שנת מס
- המבנה תומך בשנים עתידיות עם ברירות מחדל

## תיעוד נוסף

לפרטים נוספים על חישובי מס, ראה:
- `app/services/tax_calculator.py` - מחשבון מס מקיף
- `app/services/capital_asset/tax_calculator.py` - חישובי מס לנכסי הון
- `app/schemas/tax_schemas.py` - סכמות לחישובי מס
