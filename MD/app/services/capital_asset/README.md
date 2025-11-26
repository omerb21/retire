# Capital Asset Service Package - תיעוד מקיף

## סקירה כללית

חבילת Capital Asset Service מכילה מנועי חישוב מודולריים לניהול נכסי הון. הקוד מפוצל למודולים נפרדים לפי אחריות, מה שמשפר תחזוקה, בדיקות ושימוש חוזר.

## מבנה התיקיות

```
app/services/capital_asset/
├── __init__.py                  # אתחול החבילה
├── base_calculator.py           # מחלקת בסיס אבסטרקטית
├── indexation_calculator.py     # חישובי הצמדה (CPI, קבוע)
├── tax_calculator.py           # חישובי מס (פטור, קבוע, שולי, פריסה)
├── payment_calculator.py       # לוחות תשלומים
├── cashflow_calculator.py      # תזרים מזומנים
└── service.py                  # שירות מרכזי (Facade)
```

## המודולים

### 1. BaseCalculator - מחלקת בסיס

מחלקה אבסטרקטית המגדירה ממשק משותף לכל המחשבונים.

**קובץ**: `base_calculator.py`

```python
from app.services.capital_asset.base_calculator import BaseCalculator

class MyCalculator(BaseCalculator):
    def calculate(self, *args, **kwargs):
        # יישום החישוב
        pass
```

**מתודות**:
- `calculate()` - מתודה אבסטרקטית לביצוע חישוב
- `validate_inputs()` - אימות פרמטרים (ניתן לעקוף)

---

### 2. IndexationCalculator - חישובי הצמדה

מחשב הצמדה למדד המחירים לצרכן או בשיעור קבוע.

**קובץ**: `indexation_calculator.py`

**שיטות הצמדה נתמכות**:
- `NONE`: ללא הצמדה
- `FIXED`: הצמדה בשיעור קבוע
- `CPI`: הצמדה למדד המחירים לצרכן

**שימוש**:
```python
from app.services.capital_asset.indexation_calculator import IndexationCalculator
from app.models.capital_asset import IndexationMethod
from datetime import date
from decimal import Decimal

# אתחול עם סדרת מדד
cpi_series = {2020: Decimal('100'), 2025: Decimal('115')}
calculator = IndexationCalculator(cpi_series)

# הצמדה קבועה
indexed = calculator.calculate(
    base_amount=Decimal('100000'),
    indexation_method=IndexationMethod.FIXED,
    start_date=date(2020, 1, 1),
    end_date=date(2025, 1, 1),
    fixed_rate=Decimal('0.03')  # 3% שנתי
)
# תוצאה: ~115,927 (100,000 × 1.03^5)

# הצמדה למדד
indexed = calculator.calculate(
    base_amount=Decimal('100000'),
    indexation_method=IndexationMethod.CPI,
    start_date=date(2020, 1, 1),
    end_date=date(2025, 1, 1)
)
# תוצאה: 115,000 (100,000 × 115/100)
```

**מתודות**:
- `calculate(base_amount, indexation_method, start_date, end_date, fixed_rate)` - חישוב הצמדה
- `validate_inputs()` - אימות פרמטרים

---

### 3. TaxCalculator - חישובי מס

מחשב מס על נכסי הון לפי יחסי מס שונים.

**קובץ**: `tax_calculator.py`

**יחסי מס נתמכים**:
- `EXEMPT`: פטור ממס
- `FIXED_RATE`: מס בשיעור קבוע (25%)
- `TAXABLE`: חייב במס שולי (מחושב ב-Frontend)
- `TAX_SPREAD`: פריסת מס על מספר שנים

**שימוש**:
```python
from app.services.capital_asset.tax_calculator import TaxCalculator
from app.models.capital_asset import TaxTreatment
from decimal import Decimal

# אתחול עם מדרגות מס
tax_brackets = [
    (Decimal('77040'), Decimal('0.10')),
    (Decimal('110880'), Decimal('0.14')),
    (Decimal('177840'), Decimal('0.20')),
    (None, Decimal('0.47'))  # מדרגה אחרונה
]
calculator = TaxCalculator(tax_brackets)

# מס בשיעור קבוע
result = calculator.calculate(
    gross_amount=Decimal('100000'),
    tax_treatment=TaxTreatment.FIXED_RATE,
    tax_rate=Decimal('0.25')
)
print(f"מס: {result['total_tax']}")  # 25,000

# פריסת מס
result = calculator.calculate(
    gross_amount=Decimal('500000'),
    tax_treatment=TaxTreatment.TAX_SPREAD,
    spread_years=6
)
print(f"מס כולל: {result['total_tax']}")
print(f"חלק שנתי: {result['annual_portion']}")  # 83,333
print(f"מס שנתי: {result['annual_tax']}")
```

