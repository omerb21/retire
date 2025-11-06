# 🛡️ מדריך תקינות מערכת - System Integrity Guide

## 📋 תוכן עניינים
1. [סקירה כללית](#סקירה-כללית)
2. [הבעיה שנפתרה](#הבעיה-שנפתרה)
3. [הפתרון](#הפתרון)
4. [מנגנון האימות](#מנגנון-האימות)
5. [שימוש במערכת](#שימוש-במערכת)
6. [טבלאות קריטיות](#טבלאות-קריטיות)
7. [תיקון אוטומטי](#תיקון-אוטומטי)

---

## 🎯 סקירה כללית

מערכת תקינות המערכת (System Integrity) היא מנגנון אימות אוטומטי שמוודא שכל הטבלאות והנתונים הקריטיים במערכת קיימים ותקינים.

### מטרות המערכת:
- ✅ **מניעת תקלות חוזרות** - זיהוי בעיות לפני שהן משפיעות על המשתמש
- ✅ **תיקון אוטומטי** - טעינת נתונים חסרים מקבצי CSV
- ✅ **שקיפות מלאה** - דוחות מפורטים על סטטוס המערכת
- ✅ **מעקב רציף** - בדיקה אוטומטית בהפעלת השרת

---

## 🔍 הבעיה שנפתרה

### התסמינים:
1. **מקדמי קצבה חוזרים ל-200** - במקום מקדמים מדויקים מהטבלה
2. **חישובים שגויים** - בגלל נתונים חסרים
3. **תקלות חוזרות** - אותן בעיות מופיעות שוב ושוב
4. **אין אינדיקציה** - המערכת לא מתריעה על נתונים חסרים

### השורש:
הטבלאות הקריטיות (כמו `pension_fund_coefficient`) היו **ריקות** במסד הנתונים, אבל המערכת המשיכה לפעול עם ברירות מחדל שגויות.

---

## 💡 הפתרון

### 1️⃣ מאמת מערכת (System Validator)
**קובץ**: `app/core/system_validator.py`

מחלקה שבודקת את תקינות כל הטבלאות הקריטיות:

```python
class SystemValidator:
    """מאמת תקינות המערכת בהפעלה"""
    
    CRITICAL_TABLES = {
        'pension_fund_coefficient': {
            'min_rows': 1000,
            'description': 'מקדמי קצבה לקרנות פנסיה',
            'csv_file': 'MEKEDMIM/pension_fund_coefficient.csv'
        },
        # ... טבלאות נוספות
    }
```

### 2️⃣ אינטגרציה בהפעלת השרת
**קובץ**: `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on application startup"""
    Base.metadata.create_all(bind=engine)
    
    # אימות תקינות המערכת
    from app.core.system_validator import validate_system_on_startup
    
    db = next(get_db())
    try:
        is_valid = validate_system_on_startup(db)
        if not is_valid:
            logger.error("⚠️ System validation failed")
        else:
            logger.info("✅ System validation passed")
    finally:
        db.close()
```

### 3️⃣ API Endpoints
**קובץ**: `app/routers/system_health.py`

- `GET /api/v1/system/health` - בדיקת תקינות
- `POST /api/v1/system/health/fix` - תיקון אוטומטי
- `GET /api/v1/system/health/report` - דוח מפורט
- `GET /api/v1/system/health/tables/{table_name}` - מידע על טבלה ספציפית

### 4️⃣ ממשק משתמש
**קובץ**: `frontend/src/components/system-settings/SystemHealthMonitor.tsx`

לשונית חדשה במסך הגדרות: **🏥 תקינות מערכת**

תכונות:
- תצוגה ויזואלית של סטטוס כל טבלה
- כפתור "תקן אוטומטית"
- רענון אוטומטי כל 5 דקות
- התראות על בעיות

---

## 🔧 מנגנון האימות

### תהליך הבדיקה:

```
1. בדיקת קיום טבלה
   ↓
2. ספירת שורות
   ↓
3. השוואה למינימום נדרש
   ↓
4. דיווח תוצאות
```

### קריטריונים לתקינות:

| טבלה | מינימום שורות | תיאור |
|------|--------------|-------|
| `pension_fund_coefficient` | 1,000 | מקדמי קצבה לקרנות פנסיה |
| `insurance_generation_coefficient` | 100 | מקדמי דורות ביטוח מנהלים |
| `insurance_company_coefficient` | 10 | מקדמים ספציפיים לחברות |
| `tax_brackets` | 5 | מדרגות מס |
| `severance_caps` | 5 | תקרות פיצויים |
| `pension_ceilings` | 5 | תקרות קצבה |

---

## 📊 שימוש במערכת

### בהפעלת השרת:

```bash
python -m uvicorn app.main:app --reload --port 8005
```

**פלט צפוי:**
```
============================================================
🚀 Starting Retirement Planning System
============================================================
🔍 Starting system validation...
✅ מקדמי קצבה לקרנות פנסיה - תקין
✅ מקדמי דורות ביטוח מנהלים - תקין
✅ מקדמים ספציפיים לחברות - תקין
✅ מדרגות מס - תקין
✅ תקרות פיצויים - תקין
✅ תקרות קצבה - תקין
✅ System validation passed - all critical data is present
============================================================
```

### בממשק המשתמש:

1. עבור למסך **הגדרות מערכת**
2. לחץ על לשונית **🏥 תקינות מערכת**
3. צפה בסטטוס כל הטבלאות
4. אם יש בעיות - לחץ **🔧 תקן אוטומטית**

### דרך API:

```bash
# בדיקת תקינות
curl http://localhost:8005/api/v1/system/health

# תיקון אוטומטי
curl -X POST http://localhost:8005/api/v1/system/health/fix

# דוח מפורט
curl http://localhost:8005/api/v1/system/health/report
```

---

## 📦 טבלאות קריטיות

### 1. מקדמי קצבה לקרנות פנסיה
**טבלה**: `pension_fund_coefficient`  
**CSV**: `MEKEDMIM/pension_fund_coefficient.csv`  
**שורות**: 75,440

**תיאור**: מקדמים לחישוב קצבה חודשית מיתרת חיסכון, לפי:
- גיל פרישה (60-80)
- מגדר (זכר/נקבה)
- מסלול שארים (תקנוני)
- הפרש גיל בן זוג (-20 עד +20)
- תקופת הבטחה (0, 60, 120, 180, 240 חודשים)

**דוגמה**:
```
זכר, גיל 67, תקנוני, הפרש 0 → מקדם 168.24
יתרה 200,000 ÷ 168.24 = קצבה חודשית 1,189 ₪
```

### 2. מקדמי דורות ביטוח מנהלים
**טבלה**: `insurance_generation_coefficient`  
**CSV**: `MEKEDMIM/insurance_generation_coefficient.csv`  
**שורות**: 147

**תיאור**: מקדמים לפי תקופת הפוליסה (7 דורות):
- עד 31.12.1989
- 01.01.1990 - 31.12.1995
- 01.01.1996 - 31.12.2003
- 01.01.2004 - 31.12.2008
- 01.01.2009 - 31.12.2012
- 01.01.2013 - 31.12.2016
- 01.01.2017 ואילך

**דוגמה**:
```
דור 2004-2008, זכר, גיל 67 → מקדם 206.87
```

### 3. מקדמים ספציפיים לחברות
**טבלה**: `insurance_company_coefficient`  
**CSV**: `MEKEDMIM/insurance_company_coefficient.csv`  
**שורות**: מגוון

**תיאור**: מקדמים מדויקים לחברות ביטוח ספציפיות:
- כלל (מינימום 180)
- הראל (מינימום 240)
- חברות נוספות

### 4. מדרגות מס
**טבלה**: `tax_brackets`  
**מקור**: localStorage (Frontend)

**תיאור**: מדרגות מס הכנסה לפי שנים

### 5. תקרות פיצויים
**טבלה**: `severance_caps`  
**מקור**: Backend API

**תיאור**: תקרות פיצויי פיטורין לפי שנים

### 6. תקרות קצבה
**טבלה**: `pension_ceilings`  
**מקור**: localStorage (Frontend)

**תיאור**: תקרות קצבה מזכה לפי שנים

---

## 🔧 תיקון אוטומטי

### איך זה עובד?

1. **זיהוי בעיה**: המאמת מזהה טבלה ריקה או חסרת נתונים
2. **בדיקת CSV**: בודק אם קיים קובץ CSV מתאים
3. **טעינת נתונים**: טוען את הנתונים מה-CSV למסד
4. **אימות מחדש**: בודק שהבעיה נפתרה

### דוגמה:

```python
# המערכת מזהה: pension_fund_coefficient ריקה
validator.auto_fix_missing_data()

# פלט:
📥 Loading pension_fund_coefficient from MEKEDMIM/pension_fund_coefficient.csv...
✅ Loaded 75,440 rows into pension_fund_coefficient
✅ Successfully loaded pension_fund_coefficient
```

### מה קורה אם התיקון נכשל?

המערכת תדווח:
```
❌ Failed to load pension_fund_coefficient: [error message]
⚠️ Manual intervention required
```

**פעולות ידניות נדרשות**:
1. בדוק שקובץ ה-CSV קיים ותקין
2. בדוק הרשאות קריאה/כתיבה
3. בדוק שמסד הנתונים זמין
4. הרץ ידנית:
   ```python
   python -c "import pandas as pd; from app.database import engine; df = pd.read_csv('MEKEDMIM/pension_fund_coefficient.csv'); df.to_sql('pension_fund_coefficient', engine, if_exists='replace', index=False)"
   ```

---

## 🎯 מניעת בעיות עתידיות

### כללי זהב:

1. **אל תמחק טבלאות** - אם צריך לרענן, השתמש ב-`REPLACE` לא `DROP`
2. **שמור גיבויים** - של קבצי ה-CSV וה-DB
3. **בדוק אחרי שינויים** - הרץ את המאמת אחרי כל שינוי במבנה
4. **עקוב אחרי לוגים** - שים לב להתראות בהפעלת השרת
5. **השתמש בממשק** - לשונית "תקינות מערכת" היא החבר שלך

### תחזוקה שוטפת:

- **שבועי**: בדוק את לשונית "תקינות מערכת"
- **חודשי**: גבה את מסד הנתונים וקבצי ה-CSV
- **אחרי עדכון**: הרץ אימות מלא
- **לפני דפלוי**: וודא שכל הטבלאות תקינות

---

## 📚 קבצים קשורים

### Backend:
- `app/core/system_validator.py` - מנגנון האימות
- `app/routers/system_health.py` - API endpoints
- `app/main.py` - אינטגרציה בהפעלה

### Frontend:
- `frontend/src/components/system-settings/SystemHealthMonitor.tsx` - ממשק משתמש
- `frontend/src/pages/SystemSettings.tsx` - אינטגרציה במסך הגדרות
- `frontend/src/types/system-settings.types.ts` - טייפים

### Data:
- `MEKEDMIM/pension_fund_coefficient.csv`
- `MEKEDMIM/insurance_generation_coefficient.csv`
- `MEKEDMIM/insurance_company_coefficient.csv`

### Documentation:
- `docs/SYSTEM_INTEGRITY_GUIDE.md` - מדריך זה
- `frontend/src/components/system-settings/AnnuitySettings.tsx` - תיעוד מקדמי קצבה

---

## 🚨 פתרון בעיות

### בעיה: השרת לא מתחיל

**תסמינים**:
```
❌ System validation error: [error]
```

**פתרון**:
1. בדוק שמסד הנתונים קיים: `retire.db`
2. בדוק הרשאות קריאה/כתיבה
3. הרץ ידנית את הטעינה (ראה למעלה)

### בעיה: טבלה מסומנת כלא תקינה

**תסמינים**:
```
⚠️ טבלה 'pension_fund_coefficient' מכילה רק 0 שורות
```

**פתרון**:
1. לחץ "תקן אוטומטית" בממשק
2. אם נכשל - בדוק שקובץ ה-CSV קיים
3. הרץ ידנית את הטעינה

### בעיה: מקדמים עדיין 200

**תסמינים**:
- קצבאות מקבלות מקדם 200 במקום מקדם מדויק

**פתרון**:
1. בדוק בלשונית "תקינות מערכת" שהטבלה תקינה
2. אתחל את השרת מחדש
3. נקה cache של הדפדפן (Ctrl+Shift+R)
4. בדוק בקונסול שאין שגיאות

---

## ✅ סיכום

מערכת תקינות המערכת מבטיחה ש:

1. ✅ **כל הנתונים הקריטיים קיימים** - לא עוד ברירות מחדל שגויות
2. ✅ **זיהוי מוקדם של בעיות** - לפני שהן משפיעות על המשתמש
3. ✅ **תיקון אוטומטי** - רוב הבעיות נפתרות אוטומטית
4. ✅ **שקיפות מלאה** - תמיד יודעים מה המצב
5. ✅ **מניעת תקלות חוזרות** - הבעיה נפתרה לצמיתות

**זכור**: המערכת עובדת בשבילך. אם יש בעיה - היא תגיד לך ותנסה לתקן!

---

**תאריך יצירה**: 6 בנובמבר 2025  
**גרסה**: 1.0  
**מחבר**: System Integrity Team
