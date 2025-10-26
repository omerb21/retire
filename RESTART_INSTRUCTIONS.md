# 🔄 הוראות הפעלה מחדש של השרת

## ⚠️ בעיה: מספר שרתים רצים במקביל

המערכת הייתה עם 3 שרתים רצים על פורט 8005, מה שגרם לבעיות.

## ✅ פתרון: עצירה והפעלה מחדש

### שלב 1: עצירת כל השרתים
```powershell
# עצור את כל תהליכי Python
Stop-Process -Name python* -Force

# וודא שאין שום דבר על פורט 8005
netstat -ano | findstr :8005
```

### שלב 2: המתן 5 שניות
חכה כמה שניות כדי לוודא שכל החיבורים נסגרו.

### שלב 3: הפעל שרת אחד בלבד
```bash
cd "c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

### שלב 4: וודא שרק שרת אחד רץ
```powershell
# צריך לראות רק תהליך אחד
Get-Process python* | Select-Object Id,ProcessName

# צריך לראות רק PID אחד על LISTENING
netstat -ano | findstr :8005 | findstr LISTENING
```

## 📝 הערות
- אל תפעיל יותר משרת אחד!
- אם יש בעיה, עצור הכל והתחל מחדש
- השרת צריך לרוץ עם `--reload` כדי לטעון שינויים אוטומטית

## 🔍 תיקון שבוצע
תוקן חישוב יחס 32 שנים ב-`app/services/rights_fixation.py`:
- שורה 154: שונה מ-`effective_end_date` ל-`end_date`
- זה מבטיח קיזוז נכון לשנים מעל גיל פרישה
