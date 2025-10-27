# תיקון: יצירת קצבה נפרדת לכל תכנית בעזיבת עבודה

**תאריך**: 27 אוקטובר 2025  
**סטטוס**: ✅ הושלם  
**גרסה**: 1.0

---

## 🎯 הבעיה המקורית

כאשר משתמש בוחר להמיר פיצויים לקצבה בשלב עזיבת עבודה, המערכת **איחדה את כל יתרות הפיצויים** מכל התכניות לקצבה אחת עם מקדם אחד.

**דוגמה של הבעיה:**
- תכנית A (התחילה 2005): 50,000 ₪ פיצויים
- תכנית B (התחילה 2010): 30,000 ₪ פיצויים
- **תוצאה שגויה**: קצבה אחת של 80,000 ₪ עם מקדם אחד (לא נכון!)

---

## ✅ הפתרון שיושם

### 1. **מודל EmployerGrant** - הוספת שדות
**קובץ**: `app/models/employer_grant.py`

```python
# שדות חדשים:
plan_name = Column(String, nullable=True)  # שם התכנית מתיק הפנסיה
plan_start_date = Column(Date, nullable=True)  # תאריך התחלת התכנית (לחישוב מקדם)
```

**מטרה**: קשר כל מענק לתכנית ספציפית בתיק הפנסיה

---

### 2. **לוגיקת תרחישים** - יצירת קצבה נפרדת
**קובץ**: `app/services/retirement_scenarios.py`

#### שינוי ב-`_handle_termination_for_pension()`:
- **לפני**: סיכום כל הפיצויים לסכום אחד, יצירת קצבה אחת
- **אחרי**: קיבוץ מענקים לפי תכנית, יצירת קצבה נפרדת לכל תכנית

```python
# קיבוץ מענקים לפי תכנית
grants_by_plan = {}
for grant in grants:
    if grant.grant_type == GrantType.severance:
        plan_key = grant.plan_name or "ללא תכנית"
        if plan_key not in grants_by_plan:
            grants_by_plan[plan_key] = {
                'grants': [],
                'plan_start_date': grant.plan_start_date,
                'plan_name': grant.plan_name
            }
        grants_by_plan[plan_key]['grants'].append(grant)

# יצירת קצבה נפרדת לכל תכנית
for plan_key, plan_data in grants_by_plan.items():
    # חישוב סכומים לתכנית זו
    plan_severance = sum(...)
    
    # חישוב מקדם דינמי לפי תאריך התחלת התכנית
    coefficient_result = get_annuity_coefficient(
        start_date=plan_start_date,  # ← תאריך התחלת התכנית!
        ...
    )
    
    # יצירת קצבה עם המקדם המתאים
    pf = PensionFund(
        fund_name=f"קצבה מפיצויי פרישה - {plan_name}",
        balance=plan_severance,
        annuity_factor=annuity_factor,
        ...
    )
```

#### שינוי ב-`_handle_termination_for_capital()`:
- **לפני**: יצירת נכס הון אחד מאוחד
- **אחרי**: יצירת נכס הון נפרד לכל תכנית

---

### 3. **Router** - יצירת EmployerGrant לכל תכנית
**קובץ**: `app/routers/current_employer.py`

```python
# קבלת פרטי תכניות מה-Frontend
plan_details_list = json.loads(decision.plan_details)

# יצירת EmployerGrant נפרד לכל תכנית
for plan_detail in plan_details_list:
    employer_grant = EmployerGrant(
        employer_id=ce.id,
        grant_type=GrantType.severance,
        grant_amount=amount,
        grant_date=decision.termination_date,
        plan_name=plan_detail['plan_name'],
        plan_start_date=plan_detail['plan_start_date']
    )
    db.add(employer_grant)
```

---

### 4. **Schema** - קבלת מידע תכניות
**קובץ**: `app/schemas/current_employer.py`

```python
class TerminationDecisionBase(BaseModel):
    # ... שדות קיימים ...
    plan_details: Optional[str] = Field(
        None, 
        description="פרטי תכניות מלאים: שם, תאריך התחלה, סכום (JSON)"
    )
```

---

### 5. **Frontend** - שליחת פרטי תכניות
**קובץ**: `frontend/src/pages/SimpleCurrentEmployer.tsx`

