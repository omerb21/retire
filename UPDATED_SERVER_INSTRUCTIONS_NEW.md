# הוראות הפעלה למערכת תכנון פרישה

## מערכת אחת מאוחדת

המערכת כוללת שרת אחד מלא שמספק את כל הפונקציונליות:

- ניהול לקוחות מלא (CRUD)
- ניהול מענקים מלא (CRUD)
- תרחישים וחישובי פרישה
- **קיבוע זכויות מלא**
- חישובי הצמדה למדד CBS
- חישובי יחס 32 שנים
- חישובי פגיעה בהון פטור
- דוחות PDF

## הפעלת המערכת

### 1. הפעלת שרת ה-API

```powershell
# מעבר לתיקיית הפרויקט
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"

# הפעלת השרת המלא והמאוחד
python simple_server.py
```

- השרת ירוץ על פורט 8005
- בדיקת תקינות: http://localhost:8005/health
- תיעוד API: http://localhost:8005/docs

### 2. הפעלת ממשק המשתמש (פרונטאנד)

פתחו חלון PowerShell נוסף והריצו:

```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend"
npm start
```

- הממשק ייפתח אוטומטית בדפדפן בכתובת: http://localhost:3000

## יצירת לקוח חדש

1. לחצו על "לקוח חדש" בממשק המשתמש
2. מלאו את השדות החובה:
   - שם מלא
   - מספר ת.ז.
   - תאריך לידה
3. לחצו על "שמור"

## תכונות עיקריות

- ניהול לקוחות מלא
- חישובי פרישה מדויקים
- קיבוע זכויות אוטומטי
- יצירת דוחות PDF
- ממשק משתמש נוח בעברית

## פתרון בעיות נפוצות

### בעיית חיבור לשרת

אם מתקבלת שגיאת "Not Found" או "Connection Refused":

1. וודאו שהשרת רץ על פורט 8005:
   ```powershell
   netstat -ano | findstr :8005
   ```

2. אם השרת לא רץ, הפעילו מחדש:
   ```powershell
   python minimal_working_server.py --port 8005
   ```

3. אם השרת רץ אך עדיין יש שגיאות, הפעילו מחדש גם את הפרונטאנד:
   ```powershell
   cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend"
   npm start
   ```

### בעיית שמירת לקוח

אם לא ניתן לשמור לקוח חדש:

1. ודאו שמילאתם את כל שדות החובה (שם מלא, מספר ת.ז., תאריך לידה)
2. בדקו את הודעות השגיאה במסוף השרת
3. נסו להפעיל מחדש את השרת והפרונטאנד

### בעיית קיבוע זכויות

אם נדרשת פונקציונליות קיבוע זכויות מתקדמת, ניתן להשתמש בשרת המלא:

```powershell
python simple_server.py
```

שימו לב: השרת המלא עשוי להיתקל בבעיות עם נקודות קצה מסוימות. אם יש בעיות, חזרו לשרת המינימלי.

### איפוס מערכת

אם נתקלתם בבעיות קשות, ניתן לאפס את המערכת:

```powershell
# סגירת כל התהליכים
taskkill /F /IM python.exe
taskkill /F /IM node.exe

# הפעלה מחדש של השרת
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"
python minimal_working_server.py --port 8005

# בחלון נפרד - הפעלת הפרונטאנד
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend"
npm start
```

לכל בעיה נוספת, פנו לצוות התמיכה.
## דוגמה לנתונים תקינים

```json
{
  "full_name": "ישראל ישראלי",
  "id_number": "123456789",
  "birth_date": "1980-01-01",
  "gender": "male",
  "marital_status": "single"
}
```

## בדיקת המערכת

### בדיקת שרת ה-API
1. פתח דפדפן וגש לכתובת: http://localhost:8000/docs
2. בדוק את תיעוד ה-API ונסה להפעיל נקודות קצה בסיסיות
3. בדוק את בריאות המערכת בכתובת: http://localhost:8000/health

### בדיקת ה-Frontend
1. פתח דפדפן וגש לכתובת: http://localhost:3000
2. נסה ליצור לקוח חדש (שים לב למלא את כל שדות החובה!)
3. בדוק את רשימת הלקוחות הקיימים

## פתרון בעיות נפוצות

### שגיאת Field required בשמירת לקוח
אם מופיעה שגיאת "Field required" בעת שמירת לקוח:
1. ודא שמילאת את שדות החובה: `full_name` ו-`id_number`
2. בדוק שהנתונים נשלחים בפורמט JSON תקין

### בעיית פורט תפוס
אם מופיעה שגיאה שהפורט תפוס:

```powershell
# בדיקת תהליכים המשתמשים בפורט 8000
netstat -ano | findstr :8000

# סגירת תהליך לפי מזהה (PID)
taskkill /F /PID <מזהה_תהליך>
```

### בעיות בהפעלת הפרונטאנד
אם הפרונטאנד לא עולה:

```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend"
npm install
npm start
```

## בדיקת יצירת PDF

```powershell
# יצירת דוח PDF
Invoke-WebRequest -Uri "http://localhost:8002/api/v1/scenarios/24/report/pdf?client_id=1" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"from_":"2025-01","to":"2025-12","frequency":"monthly"}' `
  -OutFile "test_report.pdf"
```

### אם השתמשת בפורט אחר

אם הפעלת את השרת עם פורט אחר (לדוגמה 8003), התאם את הכתובת בהתאם:

```powershell
Invoke-WebRequest -Uri "http://localhost:8003/api/v1/scenarios/24/report/pdf?client_id=1" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"from_":"2025-01","to":"2025-12","frequency":"monthly"}' `
  -OutFile "test_report.pdf"
```

## סיכום פורטים
- שרת Backend: **http://localhost:8002** (או פורט אחר שבחרת)
- פרונטאנד: **http://localhost:3000**

---

**עדכון אחרון**: 13 בספטמבר 2025
