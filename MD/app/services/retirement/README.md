# Retirement Scenarios Module
# מודול תרחישי פרישה

## סקירה כללית

מודול זה מספק פונקציונליות מלאה לבניית וניתוח תרחישי פרישה.
הקוד המקורי (1429 שורות) פוצל למבנה מודולרי ומאורגן.

## מבנה התיקיות

```
app/services/retirement/
├── __init__.py                          # נקודת כניסה ראשית
├── README.md                            # תיעוד זה
├── constants.py                         # קבועים
├── scenario_builder.py                  # מנהל ראשי
├── base_scenario_builder.py             # מחלקת בסיס
│
├── scenarios/                           # מימושי תרחישים
│   ├── __init__.py
│   ├── max_pension_scenario.py          # תרחיש 1: מקסימום קצבה
│   ├── max_capital_scenario.py          # תרחיש 2: מקסימום הון
│   └── max_npv_scenario.py              # תרחיש 3: מאוזן (50/50)
│
├── services/                            # שירותים
│   ├── __init__.py
│   ├── state_service.py                 # ניהול מצב (שמירה/שחזור)
│   ├── conversion_service.py            # המרות בין נכסים
│   ├── termination_service.py           # טיפול בעזיבת עבודה
│   └── portfolio_import_service.py      # ייבוא תיק פנסיוני
│
└── utils/                               # כלי עזר
    ├── __init__.py
    ├── pension_utils.py                 # פונקציות קצבה
    ├── capital_utils.py                 # פונקציות הון
    ├── calculation_utils.py             # חישובים (NPV, DCF)
    └── serialization_utils.py           # סריאליזציה
```

## שימוש בסיסי

```python
from app.services.retirement import RetirementScenariosBuilder

# יצירת בונה תרחישים
builder = RetirementScenariosBuilder(
    db=db_session,
    client_id=123,
    retirement_age=67,
    pension_portfolio=pension_data  # אופציונלי
)

# בניית כל 3 התרחישים
scenarios = builder.build_all_scenarios()

# תוצאות:
# scenarios = {
#     "scenario_1_max_pension": {...},
#     "scenario_2_max_capital": {...},
#     "scenario_3_max_npv": {...}
# }
```

## תיאור התרחישים

### תרחיש 1: מקסימום קצבה
**מטרה:** מקסום הכנסה חודשית קבועה

**אסטרטגיה:**
1. המרת כל קרנות הפנסיה לקצבאות
2. המרת נכסי הון חייבים במס לקצבאות
3. המרת נכסי הון פטורים לקצבאות פטורות
4. המרת קרנות השתלמות לקצבאות פטורות
5. טיפול בפיצויי פרישה כקצבה

**מתאים ל:** מי שמעדיף ביטחון והכנסה קבועה

### תרחיש 2: מקסימום הון
**מטרה:** מקסום נזילות ושמירת גמישות

**אסטרטגיה:**
1. שמירת קצבת מינימום (5,500 ₪)
2. היוון כל שאר הקצבאות להון
3. שמירת נכסי הון כמות שהם
4. המרת קרנות השתלמות להון פטור

**חוק הברזל:** חובה לשמור קצבה מינימלית של 5,500 ₪

**מתאים ל:** מי שמעדיף גמישות ושליטה בנכסים

### תרחיש 3: מאוזן (50/50)
**מטרה:** איזון בין ביטחון לגמישות

**אסטרטגיה:**
1. המרת 50% מערך הקצבאות להון
2. שמירת 50% כקצבאות
3. שמירת נכסי הון קיימים
4. המרת קרנות השתלמות להון פטור

**מתאים ל:** מי שרוצה את שני העולמות

## רכיבים עיקריים

### 1. קבועים (constants.py)
```python
PENSION_COEFFICIENT = 200        # מקדם קצבה
MINIMUM_PENSION = 5500           # קצבת מינימום
HIGH_QUALITY_ANNUITY_THRESHOLD = 150
DEFAULT_DISCOUNT_RATE = 0.03     # 3% היוון
MAX_AGE_FOR_NPV = 90            # גיל מקסימלי לחישוב NPV
```

### 2. שירותים

#### StateService
ניהול מצב הנתונים - שמירה ושחזור של כל הנכסים

#### ConversionService
המרות בין סוגי נכסים:
- קרנות פנסיה ↔ קצבאות
- נכסי הון ↔ קצבאות
- קרנות השתלמות → הון פטור/קצבה פטורה

#### TerminationService
טיפול באירועי עזיבת עבודה:
- חישוב פיצויי פרישה
- המרה לקצבה או הון
- חישוב מקדמי קצבה דינמיים

