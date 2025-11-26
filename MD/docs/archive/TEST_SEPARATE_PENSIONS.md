# בדיקה: קצבה נפרדת לכל תכנית

## 🔧 צעדים להפעלה

### 1. אתחל את השרת מחדש
השרת צריך להטען מחדש כדי לקרוא את הקוד המעודכן:

```bash
# הרץ בטרמינל חדש
cd c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire
python -m uvicorn app.main:app --reload --port 8005
```

### 2. בדוק את התיקון

#### דוגמה של תוצאה נכונה:
בעת עזיבת עבודה עם המרה לקצבה, אתה צריך לראות בקונסול:

```
🔵 CREATING SEPARATE PENSION FUNDS FROM TAXABLE AMOUNT: 217118.0
  📦 Found 2 severance grants to process
  📊 Processing plan: מקפת אישית, amount: 82324.76, start_date: 2005-05-01
    📊 Dynamic annuity coefficient: 180.5 (source: pension_fund_coefficient)
    🟢 CREATED PENSION FUND ID: 20, balance: 82324.76, monthly: 456.0, factor: 180.5
  📊 Processing plan: מיטב, amount: 188625.96, start_date: 1995-02-01
    📊 Dynamic annuity coefficient: 195.2 (source: pension_fund_coefficient)
    🟢 CREATED PENSION FUND ID: 21, balance: 188625.96, monthly: 966.0, factor: 195.2
```

#### מה שצריך להשתנות:
- **לפני**: קצבה אחת בלבד עם סכום 217,118 ₪ ומקדם אחד
- **אחרי**: שתי קצבאות נפרדות:
  - קצבה 1: 82,324.76 ₪ עם מקדם 180.5 (מקפת אישית)
  - קצבה 2: 188,625.96 ₪ עם מקדם 195.2 (מיטב)

### 3. בדוק בממשק המשתמש

1. צור לקוח חדש עם קובץ XML שיש בו מספר תכניות עם פיצויים מעסיק נוכחי
2. עבור לעמוד "מעסיק נוכחי"
3. בצע "עזיבת עבודה"
4. בחר "המרה לקצבה"
5. אשר את ההחלטה

#### תוצאה צפויה:
- בעמוד "תיק פנסיוני" צריכות להופיע **שתי קצבאות נפרדות** (לא קצבה אחת!)
- כל קצבה צריכה להיות בשם התכנית שלה
- כל קצבה צריכה להיות בסכום שונה
- הקצבה החודשית צריכה להיות שונה לכל תכנית

---

## 📊 דוגמה מפורטת

### קלט:
```
תכנית: מקפת אישית
- תאריך התחלה: 2005-05-01
- פיצויים מעסיק נוכחי: 82,324.76 ₪

תכנית: מיטב
- תאריך התחלה: 1995-02-01
- פיצויים מעסיק נוכחי: 188,625.96 ₪

סה"כ: 270,951 ₪
```

### עיבוד:
1. **יצירת EmployerGrants** (כבר עובד):
   - Grant 1: מקפת אישית - 82,324.76 ₪ (start: 2005-05-01)
   - Grant 2: מיטב - 188,625.96 ₪ (start: 1995-02-01)

2. **חלוקה לפטור וחייב** (לפי החלטת המשתמש):
   - פטור: 53,833 ₪ (יחולק לפי יחס)
   - חייב: 217,118 ₪ (יחולק לפי יחס)

3. **יצירת קצבאות נפרדות** (✅ תוקן):
   - קצבה 1 (מקפת אישית - פטור): 19,761 ₪ / 180.5 = 109.5 ₪/חודש
   - קצבה 2 (מיטב - פטור): 34,072 ₪ / 195.2 = 174.5 ₪/חודש
   - קצבה 3 (מקפת אישית - חייב): 62,563 ₪ / 180.5 = 346.5 ₪/חודש
   - קצבה 4 (מיטב - חייב): 154,555 ₪ / 195.2 = 791.5 ₪/חודש

---

## ✅ בדיקה מהירה

בדוק בקונסול שהקוד מדפיס:

```
✅ Created 2 EmployerGrants
🔵 PROCESSING EXEMPT AMOUNT: 53833.0
🟡 CREATING SEPARATE PENSION FUNDS FROM EXEMPT AMOUNT: 53833.0
  📦 Found 2 severance grants to process
  📊 Processing plan: מקפת אישית, exempt_amount: 19761.0, start_date: 2005-05-01
    🟢 CREATED PENSION FUND ID: XX, balance: 19761.0, monthly: 109.5, factor: 180.5
  📊 Processing plan: מיטב, exempt_amount: 34072.0, start_date: 1995-02-01
    🟢 CREATED PENSION FUND ID: YY, balance: 34072.0, monthly: 174.5, factor: 195.2
🔵 PROCESSING TAXABLE AMOUNT: 217118.0
🔵 CREATING SEPARATE PENSION FUNDS FROM TAXABLE AMOUNT: 217118.0
  📦 Found 2 severance grants to process
  📊 Processing plan: מקפת אישית, amount: 82324.76, start_date: 2005-05-01
    🟢 CREATED PENSION FUND ID: ZZ, balance: 62563.0, monthly: 346.5, factor: 180.5
  📊 Processing plan: מיטב, amount: 188625.96, start_date: 1995-02-01
    🟢 CREATED PENSION FUND ID: WW, balance: 154555.0, monthly: 791.5, factor: 195.2
```

---

## 🐛 אם עדיין יש בעיה

1. **בדוק שהשרת הטען מחדש** - הוא צריך להדפיס "Application startup complete"
2. **בדוק שה-Frontend שולח plan_details** - בקונסול צריך לראות:
   ```
   📋 Plan details: [{'plan_name': 'מקפת אישית', 'plan_start_date': '20050501', 'amount': 82324.76}, ...]
   ```
3. **בדוק שה-EmployerGrants נוצרו** - בקונסול צריך לראות:
   ```
   ✅ Created EmployerGrant: מקפת אישית - 82324.76 ₪ (start: 2005-05-01)
   ✅ Created EmployerGrant: מיטב - 188625.96 ₪ (start: 1995-02-01)
   ```

---

## 📝 קבצים שעודכנו

- `app/routers/current_employer.py` - יצירת קצבה נפרדת לכל תכנית

## 🔗 Commits

- `2926d04`: "Fix: Create separate pension for each plan in annuity conversion"