**מתודות**:
- `calculate(gross_amount, tax_treatment, tax_rate, spread_years)` - חישוב מס
- `validate_inputs()` - אימות פרמטרים

**הערה חשובה**:
עבור `TAXABLE` ו-`TAX_SPREAD`, המס מחושב ב-Frontend באמצעות מדרגות מס שוליות. הפונקציה כאן מחזירה 0 כדי למנוע כפילות מס.

---

### 4. PaymentCalculator - לוחות תשלומים

מחשב לוחות תשלומים לפי תדירות.

**קובץ**: `payment_calculator.py`

**תדירויות נתמכות**:
- `MONTHLY`: חודשי
- `QUARTERLY`: רבעוני
- `ANNUALLY`: שנתי

**שימוש**:
```python
from app.services.capital_asset.payment_calculator import PaymentCalculator
from app.models.capital_asset import PaymentFrequency
from datetime import date
from decimal import Decimal

calculator = PaymentCalculator()

# תשלומים חודשיים
payments = calculator.calculate(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
    frequency=PaymentFrequency.MONTHLY,
    amount=Decimal('5000')
)
# תוצאה: 12 תשלומים של 5,000

# חישוב תשואה לתקופה
monthly_return = calculator.calculate_period_return(
    total_value=Decimal('100000'),
    annual_return_rate=Decimal('0.05'),
    frequency=PaymentFrequency.MONTHLY
)
# תוצאה: 416.67 (5,000 / 12)
```

**מתודות**:
- `calculate(start_date, end_date, frequency, amount)` - יצירת לוח תשלומים
- `calculate_period_return(total_value, annual_return_rate, frequency)` - תשואה לתקופה
- `get_payment_interval_months(frequency)` - מרווח בחודשים
- `is_payment_date(current_date, start_date, frequency)` - בדיקת תאריך תשלום

**הערה**: נכסי הון בפועל הם תמיד תשלום חד פעמי. מחלקה זו נשמרת לתמיכה עתידית.

---

### 5. CashflowCalculator - תזרים מזומנים

יוצר תחזיות תזרים מזומנים לנכסי הון.

**קובץ**: `cashflow_calculator.py`

**שימוש**:
```python
from app.services.capital_asset.cashflow_calculator import CashflowCalculator
from app.services.capital_asset.indexation_calculator import IndexationCalculator
from app.services.capital_asset.tax_calculator import TaxCalculator
from app.models.capital_asset import CapitalAsset
from datetime import date

# אתחול
indexation_calc = IndexationCalculator(cpi_series)
tax_calc = TaxCalculator(tax_brackets)
calculator = CashflowCalculator(indexation_calc, tax_calc)

# יצירת תזרים
cashflow = calculator.calculate(
    asset=my_asset,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31),
    reference_date=date(2020, 1, 1)
)

# עם פרטים נוספים
details = calculator.calculate_with_details(
    asset=my_asset,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31)
)
print(f"סה\"כ ברוטו: {details['total_gross']}")
print(f"סה\"כ מס: {details['total_tax']}")
print(f"סה\"כ נטו: {details['total_net']}")
```

**מתודות**:
- `calculate(asset, start_date, end_date, reference_date)` - יצירת תזרים
- `calculate_with_details(...)` - תזרים עם סטטיסטיקות

**הערה חשובה**: נכסי הון הם תמיד תשלום חד פעמי בתאריך ההתחלה.

---

### 6. CapitalAssetService - שירות מרכזי

שירות מרכזי המשמש כ-Facade לכל המחשבונים.

**קובץ**: `service.py`

**שימוש**:
```python
from app.services.capital_asset import CapitalAssetService
from app.providers.tax_params import TaxParamsProvider

# אתחול
tax_provider = TaxParamsProvider()
service = CapitalAssetService(tax_provider)

# תזרים לנכס בודד
cashflow = service.project_cashflow(
    asset=my_asset,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31)
)

# תזרים משולב לכל נכסי הלקוח
combined = service.generate_combined_cashflow(
    db_session=db,
    client_id=1,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31)
)

# חישוב הצמדה
indexed = service.apply_indexation(
    base_return=Decimal('100000'),
    asset=my_asset,
    target_date=date(2025, 1, 1)
)

# חישוב מס
tax = service.calculate_tax(
    gross_return=Decimal('100000'),
    asset=my_asset
)

# פריסת מס
spread_tax = service.calculate_spread_tax(
    taxable_amount=Decimal('500000'),
    spread_years=6
)
```

