# Engine Package - מנועי חישוב מודולריים

## סקירה כללית

חבילת Engine מכילה מנועי חישוב מיוחדים לתכנון פרישה. הקוד מפוצל למודולים נפרדים לפי אחריות, מה שמשפר תחזוקה, בדיקות ושימוש חוזר.

## מבנה התיקיות

```
app/calculation/
├── engine/                      # חבילת מנועי החישוב
│   ├── __init__.py              # אתחול החבילה
│   ├── base_engine.py           # מחלקת בסיס אבסטרקטית
│   ├── seniority_engine.py      # חישובי ותק
│   ├── grant_engine.py          # חישובי מענקים והצמדה
│   ├── pension_engine.py        # חישובי המרה לקצבה
│   ├── cashflow_engine.py       # יצירת תזרים מזומנים
│   └── calculation_engine.py    # מנוע חישוב מרכזי
├── engine_factory.py            # Factory לייצור מנועים
└── engine_v2.py                 # מנוע חישוב מרכזי מעודכן (גרסה חלופית)
```

## המודולים

### 1. BaseEngine - מחלקת בסיס

מחלקה אבסטרקטית המגדירה ממשק משותף לכל המנועים.

**קובץ**: `base_engine.py`

```python
from app.calculation.engine import BaseEngine

class MyEngine(BaseEngine):
    def calculate(self, *args, **kwargs):
        # יישום החישוב
        pass
```

**מתודות**:
- `calculate()` - מתודה אבסטרקטית לביצוע חישוב
- `validate_inputs()` - אימות פרמטרים (ניתן לעקוף)

---

### 2. SeniorityEngine - חישובי ותק

מחשב שנות ותק בין שני תאריכים.

**קובץ**: `seniority_engine.py`

**שימוש**:
```python
from app.calculation.engine import SeniorityEngine
from datetime import date

engine = SeniorityEngine()
years = engine.calculate(
    start_date=date(2010, 1, 1),
    end_date=date(2025, 1, 1)
)
# תוצאה: 15.0
```

**מתודות**:
- `calculate(start_date, end_date=None)` - מחשב שנות ותק
  - `start_date`: תאריך התחלת עבודה
  - `end_date`: תאריך סיום (ברירת מחדל: היום)
  - **החזרה**: מספר שנות ותק (float)

**אימותים**:
- start_date חייב להיות לפני end_date
- שני התאריכים חייבים להיות אובייקטי date

---

### 3. GrantEngine - חישובי מענקים

מחשב מענקי פיצויים כולל הצמדה ומס.

**קובץ**: `grant_engine.py`

**שימוש**:
```python
from app.calculation.engine import GrantEngine
from app.providers.tax_params import TaxParamsProvider
from datetime import date

tax_provider = TaxParamsProvider()
engine = GrantEngine(tax_provider)

grant = engine.calculate(
    base_amount=100000.0,
    start_date=date(2010, 1, 1),
    end_date=date(2025, 1, 1),
    params=None  # יטען אוטומטית
)

print(f"ברוטו: {grant['gross']}")
print(f"פטור: {grant['exempt']}")
print(f"חייב: {grant['taxable']}")
print(f"מס: {grant['tax']}")
print(f"נטו: {grant['net']}")
print(f"מקדם הצמדה: {grant['indexation_factor']}")
```

**מתודות**:

1. `calculate(base_amount, start_date, end_date, params=None)`
   - **פרמטרים**:
     - `base_amount`: סכום בסיס לפני הצמדה
     - `start_date`: תאריך התחלת עבודה
     - `end_date`: תאריך סיום/חישוב
     - `params`: פרמטרי מס (אופציונלי)
   - **החזרה**: Dictionary עם:
     - `gross`: סכום מוצמד ברוטו
     - `exempt`: חלק פטור ממס
     - `taxable`: חלק חייב במס
     - `tax`: סכום המס
     - `net`: סכום נטו אחרי מס
     - `indexation_factor`: מקדם ההצמדה

