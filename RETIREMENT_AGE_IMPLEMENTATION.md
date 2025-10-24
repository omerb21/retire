# מערכת גיל פרישה דינמית - תיעוד מלא

## סקירה כללית

המערכת עברה שדרוג מקיף להפיכת גיל הפרישה לדינמי ומבוסס על חוק ישראלי. במקום הגדרות קבועות (67 לגברים, 62 לנשים), המערכת כעת מחשבת את גיל הפרישה המדויק לפי תאריך לידה ומגדר.

## שינויים מרכזיים

### 1. Backend - שירות חישוב גיל פרישה

#### קובץ חדש: `app/services/retirement_age_service.py`

**תכונות:**
- טבלה מלאה של גילאי פרישה לנשים לפי חוק ישראלי (1944-1970+)
- חישוב מדויק כולל חודשים (לא רק שנים שלמות)
- תמיכה בהגדרות מותאמות אישית
- שמירת הגדרות ב-JSON

**פונקציות עיקריות:**
- `calculate_retirement_age(birth_date, gender)` - חישוב מלא עם שנים וחודשים
- `get_retirement_age_simple(birth_date, gender)` - חישוב בשנים שלמות (תאימות לאחור)
- `get_retirement_date(birth_date, gender)` - מחזיר תאריך פרישה מדויק
- `load_retirement_age_settings()` - טעינת הגדרות מקובץ
- `save_retirement_age_settings()` - שמירת הגדרות לקובץ

**טבלת גילאי פרישה לנשים:**
```
תאריך לידה              גיל פרישה
עד מרץ 1944             60
אפריל-אוגוסט 1944       60 + 4 חודשים
ספטמבר 1944-אפריל 1945  60 + 8 חודשים
מאי-דצמבר 1945          61
ינואר-אוגוסט 1946       61 + 4 חודשים
ספטמבר 1946-אפריל 1947  61 + 8 חודשים
מאי 1947-דצמבר 1959     62
ינואר-דצמבר 1960        62 + 4 חודשים
ינואר-דצמבר 1961        62 + 8 חודשים
ינואר-דצמבר 1962        63
ינואר-דצמבר 1963        63 + 3 חודשים
ינואר-דצמבר 1964        63 + 6 חודשים
ינואר-דצמבר 1965        63 + 9 חודשים
ינואר-דצמבר 1966        64
ינואר-דצמבר 1967        64 + 3 חודשים
ינואר-דצמבר 1968        64 + 6 חודשים
ינואר-דצמבר 1969        64 + 9 חודשים
1970 ואילך              65
```

#### קובץ חדש: `app/routers/retirement_age.py`

**API Endpoints:**
- `POST /api/v1/retirement-age/calculate` - חישוב גיל פרישה מלא
- `POST /api/v1/retirement-age/calculate-simple` - חישוב פשוט (שנים שלמות)
- `GET /api/v1/retirement-age/settings` - קבלת הגדרות נוכחיות
- `POST /api/v1/retirement-age/settings` - עדכון הגדרות

### 2. עדכון שירותי Backend קיימים

#### `services/eligibility.py`
- **לפני:** גיל פרישה קבוע (67/62)
- **אחרי:** שימוש ב-`retirement_age_service.get_retirement_date()`

#### `app/services/rights_fixation.py`
- **לפני:** `birth_date.year + (67 if gender == "male" else 62)`
- **אחרי:** `get_retirement_date(birth_date, gender)`

#### `app/services/indexation_service.py`
- **לפני:** `retirement_age = 67 if gender.lower() in ['m', 'male', 'זכר'] else 62`
- **אחרי:** `get_retirement_date(birth_date, gender)`

#### `app/services/case_service.py`
- **לפני:** `retirement_age: int = 67` (פרמטר קבוע)
- **אחרי:** `retirement_age: Optional[int] = None` + חישוב דינמי מתאריך לידה

#### `app/main.py`
- הוספת `retirement_age` router לאפליקציה

### 3. Frontend - ממשק משתמש

#### קובץ חדש: `frontend/src/utils/retirementAge.ts`

**פונקציות עזר:**
- `calculateRetirementAge(birthDate, gender)` - חישוב מלא
- `calculateRetirementAgeSimple(birthDate, gender)` - חישוב פשוט
- `getRetirementAgeSettings()` - קבלת הגדרות מערכת
- `getDefaultRetirementAge(gender)` - ברירת מחדל לפי מגדר

#### `frontend/src/pages/SystemSettings.tsx`

**לשונית חדשה: "👤 גיל פרישה"**

תכונות:
- הגדרת גיל פרישה לגברים (ברירת מחדל: 67)
- בחירה בין טבלה חוקית לגיל קבוע לנשים
- הצגת טבלה מלאה של גילאי פרישה לנשים
- שמירה וטעינה של הגדרות
- הודעות משוב למשתמש

### 4. קובץ הגדרות

**קובץ חדש:** `retirement_age_settings.json` (נוצר אוטומטית)

```json
{
  "male_retirement_age": 67,
  "use_legal_table_for_women": true,
  "female_retirement_age": 65
}
```

## דוגמאות שימוש

### Backend (Python)

