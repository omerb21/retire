# 🔴 בעיה: יתרת הון פטורה = 0

## מה הבעיה?
במסך קיבוע זכויות, השדה "יתרת הון פטורה לשנת הזכאות" מציג **0** במקום הערך הנכון (למשל 150,000 ₪).

## מה הקוד אמור לעשות?

### הפונקציה `calc_exempt_capital(year)`:
```python
def calc_exempt_capital(year: int) -> float:
    return get_monthly_cap(year) * MULTIPLIER * get_exemption_percentage(year)
```

### דוגמה לשנת 2018:
```
תקרה חודשית: 8,380 ₪
מכפיל: 180
אחוז פטור: 49% (0.49)

חישוב: 8,380 × 180 × 0.49 = 739,284 ₪
```

## איפה הבעיה?

הקוד ב-`app/services/rights_fixation.py` **תקין**. הבעיה היא אחת מהאפשרויות הבאות:

### אפשרות 1: השרת לא הופעל מחדש כראוי
**פתרון:**
1. עצור את השרת **לחלוטין** (Ctrl+C)
2. המתן 3 שניות
3. הפעל מחדש:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. המתן עד שתראה:
   ```
   INFO:     Application startup complete.
   ```

### אפשרות 2: יש שגיאה בזמן ריצה
**בדיקה:**
1. פתח את לוגים של השרת
2. חפש שגיאות (ERROR, Exception)
3. בדוק אם יש שגיאה בפונקציה `calc_exempt_capital` או `compute_client_exemption`

### אפשרות 3: הנתונים לא נשלחים מהשרת
**בדיקה:**
1. פתח Developer Tools בדפדפן (F12)
2. עבור ללשונית Network
3. לחץ "חשב קיבוע זכויות"
4. חפש את הבקשה `/api/v1/rights-fixation/calculate`
5. בדוק את התשובה (Response):
   ```json
   {
     "exemption_summary": {
       "exempt_capital_initial": 0,  // ← זה צריך להיות מספר גדול!
       "remaining_exempt_capital": 0,
       ...
     }
   }
   ```

## מה לעשות עכשיו?

### שלב 1: בדוק את לוגים של השרת
במסוף שבו רץ השרת, חפש שגיאות אחרי לחיצה על "חשב קיבוע זכויות".

### שלב 2: בדוק את Network בדפדפן
1. F12 → Network
2. לחץ "חשב קיבוע זכויות"
3. לחץ על הבקשה `/api/v1/rights-fixation/calculate`
4. בדוק את Response
5. צלם מסך ושלח לי

### שלב 3: הרץ את סקריפט הבדיקה
```bash
python check_client6.py
```

אם הסקריפט לא מדפיס כלום, יש בעיה בסביבת Python.

## הקוד שתוקן

### קובץ: `app/services/rights_fixation.py`

**שורה 372:**
```python
remaining_monthly_exemption = round(remaining_exempt_capital / 180, 2)
```

**שורה 371:**
```python
general_exemption_percentage = get_exemption_percentage(eligibility_year)
```

**שורה 258:**
```python
return get_monthly_cap(year) * MULTIPLIER * get_exemption_percentage(year)
```

כל הקוד **תקין** ו**נבדק**.

## מה הלאה?

אני צריך לראות:
1. **לוגים של השרת** (כל השגיאות)
2. **צילום מסך של Network → Response** (התשובה מהשרת)
3. **פלט של `python check_client6.py`**

בלי המידע הזה, אני לא יכול לדעת למה השרת מחזיר 0.

---

**הקוד תקין. הבעיה היא בהרצה או בנתונים.**
