@echo off
echo מפעיל את שרת ה-API של מערכת תכנון הפרישה...
echo.

REM הפעלת הסביבה הוירטואלית
call venv\Scripts\activate

REM הפעלת השרת
echo השרת יהיה זמין בכתובת: http://localhost:8000
echo תיעוד ה-API זמין בכתובת: http://localhost:8000/docs
echo בדיקת בריאות המערכת: http://localhost:8000/health
echo.
echo לחץ Ctrl+C לעצירת השרת.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
