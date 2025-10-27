# מערכת מקדמי קצבה דינמית - תיעוד מלא

## 📋 סקירה כללית

המערכת מחשבת מקדמי קצבה דינמיים לפי סוג מוצר, גיל, מגדר וחברה.
במקום מקדם קבוע של 200, המערכת שולפת את המקדם המדויק מטבלאות מקיפות.

## 🎯 מטרת המערכת

כאשר ממירים כספים לקצבה מתיק פנסיוני, המערכת:
1. מזהה את סוג המוצר (קרן פנסיה / ביטוח מנהלים)
2. **מזהה את דור הפוליסה** לפי תאריך התחלת התכנית (start_date)
3. **מחשבת את גיל הלקוח בפועל** בתאריך תחילת הקצבה (pension_start_date)
4. שולפת את נתוני הלקוח (מגדר)
5. מחפשת את המקדם המתאים בטבלאות לפי: דור + גיל בפועל + מין
6. מחשבת את הקצבה החודשית: `יתרה / מקדם`
7. שומרת את פרטי המקדם בהערות הקצבה

### 🔑 נקודות קריטיות:
- **תאריך התחלת התכנית** (start_date) קובע את **דור הפוליסה**
- **תאריך תחילת הקצבה** (pension_start_date) קובע את **הגיל בפועל**
- המקדם נבחר לפי **גיל בתאריך המימוש**, לא גיל פרישה

## 📊 טבלאות המקדמים

### 1️⃣ policy_generation_coefficient
**דורות פוליסות ביטוח מנהלים** - 147 שורות (7 דורות × 21 גילאים)

**מבנה:** כל דור כולל מקדמים לגילאים 60-80, בנפרד לזכר ונקבה

| תקופה | גיל | מקדם זכר | מקדם נקבה | הבטחה |
|-------|-----|----------|-----------|-------|
| עד 31.12.1989 | 60 | 169.2 | 189.2 | 120 |
| עד 31.12.1989 | 65 | 144.2 | 164.2 | 120 |
| עד 31.12.1989 | 68 | 129.2 | 149.2 | 120 |
| 2004-2008 | 60 | 224.37 | 244.37 | 240 |
| 2004-2008 | 67 | 206.87 | 226.87 | 240 |
| 2013 ואילך | 65 | 214.35 | 234.35 | 240 |

**כללי חישוב:**
- שינוי ליניארי לפי תקופת הבטחה:
  - 120 חודשים: 5 נקודות לשנה
  - 180 חודשים: 4.3 נקודות לשנה
  - 240 חודשים: 2.5 נקודות לשנה

### 2️⃣ product_to_generation_map
**מיפוי סוג מוצר לדור** - קובע איזה דור להשתמש לפי תאריך התחלה

### 3️⃣ company_annuity_coefficient
**מקדמים ספציפיים לחברות** - כלל, הראל

| חברה | מסלול | מגדר | גיל | מקדם בסיס | עליה שנתית |
|------|-------|------|-----|-----------|------------|
| כלל | מינימום 180 | זכר | 60 | 228.41 | 0.353% |
| כלל | מינימום 180 | נקבה | 60 | 238.51 | 0.316% |
| הראל | מינימום 240 | זכר | 67 | 201.81 | 0.149% |
| הראל | מינימום 240 | נקבה | 67 | 207.22 | 0.195% |

**חישוב לשנת יעד:**
```
מקדם = מקדם_בסיס × (1 + שיעור_עליה_שנתי × (שנת_יעד - שנת_בסיס))
```

### 4️⃣ pension_fund_coefficient
**מקדמים לקרנות פנסיה** - 75,440 שורות

**מבנה:** כל שילוב אפשרי של:
- גילאים: 60-80 (21 גילאים)
- מגדר: זכר/נקבה (2)
- הפרש גיל בן זוג: -20 עד +20 (41 אפשרויות)
- תקופות הבטחה: 0, 60, 120, 180, 240 חודשים (5)
- מסלול: תקנוני (Phoenix Pension)

**דוגמאות:**

| מסלול | מגדר | גיל | הפרש גיל | מקדם | הבטחה |
|-------|------|-----|----------|------|-------|
| תקנוני | זכר | 60 | 0 | 201.67 | 0 |
| תקנוני | זכר | 67 | 0 | 177.8 | 120 |
| תקנוני | זכר | 67 | -5 | 180.6 | 120 |
| תקנוני | נקבה | 64 | 0 | 207.22 | 240 |

## 🔄 לוגיקת בחירת מקדם