```python
from app.services.retirement_age_service import (
    calculate_retirement_age,
    get_retirement_age_simple,
    get_retirement_date
)
from datetime import date

# דוגמה 1: אישה שנולדה ב-1965
birth_date = date(1965, 6, 15)
result = calculate_retirement_age(birth_date, "female")
print(f"גיל פרישה: {result['age_years']} שנים ו-{result['age_months']} חודשים")
# פלט: גיל פרישה: 63 שנים ו-9 חודשים

# דוגמה 2: גבר שנולד ב-1960
birth_date = date(1960, 3, 20)
age = get_retirement_age_simple(birth_date, "male")
print(f"גיל פרישה: {age}")
# פלט: גיל פרישה: 67

# דוגמה 3: קבלת תאריך פרישה מדויק
retirement_date = get_retirement_date(birth_date, "male")
print(f"תאריך פרישה: {retirement_date}")
# פלט: תאריך פרישה: 2027-03-20
```

### Frontend (TypeScript)

```typescript
import { 
  calculateRetirementAgeSimple,
  getDefaultRetirementAge 
} from '../utils/retirementAge';

// דוגמה 1: חישוב גיל פרישה ללקוח
const age = await calculateRetirementAgeSimple('1965-06-15', 'female');
console.log(`גיל פרישה: ${age}`);
// פלט: גיל פרישה: 64

// דוגמה 2: קבלת ברירת מחדל לפי מגדר
const defaultAge = await getDefaultRetirementAge('male');
console.log(`גיל ברירת מחדל: ${defaultAge}`);
// פלט: גיל ברירת מחדל: 67
```

### API Calls

```bash
# חישוב גיל פרישה
curl -X POST http://localhost:8005/api/v1/retirement-age/calculate \
  -H "Content-Type: application/json" \
  -d '{"birth_date": "1965-06-15", "gender": "female"}'

# תשובה:
{
  "age_years": 63,
  "age_months": 9,
  "retirement_date": "2029-03-15",
  "source": "legal_table"
}

# קבלת הגדרות
curl http://localhost:8005/api/v1/retirement-age/settings

# עדכון הגדרות
curl -X POST http://localhost:8005/api/v1/retirement-age/settings \
  -H "Content-Type: application/json" \
  -d '{
    "male_retirement_age": 67,
    "use_legal_table_for_women": true
  }'
```

## השפעות על המערכת

### מודולים שעודכנו:
1. ✅ **קיבוע זכויות** - חישוב תאריך זכאות מדויק
2. ✅ **זיהוי מקרים (Case Detection)** - זיהוי אוטומטי של גיל פרישה
3. ✅ **תרחישי פרישה** - תמיכה בגיל פרישה דינמי
4. ✅ **חישובי מס והצמדה** - שימוש בתאריך פרישה מדויק
5. ✅ **דוחות ותזרים** - התאמה לגיל פרישה אמיתי

### מודולים שלא השתנו (עדיין משתמשים בבחירה ידנית):
- **Scenarios.tsx** - המשתמש בוחר גיל פרישה
- **RetirementScenarios.tsx** - המשתמש בוחר גיל פרישה
- **SimpleReports.tsx** - משתמש בנתונים מהשרת

## תאימות לאחור

המערכת שומרת על תאימות מלאה לאחור:
- פונקציות ישנות ממשיכות לעבוד
- קבועים `ELIG_AGE_MALE` ו-`ELIG_AGE_FEMALE` עדיין קיימים
- פרמטר `retirement_age` אופציונלי בפונקציות

## בדיקות מומלצות

### תרחישי בדיקה:

1. **אישה שנולדה ב-1960** → גיל פרישה: 62 + 4 חודשים
2. **אישה שנולדה ב-1965** → גיל פרישה: 63 + 9 חודשים
3. **אישה שנולדה ב-1970** → גיל פרישה: 65
4. **גבר שנולד ב-1960** → גיל פרישה: 67
5. **לקוח ללא תאריך לידה** → שימוש בברירת מחדל

### בדיקות פונקציונליות:

```bash
# הרצת הטסטים
pytest tests/test_retirement_age.py -v

# בדיקת API
python -m pytest tests/test_retirement_age_api.py -v
```

## הגדרות מומלצות

```json
{
  "male_retirement_age": 67,
  "use_legal_table_for_women": true
}
```

**הסבר:**
- `male_retirement_age: 67` - גיל פרישה לגברים לפי חוק
- `use_legal_table_for_women: true` - שימוש בטבלה החוקית (מומלץ!)

## פתרון בעיות

### בעיה: "Cannot find module retirement_age_service"
**פתרון:** ודא ש-`app/services/retirement_age_service.py` קיים

### בעיה: הגדרות לא נשמרות
**פתרון:** ודא הרשאות כתיבה לתיקיית המערכת

### בעיה: גיל פרישה לא מדויק לנשים
**פתרון:** ודא ש-`use_legal_table_for_women: true` בהגדרות

## תחזוקה עתידית

### הוספת שנים חדשות לטבלה:
ערוך את `FEMALE_RETIREMENT_AGE_TABLE` ב-`retirement_age_service.py`

### שינוי גיל פרישה לגברים:
עדכן דרך ממשק המשתמש או ישירות בקובץ `retirement_age_settings.json`

## סיכום

המערכת כעת תומכת בחישוב גיל פרישה דינמי ומדויק לפי חוק ישראלי, עם אפשרות להתאמה אישית דרך ממשק משתמש ידידותי. כל השירותים המרכזיים עודכנו להשתמש במערכת החדשה תוך שמירה על תאימות לאחור.

---
**תאריך יצירה:** 21/10/2025  
**גרסה:** 1.0  
**מחבר:** מערכת AI