#### PortfolioImportService
ייבוא תיק פנסיוני:
- זיהוי סוגי מוצרים
- קביעת מקדמי קצבה
- קביעת יחסי מס

### 3. כלי עזר

#### pension_utils.py
- `convert_balance_to_pension()` - המרת יתרה לקצבה
- `convert_capital_to_pension()` - המרת הון לקצבה
- `convert_education_fund_to_pension()` - המרת קרן השתלמות לקצבה
- `convert_education_fund_to_capital()` - המרת קרן השתלמות להון

#### capital_utils.py
- `create_capital_asset_from_pension()` - יצירת נכס הון מקצבה
- `capitalize_pension_with_factor()` - היוון קצבה עם מקדם

#### calculation_utils.py
- `calculate_npv_dcf()` - חישוב NPV בשיטת DCF
- `calculate_years_to_age()` - חישוב שנים עד גיל יעד

#### serialization_utils.py
- `serialize_pension_fund()` - המרת קרן פנסיה לדיקשנרי
- `serialize_capital_asset()` - המרת נכס הון לדיקשנרי
- `serialize_additional_income()` - המרת הכנסה נוספת
- `serialize_termination_event()` - המרת אירוע עזיבה

## חישובי NPV

המערכת משתמשת בשיטת DCF (Discounted Cash Flow):

```python
NPV = הון_חד_פעמי + Σ(תזרים_חודשי / (1 + r)^t)
```

כאשר:
- `r` = שיעור היוון חודשי (3% שנתי)
- `t` = מספר חודשים
- תקופה: מגיל פרישה עד גיל 90

## יחסי מס

### נכסי הון:
1. **פטור ממס (exempt)** - מס = 0
2. **חייב במס (taxable)** - מס שולי לפי מדרגות
3. **פריסת מס (tax_spread)** - פיצויי פרישה
4. **רווח הון (capital_gains)** - לא בשימוש בתרחישים

### קצבאות:
- **חייבת במס** - מס שולי
- **פטורה ממס** - מס = 0

## יתרונות המבנה החדש

### 1. אחזקה קלה
- כל קובץ אחראי על תפקיד אחד
- קל למצוא ולתקן באגים
- שינויים מקומיים לא משפיעים על כל המערכת

### 2. בדיקות
- כל רכיב ניתן לבדיקה עצמאית
- mock של שירותים קל יותר
- כיסוי טוב יותר

### 3. שימוש חוזר
- פונקציות עזר זמינות לכל התרחישים
- לוגיקה משותפת במחלקת הבסיס
- קל להוסיף תרחישים חדשים

### 4. קריאות
- קבצים קטנים וממוקדים
- שמות ברורים
- מבנה היררכי הגיוני

## הוספת תרחיש חדש

```python
# 1. צור קובץ חדש ב-scenarios/
from ..base_scenario_builder import BaseScenarioBuilder

class MyNewScenario(BaseScenarioBuilder):
    def build_scenario(self) -> Dict:
        # הלוגיקה שלך כאן
        return self._calculate_scenario_results("שם התרחיש")

# 2. הוסף ל-scenarios/__init__.py
from .my_new_scenario import MyNewScenario

# 3. הוסף ל-scenario_builder.py
scenario4 = MyNewScenario(...).build_scenario()
```

## סטטיסטיקה

### קובץ מקורי:
- **1429 שורות** בקובץ אחד
- **1 מחלקה ענקית** עם 40+ מתודות
- **קשה לתחזוקה** ובדיקה

### מבנה חדש:
- **15 קבצים** ממוקדים
- **ממוצע ~100 שורות** לקובץ
- **4 שירותים** עצמאיים
- **4 מודולי עזר**
- **3 תרחישים** נפרדים
- **1 מחלקת בסיס**

## תיקונים קריטיים שנשמרו

כל התיקונים הקריטיים מהקוד המקורי נשמרו:

✅ נכסי הון: `current_value=0`, `monthly_income=value`
✅ חישובי NPV: DCF תקין עד גיל 90
✅ חישוב מס משולב לפיצויים
✅ מקדמי קצבה דינמיים
✅ שימור יחסי מס בהמרות

## תמיכה ותחזוקה

לשאלות או בעיות:
1. בדוק את הלוגים - כל שירות מדווח על פעולותיו
2. בדוק את `execution_plan` בתוצאות - מפרט מלא של כל הפעולות
3. השתמש ב-debugger על קבצים ספציפיים

---

**גרסה:** 2.0.0  
**תאריך פיצול:** נובמבר 2025  
**מתחזק:** AI Assistant