**מתודות ציבוריות**:
- `project_cashflow(asset, start_date, end_date, reference_date)` - תזרים לנכס
- `generate_combined_cashflow(db_session, client_id, start_date, end_date)` - תזרים משולב
- `apply_indexation(base_return, asset, target_date, reference_date)` - הצמדה
- `calculate_tax(gross_return, asset)` - חישוב מס
- `calculate_spread_tax(taxable_amount, spread_years)` - פריסת מס
- `calculate_monthly_return(asset)` - תשואה חודשית

---

## תאימות לאחור

**הקובץ המקורי `capital_asset_service.py` נשאר ללא שינוי!**

כל הקוד הקיים ממשיך לעבוד בדיוק כמו קודם. הקבצים החדשים הם תוספת בלבד.

### מעבר הדרגתי

```python
# גרסה ישנה (ממשיכה לעבוד)
from app.services.capital_asset_service import CapitalAssetService
service = CapitalAssetService(tax_provider)

# גרסה חדשה (מומלץ לקוד חדש)
from app.services.capital_asset import CapitalAssetService
service = CapitalAssetService(tax_provider)
```

הממשק זהה לחלוטין - אין צורך לשנות קוד קיים!

---

## יתרונות הפיצול

### 1. **אחריות יחידה** (Single Responsibility)
כל מחשבון עוסק בתחום אחד בלבד:
- IndexationCalculator → רק הצמדה
- TaxCalculator → רק מס
- PaymentCalculator → רק תשלומים
- CashflowCalculator → רק תזרים

### 2. **בדיקות קלות**
```python
# בדיקת יחידה פשוטה
def test_indexation():
    calculator = IndexationCalculator({2020: Decimal('100'), 2025: Decimal('115')})
    result = calculator.calculate(
        Decimal('100000'),
        IndexationMethod.CPI,
        date(2020, 1, 1),
        date(2025, 1, 1)
    )
    assert result == Decimal('115000')
```

### 3. **שימוש חוזר**
```python
# שימוש במחשבון בודד בקוד אחר
from app.services.capital_asset.tax_calculator import TaxCalculator

tax_calc = TaxCalculator(tax_brackets)
tax = tax_calc.calculate(amount, TaxTreatment.FIXED_RATE, rate=Decimal('0.25'))
```

### 4. **הרחבה קלה**
הוספת מחשבון חדש:
```python
# app/services/capital_asset/new_calculator.py
from app.services.capital_asset.base_calculator import BaseCalculator

class NewCalculator(BaseCalculator):
    def calculate(self, ...):
        # לוגיקה חדשה
        pass
```

### 5. **תחזוקה משופרת**
- קוד קצר וממוקד בכל קובץ
- קל למצוא באגים
- קל לעדכן לוגיקה ספציפית

---

## דוגמאות שימוש מתקדמות

### דוגמה 1: חישוב מענק פיצויים עם הצמדה ומס

```python
from app.services.capital_asset import CapitalAssetService
from app.models.capital_asset import CapitalAsset, IndexationMethod, TaxTreatment
from decimal import Decimal
from datetime import date

service = CapitalAssetService(tax_provider)

# יצירת נכס פיצויים
severance = CapitalAsset(
    client_id=1,
    asset_type='severance_grant',
    current_value=Decimal('500000'),
    start_date=date(2025, 1, 1),
    indexation_method=IndexationMethod.CPI,
    tax_treatment=TaxTreatment.TAX_SPREAD,
    spread_years=6
)

# חישוב תזרים
cashflow = service.project_cashflow(
    asset=severance,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31),
    reference_date=date(2020, 1, 1)
)

for item in cashflow:
    print(f"תאריך: {item.date}")
    print(f"ברוטו: ₪{item.gross_return:,.2f}")
    print(f"מס: ₪{item.tax_amount:,.2f}")
    print(f"נטו: ₪{item.net_return:,.2f}")
```

### דוגמה 2: השוואת שיטות הצמדה

```python
from app.services.capital_asset.indexation_calculator import IndexationCalculator
from app.models.capital_asset import IndexationMethod
from decimal import Decimal
from datetime import date

base_amount = Decimal('100000')
start = date(2020, 1, 1)
end = date(2025, 1, 1)

calculator = IndexationCalculator(cpi_series)

# ללא הצמדה
no_index = calculator.calculate(base_amount, IndexationMethod.NONE, start, end)
print(f"ללא הצמדה: ₪{no_index:,.2f}")

# הצמדה קבועה 3%
fixed = calculator.calculate(
    base_amount, IndexationMethod.FIXED, start, end, 
    fixed_rate=Decimal('0.03')
)
print(f"הצמדה קבועה 3%: ₪{fixed:,.2f}")

# הצמדה למדד
cpi = calculator.calculate(base_amount, IndexationMethod.CPI, start, end)
print(f"הצמדה למדד: ₪{cpi:,.2f}")
```

