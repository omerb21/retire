@echo off
echo מפעיל את שרת ה-API של מערכת תכנון הפרישה...
echo.

REM הפעלת הסביבה הוירטואלית
call venv\Scripts\activate

REM הפעלת השרת
echo השרת יהיה זמין בכתובת: http://127.0.0.1:8000
echo תיעוד ה-API זמין בכתובת: http://127.0.0.1:8000/docs
echo בדיקת בריאות המערכת: http://127.0.0.1:8000/health
echo.
echo לחץ Ctrl+C לעצירת השרת.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