```
אם סוג_מוצר = "קרן פנסיה" OR "קופת גמל" OR "קרן השתלמות":
    → שלוף מ-pension_fund_coefficient
    → לפי: מגדר, גיל_פרישה, מסלול_שארים, הפרש_גיל_בן_זוג
    → חישוב: base_coefficient × adjust_percent
    
אחרת (ביטוח מנהלים / פוליסות):
    1. מצא generation_code לפי start_date
    2. נסה למצוא מקדם ספציפי לחברה:
       → אם יש company_name + option_name → company_annuity_coefficient
       → חישוב לשנת יעד: base × (1 + rate × (target_year - base_year))
    3. אם לא נמצא → fallback למקדם דור:
       → policy_generation_coefficient
       → לפי: generation_code + age + sex
       → בחירת עמודה: male_coefficient או female_coefficient
```

**חשוב:** המערכת בוחרת את המקדם המדויק לפי **גיל** ו**מין** הלקוח, לא רק לפי דור!

### 📝 דוגמה מפורטת:

**נתונים:**
- לקוח נולד: 15/03/1958
- תכנית התחילה: 01/01/2005
- תאריך מימוש (תחילת קצבה): 01/06/2026
- מין: זכר

**חישוב:**
1. **זיהוי דור:** תאריך התחלה 2005 → נמצא בטווח 2004-2008 → דור **Y2004_TO_2008**
2. **חישוב גיל:** 2026 - 1958 = 68 (מכיוון שיום הולדת כבר עבר ביוני)
3. **שליפת מקדם:** דור Y2004_TO_2008, גיל 68, זכר → מקדם **~194** (לפי הטבלה)
4. **חישוב קצבה:** יתרה 200,000 ÷ 194 = **1,031 ₪** לחודש

## 📁 מבנה הקבצים

### Backend
```
app/
├── services/
│   └── annuity_coefficient_service.py    # שירות מרכזי לחישוב מקדמים
├── routers/
│   └── annuity_coefficient.py            # API endpoints
└── main.py                                # הוספת router

MEKEDMIM/
├── policy_generation_coefficient.csv     # דורות פוליסות
├── product_to_generation_map.csv         # מיפוי מוצר לדור
├── company_annuity_coefficient.csv       # מקדמים לחברות
├── pension_fund_coefficient.csv          # מקדמים לקרנות פנסיה
└── load_sqlite.sql                       # סקריפט טעינה

load_annuity_coefficients.py             # סקריפט טעינת נתונים
```

### Frontend
```
frontend/src/
├── pages/
│   ├── PensionPortfolio.tsx              # שימוש במקדם דינמי
│   └── SystemSettings.tsx                # לשונית "מקדמי קצבה"
```

## 🚀 API Endpoints

### POST /api/v1/annuity-coefficient/calculate
**חישוב מקדם קצבה**

**Request Body:**
```json
{
  "product_type": "ביטוח מנהלים",
  "start_date": "2010-01-01",
  "gender": "זכר",
  "retirement_age": 67,
  "company_name": "הראל",
  "option_name": "מינימום 240",
  "survivors_option": "זקנה + שארים תקנוני",
  "spouse_age_diff": 0,
  "target_year": 2025
}
```

**Response:**
```json
{
  "factor_value": 201.81,
  "source_table": "company_annuity_coefficient",
  "source_keys": {
    "company_name": "הראל",
    "option_name": "מינימום 240",
    "sex": "זכר",
    "age": 67
  },
  "target_year": 2025,
  "guarantee_months": null,
  "notes": "מקור: נספח הראל 2024"
}
```

### GET /api/v1/annuity-coefficient/tables/status
**בדיקת סטטוס טבלאות**

**Response:**
```json
{
  "status": "ok",
  "tables": {
    "policy_generation_coefficient": 7,
    "product_to_generation_map": 8,
    "company_annuity_coefficient": 6,
    "pension_fund_coefficient": 3
  },
  "total_records": 24
}
```

## 💻 שימוש בקוד

### Backend - חישוב מקדם
```python
from app.services.annuity_coefficient_service import get_annuity_coefficient
from datetime import date

result = get_annuity_coefficient(
    product_type='ביטוח מנהלים',
    start_date=date(2010, 1, 1),
    gender='זכר',
    retirement_age=67,
    company_name='הראל',
    option_name='מינימום 240',
    target_year=2025
)

print(f"מקדם: {result['factor_value']}")
print(f"מקור: {result['source_table']}")
```

### Frontend - המרה לקצבה
```typescript
// חישוב מקדם
const coefficientResponse = await apiFetch('/annuity-coefficient/calculate', {
  method: 'POST',
  body: JSON.stringify({
    product_type: account.סוג_מוצר,
    start_date: account.תאריך_התחלה,
    gender: clientData.gender,
    retirement_age: retirementAge,
    company_name: account.חברה_מנהלת,
    target_year: new Date().getFullYear()
  })
});

const annuityFactor = coefficientResponse.factor_value;

// חישוב קצבה
const monthlyPension = Math.round(balance / annuityFactor);
```

## 🔧 התקנה וטעינת נתונים

### שלב 1: טעינת טבלאות למסד הנתונים
```bash
python load_annuity_coefficients.py
```