```typescript
// אסיפת פרטי תכניות מלאים
let planDetails: Array<{plan_name: string, plan_start_date: string | null, amount: number}> = [];

pensionData.forEach((account: any) => {
    const amount = Number(account.פיצויים_מעסיק_נוכחי) || 0;
    if (amount > 0) {
        planDetails.push({
            plan_name: account.שם_תכנית,
            plan_start_date: account.תאריך_התחלה,
            amount: amount
        });
    }
});

// שליחה לשרת
const payload = {
    ...terminationDecision,
    plan_details: planDetails.length > 0 ? JSON.stringify(planDetails) : null
};
```

---

### 6. **Migration** - הוספת שדות לטבלה
**קובץ**: `migrations/add_plan_details_to_employer_grant.sql`

```sql
ALTER TABLE employer_grant ADD COLUMN plan_name TEXT;
ALTER TABLE employer_grant ADD COLUMN plan_start_date DATE;
```

---

## 📊 דוגמה של התוצאה הנכונה

**קלט**: לקוח עם שתי תכניות שיש בהן פיצויים מעסיק נוכחי

| תכנית | תאריך התחלה | פיצויים | מקדם צפוי |
|------|-----------|--------|----------|
| קרן פנסיה A | 2005-01-01 | 50,000 ₪ | 180 |
| קרן פנסיה B | 2010-06-15 | 30,000 ₪ | 190 |

**פלט**: שתי קצבאות נפרדות

| קצבה | סכום מקורי | מקדם | קצבה חודשית |
|-----|----------|------|-----------|
| קצבה מ-תכנית A | 50,000 ₪ | 180 | 277.78 ₪ |
| קצבה מ-תכנית B | 30,000 ₪ | 190 | 157.89 ₪ |

**סה"כ קצבה חודשית**: 435.67 ₪ (לא 444.44 ₪ כמו בחישוב שגוי!)

---

## 🚀 צעדים להפעלה

### 1. הרץ את ה-Migration
```bash
cd c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire
sqlite3 retire.db < migrations/add_plan_details_to_employer_grant.sql
```

### 2. אתחל את השרת מחדש
```bash
python -m uvicorn app.main:app --reload --port 8005
```

### 3. בדוק את התיקון
- צור לקוח חדש
- טען קובץ XML עם מספר תכניות שיש בהן פיצויים מעסיק נוכחי
- עבור למסך "מעסיק נוכחי"
- בצע עזיבת עבודה
- בחר "המרה לקצבה"
- וודא שנוצרה קצבה נפרדת לכל תכנית

---

## 📝 קבצים שעודכנו

| קובץ | שינוי |
|-----|------|
| `app/models/employer_grant.py` | ✅ הוספת `plan_name`, `plan_start_date` |
| `app/services/retirement_scenarios.py` | ✅ קיבוץ מענקים לפי תכנית, יצירת קצבה נפרדת |
| `app/routers/current_employer.py` | ✅ יצירת `EmployerGrant` לכל תכנית |
| `app/schemas/current_employer.py` | ✅ הוספת `plan_details` לschema |
| `frontend/src/pages/SimpleCurrentEmployer.tsx` | ✅ שליחת פרטי תכניות |
| `migrations/add_plan_details_to_employer_grant.sql` | ✅ יצירת migration |

---

## ✨ יתרונות התיקון

1. **דיוק מתמטי** - כל קצבה מקבלת את המקדם המתאים לתכנית שלה
2. **שקיפות** - משתמש רואה קצבה נפרדת לכל תכנית
3. **גמישות** - תכניות עם תאריכי התחלה שונים מקבלות טיפול שונה
4. **ניתנות לעקיבה** - קל לזהות מאיזו תכנית נוצרה כל קצבה

---

## 🔍 בדיקה ידנית

כדי לבדוק את התיקון ידנית:

```python
# בשרת Python
from app.models.employer_grant import EmployerGrant
from app.database import SessionLocal

db = SessionLocal()
grants = db.query(EmployerGrant).all()

for grant in grants:
    print(f"Plan: {grant.plan_name}, Amount: {grant.grant_amount}, Start: {grant.plan_start_date}")
```

---

## 📞 תמיכה

אם יש בעיות:
1. בדוק את ה-logs של השרת
2. וודא שה-migration הורצה בהצלחה
3. בדוק שה-Frontend שולח את `plan_details` בפיילוד

---

**סטטוס**: ✅ מוכן להפעלה
