# Tax Data Service - Modular Structure

מודול מודולרי לניהול נתוני מס ממקורות ממשלתיים רשמיים.

## 📁 מבנה התיקיות

```
app/services/tax_data/
├── __init__.py              # נקודת כניסה מרכזית + TaxDataService לתאימות לאחור
├── base_service.py          # מחלקת בסיס עם utilities משותפים
├── severance_caps.py        # ניהול תקרות פיצויים
├── cpi_service.py           # נתוני מדד המחירים לצרכן (CBS)
├── tax_brackets.py          # מדרגות מס הכנסה
├── indexation.py            # חישובי הצמדה למדד
├── cache_manager.py         # ניהול cache של נתוני מס
└── README.md                # תיעוד זה
```

## 🎯 מטרת הפיצול

הקובץ המקורי `tax_data_service.py` היה מונוליתי ובלתי נוח לתחזוקה. הפיצול למודולים קטנים מאפשר:

- **קריאות משופרת** - כל מודול אחראי על תחום ספציפי
- **תחזוקה קלה** - שינויים במודול אחד לא משפיעים על אחרים
- **בדיקות יעילות** - ניתן לבדוק כל מודול בנפרד
- **הרחבה פשוטה** - קל להוסיף שירותים חדשים

## 📚 המודולים

### 1. `base_service.py`
מחלקת בסיס עם פונקציות עזר משותפות:
- `_get_most_recent_data()` - קבלת הנתון האחרון מרשימה
- `_get_data_for_year()` - קבלת נתונים לשנה ספציפית
- `_get_current_year()` - קבלת השנה הנוכחית

### 2. `severance_caps.py`
ניהול תקרות פיצויים:
- `get_severance_caps()` - קבלת כל התקרות לפי שנה
- `get_current_severance_cap(year)` - קבלת תקרה לשנה ספציפית
- `get_severance_exemption_amount(service_years, year)` - חישוב פטור ממס
- `update_severance_caps(caps)` - עדכון תקרות

### 3. `cpi_service.py`
נתוני מדד המחירים לצרכן:
- `get_cpi_data(start_year, end_year)` - קבלת נתוני מדד
- `_get_fallback_cpi_data()` - נתוני fallback כאשר CBS API לא זמין

### 4. `tax_brackets.py`
מדרגות מס הכנסה:
- `get_tax_brackets(year)` - קבלת מדרגות מס לשנה
- `_get_tax_brackets_by_year(year)` - מדרגות מס מדויקות לפי חוק

### 5. `indexation.py`
חישובי הצמדה:
- `calculate_indexation_factor(base_year, target_year)` - חישוב מקדם הצמדה בין שנים

### 6. `cache_manager.py`
ניהול cache:
- `update_tax_data_cache()` - עדכון cache מכל המקורות

## 🔄 שימוש

### שימוש חדש (מומלץ)

```python
# ייבוא ישירות מהמודול הספציפי
from app.services.tax_data.severance_caps import SeveranceCapsService
from app.services.tax_data.cpi_service import CPIService
from app.services.tax_data.tax_brackets import TaxBracketsService
from app.services.tax_data.indexation import IndexationService

# שימוש
cap = SeveranceCapsService.get_current_severance_cap(2025)
cpi = CPIService.get_cpi_data(2020, 2025)
brackets = TaxBracketsService.get_tax_brackets(2025)
factor = IndexationService.calculate_indexation_factor(2020, 2025)
```

### שימוש ישן (תאימות לאחור)

```python
# ממשיך לעבוד בדיוק כמו קודם
from app.services.tax_data_service import TaxDataService

# כל המתודות הישנות עובדות
cap = TaxDataService.get_current_severance_cap(2025)
cpi = TaxDataService.get_cpi_data(2020, 2025)
brackets = TaxDataService.get_tax_brackets(2025)
```

### שימוש מהממשק המאוחד

```python
# ייבוא מה-__init__.py
from app.services.tax_data import TaxDataService

# כל הפונקציונליות זמינה
cap = TaxDataService.get_current_severance_cap(2025)
```

