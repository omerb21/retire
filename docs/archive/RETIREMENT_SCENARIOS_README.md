# Retirement Scenarios Engine - תרחישי פרישה אוטומטיים

## תיאור

מנוע תרחישי פרישה מייצר באופן אוטומטי 3 תרחישים שונים על בסיס גיל פרישה נבחר:

1. **מקסימום קצבה** - ממיר את כל הנכסים למקורות קצבה חודשיים
2. **מקסימום הון** - ממיר למקסימום הון נזיל, תוך שמירה על קצבת מינימום (חוק ברזל)
3. **מקסימום NPV** - מחפש את התרחיש האופטימלי עם ה-NPV הגבוה ביותר

## ארכיטקטורה

### Backend

#### 1. שירות בניית תרחישים
**קובץ:** `app/services/retirement_scenarios.py`

**מחלקה עיקרית:** `RetirementScenariosBuilder`

**פונקציות עיקריות:**
- `build_all_scenarios()` - בונה את כל 3 התרחישים
- `_build_max_pension_scenario()` - תרחיש מקסימום קצבה
- `_build_max_capital_scenario()` - תרחיש מקסימום הון
- `_build_max_npv_scenario()` - תרחיש מקסימום NPV
- `_save_current_state()` / `_restore_state()` - שמירה ושחזור מצב נתונים

**קבועים:**
- `PENSION_COEFFICIENT = 200` - מקדם להמרת הון לקצבה
- `MINIMUM_PENSION = 5500` - קצבת מינימום בחוק ברזל

#### 2. API Endpoint
**קובץ:** `app/routers/scenarios.py`

**Endpoint:** `POST /api/v1/clients/{client_id}/retirement-scenarios`

**Request Body:**
```json
{
  "retirement_age": 67
}
```

**Response:**
```json
{
  "success": true,
  "client_id": 123,
  "retirement_age": 67,
  "scenarios": {
    "scenario_1_max_pension": {
      "scenario_name": "מקסימום קצבה",
      "total_pension_monthly": 15000,
      "total_capital": 500000,
      "total_additional_income_monthly": 2000,
      "estimated_npv": 3500000,
      "pension_funds_count": 3,
      "capital_assets_count": 1,
      "additional_incomes_count": 2
    },
    "scenario_2_max_capital": { ... },
    "scenario_3_max_npv": { ... }
  }
}
```

### Frontend

**קובץ:** `frontend/src/pages/RetirementScenarios.tsx`

**נתיב:** `/clients/:id/retirement-scenarios`

**תכונות:**
- טופס הזנת גיל פרישה (50-80)
- כפתור לחישוב תרחישים
- הצגת 3 תרחישים בצורה חזותית
- טבלת השוואה
- סימון התרחיש המומלץ (NPV הגבוה ביותר)

## לוגיקה עסקית

### תרחיש 1: מקסימום קצבה

1. המרת כל המוצרים הפנסיוניים לקצבה
   - `pension_amount = balance / annuity_factor`
2. המרת נכסי הון חייבים במס לקצבה
   - `pension_amount = current_value / 200`
3. המרת נכסי הון פטורים מס להכנסה נוספת פטורה
4. טיפול בעזיבת עבודה - בחירה בקצבה

### תרחיש 2: מקסימום הון

1. המרת מוצרים פנסיוניים הניתנים לפדיון להון
2. המרת קצבאות עם **חוק ברזל**:
   - שמירה על קצבת מינימום של 5,500 ₪
   - היוון הקצבאות מעל המינימום
   - מיון לפי annuity_factor לאופטימיזציה
3. טיפול בעזיבת עבודה - בחירה בפדיון

**חוק הברזל:**
```python
total_pension = 0
for fund in sorted_funds:
    if total_pension >= MINIMUM_PENSION:
        # היוון מלא
        capitalize(fund)
    else:
        # שמירת החלק הנדרש למינימום
        pension_needed = MINIMUM_PENSION - total_pension
        keep_for_pension(fund, pension_needed)
        capitalize_rest(fund)
```

### תרחיש 3: מקסימום NPV (70% קצבה, 30% הון)

תרחיש מאוזן שמחלק את **סך כל הנכסים** ל-70% קצבה ו-30% הון.

**אסטרטגיה:**
1. חישוב סך ערך כל הנכסים (קצבאות + הון)
2. יעד: 70% מהערך הכולל כקצבה, 30% כהון
3. אם יש יותר מדי קצבאות - מהוון את הקצבאות הפחות איכותיות (annuity factor גבוה)
4. אם יש יותר מדי הון - ממיר חלק להון לקצבה
5. נכסים פטורים ממס → הכנסה נוספת פטורה

זה יוצר תרחיש **שונה לחלוטין** משני התרחישים האחרים ומספק איזון בין הכנסה קבועה (קצבה) ונזילות (הון).

## חישוב NPV

נוסחה פשוטה (MVP):
```python
npv = total_capital + (total_pension * 180) + (total_additional_income * 240)
```

בגרסה מלאה - יש להשתמש בחישוב תזרים מזומנים מהווה (DCF) עם שיעור היוון מתאים.

## שמירת מצב וביטול שינויים

המערכת שומרת את המצב המקורי לפני כל תרחיש ומשחזרת אותו:

```python
original_state = self._save_current_state()
try:
    scenario1 = self._build_max_pension_scenario()
    self._restore_state(original_state)
    scenario2 = self._build_max_capital_scenario()
    ...
finally:
    self._restore_state(original_state)
```

## שימוש

1. נווט למסך לקוח
2. לחץ על "🎯 תרחישי פרישה"
3. הזן גיל פרישה רצוי
4. לחץ על "🎯 חשב תרחישי פרישה"
5. בדוק את התוצאות ובחר בתרחיש המתאים

## הרחבות עתידיות

1. **אופטימיזציה מלאה של תרחיש 3:**
   - ניסיון של כל הפרמוטציות
   - שימוש באלגוריתם אופטימיזציה (Genetic Algorithm, Simulated Annealing)

2. **חישוב NPV מדויק:**
   - תזרים מזומנים חודשי ל-30 שנה
   - שיעור היוון משתנה לפי שנים
   - התחשבות במס שולי

3. **שמירת תרחישים:**
   - שמירה של תרחיש נבחר למאגר הנתונים
   - אפשרות להשוות תרחישים שונים

4. **דוחות וויזואליזציה:**
   - גרפים של תזרים מזומנים
   - השוואת תרחישים
   - ייצוא ל-PDF

## Dependencies

- `sqlalchemy` - ORM למאגר נתונים
- `fastapi` - Web framework
- `pydantic` - Validation
- React - Frontend
- TypeScript - Type safety

## Testing

יש ליצור בדיקות עבור:
1. בניית תרחיש מקסימום קצבה
2. בניית תרחיש מקסימום הון עם חוק ברזל
3. שמירה ושחזור מצב נתונים
4. חישוב NPV
5. API endpoint

## Known Issues & Limitations

1. חישוב NPV הוא משוער ולא מבוסס על תזרים מזומנים מפורט עם היוון
2. תרחיש NPV משתמש ביחס קבוע 70/30 - בעתיד ניתן לאפטם את היחס
3. חוק ברזל בתרחיש 2 מיושם באופן פשוט - ללא התחשבות בהיוון חלקי
4. אין אפשרות לשמור תרחישים למאגר נתונים (התרחישים נוצרים on-the-fly)
5. אין אינטגרציה עם מנוע החישוב הקיים (CalculationEngine)

## Contributors

Built for the retirement planning system.