2. `calculate_indexation_only(base_amount, start_date, end_date, params=None)`
   - מחשב רק הצמדה ללא רכיבי מס
   - **החזרה**: Dictionary עם `indexed_amount` ו-`indexation_factor`

**לוגיקה עסקית**:
- משתמש במקדמי הצמדה ממשרד האוצר
- מחשב פטור/חייב לפי חוקי המס
- מעגל תוצאות ל-2 ספרות אחרי הנקודה

---

### 4. PensionEngine - חישובי קצבה

ממיר הון לקצבה חודשית.

**קובץ**: `pension_engine.py`

**שימוש**:
```python
from app.calculation.engine import PensionEngine
from app.providers.tax_params import TaxParamsProvider

tax_provider = TaxParamsProvider()
engine = PensionEngine(tax_provider)

monthly = engine.calculate(
    capital=500000.0,
    params=None  # יטען אוטומטית
)
print(f"קצבה חודשית: ₪{monthly:,.2f}")

# עם פרטים נוספים
details = engine.calculate_with_details(capital=500000.0)
print(f"חודשי: {details['monthly_pension']}")
print(f"שנתי: {details['annual_pension']}")
print(f"הון: {details['capital']}")
```

**מתודות**:

1. `calculate(capital, params=None)`
   - **פרמטרים**:
     - `capital`: סכום הון להמרה
     - `params`: פרמטרי מס (אופציונלי)
   - **החזרה**: קצבה חודשית (float)

2. `calculate_with_details(capital, params=None)`
   - **החזרה**: Dictionary עם:
     - `monthly_pension`: קצבה חודשית
     - `annual_pension`: קצבה שנתית
     - `capital`: הון מקורי

**אימותים**:
- capital לא יכול להיות שלילי
- capital חייב להיות מספרי

---

### 5. CashflowEngine - תזרים מזומנים

יוצר תחזית תזרים מזומנים.

**קובץ**: `cashflow_engine.py`

**שימוש**:
```python
from app.calculation.engine import CashflowEngine
from datetime import date

engine = CashflowEngine()

cashflow = engine.calculate(
    start_date=date(2025, 1, 1),
    months=12,
    income=15000.0,
    expense=10000.0
)

# עם סטטיסטיקות
summary = engine.calculate_net_cashflow(
    start_date=date(2025, 1, 1),
    months=12,
    income=15000.0,
    expense=10000.0
)

print(f"סה\"כ הכנסות: {summary['total_income']}")
print(f"סה\"כ הוצאות: {summary['total_expense']}")
print(f"תזרים נטו: {summary['net_cashflow']}")
```

**מתודות**:

1. `calculate(start_date, months, income, expense=0.0)`
   - **פרמטרים**:
     - `start_date`: תאריך התחלה
     - `months`: מספר חודשים
     - `income`: הכנסה חודשית
     - `expense`: הוצאה חודשית
   - **החזרה**: רשימת פריטי תזרים

2. `calculate_net_cashflow(start_date, months, income, expense=0.0)`
   - **החזרה**: Dictionary עם:
     - `cashflow`: רשימת פריטים
     - `total_income`: סה"כ הכנסות
     - `total_expense`: סה"כ הוצאות
     - `net_cashflow`: תזרים נטו
     - `months`: מספר חודשים

**אימותים**:
- months חייב להיות חיובי ושלם
- income ו-expense לא יכולים להיות שליליים

---

## EngineFactory - יצירת מנועים

Factory pattern ליצירת מופעי מנועים.

**קובץ**: `engine_factory.py`

**שימוש**:

```python
from app.calculation.engine_factory import EngineFactory
from sqlalchemy.orm import Session
from app.providers.tax_params import TaxParamsProvider

# יצירת כל המנועים
engines = EngineFactory.create_engines(db, tax_provider)
seniority = engines['seniority'].calculate(start, end)
grant = engines['grant'].calculate(amount, start, end)

# יצירת מנוע בודד
seniority_engine = EngineFactory.create_seniority_engine()
grant_engine = EngineFactory.create_grant_engine(tax_provider)
pension_engine = EngineFactory.create_pension_engine(tax_provider)
cashflow_engine = EngineFactory.create_cashflow_engine()
```