### דוגמה 3: חישוב מס עם פריסה

```python
from app.services.capital_asset.tax_calculator import TaxCalculator
from app.models.capital_asset import TaxTreatment
from decimal import Decimal

calculator = TaxCalculator(tax_brackets)

# פריסת מס על 6 שנים
result = calculator.calculate(
    gross_amount=Decimal('500000'),
    tax_treatment=TaxTreatment.TAX_SPREAD,
    spread_years=6
)

print(f"סכום כולל: ₪{Decimal('500000'):,.2f}")
print(f"חלק שנתי: ₪{result['annual_portion']:,.2f}")
print(f"מס שנתי: ₪{result['annual_tax']:,.2f}")
print(f"מס כולל: ₪{result['total_tax']:,.2f}")
print(f"\nפירוט שנתי:")
for i, yearly_tax in enumerate(result['yearly_taxes'], 1):
    print(f"  שנה {i}: ₪{yearly_tax:,.2f}")
```

### דוגמה 4: תזרים משולב למספר נכסים

```python
from app.services.capital_asset import CapitalAssetService
from sqlalchemy.orm import Session

service = CapitalAssetService(tax_provider)

# תזרים משולב לכל נכסי הלקוח
combined = service.generate_combined_cashflow(
    db_session=db,
    client_id=1,
    start_date=date(2025, 1, 1),
    end_date=date(2030, 12, 31)
)

total_gross = Decimal('0')
total_tax = Decimal('0')
total_net = Decimal('0')

for item in combined:
    print(f"\n{item['date'].strftime('%Y-%m')}:")
    print(f"  ברוטו: ₪{item['gross_return']:,.2f}")
    print(f"  מס: ₪{item['tax_amount']:,.2f}")
    print(f"  נטו: ₪{item['net_return']:,.2f}")
    
    total_gross += item['gross_return']
    total_tax += item['tax_amount']
    total_net += item['net_return']

print(f"\nסיכום:")
print(f"סה\"כ ברוטו: ₪{total_gross:,.2f}")
print(f"סה\"כ מס: ₪{total_tax:,.2f}")
print(f"סה\"כ נטו: ₪{total_net:,.2f}")
```

---

## הערות חשובות

### תלויות
- **IndexationCalculator**: דורש סדרת מדד CPI (אופציונלי)
- **TaxCalculator**: דורש מדרגות מס (אופציונלי, משתמש ב-TaxConstants)
- **PaymentCalculator**: אין תלויות
- **CashflowCalculator**: דורש IndexationCalculator ו-TaxCalculator
- **CapitalAssetService**: דורש TaxParamsProvider

### טיפול בשגיאות
כל המחשבונים מבצעים אימות קלט ומעלים `ValueError` במקרה של נתונים לא תקינים.

```python
try:
    result = calculator.calculate(...)
except ValueError as e:
    print(f"שגיאה: {e}")
```

### ביצועים
המחשבונים המודולריים מהירים כמו הקוד המקורי. אין overhead משמעותי.

### לוגיקת מס מיוחדת

#### נכסי הון עם פריסת מס (TAX_SPREAD)
- משמש בעיקר למענקי פיצויים
- הסכום מתחלק שווה על מספר השנים
- מס מחושב על החלק השנתי
- סה"כ מס = מס שנתי × מספר שנים

#### נכסי הון חייבים במס (TAXABLE)
- המס מחושב ב-Frontend באמצעות מדרגות מס שוליות
- Backend מחזיר 0 כדי למנוע כפילות
- זה מאפשר חישוב מדויק יותר עם הכנסות אחרות

---

## צעדים הבאים

1. ✅ יצירת מבנה מודולרי
2. ✅ יצירת כל המחשבונים
3. ✅ יצירת שירות מרכזי
4. ✅ תיעוד מקיף
5. ⏳ כתיבת בדיקות יחידה
6. ⏳ מעבר הדרגתי של קוד קיים
7. ⏳ הוצאת capital_asset_service.py מכלל שימוש (deprecated)

---

## תמיכה

לשאלות או בעיות, פנה למפתח הראשי או צור issue בפרויקט.

**גרסה**: 2.0  
**תאריך עדכון אחרון**: נובמבר 2025