הסקריפט:
- יוצר 4 טבלאות ב-SQLite
- טוען את כל קבצי ה-CSV
- מדווח על מספר השורות שנטענו

### שלב 2: אתחול השרת
```bash
# Backend
cd app
python -m uvicorn main:app --reload

# Frontend
cd frontend
npm run dev
```

## 📝 עדכון טבלאות

### הוספת מקדמים חדשים

1. **ערוך את קובץ ה-CSV המתאים:**
   - `policy_generation_coefficient.csv` - דורות חדשים
   - `company_annuity_coefficient.csv` - חברות/מסלולים חדשים
   - `pension_fund_coefficient.csv` - מסלולי שארים חדשים

2. **טען מחדש את הנתונים:**
   ```bash
   python load_annuity_coefficients.py
   ```

3. **אתחל את השרת**

### דוגמה - הוספת חברה חדשה
```csv
# company_annuity_coefficient.csv
7,מגדל,מינימום 180,זכר,65,2024,195.5,0.0025,נספח מגדל 2024,2024-01-01,2099-12-31
```

## 🎨 ממשק משתמש

### לשונית "מקדמי קצבה" בהגדרות מערכת

הלשונית מציגה:
1. **הסבר על מקדמי קצבה** - מה זה ואיך זה עובד
2. **תהליך אוטומטי** - 5 שלבים שהמערכת מבצעת
3. **טבלאות המקדמים** - 3 טבלאות מפורטות:
   - דורות פוליסות ביטוח מנהלים
   - מקדמים ספציפיים לחברות
   - מקדמים לקרנות פנסיה
4. **הנחיות עדכון** - איך לעדכן את הטבלאות

### תיק פנסיוני - המרה לקצבה

כאשר ממירים חשבון לקצבה:
1. המערכת מחשבת את המקדם אוטומטית
2. מציגה בקונסול: `[מקדם קצבה] תכנית X: 201.81 (מקור: company_annuity_coefficient)`
3. שומרת בהערות הקצבה:
   ```
   המרה מתיק פנסיוני
   תכנית: ביטוח מנהלים הראל
   מקדם קצבה: 201.81 (company_annuity_coefficient)
   מקור: נספח הראל 2024
   ```

## 🧪 בדיקות

### בדיקת טעינת טבלאות
```bash
# בדוק שהטבלאות נטענו
curl http://localhost:8000/api/v1/annuity-coefficient/tables/status
```

### בדיקת חישוב מקדם
```bash
curl -X POST http://localhost:8000/api/v1/annuity-coefficient/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "product_type": "ביטוח מנהלים",
    "start_date": "2010-01-01",
    "gender": "זכר",
    "retirement_age": 67,
    "company_name": "הראל",
    "option_name": "מינימום 240",
    "target_year": 2025
  }'
```

## 🔍 פתרון בעיות

### בעיה: "Cannot open CSV file"
**פתרון:** הרץ את `load_annuity_coefficients.py` מהתיקייה הראשית

### בעיה: "Table not found"
**פתרון:** הטבלאות לא נטענו. הרץ:
```bash
python load_annuity_coefficients.py
```

### בעיה: מקדם תמיד 200
**פתרון:** 
1. בדוק שהשרת רץ
2. בדוק את הקונסול לשגיאות
3. ודא שסוג המוצר מזוהה נכון

### בעיה: שגיאת TypeScript בפרונטאנד
**פתרון:** הוסף `: any` לתגובות API

## 📊 סטטיסטיקות

- **4 טבלאות** במסד הנתונים
- **75,601 רשומות** סה"כ (147+8+6+75,440)
- **147 שורות** פוליסות ביטוח מנהלים (7 דורות × 21 גילאים)
- **75,440 שורות** קרנות פנסיה (כל השילובים האפשריים)
- **2 חברות** עם מקדמים ספציפיים (כלל, הראל)
- **גילאים 60-80** עם מקדמים נפרדים לזכר ונקבה

## 🎯 יתרונות המערכת

1. **דיוק** - מקדמים מדויקים לפי כל הפרמטרים
2. **שקיפות** - המקדם והמקור נשמרים בהערות
3. **גמישות** - קל להוסיף חברות/מסלולים חדשים
4. **אוטומציה** - אין צורך בהזנה ידנית
5. **תחזוקה** - עדכון פשוט דרך קבצי CSV

## 📚 מקורות

- נספחי חברות הביטוח (כלל, הראל)
- טבלאות דורות פוליסות רשמיות
- נספחי קרנות פנסיה פומביים
- תקנות ביטוח וקצבאות

## ✅ סיכום

המערכת מספקת חישוב מקדמי קצבה דינמי ומדויק, תוך שמירה על שקיפות מלאה ואפשרות עדכון פשוטה.
כל המרה לקצבה משתמשת במקדם המתאים ביותר לפי כל הפרמטרים הרלוונטיים.