**מתודות**:
- `create_engines(db, tax_provider)` - יוצר את כל המנועים
- `create_seniority_engine()` - יוצר מנוע ותק
- `create_grant_engine(tax_provider)` - יוצר מנוע מענקים
- `create_pension_engine(tax_provider)` - יוצר מנוע קצבה
- `create_cashflow_engine()` - יוצר מנוע תזרים

---

## CalculationEngineV2 - מנוע מרכזי מעודכן

מנוע חישוב מרכזי המשתמש במנועים המודולריים.

**קובץ**: `engine_v2.py`

**שימוש**:

```python
from app.calculation.engine_v2 import CalculationEngineV2
from app.schemas.scenario import ScenarioIn
from sqlalchemy.orm import Session
from app.providers.tax_params import TaxParamsProvider

engine = CalculationEngineV2(db, tax_provider)

# חישוב תרחיש מלא
scenario = ScenarioIn(
    planned_termination_date=date(2025, 12, 31),
    other_incomes_monthly=5000.0,
    monthly_expenses=8000.0
)

result = engine.run(client_id=1, scenario=scenario)

print(f"ותק: {result.seniority_years} שנים")
print(f"מענק ברוטו: ₪{result.grant_gross:,.2f}")
print(f"מענק נטו: ₪{result.grant_net:,.2f}")
print(f"קצבה חודשית: ₪{result.pension_monthly:,.2f}")

# חישובים חלקיים
seniority = engine.calculate_seniority_only(client_id=1)
grant = engine.calculate_grant_only(client_id=1, base_amount=100000)
```

**מתודות**:

1. `run(client_id, scenario)` - מריץ תרחיש מלא
2. `calculate_seniority_only(client_id, end_date=None)` - רק ותק
3. `calculate_grant_only(client_id, base_amount, end_date=None)` - רק מענק

---

## CalculationEngine - מנוע חישוב מרכזי

מנוע החישוב המרכזי שמתאם את כל המנועים המודולריים.

**קובץ**: `calculation_engine.py`

**שימוש**:

```python
from app.calculation.engine import CalculationEngine
from app.schemas.scenario import ScenarioIn
from sqlalchemy.orm import Session
from app.providers.tax_params import TaxParamsProvider

engine = CalculationEngine(db, tax_provider)

# חישוב תרחיש מלא
scenario = ScenarioIn(
    planned_termination_date=date(2025, 12, 31),
    other_incomes_monthly=5000.0,
    monthly_expenses=8000.0
)

result = engine.run(client_id=1, scenario=scenario)

print(f"ותק: {result.seniority_years} שנים")
print(f"מענק ברוטו: ₪{result.grant_gross:,.2f}")
print(f"מענק נטו: ₪{result.grant_net:,.2f}")
print(f"קצבה חודשית: ₪{result.pension_monthly:,.2f}")
```

**מתודות**:

1. `run(client_id, scenario)` - מריץ תרחיש מלא
   - מאמת לקוח ותעסוקה
   - מחשב ותק
   - מחשב מענק עם הצמדה
   - מחשב מס
   - מחשב קצבה
   - יוצר תזרים מזומנים

---

## תאימות לאחור

**הקובץ המקורי `engine.py` הוסר והוחלף ב-`calculation_engine.py`!**

כל הייבואים עודכנו אוטומטית. הקוד הקיים ממשיך לעבוד בדיוק כמו קודם.

### שימוש נוכחי

```python
# ייבוא מהחבילה (מומלץ)
from app.calculation.engine import CalculationEngine
engine = CalculationEngine(db, tax_provider)

# ייבוא ישיר (אפשרי)
from app.calculation.engine.calculation_engine import CalculationEngine
engine = CalculationEngine(db, tax_provider)

# גרסה חלופית (מומלץ לקוד חדש)
from app.calculation.engine_v2 import CalculationEngineV2
engine = CalculationEngineV2(db, tax_provider)
```

