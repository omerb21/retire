# הוראות הפעלה מעודכנות למערכת תכנון פרישה

לאחר תיקון בעיות הייבוא במערכת, להלן הוראות הפעלה מפורטות.

## אפשרות 1: הפעלה באמצעות Docker

```powershell
# הפעלת המערכת באמצעות Docker
docker-compose down -v  # הסרת קונטיינרים וווליומים קיימים
docker-compose up -d    # הפעלת המערכת ברקע
```

אם יש בעיה בהפעלה באמצעות Docker, נסה את אפשרות 2.

## אפשרות 2: הפעלה מקומית (ללא Docker)

### שלב 1: הפעלת שרת ה-API

פתח חלון PowerShell חדש והרץ:

```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"
venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

המתן להודעה: "Uvicorn running on http://127.0.0.1:8000"

### שלב 2: הפעלת שרת ה-Frontend

פתח חלון PowerShell נוסף והרץ:

```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend\public"
python -m http.server 8001
```

המתן להודעה: "Serving HTTP on :: port 8001"

## אפשרות 3: הפעלת אפליקציה מינימלית לבדיקה

אם יש בעיה בהפעלת המערכת המלאה, ניתן להפעיל אפליקציה מינימלית לבדיקה:

```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"
python run_minimal.py
```

## בדיקת המערכת

### בדיקת שרת ה-API

1. פתח דפדפן וגש לכתובת: http://127.0.0.1:8000/docs
2. בדוק את תיעוד ה-API ונסה להפעיל נקודות קצה בסיסיות
3. בדוק את בריאות המערכת בכתובת: http://127.0.0.1:8000/health

### בדיקת ה-Frontend

1. פתח דפדפן וגש לכתובת: http://127.0.0.1:8001/api_verification_clean.html
2. הזן מזהה לקוח: 1
3. הזן מזהה תרחיש: 24
4. לחץ על "אמת סיכומים שנתיים"
5. וודא שמוצגים 12/12 חודשים ותוצאה: PASS

## פתרון בעיות נפוצות

### בעיית פורט תפוס

אם מופיעה שגיאה שהפורט תפוס, בדוק אילו תהליכים משתמשים בפורט:

```powershell
# בדיקת תהליכים המשתמשים בפורט 8000
netstat -ano | findstr :8000
```

סגור את התהליך הרלוונטי או שנה את הפורט בהפעלת השרת.

### בעיות ייבוא

אם מופיעות שגיאות ייבוא, וודא שכל התלויות מותקנות:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
```

### בעיות מסד נתונים

אם יש בעיות בחיבור למסד הנתונים, נסה לאפס אותו:

```powershell
venv\Scripts\activate
python create_db.py
```

### אבחון מפורט

לאבחון מפורט של בעיות במערכת, הרץ:

```powershell
python diagnose_server.py
```

## קבצים שתוקנו

1. `app/schemas/__init__.py` - עודכן עם ייבוא כל הסכמות הדרושות
2. `app/routers/client.py` - תוקן ייבוא הסכמות
3. `app/routers/clients.py` - תוקן ייבוא הסכמות
4. `app/routers/scenarios.py` - תוקן ייבוא הסכמות

## סקריפטים חדשים שנוצרו

1. `run_minimal.py` - אפליקציה מינימלית לבדיקה
2. `diagnose_server.py` - סקריפט לאבחון בעיות
3. `run_server.bat` - סקריפט להפעלת השרת
4. `UPDATED_SERVER_INSTRUCTIONS.md` - הוראות הפעלה מעודכנות (קובץ זה)