## ✅ תאימות לאחור

הפיצול שומר על **תאימות לאחור מלאה**:

1. **קובץ wrapper** - `tax_data_service.py` מייצא מחדש את `TaxDataService`
2. **ממשק מאוחד** - `__init__.py` מספק את כל הפונקציות הישנות
3. **אין שינוי ב-API** - כל הקוד הקיים ממשיך לעבוד ללא שינויים

## 📝 דוגמאות שימוש

### חישוב פטור ממס על פיצויים

```python
from app.services.tax_data.severance_caps import SeveranceCapsService

# חישוב פטור ממס לעובד עם 15 שנות ותק
service_years = 15
exemption = SeveranceCapsService.get_severance_exemption_amount(service_years, 2025)
print(f"פטור ממס: ₪{exemption:,.2f}")
```

### חישוב הצמדה למדד

```python
from app.services.tax_data.indexation import IndexationService

# חישוב הצמדה בין 2020 ל-2025
factor = IndexationService.calculate_indexation_factor(2020, 2025)
original_amount = 100000
indexed_amount = original_amount * factor
print(f"סכום מקורי: ₪{original_amount:,.2f}")
print(f"סכום מוצמד: ₪{indexed_amount:,.2f}")
print(f"מקדם הצמדה: {factor:.4f}")
```

### קבלת מדרגות מס

```python
from app.services.tax_data.tax_brackets import TaxBracketsService

# קבלת מדרגות מס לשנת 2025
brackets = TaxBracketsService.get_tax_brackets(2025)
for bracket in brackets:
    print(f"{bracket['description']}: {bracket['min_income']:,} - {bracket['max_income']:,}")
```

## 🔧 הוספת שנים חדשות

### הוספת תקרות פיצויים לשנה חדשה

ערוך את `severance_caps.py`:

```python
def _get_default_severance_caps(cls) -> List[Dict]:
    return [
        {'year': 2026, 'monthly_cap': 14000, 'annual_cap': 14000 * 12, 'description': 'תקרה חודשית לשנת 2026'},
        # ... שאר השנים
    ]
```

### הוספת מדרגות מס לשנה חדשה

ערוך את `tax_brackets.py`:

```python
def _get_tax_brackets_by_year(year: int) -> List[Dict]:
    if year >= 2026:
        return [
            {'min_income': 0, 'max_income': 85000, 'rate': 0.10, 'description': 'מדרגה ראשונה - 10%'},
            # ... שאר המדרגות
        ]
```

### הוספת נתוני CPI

ערוך את `cpi_service.py`:

```python
def _get_fallback_cpi_data(start_year: int, end_year: int) -> List[Dict]:
    cpi_data = {
        # ... שנים קיימות
        2026: 119.8  # נתון חדש
    }
```

## 🧪 בדיקות

כל מודול ניתן לבדיקה עצמאית:

```python
# בדיקת severance_caps
from app.services.tax_data.severance_caps import SeveranceCapsService
caps = SeveranceCapsService.get_severance_caps()
assert len(caps) > 0
assert all('year' in cap for cap in caps)

# בדיקת indexation
from app.services.tax_data.indexation import IndexationService
factor = IndexationService.calculate_indexation_factor(2024, 2025)
assert factor > 1.0  # צפוי גידול בשל אינפלציה
```

## 📊 מקורות נתונים

- **תקרות פיצויים**: רשות המיסים הישראלית
- **מדד המחירים**: הלשכה המרכזית לסטטיסטיקה (CBS)
- **מדרגות מס**: חוק מס הכנסה (פקודת מס הכנסה)

## 🔐 אבטחה

- כל הנתונים מגיעים ממקורות ממשלתיים רשמיים
- יש fallback למקרה שה-API לא זמין
- הנתונים נשמרים ב-cache לביצועים טובים יותר

## 📞 תמיכה

לשאלות או בעיות, פנה למפתח המערכת.

---

**גרסה**: 1.0.0  
**תאריך עדכון אחרון**: נובמבר 2025  
**מפתח**: צוות פיתוח מערכת פנסיה