---

## יתרונות הפיצול

### 1. **אחריות יחידה** (Single Responsibility)
כל מנוע עוסק בתחום אחד בלבד:
- SeniorityEngine → רק ותק
- GrantEngine → רק מענקים
- PensionEngine → רק קצבאות
- CashflowEngine → רק תזרים

### 2. **בדיקות קלות**
```python
# בדיקת יחידה פשוטה
def test_seniority_calculation():
    engine = SeniorityEngine()
    years = engine.calculate(date(2020, 1, 1), date(2025, 1, 1))
    assert years == 5.0
```

### 3. **שימוש חוזר**
```python
# שימוש במנוע בודד בקוד אחר
from app.calculation.engine import GrantEngine

grant_engine = GrantEngine(tax_provider)
grant = grant_engine.calculate(100000, start, end)
```

### 4. **הרחבה קלה**
הוספת מנוע חדש:
```python
# app/calculation/engine/new_engine.py
from .base_engine import BaseEngine

class NewEngine(BaseEngine):
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

### דוגמה 1: חישוב מענק עם הצמדה בלבד

```python
from app.calculation.engine import GrantEngine
from app.providers.tax_params import TaxParamsProvider

tax_provider = TaxParamsProvider()
engine = GrantEngine(tax_provider)

# רק הצמדה
indexation = engine.calculate_indexation_only(
    base_amount=100000,
    start_date=date(2010, 1, 1),
    end_date=date(2025, 1, 1)
)

print(f"סכום מוצמד: {indexation['indexed_amount']}")
print(f"מקדם: {indexation['indexation_factor']}")
```

### דוגמה 2: תזרים עם סטטיסטיקות

```python
from app.calculation.engine import CashflowEngine

engine = CashflowEngine()

summary = engine.calculate_net_cashflow(
    start_date=date(2025, 1, 1),
    months=60,  # 5 שנים
    income=20000,
    expense=15000
)

print(f"תזרים נטו ל-5 שנים: ₪{summary['net_cashflow']:,.2f}")
print(f"חיסכון חודשי ממוצע: ₪{summary['net_cashflow'] / 60:,.2f}")
```

### דוגמה 3: שרשור מנועים

```python
from app.calculation.engine_factory import EngineFactory

engines = EngineFactory.create_engines(db, tax_provider)

# שרשור: ותק → מענק → קצבה
seniority = engines['seniority'].calculate(start, end)
grant = engines['grant'].calculate(100000 * seniority, start, end)
pension = engines['pension'].calculate(grant['net'])

print(f"ותק: {seniority} שנים")
print(f"מענק נטו: ₪{grant['net']:,.2f}")
print(f"קצבה: ₪{pension:,.2f}")
```

---

## הערות חשובות

### תלויות
- **SeniorityEngine**: אין תלויות
- **GrantEngine**: דורש TaxParamsProvider
- **PensionEngine**: דורש TaxParamsProvider (אופציונלי)
- **CashflowEngine**: אין תלויות

### טיפול בשגיאות
כל המנועים מבצעים אימות קלט ומעלים `ValueError` במקרה של נתונים לא תקינים.

```python
try:
    result = engine.calculate(...)
except ValueError as e:
    print(f"שגיאה: {e}")
```

### ביצועים
המנועים המודולריים מהירים כמו הקוד המקורי. אין overhead משמעותי.

---

## צעדים הבאים

1. ✅ יצירת מבנה מודולרי
2. ✅ יצירת כל המנועים
3. ✅ יצירת Factory
4. ✅ יצירת מנוע מרכזי V2
5. ⏳ כתיבת בדיקות יחידה
6. ⏳ מעבר הדרגתי של קוד קיים
7. ⏳ הוצאת engine.py מכלל שימוש (deprecated)

---

## תמיכה

לשאלות או בעיות, פנה למפתח הראשי או צור issue בפרויקט.

**גרסה**: 2.0  
**תאריך עדכון אחרון**: נובמבר 2025
